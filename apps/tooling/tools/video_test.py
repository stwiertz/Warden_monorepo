"""Video Detection Tester — Tool 11: end-to-end video-pipeline validation.

Consumes one emitted ``map_config.<hud_version>.json`` (the unified-schema config
written by ``map_config_emitter`` / Story 9.9c) and runs the full detection
pipeline against a real video:

  stride-sampled frame extraction (``cv2.VideoCapture``)
    → once-per-session HUD-version sanity classification
    → per-frame binary ``in_match`` classification
    → a timing-derived ``{in_match, score_screen, not_in_match}`` state machine
    → per-``in_match``-span weighted map-ID
    → a deterministic ``results.json``

Closes workflow step #6 (end-to-end video pipeline validation) and gives the
Story 9.9b iterative zone-population loop its real-video acceptance gate
(``zone_picker → emit → video_test → adjust → repeat``).

Headless single file — **no GUI, no Tk, no ``image_inspector``**. Module-level
pure helpers + a thin ``main(argv)``. Reuses Tool 9's per-frame zone-fire logic
verbatim (``tools.roi_detection_tester.zone_fires_on_frame`` /
``_argmax_with_threshold`` / ``_resize_to_ref``, themselves reaching the
hue-wrap ``cv2.inRange`` math in ``tools.common.zones.band_inrange_ratio``) —
the band-matching / hue-wrap / HSV-conversion math is **never reimplemented**.

Usage::

    python apps/tooling/tools/video_test.py <video> [--config <map_config.json>]
        [--output <path>] [--stride <int>] [--threshold <float>]

Recorded design decisions
-------------------------
* **"i-frame" = stride-sampled frame, NOT codec keyframe.** True codec-I-frame
  isolation needs PyAV/ffmpeg — a new dependency forbidden by AC10. The charter
  spec's "i-frame extraction" is read as stride-sampled frames (≈1/sec). No new
  dependency is added; we never shell to ffmpeg.
* **Weighted map-ID aggregation (AC7).** For a frame, for each populated map
  ``slug``: for each zone ``(fired, ratio) = zone_fires_on_frame(...)``; the
  zone's contribution is ``(ratio if fired else 0.0) * effective_weight`` where
  ``effective_weight = weight if weight_override is None else weight_override``.
  Map score ``= sum(contributions) / sum(effective_weight)`` (normalized to
  [0,1]; divide-by-zero guarded to 0.0). Per-frame map is
  ``_argmax_with_threshold(scores, threshold=resolved_threshold,
  ordered_classes=populated_slugs_in_MAP_LABELS_order,
  zone_counts={slug: len(zones)})``. The span's canonical ``map_id`` is the
  most-frequently-argmaxed map across the span (ties → higher mean confidence);
  ``confidence`` is the mean of that map's per-frame scores over the span.
  Tool 9 carries no weighted map reduction (its fragment has no weights), so
  this story's formula is authoritative — no Tool-9 deviation to note.
* **``in_match`` / HUD-version thresholds.** ``in_match`` and the HUD-version
  sanity check reuse Tool 9's group fire-ratio (``fires / n_zones``) gated at a
  fixed ``0.5`` (Tool 9's game-state default — AC6 ties no CLI knob to them).
  Only the per-map identification gate uses the resolved ``--threshold`` /
  ``identification_threshold``.
* **Determinism (AC9 / REL-005).** ``results.json`` is written with a fixed key
  order, ``round(x, 6)`` floats, ``ensure_ascii=False``, and a trailing
  newline, so re-running on the same video+config yields a byte-identical file.
  The timestamped output **directory** name is the only non-deterministic part
  and is explicitly excluded from the determinism claim. ``video``/``config``
  are recorded as basenames (path-independent across machines).
* **AC8 degradation notes go to stderr** (not ``results.json``) so the AC9
  ``results.json`` key set stays exactly as specified.
"""

from __future__ import annotations

import argparse
import datetime
import glob
import json
import math
import os
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

# Absolute path insertion so ``tools.*`` imports resolve regardless of CWD
# (identical posture to Tool 9).
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from tools.common.labels import MAP_LABELS  # noqa: E402
from tools.common.zones import HsvBand, Rect  # noqa: E402

# Sanctioned sibling reuse — Tool 9 is `done`; module import is side-effect-free
# (its main() is __main__-guarded). The hue-wrap cv2.inRange math is reached via
# zone_fires_on_frame; argmax tie-breaking via _argmax_with_threshold; the
# reference-resolution resize via _resize_to_ref. These three symbols' contract
# is pinned by test_video_detection_tester.py so a future 9.14 Tool-9 refit
# cannot silently drift them.
from tools.roi_detection_tester import (  # noqa: E402
    ZoneSpec,
    _argmax_with_threshold,
    _resize_to_ref,
    zone_fires_on_frame,
)

