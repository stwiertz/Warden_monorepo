"""Candidate-proposal engine for the Auto ROI/HSV Discoverer (Tool 8).

Pure logic — numpy in, dataclasses out; no Tk, no file I/O. V1 method (deliberately
simple — fancier segmentation is future polish):

1. per-pixel **instability** = mean of the BGR stddev channels (lower ⇒ more stable
   HUD chrome); excluded pixels are ``+inf``;
2. threshold to a **stable mask** (pixels below a percentile cutoff), find connected
   components, take each above-min-area component's bounding box → a candidate rect;
3. derive an **HSV band** for the rect (circular Hue mean/std + ordinary S/V), with
   ``_MIN_H_TOL`` / ``_MIN_SV_TOL`` clamps and a ``k ≈ 1.5`` factor — exactly the
   ``minimap_zone_selector`` convention, in *user space* (H 0–360, S/V 0–100);
4. **score** each candidate = geometric mean of ``size_score`` (diminishing-returns
   function of rect area), ``stability_score`` = ``1 / (1 + rect_mean_instability)``,
   and ``discriminativeness_score`` (the minimum, over the other target classes, of the
   rect's circular-HSV distance — a zone is only as discriminative as its worst confuser).

Return candidates sorted descending by score, each carrying its rect, HSV band, the
three component sub-scores, and which other class is its closest confuser.
"""

import math
from dataclasses import dataclass

import cv2
import numpy as np

from .model import Candidate, HsvBand, Rect

# Tolerance floors / factor — identical to minimap_zone_selector (`_MIN_H_TOL`,
# `_MIN_SV_TOL`, the `× 1.5` in `_compute_zone_hsv`).
_MIN_H_TOL = 10           # user space (H 0–360)
_MIN_SV_TOL = 5           # user space (S/V 0–100)
_DEFAULT_MIN_RATIO = 0.3  # matching minimap_zone_selector zones

# HSV-scale conversions: OpenCV (H 0–179, S/V 0–255)  ↔  user (H 0–360, S/V 0–100).
_H_CV_TO_USER = 360.0 / 180.0      # one OpenCV H unit = 2° user
_SV_CV_TO_USER = 100.0 / 255.0
_HUE_CV_TO_RAD = 2.0 * math.pi / 180.0


@dataclass
class DiscoverParams:
    """Tunable knobs for :func:`suggest_candidates` (documented in the ``.md``)."""

    stable_percentile: float = 25.0        # pixels with instability ≤ this percentile are "stable"
    min_region_area_frac: float = 2.5e-4   # min component area as a fraction of the cell area …
    min_region_area_floor: int = 9         #   … with this absolute floor (px)
    tol_k: float = 1.5                     # band tolerance = k · combined-stddev (then clamped)
    min_ratio: float = _DEFAULT_MIN_RATIO
    area_score_ref: float = 2000.0         # area at which size_score saturates (~1.0)
    instability_scale: float = 1.0         # stability_score = 1 / (1 + mean_instability / scale)
    disc_score_cap: float = 50.0           # HSV distance at which discriminativeness_score = 1.0
    max_candidates: int = 50               # cap on the returned list (top-scored)


# ---------------------------------------------------------------------------
# HSV-space helpers (small, standalone, round-trippable)
# ---------------------------------------------------------------------------


def hsv_cv_to_user(h_cv: float, s_cv: float, v_cv: float) -> tuple[int, int, int]:
    """OpenCV-space HSV → user-space HSV (rounded ints; H ``% 360``)."""
    return (
        int(round(h_cv * _H_CV_TO_USER)) % 360,
        int(round(min(max(s_cv, 0.0), 255.0) * _SV_CV_TO_USER)),
        int(round(min(max(v_cv, 0.0), 255.0) * _SV_CV_TO_USER)),
    )


def hsv_user_to_cv(h_user: float, s_user: float, v_user: float) -> tuple[float, float, float]:
    """User-space HSV → OpenCV-space HSV (floats; H wrapped into ``[0, 180)``).

    NOTE: the ``% 180`` wrap is correct for hue *centers* (a position on the circle) —
    DO NOT use this function to convert hue *tolerances* (a magnitude). Use
    :func:`tol_h_user_to_cv` for that."""
    return ((float(h_user) / _H_CV_TO_USER) % 180.0,
            float(s_user) / _SV_CV_TO_USER, float(v_user) / _SV_CV_TO_USER)


