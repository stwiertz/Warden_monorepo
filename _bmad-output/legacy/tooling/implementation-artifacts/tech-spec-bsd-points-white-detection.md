---
title: 'Points ROI White Detection — In-Game State Classifier'
slug: 'bsd-points-white-detection'
created: '2026-03-09'
status: 'completed'
stepsCompleted: [1, 2, 3, 4]
tech_stack: [python, opencv, ffmpeg, numpy]
files_to_modify: ['tools/points_state_detector.py (new)', 'utils/image.py (add has_white_pixels)']
code_patterns: ['ROI defined at 1920x1080 ref resolution, scaled via scale_roi()', 'Single-pipe I-frame extraction via extract_iframes_scaled()', 'Deferred batch full-res extraction via extract_frame_at_timestamp()', 'CLI pattern: argparse with -o, -c, --profile flags', 'Output format: MMmSSs_type_seq.png']
test_patterns: ['tests/ directory exists, no framework established yet']
---

# Tech-Spec: Points ROI White Detection — In-Game State Classifier

**Created:** 2026-03-09

## Overview

### Problem Statement

The current black screen detector (BSD) relies on catching black loading screens to infer game transitions. This has two weaknesses: (1) high-GOP videos may not have I-frames during the brief black screen, requiring a complex two-pass workaround, and (2) the team bar saturation prescan ROI is questionable. A method that can positively classify every frame as "in-game" or "lobby" would be more robust, especially for high-GOP videos.

### Solution

A new parallel tool that checks the `points` ROI (608, 27, 64×15 at 1920×1080) for white pixels using HSV thresholds (S: 0–5, V: 90–100 on a 0–100 scale). White text present in the points area means we're in-game; absence means lobby or loading screen. Since every frame can be classified independently, this approach doesn't depend on catching a specific black frame and naturally handles high-GOP videos without a two-pass strategy. The tool produces the same output as BSD — timestamped transition PNGs with start/end labels.

### Scope

**In Scope:**
- New standalone tool (`tools/points_state_detector.py`)
- Per-frame in-game/lobby classification via `points` ROI white detection
- Transition detection (in-game → lobby = end, lobby → in-game = start)
- Same CLI interface and output format as BSD (timestamped PNGs, start/end labels)
- Works on any frame type — no two-pass needed for high-GOP videos

**Out of Scope:**
- Replacing the existing black screen detector
- Map identification or end-screen content extraction
- Modifying the existing BSD pipeline

## Context for Development

### Codebase Patterns

- ROI coordinates defined at reference resolution (1920×1080) in `config/config.yaml`, scaled via `scale_roi()` to processing resolution
- The `points` ROI already exists in config: `x:608, y:27, w:64, h:15`
- HSV thresholds for "white": S 0–5, V 90–100 (on 0–100 scale → OpenCV 0–255: S 0–12.75, V 229.5–255)
- Single-pipe I-frame extraction: `extract_iframes_scaled()` yields `(frame, timestamp)` tuples — BGR frames pre-scaled to `target_height`
- Deferred batch export: collect extraction requests during detection, then batch-extract full-res frames via `extract_frame_at_timestamp()`
- CLI pattern: `argparse` with `-o OUTPUT_DIR`, `-c CONFIG`, `--profile` flags
- Output: `MMmSSs_type_seq.png` filenames, video-named subfolder inside output dir
- `utils/config.py` provides `load_config()` for YAML loading

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `tools/black_screen_detector.py` | Reference for CLI interface, output format, state machine, deferred extraction |
| `config/config.yaml` | ROI definitions (`points` at line 62), thresholds, reference resolution |
| `utils/image.py` | `scale_roi()`, `extract_roi()`, `to_grayscale()`, `has_team_color()` — add `has_white_pixels()` here |
| `utils/video.py` | `extract_iframes_scaled()`, `extract_frame_at_timestamp()`, `get_video_info()`, `get_gop_interval()` |
| `utils/config.py` | `load_config()` for YAML config loading |

### Technical Decisions

