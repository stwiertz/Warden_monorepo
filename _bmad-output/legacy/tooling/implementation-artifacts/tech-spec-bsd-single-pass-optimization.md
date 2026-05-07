---
title: 'BSD Single-Pass Pipeline Optimization'
slug: 'bsd-single-pass-optimization'
created: '2026-02-25'
status: 'completed'
stepsCompleted: [1, 2, 3, 4]
tech_stack: ['Python 3', 'FFmpeg (subprocess)', 'ffprobe (subprocess)', 'OpenCV (cv2)', 'NumPy', 'PyYAML']
files_to_modify: ['utils/video.py', 'tools/black_screen_detector.py']
code_patterns: ['generator yielding (frame, timestamp) tuples', 'subprocess.Popen with stdout pipe for frame data', 'stderr to tempfile to avoid pipe deadlock (F9)', 'profile_stats dict with per-phase timing accumulation', 'state machine with waiting_for_end / waiting_for_start']
test_patterns: ['no test files — manual testing via --profile flag and visual inspection of exported frames']
---

# Tech-Spec: BSD Single-Pass Pipeline Optimization

**Created:** 2026-02-25

## Overview

### Problem Statement

The black screen detector spends 93% of its wall time in two sequential FFmpeg subprocess calls. First, `ffprobe` scans the entire video to enumerate all I-frame timestamps (45.8%), blocking all processing until complete. Then `ffmpeg` decodes every I-frame at full resolution (~6 MB/frame raw BGR24) through a pipe (47.3%). The two-pass design means no frame can be processed until the full ffprobe scan finishes, and piping full-resolution frames wastes bandwidth when only 360p is needed for detection.

### Solution

Replace the two-pass architecture with a single `ffmpeg` pass that decodes I-frames directly at 360p (~0.5 MB/frame) using `-vf scale=-1:360`, extracting timestamps from stderr via the `showinfo` filter instead of a separate `ffprobe` call. After detection completes, selectively re-extract only the ~20 detected frames at full resolution using targeted seeks — eliminating the need to pipe full-res data for every frame.

### Scope

**In Scope:**

- Eliminate the `ffprobe` keyframe timestamp pass — extract timestamps from `ffmpeg`'s `showinfo` filter on stderr
- Have `ffmpeg` output scaled 360p I-frames instead of full-resolution (reduce pipe data ~12x)
- After detection, perform targeted full-res extraction for only the frames that need exporting (~20 frames)
- Update profiling phases to reflect the new single-pass architecture

**Out of Scope:**

- `frame.copy()` optimization (3% of wall time — not worth the complexity)
- Detection logic or state machine changes
- ROI zone or threshold changes
- Changes to CLI interface or output format

## Context for Development

### Codebase Patterns

- FFmpeg/ffprobe invoked via `subprocess.Popen` / `subprocess.run` in `utils/video.py`
- stderr redirected to `tempfile.TemporaryFile` to avoid pipe buffer deadlock (F9)
- Frame data piped as raw BGR24 via `pipe:1`, read with `proc.stdout.read(frame_size)` + `np.frombuffer().reshape()`
- Generator pattern: `extract_iframes()` yields `(frame, timestamp)` tuples consumed by the detector loop
- Profiling via `--profile` flag: `profile_stats` dict accumulates per-phase `time.perf_counter()` deltas
- State machine: `waiting_for_end` (looking for all-ROI-black) / `waiting_for_start` (looking for minimap-non-black)
- END events export `prev_frame` (previous full-res frame); START events export current `frame`
- `prev_frame = frame.copy()` called on every non-skipped frame (~6 MB copy each time)

### Files to Modify

| File | Changes |
| ---- | ------- |
| `utils/video.py` | New `extract_iframes_scaled()` generator (single-pass with showinfo + scale filter, stderr thread for timestamps). New `extract_frame_at_timestamp()` for selective full-res extraction. Keep `_get_video_info()` as-is (0.2%). `_get_keyframe_timestamps()` becomes unused. |
| `tools/black_screen_detector.py` | Switch from `extract_iframes()` to `extract_iframes_scaled()`. Remove `downscale()` from loop (frames already 360p). Replace `prev_frame` / `frame.copy()` with `prev_timestamp` tracking. Collect detection timestamps during loop, batch full-res extraction after loop. Update profiling phases. |

