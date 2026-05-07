---
title: 'Black Screen Detector ROI Debugger'
slug: 'bsd-roi-debugger'
created: '2026-02-25'
status: 'completed'
stepsCompleted: [1, 2, 3, 4]
tech_stack: [Python 3, OpenCV (cv2), NumPy, PyYAML, FFmpeg (subprocess)]
files_to_modify: ['tools/bsd_roi_debugger.py (new)']
code_patterns: ['argparse CLI with positional video arg', 'yaml.safe_load config loading', 'sys.path.insert for utils import', 'extract_iframes_scaled yields (frame, timestamp)', 'ROI scaling via scale_roi(roi, ref_scale)', 'cv2.rectangle for annotation']
test_patterns: ['none — no test framework; manual testing against real video files']
---

# Tech-Spec: Black Screen Detector ROI Debugger

**Created:** 2026-02-25

## Overview

### Problem Statement

When the black screen detector misclassifies frames (e.g., lobby frames as "not all black"), there is no way to see why — which ROI failed, what the actual brightness values are, or what the ROI regions look like on the frame. This makes tuning ROI zones and thresholds a blind guessing game.

### Solution

A standalone diagnostic CLI script that processes a time range of I-frames and for each frame: prints per-ROI mean brightness with pass/fail status, and exports the scaled frame as a PNG with ROI rectangles drawn on it (colored by pass/fail).

### Scope

**In Scope:**
- Standalone CLI script (`tools/bsd_roi_debugger.py`)
- Reuses existing utils: `extract_iframes_scaled`, `to_grayscale`, `extract_roi`, `is_black` from `utils/`
- Accepts a time range via CLI (e.g., `--range 0:15` for first 15 seconds)
- Per-frame console output: timestamp, each ROI name + mean brightness + black/not-black verdict
- Per-frame PNG export: scaled frame with ROI rectangles drawn (green = black/pass, red = not-black/fail)
- Uses the same `config/config.yaml` as the main detector

**Out of Scope:**
- Changes to the main black screen detector (`tools/black_screen_detector.py`)
- Full-resolution frame export (scaled frames are sufficient for debugging)
- Any GUI or interactive mode

## Context for Development

### Codebase Patterns

- Tools live in `tools/` as standalone CLI scripts with `argparse`
- Shared utilities in `utils/image.py` and `utils/video.py` — stateless functions
- Config loaded from `config/config.yaml` via `yaml.safe_load`
- ROIs defined at reference resolution (1920x1080) and scaled to processing height via `scale_roi()`
- `is_black()` uses `np.mean(region) <= threshold`
- `sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))` at top of tool scripts for utils import
- `extract_iframes_scaled(video_path, target_height)` yields `(frame, timestamp)` — frames arrive pre-scaled as BGR numpy arrays
- Drawing uses OpenCV: `cv2.rectangle(frame, (x,y), (x+w,y+h), color, thickness)` — green `(0,255,0)` for pass, red `(0,0,255)` for fail
- Brightness value obtained via `float(np.mean(region))` — same calc used by `is_black()` internally

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `tools/black_screen_detector.py` | Reference for CLI structure, config loading, ROI scaling pattern (lines 27-31, 68-100) |
| `utils/image.py` | `to_grayscale`, `scale_roi`, `extract_roi`, `is_black` — all directly reusable |
| `utils/video.py` | `extract_iframes_scaled` (line 225) — single-pass I-frame extraction with scaling |
| `config/config.yaml` | ROI zone definitions, threshold, processing target_height |

### Technical Decisions

- Standalone script to avoid mixing debug code into production detector
- Reuse all existing utils — no duplication of image/video processing logic
- ROI rectangles drawn on the scaled (processing-resolution) frame, since this is for visual debugging of what the detector actually sees
- Time range filtering done by skipping/breaking on timestamps from `extract_iframes_scaled` — no need for separate ffmpeg seek
- Report `np.mean()` per ROI explicitly alongside pass/fail, so the user sees how close a region is to the threshold

## Implementation Plan

### Tasks

- [x] Task 1: Create `tools/bsd_roi_debugger.py` with CLI scaffold
  - File: `tools/bsd_roi_debugger.py` (new)
  - Action: Create the script with:
    - `sys.path.insert(0, ...)` pattern for utils import (same as `black_screen_detector.py`)
    - Imports: `argparse`, `os`, `sys`, `cv2`, `yaml`, `numpy as np`
    - Imports from utils: `extract_iframes_scaled`, `get_video_info` from `utils.video`; `to_grayscale`, `scale_roi`, `extract_roi`, `is_black` from `utils.image`
    - `load_config(config_path)` function (same pattern as detector)
    - `parse_range(range_str)` helper: parses `"START:END"` string into `(float, float)` tuple. Supports `"0:15"`, `":15"` (start=0), `"400:"` (end=infinity). Raises `ValueError` on invalid format.
    - `argparse` CLI with: positional `video`, `--range` (default `"0:15"`), `-o/--output-dir` (default `./output/debug`), `-c/--config` (default `config/config.yaml`), `--threshold` override
    - `if __name__ == "__main__": main()` entry point