def tol_h_user_to_cv(tol_user: float) -> float:
    """User-space Hue *tolerance* (°, magnitude) → OpenCV-space (clamped to ``[0, 90]``).

    Unlike :func:`hsv_user_to_cv`, this does NOT mod by 180 — a tolerance is a magnitude,
    not a position; modding it would silently collapse wide bands (e.g. h_tol=380 → 10).
    Values ≥ 90 CV units saturate the full hue circle and are clamped, not wrapped."""
    return min(max(float(tol_user) / _H_CV_TO_USER, 0.0), 90.0)


def tol_sv_user_to_cv(tol_user: float) -> float:
    """User-space S/V *tolerance* (0–100, magnitude) → OpenCV-space (0–255, no wrap, clamped)."""
    return min(max(float(tol_user) / _SV_CV_TO_USER, 0.0), 255.0)


def tol_h_cv_to_user(tol_cv: float) -> int:
    """OpenCV-space Hue tolerance (H units) → user-space (× 2°), ceil'd, clamped to ``_MIN_H_TOL``."""
    return max(_MIN_H_TOL, int(math.ceil(float(tol_cv) * _H_CV_TO_USER)))


def tol_sv_cv_to_user(tol_cv: float) -> int:
    """OpenCV-space S/V tolerance (0–255) → user-space (0–100), ceil'd, clamped to ``_MIN_SV_TOL``."""
    return max(_MIN_SV_TOL, int(math.ceil(float(tol_cv) * _SV_CV_TO_USER)))


def circular_mean_cv(hue_cv: np.ndarray) -> float:
    """Circular mean of OpenCV-space hues → OpenCV-space hue in ``[0, 180)``."""
    arr = np.asarray(hue_cv, dtype=np.float64).ravel()
    if arr.size == 0:
        return 0.0
    angles = arr * _HUE_CV_TO_RAD
    mean_sin = float(np.mean(np.sin(angles)))
    mean_cos = float(np.mean(np.cos(angles)))
    return (math.degrees(math.atan2(mean_sin, mean_cos)) % 360.0) / 2.0 % 180.0


def circular_std_cv(hue_cv: np.ndarray) -> float:
    """Circular stddev of OpenCV-space hues → OpenCV H units, clamped to ``[0, 90]``."""
    arr = np.asarray(hue_cv, dtype=np.float64).ravel()
    if arr.size == 0:
        return 0.0
    angles = arr * _HUE_CV_TO_RAD
    R = math.hypot(float(np.mean(np.sin(angles))), float(np.mean(np.cos(angles))))
    inner = max(-2.0 * math.log(min(max(R, 1e-9), 1.0)), 0.0)
    return min(max(math.degrees(math.sqrt(inner)) / 2.0, 0.0), 90.0)


def circular_dist_user(a_user: float, b_user: float) -> float:
    """Circular distance between two user-space hues (H 0–360) → ``[0, 180]``."""
    d = abs(float(a_user) - float(b_user)) % 360.0
    return min(d, 360.0 - d)


# ---------------------------------------------------------------------------
# Stable-region detection
# ---------------------------------------------------------------------------


def instability_map(std_bgr: np.ndarray, exclusion_mask: np.ndarray | None = None) -> np.ndarray:
    """Per-pixel instability = mean of the BGR stddev channels (float64). Pixels under
    ``exclusion_mask`` (``True`` = excluded) become ``+inf`` so they're never proposed."""
    m = np.asarray(std_bgr, dtype=np.float64).mean(axis=2)
    if exclusion_mask is not None:
        m = np.where(np.asarray(exclusion_mask, dtype=bool), np.inf, m)
    return m


def stable_mask(instability: np.ndarray, params: DiscoverParams) -> np.ndarray:
    """Boolean ``(h, w)`` mask: ``True`` where instability ≤ the ``stable_percentile``
    cutoff of the *finite* pixels. ``+inf`` (excluded) pixels are always ``False``."""
    inst = np.asarray(instability, dtype=np.float64)
    finite = inst[np.isfinite(inst)]
    if finite.size == 0:
        return np.zeros(inst.shape, dtype=bool)
    cutoff = float(np.percentile(finite, params.stable_percentile))
    return np.isfinite(inst) & (inst <= cutoff)