### Technical Decisions

- **showinfo filter for timestamps**: Chosen over container format output or parallel ffprobe because it requires no additional subprocess and provides frame-accurate PTS timestamps inline with the decode pass. Requires `-v info -nostats` (showinfo logs at `AV_LOG_INFO`, suppressed by default `-v error`). Stderr thread filters lines via `pts_time:` regex, ignoring other ffmpeg output.
- **Threading for stderr**: A `threading.Thread` reads stderr line-by-line, pushes parsed timestamps into a `queue.Queue`. Main thread reads frame bytes from stdout and pops timestamp via blocking `queue.get()`. showinfo writes to stderr before frame pixels reach stdout, so timestamps are always available before the corresponding frame read completes.
- **Scaled pipe output**: `ffmpeg -skip_frame nokey -i <video> -vf "showinfo,scale=-1:360" -vsync 0 -f rawvideo -pix_fmt bgr24 pipe:1`. Output frame size computed as `scaled_width = round(source_width * target_height / source_height / 2) * 2` to match ffmpeg's even-number rounding. Still requires `_get_video_info()` ffprobe call for source dimensions (0.2%, negligible).
- **Selective full-res re-extraction**: For each detected timestamp, run `ffmpeg -ss <pts> -i <video> -frames:v 1 -f rawvideo -pix_fmt bgr24 pipe:1`. Input seeking (`-ss` before `-i`) fast-seeks to nearest keyframe. Since our timestamps are keyframe PTS values, seek lands exactly on the target frame. ~100ms per frame, ~2s total for ~20 frames.
- **Detection loop simplification**: Frames arrive pre-scaled at 360p — no `downscale()` needed. No `prev_frame` storage — only `prev_timestamp` tracked. `cv2.imwrite()` moves to post-detection batch extraction phase.

## Implementation Plan

### Tasks

- [x] Task 1: Add stderr timestamp reader to `utils/video.py`
  - File: `utils/video.py`
  - Action: Add `import threading, queue, re` at the top. Add `_stderr_timestamp_reader(stderr_pipe, ts_queue)` function that reads stderr line-by-line, parses `pts_time:(\S+)` via regex, pushes `float` timestamps into `ts_queue`, and pushes `None` sentinel when the stream closes.
  - Notes: This is the thread target for pairing showinfo timestamps with piped frames.

- [x] Task 2: Add `extract_iframes_scaled()` generator to `utils/video.py`
  - File: `utils/video.py`
  - Action: New generator function `extract_iframes_scaled(video_path, target_height, profile_stats=None)` that:
    1. Calls `check_ffmpeg()` and `_get_video_info()` (profiles as `ffprobe_info`).
    2. Computes scaled dimensions: `scaled_w = round(src_w * target_height / src_h / 2) * 2`, `scaled_h = target_height`.
    3. Builds ffmpeg command: `ffmpeg -skip_frame nokey -v info -nostats -i <video> -vf "showinfo,scale=-1:{target_height}" -vsync 0 -f rawvideo -pix_fmt bgr24 pipe:1`.
    4. Spawns `subprocess.Popen` with `stdout=PIPE, stderr=PIPE`.
    5. Starts `_stderr_timestamp_reader` daemon thread.
    6. Loops: reads `scaled_w * scaled_h * 3` bytes from stdout, calls `ts_queue.get(timeout=10)` for the timestamp, yields `(frame, timestamp)`.
    7. In `finally` block: closes stdout, terminates process, waits, joins thread. Warns on non-zero exit codes (excluding SIGTERM/pipe-closed).
    8. Profiles per-frame reads as `ffmpeg_read`.
  - Notes: The `timeout=10` on `queue.get()` prevents deadlock if showinfo produces no output. `stderr=PIPE` (not tempfile) is required so the thread can read it line-by-line.

