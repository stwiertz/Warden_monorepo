---
title: 'Adaptive Frame Sampling for BSD ROI Debugger'
slug: 'bsd-adaptive-frame-sampling'
created: '2026-03-01'
status: 'completed'
stepsCompleted: [1, 2, 3, 4]
tech_stack: [python, ffmpeg, ffprobe, numpy, opencv]
files_to_modify: [utils/video.py, tools/bsd_roi_debugger.py]
code_patterns: [ffmpeg-subprocess, seek-per-frame, generator-yield, ffprobe-json-parsing, input-seeking]
test_patterns: [manual-video-regression]
---

# Tech-Spec: Adaptive Frame Sampling for BSD ROI Debugger

**Created:** 2026-03-01

## Overview

### Problem Statement

The ROI debugger only extracts I-frames via `extract_iframes_scaled()`, which relies on ffmpeg's `-skip_frame nokey` flag. MKV files (and other containers with large GOPs of ~8-10 seconds) yield too few frames to meaningfully analyze a time range — e.g., only 5 frames across a 40-second window. This makes the debugger ineffective for investigating missed detections in those regions.

### Solution

Probe the video's keyframe interval (GOP) via ffprobe. Based on the result:
- **GOP <= 2s**: Use I-frames only (current behavior — already dense enough for useful analysis).
- **GOP > 2s**: Switch to interval-based extraction (~1 frame every 2s), snapping to the nearest I-frame when one falls within a configurable tolerance of the target timestamp. This hybrid approach prefers keyframes (cheaper to decode, exact) but fills gaps with seek-decoded frames at 360p.

This change applies **only to the debugger** — the main black screen detector retains its I-frame-only pipeline.

### Scope

**In Scope:**
- GOP interval detection via ffprobe
- New extraction function in `utils/video.py` for interval-based frame sampling (seek + decode at target resolution)
- Adaptive logic in the debugger to choose I-frame vs interval mode based on GOP
- Hybrid I-frame snapping: prefer I-frame if within tolerance of target timestamp

**Out of Scope:**
- Changes to the main black screen detector's extraction pipeline
- Changes to ROI zones, thresholds, or detection logic
- Performance optimization beyond 360p downscaling
- Adding CLI flags for manual mode override (can be added later if needed)

## Context for Development

### Codebase Patterns

- `extract_iframes_scaled()` (video.py:89-177) — generator yielding `(frame, timestamp)` via single-pass ffmpeg with `-skip_frame nokey` + `showinfo` filter. Timestamps parsed from stderr via regex `pts_time:(\S+)`. Frames piped as raw BGR24 from stdout.
- `extract_frame_at_timestamp()` (video.py:183-219) — seeks to exact timestamp via `-ss <t> -i video -frames:v 1`. Returns full-resolution BGR frame. Does NOT scale — must be extended or wrapped.
- `get_video_info()` (video.py:41-67) — ffprobe JSON query for `(width, height)`. Pattern to follow for GOP detection.
- `check_ffmpeg()` (video.py:22-38) — validates ffmpeg+ffprobe on PATH, caches result. Must call before any new ffprobe function.
- Debugger `run()` (bsd_roi_debugger.py:46-142) — iterates `extract_iframes_scaled()`, filters by time range (lines 88-90), processes ROIs per frame. The time range filtering happens in the consumer, not the generator.
- Scaled dimensions computed as `round(src_w * target_height / src_h / 2) * 2` (video.py:115) — ensures even numbers for ffmpeg. Must reuse same formula in new extraction function.
- All image analysis uses `utils/image.py` stateless helpers: `to_grayscale()`, `scale_roi()`, `extract_roi()`, `is_black()`.
- No test framework — manual video regression only.

### Files to Reference

