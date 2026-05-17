"""ROI Detection Tester — Tool 9: per-frame validation against the unified config.

Consumes an emitted ``map_config.<hud_version>.json`` (the Story 9.9c unified
schema, written by ``map_config_emitter.py`` and the same artifact the runtime
and ``video_test`` consume) + Tool 6's labeled PNG dataset
(``output/labeled/v<hud>/<class>/*.png``); replays every labeled frame through
every config zone's hue-wrap ``cv2.inRange`` band test (reusing
:func:`tools.common.zones.band_inrange_ratio` — no reinvention) and reports
**three** runtime classifiers against Tool 6's ground truth:

* **HUD-version** — is this frame this config's HUD? (per-HUD detector vs the
  ``v<hud>`` parent directory across every labeled HUD dir);
* **binary in_match / not_in_match** — frame's folder ∈ the 14 map slugs →
  ``in_match``, else (``lobby`` / ``score`` / ``transition``) → ``not_in_match``;
* **per-map ID** — weighted aggregate over each map slug's zones.

Writes:

* ``report.json`` — machine-readable: three classifier sections (each with its
  own per-zone TP/FP/FN/TN/P/R/F1 + confusion + per-class P/R/F1), run metadata;
* ``summary.md`` — human-readable, canonical order HUD → in_match → map-ID;
* ``frame_predictions.csv`` (opt-in) — one row per evaluated frame.

Headless batch tool — **no GUI**. Tool 9 never writes any config; it only reads
the emitted ``map_config.<hud_version>.json``. Empty zone arrays are the normal
early state during iterative zone population: a classifier with no zones
short-circuits to ``unknown`` for every frame and its section reads
``accuracy 0.000 — zones unpopulated`` (no crash, no divide-by-zero).

Usage::

    python tools/roi_detection_tester.py [--config PATH] [--labeled DIR]
        [--output DIR] [--limit N] [--ref-height H]
        [--hud-version-threshold 0.5] [--in-match-threshold 0.5]
        [--map-threshold T] [--save-frame-predictions]
"""

from __future__ import annotations

import argparse
import csv
import datetime
import glob
import json
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

# Absolute path insertion so ``tools.*`` imports resolve regardless of CWD.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from tools.common.zones import (  # noqa: E402
    HsvBand,
    Rect,
    band_inrange_ratio,
)
from tools.common.labels import MAP_LABELS  # noqa: E402
from tools.common.labeled_dataset import default_labeled_dir as _tool6_default_labeled  # noqa: E402


# ---------------------------------------------------------------------------
# Defaults (path math intentionally identical to Tools 6/10)
# ---------------------------------------------------------------------------


def _tooling_root() -> str:
    """``apps/tooling`` — one level up from ``tools/``."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _default_labeled_dir() -> str:
    """Tool 6's labeled-dataset root (``apps/tooling/output/labeled``)."""
    return _tool6_default_labeled()


def _default_output_dir() -> str:
    """``apps/tooling/output/roi_detection_tests`` — sibling of Tool 6's output."""
    return os.path.join(_tooling_root(), "output", "roi_detection_tests")


def _default_map_configs_root() -> str:
    """``apps/tooling/output/map_configs`` — ``map_config_emitter``'s output root
    (mirrors the emitter's ``_DEFAULT_OUTPUT_DIR``)."""
    return os.path.join(_tooling_root(), "output", "map_configs")


def _version_sort_key(name: str) -> tuple:
    """Natural sort key for ``v<major>.<minor>``-style HUD-version strings so
    ``v10`` > ``v2`` (lexicographic comparison would put ``v10`` < ``v2``).
    Non-numeric components fall back to lexicographic ordering at the end of the
    key tuple."""
    parts = str(name).lstrip("v").split(".")
    key = []
    for part in parts:
        try:
            key.append((0, int(part)))   # numeric component sorts before non-numeric
        except ValueError:
            key.append((1, part))
    return tuple(key)


def _normalize_hud(s: str) -> str:
    """Bridge the labeled-dir naming (``v2.0``) and the schema/config enum
    (``v2``). Lowercase + strip a single trailing ``.0`` so the HUD-version
    classifier's ground truth (parent dir, e.g. ``v2.0``) compares equal to
    ``config.hud_version`` (``v2``). Idempotent: ``v2`` → ``v2``,
    ``v2.0`` → ``v2``, ``v10.0`` → ``v10`` (resolved at Story 9.14 kickoff)."""
    out = str(s).strip().lower()
    if out.endswith(".0"):
        out = out[:-2]
    return out


def _default_config_path() -> str | None:
    """Locate the most-recent ``map_config.<hud>.json`` under the emitter's
    output root. Sort by natural version order on the ``<hud>`` filename segment
    (``v10 > v2``); ties → most-recent mtime. ``None`` if none exist."""
    root = _default_map_configs_root()
    if not os.path.isdir(root):
        return None
    candidates: list[tuple[str, str, float]] = []
    for path in glob.glob(os.path.join(root, "map_config.*.json")):
        base = os.path.basename(path)
        # "map_config.<hud>.json" → "<hud>"
        hud = base[len("map_config."):-len(".json")]
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            mtime = 0.0
        candidates.append((hud, path, mtime))
    if not candidates:
        return None
    candidates.sort(key=lambda c: (_version_sort_key(c[0]), c[2]))
    return candidates[-1][1]


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


class ZoneSpec:
    """A single zone: its classifier membership + rect + HSV band + weight.

    Composes the reused :class:`tools.common.zones.Rect` and :class:`HsvBand`
    — does NOT redefine them.

    The unified schema (Story 9.9c) renamed the per-zone identifier ``name`` →
    ``id`` and added ``weight`` / ``weight_override``. To keep the
    cross-story contract with Story 9.13's ``video_test`` (which constructs
    ``ZoneSpec(name=..., ...)`` and pins ``.name``) live and green, ``id`` is
    the canonical attribute, ``name`` is a backward-compat read-alias, and the
    constructor accepts either ``id=`` or the legacy ``name=`` kwarg (resolved
    at Story 9.14 kickoff — see Change Log scope note).
    """

    __slots__ = ("id", "owning_class", "kind", "rect", "band",
                 "weight", "weight_override")

    def __init__(
        self,
        id: str | None = None,
        owning_class: str = "",
        kind: str = "",
        rect: Rect | None = None,
        band: HsvBand | None = None,
        weight: float = 1.0,
        weight_override: float | None = None,
        *,
        name: str | None = None,
    ):
        ident = id if id is not None else name
        if ident is None:
            raise TypeError("ZoneSpec requires 'id' (or the legacy 'name' alias)")
        self.id = str(ident)
        self.owning_class = owning_class
        self.kind = kind          # "hud_version" | "in_match" | "map"
        self.rect = rect
        self.band = band
        self.weight = float(weight)
        self.weight_override = (
            None if weight_override is None else float(weight_override)
        )

    @property
    def name(self) -> str:
        """Backward-compat alias for :attr:`id` (frozen for Story 9.13)."""
        return self.id

    @property
    def effective_weight(self) -> float:
        """``weight_override`` if set, else ``weight`` (per-map aggregate, AC6)."""
        return self.weight if self.weight_override is None else self.weight_override

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ZoneSpec):
            return NotImplemented
        return (
            self.id == other.id
            and self.owning_class == other.owning_class
            and self.kind == other.kind
            and self.rect == other.rect
            and self.band == other.band
            and self.weight == other.weight
            and self.weight_override == other.weight_override
        )

    def __repr__(self) -> str:
        return (
            f"ZoneSpec(id={self.id!r}, owning_class={self.owning_class!r}, "
            f"kind={self.kind!r}, rect={self.rect!r}, band={self.band!r}, "
            f"weight={self.weight!r}, weight_override={self.weight_override!r})"
        )