# in_match + HUD-version sanity gates reuse Tool 9's game-state default (0.5).
_IN_MATCH_THRESHOLD = 0.5
_HUD_THRESHOLD = 0.5
# HUD-version sanity classification samples the first N kept frames.
_HUD_SAMPLE_FRAMES = 30


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class _MapZone:
    """A per-map zone plus its AC7 aggregation weights (kept parallel to the
    :class:`ZoneSpec`, which has no weight fields)."""

    spec: ZoneSpec
    weight: float
    weight_override: float | None


@dataclass
class ParsedConfig:
    """The emitted unified-schema ``map_config.<hud>.json`` parsed into the
    Tool-9 reuse surface (:class:`ZoneSpec`) plus the timing/threshold knobs."""

    hud_version: str
    reference_resolution: dict          # {"width": int, "height": int}
    score_screen_duration_ms: int
    identification_threshold: float
    hud_zones: list[ZoneSpec]
    in_match_zones: list[ZoneSpec]
    map_zones: dict[str, list[_MapZone]]
    notes: list[str]                    # AC8 degradation notes (stderr-surfaced)


@dataclass
class Span:
    """A maximal run of ``in_match`` frames + its resolved map-ID."""

    start_frame: int
    end_frame: int
    map_id: str
    confidence: float


@dataclass
class _FrameRecord:
    """Per-kept-frame snapshot the pipeline folds over."""

    frame_idx: int
    timestamp_ms: int
    in_match: bool
    map_argmax: str
    map_scores: dict[str, float]


# ---------------------------------------------------------------------------
# Path defaults
# ---------------------------------------------------------------------------


