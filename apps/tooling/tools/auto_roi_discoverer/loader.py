"""Read Tool 7's output and build Tool 8's target classes.

Pure logic — no Tk. Loads ``<input>/overlay_stacks_summary.json`` and, for every
``"ok"`` cell that feeds a target class, its ``stats.npz`` side-car; builds the four
*game-state* classes — ``lobby`` / ``score`` / ``transition`` directly from their own
cells, and ``in_match`` as a frame-count-weighted pool of the ``MAP_LABELS`` cells
(mean-of-means; Chan / parallel variance pooling) — and *also* exposes each loaded
``MAP_LABELS`` cell as its own *per-map* target class (so Tool 8 picks + exports both
the game-state-cascade ROIs and the per-map / map-ID fingerprints). Clean
``LoaderError`` (no traceback) on a missing / old / mixed-resolution input —
``__main__`` prints it and exits before Tk loads.

Also reads ``config/config.yaml`` (READ-ONLY) for the faded legacy-ROI reference
overlay.
"""

import json
import os
import sys
from dataclasses import dataclass, field

import numpy as np

from tools.frame_labeler import MAP_LABELS
from tools.overlay_stack_analyzer import _default_output_dir as _tool7_default_output
from tools.overlay_stack_analyzer import load_stats_npz

from .model import TargetClassStats

# Class names whose cells feed a target class (``in_match`` is the pool of the maps).
_DIRECT_CLASSES = ("lobby", "score", "transition")
_MAP_CLASS_SET = frozenset(MAP_LABELS)
_NEEDED_CLASSES = frozenset(_DIRECT_CLASSES) | _MAP_CLASS_SET

_HUE_CV_TO_RAD = 2.0 * np.pi / 180.0  # one OpenCV H unit → radians


class LoaderError(Exception):
    """A user-facing load failure — printed cleanly to stderr (no traceback)."""


# ---------------------------------------------------------------------------
# Default paths (tracked relative to this file so a checkout move can't break them)
# ---------------------------------------------------------------------------