@dataclass
class MapConfig:
    """Loaded + parsed ``map_config.<hud_version>.json`` (unified schema)."""

    hud_version: str
    ref_height: int
    hud_version_detection: list[ZoneSpec]
    in_match_detection: list[ZoneSpec]
    identification_threshold: float
    minimap_id: str
    minimap_roi: Rect
    map_zones: dict[str, list[ZoneSpec]]   # slug -> zones (config insertion order)


@dataclass
class FrameResult:
    """Per-frame evaluation snapshot — what ``aggregate_metrics`` folds over."""

    frame_path: str
    hud_dir: str
    folder: str
    same_hud: bool
    gt_hud: str                       # normalized parent dir (always present)
    pred_hud: str                     # config.hud_version (normalized) or "unknown"
    hud_conf: float
    gt_in_match: str | None           # "in_match"/"not_in_match"/None (other-HUD)
    pred_in_match: str | None         # "in_match"/"not_in_match"/"unknown"/None
    in_match_conf: float
    gt_map: str | None                # the MAP_LABELS folder name, or None
    pred_map: str | None              # MAP_LABELS/"unknown"/None (not evaluated)
    map_conf: float
    zone_fires: dict[tuple[str, str], bool]   # (owning_class, zone_id) -> fired?


@dataclass
class _ZoneAgg:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0
    fires_on_owning: int = 0
    samples_on_owning: int = 0
    fires_on_others: int = 0
    samples_on_others: int = 0


@dataclass
class ReportData:
    """Aggregated metrics — passed to the report writers."""

    frame_count_by_class: dict[str, int]
    skipped_folders: list[str]
    skipped_other_hud: int
    hud_version_classifier: dict
    in_match_classifier: dict
    map_id_classifier: dict


# ---------------------------------------------------------------------------
# load_map_config
# ---------------------------------------------------------------------------


_REQUIRED_TOP_KEYS = (
    "schema_version",
    "reference_resolution",
    "hud_version",
    "score_screen_duration_ms",
    "hud_version_detection",
    "in_match_detection",
    "minimap_identification",
)
_REQUIRED_ZONE_KEYS = (
    "id", "x", "y", "width", "height", "hsv", "min_ratio", "weight",
    "weight_override",
)
_REQUIRED_HSV_KEYS = ("h_center", "h_tol", "s_center", "s_tol", "v_center", "v_tol")
_REQUIRED_MINIMAP_KEYS = ("id", "identification_threshold", "roi", "maps")
_REQUIRED_RECT_KEYS = ("x", "y", "width", "height")


def _parse_zone_dict(raw: dict, owning_class: str, kind: str) -> ZoneSpec:
    """Validate + build a :class:`ZoneSpec` from one unified ``Zone`` dict.

    The unified schema makes ``min_ratio`` / ``weight`` / ``weight_override``
    **required** — a missing key is a malformed-config error, NOT a silent
    default (the emitter jsonschema-validates on write; a hand-broken file must
    surface cleanly so the 9.9b loop catches emitter/zone_picker bugs). Raises
    ``ValueError`` with a user-readable message on missing/bad shape.
    """
    if not isinstance(raw, dict):
        raise ValueError(f"zone entry in '{owning_class}' is not an object: {raw!r}")
    missing = [k for k in _REQUIRED_ZONE_KEYS if k not in raw]
    if missing:
        zid = raw.get("id", "<no id>")
        raise ValueError(
            f"zone '{zid}' in '{owning_class}' missing required keys: "
            f"{', '.join(missing)}"
        )
    zid = str(raw["id"])
    if not zid:
        raise ValueError(f"zone in '{owning_class}' has an empty 'id'")
    hsv = raw["hsv"]
    if not isinstance(hsv, dict):
        raise ValueError(f"zone '{zid}' in '{owning_class}': 'hsv' must be an object")
    hsv_missing = [k for k in _REQUIRED_HSV_KEYS if k not in hsv]
    if hsv_missing:
        raise ValueError(
            f"zone '{zid}' in '{owning_class}': 'hsv' missing keys: "
            f"{', '.join(hsv_missing)}"
        )
    wo = raw["weight_override"]
    if wo is not None and not isinstance(wo, (int, float)):
        raise ValueError(
            f"zone '{zid}' in '{owning_class}': 'weight_override' must be a "
            f"number or null, got {type(wo).__name__}"
        )
    # Geometry/HSV/weight presence is checked above, but a hand-broken config
    # can still carry a wrong-typed value (null, list, object) for a present
    # key. Rect/HsvBand.__post_init__ and float() raise TypeError on those,
    # which main() does NOT catch -> uncaught traceback. AC5 requires a clean
    # message + exit 1 on any malformed config, so re-raise as ValueError
    # (mirrors the ref_height / identification_threshold guards above).
    try:
        rect = Rect(x=raw["x"], y=raw["y"], width=raw["width"], height=raw["height"])
        band = HsvBand(
            h_center=hsv["h_center"], h_tol=hsv["h_tol"],
            s_center=hsv["s_center"], s_tol=hsv["s_tol"],
            v_center=hsv["v_center"], v_tol=hsv["v_tol"],
            min_ratio=float(raw["min_ratio"]),  # explicit - never HsvBand's 0.3 default
        )
        return ZoneSpec(
            id=zid, owning_class=owning_class, kind=kind, rect=rect, band=band,
            weight=float(raw["weight"]),
            weight_override=None if wo is None else float(wo),
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"zone '{zid}' in '{owning_class}': non-numeric or invalid value "
            f"in geometry/hsv/min_ratio/weight ({exc})"
        ) from exc