def regions_from_mask(mask: np.ndarray, min_area: int) -> list[Rect]:
    """Bounding boxes of the 8-connected components of ``mask`` with area ≥ ``min_area``,
    ordered by descending area. An all-``False`` mask → ``[]``."""
    mask_u8 = np.asarray(mask, dtype=np.uint8)
    if not mask_u8.any():
        return []
    num, _labels, stats, _centroids = cv2.connectedComponentsWithStats(mask_u8, connectivity=8)
    rects: list[tuple[int, Rect]] = []
    for label in range(1, num):  # 0 is the background component
        x, y, w, h, area = (int(v) for v in stats[label])
        if area >= min_area and w > 0 and h > 0:
            rects.append((area, Rect(x, y, w, h)))
    rects.sort(key=lambda kv: kv[0], reverse=True)
    return [r for _, r in rects]


# ---------------------------------------------------------------------------
# Band derivation + scoring
# ---------------------------------------------------------------------------


def derive_band_for_rect(
    rect: Rect, mean_hsv: np.ndarray, std_hsv: np.ndarray,
    params: DiscoverParams | None = None,
) -> HsvBand:
    """HSV band for ``rect`` over the (mean, std) HSV arrays — user space, with
    ``_MIN_H_TOL`` / ``_MIN_SV_TOL`` floors and a ``params.tol_k`` factor.

    Tolerances combine the *across-pixel* spread (over the rect of the per-pixel mean)
    and the *across-frame* spread (the mean of the per-pixel temporal stddev) in
    quadrature — so a band covers both how the chrome varies within the region and how
    it flickers frame-to-frame. Hue uses circular statistics throughout.
    """
    params = params or DiscoverParams()
    rs, cs = rect.slices()
    mh = np.asarray(mean_hsv, dtype=np.float64)[rs, cs]
    sh = np.asarray(std_hsv, dtype=np.float64)[rs, cs]
    if mh.size == 0:
        return HsvBand(0, _MIN_H_TOL, 0, _MIN_SV_TOL, 50, _MIN_SV_TOL, params.min_ratio)

    # Hue (channel 0) — circular.
    h_vals = mh[..., 0].ravel()
    h_center_cv = circular_mean_cv(h_vals)
    h_spread_cv = circular_std_cv(h_vals)                  # across-pixel
    h_temporal_cv = float(np.mean(sh[..., 0]))             # across-frame (already circular per-pixel)
    h_total_cv = math.hypot(h_spread_cv, h_temporal_cv)
    h_center_user = int(round(h_center_cv * _H_CV_TO_USER)) % 360
    h_tol_user = max(_MIN_H_TOL, int(math.ceil(params.tol_k * h_total_cv * _H_CV_TO_USER)))

    def _sv_band(ch: int) -> tuple[int, int]:
        vals = mh[..., ch].ravel()
        center_cv = float(np.mean(vals))
        spread_cv = float(np.std(vals))
        temporal_cv = float(np.mean(sh[..., ch]))
        total_cv = math.hypot(spread_cv, temporal_cv)
        center_user = int(round(min(max(center_cv, 0.0), 255.0) * _SV_CV_TO_USER))
        tol_user = max(_MIN_SV_TOL, int(math.ceil(params.tol_k * total_cv * _SV_CV_TO_USER)))
        return center_user, tol_user

    s_center_user, s_tol_user = _sv_band(1)
    v_center_user, v_tol_user = _sv_band(2)
    return HsvBand(h_center_user, h_tol_user, s_center_user, s_tol_user,
                   v_center_user, v_tol_user, params.min_ratio)


def _region_hsv_user(rect: Rect, mean_hsv: np.ndarray) -> tuple[float, float, float]:
    """The region-mean HSV (user space) of ``rect`` over ``mean_hsv`` — circular for Hue."""
    rs, cs = rect.slices()
    block = np.asarray(mean_hsv, dtype=np.float64)[rs, cs]
    if block.size == 0:
        return 0.0, 0.0, 50.0
    h_user = circular_mean_cv(block[..., 0].ravel()) * _H_CV_TO_USER
    s_user = float(np.mean(block[..., 1])) * _SV_CV_TO_USER
    v_user = float(np.mean(block[..., 2])) * _SV_CV_TO_USER
    return h_user, s_user, v_user


