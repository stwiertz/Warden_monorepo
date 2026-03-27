"""Hash Comparator — CLI tool for comparing perceptual hash methods across EVA maps.

Loads labeled frames organized by map (from Frame Labeler output), generates multiple
perceptual hash types (aHash, dHash, pHash), computes pairwise Hamming Distances, and
produces a comparison report to identify the most reliable hash method + ROI combination.

Usage:
    # Compare all methods on all configured ROIs:
    python tools/hash_comparator.py --images path/to/labeled/

    # Use a specific ROI only:
    python tools/hash_comparator.py --images path/to/labeled/ --roi map_name_hud

    # Test specific methods:
    python tools/hash_comparator.py --images path/to/labeled/ --methods phash dhash

    # Resolution sweep:
    python tools/hash_comparator.py --images path/to/labeled/ --resolutions 1080 720 360

    # Write canvas previews for visual inspection:
    python tools/hash_comparator.py --images path/to/labeled/ --preview -o output/hashes
"""

import argparse
import collections
import itertools
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cv2
import imagehash
import numpy as np
from PIL import Image

from utils.config import load_config
from utils.image import apply_threshold, downscale, extract_roi, find_text_anchor, scale_roi, to_grayscale

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp"}
REF_HEIGHT = 1080  # reference resolution height for ROI coordinates


# ---------------------------------------------------------------------------
# Core hashing helpers
# ---------------------------------------------------------------------------


def compute_hash(canvas, hash_size, method):
    """Compute a perceptual hash from a grayscale canvas.

    Args:
        canvas: Single-channel grayscale numpy array.
        hash_size: Hash dimension (8 = 64-bit hash).
        method: One of 'ahash', 'dhash', 'phash'.

    Returns:
        imagehash.ImageHash: The hash object.
    """
    pil_image = Image.fromarray(canvas)
    if method == "ahash":
        return imagehash.average_hash(pil_image, hash_size=hash_size)
    elif method == "dhash":
        return imagehash.dhash(pil_image, hash_size=hash_size)
    elif method == "phash":
        return imagehash.phash(pil_image, hash_size=hash_size)
    else:
        raise ValueError(f"Unknown hash method: '{method}'. Use ahash, dhash, or phash.")


def representative_hash(canvases, hash_size, method):
    """Compute the most common (mode) hash across multiple canvases for one map.

    Using mode over multiple frames is more robust than single-frame hashing.
    If every frame produces a unique hash (unstable ROI), returns the first frame's hash.

    Args:
        canvases: List of (filename, grayscale canvas numpy array) tuples.
        hash_size: Hash dimension.
        method: Hash method string.

    Returns:
        imagehash.ImageHash: The representative hash, or None if no canvases.
    """
    if not canvases:
        return None

    hash_strings = []
    for _fname, canvas in canvases:
        h = compute_hash(canvas, hash_size, method)
        hash_strings.append(str(h))

    most_common_str = collections.Counter(hash_strings).most_common(1)[0][0]
    return imagehash.hex_to_hash(most_common_str)


# ---------------------------------------------------------------------------
# Frame loading and canvas building
# ---------------------------------------------------------------------------


def load_all_frames(images_dir):
    """Load all image files from each map subdirectory.

    Args:
        images_dir: Path to labeled/ directory with <map_name>/ subdirectories.

    Returns:
        dict: {map_name: [(filename, BGR numpy array), ...]}

    Raises:
        ValueError: If no map subdirectories with images are found.
    """
    all_frames = {}

    for entry in sorted(os.listdir(images_dir)):
        subdir = os.path.join(images_dir, entry)
        if not os.path.isdir(subdir):
            continue

        image_files = sorted(
            f for f in os.listdir(subdir)
            if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
        )
        frames = []
        for fname in image_files:
            fpath = os.path.join(subdir, fname)
            frame = cv2.imread(fpath)
            if frame is None:
                print(f"  Warning: Could not read {fpath}, skipping", file=sys.stderr)
                continue
            frames.append((fname, frame))

        if frames:
            all_frames[entry] = frames
            print(f"  {entry}: {len(frames)} frame(s)")
        else:
            print(f"  Warning: No valid images in {subdir}, skipping", file=sys.stderr)

    if not all_frames:
        raise ValueError(f"No map subdirectories with valid images found in '{images_dir}'")

    return all_frames