def load_map_config(path: str) -> MapConfig:
    """Read an emitted ``map_config.<hud_version>.json`` (unified schema) and
    project it onto Tool 9's evaluation surface.

    Tolerant ``json.loads`` + required-key check (NO jsonschema gate — the
    emitter already validated on write; a hand-broken file should give a clean
    message, not a stack trace). Malformed config → ``ValueError`` (``main``
    turns it into a clean stderr message + exit 1).
    """
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(
            f"top-level of '{path}' must be an object, got {type(data).__name__}"
        )

    missing = [k for k in _REQUIRED_TOP_KEYS if k not in data]
    if missing:
        raise ValueError(
            f"config '{path}' missing required keys: {', '.join(missing)}"
        )

    hud_version = data["hud_version"]
    if not isinstance(hud_version, str) or not hud_version:
        raise ValueError(f"config '{path}': 'hud_version' must be a non-empty string")

    ref_res = data["reference_resolution"]
    if not isinstance(ref_res, dict) or "height" not in ref_res:
        raise ValueError(
            f"config '{path}': 'reference_resolution' must be an object with 'height'"
        )
    try:
        ref_height = int(ref_res["height"])
    except (TypeError, ValueError):
        raise ValueError(
            f"config '{path}': 'reference_resolution.height' must be an integer"
        )
    if ref_height < 1:
        raise ValueError(
            f"config '{path}': 'reference_resolution.height' must be >= 1"
        )

    hud_zones_raw = data["hud_version_detection"]
    in_match_raw = data["in_match_detection"]
    if not isinstance(hud_zones_raw, list) or not isinstance(in_match_raw, list):
        raise ValueError(
            f"config '{path}': 'hud_version_detection' and 'in_match_detection' "
            f"must be arrays"
        )

    minimap = data["minimap_identification"]
    if not isinstance(minimap, dict):
        raise ValueError(f"config '{path}': 'minimap_identification' must be an object")
    mm_missing = [k for k in _REQUIRED_MINIMAP_KEYS if k not in minimap]
    if mm_missing:
        raise ValueError(
            f"config '{path}': 'minimap_identification' missing keys: "
            f"{', '.join(mm_missing)}"
        )
    try:
        ident_threshold = float(minimap["identification_threshold"])
    except (TypeError, ValueError):
        raise ValueError(
            f"config '{path}': 'minimap_identification.identification_threshold' "
            f"must be a number"
        )
    roi_raw = minimap["roi"]
    if not isinstance(roi_raw, dict):
        raise ValueError(f"config '{path}': 'minimap_identification.roi' must be an object")
    roi_missing = [k for k in _REQUIRED_RECT_KEYS if k not in roi_raw]
    if roi_missing:
        raise ValueError(
            f"config '{path}': 'minimap_identification.roi' missing keys: "
            f"{', '.join(roi_missing)}"
        )
    minimap_roi = Rect(
        x=roi_raw["x"], y=roi_raw["y"],
        width=roi_raw["width"], height=roi_raw["height"],
    )
    maps_raw = minimap["maps"]
    if not isinstance(maps_raw, dict):
        raise ValueError(f"config '{path}': 'minimap_identification.maps' must be an object")

    hud_zones = [
        _parse_zone_dict(z, _normalize_hud(hud_version), "hud_version")
        for z in hud_zones_raw
    ]
    in_match_zones = [
        _parse_zone_dict(z, "in_match", "in_match") for z in in_match_raw
    ]
    map_zones: dict[str, list[ZoneSpec]] = {}
    for slug, entry in maps_raw.items():   # config insertion order preserved (REL-005)
        if not isinstance(entry, dict) or "zones" not in entry:
            raise ValueError(
                f"config '{path}': map '{slug}' must be an object with 'zones'"
            )
        zlist = entry["zones"]
        if not isinstance(zlist, list):
            raise ValueError(f"config '{path}': map '{slug}'.zones must be an array")
        map_zones[str(slug)] = [
            _parse_zone_dict(z, str(slug), "map") for z in zlist
        ]

    return MapConfig(
        hud_version=str(hud_version),
        ref_height=ref_height,
        hud_version_detection=hud_zones,
        in_match_detection=in_match_zones,
        identification_threshold=ident_threshold,
        minimap_id=str(minimap["id"]),
        minimap_roi=minimap_roi,
        map_zones=map_zones,
    )


# ---------------------------------------------------------------------------
# Frame I/O + resize
# ---------------------------------------------------------------------------


def _read_frame_bgr(path: str) -> np.ndarray | None:
    """Windows non-ASCII-path-safe PNG read (``imdecode`` + ``np.fromfile``).
    Returns ``None`` on failure (caller logs + skips)."""
    try:
        buf = np.fromfile(path, dtype=np.uint8)
    except OSError:
        return None
    if buf.size == 0:
        return None
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    return img


def _resize_to_ref(frame_bgr: np.ndarray, ref_height: int) -> np.ndarray:
    """Aspect-preserving resize so the output's row count equals ``ref_height``.
    ``INTER_AREA`` for downscale, ``INTER_LINEAR`` for upscale. If the frame is
    already at ``ref_height``, return as-is (no copy). A zero-height frame
    (corrupt decode) is returned as-is rather than crashing with
    ``ZeroDivisionError``.

    Frozen for Story 9.13's contract pin — do not change the signature/return.
    """
    h, w = int(frame_bgr.shape[0]), int(frame_bgr.shape[1])
    if h <= 0:
        return frame_bgr  # caller already filters None; guards a 0-row decode
    if h == ref_height:
        return frame_bgr
    target_w = max(1, int(round(w * (ref_height / float(h)))))
    interp = cv2.INTER_AREA if ref_height < h else cv2.INTER_LINEAR
    return cv2.resize(frame_bgr, (target_w, ref_height), interpolation=interp)


def iter_labeled_frames(
    labeled_root: str,
    *,
    limit_per_class: int | None = None,
) -> Iterator[tuple[str, str, str, np.ndarray]]:
    """Yield ``(frame_path, hud_dir, folder_name, frame_bgr)`` for every readable
    PNG under ``<labeled_root>/v*/<class>/*.png``, in sorted
    ``(hud_dir, class, file)`` order. Every ``v*`` HUD dir present is scanned
    (so the HUD-version classifier sees cross-HUD negatives — AC2). Unreadable
    files are warned and skipped (don't crash the batch). When
    ``limit_per_class`` is set, only the first N files per ``(hud_dir, class)``
    are yielded.
    """
    if not os.path.isdir(labeled_root):
        return
    try:
        hud_dirs = sorted(os.listdir(labeled_root))
    except OSError as exc:
        print(
            f"  WARN: cannot list {labeled_root} ({exc}) - yielding no frames",
            file=sys.stderr, flush=True,
        )
        return
    for hud_dir in hud_dirs:
        hud_path = os.path.join(labeled_root, hud_dir)
        if not hud_dir.startswith("v") or not os.path.isdir(hud_path):
            continue
        try:
            class_dirs = sorted(os.listdir(hud_path))
        except OSError as exc:
            print(
                f"  WARN: cannot list {hud_path} ({exc}) - skipping",
                file=sys.stderr, flush=True,
            )
            continue
        for class_name in class_dirs:
            class_dir = os.path.join(hud_path, class_name)
            if not os.path.isdir(class_dir):
                continue
            pngs = sorted(glob.glob(os.path.join(class_dir, "*.png")))
            if limit_per_class is not None:
                pngs = pngs[: int(limit_per_class)]
            for frame_path in pngs:
                img = _read_frame_bgr(frame_path)
                if img is None:
                    print(f"  WARN: cannot read {frame_path} - skipping", file=sys.stderr)
                    continue
                yield frame_path, hud_dir, class_name, img


