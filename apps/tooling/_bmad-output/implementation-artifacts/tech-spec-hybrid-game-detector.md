---
title: 'Hybrid Game Detector'
slug: 'hybrid-game-detector'
created: '2026-03-11'
status: 'completed'
stepsCompleted: [1, 2, 3, 4]
tech_stack: [python, opencv, ffmpeg, numpy]
files_to_modify: ['tools/game_detector.py', 'utils/format.py', 'config/config.yaml']
code_patterns: ['run()+main() split', 'deferred batch extraction', 'config-driven ROI scaling', 'state machine with confirmation counters']
test_patterns: ['manual testing with video files']
---

# Tech-Spec: Hybrid Game Detector

**Created:** 2026-03-11

## Overview

### Problem Statement

Two separate tools each solve half the problem — `points_state_detector.py` detects in-game vs lobby state reliably via white pixel detection but doesn't capture the score screen, while `black_screen_detector.py` finds score screens via black screen transitions but uses a more complex detection approach (team bar prescan) that was superseded by the points method.

### Solution

New tool (`tools/game_detector.py`) that uses points white-pixel detection to find game start/end boundaries, then captures the score screen by extracting an I-frame at +14.5s after the last confirmed in-game points frame. No black screen detection needed — the fixed offset reliably lands within the 10s individual+team score window.

### Scope

**In Scope:**
- New `tools/game_detector.py` combining points-based detection with score screen capture
- Points-based start detection (white text appears, 2-frame confirm)
- Points-based end detection (white text disappears, 3-frame confirm)
- Score screen capture: extract I-frame at last_points_timestamp + 14.5s
- Extract `format_timestamp()` to shared `utils/format.py` to avoid triple-duplication
- Add `score_offset` config parameter to `points_detection` section
- Reuse shared utils from `utils/image.py` and `utils/video.py`

**Out of Scope:**
- Team bar prescan logic (dropped — replaced by points detection)
- Black screen detection (not needed for this approach)
- Modifying existing BSD or points detector behavior
- Map name detection or other post-processing

## Context for Development

### Codebase Patterns

- **run()+main() split**: All tools separate core logic (`run()` returning results) from CLI entry point (`main()` parsing args). The new tool follows this pattern.
- **Deferred batch extraction**: Both existing tools collect `extraction_requests` during the I-frame scan loop, then batch-extract full-resolution frames at the end. This minimizes ffmpeg subprocess calls.
- **Config-driven ROI scaling**: ROIs are defined at 1920x1080 reference resolution in `config/config.yaml`, scaled via `scale_roi()` to processing resolution (720px). The new tool reuses the `points` ROI zone and `points_detection` config section.
- **State machine with confirmation counters**: Points detector uses a two-state machine (`not_in_game`/`in_game`) with `start_confirm_count` (2 frames) and `end_confirm_count` (3 frames) to filter transient state changes.
- **Output format**: All tools export PNGs named `MMmSSs_type_seq.png` into a video-named subdirectory under the output dir.

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `tools/points_state_detector.py` | Primary template — state machine, white pixel detection loop, batch extraction |
| `tools/black_screen_detector.py` | Reference for profile report format, pre-end extraction pattern |
| `utils/image.py` | `scale_roi`, `extract_roi`, `has_white_pixels` — used directly |
| `utils/video.py` | `extract_iframes_scaled`, `extract_frame_at_timestamp` — used directly |
| `utils/config.py` | `load_config` — used directly |
| `config/config.yaml` | `points_detection` section for thresholds, `points` ROI in `black_detection.roi_zones` |

### Technical Decisions

- **14.5s offset for score capture:** Last points I-frame can be up to ~9s before actual game end (worst-case GOP). Then 5s team score screen. 14.5s lands safely within the 10s individual+team score window.
- **No black screen scanning:** Simplifies the tool — points detection + fixed offset is sufficient.
- **New tool, not a merge:** Avoids breaking existing tools; keeps them available as reference/fallback.
- **Score frame uses `extract_frame_at_timestamp()`:** Same full-resolution extraction as start/end frames. The timestamp is `last_confirmed_points_timestamp + score_offset`, queued into the same `extraction_requests` batch.
- **Shared `format_timestamp()`:** Currently duplicated in both existing tools. Extract to `utils/format.py` to avoid triple-duplication. Existing tools are not modified (out of scope).

## Implementation Plan

### Tasks

- [x] Task 1: Add `score_offset` to config
  - File: `config/config.yaml`
  - Action: Add `score_offset: 14.5` to the `points_detection` section
  - Notes: This is the seconds offset from the last confirmed in-game points frame to extract the score screen

