"""Overlay Stack Analyzer — Tool 7: stack labeled frames into mean/stddev images.

Walks the HUD-version-partitioned PNG dataset Tool 6 produces
(``labeled/v<ver>/<class>/*.png``) and, for every ``(version, class)`` cell,
streams a per-pixel mean (``mean.png`` — the "average screen") and population
stddev (``stddev.png`` — the "what moves" map; dark = stable HUD chrome) into a
mirrored output tree, plus an optional false-colour HSV-variance heatmap. A
stability-ranked ``overlay_stacks_summary.json`` lists every cell. Headless batch
tool — no GUI. Memory-bounded via Welford's online algorithm (frames are never
all stacked in one array).

Alongside the eyeball PNGs each ``"ok"`` cell also gets a machine-readable
``stats.npz`` side-car (``mean_bgr``/``std_bgr``/``mean_hsv``/``std_hsv`` float32
arrays + ``frame_count``/``frame_shape``) — the HSV-space pass is always-on, with
a *circular* mean/stddev for the Hue channel (OpenCV H ∈ 0..179, each unit = 2°).
Tool 8 (``auto_roi_discoverer``) consumes these ``.npz`` files. Each summary
``cells[]`` ``"ok"`` entry also carries ``most_stable_hsv`` (HSV at the cell's
single most-stable pixel — the band-center seed) and ``stability_percentiles``.

Usage:
    python tools/overlay_stack_analyzer.py [--input INPUT_DIR] [--output OUTPUT_DIR]
        [--min-frames N] [--ref-height H] [--heatmap]
"""

import argparse
import datetime
import glob
import io
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
    """``apps/tooling/output/labeled`` — intentionally identical to
    ``video_timeline_labeler._default_output_dir()`` so Tool 7's default input
    always equals Tool 6's default output. One level up from ``tools/`` (the
    tooling app root); ``apps/tooling/output/`` is already gitignored."""
    return os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
        "output",
        "labeled",
    )


def _default_output_dir() -> str:
    """``apps/tooling/output/overlay_stacks`` — same ``__file__``-relative math
    as ``_default_input_dir`` (a sibling of Tool 6's ``output/labeled``)."""
    return os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
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


# Circular streaming accumulator for the OpenCV Hue channel (0..179, each unit = 2°).
# A naive Welford on H is meaningless near the 0/179 wrap; this keeps running sums of
# sin/cos of the per-pixel hue *angle* and finalizes to a circular mean (back in
# 0..179) and a circular stddev (in H units). Same math as
# ``minimap_zone_selector/app.py:_compute_zone_hsv``.

_HUE_CV_TO_RAD = 2.0 * np.pi / 180.0  # one OpenCV H unit → radians


def _circ_hue_init(shape) -> tuple[int, np.ndarray, np.ndarray]:
    """``(count, sin_sum, cos_sum)`` zero-state on ``float64`` arrays of ``shape``
    (the 2-D ``h × w`` of a cell — the Hue channel is single-channel)."""
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
    """Return ``(circular_mean_hue, circular_stddev_hue)`` — both in OpenCV H units
    (0..179 / 0..90 respectively). ``count == 0`` → ``ValueError``; a constant hue
    (and the single-sample case) → stddev ``≈ 0``.

    ``R = √(mean_sin² + mean_cos²)``; mean angle = ``atan2(mean_sin, mean_cos)`` →
    ``% 360°`` → ``/ 2`` to OpenCV units; ``std_rad ≈ √(−2·ln max(R, 1e-9))``
    (0 when ``R ≥ 1``), degrees ``/ 2`` to OpenCV units, clamped to ``[0, 90]``
    (the largest possible circular separation is 180° = 90 H units).
    """
    n, sin_sum, cos_sum = state
    if n == 0:
        raise ValueError("cannot finalize a circular-Hue state with count 0")
    mean_sin = sin_sum / n
    mean_cos = cos_sum / n
    R = np.sqrt(mean_sin ** 2 + mean_cos ** 2)
    mean_deg = np.degrees(np.arctan2(mean_sin, mean_cos)) % 360.0
    mean_cv = (mean_deg / 2.0) % 180.0
    # Snap R values within float-noise of 1.0 to exactly 1.0 so a constant or
    # single-sample hue produces exactly std=0 (otherwise float roundoff in sin²+cos²
    # can yield R≈0.9999999 → std≈0.013° instead of 0).
    R_clipped = np.where(R >= 1.0 - 1e-9, 1.0, np.maximum(R, 1e-9))
    inner = np.maximum(-2.0 * np.log(R_clipped), 0.0)  # ≥0; exactly 0 when R≈1
    std_cv = np.clip(np.degrees(np.sqrt(inner)) / 2.0, 0.0, 90.0)
    return mean_cv, std_cv


