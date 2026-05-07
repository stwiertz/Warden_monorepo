---
title: 'Black Screen Detector Profiling & --profile Flag'
slug: 'bsd-profiling'
created: '2026-02-25'
status: 'completed'
stepsCompleted: [1, 2, 3, 4]
tech_stack: [Python 3.8+, OpenCV (cv2), FFmpeg (subprocess), NumPy, PyYAML]
files_to_modify: [tools/black_screen_detector.py, utils/video.py]
code_patterns: [generator-based frame streaming, stateless utility functions, config-driven YAML, argparse CLI]
test_patterns: [no test suite — manual validation against sample videos]
---

# Tech-Spec: Black Screen Detector Profiling & --profile Flag

**Created:** 2026-02-25

## Overview

### Problem Statement

Tool 1 (Black Screen Detector) has unknown performance characteristics. When processing long gameplay recordings, it's unclear where time is spent — FFmpeg decoding, image processing, frame copies, or disk I/O — and whether the pipeline is already optimized or has room for improvement.

### Solution

Add a `--profile` flag to the CLI that instruments each phase of the processing loop and outputs a timing breakdown report at the end, showing total time, per-phase totals/averages, and percentage breakdown.

### Scope

**In Scope:**
- Timing instrumentation across all distinct phases: ffprobe keyframe scan, ffmpeg frame read, `downscale()`, `to_grayscale()`, ROI extraction + `is_black()`, `frame.copy()`, `cv2.imwrite()`, and skip-path overhead
- Summary report at the end: total wall time, per-phase totals, per-phase averages per frame, percentage breakdown
- `--profile` CLI flag (profiling is off by default, zero overhead when not used)

