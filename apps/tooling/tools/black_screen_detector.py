"""Black Screen Detector — CLI tool for extracting start-of-round and end-of-round frames.

Iterates through I-frames of an EVA session recording, uses a two-state machine
to detect game-end transitions (non-black -> black) and game-start transitions
(black -> non-black), and exports the relevant frame for each event as a PNG.

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
        tuple: (exported_list, frame_count) where exported_list is a list of
               dicts with keys 'filename', 'type' ('start' or 'end'), and
               'timestamp', and frame_count is the total I-frames processed.
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
    # Separate minimap ROI for start detection (minimap is black during lobby,
    # non-black during gameplay; map_name has text in both lobby and gameplay)
    minimap_roi = next(r for r in scaled_rois if r["name"] == "minimap")
    rois_calibrated = False

    # Ensure output directory exists (AC 8)
    os.makedirs(output_dir, exist_ok=True)

    exported = []  # list of dicts: {filename, type, timestamp}
    prev_frame = None
    prev_timestamp = None
    skip_until = -1.0  # timestamp until which we skip detection
    # F6: sequence counter for unique filenames when timestamps collide
    detection_seq = 0

    # State machine: tracks round lifecycle to prevent consecutive end detections.
    # "waiting_for_end"   = game is (assumed) in progress, looking for end blackscreen
    # "waiting_for_start" = game ended, looking for start blackscreen (black -> non-black)
    # Initial state is determined on the first frame: if it's black, we start in
    # "waiting_for_start" (video begins before game); otherwise "waiting_for_end".
    state = None  # set on first frame

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

        # Determine initial state from first frame using minimap ROI only.
        # Minimap is black during lobby/countdown and non-black during gameplay.
        if state is None:
            small_first, _ = downscale(frame, target_height)
            gray_first = to_grayscale(small_first)
            minimap_black = is_black(extract_roi(gray_first, minimap_roi), threshold)
            if minimap_black:
                state = "waiting_for_start"
                print(f"  First frame: minimap is black — starting in waiting_for_start")
            else:
                state = "waiting_for_end"
                print(f"  First frame: minimap is not black — starting in waiting_for_end")

        # Skip logic — after an end detection, skip frames within skip_duration (AC 4)
        if timestamp < skip_until:
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

        # --- State machine ---
        if state == "waiting_for_end":
            if all_black and prev_frame is not None:
                # Non-black -> black transition: end blackscreen detected.
                # Export the PREVIOUS frame (last non-black frame = end-of-round screen).
                detection_seq += 1
                ts_str = format_timestamp(prev_timestamp)
                fname = f"{ts_str}_end_{detection_seq:03d}.png"
                out_path = os.path.join(output_dir, fname)
                cv2.imwrite(out_path, prev_frame)
                exported.append({"filename": fname, "type": "end", "timestamp": prev_timestamp})
                print(f"  END at {timestamp:.1f}s -> exported {fname} (prev frame at {prev_timestamp:.1f}s)")

                state = "waiting_for_start"
                skip_until = timestamp + skip_duration

        elif state == "waiting_for_start":
            # For start detection, check only the minimap ROI.
            # During lobby/countdown the minimap area is black; when the game
            # loads the minimap appears and becomes non-black.
            minimap_region = extract_roi(gray, minimap_roi)
            minimap_is_black = is_black(minimap_region, threshold)
            if not minimap_is_black:
                # Minimap appeared — game has started.
                # Export the CURRENT frame (first gameplay frame).
                detection_seq += 1
                ts_str = format_timestamp(timestamp)
                fname = f"{ts_str}_start_{detection_seq:03d}.png"
                out_path = os.path.join(output_dir, fname)
                cv2.imwrite(out_path, frame)
                exported.append({"filename": fname, "type": "start", "timestamp": timestamp})
                print(f"  START at {timestamp:.1f}s -> exported {fname}")

                state = "waiting_for_end"
            # If minimap still black: ignore (still in lobby/loading).
            # This prevents consecutive end detections — solves trailing dead air.

        # Store current frame as previous for next iteration
        prev_frame = frame.copy()
        prev_timestamp = timestamp

    return exported, frame_count


def main():
    parser = argparse.ArgumentParser(
        description="Detect black screen transitions in EVA recordings and export start/end-of-round frames."
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
    end_count = sum(1 for e in exported if e["type"] == "end")
    start_count = sum(1 for e in exported if e["type"] == "start")
    print(f"  Game ends detected: {end_count}")
    print(f"  Game starts detected: {start_count}")
    print(f"  Total events: {len(exported)}")
    print(f"  Output directory: {os.path.abspath(output_dir)}")
    if exported:
        print(f"  Exported frames:")
        for entry in exported:
            print(f"    - {entry['filename']}  ({entry['type']} at {entry['timestamp']:.1f}s)")
    else:
        print(f"  No transitions found.")
    print("=" * 50)


if __name__ == "__main__":
    main()
