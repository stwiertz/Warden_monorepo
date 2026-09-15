"""Tool 12 — Keyframe Engine Bench (Story 12.1) pure-logic tests (AC16).

NO GL context, NO real video decode, NO Tk, NO PIL. The GL context is the
analogue of Tk here: ``tools.keyframe_engine_bench.shader`` imports moderngl
lazily precisely so the pure seams stay testable on a box with no driver, and
nothing in this file constructs a :class:`MegaShader`.

The decoder is mocked with synthetic BGR frames (9.13 precedent).

Coverage per AC16: LUT packing, result decoding, all three hue branches
(including h_tol=180 full-circle and a 0/1-crossing wrap case), min_ratio
quantization at 1x1 and 2x2 rects, the phase state machine, circular-buffer N-2
emission, and the doubt outcome.
"""

import numpy as np
import pytest

from tools.common.zones import HsvBand, Rect, band_inrange_ratio
from tools.keyframe_engine_bench import frames as frames_mod
from tools.keyframe_engine_bench import phases as phases_mod
from tools.keyframe_engine_bench.lut import (
    MAX_RECT_TEXELS,
    MAX_RULES,
    MODE_FULL_CIRCLE,
    MODE_NORMAL,
    MODE_WRAP,
    decode_results,
    pack_rules,
    resolve_band_bounds,
)
from tools.keyframe_engine_bench.scoring import score_from_fires
from tools.keyframe_engine_bench.shader import (
    VERSION_DESKTOP,
    VERSION_ES,
    build_source,
    read_frag_body,
)
from tools.roi_detection_tester import ZoneSpec


def _zone(zid, owning, kind, rect, band):
    return ZoneSpec(
        id=zid, owning_class=owning, kind=kind, rect=rect, band=band,
        weight=1.0, weight_override=None,
    )


def _band(h_center=180, h_tol=20, s_center=50, s_tol=20, v_center=50, v_tol=20,
          min_ratio=0.3):
    return HsvBand(
        h_center=h_center, h_tol=h_tol, s_center=s_center, s_tol=s_tol,
        v_center=v_center, v_tol=v_tol, min_ratio=min_ratio,
    )


class _FakeConfig:
    """Minimal stand-in for Tool 9's MapConfig — no file, no cv2."""

    def __init__(self, hud=(), in_match=(), maps=None):
        self.hud_version = "v2"
        self.ref_height = 1080
        self.hud_version_detection = list(hud)
        self.in_match_detection = list(in_match)
        self.identification_threshold = 0.6
        self.minimap_id = "test"
        self.minimap_roi = Rect(0, 0, 1, 1)
        self.map_zones = dict(maps or {})


# ---------------------------------------------------------------------------
# resolve_band_bounds — the three branches (AC7)
# ---------------------------------------------------------------------------


class TestBandBranches:
    def test_full_circle_when_tolerance_spans_the_hue_wheel(self):
        # h_tol=180 user = 90 CV units (clamped), so h_hi - h_lo = 180 >= 180.
        # 68 of the 134 shipped rules take this branch — every low-saturation
        # (white/grey) zone surrendered hue via the accepted tuning decision.
        *_, mode = resolve_band_bounds(_band(h_center=0, h_tol=180))
        assert mode == MODE_FULL_CIRCLE

    def test_full_circle_takes_precedence_over_wrap(self):
        # A band that is BOTH >= 180 wide and out of [0,179] must resolve to
        # full-circle, mirroring band_inrange_ratio's branch ORDER (it tests
        # the width first). Getting this backwards would evaluate two sliver
        # sub-intervals instead of "match any hue".
        h_lo, h_hi, *_, mode = resolve_band_bounds(_band(h_center=100, h_tol=180))
        assert (h_hi - h_lo) >= 180 and (h_lo < 0 or h_hi > 179)
        assert mode == MODE_FULL_CIRCLE

    def test_wrap_when_band_crosses_zero(self):
        # h_center=10 user -> 5 CV; h_tol=40 user -> 20 CV; h_lo = -15 < 0.
        h_lo, h_hi, *_, mode = resolve_band_bounds(_band(h_center=10, h_tol=40))
        assert mode == MODE_WRAP
        assert h_lo < 0
        assert h_lo % 180 == 165  # the [165,179] u [0,25] sub-intervals

    def test_wrap_when_band_crosses_179(self):
        h_lo, h_hi, *_, mode = resolve_band_bounds(_band(h_center=350, h_tol=40))
        assert mode == MODE_WRAP
        assert h_hi > 179

    def test_normal_band(self):
        h_lo, h_hi, *_, mode = resolve_band_bounds(_band(h_center=180, h_tol=20))
        assert mode == MODE_NORMAL
        assert (h_lo, h_hi) == (80, 100)

    def test_hue_tolerance_is_a_magnitude_not_a_position(self):
        """The #1 shader-port trap: tol_h_user_to_cv must NOT mod by 180.

        A tolerance of 380 user-degrees is a *wide* band; modding it would
        collapse it to 10 CV units — a narrow sliver — and silently break the
        rule. It must clamp to 90 (full circle) instead.
        """
        _, _, *_, mode = resolve_band_bounds(_band(h_center=0, h_tol=380))
        assert mode == MODE_FULL_CIRCLE

    def test_sv_bounds_are_clamped_to_the_byte_range(self):
        _, _, s_lo, s_hi, v_lo, v_hi, _ = resolve_band_bounds(
            _band(s_center=0, s_tol=100, v_center=100, v_tol=100)
        )
        assert (s_lo, s_hi) == (0, 255)
        assert (v_lo, v_hi) == (0, 255)


