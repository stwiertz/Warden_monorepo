"""Overlay Stack Analyzer — Tool 7: stack labeled frames into mean/stddev images.

Walks the HUD-version-partitioned PNG dataset Tool 6 produces
(``labeled/v<ver>/<class>/*.png``) and, for every ``(version, class)`` cell,
streams a per-pixel mean (``mean.png`` — the "average screen") and population
stddev (``stddev.png`` — the "what moves" map; dark = stable HUD chrome) into a
mirrored output tree, plus an optional false-colour HSV-variance heatmap. A
stability-ranked ``overlay_stacks_summary.json`` lists every cell. Headless batch
tool — no GUI. Memory-bounded via Welford's online algorithm (frames are never
all stacked in one array).

Usage:
    python tools/overlay_stack_analyzer.py [--input INPUT_DIR] [--output OUTPUT_DIR]
        [--min-frames N] [--ref-height H] [--heatmap]
"""

import argparse
import datetime
import glob
import json
import os
import sys
from collections import Counter
from pathlib import Path

# Use absolute path to avoid shadowing stdlib modules. This tool has no required
# ``utils.*`` import (it is pure cv2 + numpy + stdlib), but the insert is kept
# for consistency with the other tools and in case future polish wants ``utils``.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cv2  # noqa: E402
import numpy as np  # noqa: E402


# ---------------------------------------------------------------------------
# Default directories (path math intentionally identical to Tool 6's)
# ---------------------------------------------------------------------------


def _default_input_dir() -> str:
    """``<repo_root>/output/labeled`` — intentionally identical to
    ``video_timeline_labeler._default_output_dir()`` so Tool 7's default input
    always equals Tool 6's default output regardless of checkout location."""
    return os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")),
        "output",
        "labeled",
    )


def _default_output_dir() -> str:
    """``<repo_root>/output/overlay_stacks`` — same ``__file__``-relative math."""
    return os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")),
        "output",
        "overlay_stacks",
    )


# ---------------------------------------------------------------------------
# Pure helpers — testable with no image I/O
# ---------------------------------------------------------------------------


def _discover_cells(input_root: str) -> list[tuple[str, str, list[str]]]:
    """Return ``[(version_dir, class_dir, sorted_png_paths), ...]`` sorted by
    ``(version_dir, class_dir)``.

    Top-level directories not matching ``v*`` are skipped; non-``.png`` files are
    ignored; cells with no PNGs are dropped. A missing/empty ``input_root`` → ``[]``.
    The literal directory names are kept (the ``v`` prefix stays — ``v1.0``,
    ``v2.0``, ``vcustom``).
    """
    if not os.path.isdir(input_root):
        return []
    try:
        version_dirs = sorted(os.listdir(input_root))
    except OSError:
        return []  # unreadable root → treat as "no cells" (main reports it cleanly)
    cells: list[tuple[str, str, list[str]]] = []
    for version_dir in version_dirs:
        version_path = os.path.join(input_root, version_dir)
        if not version_dir.startswith("v") or not os.path.isdir(version_path):
            continue
        try:
            class_dirs = sorted(os.listdir(version_path))
        except OSError:
            continue  # skip an unreadable version dir rather than crashing the run
        for class_dir in class_dirs:
            class_path = os.path.join(version_path, class_dir)
            if not os.path.isdir(class_path):
                continue
            pngs = sorted(glob.glob(os.path.join(class_path, "*.png")))
            if not pngs:
                continue
            cells.append((version_dir, class_dir, pngs))
    return sorted(cells, key=lambda cell: (cell[0], cell[1]))


def _modal_shape(shapes: list[tuple[int, int, int]]) -> tuple[int, int, int]:
    """Most-common shape across ``shapes``; ties broken by largest ``h*w``, then
    lexicographically (larger tuple wins). Empty list → ``ValueError``."""
    if not shapes:
        raise ValueError("no shapes")
    counter = Counter(tuple(int(d) for d in s) for s in shapes)
    best, _ = max(
        counter.items(),
        key=lambda kv: (kv[1], kv[0][0] * kv[0][1], kv[0]),
    )
    return best


