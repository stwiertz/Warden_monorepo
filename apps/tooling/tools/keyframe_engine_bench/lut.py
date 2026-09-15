"""PURE rule-LUT packing + result decoding (AC0c Option A, AC3, AC4).

No GL, no file I/O, no cv2 decode — importable and fully testable without a
graphics context. This module is the parity contract: the CPU pre-resolves each
rule's OpenCV **integer** band bounds exactly as ``tools/common/zones.py`` does,
and the shader compares against those bounds inclusively. Parity with
``cv2.inRange`` comes from *not re-deriving the band on the GPU*.

The 150x3 texture layout (AC0c Option A):

===========  ==================================================================
texel        RGBA channels
===========  ==================================================================
``(i, 0)``   ``x``, ``y``, ``width``, ``height`` — reference-res px, as floats
``(i, 1)``   ``h_lo``, ``h_hi``, ``s_lo``, ``s_hi`` — OpenCV int space, as floats
``(i, 2)``   ``v_lo``, ``v_hi``, ``min_ratio``, ``mode``
===========  ==================================================================

``mode`` mirrors ``band_inrange_ratio``'s three branches 1:1:

* ``0`` normal      — ``h_lo..h_hi`` inclusive
* ``1`` wrap        — ``h_lo < 0 or h_hi > 179``; two sub-intervals
* ``2`` full-circle — ``h_hi - h_lo >= 180``; hue is not tested at all

``weight`` / ``weight_override`` deliberately never enter the shader (AC4):
combination logic is CPU-side. They travel on :class:`RuleRef` instead.
"""

from dataclasses import dataclass

import numpy as np

from tools.common.zones import hsv_user_to_cv, tol_h_user_to_cv, tol_sv_user_to_cv

# AC4: the shader's rules texture is 150 wide and the render target is 150x1.
# 134 rules ship today; `bastion` has no corpus and no config entry, so a 14th
# map would push to ~140+. Sized from the config at runtime — never hardcode a
# rule count — but the texture width is the fixed engine ceiling.
MAX_RULES = 150

# The shader's per-rect pixel loop is bounded (ES 3.00 needs a constant bound,
# and an unbounded loop over a malformed rect would hang the GPU). MUST stay in
# lockstep with MAX_RECT_TEXELS in keyframe_engine_bench.frag: above the cap the
# loop truncates while `ratio` still divides by the full area, so a rule would
# silently under-fire rather than fail. `pack_rules` rejects such rects.
# Shipped rects are 1-25 px (mode 2x2), so the cap is ~164x headroom today.
MAX_RECT_TEXELS = 4096

# Padding texels (rules n_rules..149) get this as their min_ratio. A ratio is
# definitionally in [0, 1], so `step(_PAD_MIN_RATIO, ratio)` is always 0 and an
# unused texel can never read back as fired.
_PAD_MIN_RATIO = 2.0

# Band-evaluation modes — must stay in lockstep with the .frag's MODE_* consts.
MODE_NORMAL = 0
MODE_WRAP = 1
MODE_FULL_CIRCLE = 2

# Texel rows of the rules texture.
_N_ROWS = 3


@dataclass(frozen=True)
class RuleRef:
    """Texel index ``i`` -> the zone it came from (AC8b).

    CPU-side aggregation depends on this ordering, so :func:`pack_rules` returns
    it alongside the texture. ``kind`` is Tool 9's ``ZoneSpec.kind``
    (``hud_version`` | ``in_match`` | ``map``) and selects which of AC13's three
    per-classifier formulas the fire feeds.
    """

    texel: int
    owning_class: str
    zone_id: str
    kind: str
    effective_weight: float


@dataclass(frozen=True)
class PackedRules:
    """A packed rules texture + the texel->zone index that decodes its results."""

    texture: np.ndarray          # (MAX_RULES, 3, 4) float32 — GL upload-ready
    refs: tuple[RuleRef, ...]    # len == n_rules, ordered by texel index
    n_rules: int

    @property
    def rule_ids(self) -> tuple[tuple[str, str], ...]:
        """``(owning_class, zone_id)`` per texel — Tool 9's ``zone_fires`` key."""
        return tuple((r.owning_class, r.zone_id) for r in self.refs)