def _tooling_root() -> str:
    """``apps/tooling`` — one level up from ``tools/`` (Tool 6/7/9 path math)."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _version_sort_key(name: str) -> tuple:
    """Natural sort key for a ``v<major>[.<minor>...]`` token so ``v10`` sorts
    after ``v2`` (lexicographic would invert that). Non-numeric parts fall back
    to lexicographic ordering."""
    parts = str(name).lstrip("v").split(".")
    key: list[tuple[int, object]] = []
    for part in parts:
        try:
            key.append((0, int(part)))
        except ValueError:
            key.append((1, part))
    return tuple(key)


def _default_config_path() -> str | None:
    """Newest ``apps/tooling/output/map_configs/map_config.v*.json`` by natural
    version order, ties broken by mtime. ``None`` if none exist (mirrors Tool
    9's newest-by-version+mtime default-discovery posture)."""
    root = os.path.join(_tooling_root(), "output", "map_configs")
    if not os.path.isdir(root):
        return None
    candidates = glob.glob(os.path.join(root, "map_config.v*.json"))
    if not candidates:
        return None

    def _key(path: str) -> tuple:
        base = os.path.basename(path)              # map_config.v2.json
        ver = base[len("map_config.") : -len(".json")]  # noqa: E203  -> "v2"
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            mtime = 0.0
        return (_version_sort_key(ver), mtime)

    candidates.sort(key=_key)
    return candidates[-1]


# ---------------------------------------------------------------------------
# Config parser (NEW unified-schema parser — NOT Tool 9's load_zones_fragment)
# ---------------------------------------------------------------------------


_TOP_REQUIRED = (
    "schema_version",
    "reference_resolution",
    "hud_version",
    "score_screen_duration_ms",
    "hud_version_detection",
    "in_match_detection",
    "minimap_identification",
)
_ZONE_REQUIRED = ("id", "x", "y", "width", "height", "hsv", "min_ratio")
_HSV_REQUIRED = ("h_center", "h_tol", "s_center", "s_tol", "v_center", "v_tol")


def _zone_to_spec(raw: dict, owning_class: str, kind: str) -> ZoneSpec:
    """Map one unified ``Zone`` dict → a :class:`ZoneSpec`.

    ``HsvBand.min_ratio`` is set **explicitly** from ``zone["min_ratio"]`` — we
    do NOT rely on ``HsvBand``'s ``0.3`` dataclass default (the #3 disaster
    in the story Dev Notes). Raises ``ValueError`` (clean, no traceback at the
    CLI boundary) on a missing/bad-shape zone.
    """
    if not isinstance(raw, dict):
        raise ValueError(f"zone in '{owning_class}' is not a JSON object: {raw!r}")
    missing = [k for k in _ZONE_REQUIRED if k not in raw]
    if missing:
        raise ValueError(
            f"zone '{raw.get('id', '<no id>')}' in '{owning_class}' missing "
            f"required keys: {', '.join(missing)}"
        )
    hsv = raw["hsv"]
    if not isinstance(hsv, dict):
        raise ValueError(f"zone '{raw['id']}' in '{owning_class}': 'hsv' must be an object")
    hsv_missing = [k for k in _HSV_REQUIRED if k not in hsv]
    if hsv_missing:
        raise ValueError(
            f"zone '{raw['id']}' in '{owning_class}': 'hsv' missing keys: "
            f"{', '.join(hsv_missing)}"
        )
    min_ratio = float(raw["min_ratio"])
    if not math.isfinite(min_ratio) or not (0.0 <= min_ratio <= 1.0):
        raise ValueError(
            f"zone '{raw['id']}' in '{owning_class}': min_ratio must be in "
            f"[0.0, 1.0] (got {min_ratio})"
        )
    rect = Rect(x=raw["x"], y=raw["y"], width=raw["width"], height=raw["height"])
    band = HsvBand(
        h_center=hsv["h_center"], h_tol=hsv["h_tol"],
        s_center=hsv["s_center"], s_tol=hsv["s_tol"],
        v_center=hsv["v_center"], v_tol=hsv["v_tol"],
        min_ratio=min_ratio,   # explicit -- never the 0.3 default
    )
    return ZoneSpec(
        name=str(raw["id"]), owning_class=owning_class, kind=kind, rect=rect, band=band
    )


def _load_config(path: str) -> ParsedConfig:
    """Read an emitted ``map_config.<hud_version>.json`` (unified schema) and
    project it onto the Tool-9 reuse surface.

    This is a dedicated parser — ``tools.roi_detection_tester.load_zones_fragment``
    parses a *different* shape (Tool-8 ``discovered_zones.yaml`` keyed by
    ``TARGET_CLASSES``/``MAP_LABELS`` + ``_metadata``) and MUST NOT be used here.

    Empty zone arrays are tolerated (AC8) — an unpopulated classifier is recorded
    in ``notes`` and degrades gracefully at classify time. Missing required
    top-level keys raise ``ValueError`` (clean CLI error, no traceback).
    """
    with open(path, "r", encoding="utf-8-sig") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"top-level of '{path}' must be a JSON object")
    missing = [k for k in _TOP_REQUIRED if k not in data]
    if missing:
        raise ValueError(
            f"map_config '{path}' missing required keys: {', '.join(missing)}"
        )

    ref_res = data["reference_resolution"]
    if not (isinstance(ref_res, dict) and "width" in ref_res and "height" in ref_res):
        raise ValueError("reference_resolution must be an object with width+height")
    try:
        _ref_w, _ref_h = int(ref_res["width"]), int(ref_res["height"])
    except (TypeError, ValueError):
        raise ValueError("reference_resolution width/height must be integers")
    if _ref_w <= 0 or _ref_h <= 0:
        raise ValueError(
            f"reference_resolution width/height must be positive "
            f"(got width={_ref_w}, height={_ref_h})"
        )

    mi = data["minimap_identification"]
    if not isinstance(mi, dict):
        raise ValueError("minimap_identification must be an object")
    for k in ("identification_threshold", "maps"):
        if k not in mi:
            raise ValueError(f"minimap_identification missing required key '{k}'")
    try:
        _id_thr = float(mi["identification_threshold"])
    except (TypeError, ValueError):
        raise ValueError(
            "minimap_identification.identification_threshold must be a number"
        )
    if not math.isfinite(_id_thr) or not (0.0 <= _id_thr <= 1.0):
        raise ValueError(
            f"minimap_identification.identification_threshold must be in "
            f"[0.0, 1.0] (got {_id_thr})"
        )
    if not isinstance(mi["maps"], dict):
        raise ValueError("minimap_identification.maps must be an object")

    notes: list[str] = []

    if not isinstance(data["hud_version_detection"], list):
        raise ValueError("hud_version_detection must be a list")
    hud_zones = [
        _zone_to_spec(z, "hud_version", "game_state")
        for z in data["hud_version_detection"]
    ]
    if not hud_zones:
        notes.append("hud_version_detection unpopulated - HUD-version sanity check skipped")

    if not isinstance(data["in_match_detection"], list):
        raise ValueError("in_match_detection must be a list")
    in_match_zones = [
        _zone_to_spec(z, "in_match", "game_state") for z in data["in_match_detection"]
    ]
    if not in_match_zones:
        notes.append("in_match_detection unpopulated - every frame not_in_match")

    map_zones: dict[str, list[_MapZone]] = {}
    for slug, entry in mi["maps"].items():
        if not isinstance(entry, dict) or "zones" not in entry:
            raise ValueError(f"minimap_identification.maps['{slug}'] missing 'zones'")
        if not isinstance(entry["zones"], list):
            raise ValueError(
                f"minimap_identification.maps['{slug}'].zones must be a list"
            )
        zones: list[_MapZone] = []
        for z in entry["zones"]:
            if not isinstance(z, dict):
                raise ValueError(f"map '{slug}': zone is not a JSON object")
            spec = _zone_to_spec(z, slug, "map")
            if "weight" not in z or "weight_override" not in z:
                raise ValueError(
                    f"map '{slug}' zone '{z.get('id', '<no id>')}' missing "
                    f"weight/weight_override"
                )
            wo = z["weight_override"]
            weight = float(z["weight"])
            weight_override = None if wo is None else float(wo)
            if (
                not math.isfinite(weight)
                or weight < 0
                or (
                    weight_override is not None
                    and (not math.isfinite(weight_override) or weight_override < 0)
                )
            ):
                raise ValueError(
                    f"map '{slug}' zone '{z.get('id', '<no id>')}': weight / "
                    f"weight_override must be finite and non-negative (got "
                    f"weight={weight}, weight_override={weight_override})"
                )
            zones.append(
                _MapZone(
                    spec=spec,
                    weight=weight,
                    weight_override=weight_override,
                )
            )
        map_zones[str(slug)] = zones
    populated_maps = sum(1 for zs in map_zones.values() if zs)
    if populated_maps == 0:
        notes.append("minimap_identification.maps unpopulated - every span map_id=unknown")

    score_screen_duration_ms = int(data["score_screen_duration_ms"])
    if score_screen_duration_ms < 0:
        notes.append(
            f"score_screen_duration_ms is negative ({score_screen_duration_ms}) - "
            "treated like 0 (no score_screen window; falling edge -> not_in_match)"
        )

    return ParsedConfig(
        hud_version=str(data["hud_version"]),
        reference_resolution={
            "width": _ref_w,
            "height": _ref_h,
        },
        score_screen_duration_ms=score_screen_duration_ms,
        identification_threshold=_id_thr,
        hud_zones=hud_zones,
        in_match_zones=in_match_zones,
        map_zones=map_zones,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Frame extraction (cv2.VideoCapture + stride; "i-frame" = stride-sampled)
# ---------------------------------------------------------------------------


class VideoOpenError(RuntimeError):
    """Raised when ``cv2.VideoCapture`` cannot open the input video."""


def _frame_source(
    video: str, stride_override: int | None
) -> tuple[int, Iterator[tuple[int, int, np.ndarray]]]:
    """Open ``video`` once and return ``(resolved_stride, frame_iterator)``.

    ``stride`` default = ``max(1, round(fps))`` where
    ``fps = cap.get(CAP_PROP_FPS) or 30.0`` (≈1 sampled frame/sec). Each yielded
    item is ``(frame_idx, timestamp_ms, frame_bgr)`` where ``frame_idx`` is the
    decode index and ``timestamp_ms`` is ``cap.get(CAP_PROP_POS_MSEC)`` (falling
    back to ``frame_idx / fps * 1000`` when POS_MSEC is 0/unavailable — the
    known wrinkle on some containers). Corrupt decodes are skipped. The capture
    is released in a ``finally``. ``cv2.VideoCapture`` lifecycle mirrors
    ``tools.common.video_player.VideoPlayer`` (not imported — it is a Tk widget).
    """
    cap = cv2.VideoCapture(video)
    if not cap.isOpened():
        cap.release()
        raise VideoOpenError(f"cannot open video: {video}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    # NaN is truthy and fails both `not fps` and `fps <= 0`, so guard it
    # explicitly — some containers report a NaN/inf CAP_PROP_FPS, which would
    # otherwise blow up `int(round(fps))` below with an uncaught ValueError.
    if not fps or not math.isfinite(fps) or fps <= 0:
        fps = 30.0
    stride = (
        max(1, int(stride_override))
        if stride_override is not None
        else max(1, int(round(fps)))
    )

    def _gen() -> Iterator[tuple[int, int, np.ndarray]]:
        try:
            idx = -1
            last_ts = -1
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                idx += 1
                if idx % stride != 0:
                    continue
                if frame is None or getattr(frame, "size", 0) == 0:
                    continue  # corrupt decode — skip, keep going
                pos = cap.get(cv2.CAP_PROP_POS_MSEC)
                if pos and pos > 0 and math.isfinite(pos):
                    ts = int(round(pos))
                else:
                    ts = int(round(idx / fps * 1000.0))
                # Clamp to non-decreasing: a jittery / B-frame-reordered
                # CAP_PROP_POS_MSEC can go backwards, which would otherwise
                # stall the score-screen exit (`ts - falling_ts` never reaches
                # the duration) and silently merge/truncate spans.
                if ts < last_ts:
                    ts = last_ts
                last_ts = ts
                yield idx, ts, frame
        finally:
            cap.release()

    return stride, _gen()


# ---------------------------------------------------------------------------
# Classifiers — reuse Tool 9 zone-fire (no hue-wrap reinvention)
# ---------------------------------------------------------------------------


def _group_fire_ratio(zones: list[ZoneSpec], frame_at_ref: np.ndarray) -> float:
    """``fires / n_zones`` for a zone group on a reference-resized frame —
    exactly Tool 9's per-group game-state scoring shape."""
    n = len(zones)
    if n == 0:
        return 0.0
    fires = sum(1 for z in zones if zone_fires_on_frame(z, frame_at_ref)[0])
    return fires / float(n)


def _classify_in_match(
    frame_at_ref: np.ndarray, in_match_zones: list[ZoneSpec]
) -> bool:
    """Binary ``in_match`` for one frame. Reuses ``_argmax_with_threshold``
    with a single ``in_match`` pseudo-class over the group fire-ratio (Tool 9's
    empty-zone short-circuit: no zones → score 0 → ``unknown`` → ``False``)."""
    if not in_match_zones:
        return False
    score = _group_fire_ratio(in_match_zones, frame_at_ref)
    predicted, _ = _argmax_with_threshold(
        {"in_match": score},
        threshold=_IN_MATCH_THRESHOLD,
        ordered_classes=["in_match"],
        zone_counts={"in_match": len(in_match_zones)},
    )
    return predicted == "in_match"


def _classify_hud_version(
    sample_frames_at_ref: list[np.ndarray],
    hud_zones: list[ZoneSpec],
    config_hud: str,
) -> str:
    """Once-per-session HUD-version sanity check over the first N kept frames.
    Returns the config's ``hud_version`` if the ``hud_version_detection`` group
    clears the gate on average, else ``"unknown"``. Empty zones → ``unknown``
    (caller treats that as "skip the check", per AC8)."""
    if not hud_zones or not sample_frames_at_ref:
        return "unknown"
    ratios = [_group_fire_ratio(hud_zones, f) for f in sample_frames_at_ref]
    mean_ratio = sum(ratios) / float(len(ratios))
    predicted, _ = _argmax_with_threshold(
        {config_hud: mean_ratio},
        threshold=_HUD_THRESHOLD,
        ordered_classes=[config_hud],
        zone_counts={config_hud: len(hud_zones)},
    )
    return predicted


def _score_maps(
    frame_at_ref: np.ndarray, map_zones: dict[str, list[_MapZone]]
) -> dict[str, float]:
    """Weighted per-map score for one frame (AC7 formula). Unpopulated maps are
    skipped (no key emitted). Divide-by-zero (all effective weights 0) → 0.0."""
    scores: dict[str, float] = {}
    for slug, mzones in map_zones.items():
        if not mzones:
            continue
        total_w = 0.0
        contrib = 0.0
        for mz in mzones:
            eff = mz.weight if mz.weight_override is None else mz.weight_override
            total_w += eff
            fired, ratio = zone_fires_on_frame(mz.spec, frame_at_ref)
            if fired:
                contrib += ratio * eff
        scores[slug] = (contrib / total_w) if total_w > 0 else 0.0
    return scores


def _ordered_map_slugs(map_zones: dict[str, list[_MapZone]]) -> list[str]:
    """Populated map slugs in ``MAP_LABELS`` order, with any non-MAP_LABELS
    slugs appended in config insertion order (AC7 ``ordered_classes``)."""
    populated = [s for s, zs in map_zones.items() if zs]
    in_labels = [s for s in MAP_LABELS if s in populated]
    extras = [s for s in populated if s not in MAP_LABELS]
    return in_labels + extras


# ---------------------------------------------------------------------------
# Timing-derived state machine (pure)
# ---------------------------------------------------------------------------


def _run_state_machine(
    frames: list[tuple[int, int, bool]],
    score_screen_duration_ms: int,
) -> tuple[list[str], list[tuple[int, int]]]:
    """Pure state machine over ordered ``[(frame_idx, timestamp_ms, in_match)]``.

    Returns ``(states, spans)`` where ``states[i] ∈ {in_match, score_screen,
    not_in_match}`` aligned to ``frames`` and ``spans`` is the list of
    ``(start_frame_idx, end_frame_idx)`` for each maximal ``in_match`` run.

    Rules (AC7 truth table):

    * ``not_in_match``/``score_screen`` → an ``in_match`` frame ⇒ ``in_match``
      (rising edge; a rising edge during ``score_screen`` aborts the score
      window and opens a fresh span).
    * ``in_match`` true→false ⇒ falling edge: record ``falling_ts``; the window
      is evaluated **inclusively on the falling-edge frame** so
      ``score_screen_duration_ms == 0`` yields zero score frames (that frame is
      already ``not_in_match``); a positive duration makes the falling-edge
      frame the first ``score_screen`` frame.
    * in ``score_screen``, once ``ts - falling_ts >= score_screen_duration_ms``
      ⇒ ``not_in_match``.

    Documented edge cases (all unit-tested): video starts mid-match (first kept
    frame already ``in_match`` ⇒ span opens at that frame); ``in_match`` still
    true at EOF (span ends at the last kept frame, no trailing ``score_screen``);
    ``score_screen_duration_ms == 0``; rising edge during ``score_screen``;
    isolated single-frame ``in_match`` blip (valid 1-frame span — no debounce is
    specified and none is invented).
    """
    states: list[str] = []
    state = "not_in_match"
    falling_ts = 0
    dur = int(score_screen_duration_ms)

    for _idx, ts, im in frames:
        if state == "in_match":
            if im:
                state = "in_match"
            else:
                # Falling edge — evaluate the score window inclusively on this
                # frame so a 0-duration window emits zero score frames.
                falling_ts = ts
                state = "not_in_match" if (ts - falling_ts) >= dur else "score_screen"
        elif state == "score_screen":
            if im:
                state = "in_match"           # rising edge aborts the score window
            elif (ts - falling_ts) >= dur:
                state = "not_in_match"
            else:
                state = "score_screen"
        else:  # not_in_match
            state = "in_match" if im else "not_in_match"
        states.append(state)

    # Spans = maximal runs whose state is "in_match" (post-hoc run detection
    # naturally handles mid-match start, EOF-open span, and rising-edge-during-
    # score splitting the runs).
    spans: list[tuple[int, int]] = []
    run_start: int | None = None
    for (idx, _ts, _im), st in zip(frames, states):
        if st == "in_match":
            if run_start is None:
                run_start = idx
            last_idx = idx
        else:
            if run_start is not None:
                spans.append((run_start, last_idx))
                run_start = None
    if run_start is not None:
        spans.append((run_start, last_idx))
    return states, spans


def _aggregate_span_map(
    span_records: list[_FrameRecord],
    ordered_slugs: list[str],
) -> tuple[str, float]:
    """Canonical map-ID for an ``in_match`` span: the most-frequently-argmaxed
    map across the span (ties → higher mean per-frame score; a residual tie on
    both count *and* mean is broken by canonical ``ordered_slugs`` position so
    the result is stable across configs that list maps in a different order —
    REL-005/AC9 determinism). ``confidence`` = mean of that map's per-frame
    scores over the span. Every frame ``unknown`` ⇒ ``("unknown", 0.0)``."""
    counts = Counter(
        r.map_argmax for r in span_records if r.map_argmax != "unknown"
    )
    if not counts:
        return "unknown", 0.0
    max_count = max(counts.values())
    tied = [m for m, c in counts.items() if c == max_count]

    def _mean_score(slug: str) -> float:
        vals = [r.map_scores.get(slug, 0.0) for r in span_records]
        return sum(vals) / float(len(vals)) if vals else 0.0

    def _order_key(slug: str) -> int:
        # Canonical position; any slug not in ordered_slugs sorts last but
        # still deterministically (by slug name) so the tie-break is total.
        return ordered_slugs.index(slug) if slug in ordered_slugs else len(ordered_slugs)

    winner = (
        tied[0]
        if len(tied) == 1
        else max(tied, key=lambda s: (_mean_score(s), -_order_key(s), s))
    )
    return winner, round(_mean_score(winner), 6)


# ---------------------------------------------------------------------------
# results.json
# ---------------------------------------------------------------------------


def _build_results(
    *,
    hud_version: str,
    video: str,
    stride: int,
    config: str,
    records: list[_FrameRecord],
    states: list[str],
    spans: list[Span],
) -> dict:
    """Assemble the AC9 ``results.json`` dict (fixed key order, rounded floats)."""
    return {
        "hud_version": hud_version,
        "video": os.path.basename(video),
        "stride": int(stride),
        "config": os.path.basename(config),
        "frames": [
            {
                "frame_idx": r.frame_idx,
                "timestamp_ms": r.timestamp_ms,
                "state": st,
            }
            for r, st in zip(records, states)
        ],
        "matches": [
            {
                "start_frame": s.start_frame,
                "end_frame": s.end_frame,
                "map_id": s.map_id,
                "confidence": round(float(s.confidence), 6),
            }
            for s in spans
        ],
    }


def _write_results(results: dict, out_path: str) -> None:
    """Deterministic write: fixed key order (``sort_keys=False``), UTF-8,
    ``ensure_ascii=False``, trailing newline (REL-005)."""
    text = json.dumps(results, indent=2, sort_keys=False, ensure_ascii=False) + "\n"
    Path(out_path).write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="video_test.py",
        description=(
            "Tool 11 - Video Detection Tester: run an emitted "
            "map_config.<hud_version>.json against a real video and emit a "
            "deterministic results.json (HUD-version sanity -> per-frame "
            "in_match -> timing-derived state machine -> per-span weighted map-ID)."
        ),
    )
    parser.add_argument("video", help="Path to the input video (required).")
    parser.add_argument(
        "--config",
        default=None,
        help="Path to map_config.<hud_version>.json. Default: newest "
        "apps/tooling/output/map_configs/map_config.v*.json.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Path to write results.json. Default: "
        "apps/tooling/output/video_tests/v<hud>/<timestamp>/results.json.",
    )
    parser.add_argument(
        "--stride",
        type=int,
        default=None,
        help="Keep every Nth decoded frame. Default: ~1 frame/sec (round(fps)).",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Per-map identification gate. Default: the config's "
        "minimap_identification.identification_threshold.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Thin CLI entry. Returns 0 on success, 1 on any clean error (no
    Python traceback escapes to the user)."""
    args = _parse_args(argv)

    if not os.path.isfile(args.video):
        print(f"Error: video not found: {args.video}", file=sys.stderr)
        return 1

    if args.stride is not None and args.stride < 1:
        print("Error: --stride must be a positive integer", file=sys.stderr)
        return 1

    if args.threshold is not None and not (0.0 <= args.threshold <= 1.0):
        print(
            f"Error: --threshold must be in [0.0, 1.0] (got {args.threshold}) - "
            "it gates a fire-ratio score, so values outside the range make "
            "every / no map predict.",
            file=sys.stderr,
        )
        return 1

    config_path = args.config
    if config_path is None:
        config_path = _default_config_path()
        if config_path is None:
            print(
                "Error: no --config given and no map_config.v*.json under "
                f"{os.path.join(_tooling_root(), 'output', 'map_configs')} - "
                "run the map config emitter first.",
                file=sys.stderr,
            )
            return 1
    if not os.path.isfile(config_path):
        print(f"Error: config not found: {config_path}", file=sys.stderr)
        return 1

    try:
        config = _load_config(config_path)
    except (OSError, ValueError, TypeError, AttributeError, json.JSONDecodeError) as exc:
        # TypeError/AttributeError cover a hand-corrupted config whose required
        # keys are *present* but null/wrong-typed (int(None), float(None),
        # null.items()) — _load_config validates key presence, not value type,
        # so these must still surface as a clean CLI error (AC2/AC3: no
        # Python traceback escapes; Dev Notes: fail clean on a corrupted file).
        print(f"Error: cannot load config '{config_path}': {exc}", file=sys.stderr)
        return 1

    resolved_threshold = (
        float(args.threshold)
        if args.threshold is not None
        else config.identification_threshold
    )

    # AC8: surface every degradation note once, on stderr.
    for note in config.notes:
        print(f"  NOTE: {note}", file=sys.stderr)

    try:
        stride, frame_iter = _frame_source(args.video, args.stride)
    except (VideoOpenError, cv2.error) as exc:
        # cv2.error: the VideoCapture *constructor* itself can raise on a
        # backend init failure (rare) rather than returning an unopened
        # handle — keep it a clean CLI error, no traceback.
        print(f"Error: cannot open video '{args.video}': {exc}", file=sys.stderr)
        return 1

    ref_height = int(config.reference_resolution["height"])
    ordered_slugs = _ordered_map_slugs(config.map_zones)
    map_zone_counts = {
        s: len(config.map_zones[s]) for s in ordered_slugs
    }

    records: list[_FrameRecord] = []
    hud_sample: list[np.ndarray] = []
    try:
        for frame_idx, ts_ms, frame_bgr in frame_iter:
            frame_at_ref = _resize_to_ref(frame_bgr, ref_height)
            if len(hud_sample) < _HUD_SAMPLE_FRAMES:
                hud_sample.append(frame_at_ref)
            in_match = _classify_in_match(frame_at_ref, config.in_match_zones)
            if in_match and ordered_slugs:
                map_scores = _score_maps(frame_at_ref, config.map_zones)
                map_argmax, _ = _argmax_with_threshold(
                    map_scores,
                    threshold=resolved_threshold,
                    ordered_classes=ordered_slugs,
                    zone_counts=map_zone_counts,
                )
            else:
                map_scores = {}
                map_argmax = "unknown"
            records.append(
                _FrameRecord(
                    frame_idx=frame_idx,
                    timestamp_ms=ts_ms,
                    in_match=in_match,
                    map_argmax=map_argmax,
                    map_scores=map_scores,
                )
            )
    except cv2.error as exc:  # pragma: no cover - defensive (real-video only)
        print(f"Error: video decode failed: {exc}", file=sys.stderr)
        return 1

    if not records:
        print(
            f"Error: no frames decoded from {args.video} (empty/corrupt video?)",
            file=sys.stderr,
        )
        return 1

    # Once-per-session HUD-version sanity check.
    derived_hud = _classify_hud_version(
        hud_sample, config.hud_zones, config.hud_version
    )
    if config.hud_zones and derived_hud != config.hud_version:
        # Single-config CLI: _classify_hud_version can only return
        # config.hud_version (the sample cleared the gate) or "unknown" (the
        # configured HUD's own hud_version_detection zones did NOT fire on the
        # sampled frames). It can never name a *different* HUD — there is no
        # other config to score against (multi-config selection is Story
        # 1.13's scope). So this is a "did the configured HUD's zones fire?"
        # signal, NOT a cross-HUD disagreement. Word it that way.
        print(
            f"  WARN: config hud_version={config.hud_version}, but its "
            f"hud_version_detection zones did not fire on the sampled frames "
            f"(mean fire-ratio below the {_HUD_THRESHOLD} gate) - zones may be "
            f"unpopulated/mis-tuned or the footage may not match this HUD. "
            f"Proceeding with the config value.",
            file=sys.stderr,
        )

    sm_input = [(r.frame_idx, r.timestamp_ms, r.in_match) for r in records]
    states, raw_spans = _run_state_machine(
        sm_input, config.score_screen_duration_ms
    )

    # Index records by frame_idx for per-span aggregation.
    by_idx = {r.frame_idx: r for r in records}
    spans: list[Span] = []
    for start_idx, end_idx in raw_spans:
        span_records = [
            by_idx[r.frame_idx]
            for r in records
            if start_idx <= r.frame_idx <= end_idx
        ]
        map_id, confidence = _aggregate_span_map(span_records, ordered_slugs)
        spans.append(
            Span(
                start_frame=start_idx,
                end_frame=end_idx,
                map_id=map_id,
                confidence=confidence,
            )
        )

    results = _build_results(
        hud_version=config.hud_version,
        video=args.video,
        stride=stride,
        config=config_path,
        records=records,
        states=states,
        spans=spans,
    )

    # Resolve output path.
    if args.output is not None:
        out_path = args.output
    else:
        # Microsecond precision so two runs in the same wall-clock second do
        # not collide and silently overwrite the prior results.json (the
        # timestamped dir is the only non-deterministic part, excluded from
        # the REL-005 byte-identical claim — but it must still be unique).
        timestamp = datetime.datetime.now().astimezone().strftime(
            "%Y-%m-%dT%H%M%S.%f"
        )
        # Strip a single leading "v" *prefix* (not a char set — str.lstrip("v")
        # would turn "vv2" -> "2" -> "v2" and collide distinct HUD versions).
        _hv = config.hud_version
        hud_dir = "v" + (_hv[1:] if _hv.startswith("v") else _hv)
        out_path = os.path.join(
            _tooling_root(),
            "output",
            "video_tests",
            hud_dir,
            timestamp,
            "results.json",
        )
    try:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        _write_results(results, out_path)
    except OSError as exc:
        print(f"Error: cannot write results to '{out_path}': {exc}", file=sys.stderr)
        return 1

    n_in_match = sum(1 for s in states if s == "in_match")
    print(f"Video:    {os.path.abspath(args.video)}")
    print(f"Config:   {os.path.abspath(config_path)} (hud_version={config.hud_version})")
    print(f"Stride:   {stride} (kept {len(records)} frame(s))")
    print(f"States:   {n_in_match} in_match / {len(states)} kept")
    print(f"Matches:  {len(spans)} in_match span(s)")
    for s in spans:
        print(
            f"  frames {s.start_frame}-{s.end_frame}: "
            f"{s.map_id} (confidence {s.confidence:.6f})"
        )
    print(f"Results:  {os.path.abspath(out_path)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