def tile_into_canvas(gray, canvas_size, n_cols):
    """Build a square canvas by splitting a wide strip into n_cols columns stacked vertically.

    Example with n_cols=3 on a 178×13 strip (267×22 at 720p):
        col 0: pixels 0–58   (59×13)
        col 1: pixels 59–117 (59×13)   →  stacked: 59×39  →  resize to 64×64
        col 2: pixels 118–176 (59×13)

    This preserves horizontal letter features far better than a direct 267→64 squeeze,
    which applies a 4× horizontal compression and 3× vertical stretch.

    Args:
        gray: Single-channel grayscale numpy array (height, width).
        canvas_size: Target square dimension for the output canvas.
        n_cols: Number of equal columns to split into and stack vertically.

    Returns:
        numpy array of shape (canvas_size, canvas_size).
    """
    h, w = gray.shape
    col_w = w // n_cols
    cols = [gray[:, i * col_w: (i + 1) * col_w] for i in range(n_cols)]
    # Last column may be 1-2px wider if w is not evenly divisible — trim to col_w
    cols = [c[:, :col_w] for c in cols]
    stacked = np.vstack(cols)  # shape: (h * n_cols, col_w)
    return cv2.resize(stacked, (canvas_size, canvas_size), interpolation=cv2.INTER_AREA)


def build_canvases(frames, ref_roi, canvas_size, target_h, tile_cols=1, text_anchor_width=None, threshold_hash=False):
    """Crop ROI, optionally downscale, and build a square canvas for each frame.

    Args:
        frames: List of (filename, BGR numpy array) tuples.
        ref_roi: ROI dict at reference resolution (1920x1080).
        canvas_size: Target square dimension.
        target_h: Desired processing height. Frames taller than target_h are downscaled;
                  frames at or below target_h are left unchanged (downscale never upscales).
        tile_cols: Number of vertical columns to split the ROI strip into and stack
                   (default 1 = plain resize). Use 3 for wide text ROIs to preserve
                   letter features without extreme horizontal compression.
        text_anchor_width: If set, scan the ROI for the first white pixel column and
                           extract a sub-ROI of this width (in pixels @1080p) from that
                           anchor. None or 0 = disabled (use full ROI).
        threshold_hash: If True, apply Otsu's adaptive threshold after grayscale
                        conversion, binarizing the crop before hashing.
                        Default False (function level); config default is True.

    Returns:
        list: (filename, grayscale or binary canvas numpy array) tuples, skipping failed frames.
    """
    canvases = []
    for fname, frame in frames:
        # Always attempt downscale; it's a no-op when frame height <= target_h
        frame, _ = downscale(frame, target_h)

        fh, fw = frame.shape[:2]
        # Scale ROI from reference resolution to actual frame height
        roi = scale_roi(ref_roi, fh / REF_HEIGHT)

        if roi["x"] + roi["width"] > fw or roi["y"] + roi["height"] > fh:
            print(
                f"  Warning: ROI out of bounds for {fname} ({fw}x{fh}), skipping",
                file=sys.stderr,
            )
            continue

        try:
            cropped = extract_roi(frame, roi)
        except ValueError as e:
            print(f"  Warning: {e}, skipping {fname}", file=sys.stderr)
            continue

        if text_anchor_width:
            scaled_anchor_w = max(1, int(text_anchor_width * (fh / REF_HEIGHT)))
            anchor_x = find_text_anchor(cropped)
            if anchor_x == -1:
                print(
                    f"  Warning: No text anchor found in {fname}, skipping",
                    file=sys.stderr,
                )
                continue
            right = min(anchor_x + scaled_anchor_w, cropped.shape[1])
            if right - anchor_x < 2:
                print(
                    f"  Warning: Anchor crop too narrow ({right - anchor_x}px) in {fname}, skipping",
                    file=sys.stderr,
                )
                continue
            cropped = cropped[:, anchor_x:right]

        gray = to_grayscale(cropped)
        if threshold_hash:
            gray = apply_threshold(gray)
        # Tiling is disabled when anchor cropping is active: the sub-ROI is already
        # narrow and tiling would amplify anchor jitter (1px shift → large hash diff).
        if tile_cols > 1 and not text_anchor_width:
            canvas = tile_into_canvas(gray, canvas_size, tile_cols)
        else:
            canvas = cv2.resize(gray, (canvas_size, canvas_size), interpolation=cv2.INTER_AREA)
        canvases.append((fname, canvas))

    return canvases


