"""GameStateValidator — a mean/std separability *proxy* for accepted game-state zones.

Pure logic — no Tk. Distinct from ``minimap_zone_selector``'s map-keyed
``ZoneValidator``: this one is *game-state-keyed* over the four target classes
(``lobby`` / ``in_match`` / ``score`` / ``transition``). It does **not** re-stream the
labeled PNG dataset — Tool 8 reads Tool 7's aggregates by design (loading hundreds of
1080p frames per class would defeat the architecture). For each accepted zone it:

* applies the zone's HSV band to its assigned class's **mean** BGR image (the hue-wrap
  ``cv2.inRange`` + ``min_ratio`` test ``zone_fires`` uses) → an in-range pixel ratio,
  and scales it by a **frame-coverage estimate** derived from how many σ (per-pixel
  temporal stddev, from ``std_hsv``) the band spans on its tightest channel → ``tp_proxy``;
* does the same in-range test on each *other* class's mean image; the worst is ``fp_proxy``;
* marks the zone *separable* if ``tp_proxy ≥ TP_MIN`` and ``fp_proxy ≤ FP_MAX``;
* a class is *separable* if it has ≥ 1 separable zone.

``transition`` is handled exactly like every other class — no special-casing (its
zones tend to lose on their own merits). This is explicitly a **proxy**; exact
per-frame validation against the labeled dataset is the future re-fingerprinting
story's job (see ``auto_roi_discoverer.md``).
"""

from dataclasses import dataclass, field

import cv2
import numpy as np

from .discoverer import hsv_user_to_cv, tol_h_user_to_cv, tol_sv_user_to_cv

# Documented combine rule — mirrors minimap_zone_selector's "≥ threshold" idea,
# simplified for the mean/std proxy.
TP_MIN = 0.5
FP_MAX = 0.30
_COVERAGE_STD_TARGET = 2.0   # a band spanning ≥ this many σ on its tightest channel ⇒ full coverage


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ZoneValidation:
    zone_name: str
    target_class: str
    tp_proxy: float            # in-range ratio on the assigned class's mean × frame-coverage estimate
    fp_proxy: float            # worst (max) in-range ratio on the other classes' mean images
    fires_on_assigned: bool    # in-range ratio on the assigned class ≥ band.min_ratio
    worst_confuser: str | None
    coverage_estimate: float   # the σ-margin coverage factor (0..1)
    inrange_on_assigned: float # the raw in-range ratio on the assigned class's mean image
    separable: bool            # tp_proxy ≥ TP_MIN and fp_proxy ≤ FP_MAX


@dataclass
class ClassValidation:
    target_class: str
    separable: bool
    contributing_zones: list = field(default_factory=list)   # names of the separable zones
    best_tp_proxy: float = 0.0
    worst_fp_proxy: float = 0.0
    n_zones: int = 0


@dataclass
class ValidationReport:
    zones: list = field(default_factory=list)        # list[ZoneValidation]
    classes: list = field(default_factory=list)      # list[ClassValidation]

    def zone(self, name: str) -> "ZoneValidation | None":
        return next((z for z in self.zones if z.zone_name == name), None)

    def klass(self, name: str) -> "ClassValidation | None":
        return next((c for c in self.classes if c.target_class == name), None)


# ---------------------------------------------------------------------------
# Band fire test + coverage estimate
# ---------------------------------------------------------------------------


def band_inrange_ratio(band, rect, mean_bgr: np.ndarray) -> float:
    """Fraction of ``rect``'s pixels on the BGR *mean* image inside ``band`` — the
    hue-wrap-aware ``cv2.inRange`` test (no scaling: the mean image is already in cell
    pixel space, the band's coords match)."""
    rs, cs = rect.slices()
    region = np.asarray(mean_bgr)[rs, cs]
    if region.size == 0:
        return 0.0
    region_u8 = np.clip(np.round(np.asarray(region, dtype=np.float64)), 0, 255).astype(np.uint8)
    hsv = cv2.cvtColor(region_u8, cv2.COLOR_BGR2HSV)
    h_c, s_c, v_c = hsv_user_to_cv(band.h_center, band.s_center, band.v_center)
    h_t = tol_h_user_to_cv(band.h_tol)   # tolerance is a magnitude, NOT a position — no % 180
    s_t = tol_sv_user_to_cv(band.s_tol)
    v_t = tol_sv_user_to_cv(band.v_tol)
    h_lo, h_hi = int(round(h_c - h_t)), int(round(h_c + h_t))
    s_lo, s_hi = max(0, int(round(s_c - s_t))), min(255, int(round(s_c + s_t)))
    v_lo, v_hi = max(0, int(round(v_c - v_t))), min(255, int(round(v_c + v_t)))
    if (h_hi - h_lo) >= 180:
        # Tolerance covers the full hue circle — match any hue (s/v still constrain).
        mask = cv2.inRange(hsv, np.array([0, s_lo, v_lo], dtype=np.uint8),
                           np.array([179, s_hi, v_hi], dtype=np.uint8))
    elif h_lo < 0 or h_hi > 179:
        mask1 = cv2.inRange(hsv, np.array([max(0, h_lo % 180), s_lo, v_lo], dtype=np.uint8),
                            np.array([179, s_hi, v_hi], dtype=np.uint8))
        mask2 = cv2.inRange(hsv, np.array([0, s_lo, v_lo], dtype=np.uint8),
                            np.array([min(179, h_hi % 180), s_hi, v_hi], dtype=np.uint8))
        mask = cv2.bitwise_or(mask1, mask2)
    else:
        mask = cv2.inRange(hsv, np.array([h_lo, s_lo, v_lo], dtype=np.uint8),
                           np.array([h_hi, s_hi, v_hi], dtype=np.uint8))
    return float(np.count_nonzero(mask)) / float(mask.size)


