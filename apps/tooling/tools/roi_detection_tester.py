"""ROI Detection Tester — Tool 9: per-frame validation of Tool 8's discovered zones.

Consumes Tool 8's hand-merge fragment (``output/auto_rois/v<ver>/discovered_zones.yaml``)
+ Tool 6's labeled PNG dataset (``output/labeled/v<ver>/<class>/*.png``); replays every
labeled frame through every discovered zone's hue-wrap ``cv2.inRange`` band test
(reusing :func:`auto_roi_discoverer.validator.band_inrange_ratio` — no reinvention);
aggregates fires into TP/FP/FN/TN per zone and per-classifier confusion matrices for
**both** the 4-way game-state classifier (``lobby`` / ``in_match`` / ``score`` /
``transition``) and the N-way map-ID classifier (per-map zones), and writes:

* ``report.json`` — machine-readable: per-zone TP/FP/FN/TN/P/R/F1, per-class confusion
  + P/R/F1, run metadata;
* ``summary.md`` — human-readable top-line accuracies + confusion tables + worst zones;
* ``frame_predictions.csv`` (opt-in) — one row per evaluated frame.

Headless batch tool — **no GUI**. Closes the per-frame validation gap Tool 8's
``GameStateValidator`` explicitly deferred (it's a mean/std proxy; this is per-frame).
Tool 9 still **never** writes ``config/config.yaml`` — the hand-merge into config + the
``map_config.json`` v2 regen remain the future re-fingerprinting story's job.

Usage::

    python tools/roi_detection_tester.py [--zones PATH] [--labeled DIR] [--output DIR]
        [--version v2.0] [--limit N] [--ref-height H]
        [--game-state-threshold 0.5] [--map-threshold 0.5]
        [--save-frame-predictions]
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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

# Absolute path insertion so ``tools.*`` imports resolve regardless of CWD.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cv2  # noqa: E402
import numpy as np  # noqa: E402
import yaml  # noqa: E402

from tools.auto_roi_discoverer.model import (  # noqa: E402
    TARGET_CLASSES,
    HsvBand,
    Rect,
)
from tools.auto_roi_discoverer.validator import band_inrange_ratio  # noqa: E402
from tools.frame_labeler import MAP_LABELS  # noqa: E402
from tools.overlay_stack_analyzer import _default_input_dir as _tool7_default_labeled  # noqa: E402


# ---------------------------------------------------------------------------
# Defaults (path math intentionally identical to Tools 6/7/8)
# ---------------------------------------------------------------------------


def _tooling_root() -> str:
    """``apps/tooling`` — one level up from ``tools/``."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _default_labeled_dir() -> str:
    """Tool 6's labeled-dataset root — identical to Tool 7's ``--input`` default."""
    return _tool7_default_labeled()


def _default_output_dir() -> str:
    """``apps/tooling/output/roi_detection_tests`` — sibling of Tools 6/7/8 outputs."""
    return os.path.join(_tooling_root(), "output", "roi_detection_tests")


def _default_auto_rois_root() -> str:
    """``apps/tooling/output/auto_rois`` — Tool 8's export root."""
    return os.path.join(_tooling_root(), "output", "auto_rois")


def _version_sort_key(name: str) -> tuple:
    """Natural sort key for ``v<major>.<minor>``-style HUD-version dirs so ``v10.0`` >
    ``v2.0`` (lexicographic comparison would put ``v10.0`` < ``v2.0``). Non-numeric
    components fall back to lexicographic ordering at the end of the key tuple."""
    parts = str(name).lstrip("v").split(".")
    key = []
    for part in parts:
        try:
            key.append((0, int(part)))   # numeric component sorts before non-numeric
        except ValueError:
            key.append((1, part))
    return tuple(key)


def _default_zones_path() -> str | None:
    """Locate the most-recent ``v*/discovered_zones.yaml`` under Tool 8's export root.

    Sort by natural version order on the directory name (``v10.0 > v2.0``); ties →
    most-recent mtime. ``None`` if no ``v*/`` directory holds a ``discovered_zones.yaml``.
    """
    root = _default_auto_rois_root()
    if not os.path.isdir(root):
        return None
    try:
        children = sorted(os.listdir(root))
    except OSError:
        return None
    candidates: list[tuple[str, str, float]] = []
    for name in children:
        if not name.startswith("v"):
            continue
        try:
            dir_path = os.path.join(root, name)
            if not os.path.isdir(dir_path):
                continue
            zone_path = os.path.join(dir_path, "discovered_zones.yaml")
            if not os.path.isfile(zone_path):
                continue
            try:
                mtime = os.path.getmtime(zone_path)
            except OSError:
                mtime = 0.0
        except OSError:
            continue  # skip stale symlinks / permission glitches per-entry rather than aborting
        candidates.append((name, zone_path, mtime))
    if not candidates:
        return None
    candidates.sort(key=lambda c: (_version_sort_key(c[0]), c[2]))
    return candidates[-1][1]


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ZoneSpec:
    """A single zone: its class membership + its rect + its HSV band.

    Composes the reused :class:`tools.auto_roi_discoverer.model.Rect` and
    :class:`HsvBand` — does NOT redefine them.
    """

    name: str
    owning_class: str
    kind: str  # "game_state" | "map"
    rect: Rect
    band: HsvBand