# ---------------------------------------------------------------------------
# pack_rules (AC0c, AC4)
# ---------------------------------------------------------------------------


class TestPackRules:
    def test_layout_and_texel_order(self):
        cfg = _FakeConfig(
            hud=[_zone("h0", "v2", "hud_version", Rect(1, 2, 3, 4), _band())],
            in_match=[_zone("i0", "in_match", "in_match", Rect(5, 6, 7, 8), _band())],
            maps={"artefact": [_zone("a0", "artefact", "map", Rect(9, 10, 11, 12), _band())]},
        )
        packed = pack_rules(cfg, (1080, 1920, 3))

        assert packed.n_rules == 3
        assert packed.texture.shape == (MAX_RULES, 3, 4)
        assert packed.texture.dtype == np.float32
        # HUD, then in_match, then maps — mirrors Tool 9's evaluation order.
        assert [r.kind for r in packed.refs] == ["hud_version", "in_match", "map"]
        assert packed.rule_ids == (("v2", "h0"), ("in_match", "i0"), ("artefact", "a0"))
        # texel (i,0) carries the rect
        assert list(packed.texture[0, 0]) == [1, 2, 3, 4]
        assert list(packed.texture[1, 0]) == [5, 6, 7, 8]

    def test_min_ratio_is_packed_per_zone_never_the_class_default(self):
        # HsvBand defaults min_ratio to 0.3; a zone carrying 0.75 must survive.
        cfg = _FakeConfig(hud=[_zone("h0", "v2", "hud_version", Rect(0, 0, 2, 2),
                                     _band(min_ratio=0.75))])
        packed = pack_rules(cfg, (1080, 1920, 3))
        assert packed.texture[0, 2][2] == pytest.approx(0.75)

    def test_rects_are_clamped_to_the_frame(self):
        # Off-edge rect: the shader's denominator must be the CLAMPED area,
        # because band_inrange_ratio divides by the clamped mask.size.
        cfg = _FakeConfig(hud=[_zone("h0", "v2", "hud_version", Rect(1918, 1078, 10, 10), _band())])
        packed = pack_rules(cfg, (1080, 1920, 3))
        assert list(packed.texture[0, 0]) == [1918, 1078, 2, 2]

    def test_fully_off_frame_rect_packs_zero_area(self):
        cfg = _FakeConfig(hud=[_zone("h0", "v2", "hud_version", Rect(5000, 5000, 4, 4), _band())])
        packed = pack_rules(cfg, (1080, 1920, 3))
        w, h = packed.texture[0, 0][2], packed.texture[0, 0][3]
        assert w * h == 0

    def test_unused_texels_are_inert(self):
        """Padding carries an UNREACHABLE min_ratio, not a zero one.

        Zeroing the whole texel looks tidier but makes padding *fire*: area 0 ->
        ratio 0.0 against min_ratio 0.0, and `step(0.0, 0.0)` is 1.0. Everything
        except the min_ratio slot is still zero; that slot is > 1.0, which no
        ratio can reach. See TestPaddingTexels for the behavioural assertion.
        """
        cfg = _FakeConfig(hud=[_zone("h0", "v2", "hud_version", Rect(0, 0, 1, 1), _band())])
        packed = pack_rules(cfg, (1080, 1920, 3))
        pad = packed.texture[1:]
        assert (pad[:, 2, 2] > 1.0).all()          # min_ratio slot: unreachable
        assert not pad[:, :2, :].any()             # rect + h/s bounds: zero
        assert not pad[:, 2, [0, 1, 3]].any()      # v bounds + mode: zero

    def test_rejects_more_rules_than_the_texture_can_hold(self):
        maps = {
            f"m{i}": [_zone(f"z{i}", f"m{i}", "map", Rect(0, 0, 2, 2), _band())]
            for i in range(MAX_RULES + 1)
        }
        with pytest.raises(ValueError, match="rules texture"):
            pack_rules(_FakeConfig(maps=maps), (1080, 1920, 3))

    def test_effective_weight_prefers_the_override(self):
        z = ZoneSpec(id="z", owning_class="m", kind="map", rect=Rect(0, 0, 2, 2),
                     band=_band(), weight=1.0, weight_override=4.0)
        packed = pack_rules(_FakeConfig(maps={"m": [z]}), (1080, 1920, 3))
        assert packed.refs[0].effective_weight == 4.0


# ---------------------------------------------------------------------------
# decode_results (AC6)
# ---------------------------------------------------------------------------


class TestDecodeResults:
    def test_thresholds_above_127_not_equality_with_255(self):
        rgba = np.zeros((MAX_RULES, 4), dtype=np.uint8)
        rgba[0, 0] = 255
        rgba[1, 0] = 128    # a driver rounding 1.0 down must still read as fired
        rgba[2, 0] = 127
        rgba[3, 0] = 0
        assert decode_results(rgba, 4) == [True, True, False, False]

    def test_accepts_the_1x150x4_readback_shape(self):
        rgba = np.zeros((1, MAX_RULES, 4), dtype=np.uint8)
        rgba[0, 2, 0] = 255
        assert decode_results(rgba, 3) == [False, False, True]

    def test_rejects_a_short_readback(self):
        with pytest.raises(ValueError, match="at least"):
            decode_results(np.zeros((2, 4), dtype=np.uint8), 5)