def _target_shape(
    modal: tuple[int, int, int], ref_height: int | None
) -> tuple[int, int, int]:
    """``modal`` when ``ref_height is None``; otherwise
    ``(ref_height, round(ref_height * w / h), c)`` keeping the modal aspect ratio.
    The derived width is clamped to ``>= 1`` so a very-portrait modal shape can't
    collapse it to 0 (which would make ``cv2.resize`` raise)."""
    if ref_height is None:
        return tuple(int(d) for d in modal)
    h, w, c = modal
    return (int(ref_height), max(1, int(round(ref_height * w / h))), int(c))


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


def _normalize_uint8(arr: np.ndarray) -> np.ndarray:
    """Min-max normalize a (float or int) array to ``0..255`` ``uint8``. A
    constant array → all-zero (no division by zero)."""
    arr = np.asarray(arr, dtype=np.float64)
    lo = float(arr.min())
    hi = float(arr.max())
    if hi <= lo:
        return np.zeros(arr.shape, dtype=np.uint8)
    return np.round((arr - lo) / (hi - lo) * 255.0).astype(np.uint8)


def _stability_score(stddev_bgr: np.ndarray) -> float:
    """Mean of the BGR stddev map over all pixels and channels — lower = more
    stable (HUD chrome); higher = more volatile (gameplay)."""
    return float(np.asarray(stddev_bgr).mean())


def _cell_output_paths(
    output_root: str, version_dir: str, class_dir: str, heatmap: bool
) -> dict[str, str]:
    """``{"mean": ..., "stddev": ...[, "heatmap": ...]}`` absolute paths for a cell."""
    cell_dir = os.path.join(output_root, version_dir, class_dir)
    paths = {
        "mean": os.path.join(cell_dir, "mean.png"),
        "stddev": os.path.join(cell_dir, "stddev.png"),
    }
    if heatmap:
        paths["heatmap"] = os.path.join(cell_dir, "variance_heatmap.png")
    return paths


# ---------------------------------------------------------------------------
# Windows non-ASCII-path-safe PNG I/O (mirrors Tool 6's read/write fix)
# ---------------------------------------------------------------------------


def _read_bgr(path: str) -> np.ndarray | None:
    """Decode a PNG to a 3-channel BGR array, or ``None`` on any failure.

    Uses ``np.fromfile`` + ``cv2.imdecode`` rather than ``cv2.imread`` because
    ``cv2.imread`` returns ``None`` silently on Windows non-ASCII paths (e.g.
    accented usernames in ``C:\\Users\\…``). ``IMREAD_COLOR`` forces 3 channels
    even if a stray grayscale PNG turns up.
    """
    try:
        data = np.fromfile(path, dtype=np.uint8)
        if data.size == 0:
            return None
        return cv2.imdecode(data, cv2.IMREAD_COLOR)  # None on decode failure
    except (OSError, cv2.error):
        return None