- **HSV white detection**: Convert BGR ROI to HSV, check pixel ratio with S ≤ 12 and V ≥ 230 (OpenCV 0–255 scale, rounded from 0–100 input)
- **Pixel ratio threshold needed**: Not every pixel will be white — need a minimum % of white pixels in the ROI to classify as "in-game" (e.g., 5–10% — to be tuned)
- **Simpler state machine**: Two states only — `in_game` (white detected) vs `not_in_game`. Transitions trigger exports
- **No two-pass**: Every I-frame is classified independently, no dependency on catching black screens
- **Same output format**: Matching BSD for direct comparison of results
- **Confirmation frames**: Reuse `start_confirm_frames` concept to avoid false triggers on transient frames

## Implementation Plan

### Tasks

- [x] Task 1: Add `has_white_pixels()` to `utils/image.py`
  - File: `utils/image.py`
  - Action: Add a new function after `has_team_color()`:
    ```python
    def has_white_pixels(region, sat_max=12, val_min=230, min_ratio=0.05):
    ```
  - Logic:
    1. Validate input is 3-channel BGR (same guard as `has_team_color()`)
    2. Convert BGR → HSV via `cv2.cvtColor(region, cv2.COLOR_BGR2HSV)`
    3. Create mask: `(hsv[:,:,1] <= sat_max) & (hsv[:,:,2] >= val_min)`
    4. Compute ratio of white pixels: `np.count_nonzero(mask) / mask.size`
    5. Return `ratio >= min_ratio`
  - Notes: Default thresholds derived from user spec (S 0–5 on 100 scale → 0–12.75 on 255 → 12 rounded; V 90–100 on 100 → 229.5–255 → 230 rounded). `min_ratio` default of 0.05 (5%) is a starting point — the points text won't fill the entire ROI.

- [x] Task 2: Add `points_detection` config section to `config/config.yaml`
  - File: `config/config.yaml`
  - Action: Add a new section after `team_bar_detection`:
    ```yaml
    # Points ROI white detection — classifies in-game vs lobby by white text presence
    points_detection:
      sat_max: 12          # Max saturation (0-255) for white classification
      val_min: 230         # Min value (0-255) for white classification
      min_ratio: 0.05      # Min fraction of white pixels to classify as in-game
      skip_duration: 15.0  # Seconds to skip after detecting an end transition
      confirm_frames: 2    # Consecutive frames to confirm a start transition
    ```
  - Notes: Keeps thresholds configurable and separate from BSD settings. Uses the existing `points` ROI from `roi_zones`.

- [x] Task 3: Create `tools/points_state_detector.py`
  - File: `tools/points_state_detector.py` (new)
  - Action: Create the main detection tool with the following structure:

  - **3a. Module docstring and imports**
    - Docstring matching BSD style describing the tool purpose
    - Same `sys.path` hack as BSD (line 18)
    - Imports: `argparse`, `os`, `sys`, `time`, `cv2`
    - From utils: `load_config`, `extract_iframes_scaled`, `extract_frame_at_timestamp`, `get_video_info`, `scale_roi`, `extract_roi`, `has_white_pixels`

  - **3b. `format_timestamp()` helper**
    - Identical to BSD: `MMmSSs` format

  - **3c. `run()` function**
    - Signature: `run(video_path, output_dir, config, profile=False)`
    - Extract config: `reference_resolution`, `processing.target_height`, `points_detection.*`
    - Find the `points` ROI from `roi_zones` by name, scale it via `scale_roi()`
    - Aspect ratio warning (same as BSD)
    - State machine with two states:
      - `not_in_game` (initial): looking for white → transition to `in_game` (= start)
      - `in_game`: looking for no white → transition to `not_in_game` (= end)
    - For each I-frame from `extract_iframes_scaled()`:
      1. Extract the `points` ROI from the BGR frame (no grayscale conversion needed)
      2. Call `has_white_pixels(region, sat_max, val_min, min_ratio)`
      3. State machine logic:
         - **not_in_game → in_game**: White detected. Apply confirmation logic (N consecutive frames with white before firing). Record start extraction request at the first confirming frame's timestamp.
         - **in_game → not_in_game**: No white detected. Record end extraction request at the previous frame's timestamp (last known in-game frame). Apply `skip_duration`.
    - Deferred batch extraction: after detection loop, extract full-res frames via `extract_frame_at_timestamp()` and save as PNGs
    - Return: `(exported, frame_count, profile_stats)` — same shape as BSD minus `miss_reports` (not needed for v1)

  - **3d. `main()` function**
    - CLI args matching BSD: `video` (positional), `-o/--output-dir`, `-c/--config`, `--profile`
    - Validate input video and config exist
    - Load config via `load_config()`
    - Resolve output dir (CLI > config default), create video-named subfolder
    - Call `run()`, print summary matching BSD format (frames processed, ends detected, starts detected, exported frames list)
    - Print profile report if `--profile`