# ---------------------------------------------------------------------------
# Per-frame band-fire test (reuses the shared hue-wrap cv2.inRange logic)
# ---------------------------------------------------------------------------


def zone_fires_on_frame(zone: ZoneSpec, frame_bgr_at_ref: np.ndarray) -> tuple[bool, float]:
    """Per-frame band-fire test for one zone on a reference-height-resized BGR
    frame. Reuses :func:`tools.common.zones.band_inrange_ratio` — same hue-wrap
    ``cv2.inRange`` + ``bitwise_or`` logic, no reinvention. Clips the rect to
    the frame first to survive zones drawn off the edge.

    Frozen for Story 9.13's contract pin — keep the ``(fired, ratio)`` return
    and the call shape stable.
    """
    h, w = int(frame_bgr_at_ref.shape[0]), int(frame_bgr_at_ref.shape[1])
    rect = zone.rect.clamp_to((h, w, 3))
    ratio = float(band_inrange_ratio(zone.band, rect, frame_bgr_at_ref))
    return (ratio >= zone.band.min_ratio, ratio)


# ---------------------------------------------------------------------------
# Folder → ground-truth mapping
# ---------------------------------------------------------------------------


def _folder_to_in_match(folder: str) -> str:
    """Folder name → binary in_match ground truth. Any of the 14 map slugs →
    ``in_match``; everything else (``lobby`` / ``score`` / ``transition``) →
    ``not_in_match``. Tool 6's labeled-folder layout is unchanged — the binary
    ground-truth collapse lives only here (AC3)."""
    return "in_match" if folder in MAP_LABELS else "not_in_match"


# ---------------------------------------------------------------------------
# Classifier + per-frame evaluator
# ---------------------------------------------------------------------------


def _argmax_with_threshold(
    scores: dict[str, float],
    *,
    threshold: float,
    ordered_classes: tuple[str, ...] | list[str],
    zone_counts: dict[str, int],
) -> tuple[str, float]:
    """Pick the predicted class — argmax over ``scores``, gated by ``threshold``.

    Tie-break: prefer the class with more zones (more confidence); secondary
    tie-break by the natural ``ordered_classes`` order. Below threshold →
    ``"unknown"``. A score of exactly 0.0 always returns ``"unknown"`` (no zone
    fired — nothing to predict from — regardless of whether ``threshold`` is
    also 0.0). Ties on the max score use ``math.isclose`` rather than exact
    float equality so the tie-break is deterministic across float environments.

    Frozen for Story 9.13's contract pin — keep verbatim.
    """
    if not scores:
        return "unknown", 0.0
    max_score = max(scores.values())
    if max_score <= 0.0:
        return "unknown", float(max_score)
    if max_score < threshold:
        return "unknown", float(max_score)
    tied = [c for c, s in scores.items() if math.isclose(s, max_score, rel_tol=1e-9, abs_tol=1e-12)]
    if len(tied) == 1:
        return tied[0], float(max_score)
    # Tie-break: more zones wins; then natural order.
    best = max(tied, key=lambda c: (zone_counts.get(c, 0), -list(ordered_classes).index(c)))
    return best, float(max_score)


def evaluate_frame(
    frame_bgr_at_ref: np.ndarray,
    config: MapConfig,
    hud_dir: str,
    folder: str,
    *,
    hud_version_threshold: float = 0.5,
    in_match_threshold: float = 0.5,
    map_threshold: float | None = None,
) -> FrameResult:
    """Apply every config zone to one labeled frame; return a
    :class:`FrameResult` carrying the per-zone fires + the three classifier
    predictions.

    * HUD-version + in_match scores are **unweighted** ``fires / n_zones``.
    * Per-map score is the **weighted aggregate** ``Σ effective_weight × fired``
      (AC6 — resolved weighted at Story 9.14 kickoff).
    * in_match + map are only evaluated on same-HUD frames (other-HUD frames are
      recorded under ``skipped_other_hud``; their zones aren't calibrated here).
    """
    norm_cfg_hud = _normalize_hud(config.hud_version)
    gt_hud = _normalize_hud(hud_dir)
    same_hud = gt_hud == norm_cfg_hud

    zone_fires: dict[tuple[str, str], bool] = {}

    # --- HUD-version classifier (evaluated on EVERY frame) -----------------
    hud_zones = config.hud_version_detection
    n_hud = len(hud_zones)
    hud_scores: dict[str, float] = {}
    if n_hud:
        fires = 0
        for z in hud_zones:
            fired, _ratio = zone_fires_on_frame(z, frame_bgr_at_ref)
            zone_fires[(z.owning_class, z.id)] = fired
            if fired:
                fires += 1
        hud_scores[norm_cfg_hud] = fires / float(n_hud)
    pred_hud, hud_conf = _argmax_with_threshold(
        hud_scores,
        threshold=float(hud_version_threshold),
        ordered_classes=[norm_cfg_hud],
        zone_counts={norm_cfg_hud: n_hud},
    )

    gt_in_match: str | None
    pred_in_match: str | None
    in_match_conf: float
    gt_map: str | None
    pred_map: str | None
    map_conf: float

    if not same_hud:
        # Other-HUD frame: in_match + map zones aren't calibrated for this
        # config — record as skipped, leave their GT/pred unset (csv blanks).
        gt_in_match = None
        pred_in_match = None
        in_match_conf = 0.0
        gt_map = None
        pred_map = None
        map_conf = 0.0
        return FrameResult(
            frame_path="", hud_dir=hud_dir, folder=folder, same_hud=False,
            gt_hud=gt_hud, pred_hud=pred_hud, hud_conf=float(hud_conf),
            gt_in_match=gt_in_match, pred_in_match=pred_in_match,
            in_match_conf=in_match_conf,
            gt_map=gt_map, pred_map=pred_map, map_conf=map_conf,
            zone_fires=zone_fires,
        )

    # --- binary in_match classifier (same-HUD only) ------------------------
    im_zones = config.in_match_detection
    n_im = len(im_zones)
    gt_in_match = _folder_to_in_match(folder)
    if n_im == 0:
        # Empty-zones short-circuit (AC8): no zones → predict "unknown".
        pred_in_match = "unknown"
        in_match_conf = 0.0
    else:
        fires = 0
        for z in im_zones:
            fired, _ratio = zone_fires_on_frame(z, frame_bgr_at_ref)
            zone_fires[(z.owning_class, z.id)] = fired
            if fired:
                fires += 1
        ratio = fires / float(n_im)
        in_match_conf = ratio
        # Binary: clears threshold → in_match, else not_in_match (NOT unknown).
        pred_in_match = (
            "in_match" if (ratio > 0.0 and ratio >= float(in_match_threshold))
            else "not_in_match"
        )

    # --- per-map ID classifier (same-HUD only; weighted aggregate) ---------
    # Score every map's zones on every same-HUD frame so per-zone FP/TN tallies
    # cover non-map folders too; commit a map-ID *prediction* only on
    # MAP_LABELS folders (AC4 invariant + the non-map-folder regression lock).
    map_scores: dict[str, float] = {}
    map_zone_counts: dict[str, int] = {}
    for slug, zones in config.map_zones.items():
        n_z = len(zones)
        map_zone_counts[slug] = n_z
        if n_z == 0:
            continue
        agg = 0.0
        for z in zones:
            fired, _ratio = zone_fires_on_frame(z, frame_bgr_at_ref)
            zone_fires[(z.owning_class, z.id)] = fired
            if fired:
                agg += z.effective_weight
        map_scores[slug] = agg

    resolved_map_threshold = (
        config.identification_threshold if map_threshold is None
        else float(map_threshold)
    )
    gt_map = folder if folder in MAP_LABELS else None
    if folder in MAP_LABELS:
        pred_map, map_conf = _argmax_with_threshold(
            map_scores,
            threshold=float(resolved_map_threshold),
            ordered_classes=list(MAP_LABELS),
            zone_counts=map_zone_counts,
        )
    else:
        pred_map = None
        map_conf = 0.0

    return FrameResult(
        frame_path="", hud_dir=hud_dir, folder=folder, same_hud=True,
        gt_hud=gt_hud, pred_hud=pred_hud, hud_conf=float(hud_conf),
        gt_in_match=gt_in_match, pred_in_match=pred_in_match,
        in_match_conf=float(in_match_conf),
        gt_map=gt_map, pred_map=pred_map, map_conf=float(map_conf),
        zone_fires=zone_fires,
    )


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------