# ---------------------------------------------------------------------------
# Per-cell stats.npz side-car — the machine-readable companion to the PNGs
# ---------------------------------------------------------------------------


def _stats_npz_bytes(
    mean_bgr: np.ndarray,
    std_bgr: np.ndarray,
    mean_hsv: np.ndarray,
    std_hsv: np.ndarray,
    frame_count: int,
    frame_shape,
) -> bytes:
    """Serialize a cell's per-pixel stat arrays to compressed ``.npz`` bytes.

    Image arrays are stored ``float32`` (ample precision; half the disk of float64,
    and ``savez_compressed`` shrinks the smooth mean/std fields further). ``mean_hsv``
    channel 0 is the *circular* mean Hue (OpenCV 0..179); ``std_hsv`` channel 0 is the
    *circular* stddev Hue (OpenCV H units); channels 1/2 of each are ordinary S/V.
    """
    buf = io.BytesIO()
    np.savez_compressed(
        buf,
        mean_bgr=np.asarray(mean_bgr, dtype=np.float32),
        std_bgr=np.asarray(std_bgr, dtype=np.float32),
        mean_hsv=np.asarray(mean_hsv, dtype=np.float32),
        std_hsv=np.asarray(std_hsv, dtype=np.float32),
        frame_count=np.int64(int(frame_count)),
        frame_shape=np.asarray([int(d) for d in frame_shape], dtype=np.int64),
    )
    return buf.getvalue()


def load_stats_npz(src) -> dict:
    """Load a ``stats.npz`` written by :func:`_stats_npz_bytes` / :func:`_write_stats_npz`.

    ``src`` may be a filesystem path (``str``/``Path`` — read via ``Path.read_bytes``
    so Windows non-ASCII paths are safe) or raw ``bytes``. Returns a plain dict:
    ``mean_bgr``/``std_bgr``/``mean_hsv``/``std_hsv`` (float32 arrays),
    ``frame_count`` (int), ``frame_shape`` (tuple of ints).
    """
    raw = bytes(src) if isinstance(src, (bytes, bytearray)) else Path(src).read_bytes()
    with np.load(io.BytesIO(raw)) as data:
        return {
            "mean_bgr": np.asarray(data["mean_bgr"]),
            "std_bgr": np.asarray(data["std_bgr"]),
            "mean_hsv": np.asarray(data["mean_hsv"]),
            "std_hsv": np.asarray(data["std_hsv"]),
            "frame_count": int(data["frame_count"]),
            "frame_shape": tuple(int(d) for d in data["frame_shape"]),
        }


