"""Black Screen Detector — CLI tool for extracting start-of-round and end-of-round frames.

Iterates through I-frames of an EVA session recording, uses a three-state machine
(undetermined -> waiting_for_end / waiting_for_start) to detect game-end transitions
(non-black -> black) and game-start transitions (black -> non-black), and exports
the relevant frame for each event as a PNG.

Usage:
    python tools/black_screen_detector.py <video_path> [-o OUTPUT_DIR] [-c CONFIG] [--threshold N]
"""

import argparse
import os
import sys
import time

# F8: use absolute path to avoid shadowing stdlib modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cv2
import yaml

from utils.video import extract_iframes_scaled, extract_frame_at_timestamp, get_video_info
from utils.image import to_grayscale, scale_roi, extract_roi, is_black


def load_config(config_path):
    """Load and return the YAML configuration."""
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def format_timestamp(seconds):
    """Format seconds as MMmSSs for filenames (e.g. 05m23s)."""
    minutes = int(seconds) // 60
    secs = int(seconds) % 60
    return f"{minutes:02d}m{secs:02d}s"


def run(video_path, output_dir, config, threshold_override=None, profile=False):
    """Run black screen detection on a video file.

    Args:
        video_path: Path to the input video.
        output_dir: Directory to save extracted frames.
        config: Parsed YAML config dict.
        threshold_override: Optional brightness threshold override.
        profile: If True, collect per-phase timing data.

    Returns:
        tuple: (exported_list, frame_count, profile_stats) where exported_list
               is a list of dicts with keys 'filename', 'type' ('start' or
               'end'), and 'timestamp', frame_count is the total I-frames
               processed, and profile_stats is a dict of timing data (or None
               when profiling is off).
    """
    if profile:
        wall_start = time.perf_counter()
        profile_stats = {
            "grayscale": 0.0,
            "roi_check": 0.0,
            "fullres_extract": 0.0,
        }
        frames_skipped = 0
    else:
        profile_stats = None

    # Extract config values
    ref_h = config["reference_resolution"]["height"]
    target_height = config["processing"]["target_height"]
    threshold = threshold_override if threshold_override is not None else config["black_detection"]["brightness_threshold"]
    skip_duration = config["black_detection"]["skip_duration"]
    roi_zones = config["black_detection"]["roi_zones"]

    # F2: warn if source aspect ratio differs from reference resolution.
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

    # Scale ROIs from reference resolution to target processing resolution.
    ref_scale = target_height / ref_h
    scaled_rois = [scale_roi(roi, ref_scale) for roi in roi_zones]
    # Separate minimap and vertical ROIs for start detection (both are black
    # during lobby, non-black during gameplay; map_name has text in both)
    try:
        minimap_roi = next(r for r in scaled_rois if r["name"] == "minimap")
        vertical_roi = next(r for r in scaled_rois if r["name"] == "vertical")
    except StopIteration:
        roi_names = [r["name"] for r in scaled_rois]
        raise ValueError(
            f"Config must define 'minimap' and 'vertical' ROI zones. Found: {roi_names}"
        )

    # Ensure output directory exists (AC 8)
    os.makedirs(output_dir, exist_ok=True)

    exported = []  # list of dicts: {filename, type, timestamp}
    extraction_requests = []  # deferred full-res extraction requests
    prev_timestamp = None
    skip_until = -1.0  # timestamp until which we skip detection
    # F6: sequence counter for unique filenames when timestamps collide
    detection_seq = 0

    # State machine: tracks round lifecycle to prevent consecutive end detections.
    # "undetermined"      = initial state, watching for the first transition of either type
    # "waiting_for_end"   = game is in progress, looking for end blackscreen
    # "waiting_for_start" = game ended, looking for start blackscreen (black -> non-black)
    state = "undetermined"
    prev_is_end_loading = None  # tracks previous frame's end-loading status for undetermined state
    prev_start_rois_black = None  # tracks previous frame's start-ROIs status for undetermined state

    print(f"Processing: {video_path}")
    print(f"Config: threshold={threshold}, skip={skip_duration}s, target_height={target_height}px")
    print(f"ROI zones: {[r['name'] for r in roi_zones]}")
    print()

    frame_count = 0
    for frame, timestamp in extract_iframes_scaled(video_path, target_height, profile_stats=profile_stats):
        frame_count += 1

        # Skip logic — after an end detection, skip frames within skip_duration (AC 4)
        if timestamp < skip_until:
            if profile_stats is not None:
                frames_skipped += 1
            prev_timestamp = timestamp
            continue

        # Frames arrive pre-scaled — apply grayscale directly (once per frame)
        if profile_stats is not None:
            t0 = time.perf_counter()
        gray = to_grayscale(frame)
        if profile_stats is not None:
            profile_stats["grayscale"] += time.perf_counter() - t0

        # Check all ROI zones — all must be black simultaneously (AC 3)
        if profile_stats is not None:
            t0 = time.perf_counter()
        is_end_loading = True
        for sroi in scaled_rois:
            region = extract_roi(gray, sroi)
            if not is_black(region, threshold):
                is_end_loading = False
                break
        # Extract minimap+vertical ROIs (used by undetermined and waiting_for_start)
        minimap_region = extract_roi(gray, minimap_roi)
        vertical_region = extract_roi(gray, vertical_roi)
        if profile_stats is not None:
            profile_stats["roi_check"] += time.perf_counter() - t0

        # --- State machine ---
        if state == "undetermined":
            # start_rois_black: both minimap+vertical black (lobby screen).
            # "not start_rois_black" means at least one is non-black (De Morgan's),
            # so the inner guard below must verify BOTH are individually non-black.
            start_rois_black = is_black(minimap_region, threshold) and is_black(vertical_region, threshold)
            if prev_is_end_loading is None:
                # First frame — record state, do not assume anything
                prev_is_end_loading = is_end_loading
                prev_start_rois_black = start_rois_black
                print("  First frame: recording state")
                prev_timestamp = timestamp
                continue

            # endLoading detection: non-end-loading -> end-loading transition
            if not prev_is_end_loading and is_end_loading and prev_timestamp is not None:
                detection_seq += 1
                ts_str = format_timestamp(prev_timestamp)
                fname = f"{ts_str}_end_{detection_seq:03d}.png"
                extraction_requests.append({"timestamp": prev_timestamp, "type": "end", "filename": fname})
                state = "waiting_for_start"
                skip_until = timestamp + skip_duration
                print(f"  First transition: endLoading at {prev_timestamp:.1f}s")

            # startLoading detection: start-ROIs black -> non-black transition
            elif prev_start_rois_black and not start_rois_black:
                if not is_black(minimap_region, threshold) and not is_black(vertical_region, threshold):
                    detection_seq += 1
                    ts_str = format_timestamp(timestamp)
                    fname = f"{ts_str}_start_{detection_seq:03d}.png"
                    extraction_requests.append({"timestamp": timestamp, "type": "start", "filename": fname})
                    state = "waiting_for_end"
                    print(f"  First transition: startLoading at {timestamp:.1f}s")

            prev_is_end_loading = is_end_loading
            prev_start_rois_black = start_rois_black

        elif state == "waiting_for_end":
            if is_end_loading and prev_timestamp is not None:
                # Non-black -> black transition: end blackscreen detected.
                # Defer export — record the PREVIOUS timestamp for batch extraction.
                detection_seq += 1
                ts_str = format_timestamp(prev_timestamp)
                fname = f"{ts_str}_end_{detection_seq:03d}.png"
                extraction_requests.append({"timestamp": prev_timestamp, "type": "end", "filename": fname})

                state = "waiting_for_start"
                skip_until = timestamp + skip_duration

        elif state == "waiting_for_start":
            # Reuse minimap_region/vertical_region extracted above.
            start_rois_non_black = (
                not is_black(minimap_region, threshold)
                and not is_black(vertical_region, threshold)
            )
            if start_rois_non_black:
                # Both minimap and vertical are non-black — game has started.
                # Defer export — record the CURRENT timestamp for batch extraction.
                detection_seq += 1
                ts_str = format_timestamp(timestamp)
                fname = f"{ts_str}_start_{detection_seq:03d}.png"
                extraction_requests.append({"timestamp": timestamp, "type": "start", "filename": fname})

                state = "waiting_for_end"

        prev_timestamp = timestamp

    if frame_count == 0:
        print("Warning: No keyframes found in video.", file=sys.stderr)

    # --- Post-detection batch extraction phase ---
    if extraction_requests:
        if profile_stats is not None:
            t0 = time.perf_counter()
        print(f"\n  Extracting {len(extraction_requests)} full-resolution frames...")
        for i, req in enumerate(extraction_requests, 1):
            fullres_frame = extract_frame_at_timestamp(video_path, req["timestamp"], src_w, src_h)
            out_path = os.path.join(output_dir, req["filename"])
            cv2.imwrite(out_path, fullres_frame)
            exported.append({"filename": req["filename"], "type": req["type"], "timestamp": req["timestamp"]})
            if req["type"] == "end":
                print(f"  END -> exported {req['filename']} (frame at {req['timestamp']:.1f}s) [{i}/{len(extraction_requests)}]")
            else:
                print(f"  START -> exported {req['filename']} (frame at {req['timestamp']:.1f}s) [{i}/{len(extraction_requests)}]")
        if profile_stats is not None:
            profile_stats["fullres_extract"] = time.perf_counter() - t0

    if profile_stats is not None:
        wall_end = time.perf_counter()
        profile_stats["wall_time"] = wall_end - wall_start
        profile_stats["frames_total"] = frame_count
        profile_stats["frames_skipped"] = frames_skipped
        profile_stats["frames_processed"] = frame_count - frames_skipped

    return exported, frame_count, profile_stats