def _tooling_root() -> str:
    """``apps/tooling`` — ``..`` twice up from this file (``tools/auto_roi_discoverer/``)."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def default_input_dir() -> str:
    """``apps/tooling/output/overlay_stacks`` — exactly Tool 7's default ``--output``
    (imported, not re-derived, so the two always agree regardless of checkout location)."""
    return _tool7_default_output()


def default_export_root() -> str:
    """``apps/tooling/output/auto_rois`` — Tool 8's export root (a sibling of Tool 7's
    ``output/overlay_stacks`` and Tool 6's ``output/labeled``, under the existing
    ``apps/tooling/output/`` gitignore)."""
    return os.path.join(_tooling_root(), "output", "auto_rois")


DEFAULT_EXPORT_ROOT = default_export_root()
DEFAULT_EXCLUSIONS_PATH = os.path.join(DEFAULT_EXPORT_ROOT, "exclusions.yaml")


# ---------------------------------------------------------------------------
# Loaded-stacks bundle
# ---------------------------------------------------------------------------


@dataclass
class LoadedStacks:
    """Everything ``__main__`` hands the GUI after a successful load."""

    input_dir: str
    summary_path: str
    version: str                              # the HUD version the target classes were built for
    ref_height: int | None                    # Tool 7's --ref-height (None = per-cell modal)
    frame_shape: tuple[int, int, int]         # the common (h, w, c) every target class shares
    target_classes: dict                       # name -> TargetClassStats
    summary_cells: list = field(default_factory=list)   # the raw "ok" cells for this version
    generated_at: str | None = None


# ---------------------------------------------------------------------------
# load_overlay_stacks
# ---------------------------------------------------------------------------


def _resolve_stats_path(input_root: str, cell: dict) -> str | None:
    """Where this cell's ``stats.npz`` should live — from ``outputs.stats`` if present,
    else the conventional ``<input>/<version>/<class>/stats.npz``. ``None`` if neither
    path resolves to an existing file. Emits a stderr warning if the summary's
    ``outputs.stats`` path is missing on disk but the conventional path exists (likely
    stale leftover vs current cell — caller should re-run Tool 7 to refresh)."""
    rel = (cell.get("outputs") or {}).get("stats")
    summary_path = os.path.join(input_root, *str(rel).split("/")) if rel else None
    conventional_path = os.path.join(
        input_root, str(cell.get("version", "")),
        str(cell.get("class", "")), "stats.npz",
    )
    if summary_path is not None and os.path.isfile(summary_path):
        return summary_path
    if os.path.isfile(conventional_path):
        if summary_path is not None and summary_path != conventional_path:
            print(
                f"  ⚠ {cell.get('version')}/{cell.get('class')}: summary 'outputs.stats' "
                f"points to {summary_path!r} (missing); falling back to {conventional_path!r}. "
                "Re-run Tool 7 to refresh the summary.",
                file=sys.stderr, flush=True,
            )
        return conventional_path
    return None


def _version_sort_key(version: str) -> tuple:
    """Natural sort key for ``v<major>.<minor>`` style HUD-version dirs (so ``v10.0`` > ``v2.0``).
    Falls back to lexicographic on non-numeric components."""
    parts = str(version).lstrip("v").split(".")
    key = []
    for part in parts:
        try:
            key.append((0, int(part)))   # numeric component
        except ValueError:
            key.append((1, part))        # fallback for non-numeric
    return tuple(key)


def _choose_version(ok_cells: list) -> str:
    """Pick the HUD version to work on — the one with the most ``"ok"`` cells
    (ties broken by the natural-sort-largest name, e.g. ``v10.0`` over ``v2.0``)."""
    counts: dict[str, int] = {}
    for cell in ok_cells:
        counts[str(cell.get("version", ""))] = counts.get(str(cell.get("version", "")), 0) + 1
    return max(counts.items(), key=lambda kv: (kv[1], _version_sort_key(kv[0])))[0]


def _pool_in_match(loaded_cells: list, frame_shape, version: str) -> TargetClassStats | None:
    """Pool the loaded ``MAP_LABELS`` cells into the derived ``in_match`` class.

    Two streaming passes over the per-cell stat arrays (never all cells stacked at
    once — peak RAM stays ~a handful of ``(h, w, 3)`` float64 accumulators):

    * BGR + HSV S/V channels — frame-count-weighted mean-of-means then Chan/parallel
      variance pooling: ``pooled_var = Σ nᵢ·(stdᵢ² + (meanᵢ − pooled_mean)²) / Σ nᵢ``.
    * HSV Hue channel — frame-count-weighted *circular* mean of the per-cell circular
      means; the pooled Hue std is the between-cell circular spread of those means.
      This is a documented V1 approximation (per AC3 it uses only ``mean_hsv[..., 0]``;
      recombining the per-cell *within*-cell circular spreads exactly would need each
      cell's R / sin-cos sums, which the ``stats.npz`` schema does not carry).
    """
    map_cells = [c for c in loaded_cells if c["class"] in _MAP_CLASS_SET]
    # Skip zero-frame cells entirely — they have no statistical content to pool and would
    # silently inflate weights if assigned a synthetic n=1 (Chan variance pooling assumes
    # nᵢ is the true sample size, not a placeholder).
    map_cells = [c for c in map_cells if int(c["stats"].get("frame_count", 0)) > 0]
    if not map_cells:
        return None
    ns = [float(c["stats"]["frame_count"]) for c in map_cells]
    total_n = float(sum(ns))
    if total_n <= 0:
        return None
    h, w_, c_ = (int(d) for d in frame_shape)

    # --- Pass 1: weighted mean-of-means (BGR + HSV) and weighted circular Hue mean. ---
    sum_bgr = np.zeros((h, w_, c_), dtype=np.float64)
    sum_hsv_sv = np.zeros((h, w_, 2), dtype=np.float64)
    sum_sin = np.zeros((h, w_), dtype=np.float64)
    sum_cos = np.zeros((h, w_), dtype=np.float64)
    for cell, n in zip(map_cells, ns):
        st = cell["stats"]
        sum_bgr += np.asarray(st["mean_bgr"], dtype=np.float64) * n
        mean_hsv_i = np.asarray(st["mean_hsv"], dtype=np.float64)
        sum_hsv_sv += mean_hsv_i[..., 1:] * n
        theta = mean_hsv_i[..., 0] * _HUE_CV_TO_RAD
        sum_sin += np.sin(theta) * n
        sum_cos += np.cos(theta) * n
    pooled_mean_bgr = sum_bgr / total_n
    pooled_mean_sv = sum_hsv_sv / total_n
    mean_sin = sum_sin / total_n
    mean_cos = sum_cos / total_n
    R = np.sqrt(mean_sin ** 2 + mean_cos ** 2)
    pooled_h_mean = (np.degrees(np.arctan2(mean_sin, mean_cos)) % 360.0) / 2.0 % 180.0
    inner = np.maximum(-2.0 * np.log(np.clip(R, 1e-9, 1.0)), 0.0)
    pooled_h_std = np.clip(np.degrees(np.sqrt(inner)) / 2.0, 0.0, 90.0)

    # --- Pass 2: Chan/parallel variance pooling (BGR + HSV S/V). ---
    var_bgr = np.zeros((h, w_, c_), dtype=np.float64)
    var_sv = np.zeros((h, w_, 2), dtype=np.float64)
    for cell, n in zip(map_cells, ns):
        st = cell["stats"]
        m_bgr = np.asarray(st["mean_bgr"], dtype=np.float64)
        s_bgr = np.asarray(st["std_bgr"], dtype=np.float64)
        var_bgr += n * (s_bgr ** 2 + (m_bgr - pooled_mean_bgr) ** 2)
        m_hsv = np.asarray(st["mean_hsv"], dtype=np.float64)[..., 1:]
        s_hsv = np.asarray(st["std_hsv"], dtype=np.float64)[..., 1:]
        var_sv += n * (s_hsv ** 2 + (m_hsv - pooled_mean_sv) ** 2)
    pooled_std_bgr = np.sqrt(np.maximum(var_bgr / total_n, 0.0))
    pooled_std_sv = np.sqrt(np.maximum(var_sv / total_n, 0.0))

    pooled_mean_hsv = np.empty((h, w_, 3), dtype=np.float64)
    pooled_mean_hsv[..., 0] = pooled_h_mean
    pooled_mean_hsv[..., 1:] = pooled_mean_sv
    pooled_std_hsv = np.empty((h, w_, 3), dtype=np.float64)
    pooled_std_hsv[..., 0] = pooled_h_std
    pooled_std_hsv[..., 1:] = pooled_std_sv

    return TargetClassStats(
        name="in_match",
        mean_bgr=pooled_mean_bgr.astype(np.float32),
        std_bgr=pooled_std_bgr.astype(np.float32),
        mean_hsv=pooled_mean_hsv.astype(np.float32),
        std_hsv=pooled_std_hsv.astype(np.float32),
        frame_count=int(round(total_n)),
        frame_shape=tuple(int(d) for d in frame_shape),
        source_cells=tuple(f"{version}/{c['class']}" for c in map_cells),
        stability_score=None,
        is_pooled=True,
    )


def load_overlay_stacks(input_root: str) -> LoadedStacks:
    """Build the four target classes from Tool 7's output rooted at ``input_root``.

    Raises :class:`LoaderError` (caught by ``__main__`` → clean stderr, exit 1 before
    Tk loads) on: a missing/empty/unparseable ``overlay_stacks_summary.json``; an
    ``"ok"`` cell missing its ``stats.npz`` (output predates Tool 7's amendment); or
    target-class cells that disagree on ``frame_shape`` (re-run Tool 7 with ``--ref-height``).
    """
    summary_path = os.path.join(input_root, "overlay_stacks_summary.json")
    if not os.path.isfile(summary_path):
        raise LoaderError(
            f"No overlay_stacks_summary.json under {input_root!r}. "
            "Run Tool 7 (overlay_stack_analyzer) first."
        )
    try:
        with open(summary_path, "r", encoding="utf-8") as handle:
            summary = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise LoaderError(f"Could not read {summary_path!r}: {exc}. Re-run Tool 7.") from None

    cells = summary.get("cells") or []
    ok_cells = [c for c in cells if c.get("status") == "ok"]
    if not ok_cells:
        raise LoaderError(
            f"{summary_path!r} has no \"ok\" cells. Run Tool 7 (overlay_stack_analyzer) "
            "against a labeled dataset first."
        )

    version = _choose_version(ok_cells)
    versions_present = sorted({str(c.get("version", "")) for c in ok_cells})
    if len(versions_present) > 1:
        print(
            f"  ⚠ multiple HUD versions in Tool 7's output ({', '.join(versions_present)}); "
            f"using {version!r} (most cells). Re-run Tool 8 with a filtered --input to pick another.",
            file=sys.stderr, flush=True,
        )
    version_cells = [c for c in ok_cells if str(c.get("version", "")) == version]

    # Load stats.npz for every cell of this version whose class feeds a target class.
    loaded = []  # [{"class": str, "summary": cell, "stats": dict}, ...]
    shapes_seen: dict[tuple, list[str]] = {}
    for cell in version_cells:
        cls = str(cell.get("class", ""))
        if cls not in _NEEDED_CLASSES:
            continue
        stats_path = _resolve_stats_path(input_root, cell)
        if stats_path is None:
            raise LoaderError(
                f"Cell {version}/{cls} has no stats.npz side-car — your Tool 7 output "
                "predates the stats.npz amendment. Re-run Tool 7 (overlay_stack_analyzer) "
                "to regenerate the side-cars."
            )
        try:
            stats = load_stats_npz(stats_path)
        except (OSError, ValueError, KeyError) as exc:
            raise LoaderError(f"Could not read {stats_path!r}: {exc}. Re-run Tool 7.") from None
        shape = tuple(int(d) for d in stats["frame_shape"])
        shapes_seen.setdefault(shape, []).append(f"{version}/{cls}")
        loaded.append({"class": cls, "summary": cell, "stats": stats})

    if not loaded:
        raise LoaderError(
            f"No lobby / score / transition / map cells for version {version!r} in {summary_path!r}. "
            "Run Tool 7 against a properly-labeled dataset first."
        )
    if len(shapes_seen) > 1:
        detail = "; ".join(
            f"{shape}: {', '.join(sorted(names))}" for shape, names in sorted(shapes_seen.items())
        )
        raise LoaderError(
            "Target-class cells disagree on frame_shape (" + detail + "). "
            "Re-run Tool 7 (overlay_stack_analyzer) with --ref-height (e.g. --ref-height 1080) "
            "so every cell is normalized to one resolution."
        )
    frame_shape = next(iter(shapes_seen))

    by_class = {entry["class"]: entry for entry in loaded}

    def _direct_target(cls: str, entry: dict) -> TargetClassStats:
        st = entry["stats"]
        return TargetClassStats(
            name=cls,
            mean_bgr=np.asarray(st["mean_bgr"], dtype=np.float32),
            std_bgr=np.asarray(st["std_bgr"], dtype=np.float32),
            mean_hsv=np.asarray(st["mean_hsv"], dtype=np.float32),
            std_hsv=np.asarray(st["std_hsv"], dtype=np.float32),
            frame_count=int(st["frame_count"]),
            frame_shape=frame_shape,
            source_cells=(f"{version}/{cls}",),
            stability_score=entry["summary"].get("stability_score"),
            is_pooled=False,
        )

    # Build the game-state classes first (in any order — assembled in TARGET_CLASSES
    # order below), then assemble: the four game-state classes (TARGET_CLASSES order),
    # then each present per-map cell (MAP_LABELS order — exposed individually so the user
    # can pick + export per-map / map-ID zones too; same cells the in_match pool uses).
    game_state: dict[str, TargetClassStats] = {}
    for cls in _DIRECT_CLASSES:
        entry = by_class.get(cls)
        if entry is None:
            print(f"  ⚠ no {version}/{cls} cell — target class {cls!r} will be missing.",
                  file=sys.stderr, flush=True)
            continue
        game_state[cls] = _direct_target(cls, entry)
    pooled = _pool_in_match(loaded, frame_shape, version)
    if pooled is not None:
        game_state["in_match"] = pooled
    else:
        print(f"  ⚠ no map cells for version {version!r} — derived class 'in_match' will be missing.",
              file=sys.stderr, flush=True)

    target_classes: dict[str, TargetClassStats] = {}
    for cls in ("lobby", "in_match", "score", "transition"):
        if cls in game_state:
            target_classes[cls] = game_state[cls]
    for ml in MAP_LABELS:
        entry = by_class.get(ml)
        if entry is not None:
            target_classes[ml] = _direct_target(ml, entry)

    if not target_classes:
        raise LoaderError(
            f"No target classes could be built for version {version!r}. "
            "Tool 7's output has no lobby / score / transition / map cells."
        )

    return LoadedStacks(
        input_dir=os.path.abspath(input_root),
        summary_path=summary_path,
        version=version,
        ref_height=summary.get("ref_height"),
        frame_shape=frame_shape,
        target_classes=target_classes,
        summary_cells=[entry["summary"] for entry in loaded],
        generated_at=summary.get("generated_at"),
    )


# ---------------------------------------------------------------------------
# Legacy-ROI reference overlay (READ-ONLY config/config.yaml)
# ---------------------------------------------------------------------------


def load_legacy_rois(config_path: str | None) -> dict | None:
    """Read ``config/config.yaml`` (READ-ONLY) and return a flat list of labelled
    reference rectangles in *reference-resolution full-frame* coords, or ``None`` if
    the file is missing / unparseable / has nothing useful (a warning is printed; the
    tool works fine without it).

    Returns ``{"reference_resolution": {"width": W, "height": H}, "rects": [
        {"label": str, "x": int, "y": int, "width": int, "height": int}, ...]}``.
    ``black_detection.roi_zones`` are taken verbatim; ``minimap_identification`` zones
    are offset by their config's ``roi`` so they land in full-frame space too.
    """
    if not config_path or not os.path.isfile(config_path):
        print(f"  ⚠ legacy-ROI overlay disabled: config not found at {config_path!r}.",
              file=sys.stderr, flush=True)
        return None
    try:
        import yaml  # local import — only the reference overlay needs it
        with open(config_path, "r", encoding="utf-8") as handle:
            cfg = yaml.safe_load(handle) or {}
    except Exception as exc:  # noqa: BLE001 — any parse trouble degrades to "no overlay"
        print(f"  ⚠ legacy-ROI overlay disabled: could not parse {config_path!r}: {exc}.",
              file=sys.stderr, flush=True)
        return None

    rects: list[dict] = []
    ref = cfg.get("reference_resolution") or {}
    ref_res = {"width": int(ref.get("width", 1920) or 1920),
               "height": int(ref.get("height", 1080) or 1080)}

    def _rect_from(d, label):
        try:
            return {"label": str(label), "x": int(d["x"]), "y": int(d["y"]),
                    "width": int(d["width"]), "height": int(d["height"])}
        except (KeyError, TypeError, ValueError):
            return None

    for zone in (cfg.get("black_detection") or {}).get("roi_zones") or []:
        r = _rect_from(zone, f"bd:{zone.get('name', '?')}")
        if r:
            rects.append(r)
    for entry in (cfg.get("minimap_identification") or {}).get("configs") or []:
        roi = entry.get("roi") or {}
        ox, oy = int(roi.get("x", 0) or 0), int(roi.get("y", 0) or 0)
        cfg_id = entry.get("id", "?")
        for map_label, map_data in (entry.get("maps") or {}).items():
            for zd in (map_data or {}).get("zones", []) or []:
                r = _rect_from(zd, f"mm:{cfg_id}:{map_label}:{zd.get('id', '?')}")
                if r:
                    r["x"] += ox
                    r["y"] += oy
                    rects.append(r)

    if not rects:
        print(f"  ⚠ legacy-ROI overlay: no black_detection/minimap ROIs found in {config_path!r}.",
              file=sys.stderr, flush=True)
        return None
    return {"reference_resolution": ref_res, "rects": rects}
