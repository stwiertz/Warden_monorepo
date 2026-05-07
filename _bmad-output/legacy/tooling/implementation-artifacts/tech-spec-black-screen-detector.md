---
title: 'Black Screen Detector'
slug: 'black-screen-detector'
created: '2026-02-24'
status: 'completed'
stepsCompleted: [1, 2, 3, 4]
tech_stack: ['Python 3', 'FFmpeg (subprocess)', 'OpenCV (cv2)', 'PyYAML', 'argparse (stdlib)']
files_to_modify: ['config/config.yaml', 'utils/__init__.py', 'utils/video.py', 'utils/image.py', 'tools/black_screen_detector.py', 'requirements.txt']
code_patterns: ['modular utils for cross-tool reuse', 'config separated from code (YAML)', 'single-file CLI entry points under tools/', 'FFmpeg via subprocess (not library bindings)']
test_patterns: ['manual validation against known recordings (formal testing deferred to Tool 4)']
---

# Tech-Spec: Black Screen Detector

**Created:** 2026-02-24

## Overview

### Problem Statement

EVA session recordings (up to 2 hours each) contain multiple rounds separated by black screen transitions. To build the map identification pipeline, end-of-round frames must be extracted automatically. Manual extraction is impractical at scale. This tool is also the reference implementation for the same detection algorithm that will run on mobile.

### Solution

A Python CLI tool that iterates through I-frames only (via FFmpeg), checks two specific ROI zones for blackness, and when both zones are simultaneously black, exports the immediately preceding I-frame as a PNG. After each detection, it skips ~15 seconds of I-frames to avoid duplicate detections from consecutive loading screens.

### Scope

**In Scope:**

- Single video file as input (CLI argument)
- I-frame-only extraction via FFmpeg subprocess
- Downscale frames for processing (e.g., 270p–360p)
- Grayscale conversion for black detection
- Two ROI zones (minimap + map_name), both must be black simultaneously
- ROI coordinates defined at 1920x1080, scaled proportionally on downscale
- Configurable brightness threshold
- Export previous I-frame as PNG on black detection
- Timestamp-based output naming: `frame_MMmSSs.png`
- ~15s skip after each detection to avoid duplicates
- Simple `argparse` CLI interface

**Out of Scope:**

- Batch/directory processing (single video only)
- Any graphical UI
- Map identification (Tool 3)
- Frame labeling (Tool 2)
- Validation/accuracy testing (Tool 4)

## Context for Development

### Codebase Patterns

- **Clean slate** — greenfield project, no legacy constraints
- CLI-only tools, no UI
- **Modular structure:** shared `utils/` for cross-tool reuse, `tools/` for CLI entry points, `config/` for external configuration
- Config separated from code via YAML
- FFmpeg via subprocess (not Python bindings) for video decoding
- OpenCV for image processing only (resize, grayscale, ROI crop)

### Project Structure

```
warden-tooling/
├── config/
│   └── config.yaml                  — ROI zones, thresholds, skip duration
├── utils/
│   ├── __init__.py
│   ├── video.py                     — FFmpeg I-frame extraction (reusable)
│   └── image.py                     — resize, grayscale, ROI scaling (reusable)
├── tools/
│   └── black_screen_detector.py     — CLI entry point, detection logic
├── requirements.txt
```

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `description.md` | Detailed algorithm description and full pipeline overview |
| `_bmad-output/project-sprint.md` | Sprint tracker with shared decisions and success criteria |

### Files to Create

| File | Purpose |
| ---- | ------- |
| `config/config.yaml` | ROI zones (at 1080p), brightness threshold, skip duration, output settings |
| `utils/__init__.py` | Package init |
| `utils/video.py` | FFmpeg subprocess wrapper for I-frame extraction — reusable by Tool 4 |
| `utils/image.py` | Downscale, grayscale conversion, ROI extraction/scaling — reusable by Tool 3, 4 |
| `tools/black_screen_detector.py` | Main CLI tool: orchestration, argparse, calls utils |
| `requirements.txt` | opencv-python, pyyaml |

### Technical Decisions