# ---------------------------------------------------------------------------
# Collision detection
# ---------------------------------------------------------------------------


def hamming_shift_tolerant(hash_a, hash_b, max_shift):
    """Compute minimum Hamming Distance across horizontal bit-shifts of hash_b.

    Rolls each row of hash_b.hash left/right by up to max_shift positions and
    returns the minimum distance found. Useful when the ROI crop position varies
    slightly between videos (e.g. sub-pixel text anchor jitter → bit shift in dHash rows).

    Args:
        hash_a: imagehash.ImageHash
        hash_b: imagehash.ImageHash
        max_shift: Max bit positions to shift in either direction. 0 = exact Hamming Distance.

    Returns:
        int: Minimum Hamming Distance across all tested shifts.
    """
    if max_shift == 0:
        return hash_a - hash_b
    bits_a = hash_a.hash  # shape (hash_size, hash_size), dtype bool
    bits_b = hash_b.hash
    best = bits_a.size
    for shift in range(-max_shift, max_shift + 1):
        # Roll each row independently — models a uniform horizontal image crop offset
        shifted = np.roll(bits_b, shift, axis=1)
        dist = int(np.sum(bits_a != shifted))
        if dist < best:
            best = dist
    return best


def compute_pairwise_distances(hash_dict, shift_tolerance=0):
    """Compute all pairwise Hamming Distances for a dict of hashes.

    Args:
        hash_dict: {map_name: imagehash.ImageHash}
        shift_tolerance: Max horizontal bit-shift to absorb (0 = exact).

    Returns:
        list: (map_a, map_b, distance) tuples sorted ascending by distance.
    """
    distances = []
    for (name_a, hash_a), (name_b, hash_b) in itertools.combinations(hash_dict.items(), 2):
        dist = hamming_shift_tolerant(hash_a, hash_b, shift_tolerance)
        distances.append((name_a, name_b, dist))
    distances.sort(key=lambda x: x[2])
    return distances


def check_collisions(distances, threshold):
    """Return collision pairs below threshold.

    Args:
        distances: Sorted list of (map_a, map_b, distance) tuples.
        threshold: Minimum acceptable Hamming Distance.

    Returns:
        list: (map_a, map_b, distance) tuples that are collisions.
    """
    return [(a, b, d) for a, b, d in distances if d < threshold]


# ---------------------------------------------------------------------------
# Main comparison loop
# ---------------------------------------------------------------------------