# ---------------------------------------------------------------------------
# The parity contract: packed bounds vs cv2's own band test
# ---------------------------------------------------------------------------


def _shader_model(texels, frame_bgr):
    """Evaluate ONE packed rule exactly as keyframe_engine_bench.frag does. PURE.

    A faithful CPU model of the shader's per-rule branch: read the three packed
    texels, walk the rect, quantize to OpenCV HSV, apply the mode's hue test
    plus the inclusive S/V bounds, and fire on ``ratio >= min_ratio``.

    Its whole purpose is to be driven from the PACKER'S OUTPUT, so the tests
    below compare Tool 12's own bounds/mode/ratio derivation against
    ``band_inrange_ratio``. Asserting things about ``band_inrange_ratio`` alone
    would only re-test OpenCV — it would pass against an empty package.

    Deliberately NOT a port of the .frag's integer RGB2HSV_b: that is validated
    by its own 2^24 brute force. This isolates the packing contract.
    """
    import cv2

    x, y, w, h = (int(v) for v in texels[0])
    h_lo, h_hi, s_lo, s_hi = (int(v) for v in texels[1])
    v_lo, v_hi = int(texels[2][0]), int(texels[2][1])
    min_ratio, mode = float(texels[2][2]), int(texels[2][3])

    area = w * h
    if area <= 0:
        ratio = 0.0
    else:
        region = frame_bgr[y:y + h, x:x + w]
        hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
        hh, ss, vv = hsv[:, :, 0].astype(int), hsv[:, :, 1].astype(int), hsv[:, :, 2].astype(int)
        if mode == MODE_FULL_CIRCLE:
            hue_ok = np.ones_like(hh, dtype=bool)
        elif mode == MODE_WRAP:
            # GLSL mod() is floored, matching Python's % for negative operands.
            hue_ok = (hh >= (h_lo % 180)) | (hh <= (h_hi % 180))
        else:
            hue_ok = (hh >= h_lo) & (hh <= h_hi)
        in_band = hue_ok & (ss >= s_lo) & (ss <= s_hi) & (vv >= v_lo) & (vv <= v_hi)
        ratio = float(in_band.sum()) / float(area)
    return ratio >= min_ratio, ratio


def _pack_one(band, rect, frame_shape=(1080, 1920, 3)):
    """Pack a single zone and hand back its three texels."""
    cfg = _FakeConfig(hud=[_zone("z", "v2", "hud_version", rect, band)])
    packed = pack_rules(cfg, frame_shape)
    return packed.texture[0]


