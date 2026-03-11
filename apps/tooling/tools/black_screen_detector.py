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

from utils.config import load_config
from utils.video import (
    extract_frame_at_timestamp,
    extract_frames_at_interval,
    extract_iframes_scaled,
    get_gop_interval,
    get_keyframe_timestamps,
    get_video_duration,
    get_video_info,
)
from utils.image import to_grayscale, scale_roi, extract_roi, is_black, has_team_color


def format_timestamp(seconds):
    """Format seconds as MMmSSs for filenames (e.g. 05m23s)."""
    minutes = int(seconds) // 60
    secs = int(seconds) % 60
    return f"{minutes:02d}m{secs:02d}s"


def prescan_team_bar(video_path, target_height, team_bar_roi, sat_threshold):
    """Fast prescan using GOP I-frames to find in-game/not-in-game transitions.

    Iterates I-frames via single-pipe extraction, checks the team bar ROI
    for saturated color (team color bar present = in-game). Also collects
    all I-frame timestamps for reuse in interval snapping (avoids a
    separate full-video ffprobe scan).

    Args:
        video_path: Path to the input video.
        target_height: Processing height in pixels.
        team_bar_roi: Scaled ROI dict for the team bar region.
        sat_threshold: Saturation threshold for has_team_color().

    Returns:
        tuple: (transitions, iframe_count, iframe_timestamps) where
               transitions is a list of timestamps where state changes
               occur, iframe_count is the total I-frames scanned, and
               iframe_timestamps is a sorted list of all I-frame PTS times.
    """
    transitions = []
    iframe_timestamps = []
    prev_in_game = None
    iframe_count = 0

    for frame, timestamp in extract_iframes_scaled(video_path, target_height):
        iframe_count += 1
        iframe_timestamps.append(timestamp)
        region = extract_roi(frame, team_bar_roi)
        in_game = has_team_color(region, sat_threshold)

        if prev_in_game is not None and in_game != prev_in_game:
            transitions.append(timestamp)

        prev_in_game = in_game

    return transitions, iframe_count, iframe_timestamps


def build_scan_windows(transitions, padding, duration):
    """Build merged scan windows around transition timestamps.

    Args:
        transitions: List of transition timestamps in seconds.
        padding: Seconds to pad around each transition.
        duration: Total video duration in seconds.

    Returns:
        list[tuple[float, float]]: Merged (start, end) window pairs,
            clamped to [0, duration].
    """
    if not transitions:
        return []

    # Create padded windows around each transition
    windows = [
        (max(0.0, t - padding), min(duration, t + padding))
        for t in transitions
    ]
    windows.sort(key=lambda w: w[0])

    # Merge overlapping/adjacent windows
    merged = [windows[0]]
    for start, end in windows[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))

    return merged