def _write_stats_npz(
    dest: str,
    mean_bgr: np.ndarray,
    std_bgr: np.ndarray,
    mean_hsv: np.ndarray,
    std_hsv: np.ndarray,
    frame_count: int,
    frame_shape,
) -> None:
    """Write the ``stats.npz`` side-car to ``dest`` (creating parent dirs first),
    Windows non-ASCII-path-safe — serialize to bytes, then ``Path.write_bytes``."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    Path(dest).write_bytes(
        _stats_npz_bytes(mean_bgr, std_bgr, mean_hsv, std_hsv, frame_count, frame_shape)
    )


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
    """``{"mean": ..., "stddev": ..., "stats": ...[, "heatmap": ...]}`` absolute paths
    for a cell. ``stats.npz`` (the machine-readable side-car) is always present;
    ``variance_heatmap.png`` only when ``--heatmap`` is on."""
    cell_dir = os.path.join(output_root, version_dir, class_dir)
    paths = {
        "mean": os.path.join(cell_dir, "mean.png"),
        "stddev": os.path.join(cell_dir, "stddev.png"),
        "stats": os.path.join(cell_dir, "stats.npz"),
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

    # Pass 2 — re-read, resize off-shape frames, fold into the streaming accumulators:
    # BGR mean/stddev (always) plus HSV-space stats (now always-on — Tool 8 reads them).
    # The S/V channels use ordinary Welford; the Hue channel uses the circular
    # accumulator and overwrites the (meaningless) ordinary H mean/std at finalize.
    bgr_state = _welford_init(target_shape)
    hsv_state = _welford_init(target_shape)
    hue_state = _circ_hue_init((target_shape[0], target_shape[1]))
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
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        hsv_state = _welford_update(hsv_state, hsv.astype(np.float64))
        hue_state = _circ_hue_update(hue_state, hsv[:, :, 0])

    n = bgr_state[0]
    if n == 0:
        return _skipped_entry(version_dir, class_dir, "no_readable_frames")
    if n < min_frames:
        return _skipped_entry(
            version_dir, class_dir, "too_few_frames",
            frame_count=n, frame_shape=list(target_shape), resized_count=resized_count,
        )

    mean_bgr, stddev_bgr = _welford_finalize(bgr_state)
    mean_hsv_lin, std_hsv_lin = _welford_finalize(hsv_state)
    hue_mean_cv, hue_std_cv = _circ_hue_finalize(hue_state)
    mean_hsv = mean_hsv_lin.copy()
    std_hsv = std_hsv_lin.copy()
    mean_hsv[:, :, 0] = hue_mean_cv  # circular H mean (OpenCV 0..179)
    std_hsv[:, :, 0] = hue_std_cv    # circular H stddev (OpenCV H units)

    # Per-pixel instability = mean of the BGR stddev channels (the same metric Tool 8's
    # discoverer uses). The single most-stable pixel seeds Tool 8's HSV band centers.
    instability = stddev_bgr.mean(axis=2)
    sy, sx = np.unravel_index(int(np.argmin(instability)), instability.shape)
    most_stable_hsv = [
        float(mean_hsv[sy, sx, 0]),
        float(mean_hsv[sy, sx, 1]),
        float(mean_hsv[sy, sx, 2]),
    ]
    p10, p50, p90 = (float(v) for v in np.percentile(instability, [10.0, 50.0, 90.0]))
    stability_percentiles = {"p10": p10, "p50": p50, "p90": p90}

    mean_u8 = np.clip(np.round(mean_bgr), 0, 255).astype(np.uint8)
    std_u8 = np.clip(stddev_bgr, 0, 255).astype(np.uint8)
    out_paths = _cell_output_paths(output_root, version_dir, class_dir, want_heatmap)
    try:
        _write_png(out_paths["mean"], mean_u8)
        _write_png(out_paths["stddev"], std_u8)
        _write_stats_npz(
            out_paths["stats"], mean_bgr, stddev_bgr, mean_hsv, std_hsv, n, target_shape
        )
        if want_heatmap:
            # Mean of the Saturation + Value stddev maps only — Hue (channel 0) is
            # circular, so a naive per-pixel stddev there is meaningless (179 vs 0 looks
            # like huge variance for adjacent reds). The real H stat lives in std_hsv.
            scalar = std_hsv_lin[..., 1:].mean(axis=2)
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
        "stability_score": _stability_score(stddev_bgr),
        "most_stable_hsv": most_stable_hsv,
        "stability_percentiles": stability_percentiles,
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
        help="Labeled dataset root (default: apps/tooling/output/labeled — Tool 6's default output).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output root for stacked images (default: apps/tooling/output/overlay_stacks).",
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
