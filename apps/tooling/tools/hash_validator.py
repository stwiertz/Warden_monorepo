"""Hash Accuracy Validator (Tool 4) — Validates map_config.json reference hashes against labeled frames.

Loads map_config.json, iterates all *_start.png and *_end.png labeled frames in output/labeled/,
predicts the map for each frame via nearest hash (shift-tolerant Hamming distance), and reports
per-frame and per-map accuracy. Maps with no reference hash in map_config.json are listed
separately as "no_reference". Outputs output/accuracy_report.json.

Usage:
    python tools/hash_validator.py
    python tools/hash_validator.py --images output/labeled --map-config output/map_config.json
    python tools/hash_validator.py --shift-tolerance 0
    python tools/hash_validator.py --resolution 720
"""

import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import cv2
import imagehash

from hash_comparator import IMAGE_EXTENSIONS, build_canvases, compute_hash, hamming_shift_tolerant

REF_HEIGHT = 1080  # reference resolution height for ROI coordinates


# ---------------------------------------------------------------------------
# Frame loading
# ---------------------------------------------------------------------------


def load_labeled_frames(images_dir):
    """Load start/end frames from each map subdirectory, skipping score frames.

    Args:
        images_dir: Path to labeled/ directory with <map_name>/ subdirectories.

    Returns:
        dict: {map_name: [(filename, BGR numpy array), ...]}

    Raises:
        ValueError: If no frames are found in any subdirectory.
    """
    all_frames = {}

    for entry in sorted(os.listdir(images_dir)):
        subdir = os.path.join(images_dir, entry)
        if not os.path.isdir(subdir):
            continue

        image_files = sorted(
            f for f in os.listdir(subdir)
            if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
            and os.path.splitext(f)[0].lower().endswith(("_start", "_end"))
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
            print(f"  Warning: No valid start/end images in {subdir}, skipping", file=sys.stderr)

    if not all_frames:
        raise ValueError(f"No map subdirectories with valid start/end frames found in '{images_dir}'")

    return all_frames


# ---------------------------------------------------------------------------
# Prediction
# ---------------------------------------------------------------------------


def predict_map(canvas, ref_hashes, hash_size, method, shift_tolerance):
    """Predict the map for a canvas by finding the nearest reference hash.

    Args:
        canvas: Single-channel grayscale numpy canvas.
        ref_hashes: dict {map_name: list[imagehash.ImageHash]}
            Each map may have multiple reference hashes (e.g. from different video sources).
            The minimum distance across all hashes for a map is used.
        hash_size: Hash dimension.
        method: Hash method string ('ahash', 'dhash', 'phash').
        shift_tolerance: Max horizontal bit-shift for Hamming distance comparison.

    Returns:
        tuple: (predicted_map_name, min_distance)
    """
    frame_hash = compute_hash(canvas, hash_size, method)

    best_name = None
    best_dist = None

    for map_name, hashes in ref_hashes.items():  # insertion order is alphabetical (sorted at build time)
        for ref_hash in hashes:
            dist = hamming_shift_tolerant(frame_hash, ref_hash, shift_tolerance)
            if best_dist is None or dist < best_dist:
                best_dist = dist
                best_name = map_name

    return best_name, best_dist


# ---------------------------------------------------------------------------
# Validation loop
# ---------------------------------------------------------------------------


def run_validation(labeled_frames, map_config, shift_tolerance, resolution, all_map_names=None):
    """Run per-frame predictions against reference hashes.

    Args:
        labeled_frames: dict {map_name: [(fname, BGR array), ...]}
        map_config: Parsed map_config.json dict.
        shift_tolerance: Max horizontal bit-shift for Hamming comparisons.
        resolution: Processing height in pixels (must match resolution used to generate map_config).
        all_map_names: Optional set of all map folder names in images_dir (including those with
                       no start/end frames). When provided, no_reference is derived from this
                       set rather than from labeled_frames keys — ensuring empty folders (e.g.
                       maps awaiting labeling) still appear in the report.

    Returns:
        tuple: (frame_results_list, sorted_no_reference_list)
            frame_results_list: list of dicts with frame, true_map, predicted, distance, correct
            sorted_no_reference_list: sorted list of map names with no reference hash
    """
    roi_dict = {**map_config["roi"], "name": "map_name_hud"}
    canvas_size = map_config["canvas_size"]
    hash_size = map_config["hash_size"]
    method = map_config["hash_method"]
    tile_cols = map_config.get("tile_cols", 3)

    # Sort alphabetically at build time so iteration order is stable (alphabetical tie-break)
    # without needing sorted() on every per-frame predict call (F4).
    # Values may be a single hex string or a list of hex strings (multi-source hashes).
    ref_hashes = {}
    for name, h in sorted(map_config["maps"].items()):
        if isinstance(h, list):
            ref_hashes[name] = [imagehash.hex_to_hash(x) for x in h]
        else:
            ref_hashes[name] = [imagehash.hex_to_hash(h)]

    # Use all_map_names if provided so empty dirs (no start/end frames yet) are captured
    candidate_names = all_map_names if all_map_names is not None else set(labeled_frames.keys())
    known = {name: frames for name, frames in labeled_frames.items() if name in ref_hashes}
    no_reference = sorted(name for name in candidate_names if name not in ref_hashes)

    frame_results = []

    for map_name, frames in sorted(known.items()):
        canvases = build_canvases(
            frames, roi_dict, canvas_size, resolution, tile_cols, text_anchor_width=None
        )

        # Report actual processable count vs loaded count (F7)
        n_skipped = len(frames) - len(canvases)
        skip_note = f", {n_skipped} skipped (ROI/read error)" if n_skipped else ""
        print(f"\n  Validating '{map_name}' ({len(canvases)} frame(s){skip_note})...")

        # Skip map entirely if no canvases were built (F3)
        if not canvases:
            print(f"  Warning: No valid canvases for '{map_name}', skipping", file=sys.stderr)
            continue

        for fname, canvas in canvases:
            predicted, dist = predict_map(canvas, ref_hashes, hash_size, method, shift_tolerance)
            correct = predicted == map_name
            frame_results.append({
                "frame": fname,
                "true_map": map_name,
                "predicted": predicted,
                "distance": dist,
                "correct": correct,
            })
            status = "OK" if correct else f"WRONG (predicted: {predicted})"
            print(f"    {fname}: dist={dist}  {status}")

    return frame_results, no_reference


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def generate_report(frame_results, no_reference, output_dir):
    """Generate accuracy_report.json and print summary to stdout.

    Args:
        frame_results: list of per-frame result dicts.
        no_reference: sorted list of map names with no reference hash.
        output_dir: Directory to write accuracy_report.json.

    Returns:
        str: Absolute path to the written report.
    """
    # Group by true_map
    by_map_frames = collections.defaultdict(list)
    for result in frame_results:
        by_map_frames[result["true_map"]].append(result)

    by_map = {}
    for map_name in sorted(by_map_frames):
        results = by_map_frames[map_name]
        total = len(results)
        correct = sum(1 for r in results if r["correct"])
        incorrect = total - correct
        accuracy = round(correct / total, 4) if total > 0 else 0.0
        by_map[map_name] = {
            "total": total,
            "correct": correct,
            "incorrect": incorrect,
            "accuracy": accuracy,
            "frames": [
                {
                    "frame": r["frame"],
                    "predicted": r["predicted"],
                    "distance": r["distance"],
                    "correct": r["correct"],
                }
                for r in results
            ],
        }

    total_frames = len(frame_results)
    total_correct = sum(1 for r in frame_results if r["correct"])
    total_incorrect = total_frames - total_correct
    overall_accuracy = round(total_correct / total_frames, 4) if total_frames > 0 else 0.0

    report = {
        "summary": {
            "total_frames": total_frames,
            "correct": total_correct,
            "incorrect": total_incorrect,
            "accuracy": overall_accuracy,
            "maps_evaluated": sorted(by_map.keys()),
            "maps_no_reference": no_reference,
        },
        "by_map": by_map,
        "no_reference": no_reference,
    }

    os.makedirs(output_dir, exist_ok=True)  # guard if called outside main() (F6)
    report_path = os.path.join(output_dir, "accuracy_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    # Print summary
    print(f"\n{'='*60}")
    print(f"Accuracy Summary")
    print(f"  Total frames: {total_frames}")
    print(f"  Correct:      {total_correct}")
    print(f"  Incorrect:    {total_incorrect}")
    print(f"  Accuracy:     {overall_accuracy:.1%}")
    if no_reference:
        print(f"  No reference: {no_reference}")
    if total_incorrect > 0:
        print("\n  Incorrect predictions:")
        for r in frame_results:
            if not r["correct"]:
                print(f"    [{r['true_map']}] {r['frame']} -> predicted '{r['predicted']}' (dist={r['distance']})")
    print(f"{'='*60}")
    print(f"\n  Report written: {os.path.abspath(report_path)}")

    return report_path


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Validate map_config.json reference hashes against labeled start/end frames."
    )
    parser.add_argument(
        "--images",
        metavar="DIR",
        default="output/labeled",
        help="Path to labeled/ directory with <map_name>/ subdirectories (default: output/labeled)",
    )
    parser.add_argument(
        "--map-config",
        metavar="PATH",
        default="output/map_config.json",
        help="Path to map_config.json (default: output/map_config.json)",
    )
    parser.add_argument(
        "--shift-tolerance",
        type=int,
        default=2,
        metavar="N",
        help="Max horizontal bit-shift for Hamming distance comparison (default: 2)",
    )
    parser.add_argument(
        "--resolution",
        type=int,
        default=720,
        metavar="N",
        help="Processing height in pixels — must match resolution used to generate map_config.json (default: 720)",
    )
    parser.add_argument(
        "-o", "--output-dir",
        default="output",
        help="Output directory for accuracy_report.json (default: output)",
    )

    args = parser.parse_args()

    # Validate inputs
    if not os.path.isdir(args.images):
        print(f"Error: Images directory not found: {args.images}", file=sys.stderr)
        sys.exit(1)

    if not os.path.isfile(args.map_config):
        print(f"Error: Map config not found: {args.map_config}", file=sys.stderr)
        sys.exit(1)

    with open(args.map_config) as f:
        map_config = json.load(f)

    os.makedirs(args.output_dir, exist_ok=True)

    print("Hash Accuracy Validator")
    print(f"  Images:          {os.path.abspath(args.images)}")
    print(f"  Map config:      {os.path.abspath(args.map_config)}")
    print(f"  Shift tolerance: {args.shift_tolerance}")
    print(f"  Resolution:      {args.resolution}p")
    print(f"  Output:          {os.path.abspath(args.output_dir)}")

    # Scan all subdirs upfront so empty map folders are captured in no_reference
    all_map_names = {
        entry for entry in os.listdir(args.images)
        if os.path.isdir(os.path.join(args.images, entry))
    }

    print(f"\nLoading labeled frames from '{args.images}'...")
    sys.stdout.flush()  # ensure banner is flushed before stderr warnings appear (F5)
    try:
        labeled_frames = load_labeled_frames(args.images)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"\nRunning validation ({len(map_config['maps'])} reference maps)...")
    try:
        frame_results, no_reference = run_validation(
            labeled_frames, map_config, args.shift_tolerance, args.resolution,
            all_map_names=all_map_names,
        )
    except Exception as e:
        print(f"Error during validation: {e}", file=sys.stderr)
        sys.exit(1)

    generate_report(frame_results, no_reference, args.output_dir)

    print("\nDone.")


if __name__ == "__main__":
    main()