class TestCpuParityContract:
    """Tool 12's PACKED rule must fire identically to Tool 9's CPU reference.

    This is the CPU half of the parity contract, and it is driven through
    ``pack_rules`` -> ``_shader_model`` so a drift in the packer's bounds, mode
    selection, clamping or min_ratio handling fails HERE rather than as a
    mystery accuracy regression in the bench. (The GPU half needs a context and
    is exercised by the bench run, not the suite — AC16.)
    """

    @pytest.mark.parametrize("h_center,h_tol,expected_mode", [
        (180, 20, MODE_NORMAL),
        (10, 40, MODE_WRAP),
        (0, 180, MODE_FULL_CIRCLE),
    ])
    def test_modes_match_band_inrange_ratio_branch_selection(self, h_center, h_tol,
                                                             expected_mode):
        band = _band(h_center=h_center, h_tol=h_tol)
        *_, mode = resolve_band_bounds(band)
        assert mode == expected_mode

    @pytest.mark.parametrize("h_center,h_tol", [
        (180, 20),      # normal
        (10, 40),       # wrap across 0
        (350, 40),      # wrap across 179
        (0, 180),       # full circle
        (29, 10),       # hud_z02-like: banker's rounding makes the band asymmetric
        (23, 10),       # atlantis_z00-like
    ])
    @pytest.mark.parametrize("seed", [0, 1, 2])
    def test_packed_rule_fires_exactly_when_the_cpu_reference_fires(self, h_center,
                                                                    h_tol, seed):
        """The load-bearing parity assertion: packer output vs cv2.inRange.

        Random content over a 4x4 rect, so ratios land on 0, 1/16, ... 1 and
        straddle min_ratio in both directions. If the packer ever re-derives a
        bound differently from zones.py — the #1 shader-port trap — this fails.
        """
        band = _band(h_center=h_center, h_tol=h_tol, s_center=50, s_tol=40,
                     v_center=50, v_tol=40, min_ratio=0.3)
        rect = Rect(2, 3, 4, 4)
        rng = np.random.default_rng(seed)
        frame = rng.integers(0, 256, (16, 16, 3), dtype=np.uint8)

        gpu_fired, gpu_ratio = _shader_model(_pack_one(band, rect, frame.shape), frame)
        cpu_ratio = band_inrange_ratio(band, rect, frame)
        cpu_fired = cpu_ratio >= band.min_ratio

        assert gpu_ratio == pytest.approx(cpu_ratio)
        assert gpu_fired == cpu_fired

    def test_min_ratio_quantization_on_a_2x2_rect(self):
        """On a 2x2 rect (4 px), `ratio >= 0.3` means >= 2 of 4 pixels.

        min_ratio is dominated by quantization, not by ratio: 1/4 = 0.25 misses
        and 2/4 = 0.50 clears, so 0.3 and 0.49 are the same rule here. Asserted
        on BOTH engines so the quantization is a shared property, not a
        coincidence.
        """
        band = _band(h_center=0, h_tol=180, s_center=0, s_tol=100,
                     v_center=100, v_tol=2, min_ratio=0.3)
        rect = Rect(0, 0, 2, 2)
        img = np.zeros((2, 2, 3), dtype=np.uint8)
        texels = _pack_one(band, rect, img.shape)

        img[0, 0] = 255                      # 1 of 4 in-band -> 0.25 < 0.3
        assert band_inrange_ratio(band, rect, img) == pytest.approx(0.25)
        fired, ratio = _shader_model(texels, img)
        assert ratio == pytest.approx(0.25) and fired is False

        img[0, 1] = 255                      # 2 of 4 -> 0.50 >= 0.3
        assert band_inrange_ratio(band, rect, img) == pytest.approx(0.50)
        fired, ratio = _shader_model(texels, img)
        assert ratio == pytest.approx(0.50) and fired is True

    def test_min_ratio_quantization_on_a_1x1_rect(self):
        """On a 1x1 rect, `ratio >= 0.3` means ANY single in-band pixel.

        Fourteen of the shipped rules are literally w=1,h=1 — a rect with
        w=1,h=1 IS a point (E1), and its min_ratio is effectively binary.
        """
        band = _band(h_center=0, h_tol=180, s_center=0, s_tol=100,
                     v_center=100, v_tol=2, min_ratio=0.3)
        rect = Rect(0, 0, 1, 1)
        black = np.zeros((1, 1, 3), dtype=np.uint8)
        white = np.full((1, 1, 3), 255, dtype=np.uint8)
        assert band_inrange_ratio(band, rect, black) == 0.0
        assert band_inrange_ratio(band, rect, white) == 1.0
        assert _shader_model(_pack_one(band, rect, black.shape), black) == (False, 0.0)
        assert _shader_model(_pack_one(band, rect, white.shape), white) == (True, 1.0)

    def test_zero_area_rect_yields_zero_ratio_on_both_engines(self):
        band = _band()
        img = np.full((4, 4, 3), 128, dtype=np.uint8)
        assert band_inrange_ratio(band, Rect(0, 0, 0, 0), img) == 0.0
        _, ratio = _shader_model(_pack_one(band, Rect(0, 0, 0, 0), img.shape), img)
        assert ratio == 0.0

    def test_off_frame_rect_clamps_and_divides_by_the_clamped_area(self):
        """Tool 9 divides by the CLAMPED mask.size, not the declared w*h.

        Latent today (0 of 134 rects exceed 1920x1080) and a silent parity break
        the moment a zone is drawn off-edge — which is exactly why the clamp
        lives in the packer, CPU-side, where Rect.clamp_to is reused verbatim.
        """
        band = _band(h_center=0, h_tol=180, s_center=0, s_tol=100,
                     v_center=100, v_tol=2, min_ratio=0.3)
        img = np.full((4, 4, 3), 255, dtype=np.uint8)
        rect = Rect(2, 2, 10, 10)            # only the 2x2 bottom-right corner is on-frame
        texels = _pack_one(band, rect, img.shape)
        assert tuple(int(v) for v in texels[0]) == (2, 2, 2, 2)
        fired, ratio = _shader_model(texels, img)
        assert ratio == pytest.approx(band_inrange_ratio(band, rect, img))
        assert ratio == 1.0 and fired is True


# ---------------------------------------------------------------------------
# in_match_call + doubt (AC8)
# ---------------------------------------------------------------------------


class TestInMatchCall:
    def test_unanimous_votes_are_confident(self):
        assert phases_mod.in_match_call(1.0) == phases_mod.CALL_YES
        assert phases_mod.in_match_call(0.0) == phases_mod.CALL_NO

    def test_split_votes_are_doubt_on_the_shipped_three_zone_config(self):
        # 3 in_match zones -> ratios quantize to {0, 1/3, 2/3, 1}.
        assert phases_mod.in_match_call(1.0 / 3.0) == phases_mod.CALL_DOUBT
        assert phases_mod.in_match_call(2.0 / 3.0) == phases_mod.CALL_DOUBT

    def test_zero_margin_reproduces_the_hard_binary_9_13_behaviour(self):
        assert phases_mod.in_match_call(1.0 / 3.0, doubt_margin=0.0) == phases_mod.CALL_NO
        assert phases_mod.in_match_call(2.0 / 3.0, doubt_margin=0.0) == phases_mod.CALL_YES
        assert phases_mod.in_match_call(0.0, doubt_margin=0.0) == phases_mod.CALL_NO


# ---------------------------------------------------------------------------
# Phase state machine (AC8, AC10)
# ---------------------------------------------------------------------------


_Y, _N, _D = phases_mod.CALL_YES, phases_mod.CALL_NO, phases_mod.CALL_DOUBT
_IM = phases_mod.STATE_IN_MATCH
_SS = phases_mod.STATE_SCORE_SCREEN
_NI = phases_mod.STATE_NOT_IN_MATCH
_DB = phases_mod.STATE_DOUBT


def _frames(calls, step_ms=1000):
    return [(i, i * step_ms, c) for i, c in enumerate(calls)]


