"""Variance / heatmap preprocessing + band auto-seed — Tk-free pure logic.

Folds the retired Tool 7 (``overlay_stack_analyzer.py`` @ ``ba6b326``) variance
signal and the retired Tool 8 (``auto_roi_discoverer/discoverer.py`` @
``0c1c656^``) band-seed math into one importable helper, so AC5/AC6 are
**ports, not reinventions**. The Welford + circular-Hue accumulators and
:func:`derive_band_for_rect` / :func:`circular_mean_cv` / :func:`circular_std_cv`
are byte-for-byte the recovered sources; the only deltas are (1) a single-pass
fold (frames are already in memory in the picker — the original two-pass
PNG re-read was a memory-bound batch concern that does not apply here) and
(2) the public :func:`class_stats` facade.

No tkinter — :class:`ClassStats` is unit-tested headless (AC11).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass

import cv2
import numpy as np

from tools.common.zones import HsvBand, Rect, band_inrange_ratio

# ---------------------------------------------------------------------------
# Welford (BGR / linear-HSV) — verbatim from overlay_stack_analyzer.py @ ba6b326
# ---------------------------------------------------------------------------


def _welford_init(shape) -> tuple[int, np.ndarray, np.ndarray]:
    """``(count, mean, M2)`` zero-state on ``float64`` arrays of ``shape``."""
    return (0, np.zeros(shape, dtype=np.float64), np.zeros(shape, dtype=np.float64))


def _welford_update(
    state: tuple[int, np.ndarray, np.ndarray], x: np.ndarray
) -> tuple[int, np.ndarray, np.ndarray]:
    """Fold one sample ``x`` into ``state`` (Welford's online algorithm)."""
    n, mean, m2 = state
    n += 1
    delta = x - mean
    mean = mean + delta / n
    delta2 = x - mean
    m2 = m2 + delta * delta2
    return (n, mean, m2)


def _welford_finalize(
    state: tuple[int, np.ndarray, np.ndarray]
) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(mean, population_stddev)``. ``count == 0`` → ``ValueError``;
    ``count == 1`` → stddev is all-zero (M2 is zero), which is correct."""
    n, mean, m2 = state
    if n == 0:
        raise ValueError("cannot finalize a Welford state with count 0")
    var = np.maximum(m2 / n, 0.0)  # population variance; clamp tiny-negative roundoff
    return mean, np.sqrt(var)


# ---------------------------------------------------------------------------
# Circular-Hue streaming accumulator — verbatim from overlay_stack_analyzer.py
# (OpenCV Hue 0..179, each unit = 2°; a naive Welford near the 0/179 wrap is
# meaningless, so keep running sin/cos sums and finalize to a circular mean/std).
# ---------------------------------------------------------------------------

_HUE_CV_TO_RAD = 2.0 * np.pi / 180.0  # one OpenCV H unit → radians


def _circ_hue_init(shape) -> tuple[int, np.ndarray, np.ndarray]:
    """``(count, sin_sum, cos_sum)`` zero-state on ``float64`` arrays of ``shape``."""
    return (0, np.zeros(shape, dtype=np.float64), np.zeros(shape, dtype=np.float64))


def _circ_hue_update(
    state: tuple[int, np.ndarray, np.ndarray], hue_cv: np.ndarray
) -> tuple[int, np.ndarray, np.ndarray]:
    """Fold one frame's OpenCV Hue channel (uint8 0..179) into the circular state."""
    n, sin_sum, cos_sum = state
    angles = np.asarray(hue_cv, dtype=np.float64) * _HUE_CV_TO_RAD
    return (n + 1, sin_sum + np.sin(angles), cos_sum + np.cos(angles))


def _circ_hue_finalize(
    state: tuple[int, np.ndarray, np.ndarray]
) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(circular_mean_hue, circular_stddev_hue)`` — both in OpenCV H
    units (0..179 / 0..90). ``count == 0`` → ``ValueError``; a constant hue (and
    the single-sample case) → stddev ``≈ 0``."""
    n, sin_sum, cos_sum = state
    if n == 0:
        raise ValueError("cannot finalize a circular-Hue state with count 0")
    mean_sin = sin_sum / n
    mean_cos = cos_sum / n
    R = np.sqrt(mean_sin ** 2 + mean_cos ** 2)
    mean_deg = np.degrees(np.arctan2(mean_sin, mean_cos)) % 360.0
    mean_cv = (mean_deg / 2.0) % 180.0
    # Snap R within float-noise of 1.0 to exactly 1.0 so a constant / single
    # sample hue produces exactly std=0 (float roundoff in sin²+cos² otherwise
    # yields R≈0.9999999 → std≈0.013° instead of 0).
    R_clipped = np.where(R >= 1.0 - 1e-9, 1.0, np.maximum(R, 1e-9))
    inner = np.maximum(-2.0 * np.log(R_clipped), 0.0)  # ≥0; exactly 0 when R≈1
    std_cv = np.clip(np.degrees(np.sqrt(inner)) / 2.0, 0.0, 90.0)
    return mean_cv, std_cv


def _normalize_uint8(arr: np.ndarray) -> np.ndarray:
    """Min-max normalize a (float or int) array to ``0..255`` ``uint8``. A
    constant array → all-zero (no division by zero)."""
    arr = np.asarray(arr, dtype=np.float64)
    lo = float(arr.min())
    hi = float(arr.max())
    if hi <= lo:
        return np.zeros(arr.shape, dtype=np.uint8)
    return np.round((arr - lo) / (hi - lo) * 255.0).astype(np.uint8)


# ---------------------------------------------------------------------------
# Band-seed scalars — verbatim from auto_roi_discoverer/discoverer.py @ 0c1c656^
# ---------------------------------------------------------------------------

_MIN_H_TOL = 10            # user space (H 0–360)
_MIN_SV_TOL = 5            # user space (S/V 0–100)
_DEFAULT_MIN_RATIO = 0.3   # matching the retired minimap_zone_selector zones
_H_CV_TO_USER = 360.0 / 180.0      # one OpenCV H unit = 2° user
_SV_CV_TO_USER = 100.0 / 255.0
_DEFAULT_TOL_K = 1.5               # band tolerance = k · combined-stddev (then clamped)


def circular_mean_cv(hue_cv: np.ndarray) -> float:
    """Circular mean of OpenCV-space hues → OpenCV-space hue in ``[0, 180)``."""
    arr = np.asarray(hue_cv, dtype=np.float64).ravel()
    if arr.size == 0:
        return 0.0
    angles = arr * (2.0 * math.pi / 180.0)
    mean_sin = float(np.mean(np.sin(angles)))
    mean_cos = float(np.mean(np.cos(angles)))
    return (math.degrees(math.atan2(mean_sin, mean_cos)) % 360.0) / 2.0 % 180.0


def circular_std_cv(hue_cv: np.ndarray) -> float:
    """Circular stddev of OpenCV-space hues → OpenCV H units, clamped ``[0, 90]``."""
    arr = np.asarray(hue_cv, dtype=np.float64).ravel()
    if arr.size == 0:
        return 0.0
    angles = arr * (2.0 * math.pi / 180.0)
    R = math.hypot(float(np.mean(np.sin(angles))), float(np.mean(np.cos(angles))))
    inner = max(-2.0 * math.log(min(max(R, 1e-9), 1.0)), 0.0)
    return min(max(math.degrees(math.sqrt(inner)) / 2.0, 0.0), 90.0)


def derive_band_for_rect(
    rect: Rect,
    mean_hsv: np.ndarray,
    std_hsv: np.ndarray,
    tol_k: float = _DEFAULT_TOL_K,
    min_ratio: float = _DEFAULT_MIN_RATIO,
) -> HsvBand:
    """HSV band for ``rect`` over the (mean, std) HSV arrays — user space, with
    ``_MIN_H_TOL`` / ``_MIN_SV_TOL`` floors and a ``tol_k`` factor.

    Tolerances combine the *across-pixel* spread (over the rect, of the per-pixel
    mean) and the *across-frame* spread (the mean of the per-pixel temporal
    stddev) in quadrature — so a band covers both how the chrome varies within
    the region and how it flickers frame-to-frame. Hue uses circular statistics
    throughout. Verbatim from the recovered Tool 8 discoverer (its
    ``DiscoverParams.tol_k``/``min_ratio`` flattened into plain args).
    """
    rs, cs = rect.slices()
    mh = np.asarray(mean_hsv, dtype=np.float64)[rs, cs]
    sh = np.asarray(std_hsv, dtype=np.float64)[rs, cs]
    if mh.size == 0:
        return HsvBand(0, _MIN_H_TOL, 0, _MIN_SV_TOL, 50, _MIN_SV_TOL, min_ratio)

    # Hue (channel 0) — circular.
    h_vals = mh[..., 0].ravel()
    h_center_cv = circular_mean_cv(h_vals)
    h_spread_cv = circular_std_cv(h_vals)                  # across-pixel
    h_temporal_cv = float(np.mean(sh[..., 0]))             # across-frame (already circular)
    h_total_cv = math.hypot(h_spread_cv, h_temporal_cv)
    h_center_user = int(round(h_center_cv * _H_CV_TO_USER)) % 360
    h_tol_user = max(_MIN_H_TOL, int(math.ceil(tol_k * h_total_cv * _H_CV_TO_USER)))

    def _sv_band(ch: int) -> tuple[int, int]:
        vals = mh[..., ch].ravel()
        center_cv = float(np.mean(vals))
        spread_cv = float(np.std(vals))
        temporal_cv = float(np.mean(sh[..., ch]))
        total_cv = math.hypot(spread_cv, temporal_cv)
        center_user = int(round(min(max(center_cv, 0.0), 255.0) * _SV_CV_TO_USER))
        tol_user = max(_MIN_SV_TOL, int(math.ceil(tol_k * total_cv * _SV_CV_TO_USER)))
        return center_user, tol_user

    s_center_user, s_tol_user = _sv_band(1)
    v_center_user, v_tol_user = _sv_band(2)
    return HsvBand(
        h_center_user, h_tol_user, s_center_user, s_tol_user,
        v_center_user, v_tol_user, min_ratio,
    )


# ---------------------------------------------------------------------------
# Public facade — single-pass per-class stats over already-loaded frames
# ---------------------------------------------------------------------------


@dataclass
class ClassStats:
    """Per-(class) variance products + a band-seed closure.

    ``mean_bgr`` / ``stddev_bgr`` are ``float64`` BGR; the ``stddev.png`` view is
    ``clip(stddev_bgr, 0, 255).astype(uint8)`` (NOT min-max normalized — dark =
    stable HUD chrome = ROI candidate). ``mean_hsv`` / ``std_hsv`` channel 0 is
    the *circular* Hue result (OpenCV 0..179 / H units); channels 1/2 are linear
    S/V. ``heatmap_bgr`` is the ``COLORMAP_JET`` false-colour over the min-max
    normalized S+V stddev only — Hue is excluded by design.
    """

    frame_count: int
    mean_bgr: np.ndarray
    stddev_bgr: np.ndarray
    mean_hsv: np.ndarray
    std_hsv: np.ndarray
    heatmap_bgr: np.ndarray

    def stddev_view_u8(self) -> np.ndarray:
        """``stddev.png``-equivalent view: ``clip(0,255)`` — NOT normalized."""
        return np.clip(self.stddev_bgr, 0, 255).astype(np.uint8)

    def mean_view_u8(self) -> np.ndarray:
        """``mean.png``-equivalent view (the 'average screen' BGR image)."""
        return np.clip(np.round(self.mean_bgr), 0, 255).astype(np.uint8)

    def derive_band(self, rect: Rect, tol_k: float = _DEFAULT_TOL_K) -> HsvBand:
        """Auto-seed an :class:`HsvBand` for ``rect`` (AC6 — a starting point,
        not a final answer; the operator adjusts it in the HSV editor)."""
        return derive_band_for_rect(rect, self.mean_hsv, self.std_hsv, tol_k=tol_k)


def class_stats(
    frames: Iterable[np.ndarray],
    progress: Callable[[int], None] | None = None,
) -> ClassStats:
    """Single-pass per-class variance fold over BGR frames.

    ``frames`` may be any iterable (a list, or a generator that decodes PNGs
    lazily) — it is consumed exactly once, so the picker can stream thousands
    of 1080p frames through it without ever holding them all in memory. Frames
    must share a shape (the picker resizes on load — same contract as Tool 7's
    modal-shape pass). Raises ``ValueError`` if the iterable yields no frames.
    The fold is the recovered Tool 7 per-frame loop, minus the two-pass PNG
    re-read: BGR Welford + linear-HSV Welford + circular-Hue accumulator, then
    channel-0 of mean/std HSV overwritten with the circular results (channels
    1/2 stay linear S/V). ``progress`` (if given) is called with the running
    frame count after each frame is folded.
    """
    bgr_state = hsv_state = hue_state = None
    count = 0

    for frame in frames:
        f = np.asarray(frame)
        if bgr_state is None:  # first frame fixes the shape (was frames[0])
            shape = f.shape
            bgr_state = _welford_init(shape)
            hsv_state = _welford_init(shape)
            hue_state = _circ_hue_init((shape[0], shape[1]))
        bgr_state = _welford_update(bgr_state, f.astype(np.float64))
        hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
        hsv_state = _welford_update(hsv_state, hsv.astype(np.float64))
        hue_state = _circ_hue_update(hue_state, hsv[:, :, 0])
        count += 1
        if progress is not None:
            progress(count)

    if count == 0:
        raise ValueError("class_stats requires at least one frame")

    mean_bgr, stddev_bgr = _welford_finalize(bgr_state)
    mean_hsv_lin, std_hsv_lin = _welford_finalize(hsv_state)
    hue_mean_cv, hue_std_cv = _circ_hue_finalize(hue_state)

    mean_hsv = mean_hsv_lin.copy()
    std_hsv = std_hsv_lin.copy()
    mean_hsv[:, :, 0] = hue_mean_cv  # circular H mean (OpenCV 0..179)
    std_hsv[:, :, 0] = hue_std_cv    # circular H stddev (OpenCV H units)

    # Heatmap: S+V stddev only (Hue channel 0 is circular — a naive per-pixel
    # stddev there is meaningless: 179 vs 0 looks like huge variance for
    # adjacent reds). The real H stat lives in std_hsv[...,0].
    scalar = std_hsv_lin[..., 1:].mean(axis=2)
    heatmap_bgr = cv2.applyColorMap(_normalize_uint8(scalar), cv2.COLORMAP_JET)

    return ClassStats(
        frame_count=bgr_state[0],
        mean_bgr=mean_bgr,
        stddev_bgr=stddev_bgr,
        mean_hsv=mean_hsv,
        std_hsv=std_hsv,
        heatmap_bgr=heatmap_bgr,
    )


# ---------------------------------------------------------------------------
# Already-picked zone-set re-evaluation — the "no-redraw re-check" (Story 9.12
# follow-up). Pure / Tk-free / unit-tested headless; lives here (not app.py)
# because variance.py is C7-survivable: an Epic 11 Qt rewrite discards the Tk
# glue but reuses this module as-is, so the re-check logic is not lost.
#
# Numerics are byte-for-byte the prior inline app.py readout: per-zone
# band_inrange_ratio on the (clamped) rect over the class mean image; aggregate
# = Σ effective_weight·fired / Σ effective_weight, effective_weight =
# weight_override if not None else weight. Moving this here changes NO behaviour
# — app.py now delegates instead of duplicating the loop.
# ---------------------------------------------------------------------------


@dataclass
class ZoneSetReadout:
    """Re-evaluation of an already-picked zone set against a class mean image.

    ``ratios`` / ``fired`` are per-zone, in the input order. ``aggregate`` is
    the weighted fired-fraction (0.0 when the set is empty or total weight is
    0). ``n_zones`` is ``len(zones)``. This is the signal that lets the operator
    flip the Class/Map dropdown to the negative class and instantly see how the
    SAVED zones score there — no manual ROI redraw.
    """

    ratios: list[float]
    fired: list[bool]
    aggregate: float
    n_zones: int


def evaluate_zone_set(
    zones: "list[tuple[Rect, HsvBand, float, float | None]]",
    mean_bgr: np.ndarray,
) -> ZoneSetReadout:
    """Re-evaluate ``zones`` (the picker's ``(rect, band, weight, wo)`` tuples)
    against ``mean_bgr`` (a :class:`ClassStats.mean_bgr`). Pure; no Tk, no I/O.
    """
    ratios: list[float] = []
    fired: list[bool] = []
    total = 0.0
    fired_w = 0.0
    for rect, band, weight, wo in zones:
        eff = float(weight if wo is None else wo)
        total += eff
        r = band_inrange_ratio(band, rect.clamp_to(mean_bgr.shape), mean_bgr)
        hit = r >= band.min_ratio
        ratios.append(r)
        fired.append(hit)
        if hit:
            fired_w += eff
    aggregate = fired_w / total if total else 0.0
    return ZoneSetReadout(
        ratios=ratios, fired=fired, aggregate=aggregate, n_zones=len(zones)
    )


# ---------------------------------------------------------------------------
# Live positive-VS-negative discrimination — a candidate (rect, band) scored
# against BOTH class proxy means at once, so the operator sees at ＋Add time
# whether the zone fires on the target class and stays dark on the other. Pure
# / Tk-free / C7-survivable. The picker caches the two means (positive pooled
# maps / negative lobby+score+transition) and calls this on every drag + Add.
# ---------------------------------------------------------------------------


@dataclass
class ZoneDiscrimination:
    """Same band scored on the positive and the negative mean image. Useful
    zone ⇔ ``discriminant`` (fires positive, dark negative)."""

    pos_ratio: float
    neg_ratio: float
    pos_fires: bool
    neg_fires: bool

    @property
    def discriminant(self) -> bool:
        return self.pos_fires and not self.neg_fires


def zone_discrimination(
    rect: Rect, band: HsvBand, pos_mean_bgr: np.ndarray, neg_mean_bgr: np.ndarray
) -> ZoneDiscrimination:
    """Score ``(rect, band)`` against both class means. Each fire flag is the
    band's own ``min_ratio`` applied to that mean's in-range ratio."""
    pr = band_inrange_ratio(band, rect.clamp_to(pos_mean_bgr.shape), pos_mean_bgr)
    nr = band_inrange_ratio(band, rect.clamp_to(neg_mean_bgr.shape), neg_mean_bgr)
    return ZoneDiscrimination(
        pos_ratio=pr,
        neg_ratio=nr,
        pos_fires=pr >= band.min_ratio,
        neg_fires=nr >= band.min_ratio,
    )