- **FFmpeg over OpenCV for video decoding:** OpenCV's `VideoCapture` cannot selectively decode only I-frames. FFmpeg subprocess is required for keyframe-only iteration.
- **ROI-based detection:** Full-frame black check would produce false positives. Two specific zones (minimap top-left, map_name center) must both be black simultaneously.
- **ROI coordinates at 1080p:** minimap `(x:104, y:0, w:38, h:234)`, map_name `(x:827, y:79, w:264, h:22)`. Scale proportionally when processing at lower resolution.
- **Previous frame export:** On black detection, export the I-frame immediately before the black frame (the end-of-round screen).
- **15s skip logic:** After detecting a black screen, skip forward ~15 seconds of I-frames before resuming detection to avoid duplicate detections from consecutive loading screens.
- **Config in YAML:** All tunable values (ROI zones, thresholds, skip duration) live in `config/config.yaml`, not hardcoded.
- **Shared utils:** `video.py` and `image.py` designed for reuse across all 4 pipeline tools.
- **argparse for CLI:** Standard library, no extra dependencies.

## Implementation Plan

### Tasks

- [x] Task 1: Create project config file
  - File: `config/config.yaml`
  - Action: Define all configurable values — ROI zones at 1080p reference resolution, brightness threshold, skip duration, default processing resolution. Structure ROIs as a list with `name`, `x`, `y`, `width`, `height` fields. Include `reference_resolution` (1920x1080) so scaling math is explicit.
  - Notes: This is the single source of truth for all tunable parameters. Other tools will extend this file later.

- [x] Task 2: Create requirements file
  - File: `requirements.txt`
  - Action: Add `opencv-python` and `pyyaml`. Pin major versions for reproducibility.

- [x] Task 3: Create utils package init
  - File: `utils/__init__.py`
  - Action: Empty init file to make `utils` importable as a package.

- [x] Task 4: Create video utility — FFmpeg I-frame extraction
  - File: `utils/video.py`
  - Action: Implement a generator function that yields `(numpy_array, timestamp_seconds)` tuples for each I-frame in a video file.
  - Implementation approach:
    1. Use `ffprobe` to get video dimensions (width, height) and list all I-frame PTS timestamps.
    2. Run `ffmpeg` with `-skip_frame nokey` to decode only keyframes, pipe raw BGR24 bytes to stdout via `-f rawvideo -pix_fmt bgr24 pipe:1`. Use `-vsync 0` to prevent frame duplication.
    3. Read exactly `width * height * 3` bytes per frame from the pipe, reshape to numpy array `(height, width, 3)`.
    4. Pair each frame with the corresponding timestamp from the ffprobe list (both iterate in presentation order).
  - Include a helper function to validate that `ffmpeg` and `ffprobe` are available on PATH.
  - Notes: This module must not import OpenCV — it only deals with FFmpeg and numpy. This keeps it reusable without pulling in image processing dependencies where not needed.

- [x] Task 5: Create image utility — processing helpers
  - File: `utils/image.py`
  - Action: Implement reusable image processing functions using OpenCV:
    1. `downscale(frame, target_height)` — Resize frame proportionally to target height, return resized frame and the scale factor used.
    2. `to_grayscale(frame)` — Convert BGR frame to single-channel grayscale.
    3. `scale_roi(roi, scale_factor)` — Scale an ROI dict's `x`, `y`, `width`, `height` from reference resolution to processing resolution using the given scale factor. Return new ROI with integer coordinates.
    4. `extract_roi(frame, roi)` — Crop the ROI region from a frame, return the cropped region.
    5. `is_black(region, threshold)` — Check if the mean pixel value of a grayscale region is below the brightness threshold. Return boolean.
  - Notes: All functions are stateless and reusable. Tool 3 and Tool 4 will reuse `downscale`, `extract_roi`, and `scale_roi`.

- [x] Task 6: Create the Black Screen Detector CLI tool
  - File: `tools/black_screen_detector.py`
  - Action: Implement the main detection tool with the following structure:
    1. **CLI arguments** (argparse):
       - `video` (positional) — path to input video file
       - `--output-dir` / `-o` — output directory for extracted frames (default: `./output`)
       - `--config` / `-c` — path to config file (default: `config/config.yaml`)
       - `--threshold` — brightness threshold override (optional, overrides config value)
    2. **Config loading**: Read YAML config, extract ROI zones, threshold, skip duration, processing resolution.
    3. **Detection loop**:
       - Call `utils.video.extract_iframes()` to get the I-frame generator
       - For each frame: downscale via `utils.image.downscale()`, convert to grayscale, scale ROIs, extract both ROI regions, check if both are black
       - Track `previous_frame` (full resolution, BGR — for export) and `previous_timestamp`
       - When both ROIs are black: save `previous_frame` as PNG to output dir with filename `frame_MMmSSs.png`, then skip I-frames until timestamp exceeds `current_timestamp + skip_duration`
       - For the very first I-frame, there is no "previous frame" — just store it and continue
    4. **Output**: Print summary to stdout — number of transitions detected, output directory path, list of exported filenames.
  - Notes: The previous frame must be kept at full resolution (before downscale) so exports are high quality. Only the black detection check operates on the downscaled/grayscale version.