class TestPhaseStateMachine:
    def test_rising_edge_opens_a_span(self):
        f = _frames([_N, _Y, _Y])
        emitted, internal = phases_mod.resolve_phases(f, 15000)
        assert emitted == [_NI, _IM, _IM]
        assert phases_mod.spans_from_states(f, internal) == [(1, 2)]

    def test_falling_edge_opens_the_score_window(self):
        f = _frames([_Y, _N])
        emitted, _ = phases_mod.resolve_phases(f, 15000)
        assert emitted == [_IM, _SS]

    def test_score_window_closes_after_its_duration(self):
        # step 1000 ms, duration 3000 ms: falling at ts=1000, so ts=4000 closes.
        f = _frames([_Y, _N, _N, _N, _N])
        emitted, _ = phases_mod.resolve_phases(f, 3000)
        assert emitted == [_IM, _SS, _SS, _SS, _NI]

    def test_zero_duration_window_emits_no_score_frames(self):
        """The intent behind video_test.py:613's `0 >= dur`, ported explicitly.

        On the falling-edge frame elapsed time IS zero by definition, so a
        zero-length window is already over and the frame goes straight to
        not_in_match.
        """
        f = _frames([_Y, _N, _N])
        emitted, _ = phases_mod.resolve_phases(f, 0)
        assert emitted == [_IM, _NI, _NI]

    def test_rising_edge_during_score_screen_aborts_the_window(self):
        f = _frames([_Y, _N, _Y])
        emitted, internal = phases_mod.resolve_phases(f, 15000)
        assert emitted == [_IM, _SS, _IM]
        assert phases_mod.spans_from_states(f, internal) == [(0, 0), (2, 2)]

    def test_video_starting_mid_match_opens_a_span_at_the_first_frame(self):
        f = _frames([_Y, _Y])
        _, internal = phases_mod.resolve_phases(f, 15000)
        assert phases_mod.spans_from_states(f, internal) == [(0, 1)]

    def test_span_still_open_at_eof_ends_at_the_last_frame(self):
        f = _frames([_N, _Y, _Y])
        _, internal = phases_mod.resolve_phases(f, 15000)
        assert phases_mod.spans_from_states(f, internal) == [(1, 2)]

    def test_isolated_single_frame_blip_is_a_valid_one_frame_span(self):
        # No debounce is specified and none is invented.
        f = _frames([_N, _Y, _N])
        _, internal = phases_mod.resolve_phases(f, 15000)
        assert phases_mod.spans_from_states(f, internal) == [(1, 1)]


class TestDoubtIsFirstClass:
    def test_doubt_is_emitted_never_forced_to_the_nearest_class(self):
        f = _frames([_Y, _D, _Y])
        emitted, _ = phases_mod.resolve_phases(f, 15000)
        assert emitted == [_IM, _DB, _IM]

    def test_doubt_holds_the_internal_state_and_does_not_split_a_span(self):
        f = _frames([_Y, _D, _Y])
        _, internal = phases_mod.resolve_phases(f, 15000)
        assert internal == [_IM, _IM, _IM]
        assert phases_mod.spans_from_states(f, internal) == [(0, 2)]

    def test_doubt_does_not_stop_the_score_screen_clock(self):
        """Surrounding reliable context still resolves the doubtful stretch.

        The score window was armed by a CONFIDENT falling edge; a doubtful frame
        must not freeze that timer, or an unreliable frame could hold the
        timeline in score_screen indefinitely.
        """
        f = _frames([_Y, _N, _D, _D, _N])
        emitted, internal = phases_mod.resolve_phases(f, 2000)
        assert emitted == [_IM, _SS, _DB, _DB, _NI]
        assert internal[3] == _NI    # clock expired underneath the doubt

    def test_doubt_from_the_start_never_opens_a_span(self):
        f = _frames([_D, _D])
        emitted, internal = phases_mod.resolve_phases(f, 15000)
        assert emitted == [_DB, _DB]
        assert phases_mod.spans_from_states(f, internal) == []

    def test_doubt_state_is_in_the_extended_timeline_enum(self):
        # AC10 verdict: extend 9.13's enum rather than map doubt -> not_in_match.
        assert _DB in phases_mod.TIMELINE_STATES
        assert set(phases_mod.TIMELINE_STATES) == {_IM, _SS, _NI, _DB}


# ---------------------------------------------------------------------------
# Circular buffer (AC9)
# ---------------------------------------------------------------------------


class TestKeyframeRing:
    def test_emits_frame_n_minus_2(self):
        ring = phases_mod.KeyframeRing()
        for i in range(3):
            ring.push(i, i * 1000, np.full((2, 2, 3), i, dtype=np.uint8))
        idx, ts, frame = ring.retro()
        assert (idx, ts) == (0, 0)
        assert frame[0, 0, 0] == 0

    def test_returns_none_until_three_keyframes_are_seen(self):
        ring = phases_mod.KeyframeRing()
        assert ring.retro() is None
        ring.push(0, 0, np.zeros((1, 1, 3), dtype=np.uint8))
        assert ring.retro() is None
        ring.push(1, 1000, np.zeros((1, 1, 3), dtype=np.uint8))
        assert ring.retro() is None

    def test_never_holds_more_than_three_frames(self):
        # 1061 keyframes x 6.2 MB = 6.6 GB if this ever grows.
        ring = phases_mod.KeyframeRing()
        for i in range(50):
            ring.push(i, i * 1000, np.zeros((1, 1, 3), dtype=np.uint8))
        assert len(ring) == 3
        assert ring.retro()[0] == 47