def _safe_div(num: float, denom: float) -> float:
    return float(num) / float(denom) if denom else 0.0


def _per_class_from_confusion(
    confusion: dict[str, dict[str, int]],
    classes: list[str],
) -> dict[str, dict[str, float]]:
    """Per-class precision/recall/F1 from a confusion matrix.

    Precision = TP / Σ predicted=c. Recall = TP / support_c. F1 = 2PR/(P+R).
    All ``/0`` guarded to 0.0. ``support_c`` is the number of rows for that class.
    """
    out: dict[str, dict[str, float]] = {}
    pred_totals: dict[str, int] = {}
    for gt, row in confusion.items():
        for pred, count in row.items():
            pred_totals[pred] = pred_totals.get(pred, 0) + int(count)
    for cls in classes:
        row = confusion.get(cls, {})
        tp = int(row.get(cls, 0))
        support = sum(int(v) for v in row.values())
        pred_total = pred_totals.get(cls, 0)
        precision = _safe_div(tp, pred_total)
        recall = _safe_div(tp, support)
        f1 = _safe_div(2 * precision * recall, precision + recall)
        out[cls] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support,
        }
    return out


def _zone_per_zone_list(
    zone_index: dict[tuple[str, str], ZoneSpec],
    zone_agg: dict[tuple[str, str], _ZoneAgg],
    kind: str,
) -> list[dict]:
    """Build the per-zone TP/FP/FN/TN/P/R/F1 list for one classifier ``kind``."""
    out: list[dict] = []
    for (owning_class, zone_id), agg in zone_agg.items():
        spec = zone_index[(owning_class, zone_id)]
        if spec.kind != kind:
            continue
        precision = _safe_div(agg.tp, agg.tp + agg.fp)
        recall = _safe_div(agg.tp, agg.tp + agg.fn)
        f1 = _safe_div(2 * precision * recall, precision + recall)
        out.append({
            "zone_id": zone_id,
            "owning_class": owning_class,
            "kind": spec.kind,
            "tp": agg.tp, "fp": agg.fp, "fn": agg.fn, "tn": agg.tn,
            "precision": precision, "recall": recall, "f1": f1,
            "fire_rate_on_owning": _safe_div(agg.fires_on_owning, agg.samples_on_owning),
            "fire_rate_on_others": _safe_div(agg.fires_on_others, agg.samples_on_others),
        })
    return out