def resolve_band_bounds(band) -> tuple[int, int, int, int, int, int, int]:
    """One zone's HSV band -> ``(h_lo, h_hi, s_lo, s_hi, v_lo, v_hi, mode)``.

    Reuses ``zones.py``'s conversions VERBATIM — do not re-derive them here.

    The center/tolerance asymmetry is the #1 shader-port trap and is load-bearing:
    ``hsv_user_to_cv`` applies ``% 180`` (correct for a hue *center* — a position
    on the circle) while ``tol_h_user_to_cv`` does NOT (a tolerance is a
    *magnitude*; modding it would silently collapse wide bands, e.g. h_tol=380
    -> 10). Values >= 90 CV units saturate the circle and are clamped, not wrapped.

    ``h_lo``/``h_hi`` are returned RAW (unwrapped, possibly negative or > 179) —
    the shader derives ``mod(h, 180)`` itself for the wrap branch, and GLSL's
    ``mod()`` is floored like Python's ``%``, so the two sub-intervals
    reconstruct exactly.
    """
    h_c, s_c, v_c = hsv_user_to_cv(band.h_center, band.s_center, band.v_center)
    h_t = tol_h_user_to_cv(band.h_tol)      # magnitude — NO % 180; clamped to 90
    s_t = tol_sv_user_to_cv(band.s_tol)
    v_t = tol_sv_user_to_cv(band.v_tol)
    h_lo, h_hi = int(round(h_c - h_t)), int(round(h_c + h_t))
    s_lo, s_hi = max(0, int(round(s_c - s_t))), min(255, int(round(s_c + s_t)))
    v_lo, v_hi = max(0, int(round(v_c - v_t))), min(255, int(round(v_c + v_t)))

    # Branch selection order mirrors band_inrange_ratio exactly: full-circle is
    # tested FIRST, so a band that is both >= 180 wide and out of [0,179] is
    # full-circle, not wrap.
    if (h_hi - h_lo) >= 180:
        mode = MODE_FULL_CIRCLE
    elif h_lo < 0 or h_hi > 179:
        mode = MODE_WRAP
    else:
        mode = MODE_NORMAL
    return h_lo, h_hi, s_lo, s_hi, v_lo, v_hi, mode


def _iter_zones(config):
    """Every zone in the config, in the canonical texel order.

    HUD-version zones, then in_match zones, then map zones in config insertion
    order (REL-005 preserves that order on load). This mirrors Tool 9's
    ``evaluate_frame`` evaluation order so the two are trivially comparable.
    """
    yield from config.hud_version_detection
    yield from config.in_match_detection
    for zones in config.map_zones.values():
        yield from zones


