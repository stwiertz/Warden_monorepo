"""BSD ROI Debugger — diagnostic CLI for inspecting per-ROI brightness values.

Processes I-frames within a time range and for each frame: prints per-ROI mean
brightness with pass/fail status, and exports an annotated PNG with ROI
rectangles drawn on it (green = black/pass, red = not-black/fail).

Usage:
    python tools/bsd_roi_debugger.py <video_path> [--range 0:15] [-o OUTPUT_DIR] [-c CONFIG] [--threshold N]
"""

import argparse
import math
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cv2
import numpy as np
import yaml

from utils.video import extract_iframes_scaled, get_video_info
from utils.image import to_grayscale, scale_roi, extract_roi, is_black


def load_config(config_path):
    """Load and return the YAML configuration."""
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def parse_range(range_str):
    """Parse a 'START:END' range string into a (float, float) tuple.

    Supports formats: '0:15', ':15' (start=0), '400:' (end=infinity).
    """
    parts = range_str.split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid range format '{range_str}'. Expected 'START:END'.")
    start_str, end_str = parts
    start = float(start_str) if start_str.strip() else 0.0
    end = float(end_str) if end_str.strip() else float("inf")
    if math.isnan(start) or math.isnan(end):
        raise ValueError(f"Range values must be numbers, got '{range_str}'.")
    if start < 0 or end < 0:
        raise ValueError(f"Range values must be non-negative, got '{range_str}'.")
    if start > end:
        raise ValueError(f"Range start ({start}) must be <= end ({end}).")
    return (start, end)


def run(video_path, output_dir, config, time_range, threshold_override=None):
    """Run ROI debug analysis on a video file.

    Returns:
        int: Number of frames analyzed.
    """
    # Extract config values
    ref_h = config["reference_resolution"]["height"]
    target_height = config["processing"]["target_height"]
    threshold = threshold_override if threshold_override is not None else config["black_detection"]["brightness_threshold"]
    roi_zones = config["black_detection"]["roi_zones"]

    # Warn if source aspect ratio differs from reference resolution
    src_w, src_h = get_video_info(video_path)
    ref_w = config["reference_resolution"]["width"]
    source_aspect = src_w / src_h
    ref_aspect = ref_w / ref_h
    if abs(source_aspect - ref_aspect) > 0.01:
        print(
            f"Warning: Source aspect ratio ({src_w}x{src_h} = {source_aspect:.3f}) "
            f"differs from reference ({ref_w}x{ref_h} = {ref_aspect:.3f}). "
            "ROI positions may be inaccurate.",
            file=sys.stderr,
        )

    # Scale ROIs from reference resolution to processing resolution
    ref_scale = target_height / ref_h
    scaled_rois = [scale_roi(roi, ref_scale) for roi in roi_zones]

    os.makedirs(output_dir, exist_ok=True)

    range_start, range_end = time_range
    frame_count = 0
    frame_seq = 0

    print(f"Processing: {video_path}")
    print(f"Config: threshold={threshold}, target_height={target_height}px")
    print(f"Range: {range_start:.1f}s - {range_end if range_end != float('inf') else 'end'}s")
    print(f"ROI zones: {[r['name'] for r in roi_zones]}")
    print()

    for frame, timestamp in extract_iframes_scaled(video_path, target_height):
        if timestamp < range_start:
            continue
        if timestamp > range_end:
            break

        frame_count += 1
        frame_seq += 1
        gray = to_grayscale(frame)

        # Analyze each ROI
        roi_results = []
        for sroi in scaled_rois:
            region = extract_roi(gray, sroi)
            mean_val = float(np.mean(region))
            black = is_black(region, threshold)
            roi_results.append({
                "name": sroi["name"],
                "roi": sroi,
                "mean": mean_val,
                "black": black,
            })

        # Console output
        parts = []
        for r in roi_results:
            tag = "BLACK" if r["black"] else "FAIL"
            parts.append(f"{r['name']}: {r['mean']:.1f} {tag}")
        print(f"  {timestamp:.1f}s | {' | '.join(parts)}")

        failing = [r["name"] for r in roi_results if not r["black"]]
        if not failing:
            print(f"  -> ALL BLACK")
        else:
            print(f"  -> NOT ALL BLACK ({', '.join(failing)})")

        # Annotated frame export — draw on a writable copy of the BGR frame
        frame = frame.copy()
        for r in roi_results:
            x, y = r["roi"]["x"], r["roi"]["y"]
            w, h = r["roi"]["width"], r["roi"]["height"]
            color = (0, 255, 0) if r["black"] else (0, 0, 255)
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
            label_y = y + 12 if y < 15 else y - 5
            cv2.putText(frame, f"{r['name']}: {r['mean']:.1f}", (x, label_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1)

        # Timestamp label
        cv2.putText(frame, f"{timestamp:.1f}s", (5, 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

        out_path = os.path.join(output_dir, f"debug_{frame_seq:03d}_{timestamp:.1f}s.png")
        if not cv2.imwrite(out_path, frame):
            print(f"Warning: Failed to write {out_path}", file=sys.stderr)

    return frame_count


def main():
    parser = argparse.ArgumentParser(
        description="Diagnostic tool for inspecting per-ROI brightness values in black screen detection."
    )
    parser.add_argument(
        "video",
        help="Path to the input video file",
    )
    parser.add_argument(
        "--range",
        default="0:15",
        help="Time range to analyze as START:END in seconds (default: 0:15)",
    )
    parser.add_argument(
        "-o", "--output-dir",
        default="./output/debug",
        help="Output directory for annotated PNGs (default: ./output/debug)",
    )
    parser.add_argument(
        "-c", "--config",
        default="config/config.yaml",
        help="Path to config file (default: config/config.yaml)",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=None,
        help="Brightness threshold override (0-255)",
    )
    args = parser.parse_args()

    # Validate input video exists
    if not os.path.isfile(args.video):
        print(f"Error: Video file not found: {args.video}", file=sys.stderr)
        sys.exit(1)

    # Validate config exists
    if not os.path.isfile(args.config):
        print(f"Error: Config file not found: {args.config}", file=sys.stderr)
        sys.exit(1)

    config = load_config(args.config)

    try:
        time_range = parse_range(args.range)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        frame_count = run(args.video, args.output_dir, config, time_range, args.threshold)
    except Exception as e:
        print(f"Error during processing: {e}", file=sys.stderr)
        sys.exit(1)

    print()
    if frame_count == 0:
        print("No frames found in range.")
    else:
        print("=" * 50)
        print(f"Summary:")
        print(f"  Frames analyzed: {frame_count}")
        print(f"  Range: {time_range[0]:.1f}s - {time_range[1] if time_range[1] != float('inf') else 'end'}s")
        print(f"  Output directory: {os.path.abspath(args.output_dir)}")
        print("=" * 50)


if __name__ == "__main__":
    main()