def aggregate_metrics(
    per_frame_results: list[FrameResult],
    config: MapConfig,
) -> ReportData:
    """Fold per-frame results into three classifier blocks (HUD-version /
    in_match / map-ID), each owning its per-zone TP/FP/FN/TN + confusion +
    per-class P/R/F1 + top-line accuracy. All divisions guarded against ``/0``.
    """
    norm_cfg_hud = _normalize_hud(config.hud_version)

    # Per-zone aggregates keyed by (owning_class, zone_id).
    zone_index: dict[tuple[str, str], ZoneSpec] = {}
    for z in config.hud_version_detection:
        zone_index[(z.owning_class, z.id)] = z
    for z in config.in_match_detection:
        zone_index[(z.owning_class, z.id)] = z
    for zones in config.map_zones.values():
        for z in zones:
            zone_index[(z.owning_class, z.id)] = z
    zone_agg: dict[tuple[str, str], _ZoneAgg] = {k: _ZoneAgg() for k in zone_index}

    hud_empty = len(config.hud_version_detection) == 0
    in_match_empty = len(config.in_match_detection) == 0
    map_empty = (
        len(config.map_zones) == 0
        or all(len(z) == 0 for z in config.map_zones.values())
    )

    # HUD-version confusion: rows = every normalized GT hud present (so cross-
    # HUD negatives count); columns = {config.hud_version, "unknown"}.
    hud_row_classes: list[str] = []
    hud_cols = [norm_cfg_hud, "unknown"]
    hud_confusion: dict[str, dict[str, int]] = {}

    im_classes = ["in_match", "not_in_match"]
    im_cols = ["in_match", "not_in_match", "unknown"]
    im_confusion: dict[str, dict[str, int]] = {
        c: {p: 0 for p in im_cols} for c in im_classes
    }

    map_confusion: dict[str, dict[str, int]] = {
        c: {p: 0 for p in list(MAP_LABELS) + ["unknown"]} for c in MAP_LABELS
    }

    n_hud_eval = n_hud_correct = 0
    n_im_eval = n_im_correct = 0
    n_map_eval = n_map_correct = 0
    frame_count_by_class: dict[str, int] = {}
    skipped_folders: set[str] = set()
    skipped_other_hud = 0

    for fr in per_frame_results:
        frame_count_by_class[fr.folder] = frame_count_by_class.get(fr.folder, 0) + 1

        # --- HUD-version (every frame) ---
        n_hud_eval += 1
        if fr.gt_hud not in hud_confusion:
            hud_confusion[fr.gt_hud] = {p: 0 for p in hud_cols}
            hud_row_classes.append(fr.gt_hud)
        pred_h = fr.pred_hud if fr.pred_hud in hud_cols else "unknown"
        hud_confusion[fr.gt_hud][pred_h] += 1
        if fr.pred_hud == fr.gt_hud:
            n_hud_correct += 1

        if not fr.same_hud:
            skipped_other_hud += 1

        # --- binary in_match (same-HUD only) ---
        if fr.same_hud and fr.gt_in_match is not None:
            n_im_eval += 1
            pred_im = fr.pred_in_match if fr.pred_in_match in im_cols else "unknown"
            im_confusion.setdefault(fr.gt_in_match, {p: 0 for p in im_cols})
            im_confusion[fr.gt_in_match][pred_im] += 1
            if fr.pred_in_match == fr.gt_in_match:
                n_im_correct += 1

        # --- per-map ID (same-HUD, MAP_LABELS folders only) ---
        if fr.same_hud and fr.gt_map is not None and fr.pred_map is not None:
            n_map_eval += 1
            pred_m = fr.pred_map if fr.pred_map in map_confusion[fr.gt_map] else "unknown"
            map_confusion[fr.gt_map][pred_m] += 1
            if fr.pred_map == fr.gt_map:
                n_map_correct += 1

        # Folders with no MAP_LABELS membership AND no same-HUD in_match GT are
        # never "skipped" for in_match (not_in_match is a real class), so the
        # only skip bucket is other-HUD frames recorded above. Key the note by
        # "<hud_dir>/<folder>" (NOT folder alone): the same folder name exists
        # under every scanned v* dir, so a bare-folder key would mislabel a
        # folder fully evaluated under the config's HUD as "not evaluated"
        # just because its other-HUD twin was skipped.
        if not fr.same_hud:
            skipped_folders.add(f"{fr.hud_dir}/{fr.folder}")

        # --- per-zone TP/FP/FN/TN ---
        for (owning_class, zone_id), fired in fr.zone_fires.items():
            agg = zone_agg.get((owning_class, zone_id))
            if agg is None:
                continue
            spec = zone_index[(owning_class, zone_id)]
            if spec.kind == "hud_version":
                positive = fr.gt_hud == owning_class
            elif spec.kind == "in_match":
                if not fr.same_hud or fr.gt_in_match is None:
                    continue
                positive = fr.gt_in_match == "in_match"
            else:  # "map"
                if not fr.same_hud:
                    continue
                positive = fr.gt_map == owning_class

            if positive:
                agg.samples_on_owning += 1
                if fired:
                    agg.tp += 1
                    agg.fires_on_owning += 1
                else:
                    agg.fn += 1
            else:
                agg.samples_on_others += 1
                if fired:
                    agg.fp += 1
                    agg.fires_on_others += 1
                else:
                    agg.tn += 1

    hud_per_class = _per_class_from_confusion(hud_confusion, hud_row_classes)
    im_per_class = _per_class_from_confusion(im_confusion, im_classes)
    map_per_class = _per_class_from_confusion(map_confusion, list(MAP_LABELS))

    hud_block = {
        "accuracy": _safe_div(n_hud_correct, n_hud_eval),
        "n_evaluated": n_hud_eval,
        "n_correct": n_hud_correct,
        "zones_unpopulated": hud_empty,
        "row_classes": hud_row_classes,
        "pred_classes": hud_cols,
        "confusion": hud_confusion,
        "per_class": hud_per_class,
        "per_zone": _zone_per_zone_list(zone_index, zone_agg, "hud_version"),
    }
    im_block = {
        "accuracy": _safe_div(n_im_correct, n_im_eval),
        "n_evaluated": n_im_eval,
        "n_correct": n_im_correct,
        "zones_unpopulated": in_match_empty,
        "row_classes": im_classes,
        "pred_classes": im_cols,
        "confusion": im_confusion,
        "per_class": im_per_class,
        "per_zone": _zone_per_zone_list(zone_index, zone_agg, "in_match"),
    }
    map_block = {
        "accuracy": _safe_div(n_map_correct, n_map_eval),
        "n_evaluated": n_map_eval,
        "n_correct": n_map_correct,
        "zones_unpopulated": map_empty,
        "row_classes": list(MAP_LABELS),
        "pred_classes": list(MAP_LABELS) + ["unknown"],
        "confusion": map_confusion,
        "per_class": map_per_class,
        "per_zone": _zone_per_zone_list(zone_index, zone_agg, "map"),
    }

    return ReportData(
        frame_count_by_class=frame_count_by_class,
        skipped_folders=sorted(skipped_folders),
        skipped_other_hud=skipped_other_hud,
        hud_version_classifier=hud_block,
        in_match_classifier=im_block,
        map_id_classifier=map_block,
    )


# ---------------------------------------------------------------------------
# Report writers
# ---------------------------------------------------------------------------


def write_report(report_data: ReportData, run_metadata: dict, out_dir: str) -> str:
    """Write ``report.json`` per AC7 — three classifier sections. Returns the path."""
    out_path = os.path.join(out_dir, "report.json")
    payload = {
        "tool": "roi_detection_tester (Tool 9)",
        "generated_at": datetime.datetime.now().astimezone().isoformat(),
        "run_metadata": {
            **run_metadata,
            "frame_count_by_class": report_data.frame_count_by_class,
            "skipped_folders": report_data.skipped_folders,
            "skipped_other_hud": report_data.skipped_other_hud,
        },
        "hud_version_classifier": report_data.hud_version_classifier,
        "in_match_classifier": report_data.in_match_classifier,
        "map_id_classifier": report_data.map_id_classifier,
    }
    Path(out_path).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    return out_path


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return "_(no rows)_\n"
    out = ["| " + " | ".join(headers) + " |"]
    out.append("|" + "|".join("---" for _ in headers) + "|")
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out) + "\n"


def _confusion_table(
    confusion: dict[str, dict[str, int]],
    row_classes: list[str],
    pred_classes: list[str] | None = None,
) -> str:
    """Confusion table. ``pred_classes`` defaults to ``row_classes + ['unknown']``
    (symmetric classifiers); the HUD-version classifier passes asymmetric
    ``pred_classes`` (``{config.hud_version, unknown}``)."""
    if pred_classes is None:
        pred_classes = row_classes + ["unknown"]
    headers = ["GT \\ Pred"] + pred_classes
    rows: list[list[str]] = []
    for gt in row_classes:
        row = [gt]
        for pred in pred_classes:
            row.append(str(confusion.get(gt, {}).get(pred, 0)))
        rows.append(row)
    return _md_table(headers, rows)


def _per_class_table(per_class: dict[str, dict[str, float]], classes: list[str]) -> str:
    headers = ["class", "precision", "recall", "F1", "support"]
    rows: list[list[str]] = []
    for cls in classes:
        m = per_class.get(cls, {})
        rows.append([
            cls,
            f"{m.get('precision', 0.0):.3f}",
            f"{m.get('recall', 0.0):.3f}",
            f"{m.get('f1', 0.0):.3f}",
            str(int(m.get("support", 0))),
        ])
    return _md_table(headers, rows)


def _worst_zones_table(per_zone: list[dict], top_n: int = 10) -> str:
    # Only count zones that actually had positives — otherwise the F1=0.0 floor
    # is just "this zone had no GT support", which isn't a quality signal.
    scored = [z for z in per_zone if (z["tp"] + z["fn"]) > 0]
    scored.sort(key=lambda z: (z["f1"], -z["fp"] - z["fn"]))
    headers = ["zone", "class", "kind", "TP", "FP", "FN", "P", "R", "F1"]
    rows: list[list[str]] = []
    for z in scored[:top_n]:
        rows.append([
            z["zone_id"], z["owning_class"], z["kind"],
            str(z["tp"]), str(z["fp"]), str(z["fn"]),
            f"{z['precision']:.3f}", f"{z['recall']:.3f}", f"{z['f1']:.3f}",
        ])
    return _md_table(headers, rows)


