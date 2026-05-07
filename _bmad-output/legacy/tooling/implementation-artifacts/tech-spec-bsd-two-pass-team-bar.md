---
title: 'Two-Pass BSD with Team Bar Pre-Scan'
slug: 'bsd-two-pass-team-bar'
created: '2026-03-01'
status: 'completed'
stepsCompleted: [1, 2, 3, 4]
tech_stack: [Python, OpenCV, FFmpeg, NumPy]
files_to_modify: [tools/black_screen_detector.py, utils/image.py, config/config.yaml]
code_patterns: [stateless image functions in utils/image.py, ROI scaling from 1920x1080 reference, ffmpeg subprocess wrappers in utils/video.py, config-driven ROI zones in YAML]
test_patterns: [no formal test suite — validation via manual run on source videos]
---

# Tech-Spec: Two-Pass BSD with Team Bar Pre-Scan

**Created:** 2026-03-01

## Overview

### Problem Statement

For videos with large GOP intervals (>2s), the BSD falls back to 2s interval mode which spawns a separate ffmpeg subprocess per frame. On a 70-minute video this means ~2000 subprocess calls, taking ~700s wall time with 99.6% spent in subprocess overhead. The actual detection processing (grayscale, ROI checks) is negligible at 0.4%.

### Solution

Add a fast two-pass strategy for interval-mode videos. Pass 1 uses the single-pipe I-frame extractor (`extract_iframes_scaled`) to scan GOP keyframes for the presence of a team color bar (orange/blue) in a new bottom-screen ROI. This classifies frames as "in-game" vs "not-in-game" and identifies transition windows. Pass 2 then runs targeted 2s-interval scanning only within narrow windows around those transitions, feeding frames into the existing state machine for exact black screen detection.

### Scope

**In Scope:**
- New ROI zone for the team bar region (bottom 65px, starting 430px from left at 1920x1080)
- Color saturation detection (orange/blue in HSV space) as a new check alongside `is_black`
- Two-pass logic for interval-mode videos: fast GOP scan → targeted window scan
- Expected speedup from ~700s to under a minute for large-GOP videos

**Out of Scope:**
- Changes to the I-frame mode path (GOP <= 2s) — already works fine
- Changes to the state machine logic itself — just feeding it fewer, smarter frames
- Support for team colors beyond orange and blue

## Context for Development

### Codebase Patterns

- All video decoding goes through FFmpeg subprocesses in `utils/video.py` — OpenCV is used only for image processing
- ROI zones are defined at 1920x1080 reference resolution in `config/config.yaml` and scaled proportionally at runtime
- The BSD already has a two-mode split: I-frame mode (GOP <= 2s, single pipe) vs interval mode (GOP > 2s, per-frame subprocess)
- Image analysis functions are stateless in `utils/image.py` (grayscale, ROI extraction, is_black)
- The state machine in `black_screen_detector.py` is frame-source agnostic — it processes `(frame, timestamp)` tuples regardless of source

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `tools/black_screen_detector.py` | Main BSD tool — contains state machine, sampling mode selection, CLI |
| `utils/video.py` | FFmpeg wrappers — `extract_iframes_scaled`, `extract_frames_at_interval` |
| `utils/image.py` | Image processing — `is_black`, `extract_roi`, `to_grayscale`, `scale_roi` |
| `config/config.yaml` | ROI zone definitions, detection thresholds, processing settings |

### Technical Decisions

- **Detection via HSV saturation, not hue**: Pixel analysis confirmed mean saturation is the cleanest discriminator. In-game bar: mean S=136–156. Scoreboard: mean S=50–54. Threshold ~90 separates perfectly. Hue shifts between team colors so is unreliable alone.
- **Bar ROI at 1920x1080**: y:1015–1080, x:430–1490 (bottom 65px, 1060px wide). Distinct from existing top-left ROIs.
- **New `has_team_color()` function**: Add to `utils/image.py`. Takes BGR region, converts to HSV, returns `mean(S) > threshold`. Follows existing stateless pattern.
- **`extract_roi()` already handles BGR**: No change needed — it uses `frame.shape[:2]` which works for both 2D and 3D arrays.
- **Pass 1 is classification only**: Scan I-frames, classify each as "in-game" (high sat) or "not-in-game" (low sat), collect transition timestamps. No state machine needed.
- **Pass 2 windows**: Pad transitions by ~30s on each side to ensure black screen frames fall within range. Merge overlapping windows. In practice, paired end→start transitions (46–77s apart) merge into single windows that cover the full loading sequence.
- **Injection point**: BSD lines 128–149 where `use_interval_mode` triggers the slow path. The two-pass logic replaces this path entirely.
- **State machine gap safety**: Between windows, the state machine state persists. This is safe because gaps only occur during stable gameplay (no transitions), so `prev_*` values remain consistent with the next window's first frames.
- **Fallback**: If the prescan finds 0 transitions, fall back to scanning the full video as a single window (same behavior as current interval mode).