- [x] Task 2: Create shared `format_timestamp` utility
  - File: `utils/format.py`
  - Action: Create new file with `format_timestamp(seconds)` function that formats seconds as `MMmSSs` (e.g. `05m23s`)
  - Notes: Extracted from the identical implementations in `points_state_detector.py` and `black_screen_detector.py`. New tool imports from here.

- [x] Task 3: Create `tools/game_detector.py`
  - File: `tools/game_detector.py`
  - Action: Create new tool based on `points_state_detector.py` with the following modifications:
    1. **Import `format_timestamp` from `utils/format.py`** instead of defining it locally
    2. **Read `score_offset` from config** (`config["points_detection"]["score_offset"]`)
    3. **Track `last_in_game_timestamp`**: Update to `prev_timestamp` on every frame where `white_detected` is True and `state == "in_game"`
    4. **On confirmed end transition**: In addition to queuing the end frame extraction request, queue a score screen extraction request at timestamp `last_in_game_timestamp + score_offset` with type `"score"` and filename `{ts_str}_score_{seq}.png` (where `ts_str` is formatted from the score timestamp)
    5. **CLI interface**: Same args as points detector (`video`, `-o`, `-c`, `--profile`) but without `--roi` (always uses `points`)
    6. **Summary output**: Include score screen count alongside start/end counts
  - Notes: The state machine is identical to `points_state_detector.py`. The only additions are tracking `last_in_game_timestamp` and queuing the score extraction request on end transitions.

### Acceptance Criteria

- [x] AC 1: Given a video with game rounds, when `game_detector.py` is run, then it detects start transitions (white text appears in points ROI with 2-frame confirmation) and exports a full-resolution PNG for each start
- [x] AC 2: Given a video with game rounds, when `game_detector.py` is run, then it detects end transitions (white text disappears from points ROI with 3-frame confirmation) and exports a full-resolution PNG for each end
- [x] AC 3: Given a confirmed end transition with `last_in_game_timestamp` at T, when the score extraction is queued, then a full-resolution frame is extracted at timestamp `T + 14.5s` and exported as `{MMmSSs}_score_{seq}.png`
- [x] AC 4: Given the `score_offset` parameter is set in `config/config.yaml`, when the tool reads config, then it uses the configured value (not a hardcoded 14.5)
- [x] AC 5: Given a video file that doesn't exist, when `game_detector.py` is run, then it prints an error message and exits with code 1
- [x] AC 6: Given a video with no game rounds (no white pixels in points ROI), when `game_detector.py` is run, then it completes with 0 transitions found and no exported frames
- [x] AC 7: Given a video that ends mid-game (white still present), when `game_detector.py` is run, then it prints a warning about no end transition and does not export a score screen for the incomplete round
- [x] AC 8: Given `--profile` flag is passed, when `game_detector.py` completes, then it prints a timing breakdown report

## Additional Context

### Dependencies

- No new external dependencies — uses existing `cv2`, `numpy`, `ffmpeg` stack
- Depends on existing shared utilities: `utils/image.py`, `utils/video.py`, `utils/config.py`
- Depends on `points` ROI zone being defined in `config/config.yaml`

### Testing Strategy

- **Manual testing**: Run against known video files with multiple game rounds and verify:
  - Start/end frames match expected timestamps
  - Score screen frame shows the individual+team score overlay (not the team-only screen or the black screen)
  - Output filenames follow the `MMmSSs_type_seq.png` pattern
- **Edge cases to test**:
  - Video with only 1 game round
  - Video that ends mid-game (no end transition)
  - Video where score timestamp exceeds video duration (should handle gracefully — ffmpeg will extract the last available frame or fail, which should be caught)
- **Comparison testing**: Run both `points_state_detector.py` and `game_detector.py` on the same video — start/end detections should match exactly

### Notes

- **Score timestamp exceeding video duration**: If a game ends near the end of the recording, `last_in_game_timestamp + 14.5s` could exceed the video length. The tool should catch the ffmpeg error and log a warning rather than crashing. This is an edge case but worth handling.
- **Future consideration**: The existing tools (`black_screen_detector.py`, `points_state_detector.py`) remain untouched. If this tool proves reliable, they could eventually be deprecated or moved to a `tools/legacy/` folder, but that's out of scope.

## Review Notes
- Adversarial review completed
- Findings: 12 total, 3 fixed, 9 skipped (noise/out-of-scope)
- Resolution approach: auto-fix
- Fixed: extraction_requests sorting, narrowed exception handling, AC checkboxes marked