| File | Purpose |
| ---- | ------- |
| utils/video.py:89-177 | `extract_iframes_scaled()` — current I-frame generator, pattern to follow |
| utils/video.py:183-219 | `extract_frame_at_timestamp()` — existing seek-based extraction (full-res only) |
| utils/video.py:41-67 | `get_video_info()` — ffprobe pattern to follow for GOP detection |
| tools/bsd_roi_debugger.py:46-142 | `run()` — main consumer, needs adaptive strategy selection |
| tools/bsd_roi_debugger.py:87-91 | Frame iteration + time range filtering — the integration point |
| config/config.yaml | Processing config: `target_height`, thresholds, ROI zones |
| utils/image.py | Stateless image helpers reused by debugger |

### Technical Decisions

- **GOP detection**: Use `ffprobe -v error -select_streams v:0 -read_intervals "%+30" -show_frames -show_entries frame=pts_time,key_frame -of json` to scan only the first 30 seconds. Parse I-frame timestamps, compute median interval. `-read_intervals "%+30"` limits the scan to avoid reading the entire file.
- **GOP threshold**: 2.0 seconds. At or below → I-frame mode (current behavior). Above → interval mode.
- **Interval extraction**: Per-timestamp `ffmpeg -ss <t> -i video -vf scale=W:H -frames:v 1 -f rawvideo -pix_fmt bgr24 pipe:1`. Input seeking (`-ss` before `-i`) fast-seeks to nearest keyframe then decodes forward. At 360p with rawvideo pipe, each frame is ~640*360*3 = ~691KB.
- **Hybrid snapping**: Build target timestamps at 2s interval across the range. Collect I-frame timestamps from the GOP probe (filtered to the analysis range). For each target, if an I-frame is within 0.5s tolerance, use the I-frame timestamp instead. Deduplicate the final list.
- **New functions, not modify existing**: Add `get_gop_interval()` and `extract_frames_at_interval()` in `utils/video.py`. Do not modify `extract_iframes_scaled()` — the detector's pipeline stays untouched.
- **Resolution**: Interval-extracted frames scaled to 360p in the ffmpeg command via `-vf scale=W:H`, using the same even-number formula as `extract_iframes_scaled()`.
- **Generator interface**: `extract_frames_at_interval()` yields `(frame, timestamp)` tuples — same contract as `extract_iframes_scaled()` — so the debugger's frame loop needs minimal changes.

## Implementation Plan

### Tasks

- [x] Task 1: Add `get_keyframe_timestamps()` to `utils/video.py`
  - File: `utils/video.py`
  - Action: Add a new function after `get_video_info()` (after line 67) that probes keyframe timestamps using ffprobe:
    ```python
    def get_keyframe_timestamps(video_path, scan_duration=30):
        """Get I-frame timestamps from the first N seconds of a video.

        Args:
            video_path: Path to the input video file.
            scan_duration: How many seconds to scan from the start (default 30).

        Returns:
            list[float]: Sorted list of keyframe PTS timestamps in seconds.

        Raises:
            RuntimeError: If ffprobe returns no frame data.
        """
        check_ffmpeg()
        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-read_intervals", f"%+{scan_duration}",
            "-show_frames",
            "-show_entries", "frame=pts_time,key_frame",
            "-of", "json",
            str(video_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        frames = data.get("frames", [])
        if not frames:
            raise RuntimeError(
                f"No frame data returned by ffprobe for '{video_path}'. "
                "Ensure the file is a valid video."
            )
        return sorted(
            float(f["pts_time"])
            for f in frames
            if f.get("key_frame") == 1
        )
    ```
  - Notes: Follows the same pattern as `get_video_info()` — ffprobe subprocess, JSON parsing, validation. The `-read_intervals "%+30"` flag limits scanning to the first 30 seconds.