def _print_profile_report(ps):
    """Print a formatted profiling report from collected timing data."""
    wall = ps["wall_time"]
    total_frames = ps["frames_total"]
    processed = ps["frames_processed"]
    skipped = ps["frames_skipped"]

    # Phases to report, with their per-frame divisor (None = one-time, show dash)
    phase_divisors = {
        "ffprobe_info": None,
        "ffmpeg_read": total_frames,
        "grayscale": processed,
        "roi_check": processed,
        "fullres_extract": None,
    }

    # Build rows sorted by total time descending
    rows = []
    accounted = 0.0
    for phase, divisor in phase_divisors.items():
        total_s = ps.get(phase, 0.0)
        accounted += total_s
        pct = (total_s / wall * 100) if wall > 0 else 0.0
        if divisor and divisor > 0:
            avg_ms = (total_s / divisor) * 1000
            avg_str = f"{avg_ms:>10.2f}"
        else:
            avg_str = "         \u2014"
        rows.append((phase, total_s, avg_str, pct))

    rows.sort(key=lambda r: r[1], reverse=True)

    unaccounted = wall - accounted
    unaccounted_pct = (unaccounted / wall * 100) if wall > 0 else 0.0

    print()
    print("PROFILE REPORT")
    print("=" * 50)
    print(f"Wall time:       {wall:.2f}s")
    print(f"Frames total:    {total_frames} ({processed} processed, {skipped} skipped)")
    print()

    sep = "\u2500"
    print(f"{'Phase':<19s}  {'Total (s)':>10s}  {'Avg/frame (ms)':>14s}  {'   %':>5s}")
    print(f"{sep * 19}  {sep * 10}  {sep * 14}  {sep * 5}")

    for phase, total_s, avg_str, pct in rows:
        print(f"{phase:<19s}  {total_s:>10.2f}  {avg_str:>14s}  {pct:>4.1f}%")

    print(f"{sep * 19}  {sep * 10}  {sep * 14}  {sep * 5}")
    acc_pct = (accounted / wall * 100) if wall > 0 else 0
    print(f"{'Accounted:':<19s}  {accounted:>10.2f}  {'':>14s}  {acc_pct:>4.1f}%")
    print(f"{'Unaccounted:':<19s}  {unaccounted:>10.2f}  {'':>14s}  {unaccounted_pct:>4.1f}%")


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
    parser.add_argument(
        "--profile",
        action="store_true",
        help="Print per-phase timing breakdown after processing",
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
        exported, frame_count, profile_stats = run(
            args.video, output_dir, config, args.threshold, profile=args.profile
        )
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

    # Print profiling report if --profile was passed
    if profile_stats is not None:
        _print_profile_report(profile_stats)


if __name__ == "__main__":
    main()