def coverage_estimate(band, rect, std_hsv: np.ndarray) -> float:
    """Frame-coverage proxy ∈ ``[0, 1]`` — the band's per-channel tolerance (OpenCV
    units) over the rect's mean per-channel temporal stddev, min over channels, divided
    by ``_COVERAGE_STD_TARGET`` and clamped. A wide-in-σ band on every channel ⇒ ~1.0;
    a band tighter than the per-frame jitter ⇒ small."""
    rs, cs = rect.slices()
    block = np.asarray(std_hsv, dtype=np.float64)[rs, cs]
    if block.size == 0:
        return 0.0
    h_t_cv = band.h_tol / 2.0
    s_t_cv = band.s_tol * 255.0 / 100.0
    v_t_cv = band.v_tol * 255.0 / 100.0
    margins = (
        h_t_cv / max(float(np.mean(block[..., 0])), 1.0),
        s_t_cv / max(float(np.mean(block[..., 1])), 1.0),
        v_t_cv / max(float(np.mean(block[..., 2])), 1.0),
    )
    return float(min(1.0, min(margins) / _COVERAGE_STD_TARGET))


# ---------------------------------------------------------------------------
# GameStateValidator
# ---------------------------------------------------------------------------


class GameStateValidator:
    """Game-state-keyed separability proxy over the four target classes."""

    TP_MIN = TP_MIN
    FP_MAX = FP_MAX

    @staticmethod
    def evaluate(zones_by_class: dict, class_stats: dict, *,
                 comparison_classes: dict | None = None) -> ValidationReport:
        """``zones_by_class``: ``{target_class: [DiscoveredZone, ...]}``.
        ``class_stats``: ``{target_class: TargetClassStats}`` (the loaded working set).
        ``comparison_classes`` (optional): ``{target_class: [class names]}`` — the set of
        *other* classes to compute a zone's FP-proxy over (the GUI passes a containment-
        aware set: a game-state class compares only against the other game-state classes;
        a per-map class compares against the other maps + ``{lobby, score, transition}``
        but not ``in_match`` which contains it). ``None`` ⇒ all other loaded classes."""
        class_stats = class_stats or {}
        zone_results: list[ZoneValidation] = []
        for cls, zones in (zones_by_class or {}).items():
            assigned = class_stats.get(cls)
            if comparison_classes is not None and cls in comparison_classes:
                others = [c for c in comparison_classes[cls] if c in class_stats and c != cls]
            else:
                others = [c for c in class_stats if c != cls]
            for zone in zones or []:
                if assigned is None:
                    zone_results.append(ZoneValidation(
                        zone_name=zone.name, target_class=cls, tp_proxy=0.0, fp_proxy=0.0,
                        fires_on_assigned=False, worst_confuser=None, coverage_estimate=0.0,
                        inrange_on_assigned=0.0, separable=False,
                    ))
                    continue
                inrange = band_inrange_ratio(zone.band, zone.rect, assigned.mean_bgr)
                cov = coverage_estimate(zone.band, zone.rect, assigned.std_hsv)
                tp_proxy = float(inrange * cov)
                fires = inrange >= zone.band.min_ratio
                worst_fp = 0.0
                worst_confuser: str | None = None
                for other_cls in others:
                    fp = band_inrange_ratio(zone.band, zone.rect, class_stats[other_cls].mean_bgr)
                    if fp > worst_fp:
                        worst_fp, worst_confuser = fp, other_cls
                separable = (tp_proxy >= TP_MIN) and (worst_fp <= FP_MAX)
                zone_results.append(ZoneValidation(
                    zone_name=zone.name, target_class=cls, tp_proxy=tp_proxy,
                    fp_proxy=float(worst_fp), fires_on_assigned=bool(fires),
                    worst_confuser=worst_confuser, coverage_estimate=cov,
                    inrange_on_assigned=float(inrange), separable=bool(separable),
                ))

        class_results: list[ClassValidation] = []
        all_classes = list((class_stats or {}).keys())
        for cls in (zones_by_class or {}):
            if cls not in all_classes:
                all_classes.append(cls)
        for cls in all_classes:
            zvs = [z for z in zone_results if z.target_class == cls]
            contributing = [z.zone_name for z in zvs if z.separable]
            class_results.append(ClassValidation(
                target_class=cls,
                separable=len(contributing) > 0,
                contributing_zones=contributing,
                best_tp_proxy=max((z.tp_proxy for z in zvs), default=0.0),
                worst_fp_proxy=max((z.fp_proxy for z in zvs), default=0.0),
                n_zones=len(zvs),
            ))
        return ValidationReport(zones=zone_results, classes=class_results)