- [x] Task 2: Add `get_gop_interval()` to `utils/video.py`
  - File: `utils/video.py`
  - Action: Add a function after `get_keyframe_timestamps()` that computes the median GOP from keyframe timestamps:
    ```python
    def get_gop_interval(video_path, scan_duration=30):
        """Compute the median keyframe interval (GOP) for a video.

        Args:
            video_path: Path to the input video file.
            scan_duration: How many seconds to scan from the start (default 30).

        Returns:
            float: Median interval between consecutive keyframes in seconds.
                   Returns 0.0 if fewer than 2 keyframes are found.
        """
        timestamps = get_keyframe_timestamps(video_path, scan_duration)
        if len(timestamps) < 2:
            return 0.0
        intervals = [
            timestamps[i + 1] - timestamps[i]
            for i in range(len(timestamps) - 1)
        ]
        intervals.sort()
        mid = len(intervals) // 2
        if len(intervals) % 2 == 0:
            return (intervals[mid - 1] + intervals[mid]) / 2
        return intervals[mid]
    ```
  - Notes: Median is more robust than mean — a single outlier GOP (e.g., scene change) won't skew the result. Returns 0.0 for single-keyframe files (edge case — treat as I-frame mode).

- [x] Task 3: Add `extract_frame_at_timestamp_scaled()` to `utils/video.py`
  - File: `utils/video.py`
  - Action: Add a function after `extract_frame_at_timestamp()` (after line 219) that extracts a single frame at a given timestamp, scaled to target height:
    ```python
    def extract_frame_at_timestamp_scaled(video_path, timestamp, target_height):
        """Extract a single frame at a timestamp, scaled to target height.

        Uses input seeking (-ss before -i) for fast seeking. Scales in the
        ffmpeg pipeline to avoid decoding full resolution.

        Args:
            video_path: Path to the input video file.
            timestamp: PTS timestamp in seconds (float).
            target_height: Desired output height in pixels.

        Returns:
            numpy array of shape (scaled_h, scaled_w, 3) in BGR color order.

        Raises:
            RuntimeError: If the extracted frame size doesn't match expected dimensions.
        """
        src_w, src_h = get_video_info(video_path)
        scaled_w = round(src_w * target_height / src_h / 2) * 2
        scaled_h = target_height

        cmd = [
            "ffmpeg",
            "-v", "error",
            "-ss", f"{timestamp:.6f}",
            "-i", str(video_path),
            "-vf", f"scale={scaled_w}:{scaled_h}",
            "-frames:v", "1",
            "-f", "rawvideo",
            "-pix_fmt", "bgr24",
            "pipe:1",
        ]

        result = subprocess.run(cmd, capture_output=True, check=True)
        expected_size = scaled_w * scaled_h * 3
        if len(result.stdout) != expected_size:
            raise RuntimeError(
                f"Frame extraction at {timestamp:.6f}s returned {len(result.stdout)} bytes, "
                f"expected {expected_size} ({scaled_w}x{scaled_h} BGR24)"
            )
        return np.frombuffer(result.stdout, dtype=np.uint8).reshape(
            (scaled_h, scaled_w, 3)
        )
    ```
  - Notes: Follows same pattern as `extract_frame_at_timestamp()` but adds `-vf scale=W:H` and computes scaled dimensions using the same even-number formula as `extract_iframes_scaled()` (line 115). Calls `get_video_info()` internally — this adds one ffprobe call per frame. To avoid repeated ffprobe calls, the debugger should cache `(src_w, src_h)` and pass dimensions. However, for simplicity in this iteration we accept the overhead since the debugger already calls `get_video_info()` once, and ffprobe is fast. **Optimization note**: if profiling shows this matters, refactor to accept `(src_w, src_h)` as optional params.

