"""Game Detector — CLI tool for detecting game rounds and capturing score screens.

Uses kda ROI white-pixel detection to find game start/end boundaries, then
captures the score screen by extracting a frame at a fixed offset after the last
confirmed in-game kda frame. Combines the reliability of kda-based detection
with automatic score screen capture.

Usage:
    python tools/game_detector.py <video_path> [-o OUTPUT_DIR] [-c CONFIG] [--profile]
"""

import argparse
import os
import subprocess
import sys
import time
import traceback

# Use absolute path to avoid shadowing stdlib modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cv2

from utils.config import load_config
from utils.format import format_timestamp
from utils.video import (
    extract_frame_at_timestamp,
    extract_iframes_scaled,
    get_video_info,
)
from utils.image import scale_roi, extract_roi, has_white_pixels


def run(video_path, output_dir, config, profile=False):
    """Run game detection (start/end/score) on a video file.

    Args:
        video_path: Path to the input video.
        output_dir: Directory to save extracted frames.
        config: Parsed YAML config dict.
        profile: If True, collect per-phase timing data.

    Returns:
        tuple: (exported_list, frame_count, profile_stats) where
               exported_list is a list of dicts with keys 'filename', 'type'
               ('start', 'end', or 'score'), and 'timestamp', frame_count is
               the total I-frames processed, profile_stats is a dict of timing
               data (or None when profiling is off).
    """
    if profile:
        wall_start = time.perf_counter()
        profile_stats = {
            "roi_check": 0.0,
            "fullres_extract": 0.0,
        }
        frames_skipped = 0
    else:
        profile_stats = None

    # Extract config values
    ref_h = config["reference_resolution"]["height"]
    ref_w = config["reference_resolution"]["width"]
    target_height = config["processing"]["target_height"]
    pd_config = config["points_detection"]
    sat_max = pd_config["sat_max"]
    val_min = pd_config["val_min"]
    min_ratio = pd_config["min_ratio"]
    skip_duration = pd_config["skip_duration"]
    start_confirm_frames = pd_config["start_confirm_frames"]
    end_confirm_frames = pd_config["end_confirm_frames"]
    score_offset = pd_config["score_offset"]

    # Find the KDA ROI from config
    roi_zones = config["black_detection"]["roi_zones"]
    kda_roi_raw = None
    for roi in roi_zones:
        if roi["name"] == "kda":
            kda_roi_raw = roi
            break
    if kda_roi_raw is None:
        raise ValueError(
            f"Config must define a 'kda' ROI zone. "
            f"Found: {[r['name'] for r in roi_zones]}"
        )

    # Aspect ratio warning
    src_w, src_h = get_video_info(video_path)
    source_aspect = src_w / src_h
    ref_aspect = ref_w / ref_h
    if abs(source_aspect - ref_aspect) > 0.01:
        print(
            f"Warning: Source aspect ratio ({src_w}x{src_h} = {source_aspect:.3f}) "
            f"differs from reference ({ref_w}x{ref_h} = {ref_aspect:.3f}). "
            "ROI positions may be inaccurate.",
            file=sys.stderr,
        )

    # Scale ROI from reference resolution to processing resolution
    ref_scale = target_height / ref_h
    kda_roi = scale_roi(kda_roi_raw, ref_scale)

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    exported = []
    extraction_requests = []
    prev_timestamp = None
    skip_until = -1.0
    detection_seq = 0

    # State machine: two states
    # "not_in_game" (initial) — looking for white (start transition)
    # "in_game" — looking for no white (end transition)
    state = "not_in_game"
    start_confirm_count = 0
    start_candidate_timestamp = None
    end_confirm_count = 0
    end_candidate_timestamp = None
    last_in_game_timestamp = None  # tracks last frame where white was detected in-game

    print(f"Processing: {video_path}")
    print(f"Config: sat_max={sat_max}, val_min={val_min}, min_ratio={min_ratio}, "
          f"skip={skip_duration}s, start_confirm={start_confirm_frames}, "
          f"end_confirm={end_confirm_frames}, score_offset={score_offset}s, "
          f"target_height={target_height}px")
    print(f"ROI: kda ({kda_roi_raw['x']},{kda_roi_raw['y']} "
          f"{kda_roi_raw['width']}x{kda_roi_raw['height']} @ {ref_w}x{ref_h})")
    print()

    frame_count = 0
    for frame, timestamp in extract_iframes_scaled(video_path, target_height, profile_stats=profile_stats):
        frame_count += 1

        # Skip logic — after an end detection, skip frames within skip_duration
        if timestamp < skip_until:
            if profile_stats is not None:
                frames_skipped += 1
            prev_timestamp = timestamp
            continue

        # Extract KDA ROI (BGR, no grayscale needed)
        if profile_stats is not None:
            t0 = time.perf_counter()
        region = extract_roi(frame, kda_roi)
        white_detected = has_white_pixels(region, sat_max, val_min, min_ratio)
        if profile_stats is not None:
            profile_stats["roi_check"] += time.perf_counter() - t0

        # --- State machine ---
        if state == "not_in_game":
            if white_detected:
                # Potential start — apply confirmation logic
                start_confirm_count += 1
                if start_candidate_timestamp is None:
                    start_candidate_timestamp = timestamp
                if start_confirm_count >= start_confirm_frames:
                    # Confirmed start transition
                    confirmed_ts = start_candidate_timestamp
                    detection_seq += 1
                    ts_str = format_timestamp(confirmed_ts)
                    fname = f"{ts_str}_start_{detection_seq:03d}.png"
                    extraction_requests.append({
                        "timestamp": confirmed_ts,
                        "type": "start",
                        "filename": fname,
                    })
                    state = "in_game"
                    last_in_game_timestamp = timestamp
                    start_confirm_count = 0
                    start_candidate_timestamp = None
                    end_confirm_count = 0
                    end_candidate_timestamp = None
                    print(f"  START at {confirmed_ts:.1f}s")
            else:
                # Reset confirmation counter
                start_confirm_count = 0
                start_candidate_timestamp = None

        elif state == "in_game":
            if white_detected:
                # White still present — update last known in-game timestamp
                last_in_game_timestamp = timestamp
                end_confirm_count = 0
                end_candidate_timestamp = None
            else:
                # Potential end — apply confirmation logic
                end_confirm_count += 1
                if end_candidate_timestamp is None:
                    end_candidate_timestamp = prev_timestamp if prev_timestamp is not None else timestamp
                if end_confirm_count >= end_confirm_frames:
                    # Confirmed end transition
                    confirmed_end_ts = end_candidate_timestamp
                    detection_seq += 1
                    ts_str = format_timestamp(confirmed_end_ts)
                    fname = f"{ts_str}_end_{detection_seq:03d}.png"
                    extraction_requests.append({
                        "timestamp": confirmed_end_ts,
                        "type": "end",
                        "filename": fname,
                    })

                    # Queue score screen extraction at last_in_game_timestamp + score_offset
                    if last_in_game_timestamp is not None:
                        score_ts = last_in_game_timestamp + score_offset
                        detection_seq += 1
                        score_ts_str = format_timestamp(score_ts)
                        score_fname = f"{score_ts_str}_score_{detection_seq:03d}.png"
                        extraction_requests.append({
                            "timestamp": score_ts,
                            "type": "score",
                            "filename": score_fname,
                        })
                        print(f"  END at {confirmed_end_ts:.1f}s  |  SCORE at {score_ts:.1f}s")
                    else:
                        print(f"  END at {confirmed_end_ts:.1f}s  |  SCORE skipped (no in-game timestamp)")

                    state = "not_in_game"
                    skip_until = timestamp + skip_duration
                    start_confirm_count = 0
                    start_candidate_timestamp = None
                    end_confirm_count = 0
                    end_candidate_timestamp = None
                    last_in_game_timestamp = None

        prev_timestamp = timestamp

    # End-of-video warnings
    if frame_count == 0:
        print("Warning: No keyframes found in video.", file=sys.stderr)
    if state == "in_game":
        print("Warning: Video ended while in-game — last round has no end transition. "
              "No score screen exported for incomplete round.", file=sys.stderr)
    if start_confirm_count > 0:
        print(f"Warning: Video ended with {start_confirm_count} partial start confirmation frame(s) "
              f"(needed {start_confirm_frames}) — potential start discarded.", file=sys.stderr)
    if end_confirm_count > 0:
        print(f"Warning: Video ended with {end_confirm_count} partial end confirmation frame(s) "
              f"(needed {end_confirm_frames}) — potential end discarded.", file=sys.stderr)

    # --- Post-detection batch extraction phase ---
    if extraction_requests:
        # Sort by timestamp for sequential seeking (score frames interleave with end frames)
        extraction_requests.sort(key=lambda r: r["timestamp"])
        if profile_stats is not None:
            t0 = time.perf_counter()
        print(f"\n  Extracting {len(extraction_requests)} full-resolution frames...")
        for i, req in enumerate(extraction_requests, 1):
            if req["type"] == "score":
                try:
                    fullres_frame = extract_frame_at_timestamp(video_path, req["timestamp"], src_w, src_h)
                except (RuntimeError, subprocess.CalledProcessError) as e:
                    print(f"  Warning: Could not extract score frame at {req['timestamp']:.1f}s "
                          f"(may exceed video duration): {e}", file=sys.stderr)
                    continue
            else:
                fullres_frame = extract_frame_at_timestamp(video_path, req["timestamp"], src_w, src_h)
            out_path = os.path.join(output_dir, req["filename"])
            cv2.imwrite(out_path, fullres_frame)
            exported.append({
                "filename": req["filename"],
                "type": req["type"],
                "timestamp": req["timestamp"],
            })
            print(f"  {req['type'].upper()} -> exported {req['filename']} "
                  f"(frame at {req['timestamp']:.1f}s) [{i}/{len(extraction_requests)}]")
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

    phase_divisors = {
        "ffprobe_info": None,
        "ffmpeg_read": total_frames,
        "roi_check": processed,
        "fullres_extract": None,
    }

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
        description="Detect game rounds via kda ROI and capture score screens."
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
        "--profile",
        action="store_true",
        help="Print per-phase timing breakdown after processing",
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

    # Resolve output directory — CLI arg > config default
    output_dir = args.output_dir if args.output_dir else config["output"]["default_dir"]

    # Create video-named subfolder inside output directory
    video_stem = os.path.splitext(os.path.basename(args.video))[0]
    output_dir = os.path.join(output_dir, video_stem)

    try:
        exported, frame_count, profile_stats = run(
            args.video, output_dir, config, profile=args.profile,
        )
    except Exception as e:
        print(f"Error during processing: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)

    # Print summary
    print()
    print("=" * 50)
    print(f"Summary:")
    print(f"  Frames processed: {frame_count}")
    start_count = sum(1 for e in exported if e["type"] == "start")
    end_count = sum(1 for e in exported if e["type"] == "end")
    score_count = sum(1 for e in exported if e["type"] == "score")
    print(f"  Game starts detected: {start_count}")
    print(f"  Game ends detected: {end_count}")
    print(f"  Score screens captured: {score_count}")
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