### Acceptance Criteria

- [ ] AC 1: Given a video with in-game footage containing visible score text, when `points_state_detector.py` processes the video, then frames with white pixels in the `points` ROI (S ≤ 12, V ≥ 230, ratio ≥ 5%) are classified as `in_game`.

- [ ] AC 2: Given a video with lobby/loading screens where the points area is absent or dark, when `points_state_detector.py` processes the video, then those frames are classified as `not_in_game`.

- [ ] AC 3: Given a transition from in-game to lobby (white disappears from points ROI), when detected, then an `end` frame is exported using the previous frame's timestamp, with filename format `MMmSSs_end_NNN.png`.

- [ ] AC 4: Given a transition from lobby to in-game (white appears in points ROI), when detected and confirmed over `confirm_frames` consecutive frames, then a `start` frame is exported using the first confirming frame's timestamp, with filename format `MMmSSs_start_NNN.png`.

- [ ] AC 5: Given `skip_duration` is configured, when an end transition is detected, then subsequent frames within `skip_duration` seconds are skipped to avoid duplicate detections.

- [ ] AC 6: Given a video file path that does not exist, when the tool is invoked, then it prints an error message to stderr and exits with code 1.

- [ ] AC 7: Given no transitions are found in a video, when processing completes, then the summary reports 0 events and no files are exported.

- [ ] AC 8: Given `--profile` flag is passed, when processing completes, then a timing breakdown is printed (wall time, frames processed, per-phase times).

- [ ] AC 9: Given the same video processed by both BSD and `points_state_detector`, when comparing outputs, then both tools produce PNG files in the same output format (`MMmSSs_type_seq.png`) in a video-named subfolder.

## Additional Context

### Dependencies

- No new external dependencies — uses existing `opencv-python`, `numpy`, `pyyaml`, and system `ffmpeg`
- Reuses all existing utilities from `utils/image.py`, `utils/video.py`, `utils/config.py`

### Testing Strategy

- **Manual comparison test**: Run both BSD and `points_state_detector` on the same video, compare detected transition timestamps. Differences highlight where each method succeeds/fails.
- **Threshold tuning**: Use the existing `tools/image_inspector/` or `tools/bsd_roi_debugger.py` to visually inspect the `points` ROI on sample frames and verify the HSV thresholds catch white text reliably.
- **Edge cases to test manually**:
  - Video starting in-game (first frame has white points)
  - Video starting in lobby (first frame has no white points)
  - Very short games (quick transitions)
  - High-GOP video where BSD struggles (primary motivation)

### Notes

- The `min_ratio` threshold (5% default) may need tuning based on real video data. The points ROI is small (64×15 = 960 pixels at 1080p), so even a few white characters should hit 5%.
- This tool intentionally does not include recovery/miss detection logic (unlike BSD). If v1 proves reliable, recovery logic can be added later.
- The `points` ROI position assumes standard 1920×1080 game UI layout. Non-standard resolutions or UI scaling may shift the score text outside this ROI.

## Review Notes
- Adversarial review completed
- Findings: 14 total, 5 fixed, 9 skipped (noise/undecided/out-of-scope)
- Resolution approach: auto-fix
- Fixed: F1 (print after null), F2 (falsy 0.0 trap), F3 (zero-size ZeroDivisionError), F4+F5 (end-of-video warnings), F11 (traceback on error)