def _worst_confused_pairs(confusion: dict[str, dict[str, int]], top_n: int = 5) -> str:
    pairs: list[tuple[str, str, int, int]] = []
    for gt, row in confusion.items():
        support = sum(int(v) for v in row.values())
        for pred, count in row.items():
            if pred == gt:
                continue
            if count <= 0:
                continue
            pairs.append((gt, pred, int(count), support))
    pairs.sort(key=lambda p: p[2], reverse=True)
    headers = ["GT", "predicted", "count", "fraction"]
    rows: list[list[str]] = []
    for gt, pred, count, support in pairs[:top_n]:
        frac = (count / support) if support else 0.0
        rows.append([gt, pred, str(count), f"{frac:.3f}"])
    return _md_table(headers, rows)


def _accuracy_line(block: dict) -> str:
    """Top-line accuracy text, with the AC8 empty-zones header variant."""
    if block.get("zones_unpopulated"):
        return f"**Accuracy:** 0.000 — zones unpopulated ({block['n_correct']}/{block['n_evaluated']})"
    return (
        f"**Accuracy:** {block['accuracy']:.3f} "
        f"({block['n_correct']}/{block['n_evaluated']})"
    )


def _classifier_section(
    lines: list[str], title: str, block: dict,
) -> None:
    lines.append(f"## {title}")
    lines.append("")
    lines.append(_accuracy_line(block))
    lines.append("")
    lines.append("### Confusion (rows = ground truth, columns = predicted)")
    lines.append("")
    lines.append(_confusion_table(
        block["confusion"], block["row_classes"], block["pred_classes"]
    ))
    lines.append("### Per-class precision / recall / F1")
    lines.append("")
    lines.append(_per_class_table(block["per_class"], block["row_classes"]))
    lines.append("### Worst-performing zones (top 10 by F1)")
    lines.append("")
    lines.append(_worst_zones_table(block["per_zone"], top_n=10))
    lines.append("### Worst-confused pairs (top 5 by off-diagonal count)")
    lines.append("")
    lines.append(_worst_confused_pairs(block["confusion"], top_n=5))


def write_summary(report_data: ReportData, run_metadata: dict, out_dir: str) -> str:
    """Write ``summary.md`` — canonical order HUD-version → in_match → map-ID."""
    out_path = os.path.join(out_dir, "summary.md")
    lines: list[str] = []
    lines.append("# Tool 9 — ROI Detection Tester report")
    lines.append("")
    lines.append("## Run")
    lines.append("")
    lines.append(f"- config: `{run_metadata.get('config_path', '')}`")
    lines.append(f"- labeled: `{run_metadata.get('labeled_path', '')}`")
    lines.append(f"- hud_version: `{run_metadata.get('hud_version', '')}`")
    lines.append(
        f"- ref_height: `{run_metadata.get('ref_height', '')}` "
        f"(source: {run_metadata.get('ref_height_source', '')})"
    )
    lines.append(
        f"- thresholds: hud_version=`{run_metadata.get('hud_version_threshold', 0.5)}`; "
        f"in_match=`{run_metadata.get('in_match_threshold', 0.5)}`; "
        f"map=`{run_metadata.get('map_threshold', '')}`"
    )
    limit = run_metadata.get("limit_per_class")
    lines.append(f"- limit_per_class: `{limit if limit is not None else 'all'}`")
    lines.append(f"- skipped_other_hud frames: `{report_data.skipped_other_hud}`")
    lines.append("")

    lines.append("### Frame counts by folder")
    lines.append("")
    rows = [[k, str(v)] for k, v in sorted(report_data.frame_count_by_class.items())]
    lines.append(_md_table(["folder", "count"], rows))

    if report_data.skipped_folders:
        lines.append("Other-HUD `<hud_dir>/<folder>` (in_match/map not evaluated "
                     f"for those frames): {', '.join(report_data.skipped_folders)}")
        lines.append("")

    _classifier_section(lines, "HUD-version classifier",
                         report_data.hud_version_classifier)
    _classifier_section(lines, "Binary in_match classifier",
                         report_data.in_match_classifier)
    _classifier_section(lines, "Per-map ID classifier",
                         report_data.map_id_classifier)

    Path(out_path).write_text("\n".join(lines), encoding="utf-8")
    return out_path