def pack_rules(config, frame_shape) -> PackedRules:
    """``MapConfig`` -> a GL-upload-ready ``(150, 3, 4)`` float32 rules texture.

    ``frame_shape`` is ``(h, w[, c])`` of the frame the rules will be evaluated
    against; every rect is clamped to it HERE, CPU-side, where
    ``Rect.clamp_to`` is reused verbatim.

    Clamping in the packer is part of the parity contract, not a nicety: Tool 9
    clamps each rect before evaluating and ``band_inrange_ratio`` divides by the
    **clamped** ``mask.size``, not the declared ``width x height``. A naive
    ``ratio = count / (w*h)`` in the shader would diverge the moment a zone is
    drawn off-edge. ``Rect.clamp_to`` returns a 0-area rect when fully
    off-frame, and a 0-area rect yields ``ratio = 0.0`` — which the shader then
    still feeds through the same ``ratio >= min_ratio`` test, exactly as
    ``zone_fires_on_frame`` does (so a hypothetical ``min_ratio == 0`` rule
    fires on both paths identically).

    Today this is latent: 0 of the 134 shipped rects exceed 1920x1080.

    Raises:
        ValueError: if the config carries more than :data:`MAX_RULES` rules, or
            if any clamped rect exceeds :data:`MAX_RECT_TEXELS` pixels.
    """
    zones = list(_iter_zones(config))
    n_rules = len(zones)
    if n_rules > MAX_RULES:
        raise ValueError(
            f"config carries {n_rules} rules but the engine's rules texture is "
            f"{MAX_RULES} wide (AC4). Widen MAX_RULES here and in "
            f"keyframe_engine_bench.frag together, or split the config."
        )

    # Padding texels are pre-filled with an UNREACHABLE min_ratio rather than
    # left at zero. A zeroed rule has area 0 -> ratio 0.0 and min_ratio 0.0, and
    # `step(0.0, 0.0)` is 1.0 -- so every padding texel would read back as
    # *fired*. Harmless while `decode_results` slices [:n_rules], but it is a
    # landmine for any consumer that reads the full 150-wide readback.
    # `_PAD_MIN_RATIO > 1.0` is unreachable for a ratio in [0, 1], so padding
    # reads back 0 without special-casing area == 0 in the shader -- which must
    # NOT be done, because a genuinely off-frame rule with min_ratio == 0 fires
    # on the CPU (`band_inrange_ratio` -> 0.0, `0.0 >= 0.0`) and must fire here.
    texture = np.zeros((MAX_RULES, _N_ROWS, 4), dtype=np.float32)
    texture[:, 2, 2] = _PAD_MIN_RATIO
    refs: list[RuleRef] = []

    for i, z in enumerate(zones):
        rect = z.rect.clamp_to(frame_shape)
        area = rect.width * rect.height
        if area > MAX_RECT_TEXELS:
            raise ValueError(
                f"zone {z.id!r} ({z.owning_class}) clamps to "
                f"{rect.width}x{rect.height} = {area} px, but the shader's "
                f"per-rect loop is capped at MAX_RECT_TEXELS={MAX_RECT_TEXELS}. "
                f"Above the cap the loop truncates while `ratio` still divides "
                f"by the full area, so the rule SILENTLY under-fires instead of "
                f"failing — a parity break, not an error. Raise "
                f"MAX_RECT_TEXELS here and in keyframe_engine_bench.frag "
                f"together (they must match), or shrink the zone."
            )
        h_lo, h_hi, s_lo, s_hi, v_lo, v_hi, mode = resolve_band_bounds(z.band)

        texture[i, 0] = (rect.x, rect.y, rect.width, rect.height)
        texture[i, 1] = (h_lo, h_hi, s_lo, s_hi)
        # min_ratio explicitly from the zone — never HsvBand's 0.3 class default.
        texture[i, 2] = (v_lo, v_hi, z.band.min_ratio, mode)

        refs.append(
            RuleRef(
                texel=i,
                owning_class=z.owning_class,
                zone_id=z.id,
                kind=z.kind,
                effective_weight=float(z.effective_weight),
            )
        )

    return PackedRules(texture=texture, refs=tuple(refs), n_rules=n_rules)


def decode_results(rgba8: np.ndarray, n_rules: int) -> list[bool]:
    """``(1, 150, 4)`` (or ``(150, 4)``) RGBA8 readback -> one bool per rule.

    The render target is RGBA8, NOT RGBA32F: RGBA32F is texture-only and is not
    color-renderable in ES 3.0 core (it needs ``EXT_color_buffer_float``), and
    ``glReadPixels`` guarantees only ``GL_RGBA``/``GL_UNSIGNED_BYTE``. The
    shader writes 1.0/0.0, which quantizes to 255/0.

    Threshold is ``> 127``, never ``== 255`` — an exact-equality test would be
    hostage to any driver's rounding of 1.0 -> 254.
    """
    arr = np.asarray(rgba8)
    flat = arr.reshape(-1, 4)
    if flat.shape[0] < n_rules:
        raise ValueError(
            f"readback holds {flat.shape[0]} texels, need at least {n_rules}"
        )
    return [bool(v > 127) for v in flat[:n_rules, 0]]