- [x] Task 2: Implement the core processing loop
  - File: `tools/bsd_roi_debugger.py`
  - Action: Implement `run(video_path, output_dir, config, time_range, threshold_override)`:
    - Load config values: `ref_h`, `target_height`, `threshold`, `roi_zones` (same as detector)
    - Scale ROIs using `scale_roi(roi, ref_scale)` for each zone
    - Iterate `extract_iframes_scaled(video_path, target_height)`:
      - Skip frames where `timestamp < time_range[0]`
      - Break when `timestamp > time_range[1]`
      - For each frame in range:
        1. Convert to grayscale: `gray = to_grayscale(frame)`
        2. For each scaled ROI: extract region, compute `mean_val = float(np.mean(region))`, check `is_black(region, threshold)`
        3. Print console line: `"  {timestamp:.1f}s | {roi_name}: {mean_val:.1f} {'BLACK' if black else 'FAIL'} | ..."`
        4. Also print overall verdict: `"  → ALL BLACK"` or `"  → NOT ALL BLACK ({failing_roi_names})"`

- [x] Task 3: Implement annotated frame export
  - File: `tools/bsd_roi_debugger.py`
  - Action: After computing ROI results for a frame, draw annotations on the BGR frame (before grayscale was applied — use the original `frame` from the iterator):
    - For each scaled ROI: `cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)` where color is `(0, 255, 0)` (green) if black, `(0, 0, 255)` (red) if not black
    - Add ROI label + brightness value: `cv2.putText(frame, f"{roi_name}: {mean_val:.1f}", (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1)`
    - Add timestamp label: `cv2.putText(frame, f"{timestamp:.1f}s", (5, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255,255,255), 1)`
    - Export: `cv2.imwrite(os.path.join(output_dir, f"debug_{timestamp:.1f}s.png"), frame)`
  - Notes: Use the annotated frame copy (not grayscale). `putText` y-offset of -5 above rectangle keeps labels from overlapping the ROI.

- [x] Task 4: Wire up `main()` with validation and summary
  - File: `tools/bsd_roi_debugger.py`
  - Action: In `main()`:
    - Validate video file exists, config file exists (same pattern as detector)
    - Parse `--range` with `parse_range()`
    - Call `run()` and collect frame count
    - Print summary: frames analyzed, output directory, range processed
    - `os.makedirs(output_dir, exist_ok=True)` before processing

### Acceptance Criteria

- [ ] AC 1: Given a video file and `--range 0:15`, when running `bsd_roi_debugger.py`, then it prints per-ROI brightness values and black/not-black verdicts for every I-frame with timestamp between 0s and 15s.
- [ ] AC 2: Given a video file and `--range 0:15`, when running the debugger, then it exports one annotated PNG per I-frame in the range to the output directory, with colored rectangles (green=black, red=not-black) drawn on each ROI zone.
- [ ] AC 3: Given an invalid video path, when running the debugger, then it prints an error message to stderr and exits with code 1.
- [ ] AC 4: Given `--range 400:420`, when running the debugger, then only frames in that time window are processed — frames before 400s are skipped, iteration stops after 420s.
- [ ] AC 5: Given `--threshold 25` override, when running the debugger, then the override threshold is used for all is_black checks instead of the config value.
- [ ] AC 6: Given a range with no I-frames (e.g., video is shorter than the range start), when running the debugger, then it prints "No frames found in range" and exits cleanly.
- [ ] AC 7: Given the debugger output, when inspecting the annotated PNGs, then each ROI rectangle label shows the ROI name and exact mean brightness value (e.g., "minimap: 4.2").

## Additional Context

### Dependencies

- Same dependencies as the main detector: OpenCV (`cv2`), NumPy, PyYAML, FFmpeg on PATH
- No new dependencies required

### Testing Strategy

- **Manual testing:** Run against a known video file with `--range 0:15` and visually inspect:
  - Console output shows per-ROI brightness values for each frame
  - Exported PNGs show correctly positioned ROI rectangles with correct color coding
  - Compare brightness values against the `brightness_threshold` in config to verify pass/fail logic
- **Edge case testing:** Run with `--range 9999:10000` on a short video to verify "No frames found" behavior
- **Threshold override:** Run with `--threshold 50` and verify that previously-failing ROIs now pass

### Notes

- This tool processes all I-frames through ffmpeg even for frames outside the range (it skips/breaks in Python). For very long videos with a late range, this is inefficient but acceptable for a debug tool. Future optimization could add ffmpeg `-ss` seeking if needed.
- The annotated PNGs are at processing resolution (360p by default), not full resolution. This is intentional — it shows exactly what the detector sees.
- ROI label placement (`y-5` above the rectangle) may clip at the top of the frame for ROIs starting at y=0. The label will still be partially visible.