## Implementation Plan

### Tasks

- [x] Task 1: Add `has_team_color()` function to `utils/image.py`
  - File: `utils/image.py`
  - Action: Add a new stateless function following the `is_black()` pattern:
    ```python
    def has_team_color(region, saturation_threshold):
        """Check if a BGR region contains a saturated team color bar.

        Args:
            region: BGR numpy array (height, width, 3).
            saturation_threshold: Minimum mean saturation (0-255) to detect bar.

        Returns:
            bool: True if mean saturation exceeds the threshold.
        """
        hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
        return float(np.mean(hsv[:, :, 1])) > saturation_threshold
    ```
  - Notes: `cv2` and `np` are already imported. Place after `is_black()` to keep related functions grouped.

- [x] Task 2: Add team bar ROI and detection config to `config/config.yaml`
  - File: `config/config.yaml`
  - Action: Add a `team_bar` entry to `roi_zones` and a new `team_bar_detection` section:
    ```yaml
    roi_zones:
      # ... existing zones ...
      - name: team_bar
        x: 430
        y: 1015
        width: 1060
        height: 65

    team_bar_detection:
      saturation_threshold: 90
      window_padding: 30.0
    ```
  - Notes: The ROI is at 1920x1080 reference resolution — scaling is handled by existing `scale_roi()`. The `team_bar_detection` section is a new top-level key, separate from `black_detection`.

- [x] Task 3: Add `prescan_team_bar()` function to BSD
  - File: `tools/black_screen_detector.py`
  - Action: Add a new function before `run()`:
    ```python
    def prescan_team_bar(video_path, target_height, team_bar_roi, sat_threshold):
        """Fast prescan using GOP I-frames to find in-game/not-in-game transitions.

        Iterates I-frames via single-pipe extraction, checks the team bar ROI
        for saturated color (team color bar present = in-game).

        Args:
            video_path: Path to the input video.
            target_height: Processing height in pixels.
            team_bar_roi: Scaled ROI dict for the team bar region.
            sat_threshold: Saturation threshold for has_team_color().

        Returns:
            list[float]: Timestamps where transitions occur (in-game → not-in-game
                         or not-in-game → in-game).
        """
    ```
  - Logic:
    1. Call `extract_iframes_scaled(video_path, target_height)` to iterate I-frames
    2. For each frame, `extract_roi(frame, team_bar_roi)` on the BGR frame (NOT grayscale)
    3. Call `has_team_color(region, sat_threshold)` to classify
    4. Track `prev_in_game` state. When it changes, record the timestamp as a transition
    5. Return sorted list of transition timestamps
  - Notes: Import `has_team_color` from `utils.image` alongside existing imports.

- [x] Task 4: Add `build_scan_windows()` function to BSD
  - File: `tools/black_screen_detector.py`
  - Action: Add a pure function after `prescan_team_bar()`:
    ```python
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
    ```
  - Logic:
    1. For each transition timestamp, create a window `(max(0, t - padding), min(duration, t + padding))`
    2. Sort windows by start time
    3. Merge overlapping/adjacent windows: if window B starts before window A ends, extend A to cover B
    4. Return merged list
  - Notes: Pure function, no side effects. Paired end→start transitions (46–77s apart) will naturally merge into single windows with 30s padding.

- [x] Task 5: Integrate two-pass logic into `run()` function
  - File: `tools/black_screen_detector.py`
  - Action: Replace the interval-mode path (current lines 128–149) with two-pass logic:
    1. Read `team_bar_detection` config values (`saturation_threshold`, `window_padding`)
    2. Find and scale the `team_bar` ROI from `roi_zones` (using existing `scale_roi()`)
    3. Run `prescan_team_bar()` → get transition list
    4. If transitions found: `build_scan_windows()` → get windows
    5. If no transitions found: fall back to single window `[(0.0, duration)]`
    6. Build `frame_iter` by chaining `extract_frames_at_interval()` calls across all windows:
       ```python
       def _chain_windows(video_path, target_height, windows, interval, iframe_timestamps):
           for start, end in windows:
               yield from extract_frames_at_interval(
                   video_path, target_height, start, end,
                   interval=interval, iframe_timestamps=iframe_timestamps,
               )
       ```
    7. Feed the chained iterator into the existing state machine loop (no changes to state machine)
  - Console output updates:
    - Print prescan summary: `"Prescan: {n} transitions found in {iframe_count} I-frames"`
    - Print windows: `"Scan windows: {windows} ({total_duration:.0f}s of {video_duration:.0f}s)"`
    - When `--profile` is passed, add `prescan` phase to `profile_stats`
  - Notes: The `_chain_windows` helper can be a module-level function or nested inside `run()`. The `iframe_timestamps` list (already computed for snapping) can be reused. The state machine loop and all downstream logic remain untouched.