### Acceptance Criteria

- [x] AC 1: Given a video file with black screen transitions between rounds, when the tool is run, then it exports one PNG per transition containing the end-of-round frame (the I-frame immediately preceding the first black I-frame).

- [x] AC 2: Given a video file, when processing, then only I-frames are decoded (verified by FFmpeg `-skip_frame nokey` flag), not every frame in the video.

- [x] AC 3: Given an I-frame being checked, when evaluating blackness, then both ROI zones (minimap and map_name) must have mean brightness below the threshold simultaneously for the frame to be considered black.

- [x] AC 4: Given a black screen is detected, when resuming detection, then all I-frames within the next ~15 seconds (configurable `skip_duration`) are skipped before detection resumes.

- [x] AC 5: Given exported frames, when checking filenames, then each follows the format `frame_MMmSSs.png` where MM is zero-padded minutes and SS is zero-padded seconds (e.g., `frame_05m23s.png`).

- [x] AC 6: Given ROI coordinates defined at 1920x1080, when processing at a lower resolution, then ROI coordinates are scaled proportionally using the downscale factor, and detection still works correctly.

- [x] AC 7: Given an invalid video path, when the tool is run, then it exits with a clear error message and non-zero exit code.

- [x] AC 8: Given the output directory does not exist, when the tool is run, then it creates the directory automatically.

- [x] AC 9: Given a video with no black screen transitions, when the tool is run, then it completes without error and exports zero frames, printing a summary indicating no transitions found.

- [x] AC 10: Given all configurable values (ROI zones, threshold, skip duration, processing resolution), when the tool is run, then all values are read from `config/config.yaml` with no hardcoded defaults in the detection logic.

## Additional Context

### Dependencies

- `opencv-python` — image processing (resize, grayscale, pixel read)
- `pyyaml` — config file parsing
- `ffmpeg` — must be installed on system PATH (not a Python package)
- Python 3.8+ (f-strings, subprocess improvements)

### Testing Strategy

- **Manual validation**: Run the tool against a known EVA recording where transitions have been manually counted. Verify:
  - Correct number of frames exported (matches manual count)
  - Each exported frame is an end-of-round screen (not a black frame, not a mid-round frame)
  - No duplicate exports for the same transition
  - Timestamps in filenames are reasonable
- **Threshold tuning**: If false positives or missed detections occur, adjust `brightness_threshold` in config and re-run. Start with a conservative value (e.g., 10–15 out of 255) and increase if needed.
- **Formal validation**: Deferred to Tool 4, which will run automated accuracy reports against labeled ground truth.

### Notes

- This tool's output (extracted frames) feeds directly into Tool 2 (Frame Labeling)
- Threshold values validated here should transfer directly to mobile implementation
- Success criteria: 100% transition detection, 0 false positives
- **Risk — FFmpeg frame/timestamp sync**: The approach of pairing piped raw frames with ffprobe timestamps assumes both iterate in the same order. If a video has unusual encoding (B-frame reordering), this could desync. Mitigation: use `-vsync 0` and verify on test videos.
- **Risk — ROI coordinates**: The provided ROI values are for 1080p. If source recordings are at a different resolution, the reference resolution in config must be updated to match.
- **Future**: When Tool 4 is built, it will reuse `utils/video.py` for end-to-end pipeline testing.

## Review Notes

- Adversarial review completed
- Findings: 15 total, 14 fixed, 1 skipped (noise)
- Resolution approach: auto-fix
- Key fixes applied:
  - F1 (Critical): Added frame count mismatch warning between ffprobe/ffmpeg
  - F2 (High): Added aspect ratio validation for non-1080p source video
  - F3 (High): Added bounds checking and truncation warnings to extract_roi
  - F4 (High): Added descriptive RuntimeError for missing video streams
  - F9 (Medium): Redirected FFmpeg stderr to temp file (avoids pipe deadlock) with error reporting
  - F6 (Medium): Added sequence counter to filenames for collision prevention
  - F7 (Medium): Skip resize when target >= source height
  - F10 (Medium): Changed to <= for threshold comparison
- Skipped: F14 (noise — explicit numpy pin is intentional for reproducibility)