def run_comparison(
    images_dir, rois, methods, canvas_size, hash_size, collision_threshold,
    resolutions=None, tile_cols=1, text_anchor_width=None, shift_tolerance=0,
    threshold_hash=False, preview=False, preview_dir=None
):
    """Run multi-hash comparison across all ROIs, methods, and optional resolutions.

    Args:
        images_dir: Path to labeled/ directory with <map_name>/ subdirectories.
        rois: List of ROI dicts at reference resolution (1920x1080).
        methods: List of method strings.
        canvas_size: Target canvas size.
        hash_size: Hash size.
        collision_threshold: Min Hamming Distance before flagging collision.
        resolutions: Optional list of target heights to sweep. None = source only.
        tile_cols: Number of vertical columns for tiling canvas construction.
        text_anchor_width: If set, anchor sub-ROI extraction to first white pixel column
                           (pixels @1080p). None or 0 = disabled.
        shift_tolerance: Max horizontal bit-shift to absorb when comparing hashes (0 = exact).
        threshold_hash: If True, apply Otsu's adaptive threshold after grayscale conversion
                        before hashing. Matches the setting used in warden_analyzer.py at
                        inference time. Default False.
        preview: If True, write canvas images to preview_dir.
        preview_dir: Directory for preview images.

    Returns:
        dict: {roi_name: {resolution: {method: {hashes, distances, collisions, stats}}}}
    """
    print(f"\nLoading frames from '{images_dir}'...")
    all_frames = load_all_frames(images_dir)

    # Get source height from first frame for default resolution
    first_frames = next(iter(all_frames.values()))
    src_h = first_frames[0][1].shape[0]  # used only to determine default res_list

    res_list = resolutions if resolutions else [src_h]
    results = {}

    for roi_config in rois:
        roi_name = roi_config["name"]
        results[roi_name] = {}

        print(f"\n{'='*60}")
        print(
            f"ROI: {roi_name}  "
            f"({roi_config['x']},{roi_config['y']} "
            f"{roi_config['width']}x{roi_config['height']} @ {REF_HEIGHT}p)"
        )

        for target_h in res_list:
            results[roi_name][target_h] = {}
            print(f"\n  Resolution: {target_h}p")

            # Build canvases for each map
            map_canvases = {}
            for map_name, frames in all_frames.items():
                canvases = build_canvases(frames, roi_config, canvas_size, target_h, tile_cols, text_anchor_width=text_anchor_width, threshold_hash=threshold_hash)
                map_canvases[map_name] = canvases

                if preview and preview_dir and canvases:
                    for fname, canvas in canvases:
                        stem = os.path.splitext(fname)[0]
                        preview_name = (
                            f"preview_{roi_name}_{target_h}p_{map_name}_{stem}.png"
                        )
                        cv2.imwrite(os.path.join(preview_dir, preview_name), canvas)

            for method in methods:
                print(f"\n  Method: {method}")

                hash_dict = {}
                for map_name, canvases in map_canvases.items():
                    if not canvases:
                        print(
                            f"    Warning: No valid canvases for '{map_name}', skipping",
                            file=sys.stderr,
                        )
                        continue
                    rep = representative_hash(canvases, hash_size, method)
                    if rep is not None:
                        hash_dict[map_name] = rep
                        print(f"    {map_name}: {str(rep)}  ({len(canvases)} frame(s))")

                if len(hash_dict) < 2:
                    print("    Not enough maps to compare, skipping.", file=sys.stderr)
                    results[roi_name][target_h][method] = {
                        "hashes": {n: str(h) for n, h in hash_dict.items()},
                        "distances": [],
                        "collisions": [],
                        "stats": {"min": 0, "max": 0, "mean": 0.0, "collision_count": 0},
                    }
                    continue

                distances = compute_pairwise_distances(hash_dict, shift_tolerance)
                collisions = check_collisions(distances, collision_threshold)
                dist_values = [d for _, _, d in distances]
                stats = {
                    "min": min(dist_values),
                    "max": max(dist_values),
                    "mean": round(sum(dist_values) / len(dist_values), 2),
                    "collision_count": len(collisions),
                }

                print(
                    f"    Distances — min={stats['min']}, max={stats['max']}, "
                    f"mean={stats['mean']}, collisions={stats['collision_count']}"
                )
                for name_a, name_b, dist in distances[:5]:
                    marker = "  << COLLISION" if dist < collision_threshold else ""
                    print(f"      {dist:>3d}  {name_a} vs {name_b}{marker}")
                if len(distances) > 5:
                    print(f"      ... ({len(distances) - 5} more pairs)")
                if collisions:
                    for name_a, name_b, dist in collisions:
                        print(
                            f"    COLLISION: '{name_a}' vs '{name_b}' dist={dist}",
                            file=sys.stderr,
                        )

                results[roi_name][target_h][method] = {
                    "hashes": {n: str(h) for n, h in hash_dict.items()},
                    "distances": [
                        {"map_a": a, "map_b": b, "distance": d}
                        for a, b, d in distances
                    ],
                    "collisions": [
                        {"map_a": a, "map_b": b, "distance": d}
                        for a, b, d in collisions
                    ],
                    "stats": stats,
                }

    return results


# ---------------------------------------------------------------------------
# Best combination selection
# ---------------------------------------------------------------------------


def select_best_combination(results):
    """Select the (roi, resolution, method) with highest minimum pairwise distance.

    Tie-breaks on collision count (lower is better), then method name alphabetically.

    Returns:
        tuple: ((roi_name, resolution, method), min_dist) or (None, -1).
    """
    best_combo = None
    best_min = -1
    best_collisions = float("inf")

    for roi_name, res_data in results.items():
        for resolution, method_data in res_data.items():
            for method, data in method_data.items():
                min_dist = data["stats"]["min"]
                col = data["stats"]["collision_count"]
                if (
                    min_dist > best_min
                    or (min_dist == best_min and col < best_collisions)
                ):
                    best_combo = (roi_name, resolution, method)
                    best_min = min_dist
                    best_collisions = col

    return best_combo, best_min


# ---------------------------------------------------------------------------
# Output generation
# ---------------------------------------------------------------------------