def run(video_path, output_dir, config, threshold_override=None, profile=False):
    """Run black screen detection on a video file.

    Args:
        video_path: Path to the input video.
        output_dir: Directory to save extracted frames.
        config: Parsed YAML config dict.
        threshold_override: Optional brightness threshold override.
        profile: If True, collect per-phase timing data.

    Returns:
        tuple: (exported_list, frame_count, profile_stats, miss_reports) where
               exported_list is a list of dicts with keys 'filename', 'type'
               ('start' or 'end'), and 'timestamp', frame_count is the total
               I-frames processed, profile_stats is a dict of timing data (or
               None when profiling is off), and miss_reports is a list of dicts
               with keys 'type' ('missed_end' or 'missed_start'),
               'window_start', and 'window_end' (empty if no recoveries).
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
    start_confirm_frames = config["black_detection"].get("start_confirm_frames", 2)
    pre_end_offset = config["black_detection"].get("pre_end_offset", 10.0)
    max_game_duration = config["black_detection"].get("max_game_duration", 600)  # 10 min cap for miss windows
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
    # Validate that required ROI zones exist (minimap+vertical are used for start detection)
    roi_names = {r["name"] for r in scaled_rois}
    for required in ("minimap", "vertical"):
        if required not in roi_names:
            raise ValueError(
                f"Config must define 'minimap' and 'vertical' ROI zones. Found: {sorted(roi_names)}"
            )

    # Ensure output directory exists (AC 8)
    os.makedirs(output_dir, exist_ok=True)

    exported = []  # list of dicts: {filename, type, timestamp}
    extraction_requests = []  # deferred full-res extraction requests
    miss_reports = []  # list of dicts: {type, window_start, window_end}
    prev_timestamp = None
    skip_until = -1.0  # timestamp until which we skip detection
    last_event_timestamp = 0.0  # timestamp of most recent detection (normal or recovery)
    pre_end_safe_after = 0.0  # earliest safe timestamp for pre-end frames (avoids loading screens)
    # F6: sequence counter for unique filenames when timestamps collide
    detection_seq = 0

    # State machine: tracks round lifecycle to prevent consecutive end detections.
    # "undetermined"      = initial state, watching for the first transition of either type
    # "waiting_for_end"   = game is in progress, looking for end blackscreen
    # "waiting_for_start" = game ended, looking for start blackscreen (black -> non-black)
    state = "undetermined"
    prev_is_end_loading = None  # tracks previous frame's end-loading status for undetermined state
    prev_start_rois_black = None  # tracks previous frame's start-ROIs status for undetermined state
    start_confirm_count = 0  # consecutive frames passing start validation
    start_candidate_timestamp = None  # timestamp of first confirming frame
    saw_black_in_wait = False  # gate: must see loading screen before accepting start

    # Adaptive frame sampling: probe GOP to choose extraction strategy
    gop_interval = get_gop_interval(video_path)
    use_interval_mode = gop_interval > 2.0

    print(f"Processing: {video_path}")
    print(f"Config: threshold={threshold}, skip={skip_duration}s, target_height={target_height}px, start_confirm={start_confirm_frames}")
    print(f"ROI zones: {[r['name'] for r in roi_zones]}")
    if use_interval_mode:
        print(f"Sampling: two-pass mode (GOP={gop_interval:.1f}s > 2.0s)")
    else:
        print(f"Sampling: I-frame mode (GOP={gop_interval:.1f}s <= 2.0s)")
    print()

    if use_interval_mode:
        duration = get_video_duration(video_path)

        # --- Pass 1: prescan GOP I-frames for team bar transitions ---
        sat_threshold = config.get("team_bar_detection", {}).get("saturation_threshold", 90)
        window_padding = config.get("team_bar_detection", {}).get("window_padding", 30.0)

        # Find and scale the team_bar ROI
        team_bar_roi_raw = None
        for roi in roi_zones:
            if roi["name"] == "team_bar":
                team_bar_roi_raw = roi
                break
        if team_bar_roi_raw is None:
            raise ValueError(
                "Config must define a 'team_bar' ROI zone for two-pass mode. "
                f"Found: {[r['name'] for r in roi_zones]}"
            )
        team_bar_roi = scale_roi(team_bar_roi_raw, ref_scale)

        if profile_stats is not None:
            t0_prescan = time.perf_counter()

        transitions, iframe_count, iframe_timestamps = prescan_team_bar(
            video_path, target_height, team_bar_roi, sat_threshold,
        )

        if profile_stats is not None:
            profile_stats["prescan"] = time.perf_counter() - t0_prescan

        print(f"  Prescan: {len(transitions)} transitions found in {iframe_count} I-frames")

        # --- Build scan windows ---
        if transitions:
            windows = build_scan_windows(transitions, window_padding, duration)
        else:
            windows = [(0.0, duration)]
            print("  Prescan: no transitions found, falling back to full scan")

        window_total = sum(end - start for start, end in windows)
        window_strs = [f"[{s:.0f}s-{e:.0f}s]" for s, e in windows]
        print(f"  Scan windows: {' '.join(window_strs)} ({window_total:.0f}s of {duration:.0f}s)")
        print()

        # --- Pass 2: targeted interval scanning within windows ---
        # iframe_timestamps already collected during prescan (no extra ffprobe needed)

        def _chain_windows():
            for start, end in windows:
                yield from extract_frames_at_interval(
                    video_path, target_height, start, end,
                    interval=2.0, iframe_timestamps=iframe_timestamps,
                )

        frame_iter = _chain_windows()
    else:
        frame_iter = extract_iframes_scaled(video_path, target_height, profile_stats=profile_stats)

    frame_count = 0
    for frame, timestamp in frame_iter:
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

        # Check brightness-based ROI zones and cache results (AC 3).
        # Skip team_bar — it uses saturation detection, not brightness.
        if profile_stats is not None:
            t0 = time.perf_counter()
        roi_black = {}
        is_end_loading = True
        for sroi in scaled_rois:
            if sroi["name"] == "team_bar":
                continue
            region = extract_roi(gray, sroi)
            black = is_black(region, threshold)
            roi_black[sroi["name"]] = black
            if not black:
                is_end_loading = False
        minimap_black = roi_black["minimap"]
        vertical_black = roi_black["vertical"]
        if profile_stats is not None:
            profile_stats["roi_check"] += time.perf_counter() - t0

        # --- State machine ---
        # start_rois_black: both minimap+vertical black (lobby/loading screen).
        start_rois_black = minimap_black and vertical_black

        if state == "undetermined":
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
                # Pre-end snapshot: extract frame at T-offset for score context
                pre_end_ts = prev_timestamp - pre_end_offset
                if pre_end_offset > 0 and pre_end_ts >= pre_end_safe_after:
                    pre_ts_str = format_timestamp(pre_end_ts)
                    pre_fname = f"{pre_ts_str}_end-{int(pre_end_offset)}s_{detection_seq:03d}.png"
                    extraction_requests.append({"timestamp": pre_end_ts, "type": "pre-end", "filename": pre_fname})
                state = "waiting_for_start"
                skip_until = timestamp + skip_duration
                saw_black_in_wait = False
                last_event_timestamp = prev_timestamp
                pre_end_safe_after = timestamp + skip_duration
                print(f"  First transition: endLoading at {prev_timestamp:.1f}s")

            # startLoading detection: start-ROIs black -> non-black transition
            # Inner guard: BOTH must be individually non-black (De Morgan's)
            elif prev_start_rois_black and not start_rois_black:
                if not minimap_black and not vertical_black:
                    detection_seq += 1
                    ts_str = format_timestamp(timestamp)
                    fname = f"{ts_str}_start_{detection_seq:03d}.png"
                    extraction_requests.append({"timestamp": timestamp, "type": "start", "filename": fname})
                    state = "waiting_for_end"
                    start_confirm_count = 0
                    start_candidate_timestamp = None
                    last_event_timestamp = timestamp
                    pre_end_safe_after = timestamp
                    print(f"  First transition: startLoading at {timestamp:.1f}s")

        elif state == "waiting_for_end":
            if is_end_loading and prev_timestamp is not None:
                # Non-black -> black transition: end blackscreen detected.
                # Defer export — record the PREVIOUS timestamp for batch extraction.
                detection_seq += 1
                ts_str = format_timestamp(prev_timestamp)
                fname = f"{ts_str}_end_{detection_seq:03d}.png"
                extraction_requests.append({"timestamp": prev_timestamp, "type": "end", "filename": fname})
                # Pre-end snapshot: extract frame at T-offset for score context
                pre_end_ts = prev_timestamp - pre_end_offset
                if pre_end_offset > 0 and pre_end_ts >= pre_end_safe_after:
                    pre_ts_str = format_timestamp(pre_end_ts)
                    pre_fname = f"{pre_ts_str}_end-{int(pre_end_offset)}s_{detection_seq:03d}.png"
                    extraction_requests.append({"timestamp": pre_end_ts, "type": "pre-end", "filename": pre_fname})

                state = "waiting_for_start"
                skip_until = timestamp + skip_duration
                start_confirm_count = 0
                start_candidate_timestamp = None
                saw_black_in_wait = False
                last_event_timestamp = prev_timestamp
                pre_end_safe_after = timestamp + skip_duration

            elif prev_start_rois_black and not start_rois_black:
                if not minimap_black and not vertical_black:
                    # RECOVERY: detected a start while waiting for end.
                    # This means we missed an end transition.
                    window_start = max(last_event_timestamp, timestamp - max_game_duration)
                    miss_reports.append({
                        "type": "missed_end",
                        "window_start": window_start,
                        "window_end": timestamp,
                    })
                    detection_seq += 1
                    ts_str = format_timestamp(timestamp)
                    fname = f"{ts_str}_start_{detection_seq:03d}.png"
                    extraction_requests.append({"timestamp": timestamp, "type": "start", "filename": fname})
                    last_event_timestamp = timestamp
                    pre_end_safe_after = timestamp
                    # Stay in waiting_for_end — we just detected a start, next should be an end
                    start_confirm_count = 0
                    start_candidate_timestamp = None
                    print(f"  RECOVERY: startLoading at {timestamp:.1f}s (missed end in [{window_start:.1f}s, {timestamp:.1f}s])")

        elif state == "waiting_for_start":
            # Gate: must witness a loading screen (minimap+vertical black)
            # before accepting a start. This skips lobby screens that appear
            # between the end detection and the actual game loading screen.
            if start_rois_black:
                saw_black_in_wait = True
                start_confirm_count = 0
                start_candidate_timestamp = None
            elif saw_black_in_wait:
                if not minimap_black and not vertical_black:
                    start_confirm_count += 1
                    if start_candidate_timestamp is None:
                        start_candidate_timestamp = timestamp
                    if start_confirm_count >= start_confirm_frames:
                        # Confirmed start — use timestamp of first confirming frame.
                        detection_seq += 1
                        ts_str = format_timestamp(start_candidate_timestamp)
                        fname = f"{ts_str}_start_{detection_seq:03d}.png"
                        extraction_requests.append({"timestamp": start_candidate_timestamp, "type": "start", "filename": fname})
                        state = "waiting_for_end"
                        last_event_timestamp = start_candidate_timestamp
                        pre_end_safe_after = start_candidate_timestamp
                        start_confirm_count = 0
                        start_candidate_timestamp = None
                elif not prev_is_end_loading and is_end_loading:
                    # RECOVERY: detected an end while waiting for start.
                    # This means we missed a start transition (and possibly a full game).
                    window_start = max(last_event_timestamp, prev_timestamp - max_game_duration)
                    miss_reports.append({
                        "type": "missed_start",
                        "window_start": window_start,
                        "window_end": prev_timestamp,
                    })
                    detection_seq += 1
                    ts_str = format_timestamp(prev_timestamp)
                    fname = f"{ts_str}_end_{detection_seq:03d}.png"
                    extraction_requests.append({"timestamp": prev_timestamp, "type": "end", "filename": fname})
                    # Pre-end snapshot: extract frame at T-offset for score context
                    pre_end_ts = prev_timestamp - pre_end_offset
                    if pre_end_offset > 0 and pre_end_ts >= pre_end_safe_after:
                        pre_ts_str = format_timestamp(pre_end_ts)
                        pre_fname = f"{pre_ts_str}_end-{int(pre_end_offset)}s_{detection_seq:03d}.png"
                        extraction_requests.append({"timestamp": pre_end_ts, "type": "pre-end", "filename": pre_fname})
                    last_event_timestamp = prev_timestamp
                    # Stay in waiting_for_start — we just detected an end, next should be a start
                    skip_until = timestamp + skip_duration
                    pre_end_safe_after = timestamp + skip_duration
                    start_confirm_count = 0
                    start_candidate_timestamp = None
                    saw_black_in_wait = False
                    print(f"  RECOVERY: endLoading at {prev_timestamp:.1f}s (missed start in [{window_start:.1f}s, {prev_timestamp:.1f}s])")
                else:
                    start_confirm_count = 0
                    start_candidate_timestamp = None

        prev_is_end_loading = is_end_loading
        prev_start_rois_black = start_rois_black
        prev_timestamp = timestamp

    if frame_count == 0:
        print("Warning: No keyframes found in video.", file=sys.stderr)

    # --- Post-detection batch extraction phase ---
    if extraction_requests:
        # Sort by timestamp for sequential seeking (pre-end frames interleave with end frames)
        extraction_requests.sort(key=lambda r: r["timestamp"])
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
            elif req["type"] == "pre-end":
                print(f"  PRE-END -> exported {req['filename']} (frame at {req['timestamp']:.1f}s) [{i}/{len(extraction_requests)}]")
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

    return exported, frame_count, profile_stats, miss_reports


def _print_profile_report(ps):
    """Print a formatted profiling report from collected timing data."""
    wall = ps["wall_time"]
    total_frames = ps["frames_total"]
    processed = ps["frames_processed"]
    skipped = ps["frames_skipped"]

    # Phases to report, with their per-frame divisor (None = one-time, show dash)
    phase_divisors = {}
    if "prescan" in ps:
        phase_divisors["prescan"] = None
    phase_divisors.update({
        "ffprobe_info": None,
        "ffmpeg_read": total_frames,
        "grayscale": processed,
        "roi_check": processed,
        "fullres_extract": None,
    })

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

    # Create video-named subfolder inside output directory
    video_stem = os.path.splitext(os.path.basename(args.video))[0]
    output_dir = os.path.join(output_dir, video_stem)

    try:
        exported, frame_count, profile_stats, miss_reports = run(
            args.video, output_dir, config, args.threshold, profile=args.profile
        )
    except Exception as e:
        print(f"Error during processing: {e}", file=sys.stderr)
        sys.exit(1)

    # Print summary (AC 9 — always prints, even if 0 transitions)
    print()
    print("=" * 50)
    print(f"Summary:")
    print(f"  Frames processed: {frame_count}")
    end_count = sum(1 for e in exported if e["type"] == "end")
    start_count = sum(1 for e in exported if e["type"] == "start")
    pre_end_count = sum(1 for e in exported if e["type"] == "pre-end")
    print(f"  Game ends detected: {end_count}")
    print(f"  Pre-end snapshots: {pre_end_count}")
    print(f"  Game starts detected: {start_count}")
    print(f"  Total events: {len(exported)}")
    print(f"  Output directory: {os.path.abspath(output_dir)}")
    if exported:
        print(f"  Exported frames:")
        for entry in exported:
            print(f"    - {entry['filename']}  ({entry['type']} at {entry['timestamp']:.1f}s)")
    else:
        print(f"  No transitions found.")
    if miss_reports:
        print(f"  Recovery events: {len(miss_reports)}")
        print(f"  Missed transitions:")
        for mr in miss_reports:
            window_start_str = format_timestamp(mr['window_start'])
            window_end_str = format_timestamp(mr['window_end'])
            print(f"    - {mr['type']}: estimated between {window_start_str} ({mr['window_start']:.1f}s) and {window_end_str} ({mr['window_end']:.1f}s)")
    print("=" * 50)

    # Print profiling report if --profile was passed
    if profile_stats is not None:
        _print_profile_report(profile_stats)


if __name__ == "__main__":
    main()