def _write_png(dest: str, arr: np.ndarray) -> None:
    """Encode ``arr`` to PNG bytes and write them to ``dest`` (creating parent
    dirs first). Windows non-ASCII-path-safe — same pattern as Tool 6's writes."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    ok, buf = cv2.imencode(".png", arr)
    if not ok:
        raise RuntimeError(f"cv2.imencode returned False for {dest}")
    Path(dest).write_bytes(buf.tobytes())


# ---------------------------------------------------------------------------
# Per-cell streaming processor
# ---------------------------------------------------------------------------


def _skipped_entry(
    version_dir: str,
    class_dir: str,
    reason: str,
    *,
    frame_count: int = 0,
    frame_shape: list[int] | None = None,
    resized_count: int = 0,
) -> dict:
    return {
        "version": version_dir,
        "class": class_dir,
        "status": "skipped",
        "reason": reason,
        "frame_count": frame_count,
        "frame_shape": frame_shape,
        "resized_count": resized_count,
        "stability_score": None,
        "outputs": None,
    }


def _rel_outputs(out_paths: dict[str, str], output_root: str) -> dict[str, str]:
    return {
        key: os.path.relpath(path, output_root).replace(os.sep, "/")
        for key, path in out_paths.items()
    }


def _process_cell(
    version_dir: str,
    class_dir: str,
    paths: list[str],
    output_root: str,
    ref_height: int | None,
    want_heatmap: bool,
    min_frames: int,
) -> dict:
    """Stream one ``(version, class)`` cell → ``mean.png`` + ``stddev.png``
    (+ optional ``variance_heatmap.png``); return the summary ``cells[]`` entry.

    Two cheap passes over the path list: pass 1 reads each PNG once and records
    its shape (so the modal shape is known); pass 2 re-reads and folds each frame
    into the Welford accumulators. Re-reading PNGs is the price of bounded memory —
    a long same-class span can be hundreds of 1080p frames, multi-GB if stacked.
    """
    # Pass 1 — collect shapes of readable frames (frames discarded; memory bounded).
    shapes: list[tuple[int, int, int]] = []
    for path in paths:
        frame = _read_bgr(path)
        if frame is None:
            print(f"  ⚠ skip (decode failed): {path}", file=sys.stderr, flush=True)
            continue
        shapes.append(tuple(frame.shape))
    if not shapes:
        return _skipped_entry(version_dir, class_dir, "no_readable_frames")

    target_shape = _target_shape(_modal_shape(shapes), ref_height)
    target_h, target_w = target_shape[0], target_shape[1]

    # Pass 2 — re-read, resize off-shape frames, fold into Welford accumulators.
    bgr_state = _welford_init(target_shape)
    hsv_state = _welford_init(target_shape) if want_heatmap else None
    resized_count = 0
    for path in paths:
        frame = _read_bgr(path)
        if frame is None:
            continue  # already warned during pass 1
        if tuple(frame.shape) != target_shape:
            downscale = frame.shape[0] > target_h or frame.shape[1] > target_w
            interp = cv2.INTER_AREA if downscale else cv2.INTER_LINEAR
            frame = cv2.resize(frame, (target_w, target_h), interpolation=interp)
            resized_count += 1
        bgr_state = _welford_update(bgr_state, frame.astype(np.float64))
        if want_heatmap:
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            hsv_state = _welford_update(hsv_state, hsv.astype(np.float64))

    n = bgr_state[0]
    if n == 0:
        return _skipped_entry(version_dir, class_dir, "no_readable_frames")
    if n < min_frames:
        return _skipped_entry(
            version_dir, class_dir, "too_few_frames",
            frame_count=n, frame_shape=list(target_shape), resized_count=resized_count,
        )

    mean, stddev = _welford_finalize(bgr_state)
    mean_u8 = np.clip(np.round(mean), 0, 255).astype(np.uint8)
    std_u8 = np.clip(stddev, 0, 255).astype(np.uint8)
    out_paths = _cell_output_paths(output_root, version_dir, class_dir, want_heatmap)
    try:
        _write_png(out_paths["mean"], mean_u8)
        _write_png(out_paths["stddev"], std_u8)
        if want_heatmap:
            _, hsv_std = _welford_finalize(hsv_state)
            # Mean of the Saturation + Value stddev maps only — Hue (channel 0) is
            # circular in OpenCV's 0..179 range, so a naive per-pixel stddev there
            # is meaningless (179 vs 0 looks like huge variance for adjacent reds).
            scalar = hsv_std[..., 1:].mean(axis=2)
            heat = cv2.applyColorMap(_normalize_uint8(scalar), cv2.COLORMAP_JET)
            _write_png(out_paths["heatmap"], heat)
    except (OSError, RuntimeError, cv2.error) as exc:
        print(
            f"  ⚠ write failed for {version_dir}/{class_dir}: {exc}",
            file=sys.stderr, flush=True,
        )
        return _skipped_entry(
            version_dir, class_dir, "error",
            frame_count=n, frame_shape=list(target_shape), resized_count=resized_count,
        )

    return {
        "version": version_dir,
        "class": class_dir,
        "status": "ok",
        "reason": None,
        "frame_count": n,
        "frame_shape": [int(target_shape[0]), int(target_shape[1]), int(target_shape[2])],
        "resized_count": resized_count,
        "stability_score": _stability_score(stddev),
        "outputs": _rel_outputs(out_paths, output_root),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Tool 7 — Analyze overlay stacks: per-(version,class) mean/stddev "
        "images from Tool 6's labeled dataset."
    )
    parser.add_argument(
        "--input",
        default=None,
        help="Labeled dataset root (default: <repo_root>/output/labeled — Tool 6's default output).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output root for stacked images (default: <repo_root>/output/overlay_stacks).",
    )
    parser.add_argument(
        "--min-frames",
        type=int,
        default=2,
        dest="min_frames",
        help="Minimum readable frames per cell before outputs are produced (default: 2).",
    )
    parser.add_argument(
        "--ref-height",
        type=int,
        default=None,
        dest="ref_height",
        help="Resize every cell to this pixel height (width keeps the modal aspect ratio). "
        "Default: per-cell modal shape, no resize.",
    )
    parser.add_argument(
        "--heatmap",
        action="store_true",
        help="Also emit a false-colour HSV-variance heatmap per cell (variance_heatmap.png).",
    )
    args = parser.parse_args(argv)
    if args.min_frames < 1:
        parser.error("--min-frames must be a positive integer")
    if args.ref_height is not None and args.ref_height < 1:
        parser.error("--ref-height must be a positive integer")
    return args


def _print_table(results: list[dict]) -> None:
    headers = ("version", "class", "n", "stability", "status")
    rows = []
    for entry in results:
        score = "" if entry["stability_score"] is None else f"{entry['stability_score']:.3f}"
        rows.append(
            (
                str(entry["version"]),
                str(entry["class"]),
                str(entry["frame_count"]),
                score,
                str(entry["status"]),
            )
        )
    widths = [
        max(len(headers[i]), *(len(row[i]) for row in rows)) if rows else len(headers[i])
        for i in range(len(headers))
    ]

    def fmt(cols) -> str:
        return "  ".join(col.ljust(widths[i]) for i, col in enumerate(cols))

    print(fmt(headers), flush=True)
    print(fmt(tuple("-" * w for w in widths)), flush=True)
    for row in rows:
        print(fmt(row), flush=True)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    input_dir = os.path.abspath(args.input) if args.input else _default_input_dir()
    output_dir = os.path.abspath(args.output) if args.output else _default_output_dir()
    min_frames = args.min_frames
    ref_height = args.ref_height
    want_heatmap = args.heatmap

    print(f"Input:      {input_dir}", flush=True)
    print(f"Output:     {output_dir}", flush=True)
    print(f"Heatmap:    {'on' if want_heatmap else 'off'}", flush=True)
    print(f"Ref height: {ref_height if ref_height is not None else 'unset (per-cell modal)'}", flush=True)
    print(f"Min frames: {min_frames}", flush=True)

    cells_in = _discover_cells(input_dir)
    if not cells_in:
        print(
            f"No labeled cells found under {input_dir}. Run Tool 6 first.",
            file=sys.stderr, flush=True,
        )
        return 1

    versions = sorted({version for version, _, _ in cells_in})
    cell_list = ", ".join(f"{version}/{cls}" for version, cls, _ in cells_in)
    print(
        f"Discovered {len(cells_in)} cell(s) across {len(versions)} HUD version(s): {cell_list}",
        flush=True,
    )

    results: list[dict] = []
    for version, cls, paths in cells_in:
        print(f"[{version}/{cls}] {len(paths)} frame(s) — processing...", flush=True)
        try:
            entry = _process_cell(
                version, cls, paths, output_dir, ref_height, want_heatmap, min_frames
            )
        except Exception as exc:  # noqa: BLE001 - one bad cell must not abort the batch
            print(
                f"  ⚠ unexpected error processing {version}/{cls}: {exc}",
                file=sys.stderr, flush=True,
            )
            entry = _skipped_entry(version, cls, "error")
        results.append(entry)

    results.sort(
        key=lambda entry: (
            0 if entry["status"] == "ok" else 1,
            entry["stability_score"] if entry["stability_score"] is not None else float("inf"),
        )
    )

    try:
        os.makedirs(output_dir, exist_ok=True)
    except OSError as exc:
        print(f"⚠ could not create output dir {output_dir}: {exc}", file=sys.stderr, flush=True)
        return 1

    summary = {
        "input_dir": input_dir,
        "output_dir": output_dir,
        "generated_at": datetime.datetime.now().astimezone().isoformat(),
        "heatmap": want_heatmap,
        "ref_height": ref_height,
        "min_frames": min_frames,
        "cells": results,
    }
    summary_path = os.path.join(output_dir, "overlay_stacks_summary.json")
    try:
        with open(summary_path, "w", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=2)
    except OSError as exc:
        print(f"⚠ could not write summary {summary_path}: {exc}", file=sys.stderr, flush=True)
        return 1

    _print_table(results)
    print(f"Summary: {summary_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