def generate_report(results, output_dir, best_combo, best_min, shift_tolerance=0):
    """Write hash_comparison_report.json.

    Args:
        results: Nested dict from run_comparison().
        output_dir: Where to write the report.
        best_combo: (roi_name, resolution, method) or None.
        best_min: Minimum pairwise distance for best combo.

    Returns:
        str: Absolute path to the written report file.
    """
    if best_combo:
        roi_name, resolution, method = best_combo
        recommendation = {
            "roi": roi_name,
            "resolution": resolution,
            "method": method,
            "min_pairwise_distance": best_min,
            "note": (
                f"Best: {method} on '{roi_name}' at {resolution}p "
                f"(min distance = {best_min})"
            ),
        }
    else:
        recommendation = {"note": "No valid combinations found."}

    report = {"recommendation": recommendation, "shift_tolerance": shift_tolerance, "results": results}

    report_path = os.path.join(output_dir, "hash_comparison_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n  Report written: {os.path.abspath(report_path)}")
    return report_path


def generate_map_config(results, best_combo, config, output_dir, tile_cols=1):
    """Write map_config.json using the best-performing method+ROI combination.

    Format matches map_config_generator.py output (adds 'hash_method' field).

    Args:
        results: Nested dict from run_comparison().
        best_combo: (roi_name, resolution, method) or None.
        config: Parsed YAML config dict.
        output_dir: Output directory path.
    """
    if not best_combo:
        print("  Warning: No best combination found — skipping map_config.json", file=sys.stderr)
        return

    roi_name, resolution, method = best_combo
    method_data = results[roi_name][resolution][method]

    # Find ROI entry by name from config rois list, fall back to legacy roi key
    rois = config["map_identification"].get("rois", [])
    roi_entry = next((r for r in rois if r["name"] == roi_name), None)
    if roi_entry is None:
        roi_entry = config["map_identification"].get("roi") or {}
    if not roi_entry:
        print(
            f"  Warning: ROI '{roi_name}' not found in config for map_config.json — "
            "roi coordinates will be zeros.",
            file=sys.stderr,
        )

    ref_res = config["reference_resolution"]
    output = {
        "reference_resolution": ref_res,
        "roi": {
            "x": roi_entry.get("x", 0),
            "y": roi_entry.get("y", 0),
            "width": roi_entry.get("width", 0),
            "height": roi_entry.get("height", 0),
        },
        "canvas_size": config["map_identification"]["canvas_size"],
        "hash_size": config["map_identification"]["hash_size"],
        "hash_method": method,
        "tile_cols": tile_cols,
        "maps": method_data["hashes"],
    }

    output_path = os.path.join(output_dir, "map_config.json")
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"  map_config.json written: {os.path.abspath(output_path)}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Compare perceptual hash methods (aHash/dHash/pHash) for EVA map identification."
    )
    parser.add_argument(
        "--images",
        metavar="DIR",
        required=True,
        help="Path to labeled/ directory with <map_name>/ subdirectories",
    )
    parser.add_argument(
        "--roi",
        metavar="NAME",
        default=None,
        help="ROI name from config to use (default: all configured ROIs)",
    )
    parser.add_argument(
        "--methods",
        nargs="+",
        metavar="METHOD",
        choices=["ahash", "dhash", "phash"],
        default=None,
        help="Hash methods to test (default: all from config)",
    )
    parser.add_argument(
        "--resolutions",
        nargs="+",
        type=int,
        metavar="HEIGHT",
        default=None,
        help="Resolution heights to sweep, e.g. 1080 720 360 (default: source only)",
    )
    parser.add_argument(
        "--tile-cols",
        type=int,
        default=None,
        metavar="N",
        help="Split the ROI strip into N equal columns stacked vertically before hashing "
             "(default: from config, fallback 3). Use 1 to disable tiling.",
    )
    parser.add_argument(
        "--shift-tolerance",
        type=int,
        default=None,
        metavar="N",
        help="Max horizontal bit-shift to absorb when comparing hashes "
             "(0 = exact, default: from config). Each unit ≈ 1/hash_size of ROI width.",
    )
    parser.add_argument(
        "--threshold-hash",
        dest="threshold_hash",
        default=None,
        action="store_true",
        help="Binarize the grayscale crop with Otsu's threshold before hashing (overrides config).",
    )
    parser.add_argument(
        "--no-threshold-hash",
        dest="threshold_hash",
        action="store_false",
        help="Disable threshold binarization before hashing (overrides config).",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Write processed canvas images to output dir for visual inspection",
    )
    parser.add_argument(
        "-o", "--output-dir",
        default=None,
        help="Output directory for report and map_config.json (default: from config)",
    )
    parser.add_argument(
        "-c", "--config",
        default="config/config.yaml",
        help="Path to config file (default: config/config.yaml)",
    )

    args = parser.parse_args()

    # Validate inputs
    if not os.path.isfile(args.config):
        print(f"Error: Config file not found: {args.config}", file=sys.stderr)
        sys.exit(1)

    if not os.path.isdir(args.images):
        print(f"Error: Images directory not found: {args.images}", file=sys.stderr)
        sys.exit(1)

    config = load_config(args.config)
    map_id = config["map_identification"]

    # Resolve ROIs
    rois = map_id.get("rois", [])
    if not rois:
        legacy = map_id.get("roi")
        if legacy:
            rois = [legacy]

    if args.roi:
        rois = [r for r in rois if r["name"] == args.roi]
        if not rois:
            print(f"Error: ROI '{args.roi}' not found in config", file=sys.stderr)
            sys.exit(1)

    # Skip ROIs with zero/missing dimensions (TBD placeholders)
    valid_rois = [r for r in rois if r.get("width", 0) > 0 and r.get("height", 0) > 0]
    skipped = [r["name"] for r in rois if r not in valid_rois]
    if skipped:
        print(f"  Skipping ROIs with no coordinates (TBD): {skipped}", file=sys.stderr)
    if not valid_rois:
        print(
            "Error: No valid ROIs found. Set coordinates in config/config.yaml.",
            file=sys.stderr,
        )
        sys.exit(1)
    rois = valid_rois

    # Resolve methods, resolutions, tile_cols, shift_tolerance from CLI or config
    methods = args.methods or map_id.get("hash_methods", ["ahash", "dhash", "phash"])
    resolutions = args.resolutions or (map_id.get("resolutions") or None)
    tile_cols = args.tile_cols if args.tile_cols is not None else map_id.get("tile_cols", 3)
    text_anchor_width = map_id.get("text_anchor_width") or None
    shift_tolerance = args.shift_tolerance if args.shift_tolerance is not None else map_id.get("shift_tolerance", 0)
    threshold_hash = args.threshold_hash if args.threshold_hash is not None else map_id.get("threshold_hash", False)

    # Resolve output directory
    output_dir = args.output_dir or config["output"]["default_dir"]
    os.makedirs(output_dir, exist_ok=True)

    canvas_size = map_id["canvas_size"]
    hash_size = map_id["hash_size"]
    collision_threshold = map_id["collision_threshold"]

    print("Hash Comparator")
    print(f"  Images:      {os.path.abspath(args.images)}")
    print(f"  Output:      {os.path.abspath(output_dir)}")
    print(f"  ROIs:        {[r['name'] for r in rois]}")
    print(f"  Methods:     {methods}")
    print(f"  Resolutions: {resolutions or 'source'}")
    print(f"  Tile cols:   {tile_cols}")
    print(f"  Anchor width: {f'{text_anchor_width}px @1080p' if text_anchor_width else 'disabled'}")
    print(f"  Shift tolerance: {shift_tolerance} bit(s)")
    print(f"  Threshold hash: {threshold_hash}")

    try:
        results = run_comparison(
            images_dir=args.images,
            rois=rois,
            methods=methods,
            canvas_size=canvas_size,
            hash_size=hash_size,
            collision_threshold=collision_threshold,
            resolutions=resolutions,
            tile_cols=tile_cols,
            text_anchor_width=text_anchor_width,
            shift_tolerance=shift_tolerance,
            threshold_hash=threshold_hash,
            preview=args.preview,
            preview_dir=output_dir if args.preview else None,
        )
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error during processing: {e}", file=sys.stderr)
        sys.exit(1)

    best_combo, best_min = select_best_combination(results)

    print(f"\n{'='*60}")
    if best_combo:
        roi_name, resolution, method = best_combo
        col = results[roi_name][resolution][method]["stats"]["collision_count"]
        print(f"Recommendation: {method} on ROI '{roi_name}' at {resolution}p")
        print(f"  Min pairwise distance: {best_min}  |  Collisions: {col}")
    else:
        print("Warning: Could not determine best combination.", file=sys.stderr)
    print(f"{'='*60}")

    generate_report(results, output_dir, best_combo, best_min, shift_tolerance)
    generate_map_config(results, best_combo, config, output_dir, tile_cols=tile_cols)

    print("\nDone.")


if __name__ == "__main__":
    main()