- [x] Task 3: Add `extract_frame_at_timestamp()` to `utils/video.py`
  - File: `utils/video.py`
  - Action: New function `extract_frame_at_timestamp(video_path, timestamp, width, height)` that:
    1. Builds command: `ffmpeg -v error -ss {timestamp} -i <video> -frames:v 1 -f rawvideo -pix_fmt bgr24 pipe:1`.
    2. Runs via `subprocess.run(cmd, capture_output=True, check=True)`.
    3. Validates `len(result.stdout) == width * height * 3`, raises `RuntimeError` if not.
    4. Returns `np.frombuffer(result.stdout, dtype=np.uint8).reshape((height, width, 3))`.
  - Notes: Input seeking (`-ss` before `-i`) fast-seeks to the nearest keyframe. Since timestamps are keyframe PTS values, seek lands exactly on target. Use full-precision timestamp string (`f"{timestamp:.6f}"`) to avoid rounding drift.

- [x] Task 4: Make `_get_video_info()` public in `utils/video.py`
  - File: `utils/video.py`
  - Action: Rename `_get_video_info` to `get_video_info`. Update all internal callers (`extract_iframes`, `extract_iframes_scaled`).
  - Notes: The detector needs source dimensions for the post-loop extraction phase.

- [x] Task 5: Modify detection loop in `tools/black_screen_detector.py`
  - File: `tools/black_screen_detector.py`
  - Action:
    1. Update imports: add `extract_iframes_scaled, extract_frame_at_timestamp, get_video_info` from `utils.video`. Remove `downscale` from `utils.image` imports.
    2. Remove `prev_frame = None` initialization. Keep `prev_timestamp = None`.
    3. Replace `extract_iframes(video_path, profile_stats=profile_stats)` with `extract_iframes_scaled(video_path, target_height, profile_stats=profile_stats)`.
    4. Remove `rois_calibrated` block (frames are already at target_height; ROIs scaled from reference to target are correct by construction).
    5. Remove all `downscale()` calls inside the loop — frames arrive pre-scaled.
    6. Remove `prev_frame = frame.copy()` and its profiling — replace with `prev_timestamp = timestamp`.
    7. In `waiting_for_end` branch: instead of `cv2.imwrite(out_path, prev_frame)`, append to `extraction_requests` list: `{"timestamp": prev_timestamp, "type": "end", "filename": fname}`.
    8. In `waiting_for_start` branch: instead of `cv2.imwrite(out_path, frame)`, append to `extraction_requests` list: `{"timestamp": timestamp, "type": "start", "filename": fname}`.
    9. Remove `profile_stats["downscale"]`, `profile_stats["frame_copy"]`, and `profile_stats["imwrite"]` initialization.
  - Notes: The initial state determination (first frame) also no longer needs `downscale()` — the frame is already 360p. Just apply `to_grayscale()` directly.

- [x] Task 6: Add post-detection batch extraction phase to `tools/black_screen_detector.py`
  - File: `tools/black_screen_detector.py`
  - Action: After the detection loop, add a batch extraction phase:
    1. Call `get_video_info(video_path)` to get source `(width, height)`.
    2. Profile the extraction phase as `fullres_extract`.
    3. For each request in `extraction_requests`:
       - Call `extract_frame_at_timestamp(video_path, req["timestamp"], width, height)`.
       - `cv2.imwrite(os.path.join(output_dir, req["filename"]), frame)`.
       - Print the detection message (currently printed inline during detection).
    4. Build the `exported` list from the extraction results.
  - Notes: This phase is expected to take ~2s for ~20 frames. Print extraction progress so the user sees something during this phase.

- [x] Task 7: Update profiling in `tools/black_screen_detector.py`
  - File: `tools/black_screen_detector.py`
  - Action:
    1. Remove `downscale`, `frame_copy`, `imwrite` from `profile_stats` initialization.
    2. Add `fullres_extract` to `profile_stats` initialization (set to `0.0`).
    3. In `_print_profile_report()`: update `phase_divisors` dict — remove `ffprobe_keyframes`, `downscale`, `frame_copy`. Add `fullres_extract: None` (one-time batch). Keep `imwrite: None` if tracked separately within extraction, or fold into `fullres_extract`.
  - Notes: The new profile report should show: `ffprobe_info`, `ffmpeg_read`, `grayscale`, `roi_check`, `fullres_extract`. Expected result: `ffmpeg_read` dominates at ~90%+ (but at much lower absolute time due to 360p frames), `fullres_extract` is a small constant.