**Out of Scope:**
- Implementing optimizations (the report reveals if there's room)
- Profiling tools 2-4
- Memory profiling

## Context for Development

### Codebase Patterns

- CLI tools live in `tools/` with argparse-based `main()`
- Shared utilities in `utils/` (stateless functions, no side effects)
- Config loaded from `config/config.yaml` via `yaml.safe_load()`
- `extract_iframes()` is a generator yielding `(frame, timestamp)` — first `next()` bundles all setup (ffprobe x2 + ffmpeg Popen + first read)
- The `run()` function contains the main processing loop; profiling instrumentation goes here
- No test suite exists — validation is manual against sample videos

### Files to Reference

| File | Purpose | Lines |
| ---- | ------- | ----- |
| `tools/black_screen_detector.py` | Main tool — `run()` loop (L38-194) and CLI `main()` (L197-265) | 265 |
| `utils/video.py` | `extract_iframes()` generator (L91-181), `_get_keyframe_timestamps()` (L67-88), `_get_video_info()` (L38-64) | 182 |
| `utils/image.py` | `downscale()` (L13-34), `to_grayscale()` (L37-46), `extract_roi()` (L68-101), `is_black()` (L104-116) | 117 |
| `config/config.yaml` | Runtime configuration — thresholds, ROI zones, processing params | ~20 |

### Technical Decisions

- Use `time.perf_counter()` for high-resolution wall-clock timing
- Pass an optional `profile_stats` dict through the call chain (`run()` → `extract_iframes()`)
- When `profile_stats is None` (default): zero overhead — just a single `if` guard per instrumentation point
- Instrument inside `extract_iframes()` to separate ffprobe scan time from per-frame ffmpeg decode time
- Print the profiling report in `main()` after `run()` returns, below the normal summary
- Report format: table with phase name, total time, avg per frame, % of total wall time

### Timing Phases Identified

| Phase | Location | Frequency | What It Measures |
|-------|----------|-----------|-----------------|
| `ffprobe_info` | `video.py:_get_video_info()` | Once | ffprobe subprocess for video dimensions |
| `ffprobe_keyframes` | `video.py:_get_keyframe_timestamps()` | Once | ffprobe scan of all keyframe timestamps |
| `ffmpeg_read` | `video.py:proc.stdout.read()` + numpy reshape | Per frame | Raw frame decode + pipe read |
| `downscale` | `image.py:downscale()` via detector | Per non-skipped frame | cv2.resize full-res → 360p |
| `grayscale` | `image.py:to_grayscale()` via detector | Per non-skipped frame | cv2.cvtColor BGR→gray |
| `roi_check` | `image.py:extract_roi()` + `is_black()` via detector | Per non-skipped frame (x2 ROIs) | ROI crop + mean brightness check |
| `frame_copy` | `detector.py:frame.copy()` | Per frame (including skipped!) | Full-resolution numpy array copy |
| `imwrite` | `detector.py:cv2.imwrite()` | Per detection (rare) | PNG encode + disk write |

## Implementation Plan

### Tasks

- [x] Task 1: Instrument `extract_iframes()` with optional profiling
  - File: `utils/video.py`
  - Action: Add an optional `profile_stats=None` parameter to `extract_iframes()`. When provided (a dict), time and record:
    - `ffprobe_info`: wrap `_get_video_info()` call with perf_counter, store total in `profile_stats["ffprobe_info"]`
    - `ffprobe_keyframes`: wrap `_get_keyframe_timestamps()` call with perf_counter, store total in `profile_stats["ffprobe_keyframes"]`
    - `ffmpeg_read`: wrap each `proc.stdout.read(frame_size)` + `np.frombuffer().reshape()` with perf_counter, accumulate in `profile_stats["ffmpeg_read"]`
  - Notes: Add `import time` at top. When `profile_stats is None`, the existing code path is unchanged — only add `if profile_stats is not None:` guards. The generator's yield signature stays `(frame, timestamp)` — timings go into the mutable dict, not the yield.

- [x] Task 2: Add `profile` parameter to `run()` and instrument the processing loop
  - File: `tools/black_screen_detector.py`
  - Action: Add `profile=False` parameter to `run()`. When `True`:
    - Create `profile_stats` dict, pass it to `extract_iframes(video_path, profile_stats=profile_stats)`
    - Wrap `downscale()` call (L142) with perf_counter, accumulate in `profile_stats["downscale"]`
    - Wrap `to_grayscale()` call (L143) with perf_counter, accumulate in `profile_stats["grayscale"]`
    - Wrap the ROI loop (L147-151) with perf_counter, accumulate in `profile_stats["roi_check"]`
    - Wrap `prev_frame = frame.copy()` (L191) with perf_counter, accumulate in `profile_stats["frame_copy"]`
    - Wrap each `cv2.imwrite()` call (L162, L182) with perf_counter, accumulate in `profile_stats["imwrite"]`
    - Record `wall_start` at top of `run()` and `wall_end` at bottom
    - Track `frames_processed` (non-skipped) and `frames_skipped` counts
  - Notes: Add `import time` at top. Return signature changes from `(exported, frame_count)` to `(exported, frame_count, profile_stats)` where `profile_stats` is `None` when profiling is off, or the populated dict when on. The initial-state detection block (L124-133) uses downscale/grayscale/roi too but runs once — include it in the same accumulators.

- [x] Task 3: Add `--profile` CLI flag and print the profiling report
  - File: `tools/black_screen_detector.py`
  - Action:
    - Add `--profile` argument to the argparse parser: `parser.add_argument("--profile", action="store_true", help="Print per-phase timing breakdown after processing")`
    - Pass `profile=args.profile` to `run()`
    - Update the `run()` call to unpack 3 values: `exported, frame_count, profile_stats = run(...)`
    - After the existing summary block, if `profile_stats is not None`, print a profiling report with this format:
      ```
      PROFILE REPORT
      ==================================================
      Wall time:       12.34s
      Frames total:    150 (120 processed, 30 skipped)

      Phase              Total (s)   Avg/frame (ms)    %
      ─────────────────  ──────────  ──────────────  ────
      ffmpeg_read            8.12          54.13     65.8%
      downscale              1.45           12.08    11.8%
      frame_copy             1.20            8.00     9.7%
      grayscale              0.89            7.42     7.2%
      roi_check              0.34            2.83     2.8%
      ffprobe_keyframes      0.22              —      1.8%
      ffprobe_info           0.05              —      0.4%
      imwrite                0.03              —      0.2%
      ─────────────────  ──────────  ──────────────  ────
      Accounted:            12.30                   99.7%
      Unaccounted:           0.04                    0.3%
      ```
    - Sort phases by total time descending
    - For one-time phases (`ffprobe_info`, `ffprobe_keyframes`, `imwrite`), show `—` for avg/frame
    - `Avg/frame` for per-frame phases uses `frames_processed` (non-skipped) as divisor, except `frame_copy` which uses `frame_count` (total including skipped)
    - `Unaccounted` = wall time minus sum of all phases (captures loop overhead, Python interpreter, etc.)
  - Notes: This is the user-facing output. Keep it clean and readable.

### Acceptance Criteria

- [x] AC 1: Given a video file, when `--profile` is NOT passed, then the tool produces identical output to the current version and `profile_stats` is `None` (zero behavioral change).
- [x] AC 2: Given a video file, when `--profile` IS passed, then the tool prints the normal summary followed by a `PROFILE REPORT` section showing all 8 timing phases.
- [x] AC 3: Given the profile report, when reading the output, then each phase shows total seconds, avg per frame in ms (where applicable), and percentage of wall time — sorted by total time descending.
- [x] AC 4: Given the profile report, when summing all phase totals, then `Accounted` + `Unaccounted` equals the reported `Wall time` (no missing time).
- [x] AC 5: Given a video with skipped frames (skip_duration triggers), when `--profile` is passed, then the report shows correct `frames_skipped` count and `frame_copy` avg uses total frame count (not just processed).
- [x] AC 6: Given the `extract_iframes()` function, when called without `profile_stats`, then it behaves identically to the current implementation (backward compatible).
- [x] AC 7: Given `--profile` is not passed, when running the tool, then the only overhead is a single `if profile:` boolean check at the top of `run()` — no timing calls are made.

## Additional Context

### Dependencies

No new dependencies. Uses only `time.perf_counter()` from the Python stdlib, already available in Python 3.3+.

### Testing Strategy

**Manual validation (no test suite exists):**

1. Run without `--profile` on a sample video — confirm output is identical to current behavior
2. Run with `--profile` on a sample video — confirm the profile report prints after the summary
3. Verify all 8 phases appear in the report and percentages sum to ~100%
4. Verify `Accounted` + `Unaccounted` = `Wall time`
5. Run with `--profile` on a video that triggers skip_duration — verify `frames_skipped` is non-zero and `frame_copy` avg uses total count
6. Spot-check: `ffmpeg_read` should dominate (>50%) for typical videos — if not, the instrumentation may be wrong

### Notes

- **Observed bottleneck candidate:** `prev_frame = frame.copy()` copies the full-resolution frame (1920x1080x3 = ~6MB) on every iteration, including skipped frames. The profiler will quantify whether this is significant.
- **Expected result:** `ffmpeg_read` likely dominates, as I-frame decoding from compressed video is computationally expensive. If the Python-side processing (downscale, grayscale, roi_check, frame_copy) is <20% of wall time, the tool is already near-optimal — FFmpeg decode is the floor.
- **Future consideration:** If `frame_copy` turns out to be significant, it could be eliminated by only copying when in `waiting_for_end` state (the copy is only needed for end-detection export). This is an optimization, out of scope for this spec.

## Review Notes
- Adversarial review completed
- Findings: 7 total, 1 fixed, 6 acknowledged (by-design or negligible)
- Resolution approach: auto-fix
- F2 fixed: instrumented `waiting_for_start` minimap ROI check under `roi_check` phase
