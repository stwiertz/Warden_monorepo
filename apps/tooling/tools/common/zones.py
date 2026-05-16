"""Shared zone primitives + the hue-wrap band-fire test.

Pure data + numpy/cv2 logic — no Tk, no file I/O. Relocated **verbatim** by
Story 9.11 from the now-retired Tool 8 package so the surviving Tool 9
(``roi_detection_tester``) — and Tool 9's future 9.14 refit — have a durable
home for ``Rect`` / ``HsvBand`` / ``TARGET_CLASSES`` and the
``band_inrange_ratio`` test plus its cross-module HSV-conversion closure
(``hsv_user_to_cv`` / ``tol_h_user_to_cv`` / ``tol_sv_user_to_cv`` +
``_H_CV_TO_USER`` / ``_SV_CV_TO_USER``).

ROI/zone coordinates are in *cell pixel space*; HSV bands are stored in *user
space* (H 0–360, S/V 0–100). Behaviour is byte-for-byte identical to the
retired sources (Story 9.11 is a relocation, not a rewrite). Exact
pre-retirement module/line provenance is preserved in git history and the
Story 9.11 File List.
"""

from dataclasses import dataclass

import cv2
import numpy as np


# The four game-state target classes. ``in_match`` is a *derived* class (the
# MAP_LABELS cells pooled); ``transition`` is kept so the future detector
# cascade learns to *recognize and reject* it — no special-casing in the engine.
TARGET_CLASSES = ("lobby", "in_match", "score", "transition")

# HSV-scale conversions: OpenCV (H 0–179, S/V 0–255)  ↔  user (H 0–360, S/V 0–100).
_H_CV_TO_USER = 360.0 / 180.0      # one OpenCV H unit = 2° user
_SV_CV_TO_USER = 100.0 / 255.0


@dataclass
class Rect:
    """An axis-aligned rectangle in cell pixel space."""

    x: int
    y: int
    width: int
    height: int

    def __post_init__(self):
        self.x = int(self.x)
        self.y = int(self.y)
        self.width = int(self.width)
        self.height = int(self.height)

    @property
    def area(self) -> int:
        return max(0, self.width) * max(0, self.height)

    def as_tuple(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.width, self.height)

    def slices(self) -> tuple[slice, slice]:
        """``(row_slice, col_slice)`` for indexing a ``(h, w[, c])`` array."""
        return (slice(self.y, self.y + self.height), slice(self.x, self.x + self.width))

    def clamp_to(self, shape) -> "Rect":
        """Return a copy clipped to fit fully inside ``shape`` (``(h, w[, c])``).

        A fully off-frame rect returns a 0-area Rect (width=0 or height=0); downstream
        consumers (``band_inrange_ratio``, ``zone_fires_on_frame``) already handle empty
        regions by returning 0.0. Pre-fix this returned a 1×1 sliver at the boundary
        which could silently false-fire."""
        h, w = int(shape[0]), int(shape[1])
        x_start = max(0, min(self.x, w))
        y_start = max(0, min(self.y, h))
        x_end = max(x_start, min(self.x + self.width, w))
        y_end = max(y_start, min(self.y + self.height, h))
        return Rect(x_start, y_start, x_end - x_start, y_end - y_start)


@dataclass
class HsvBand:
    """An HSV inclusion band in *user space* (H 0–360, S/V 0–100)."""

    h_center: int
    h_tol: int
    s_center: int
    s_tol: int
    v_center: int
    v_tol: int
    min_ratio: float = 0.3

    def __post_init__(self):
        self.h_center = int(self.h_center)
        self.h_tol = int(self.h_tol)
        self.s_center = int(self.s_center)
        self.s_tol = int(self.s_tol)
        self.v_center = int(self.v_center)
        self.v_tol = int(self.v_tol)
        self.min_ratio = float(self.min_ratio)

    def hsv_dict(self) -> dict:
        """The ``hsv:`` sub-dict shape ``config/config.yaml`` zones use."""
        return {
            "h_center": self.h_center, "h_tol": self.h_tol,
            "s_center": self.s_center, "s_tol": self.s_tol,
            "v_center": self.v_center, "v_tol": self.v_tol,
        }


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