@dataclass
class ZonesFragment:
    """Loaded Tool 8 fragment, split by classifier."""

    metadata: dict
    game_state_zones: dict[str, list[ZoneSpec]]   # ordered TARGET_CLASSES
    map_zones: dict[str, list[ZoneSpec]]          # ordered MAP_LABELS
    ignored_classes: list[str]


@dataclass
class FrameResult:
    """Per-frame evaluation snapshot — what ``aggregate_metrics`` folds over."""

    frame_path: str
    folder: str
    gt_game_state: str | None    # lobby / in_match / score / transition / None (skipped)
    gt_map: str | None           # the MAP_LABELS folder name, or None
    zone_fires: dict[tuple[str, str], bool]   # (owning_class, zone_name) -> fired?
    gs_scores: dict[str, float]
    gs_predicted: str            # one of TARGET_CLASSES or "unknown"
    gs_max_score: float
    map_scores: dict[str, float]
    map_predicted: str | None    # one of MAP_LABELS or "unknown", None when GT skips map-ID
    map_max_score: float


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

    n_zones_by_class: dict[str, int]
    frame_count_by_class: dict[str, int]
    skipped_folders: list[str]
    per_zone: list[dict]
    game_state: dict
    map_id: dict


# ---------------------------------------------------------------------------
# load_zones_fragment
# ---------------------------------------------------------------------------


_REQUIRED_ZONE_KEYS = ("x", "y", "width", "height", "hsv")
_REQUIRED_HSV_KEYS = ("h_center", "h_tol", "s_center", "s_tol", "v_center", "v_tol")


def _parse_zone_dict(raw: dict, owning_class: str, kind: str) -> ZoneSpec:
    """Validate + build a :class:`ZoneSpec` from one zone dict. Raises ``ValueError``
    with a user-readable message on missing/bad shape.
    """
    if not isinstance(raw, dict):
        raise ValueError(f"zone entry in class '{owning_class}' is not a mapping: {raw!r}")
    name = str(raw.get("name") or "")
    if not name:
        raise ValueError(f"zone in class '{owning_class}' has no 'name' field")
    missing = [k for k in _REQUIRED_ZONE_KEYS if k not in raw]
    if missing:
        raise ValueError(
            f"zone '{name}' (class '{owning_class}') missing required keys: {', '.join(missing)}"
        )
    hsv = raw.get("hsv") or {}
    if not isinstance(hsv, dict):
        raise ValueError(f"zone '{name}' (class '{owning_class}') 'hsv' must be a mapping")
    hsv_missing = [k for k in _REQUIRED_HSV_KEYS if k not in hsv]
    if hsv_missing:
        raise ValueError(
            f"zone '{name}' (class '{owning_class}') 'hsv' missing keys: {', '.join(hsv_missing)}"
        )
    rect = Rect(x=raw["x"], y=raw["y"], width=raw["width"], height=raw["height"])
    band = HsvBand(
        h_center=hsv["h_center"], h_tol=hsv["h_tol"],
        s_center=hsv["s_center"], s_tol=hsv["s_tol"],
        v_center=hsv["v_center"], v_tol=hsv["v_tol"],
        min_ratio=float(raw.get("min_ratio", 0.3)),
    )
    return ZoneSpec(name=name, owning_class=owning_class, kind=kind, rect=rect, band=band)


def load_zones_fragment(path: str) -> ZonesFragment:
    """Read a Tool 8 ``discovered_zones.yaml`` / ``.json`` and split by classifier.

    Empty class lists tolerated (e.g. live yaml has ``lobby: []``). Unknown top-level
    keys (not in ``TARGET_CLASSES`` ∪ ``MAP_LABELS`` and not ``_metadata``) warn to
    stderr and land in ``ignored_classes``. Bad-shape zone dict → ``ValueError``.
    """
    suffix = Path(path).suffix.lower()
    with open(path, "r", encoding="utf-8") as fh:
        if suffix == ".json":
            data = json.load(fh)
        else:
            data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"top-level of '{path}' must be a mapping, got {type(data).__name__}")

    metadata = data.get("_metadata") or {}
    game_state: dict[str, list[ZoneSpec]] = {cls: [] for cls in TARGET_CLASSES}
    maps: dict[str, list[ZoneSpec]] = {cls: [] for cls in MAP_LABELS}
    ignored: list[str] = []

    for key, value in data.items():
        if key == "_metadata":
            continue
        if key in TARGET_CLASSES:
            for raw in value or []:
                game_state[key].append(_parse_zone_dict(raw, key, "game_state"))
        elif key in MAP_LABELS:
            for raw in value or []:
                maps[key].append(_parse_zone_dict(raw, key, "map"))
        else:
            ignored.append(str(key))
            print(f"  WARN: ignoring unknown class '{key}' in zones fragment", file=sys.stderr)

    return ZonesFragment(
        metadata=metadata if isinstance(metadata, dict) else {},
        game_state_zones=game_state,
        map_zones=maps,
        ignored_classes=ignored,
    )