def _region_instability(rect: Rect, instability: np.ndarray) -> float:
    """Mean of the finite instability pixels inside ``rect`` (``inf`` if none are finite)."""
    rs, cs = rect.slices()
    block = np.asarray(instability, dtype=np.float64)[rs, cs]
    finite = block[np.isfinite(block)]
    return float(finite.mean()) if finite.size else float("inf")


def _size_score(area: int, params: DiscoverParams) -> float:
    ref = max(1.0, params.area_score_ref)
    return float(min(1.0, math.log1p(max(0, area)) / math.log1p(ref)))


def _stability_score(mean_instability: float, params: DiscoverParams) -> float:
    if not math.isfinite(mean_instability):
        return 0.0
    return float(1.0 / (1.0 + max(0.0, mean_instability) / max(1e-9, params.instability_scale)))


def _discriminativeness(
    rect: Rect, target_mean_hsv: np.ndarray, other_means_hsv: dict, params: DiscoverParams,
) -> tuple[float, str | None]:
    """``(score, closest_confuser)`` — min over the other classes of the rect's
    circular-HSV distance (in a roughly-0..~170 space), normalised to ``[0, 1]``."""
    if not other_means_hsv:
        return 1.0, None
    t_h, t_s, t_v = _region_hsv_user(rect, target_mean_hsv)
    if not (math.isfinite(t_h) and math.isfinite(t_s) and math.isfinite(t_v)):
        return 0.0, None  # degenerate target stats — conservatively NOT discriminative
    best_dist = float("inf")
    best_name: str | None = None
    for name, arr in other_means_hsv.items():
        o_h, o_s, o_v = _region_hsv_user(rect, arr)
        if not (math.isfinite(o_h) and math.isfinite(o_s) and math.isfinite(o_v)):
            continue  # skip degenerate-stats class
        dh = circular_dist_user(t_h, o_h) / 180.0 * 100.0   # rescale 0..180 → 0..100
        ds = abs(t_s - o_s)
        dv = abs(t_v - o_v)
        dist = math.sqrt(dh * dh + ds * ds + dv * dv)
        if dist < best_dist:
            best_dist, best_name = dist, name
    if not math.isfinite(best_dist):
        return 0.0, None  # no comparable other class — conservatively NOT discriminative
    return float(min(1.0, best_dist / max(1e-9, params.disc_score_cap))), best_name


def suggest_candidates(
    target_stats, other_means_hsv: dict, exclusion_mask: np.ndarray | None = None,
    *, params: DiscoverParams | None = None,
) -> list[Candidate]:
    """Rank candidate ROI zones for ``target_stats`` (a :class:`model.TargetClassStats`).

    ``other_means_hsv`` maps each *other* target class's name → its ``mean_hsv`` array
    (same shape) — used for the discriminativeness term; pass ``{}`` to skip it.
    ``exclusion_mask`` is a ``(h, w)`` boolean array (``True`` = excluded). Returns the
    top ``params.max_candidates`` :class:`model.Candidate`s, sorted by descending score.
    """
    params = params or DiscoverParams()
    inst = instability_map(target_stats.std_bgr, exclusion_mask)
    total_px = inst.size
    min_area = max(int(params.min_region_area_floor),
                   int(round(params.min_region_area_frac * total_px)))
    regions = regions_from_mask(stable_mask(inst, params), min_area)

    candidates: list[Candidate] = []
    for rect in regions:
        band = derive_band_for_rect(rect, target_stats.mean_hsv, target_stats.std_hsv, params)
        mi = _region_instability(rect, inst)
        size_score = _size_score(rect.area, params)
        stab_score = _stability_score(mi, params)
        disc_score, confuser = _discriminativeness(
            rect, target_stats.mean_hsv, other_means_hsv, params
        )
        total = float((max(0.0, size_score) * max(0.0, stab_score) * max(0.0, disc_score)) ** (1.0 / 3.0))
        candidates.append(Candidate(
            rect=rect, band=band, score=total,
            size_score=size_score, stability_score=stab_score,
            discriminativeness_score=disc_score, closest_confuser=confuser,
            instability=mi if math.isfinite(mi) else float("inf"),
        ))
    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates[: max(0, params.max_candidates)]