- [x] Task 4: Add `extract_frames_at_interval()` generator to `utils/video.py`
  - File: `utils/video.py`
  - Action: Add a generator function after `extract_frame_at_timestamp_scaled()` that yields `(frame, timestamp)` tuples at a regular interval, with I-frame snapping:
    ```python
    def extract_frames_at_interval(video_path, target_height, start, end,
                                    interval=2.0, iframe_timestamps=None,
                                    snap_tolerance=0.5):
        """Yield (frame, timestamp) at regular intervals with I-frame snapping.

        Builds a list of target timestamps spaced by `interval` seconds. For each
        target, if an I-frame timestamp is within `snap_tolerance`, the I-frame
        timestamp is used instead (cheaper to seek to). Duplicates are removed.

        Args:
            video_path: Path to the input video file.
            target_height: Desired output height in pixels.
            start: Start of time range in seconds.
            end: End of time range in seconds.
            interval: Seconds between target frames (default 2.0).
            iframe_timestamps: Optional sorted list of known I-frame PTS times.
                If None, no snapping is performed.
            snap_tolerance: Max distance in seconds to snap to an I-frame (default 0.5).

        Yields:
            tuple: (frame, timestamp) where frame is BGR numpy array at target_height.
        """
        # Build target timestamp grid
        targets = []
        t = start
        while t <= end:
            targets.append(t)
            t += interval

        # Snap to nearby I-frames
        if iframe_timestamps:
            snapped = []
            for target in targets:
                best = target
                for iframe_ts in iframe_timestamps:
                    if abs(iframe_ts - target) <= snap_tolerance:
                        best = iframe_ts
                        break
                snapped.append(best)
            # Deduplicate while preserving order
            seen = set()
            targets = []
            for ts in snapped:
                if ts not in seen:
                    seen.add(ts)
                    targets.append(ts)

        for ts in targets:
            frame = extract_frame_at_timestamp_scaled(video_path, ts, target_height)
            yield frame, ts
    ```
  - Notes: The snapping logic iterates I-frame timestamps for each target. Since both lists are small (< 100 elements), linear scan is fine. The generator yields the same `(frame, timestamp)` contract as `extract_iframes_scaled()`, making it a drop-in replacement in the debugger's frame loop. `iframe_timestamps` should be the full list from `get_keyframe_timestamps()` — the function handles filtering to the range internally via the snap tolerance.

- [x] Task 5: Update debugger `run()` to use adaptive frame sampling
  - File: `tools/bsd_roi_debugger.py`
  - Action: Modify `run()` to probe GOP and select extraction strategy. Changes:
    1. Add import at top of file: `from utils.video import get_gop_interval, get_keyframe_timestamps, extract_frames_at_interval`
    2. In `run()`, after existing setup (line 76, after `os.makedirs`), add GOP detection:
       ```python
       # Adaptive frame sampling: probe GOP to choose extraction strategy
       gop_interval = get_gop_interval(video_path)
       use_interval_mode = gop_interval > 2.0
       ```
    3. Update the console output (after existing print statements around line 83-85):
       ```python
       if use_interval_mode:
           print(f"Sampling: interval mode (GOP={gop_interval:.1f}s > 2.0s, extracting every 2.0s)")
       else:
           print(f"Sampling: I-frame mode (GOP={gop_interval:.1f}s <= 2.0s)")
       ```
    4. Replace the frame iteration block (lines 87-91) with adaptive selection:
       ```python
       if use_interval_mode:
           iframe_timestamps = get_keyframe_timestamps(video_path)
           frame_iter = extract_frames_at_interval(
               video_path, target_height, range_start, range_end,
               interval=2.0, iframe_timestamps=iframe_timestamps,
           )
       else:
           frame_iter = (
               (frame, ts) for frame, ts in extract_iframes_scaled(video_path, target_height)
               if range_start <= ts <= range_end
           )

       for frame, timestamp in frame_iter:
       ```
    5. Remove the old time range filtering inside the loop (lines 88-90: `if timestamp < range_start: continue` and `if timestamp > range_end: break`) since both paths now handle range filtering.
  - Notes: The I-frame path wraps `extract_iframes_scaled()` in a generator expression that filters by range — same behavior as before but now the filtering is consistent between both paths. The interval path passes the full `iframe_timestamps` list (not filtered to range) because `get_keyframe_timestamps()` only scans the first 30s anyway and snapping handles out-of-range gracefully.