### Acceptance Criteria

- [x] AC 1: Given a video with GOP > 2s, when running BSD, then it performs a prescan using single-pipe I-frame extraction and prints prescan summary before scanning targeted windows.
- [x] AC 2: Given the prescan detects transitions, when building scan windows with 30s padding, then overlapping windows are merged into contiguous ranges (e.g., end at 160s and start at 228s with 30s padding → single window [130, 258]).
- [x] AC 3: Given `lvlaste.mkv` (70min, GOP=8.3s), when running BSD with two-pass mode, then it detects the same number of start/end events as current interval mode, with timestamps within ±2s tolerance.
- [x] AC 4: Given a video where prescan finds 0 transitions, when running BSD, then it falls back to scanning the full video as a single window (equivalent to current interval mode behavior).
- [x] AC 5: Given a BGR frame region with the team bar visible (in-game), when calling `has_team_color()` with threshold 90, then it returns True.
- [x] AC 6: Given a BGR frame region without the team bar (scoreboard or loading screen), when calling `has_team_color()` with threshold 90, then it returns False.
- [x] AC 7: Given the `--profile` flag, when running BSD in two-pass mode, then the profile report includes a `prescan` phase with total time and I-frame count.
- [x] AC 8: Given the two-pass mode, when processing completes, then wall time is at least 5x faster than current interval mode on the same video.

## Additional Context

### Dependencies

- No new dependencies — uses existing OpenCV HSV conversion (`cv2.cvtColor` with `COLOR_BGR2HSV`), NumPy for array mean
- Requires `extract_iframes_scaled` from `utils/video.py` (already exists)
- Requires `extract_frames_at_interval` from `utils/video.py` (already exists)

### Testing Strategy

- **Manual validation on `lvlaste.mkv`**: Run both current interval mode and new two-pass mode, compare detected events (count and timestamps). Events should match within ±2s.
- **Profile comparison**: Run with `--profile` on both modes, verify speedup meets AC 8 (>5x faster).
- **Edge case: no transitions**: Test with a video that is entirely gameplay or entirely lobby to verify fallback behavior.
- **Pixel verification**: Spot-check `has_team_color()` on exported start frames (expect True) and end frames (expect False) from the lvlaste output.

### Notes

- Team colors observed: orange (Alliance, mean S=136) and blue (Rebels, mean S=155)
- The bar contains the POV player name and is consistently present during active gameplay
- On scoreboard/end screens and loading screens, this bar region has mean S=50–54
- Transition gaps (end→start) range from 46–77s in lvlaste.mkv — with 30s padding, these always merge into single windows
- The prescan itself should process ~500 I-frames (70min / 8.3s GOP) through the single pipe in a few seconds
- Future optimization: the prescan could also be useful for Tool 2 (frame labeling) to quickly identify game boundaries

## Review Notes

### Review 1 (prior session)
- Adversarial review completed
- Findings: 13 total, 1 fixed, 12 skipped
- Resolution approach: auto-fix
- Fixed: F4 (prescan phase conditionally included in profile report)
- Skipped as noise/undecided: F1, F2, F6-F13
- Skipped as out-of-scope: F3 (tests - manual validation per spec), F5 (pre-existing ffprobe architecture)

### Review 2 (current session)
- Adversarial review completed
- Findings: 13 total, 3 fixed, 10 skipped (by-design/noise/low-impact/latent)
- Resolution approach: auto-fix
- F1 (High, fixed): Excluded `team_bar` ROI from `is_end_loading` aggregate — was poisoning end-detection logic
- F3 (Medium, fixed): Collect iframe timestamps during prescan; eliminated redundant full-video ffprobe scan
- F4 (Medium, fixed): Added input validation to `has_team_color()` — raises ValueError on non-BGR input
- Skipped as by-design: F2 (window gap state — spec's safety note), F12 (per-frame subprocess architecture)
- Skipped as noise: F5, F9, F13
- Skipped as low-impact: F6 (window boundary duplicates), F7 (padding validation), F8 (timestamp bias), F10 (config inconsistency), F11 (closure hazard)
