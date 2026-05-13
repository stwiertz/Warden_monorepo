"""Dataclasses shared across the Auto ROI/HSV Discoverer (Tool 8).

Pure data — no Tk, no file I/O. All ROI/zone coordinates are in the *cell pixel
space* the loader verified every target class shares (the ``--ref-height`` resized
space if Tool 7 ran with it, else the single common modal shape). HSV bands are
stored in *user space* (H 0–360, S/V 0–100) — the same convention
``minimap_zone_selector``'s config zone dicts use.
"""

from dataclasses import dataclass

import numpy as np


# The four game-state target classes Tool 8 works over. ``in_match`` is a *derived*
# class (the MAP_LABELS cells pooled); ``transition`` is kept so the future detector
# cascade learns to *recognize and reject* it — no special-casing in the engine.
# (Tool 8 *also* exposes each loaded per-map cell as its own target — see the loader.)
TARGET_CLASSES = ("lobby", "in_match", "score", "transition")

# Game-state classes that exist on every screen as their own static chrome (i.e. the
# ones a per-map zone should still be distinct from). ``in_match`` is excluded because
# it *contains* every per-map cell.
_NON_POOL_GAME_STATE = ("lobby", "score", "transition")


def comparison_classes(name: str, available, *, map_classes) -> list[str]:
    """The "other classes" to use for a target ``name``'s discriminativeness term (the
    discoverer) and FP-proxy (the validator) — **containment-aware**:

    * a **game-state** class (``lobby`` / ``in_match`` / ``score`` / ``transition``)
      compares only against the *other* game-state classes — so the best in-match
      marker (a fixed HUD element present identically on every map) still scores high on
      discriminativeness *vs. lobby/score/transition* instead of being penalised for
      "looking like all the maps";
    * a **per-map** class compares against the *other* per-map classes **plus**
      ``{lobby, score, transition}`` but **not** ``in_match`` (which contains it).

    ``available`` = the loaded class names (any iterable); ``map_classes`` = the ordered
    per-map class names (e.g. ``frame_labeler.MAP_LABELS``). Order is preserved
    (game-state in ``TARGET_CLASSES`` order, maps in ``map_classes`` order). Falls back
    to "all other available classes" for an unrecognised ``name``.
    """
    avail = set(available)
    map_set = set(map_classes) & avail
    game_state = [c for c in TARGET_CLASSES if c in avail]
    if name in game_state:
        return [c for c in game_state if c != name]
    if name in map_set:
        return ([c for c in map_classes if c in map_set and c != name]
                + [c for c in _NON_POOL_GAME_STATE if c in avail])
    return [c for c in available if c != name]


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


@dataclass
class Candidate:
    """A scored ROI candidate proposed by the discoverer (``discoverer.suggest_candidates``)."""

    rect: Rect
    band: HsvBand
    score: float                       # the combined total (geometric mean of the three below)
    size_score: float                  # 0..1 — diminishing-returns function of rect area
    stability_score: float             # 0..1 — inverse of the rect's mean instability
    discriminativeness_score: float    # 0..1 — min HSV distance to the other target classes
    closest_confuser: str | None       # which other target class is the tightest confuser
    instability: float                 # the rect's mean per-pixel BGR-stddev (raw)


@dataclass
class DiscoveredZone:
    """A zone the user accepted — from a candidate or drawn manually — for a class."""

    name: str
    target_class: str
    rect: Rect
    band: HsvBand
    origin: str = "manual"             # "candidate" | "manual"

    def zone_dict(self) -> dict:
        """Config-shaped zone dict (the same shape ``minimap_zone_selector`` writes —
        sans the minimap-specific ``weight`` / ``weight_override``)."""
        return {
            "name": self.name,
            "x": self.rect.x, "y": self.rect.y,
            "width": self.rect.width, "height": self.rect.height,
            "hsv": self.band.hsv_dict(),
            "min_ratio": self.band.min_ratio,
        }


@dataclass
class ExclusionRect:
    """A named rectangle to mask out before discovery (from ``exclusions.yaml``)."""

    name: str
    x: int
    y: int
    width: int
    height: int

    def __post_init__(self):
        self.name = str(self.name)
        self.x = int(self.x)
        self.y = int(self.y)
        self.width = int(self.width)
        self.height = int(self.height)

    def as_dict(self) -> dict:
        return {"name": self.name, "x": self.x, "y": self.y,
                "width": self.width, "height": self.height}

    @property
    def rect(self) -> Rect:
        return Rect(self.x, self.y, self.width, self.height)


@dataclass
class TargetClassStats:
    """Per-pixel statistics for one target class — the working set the loader builds
    from Tool 7's output. Every loaded target class shares ``frame_shape``."""

    name: str
    mean_bgr: np.ndarray              # (h, w, 3) float32
    std_bgr: np.ndarray               # (h, w, 3) float32
    mean_hsv: np.ndarray              # (h, w, 3) float32 — ch0 = circular mean H (OpenCV 0..179)
    std_hsv: np.ndarray               # (h, w, 3) float32 — ch0 = circular std H (OpenCV H units)
    frame_count: int
    frame_shape: tuple[int, int, int]
    source_cells: tuple[str, ...] = ()       # the "version/class" cell(s) it was built from
    stability_score: float | None = None     # the summary's stability_score (None for pooled in_match)
    is_pooled: bool = False                   # True only for the derived in_match class