### Acceptance Criteria

- [x] AC 1: Given a video file, when running the detector, then no `ffprobe -skip_frame nokey` subprocess is spawned (the keyframe timestamp scan is eliminated).
- [x] AC 2: Given a video file, when running with `--profile`, then the profile report contains no `ffprobe_keyframes` phase and shows a new `fullres_extract` phase.
- [x] AC 3: Given a video file, when running the detector, then frames piped from ffmpeg are at `target_height` resolution (360p), not source resolution.
- [x] AC 4: Given a video with known transitions (same test recording used for profiling), when running the detector, then the same transitions are detected at the same timestamps as the old two-pass implementation.
- [x] AC 5: Given a video with detected transitions, when the batch extraction phase runs, then exported PNG frames are at full source resolution (e.g., 1920x1080), not 360p.
- [x] AC 6: Given a video file, when running with `--profile`, then wall time is measurably reduced compared to the old architecture (expected ~45% reduction from eliminating the ffprobe keyframe scan, plus reduced pipe throughput).
- [x] AC 7: Given ffmpeg terminates unexpectedly during the detection pass, when the stderr reader thread is running, then the thread exits cleanly (no deadlock, no unhandled exception) and the error is reported to stderr.
- [x] AC 8: Given the `--profile` flag is not passed, when running the detector, then no profiling overhead is added (same conditional pattern as current implementation).

## Additional Context

### Dependencies

- Python stdlib `threading`, `queue`, `re` — all built-in, no new external packages required.
- FFmpeg must support the `showinfo` video filter — available since FFmpeg 0.8 (effectively all modern installations).
- No changes to `config/config.yaml` or `utils/image.py`.

### Testing Strategy

- **Regression test**: Run against the same test recording used for the profiling data. Compare exported filenames, timestamps, and frame content against the old output. All detections must match.
- **Profile comparison**: Run old and new versions with `--profile` on the same video. Compare wall time, verify `ffprobe_keyframes` is gone, verify `fullres_extract` appears.
- **Edge case — short video**: Test with a very short video (1-2 keyframes) to verify the generator handles early termination and the extraction phase handles zero detections.
- **Edge case — no detections**: Test with a video that has no black screen transitions. Verify the extraction phase is skipped cleanly.
- **Visual inspection**: Spot-check a few exported frames to confirm they are full-resolution and match the expected game state.

### Notes

- **showinfo output format risk**: The regex `pts_time:(\S+)` is stable across FFmpeg versions (tested output format since FFmpeg 2.x). If a future FFmpeg version changes the showinfo format, this would break timestamp extraction. Mitigation: the `queue.get(timeout=10)` prevents silent deadlock — it raises a clear error.
- **Timestamp precision**: Both showinfo and the old ffprobe report `pts_time` as floating-point seconds. Values should match exactly for the same frames, but if minor drift occurs, seek-based re-extraction still lands on the correct keyframe (input seeking snaps to the nearest keyframe).
- **Thread cleanup**: The `finally` block in `extract_iframes_scaled()` terminates the ffmpeg process, which closes stderr, which causes the reader thread to exit its read loop and push the `None` sentinel. The main thread joins the thread with a timeout to prevent hangs.
- **Future optimization**: If the ~2s batch extraction becomes a bottleneck (unlikely at ~20 frames), it could be parallelized with `concurrent.futures.ThreadPoolExecutor`. Not needed now.

## Review Notes
- Adversarial review completed
- Findings: 14 total, 7 fixed, 2 acknowledged (minor/compat), 5 noise/invalid
- Resolution approach: auto-fix
- Fixed: explicit scale dimensions (F1), queue.Empty handling (F2), double grayscale elimination (F3), aspect ratio warning restored (F4), stderr pipe close (F5), reused get_video_info result (F6), zero-frame warning (F7)
- Acknowledged: duplicate get_video_info (minor overhead), dead code kept for backward compatibility