# ---------------------------------------------------------------------------
# Frame-source seam (AC8b) — decoder mocked, never a real decode
# ---------------------------------------------------------------------------


class TestVideoFrameSource:
    def test_streams_keyframes_with_millisecond_timestamps(self):
        def fake_extractor(path, profile_stats=None):
            for i in range(3):
                yield np.full((1080, 1920, 3), i, dtype=np.uint8), i * 4.166667

        out = list(frames_mod.iter_video_keyframes(
            "nonexistent.mp4", 1080, extractor=fake_extractor
        ))
        assert [f.frame_idx for f in out] == [0, 1, 2]
        assert [f.timestamp_ms for f in out] == [0, 4167, 8333]
        assert out[0].frame_bgr.shape == (1080, 1920, 3)

    def test_does_not_resize_a_frame_already_at_reference_height(self):
        """AC5 — do not scale twice. At 1920x1080 -> 1080 this is a no-op and
        _resize_to_ref returns the same object (no copy, no resample)."""
        src = np.full((1080, 1920, 3), 7, dtype=np.uint8)

        def fake_extractor(path, profile_stats=None):
            yield src, 0.0

        out = list(frames_mod.iter_video_keyframes(
            "x.mp4", 1080, extractor=fake_extractor
        ))
        assert out[0].frame_bgr is src

    def test_is_lazy_and_never_accumulates(self):
        pushed = []

        def fake_extractor(path, profile_stats=None):
            for i in range(1000):
                pushed.append(i)
                yield np.zeros((1080, 1920, 3), dtype=np.uint8), float(i)

        gen = frames_mod.iter_video_keyframes("x.mp4", 1080, extractor=fake_extractor)
        next(gen)
        assert len(pushed) == 1    # generator, not a materialized list


class TestLabeledFrameSource:
    def test_missing_root_yields_nothing(self):
        assert list(frames_mod.iter_labeled_frames("does/not/exist", 1080)) == []

    def test_reads_pngs_in_sorted_hud_class_file_order(self, tmp_path):
        import cv2

        for cls in ("lobby", "artefact"):
            d = tmp_path / "v2" / cls
            d.mkdir(parents=True)
            for name in ("b.png", "a.png"):
                img = np.full((1080, 1920, 3), 9, dtype=np.uint8)
                ok, buf = cv2.imencode(".png", img)
                assert ok
                (d / name).write_bytes(buf.tobytes())

        out = list(frames_mod.iter_labeled_frames(str(tmp_path), 1080))
        assert [(f.folder, f.path.split("\\")[-1].split("/")[-1]) for f in out] == [
            ("artefact", "a.png"), ("artefact", "b.png"),
            ("lobby", "a.png"), ("lobby", "b.png"),
        ]
        assert [f.frame_idx for f in out] == [0, 1, 2, 3]
        assert all(f.hud_dir == "v2" for f in out)

    def test_skips_non_hud_directories(self, tmp_path):
        (tmp_path / "notes").mkdir()
        assert list(frames_mod.iter_labeled_frames(str(tmp_path), 1080)) == []


# ---------------------------------------------------------------------------
# Shader source assembly (AC6) — text only, no context
# ---------------------------------------------------------------------------


def _code_only(src: str) -> str:
    """GLSL with ``//`` comments stripped.

    The .frag documents the ES-3.0 rules in prose, so it legitimately *mentions*
    gl_FragColor and texture2D in comments. These checks are about the CODE.
    """
    return "\n".join(line.split("//", 1)[0] for line in src.splitlines())


class TestShaderSource:
    def test_only_the_version_line_differs_between_dialects(self):
        body = read_frag_body()
        es = build_source(body, VERSION_ES)
        desktop = build_source(body, VERSION_DESKTOP)
        assert es.split("\n", 1)[1] == desktop.split("\n", 1)[1]
        assert es.startswith("#version 300 es")
        assert desktop.startswith("#version 330 core")

    def test_body_carries_no_version_line_of_its_own(self):
        assert "#version" not in _code_only(read_frag_body())

    def test_body_holds_the_mandatory_es_precision_statements(self):
        body = read_frag_body()
        assert "precision highp float;" in body
        assert "precision highp int;" in body
        # sampler2D defaults to LOWP in the ES fragment language — which would
        # shred both the RGBA32F rule bounds and the 8-bit frame.
        assert "precision highp sampler2D;" in body

    def test_body_avoids_the_es_3_0_incompatible_constructs(self):
        code = _code_only(read_frag_body())
        assert "gl_FragColor" not in code      # out vec4 only
        assert "texture2D(" not in code        # texture()/texelFetch() only
        assert "layout(location" not in code   # banned on uniforms in both
        assert "out vec4" in code

    def test_profile_gpu_and_gate_glsl_need_no_video(self):
        """Both are diagnostic modes; argparse must accept them bare.

        `--profile-gpu` exists because the run output's upload/shader split is
        misattributed (GL uploads are async, so the blocking readback absorbs the
        tail of the transfer). It is the number 12.2/12.3 need.
        """
        from tools.keyframe_engine_bench.__main__ import _parse_args

        assert _parse_args(["--profile-gpu"]).video is None
        assert _parse_args(["--gate-glsl"]).gate_glsl is True
        assert _parse_args(["--profile-gpu"]).profile_gpu is True

    def test_body_uses_float_mod_not_integer_modulo_for_hue_wrap(self):
        """Integer `%` is UNDEFINED for negative operands in ES 3.00.

        h_lo can be negative (that is exactly what the wrap branch means), so an
        integer `%` here would be undefined behaviour that happens to work on
        desktop — precisely the class of bug AC6 exists to prevent.
        """
        code = _code_only(read_frag_body())
        assert "mod(float(h_lo)" in code
        assert "h_lo %" not in code
        assert "h_hi %" not in code