def write_frame_predictions(per_frame_results: list[FrameResult], out_dir: str) -> str:
    """Write the opt-in ``frame_predictions.csv`` (AC9 column set). Returns the path."""
    out_path = os.path.join(out_dir, "frame_predictions.csv")
    with open(out_path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow([
            "frame_path",
            "ground_truth_hud_version", "predicted_hud_version", "hud_version_confidence",
            "ground_truth_in_match", "predicted_in_match", "in_match_confidence",
            "ground_truth_map_id", "predicted_map_id", "map_id_confidence",
        ])
        for fr in per_frame_results:
            writer.writerow([
                fr.frame_path,
                fr.gt_hud, fr.pred_hud, f"{fr.hud_conf:.4f}",
                fr.gt_in_match or "",
                fr.pred_in_match if fr.pred_in_match is not None else "",
                f"{fr.in_match_conf:.4f}" if fr.gt_in_match is not None else "",
                fr.gt_map or "",
                fr.pred_map if fr.pred_map is not None else "",
                f"{fr.map_conf:.4f}" if fr.gt_map is not None else "",
            ])
    return out_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _existing_file_or_error(parser: argparse.ArgumentParser, label: str, value: str) -> str:
    if not os.path.isfile(value):
        parser.error(f"{label} not found: {value}")
    return value


def _existing_dir_or_error(parser: argparse.ArgumentParser, label: str, value: str) -> str:
    if not os.path.isdir(value):
        parser.error(f"{label} not found: {value}")
    return value


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Tool 9 - ROI Detection Tester: per-frame validation of an "
        "emitted map_config.<hud_version>.json (unified schema) against Tool 6's "
        "labeled PNG dataset. Reports three classifiers: HUD-version, binary "
        "in_match, and per-map ID."
    )
    parser.add_argument(
        "--config", default=None,
        help="Path to an emitted map_config.<hud_version>.json. Default: "
        "newest map_config.*.json under apps/tooling/output/map_configs.",
    )
    parser.add_argument(
        "--labeled", default=None,
        help="Tool 6's labeled-dataset root (default: apps/tooling/output/labeled). "
        "Every v* HUD dir present is scanned.",
    )
    parser.add_argument(
        "--output", default=None,
        help="Report-output root (default: apps/tooling/output/roi_detection_tests).",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Cap frames per (hud, class) at N (positive int; default: no cap).",
    )
    parser.add_argument(
        "--ref-height", type=int, default=None, dest="ref_height",
        help="Override the reference resolution (rows). Default: the config's "
        "reference_resolution.height.",
    )
    parser.add_argument(
        "--hud-version-threshold", type=float, default=0.5,
        dest="hud_version_threshold",
        help="Min zone-fire ratio for the HUD-version classifier to commit "
        "(default: 0.5; below -> 'unknown').",
    )
    parser.add_argument(
        "--in-match-threshold", type=float, default=0.5, dest="in_match_threshold",
        help="Min zone-fire ratio for the binary in_match classifier to predict "
        "'in_match' (default: 0.5; below -> 'not_in_match').",
    )
    parser.add_argument(
        "--map-threshold", type=float, default=None, dest="map_threshold",
        help="Override the per-map identification threshold. Default: the "
        "config's minimap_identification.identification_threshold.",
    )
    parser.add_argument(
        "--save-frame-predictions", action="store_true", dest="save_frame_predictions",
        help="Also write a per-frame predictions CSV (opt-in; off by default).",
    )
    args = parser.parse_args(argv)

    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be a positive integer")
    if args.ref_height is not None and args.ref_height < 1:
        parser.error("--ref-height must be a positive integer")
    if not (0.0 <= args.hud_version_threshold <= 1.0):
        parser.error("--hud-version-threshold must be in [0.0, 1.0]")
    if not (0.0 <= args.in_match_threshold <= 1.0):
        parser.error("--in-match-threshold must be in [0.0, 1.0]")
    if args.map_threshold is not None and not (0.0 <= args.map_threshold <= 1.0):
        parser.error("--map-threshold must be in [0.0, 1.0]")

    # Resolve defaults BEFORE existence checks.
    if args.config is None:
        args.config = _default_config_path()
        if args.config is None:
            parser.error(
                "No --config provided and no map_config.*.json under "
                f"{_default_map_configs_root()} - run map_config_emitter first."
            )
    _existing_file_or_error(parser, "--config", args.config)

    if args.labeled is None:
        args.labeled = _default_labeled_dir()
    _existing_dir_or_error(parser, "--labeled", args.labeled)

    if args.output is None:
        args.output = _default_output_dir()
    return args


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)  # argparse.error propagates SystemExit on bad input

    try:
        config = load_map_config(args.config)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"  ERROR: cannot load map config '{args.config}': {exc}", file=sys.stderr)
        return 1

    if args.ref_height is not None:
        ref_height, ref_height_source = int(args.ref_height), "--ref-height"
    else:
        ref_height, ref_height_source = config.ref_height, "config"

    norm_hud = _normalize_hud(config.hud_version)
    resolved_map_threshold = (
        config.identification_threshold if args.map_threshold is None
        else float(args.map_threshold)
    )

    print(f"Config:   {os.path.abspath(args.config)}", flush=True)
    print(f"Labeled:  {os.path.abspath(args.labeled)}", flush=True)
    print(f"HUD ver:  {config.hud_version} (normalized: {norm_hud})", flush=True)
    print(
        f"Ref H:    {ref_height} (source: {ref_height_source}); "
        f"thresholds: hud={args.hud_version_threshold} "
        f"in_match={args.in_match_threshold} map={resolved_map_threshold}",
        flush=True,
    )
    print(f"Frames:   scanning {args.labeled} (all v* dirs) ...", flush=True)

    per_frame: list[FrameResult] = []
    current_key: tuple[str, str] | None = None
    folder_start = 0
    for frame_path, hud_dir, folder, frame_bgr in iter_labeled_frames(
        args.labeled, limit_per_class=args.limit,
    ):
        key = (hud_dir, folder)
        if key != current_key:
            if current_key is not None:
                print(
                    f"  [{current_key[0]}/{current_key[1]}] "
                    f"{len(per_frame) - folder_start} frame(s) done",
                    flush=True,
                )
            current_key = key
            folder_start = len(per_frame)
            print(f"  [{hud_dir}/{folder}] processing ...", flush=True)
        frame_at_ref = _resize_to_ref(frame_bgr, ref_height)
        result = evaluate_frame(
            frame_at_ref, config, hud_dir, folder,
            hud_version_threshold=args.hud_version_threshold,
            in_match_threshold=args.in_match_threshold,
            map_threshold=args.map_threshold,
        )
        result.frame_path = frame_path
        per_frame.append(result)
    if current_key is not None:
        print(
            f"  [{current_key[0]}/{current_key[1]}] "
            f"{len(per_frame) - folder_start} frame(s) done",
            flush=True,
        )

    if not per_frame:
        print(
            f"  ERROR: no readable PNG frames found under {args.labeled} "
            f"(expected <labeled>/v*/<class>/*.png)",
            file=sys.stderr,
        )
        return 1

    report_data = aggregate_metrics(per_frame, config)

    # Compose the output directory: <output>/<normalized hud>/<timestamp>/
    timestamp = datetime.datetime.now().astimezone().strftime("%Y-%m-%dT%H%M%S")
    out_dir = os.path.join(args.output, norm_hud, timestamp)
    try:
        os.makedirs(out_dir, exist_ok=True)
    except OSError as exc:
        print(f"  ERROR: cannot create output directory '{out_dir}': {exc}", file=sys.stderr)
        return 1

    run_metadata = {
        "config_path": os.path.abspath(args.config),
        "labeled_path": os.path.abspath(args.labeled),
        "hud_version": config.hud_version,
        "hud_version_normalized": norm_hud,
        "ref_height": ref_height,
        "ref_height_source": ref_height_source,
        "hud_version_threshold": float(args.hud_version_threshold),
        "in_match_threshold": float(args.in_match_threshold),
        "map_threshold": float(resolved_map_threshold),
        "map_threshold_source": (
            "config" if args.map_threshold is None else "--map-threshold"
        ),
        "limit_per_class": args.limit,
    }

    try:
        write_report(report_data, run_metadata, out_dir)
        write_summary(report_data, run_metadata, out_dir)
        if args.save_frame_predictions:
            write_frame_predictions(per_frame, out_dir)
    except OSError as exc:
        print(f"  ERROR: writing report failed: {exc}", file=sys.stderr)
        return 1

    print(f"Tool 9 wrote report to {out_dir}")
    hv = report_data.hud_version_classifier
    im = report_data.in_match_classifier
    mp = report_data.map_id_classifier
    print(
        f"  HUD-version accuracy: {hv['accuracy']:.3f} "
        f"({hv['n_correct']}/{hv['n_evaluated']})"
        f"{' - zones unpopulated' if hv['zones_unpopulated'] else ''}"
    )
    print(
        f"  in_match accuracy:    {im['accuracy']:.3f} "
        f"({im['n_correct']}/{im['n_evaluated']})"
        f"{' - zones unpopulated' if im['zones_unpopulated'] else ''}"
    )
    print(
        f"  map-ID accuracy:      {mp['accuracy']:.3f} "
        f"({mp['n_correct']}/{mp['n_evaluated']})"
        f"{' - zones unpopulated' if mp['zones_unpopulated'] else ''}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