# ---------------------------------------------------------------------------
# Frame I/O + resize
# ---------------------------------------------------------------------------


def _read_frame_bgr(path: str) -> np.ndarray | None:
    """Windows non-ASCII-path-safe PNG read (``imdecode`` + ``np.fromfile`` — same
    pattern Tools 6/7/8 use). Returns ``None`` on failure (caller logs + skips)."""
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
    already at ``ref_height``, return as-is (no copy). A zero-height frame (corrupt
    decode) is returned as-is rather than crashing with ``ZeroDivisionError``."""
    h, w = int(frame_bgr.shape[0]), int(frame_bgr.shape[1])
    if h <= 0:
        return frame_bgr  # caller already filters None; this guards against a 0-row decode
    if h == ref_height:
        return frame_bgr
    target_w = max(1, int(round(w * (ref_height / float(h)))))
    interp = cv2.INTER_AREA if ref_height < h else cv2.INTER_LINEAR
    return cv2.resize(frame_bgr, (target_w, ref_height), interpolation=interp)


def iter_labeled_frames(
    labeled_root: str,
    version: str,
    *,
    limit_per_class: int | None = None,
) -> Iterator[tuple[str, str, np.ndarray]]:
    """Yield ``(frame_path, folder_name, frame_bgr)`` for every readable PNG under
    ``<labeled_root>/<version>/<class>/*.png``, in sorted ``(class, file)`` order.
    Unreadable files are warned and skipped (don't crash the batch). When
    ``limit_per_class`` is set, only the first N files per class are yielded.
    """
    version_dir = os.path.join(labeled_root, version)
    if not os.path.isdir(version_dir):
        return
    try:
        class_dirs = sorted(os.listdir(version_dir))
    except OSError as exc:
        print(
            f"  WARN: cannot list {version_dir} ({exc}) — yielding no frames",
            file=sys.stderr, flush=True,
        )
        return
    for class_name in class_dirs:
        class_dir = os.path.join(version_dir, class_name)
        if not os.path.isdir(class_dir):
            continue
        pngs = sorted(glob.glob(os.path.join(class_dir, "*.png")))
        if limit_per_class is not None:
            pngs = pngs[: int(limit_per_class)]
        for frame_path in pngs:
            img = _read_frame_bgr(frame_path)
            if img is None:
                print(f"  WARN: cannot read {frame_path} — skipping", file=sys.stderr)
                continue
            yield frame_path, class_name, img


# ---------------------------------------------------------------------------
# Per-frame band-fire test (reuses Tool 8's hue-wrap cv2.inRange logic)
# ---------------------------------------------------------------------------


def zone_fires_on_frame(zone: ZoneSpec, frame_bgr_at_ref: np.ndarray) -> tuple[bool, float]:
    """Per-frame band-fire test for one zone on a reference-height-resized BGR frame.

    Reuses :func:`tools.auto_roi_discoverer.validator.band_inrange_ratio` — same
    hue-wrap ``cv2.inRange`` + ``bitwise_or`` logic, no reinvention. Clips the rect
    to the frame first to survive zones drawn off the edge.
    """
    h, w = int(frame_bgr_at_ref.shape[0]), int(frame_bgr_at_ref.shape[1])
    rect = zone.rect.clamp_to((h, w, 3))
    ratio = float(band_inrange_ratio(zone.band, rect, frame_bgr_at_ref))
    return (ratio >= zone.band.min_ratio, ratio)


# ---------------------------------------------------------------------------
# Folder → ground-truth mapping
# ---------------------------------------------------------------------------


_GS_DIRECT = {"lobby": "lobby", "score": "score", "transition": "transition"}


def _folder_to_gs(folder: str, map_labels: tuple[str, ...] | list[str]) -> str | None:
    """Folder name → game-state ground truth. Returns ``None`` for an unrecognised
    folder (caller records it in ``skipped_folders``)."""
    if folder in _GS_DIRECT:
        return _GS_DIRECT[folder]
    if folder in map_labels:
        return "in_match"
    return None


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
    tie-break by the natural ``ordered_classes`` order. Below threshold → ``"unknown"``.
    A score of exactly 0.0 always returns ``"unknown"`` (no zone fired — nothing to
    predict from — regardless of whether ``threshold`` is also 0.0). Ties on the
    max score use ``math.isclose`` rather than exact float equality so the tie-break
    is deterministic across float environments.
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
    fragment: ZonesFragment,
    folder: str,
    *,
    game_state_threshold: float = 0.5,
    map_threshold: float = 0.5,
) -> FrameResult:
    """Apply every zone in the fragment to one labeled frame; return a
    :class:`FrameResult` carrying the per-zone fires, the per-classifier score
    vectors, and the predicted classes (per AC4/AC5).
    """
    gt_gs = _folder_to_gs(folder, MAP_LABELS)
    gt_map = folder if folder in MAP_LABELS else None

    zone_fires: dict[tuple[str, str], bool] = {}

    gs_scores: dict[str, float] = {}
    gs_zone_counts: dict[str, int] = {}
    for cls in TARGET_CLASSES:
        zones = fragment.game_state_zones.get(cls, [])
        n_zones = len(zones)
        gs_zone_counts[cls] = n_zones
        if n_zones == 0:
            continue
        fires = 0
        for z in zones:
            fired, _ratio = zone_fires_on_frame(z, frame_bgr_at_ref)
            zone_fires[(cls, z.name)] = fired
            if fired:
                fires += 1
        gs_scores[cls] = fires / float(n_zones)

    gs_predicted, gs_max = _argmax_with_threshold(
        gs_scores,
        threshold=float(game_state_threshold),
        ordered_classes=TARGET_CLASSES,
        zone_counts=gs_zone_counts,
    )

    # Apply every per-map zone to every frame so the per-zone FP/TN tallies cover
    # non-map folders too. Map-ID *prediction* only commits when the folder itself
    # is in MAP_LABELS — see AC5.
    map_scores: dict[str, float] = {}
    map_zone_counts: dict[str, int] = {}
    for cls in MAP_LABELS:
        zones = fragment.map_zones.get(cls, [])
        n_zones = len(zones)
        map_zone_counts[cls] = n_zones
        if n_zones == 0:
            continue
        fires = 0
        for z in zones:
            fired, _ratio = zone_fires_on_frame(z, frame_bgr_at_ref)
            zone_fires[(cls, z.name)] = fired
            if fired:
                fires += 1
        map_scores[cls] = fires / float(n_zones)

    map_predicted: str | None
    if folder in MAP_LABELS:
        map_predicted, map_max = _argmax_with_threshold(
            map_scores,
            threshold=float(map_threshold),
            ordered_classes=tuple(MAP_LABELS),
            zone_counts=map_zone_counts,
        )
    else:
        # Non-map folders don't commit a map-ID prediction (AC5), but we preserve
        # the per-class fire scores so downstream debug introspection
        # (frame_predictions.csv, future report consumers) can still see which map
        # zones false-fired on those frames.
        map_predicted = None
        map_max = 0.0

    return FrameResult(
        frame_path="",
        folder=folder,
        gt_game_state=gt_gs,
        gt_map=gt_map,
        zone_fires=zone_fires,
        gs_scores=gs_scores,
        gs_predicted=gs_predicted,
        gs_max_score=float(gs_max),
        map_scores=map_scores,
        map_predicted=map_predicted,
        map_max_score=float(map_max),
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

    Precision = TP / Σ predicted=c (over all GT including "unknown" is not used here:
    "unknown" is never a GT, only a prediction). Recall = TP / support_c. F1 = 2PR/(P+R).
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


def aggregate_metrics(
    per_frame_results: list[FrameResult],
    fragment: ZonesFragment,
) -> ReportData:
    """Fold per-frame results into per-zone TP/FP/FN/TN + per-classifier confusion
    matrices + top-line accuracies (per AC7). All divisions guarded against ``/0``.
    """
    # Per-zone aggregates keyed by (owning_class, zone_name).
    zone_index: dict[tuple[str, str], ZoneSpec] = {}
    for cls, zones in fragment.game_state_zones.items():
        for z in zones:
            zone_index[(cls, z.name)] = z
    for cls, zones in fragment.map_zones.items():
        for z in zones:
            zone_index[(cls, z.name)] = z

    zone_agg: dict[tuple[str, str], _ZoneAgg] = {k: _ZoneAgg() for k in zone_index}

    # Confusion matrices: rows = GT, columns = predicted (incl. "unknown").
    gs_confusion: dict[str, dict[str, int]] = {
        cls: {pred: 0 for pred in list(TARGET_CLASSES) + ["unknown"]}
        for cls in TARGET_CLASSES
    }
    map_confusion: dict[str, dict[str, int]] = {
        cls: {pred: 0 for pred in list(MAP_LABELS) + ["unknown"]}
        for cls in MAP_LABELS
    }

    n_gs_eval = 0
    n_gs_correct = 0
    n_map_eval = 0
    n_map_correct = 0
    frame_count_by_class: dict[str, int] = {}
    skipped_folders: set[str] = set()

    for fr in per_frame_results:
        frame_count_by_class[fr.folder] = frame_count_by_class.get(fr.folder, 0) + 1

        # Game-state classifier eval (skip unrecognised folders).
        if fr.gt_game_state is not None:
            n_gs_eval += 1
            gs_confusion.setdefault(fr.gt_game_state, {})
            row = gs_confusion[fr.gt_game_state]
            row[fr.gs_predicted] = row.get(fr.gs_predicted, 0) + 1
            if fr.gs_predicted == fr.gt_game_state:
                n_gs_correct += 1
        else:
            skipped_folders.add(fr.folder)

        # Map-ID classifier eval (only on MAP_LABELS folders).
        if fr.gt_map is not None and fr.map_predicted is not None:
            n_map_eval += 1
            map_confusion.setdefault(fr.gt_map, {})
            row = map_confusion[fr.gt_map]
            row[fr.map_predicted] = row.get(fr.map_predicted, 0) + 1
            if fr.map_predicted == fr.gt_map:
                n_map_correct += 1

        # Per-zone TP/FP/FN/TN. Owning class for a game-state zone = its game-state
        # class (frames whose folder→gs == owning_class are positives, using the
        # AC4 mapping — so MAP_LABELS folders are positives for in_match zones).
        # Owning class for a per-map zone = the map name (only that folder's frames
        # are positives; all other folders incl. lobby/score/transition + other maps
        # are negatives).
        for (owning_class, zone_name), fired in fr.zone_fires.items():
            agg = zone_agg.get((owning_class, zone_name))
            if agg is None:
                continue
            spec = zone_index[(owning_class, zone_name)]
            if spec.kind == "game_state":
                positive = fr.gt_game_state == owning_class
                # Skip the per-zone tally on unrecognised folders for game-state
                # zones — there's no defined positive/negative.
                if fr.gt_game_state is None:
                    continue
            else:  # "map"
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

    per_zone: list[dict] = []
    for (owning_class, zone_name), agg in zone_agg.items():
        spec = zone_index[(owning_class, zone_name)]
        precision = _safe_div(agg.tp, agg.tp + agg.fp)
        recall = _safe_div(agg.tp, agg.tp + agg.fn)
        f1 = _safe_div(2 * precision * recall, precision + recall)
        per_zone.append({
            "name": zone_name,
            "owning_class": owning_class,
            "kind": spec.kind,
            "tp": agg.tp, "fp": agg.fp, "fn": agg.fn, "tn": agg.tn,
            "precision": precision, "recall": recall, "f1": f1,
            "fire_rate_on_owning": _safe_div(agg.fires_on_owning, agg.samples_on_owning),
            "fire_rate_on_others": _safe_div(agg.fires_on_others, agg.samples_on_others),
        })

    gs_per_class = _per_class_from_confusion(gs_confusion, list(TARGET_CLASSES))
    map_per_class = _per_class_from_confusion(map_confusion, list(MAP_LABELS))

    n_zones_by_class: dict[str, int] = {}
    for cls in TARGET_CLASSES:
        n_zones_by_class[cls] = len(fragment.game_state_zones.get(cls, []))
    for cls in MAP_LABELS:
        n_zones_by_class[cls] = len(fragment.map_zones.get(cls, []))

    game_state_block = {
        "accuracy": _safe_div(n_gs_correct, n_gs_eval),
        "n_evaluated": n_gs_eval,
        "n_correct": n_gs_correct,
        "confusion": gs_confusion,
        "per_class": gs_per_class,
    }
    map_id_block = {
        "accuracy": _safe_div(n_map_correct, n_map_eval),
        "n_evaluated": n_map_eval,
        "n_correct": n_map_correct,
        "confusion": map_confusion,
        "per_class": map_per_class,
    }

    return ReportData(
        n_zones_by_class=n_zones_by_class,
        frame_count_by_class=frame_count_by_class,
        skipped_folders=sorted(skipped_folders),
        per_zone=per_zone,
        game_state=game_state_block,
        map_id=map_id_block,
    )


# ---------------------------------------------------------------------------
# Report writers
# ---------------------------------------------------------------------------


def write_report(report_data: ReportData, run_metadata: dict, out_dir: str) -> str:
    """Write ``report.json`` per the AC8 schema. Returns the path."""
    out_path = os.path.join(out_dir, "report.json")
    payload = {
        "tool": "roi_detection_tester (Tool 9)",
        "generated_at": datetime.datetime.now().astimezone().isoformat(),
        "run_metadata": {
            **run_metadata,
            "frame_count_by_class": report_data.frame_count_by_class,
            "n_zones_by_class": report_data.n_zones_by_class,
            "skipped_folders": report_data.skipped_folders,
        },
        "game_state": report_data.game_state,
        "map_id": report_data.map_id,
        "per_zone": report_data.per_zone,
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


def _confusion_table(confusion: dict[str, dict[str, int]], classes: list[str]) -> str:
    pred_classes = classes + ["unknown"]
    headers = ["GT \\ Pred"] + pred_classes
    rows: list[list[str]] = []
    for gt in classes:
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
    # Only count zones that actually had positives — otherwise the F1=0.0 floor is just
    # "this zone had no GT support", which isn't a quality signal.
    scored = [z for z in per_zone if (z["tp"] + z["fn"]) > 0]
    scored.sort(key=lambda z: (z["f1"], -z["fp"] - z["fn"]))
    headers = ["zone", "class", "kind", "TP", "FP", "FN", "P", "R", "F1"]
    rows: list[list[str]] = []
    for z in scored[:top_n]:
        rows.append([
            z["name"], z["owning_class"], z["kind"],
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


def write_summary(report_data: ReportData, run_metadata: dict, out_dir: str) -> str:
    """Write ``summary.md`` — human-readable top-line numbers + confusion tables +
    worst-performing zones + worst-confused class pairs. Returns the path."""
    out_path = os.path.join(out_dir, "summary.md")
    lines: list[str] = []
    lines.append("# Tool 9 — ROI Detection Tester report")
    lines.append("")
    lines.append("## Run")
    lines.append("")
    lines.append(f"- zones: `{run_metadata.get('zones_path', '')}`")
    lines.append(f"- labeled: `{run_metadata.get('labeled_path', '')}`")
    lines.append(
        f"- version: `{run_metadata.get('version', '')}` "
        f"(source: {run_metadata.get('version_source', '')})"
    )
    lines.append(
        f"- ref_height: `{run_metadata.get('ref_height', '')}` "
        f"(source: {run_metadata.get('ref_height_source', '')})"
    )
    lines.append(
        f"- game_state_threshold: `{run_metadata.get('game_state_threshold', 0.5)}`; "
        f"map_threshold: `{run_metadata.get('map_threshold', 0.5)}`"
    )
    limit = run_metadata.get("limit_per_class")
    lines.append(f"- limit_per_class: `{limit if limit is not None else 'all'}`")
    lines.append("")

    lines.append("### Frame counts by folder")
    lines.append("")
    rows = [[k, str(v)] for k, v in sorted(report_data.frame_count_by_class.items())]
    lines.append(_md_table(["folder", "count"], rows))

    if report_data.skipped_folders:
        lines.append("Skipped folders (no game-state mapping): "
                     f"{', '.join(report_data.skipped_folders)}")
        lines.append("")

    gs = report_data.game_state
    lines.append("## Game-state classifier")
    lines.append("")
    lines.append(f"**Accuracy:** {gs['accuracy']:.3f} "
                 f"({gs['n_correct']}/{gs['n_evaluated']})")
    lines.append("")
    lines.append("### Confusion (rows = ground truth, columns = predicted)")
    lines.append("")
    lines.append(_confusion_table(gs["confusion"], list(TARGET_CLASSES)))
    lines.append("### Per-class precision / recall / F1")
    lines.append("")
    lines.append(_per_class_table(gs["per_class"], list(TARGET_CLASSES)))

    mi = report_data.map_id
    lines.append("## Map-ID classifier")
    lines.append("")
    lines.append(f"**Accuracy:** {mi['accuracy']:.3f} "
                 f"({mi['n_correct']}/{mi['n_evaluated']})")
    lines.append("")
    lines.append("### Confusion (rows = ground truth, columns = predicted)")
    lines.append("")
    lines.append(_confusion_table(mi["confusion"], list(MAP_LABELS)))
    lines.append("### Per-class precision / recall / F1")
    lines.append("")
    lines.append(_per_class_table(mi["per_class"], list(MAP_LABELS)))

    lines.append("## Worst-performing zones (top 10 by F1)")
    lines.append("")
    lines.append(_worst_zones_table(report_data.per_zone, top_n=10))

    lines.append("## Worst-confused class pairs (top 5 by off-diagonal count)")
    lines.append("")
    lines.append("### Game-state classifier")
    lines.append("")
    lines.append(_worst_confused_pairs(gs["confusion"], top_n=5))
    lines.append("### Map-ID classifier")
    lines.append("")
    lines.append(_worst_confused_pairs(mi["confusion"], top_n=5))

    Path(out_path).write_text("\n".join(lines), encoding="utf-8")
    return out_path


def write_frame_predictions(per_frame_results: list[FrameResult], out_dir: str) -> str:
    """Write the opt-in ``frame_predictions.csv``. Returns the path."""
    out_path = os.path.join(out_dir, "frame_predictions.csv")
    with open(out_path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow([
            "frame_path", "ground_truth_folder",
            "ground_truth_game_state", "predicted_game_state", "gs_max_score",
            "ground_truth_map", "predicted_map", "map_max_score",
        ])
        for fr in per_frame_results:
            writer.writerow([
                fr.frame_path, fr.folder,
                fr.gt_game_state or "", fr.gs_predicted, f"{fr.gs_max_score:.4f}",
                fr.gt_map or "",
                fr.map_predicted if fr.map_predicted is not None else "",
                f"{fr.map_max_score:.4f}",
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
        description="Tool 9 — ROI Detection Tester: per-frame validation of "
        "Tool 8's discovered_zones.yaml against Tool 6's labeled PNG dataset."
    )
    parser.add_argument(
        "--zones", default=None,
        help="Path to Tool 8's discovered_zones.yaml (or .json). "
        "Default: most-recent v*/discovered_zones.yaml under apps/tooling/output/auto_rois.",
    )
    parser.add_argument(
        "--labeled", default=None,
        help="Tool 6's labeled-dataset root (default: apps/tooling/output/labeled).",
    )
    parser.add_argument(
        "--output", default=None,
        help="Report-output root (default: apps/tooling/output/roi_detection_tests).",
    )
    parser.add_argument(
        "--version", default=None,
        help="HUD version override (e.g. v2.0). Default: from zones-yaml _metadata, "
        "else inferred from the zones-yaml parent directory.",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Cap frames per class at N (positive int; default: no cap).",
    )
    parser.add_argument(
        "--ref-height", type=int, default=None, dest="ref_height",
        help="Override the reference resolution (rows). Default: zones-yaml "
        "_metadata.frame_shape[0].",
    )
    parser.add_argument(
        "--game-state-threshold", type=float, default=0.5, dest="game_state_threshold",
        help="Min max-class-score for the game-state classifier to commit (default: 0.5; "
        "below → 'unknown').",
    )
    parser.add_argument(
        "--map-threshold", type=float, default=0.5, dest="map_threshold",
        help="Min max-class-score for the map-ID classifier to commit (default: 0.5; "
        "below → 'unknown').",
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
    if not (0.0 <= args.game_state_threshold <= 1.0):
        parser.error("--game-state-threshold must be in [0.0, 1.0]")
    if not (0.0 <= args.map_threshold <= 1.0):
        parser.error("--map-threshold must be in [0.0, 1.0]")

    # Resolve defaults BEFORE existence checks.
    if args.zones is None:
        args.zones = _default_zones_path()
        if args.zones is None:
            parser.error(
                "No --zones provided and no v*/discovered_zones.yaml under "
                f"{_default_auto_rois_root()} — run Tool 8 first."
            )
    _existing_file_or_error(parser, "--zones", args.zones)

    if args.labeled is None:
        args.labeled = _default_labeled_dir()
    _existing_dir_or_error(parser, "--labeled", args.labeled)

    if args.output is None:
        args.output = _default_output_dir()
    return args


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def _resolve_version(metadata: dict, zones_path: str, override: str | None) -> tuple[str, str]:
    """Pick the HUD version + record its source ('--version' / 'metadata' / 'path')."""
    if override:
        return str(override), "--version"
    md_ver = metadata.get("hud_version")
    if isinstance(md_ver, str) and md_ver:
        return md_ver, "metadata"
    parent = os.path.basename(os.path.dirname(os.path.abspath(zones_path)))
    if parent.startswith("v"):
        return parent, "path"
    return "v_unknown", "path"


def _resolve_ref_height(metadata: dict, override: int | None) -> tuple[int | None, str]:
    if override is not None:
        return int(override), "--ref-height"
    frame_shape = metadata.get("frame_shape")
    if isinstance(frame_shape, (list, tuple)) and len(frame_shape) >= 1:
        try:
            return int(frame_shape[0]), "metadata"
        except (TypeError, ValueError):
            return None, "metadata"
    return None, "metadata"


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)  # argparse.error propagates SystemExit on bad input

    try:
        fragment = load_zones_fragment(args.zones)
    except (OSError, ValueError, yaml.YAMLError, json.JSONDecodeError) as exc:
        print(f"  ERROR: cannot load zones fragment '{args.zones}': {exc}", file=sys.stderr)
        return 1

    version, version_source = _resolve_version(fragment.metadata, args.zones, args.version)
    ref_height, ref_height_source = _resolve_ref_height(fragment.metadata, args.ref_height)
    if ref_height is None:
        print(
            "  ERROR: --ref-height required (zones yaml has no _metadata.frame_shape)",
            file=sys.stderr,
        )
        return 1

    version_dir = os.path.join(args.labeled, version)
    if not os.path.isdir(version_dir):
        print(
            f"  ERROR: labeled-version directory not found: {version_dir}",
            file=sys.stderr,
        )
        return 1

    print(f"Zones:    {os.path.abspath(args.zones)}", flush=True)
    print(f"Labeled:  {os.path.abspath(args.labeled)}", flush=True)
    print(f"Version:  {version} (source: {version_source})", flush=True)
    print(
        f"Ref H:    {ref_height} (source: {ref_height_source}); "
        f"thresholds: gs={args.game_state_threshold} map={args.map_threshold}",
        flush=True,
    )
    print(f"Frames:   scanning {version_dir} ...", flush=True)

    # Coordinate-frame contract: Tool 8 stamps the cell shape its zones were drawn
    # against into _metadata.frame_shape. If our post-resize frames don't match, the
    # zones may silently clip — warn once on the first frame, then carry on (the user
    # may want to deliberately test new aspect ratios against existing zones).
    coord_frame_shape = fragment.metadata.get("frame_shape")
    aspect_warning_emitted = False

    # Process every labeled frame. One progress line per folder as it finishes.
    per_frame: list[FrameResult] = []
    current_folder: str | None = None
    folder_start = 0
    for frame_path, folder, frame_bgr in iter_labeled_frames(
        args.labeled, version, limit_per_class=args.limit,
    ):
        if folder != current_folder:
            if current_folder is not None:
                print(
                    f"  [{current_folder}] {len(per_frame) - folder_start} frame(s) done",
                    flush=True,
                )
            current_folder = folder
            folder_start = len(per_frame)
            print(f"  [{folder}] processing ...", flush=True)
        frame_at_ref = _resize_to_ref(frame_bgr, ref_height)
        if not aspect_warning_emitted and coord_frame_shape:
            try:
                expected_h, expected_w = int(coord_frame_shape[0]), int(coord_frame_shape[1])
                actual_h, actual_w = int(frame_at_ref.shape[0]), int(frame_at_ref.shape[1])
                if (expected_h, expected_w) != (actual_h, actual_w):
                    print(
                        f"  ⚠ aspect-frame mismatch: zones drawn against {expected_h}x{expected_w} "
                        f"cells; this frame resized to {actual_h}x{actual_w}. Zones with "
                        f"x+width > {actual_w} or y+height > {actual_h} will be silently "
                        f"clipped. Re-run Tool 7 + Tool 8 on the new aspect to refresh.",
                        file=sys.stderr, flush=True,
                    )
            except (TypeError, ValueError, IndexError):
                pass  # malformed metadata — don't crash the run
            aspect_warning_emitted = True
        result = evaluate_frame(
            frame_at_ref, fragment, folder,
            game_state_threshold=args.game_state_threshold,
            map_threshold=args.map_threshold,
        )
        result.frame_path = frame_path
        per_frame.append(result)
    if current_folder is not None:
        print(
            f"  [{current_folder}] {len(per_frame) - folder_start} frame(s) done",
            flush=True,
        )

    if not per_frame:
        print(
            f"  ERROR: no readable PNG frames found under {version_dir}",
            file=sys.stderr,
        )
        return 1

    report_data = aggregate_metrics(per_frame, fragment)

    # Compose the output directory: <output>/<version>/<timestamp>/
    timestamp = datetime.datetime.now().astimezone().strftime("%Y-%m-%dT%H%M%S")
    out_dir = os.path.join(args.output, version, timestamp)
    try:
        os.makedirs(out_dir, exist_ok=True)
    except OSError as exc:
        print(f"  ERROR: cannot create output directory '{out_dir}': {exc}", file=sys.stderr)
        return 1

    run_metadata = {
        "zones_path": os.path.abspath(args.zones),
        "labeled_path": os.path.abspath(args.labeled),
        "version": version,
        "version_source": version_source,
        "ref_height": ref_height,
        "ref_height_source": ref_height_source,
        "game_state_threshold": float(args.game_state_threshold),
        "map_threshold": float(args.map_threshold),
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
    print(
        f"  game-state accuracy: {report_data.game_state['accuracy']:.3f} "
        f"({report_data.game_state['n_correct']}/{report_data.game_state['n_evaluated']})"
    )
    print(
        f"  map-ID accuracy:    {report_data.map_id['accuracy']:.3f} "
        f"({report_data.map_id['n_correct']}/{report_data.map_id['n_evaluated']})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
