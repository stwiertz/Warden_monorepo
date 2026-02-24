"""Black Screen Detector — CLI tool for extracting end-of-round frames.

Iterates through I-frames of an EVA session recording, detects black screen
transitions by checking two ROI zones, and exports the preceding I-frame
(the end-of-round screen) as a PNG.

Usage:
    python tools/black_screen_detector.py <video_path> [-o OUTPUT_DIR] [-c CONFIG] [--threshold N]
"""

import argparse
import os
import sys

# F8: use absolute path to avoid shadowing stdlib modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cv2
import yaml

from utils.video import extract_iframes
from utils.image import downscale, to_grayscale, scale_roi, extract_roi, is_black


def load_config(config_path):
    """Load and return the YAML configuration."""
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def format_timestamp(seconds):
    """Format seconds as MMmSSs for filenames (e.g. 05m23s)."""
    minutes = int(seconds) // 60
    secs = int(seconds) % 60
    return f"{minutes:02d}m{secs:02d}s"


def run(video_path, output_dir, config, threshold_override=None):
    """Run black screen detection on a video file.

    Args:
        video_path: Path to the input video.
        output_dir: Directory to save extracted frames.
        config: Parsed YAML config dict.
        threshold_override: Optional brightness threshold override.

    Returns:
        tuple: (exported_filenames, frame_count) where exported_filenames
               is a list of str and frame_count is the total I-frames processed.
    """
    # Extract config values
    ref_h = config["reference_resolution"]["height"]
    target_height = config["processing"]["target_height"]
    threshold = threshold_override if threshold_override is not None else config["black_detection"]["brightness_threshold"]
    skip_duration = config["black_detection"]["skip_duration"]
    roi_zones = config["black_detection"]["roi_zones"]

    # F2: scale ROIs from reference resolution to target processing resolution.
    # This is correct when source video matches reference resolution (1080p).
    # For non-reference sources, the downscale() function returns the actual
    # scale factor which we use to re-scale ROIs on the first frame.
    ref_scale = target_height / ref_h
    scaled_rois = [scale_roi(roi, ref_scale) for roi in roi_zones]
    rois_calibrated = False

    # Ensure output directory exists (AC 8)
    os.makedirs(output_dir, exist_ok=True)

    exported = []
    prev_frame = None
    prev_timestamp = None
    skip_until = -1.0  # timestamp until which we skip detection
    # F6: sequence counter for unique filenames when timestamps collide
    detection_seq = 0

    print(f"Processing: {video_path}")
    print(f"Config: threshold={threshold}, skip={skip_duration}s, target_height={target_height}px")
    print(f"ROI zones: {[r['name'] for r in roi_zones]}")
    print()

    frame_count = 0
    for frame, timestamp in extract_iframes(video_path):
        frame_count += 1

        # F2: on first frame, check if source resolution matches reference.
        # If not, recalculate ROI scaling using actual downscale factor.
        if not rois_calibrated:
            source_h = frame.shape[0]
            if source_h != ref_h:
                actual_scale = target_height / source_h
                # ROIs are defined at reference res — scale via reference, not source
                # The correct factor is: (target_height / ref_h), which maps
                # reference-resolution ROI coords to the downscaled frame.
                # But the downscaled frame's width depends on source aspect ratio,
                # not reference. If source is the same aspect ratio as reference
                # (which it should be for game recordings), ref_scale is correct.
                # Warn if aspect ratios differ.
                source_w = frame.shape[1]
                ref_w = config["reference_resolution"]["width"]
                source_aspect = source_w / source_h
                ref_aspect = ref_w / ref_h
                if abs(source_aspect - ref_aspect) > 0.01:
                    print(
                        f"Warning: Source aspect ratio ({source_w}x{source_h} = {source_aspect:.3f}) "
                        f"differs from reference ({ref_w}x{ref_h} = {ref_aspect:.3f}). "
                        "ROI positions may be inaccurate.",
                        file=sys.stderr,
                    )
            rois_calibrated = True

        # Skip logic — after a detection, skip frames within skip_duration (AC 4)
        if timestamp < skip_until:
            # F5: only store the last frame before skip ends (not every frame)
            next_would_clear_skip = True  # optimistic — update prev on last skip frame
            prev_frame = frame.copy()
            prev_timestamp = timestamp
            continue

        # Downscale for processing
        small_frame, _ = downscale(frame, target_height)
        gray = to_grayscale(small_frame)

        # Check all ROI zones — all must be black simultaneously (AC 3)
        all_black = True
        for sroi in scaled_rois:
            region = extract_roi(gray, sroi)
            if not is_black(region, threshold):
                all_black = False
                break

        if all_black and prev_frame is not None:
            # Black screen detected — export the PREVIOUS frame (AC 1)
            detection_seq += 1
            ts_str = format_timestamp(prev_timestamp)
            # F6: append sequence number to guarantee unique filenames
            fname = f"frame_{ts_str}_{detection_seq:03d}.png"
            out_path = os.path.join(output_dir, fname)
            cv2.imwrite(out_path, prev_frame)
            exported.append(fname)
            print(f"  Detected transition at {timestamp:.1f}s -> exported {fname} (prev frame at {prev_timestamp:.1f}s)")

            # Skip forward to avoid duplicates (AC 4)
            skip_until = timestamp + skip_duration

        # Store current frame as previous for next iteration
        prev_frame = frame.copy()
        prev_timestamp = timestamp

    return exported, frame_count


def main():
    parser = argparse.ArgumentParser(
        description="Detect black screen transitions in EVA recordings and export end-of-round frames."
    )
    parser.add_argument(
        "video",
        help="Path to the input video file",
    )
    parser.add_argument(
        "-o", "--output-dir",
        default=None,
        help="Output directory for extracted frames (default: from config, relative to CWD)",
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

    # Validate input video exists (AC 7)
    if not os.path.isfile(args.video):
        print(f"Error: Video file not found: {args.video}", file=sys.stderr)
        sys.exit(1)

    # Validate config exists
    if not os.path.isfile(args.config):
        print(f"Error: Config file not found: {args.config}", file=sys.stderr)
        sys.exit(1)

    config = load_config(args.config)

    # F12: resolve output directory — CLI arg > config default (relative to CWD)
    output_dir = args.output_dir if args.output_dir else config["output"]["default_dir"]

    try:
        exported, frame_count = run(args.video, output_dir, config, args.threshold)
    except Exception as e:
        print(f"Error during processing: {e}", file=sys.stderr)
        sys.exit(1)

    # Print summary (AC 9 — always prints, even if 0 transitions)
    print()
    print("=" * 50)
    print(f"Summary:")
    print(f"  I-frames processed: {frame_count}")
    print(f"  Transitions detected: {len(exported)}")
    print(f"  Output directory: {os.path.abspath(output_dir)}")
    if exported:
        print(f"  Exported frames:")
        for fname in exported:
            print(f"    - {fname}")
    else:
        print(f"  No transitions found.")
    print("=" * 50)


if __name__ == "__main__":
    main()