- [x] Task 6: Handle `get_keyframe_timestamps` scan range for long videos
  - File: `utils/video.py`
  - Action: In `get_keyframe_timestamps()`, the default `scan_duration=30` only returns timestamps from the first 30 seconds. When the debugger needs I-frame timestamps for snapping in a range like `1030:1070`, the first-30s timestamps are useless. Update the debugger's call in Task 5 to pass a broader scan range:
    ```python
    iframe_timestamps = get_keyframe_timestamps(video_path, scan_duration=int(range_end) + 30)
    ```
    This scans up to `range_end + 30s`, ensuring I-frame timestamps covering the analysis range are available for snapping. For GOP detection (which only needs a representative sample), `get_gop_interval()` still uses the default 30s scan.
  - Notes: Scanning up to `range_end` in ffprobe `-read_intervals` reads frame headers only (no decoding), so even `%+1100` for a video at 1070s is fast — a few seconds at most. The cost is proportional to frame count, not video bitrate.

### Acceptance Criteria

- [x] AC 1: Given a video with GOP <= 2.0s (e.g., astera.mp4), when the debugger runs, then it uses I-frame mode and the output is identical to the current behavior (same frame count, same timestamps, same ROI analysis).
- [x] AC 2: Given a video with GOP > 2.0s (e.g., lvlaste.mkv with ~8.3s GOP), when the debugger runs with `--range 1030:1070`, then it uses interval mode and yields approximately 20 frames (~1 every 2s) instead of the current 5 I-frames.
- [x] AC 3: Given interval mode is active, when a target timestamp falls within 0.5s of a known I-frame, then the I-frame timestamp is used instead of the target, and no duplicate frames are produced.
- [x] AC 4: Given `get_gop_interval()` is called on a valid video, when it scans the first 30 seconds, then it returns the median interval between consecutive keyframes as a float (or 0.0 if fewer than 2 keyframes exist).
- [x] AC 5: Given `extract_frames_at_interval()` is called with a time range and interval, when it yields frames, then each frame is a BGR numpy array scaled to target_height with correct dimensions (even-number width matching ffmpeg rounding).
- [x] AC 6: Given the debugger runs in interval mode, when it prints the sampling header, then it displays the detected GOP value and confirms interval mode is active (e.g., "Sampling: interval mode (GOP=8.3s > 2.0s, extracting every 2.0s)").

## Additional Context

### Dependencies

None — uses existing ffmpeg/ffprobe already required by the project.

### Testing Strategy

- **GOP detection**: Run on astera.mp4 (MP4, likely small GOP) and lvlaste.mkv (MKV, known large GOP ~8s) — verify correct GOP measurement
- **Frame count**: Run debugger on lvlaste.mkv `--range 1030:1070` — should yield ~20 frames (1 per 2s) instead of 5
- **Visual verification**: Check annotated PNGs in output/debug — frames should be evenly spaced and show correct ROI analysis
- **Regression**: Run on astera.mp4 with small GOP — should use I-frame mode and produce identical results to current behavior

### Notes

- lvlaste.mkv GOP is ~8.3s based on observed I-frame spacing (1033, 1041, 1050, 1058, 1066)
- The `Warning: ffmpeg exited with code 1` in the debugger output is from the I-frame pipeline terminating early when the time range ends — not related to this feature
- Future enhancement: add `--mode iframe|interval|auto` CLI flag for manual override

## Review Notes

- Adversarial review completed
- Findings: 14 total, 4 fixed, 10 skipped (noise/by-design/deferred)
- Resolution approach: auto-fix
- F1 (Critical, fixed): Added missing `check_ffmpeg()` to `extract_frame_at_timestamp_scaled`
- F4 (High, fixed): Snap logic now finds closest I-frame by minimum distance, not first match
- F5 (High, fixed): `extract_frames_at_interval` raises `ValueError` on `end=float('inf')`
- F7 (High, fixed): Restored early-break behavior in I-frame mode (skip/break instead of filter-all)