# ---------------------------------------------------------------------------
# scoring.py — Tool 9's THREE per-classifier formulas (AC13)
# ---------------------------------------------------------------------------


class TestPerClassifierScoring:
    """AC13's central trap: Tool 9 uses THREE different formulas, not one.

    `sprint-change-proposal-2026-07-16.md:285`'s "Tool 9 sums raw weighted" is
    true of the MAP-ID classifier only. Implementing that form everywhere
    silently breaks two of the three accuracy numbers — and it breaks them as
    plausible numbers, not as an error. These lock each formula independently so
    swapping one for another fails here instead of in a live bench run.
    """

    def _packed(self, n_hud=4, n_im=4, maps=None):
        rect, band = Rect(0, 0, 2, 2), _band()
        cfg = _FakeConfig(
            hud=[_zone(f"h{i}", "v2", "hud_version", rect, band) for i in range(n_hud)],
            in_match=[_zone(f"m{i}", "v2", "in_match", rect, band) for i in range(n_im)],
            maps={
                slug: [_zone(f"{slug}_z{i}", slug, "map", rect, band) for i in range(n)]
                for slug, n in (maps or {}).items()
            },
        )
        return cfg, pack_rules(cfg, (1080, 1920, 3))

    def test_hud_version_is_normalized_by_zone_count_and_unweighted(self):
        cfg, packed = self._packed(n_hud=4, n_im=0)
        fires = [True, True, False, False]        # 2 of 4
        sc = score_from_fires(fires, packed, cfg)
        assert sc.hud_conf == pytest.approx(0.5)  # fires / n_hud — NOT a raw sum

    def test_in_match_is_normalized_then_hard_binary_never_unknown(self):
        """The classifier that drives the phase machine never returns unknown.

        This is precisely why AC8's doubt has no upstream `unknown` to inherit
        and had to be INTRODUCED by 12.1 (roi_detection_tester.py:725-729).
        """
        cfg, packed = self._packed(n_hud=0, n_im=4)
        assert score_from_fires([True, True, False, False], packed, cfg).pred_in_match == "in_match"
        assert score_from_fires([True, False, False, False], packed, cfg).pred_in_match == "not_in_match"
        for pattern in ([False] * 4, [True] * 4, [True, False, True, False]):
            assert score_from_fires(pattern, packed, cfg).pred_in_match in ("in_match", "not_in_match")

    def test_map_id_is_a_RAW_unnormalized_weighted_sum(self):
        """Raw, so confidence is unbounded and NOT comparable to the other two.

        Finding 3's degeneracy, reproduced as-is rather than "fixed" (9.16's
        call): every shipped rule carries weight 1.0, so this reduces to a plain
        count of fired zones and `identification_threshold = 0.6` on an
        unnormalized sum is near-inert.
        """
        cfg, packed = self._packed(n_hud=0, n_im=0, maps={"atlantis": 5})
        sc = score_from_fires([True] * 3 + [False] * 2, packed, cfg)
        # 3 fired x weight 1.0 = 3.0 — a COUNT, not 3/5 = 0.6.
        assert sc.map_scores["atlantis"] == pytest.approx(3.0)
        assert sc.map_conf == pytest.approx(3.0)

    def test_the_three_formulas_disagree_on_identical_fire_patterns(self):
        """The regression that matters: one formula used everywhere still yields
        each classifier's *shape* while producing the wrong number for two.
        """
        cfg, packed = self._packed(n_hud=4, n_im=4, maps={"atlantis": 4})
        fires = [True, True, False, False] * 3     # 2 of 4 in every group
        sc = score_from_fires(fires, packed, cfg)
        assert sc.hud_conf == pytest.approx(0.5)                 # normalized
        assert sc.in_match_conf == pytest.approx(0.5)            # normalized
        assert sc.map_scores["atlantis"] == pytest.approx(2.0)   # RAW

    def test_map_scores_carries_every_slug_that_has_zones(self):
        """Load-bearing for the span aggregation in _run_video: because a slug
        with zones always gets an entry (0.0 when nothing fired), a span-level
        `if agg:` is always true and its `unknown` branch is unreachable.
        """
        cfg, packed = self._packed(n_hud=0, n_im=0, maps={"atlantis": 2, "the_cliff": 2})
        sc = score_from_fires([False] * 4, packed, cfg)
        assert set(sc.map_scores) == {"atlantis", "the_cliff"}
        assert all(v == 0.0 for v in sc.map_scores.values())

    def test_rejects_a_fire_vector_that_would_misalign_texel_order(self):
        cfg, packed = self._packed(n_hud=2, n_im=0)
        with pytest.raises(ValueError, match="texel order"):
            score_from_fires([True], packed, cfg)


# ---------------------------------------------------------------------------
# Review-hardening guards (code review 2026-07-19)
# ---------------------------------------------------------------------------


class TestRectAreaCap:
    """A rect above the shader's loop cap must FAIL, not silently under-fire.

    The shader caps its loop at MAX_RECT_TEXELS but `ratio` divides by the full
    area, so an oversized rect can never exceed MAX_RECT_TEXELS/area — it
    diverges from the CPU as a wrong number rather than an error. The packer is
    where that becomes unreachable.
    """

    def test_rejects_a_rect_larger_than_the_shader_loop_cap(self):
        big = Rect(0, 0, 100, 100)           # 10_000 px > 4096
        cfg = _FakeConfig(hud=[_zone("z", "v2", "hud_version", big, _band())])
        with pytest.raises(ValueError, match="MAX_RECT_TEXELS"):
            pack_rules(cfg, (1080, 1920, 3))

    def test_accepts_a_rect_exactly_at_the_cap(self):
        exact = Rect(0, 0, 64, 64)           # 4096 px
        cfg = _FakeConfig(hud=[_zone("z", "v2", "hud_version", exact, _band())])
        assert pack_rules(cfg, (1080, 1920, 3)).n_rules == 1

    def test_the_cap_matches_the_shader_constant(self):
        """Two constants, one contract — drift here is a silent parity break."""
        assert f"const int MAX_RECT_TEXELS = {MAX_RECT_TEXELS};" in read_frag_body()

    def test_the_cap_is_applied_to_the_CLAMPED_area_not_the_declared_one(self):
        """A huge rect mostly off-frame clamps small and must be accepted."""
        cfg = _FakeConfig(
            hud=[_zone("z", "v2", "hud_version", Rect(1900, 1070, 500, 500), _band())]
        )
        assert pack_rules(cfg, (1080, 1920, 3)).n_rules == 1


class TestPaddingTexels:
    def test_unused_texels_can_never_read_back_as_fired(self):
        """A zeroed texel would have area 0 -> ratio 0.0 AND min_ratio 0.0, and
        `step(0.0, 0.0)` is 1.0 — so every padding texel would read as *fired*.
        Harmless only while decode_results slices [:n_rules]; a landmine for any
        consumer that reads the full 150-wide readback.
        """
        cfg = _FakeConfig(hud=[_zone("z", "v2", "hud_version", Rect(0, 0, 2, 2), _band())])
        packed = pack_rules(cfg, (1080, 1920, 3))
        frame = np.zeros((16, 16, 3), dtype=np.uint8)
        for i in range(packed.n_rules, MAX_RULES):
            fired, _ = _shader_model(packed.texture[i], frame)
            assert fired is False, f"padding texel {i} fired"

    def test_a_real_zero_area_rule_with_zero_min_ratio_STILL_fires(self):
        """The padding fix must not change real-rule semantics: an off-frame
        rule with min_ratio 0 fires on the CPU (band_inrange_ratio -> 0.0, and
        `0.0 >= 0.0`), so it must fire here too.
        """
        band = _band(min_ratio=0.0)
        img = np.zeros((4, 4, 3), dtype=np.uint8)
        fired, ratio = _shader_model(_pack_one(band, Rect(50, 50, 4, 4), img.shape), img)
        assert ratio == 0.0 and fired is True


class TestDoubtMarginBounds:
    def test_a_margin_at_or_above_the_threshold_is_rejected(self):
        """Every ratio in (0,1) would fall inside the band -> every frame calls
        doubt -> the machine only advances on exactly 0.0 or 1.0. That is a
        silently useless run, so the CLI refuses it.
        """
        from tools.keyframe_engine_bench.__main__ import main

        assert main(["video.mp4", "--doubt-margin", "0.5"]) == 2
        assert main(["video.mp4", "--doubt-margin", "0.9"]) == 2

    def test_a_negative_margin_is_rejected(self):
        from tools.keyframe_engine_bench.__main__ import main

        assert main(["video.mp4", "--doubt-margin", "-0.1"]) == 2

    def test_zero_margin_matches_tool9_at_every_threshold_including_zero(self):
        """`doubt_margin = 0` must collapse to Tool 9's hard-binary call, and
        Tool 9's form carries a `ratio > 0.0` guard (roi_detection_tester.py:727)
        that only matters at threshold 0.
        """
        for threshold in (0.0, 0.25, 0.5, 1.0):
            for ratio in (0.0, 0.1, 0.25, 0.5, 0.75, 1.0):
                got = phases_mod.in_match_call(ratio, threshold=threshold, doubt_margin=0.0)
                tool9 = "yes" if (ratio > 0.0 and ratio >= threshold) else "no"
                assert got == tool9, f"ratio={ratio} threshold={threshold}"


class TestLabeledRootHudFilter:
    @pytest.mark.parametrize("name,ok", [
        ("v1", True), ("v2", True), ("v2.1", True), ("v10", True),
        ("videos", False), ("validation", False), ("v2_backup", False),
        ("notes", False), ("v", False),
    ])
    def test_only_version_shaped_directories_count_as_hud_versions(self, name, ok):
        """A bare startswith("v") would swallow `videos/`, `validation/`,
        `v2_backup/` — silently inflating the HUD classifier's denominator.
        """
        assert bool(frames_mod._HUD_DIR_RE.match(name)) is ok
