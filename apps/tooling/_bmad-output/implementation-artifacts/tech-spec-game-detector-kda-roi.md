---
title: 'Game Detector — Switch to KDA ROI'
slug: 'game-detector-kda-roi'
created: '2026-03-11'
status: 'completed'
stepsCompleted: [1, 2, 3, 4]
tech_stack: [python, opencv, ffmpeg, numpy]
files_to_modify: ['tools/game_detector.py']
code_patterns: ['run()+main() split', 'config-driven ROI scaling', 'state machine with confirmation counters']
test_patterns: ['manual testing with video files']
---

# Tech-Spec: Game Detector — Switch to KDA ROI

**Created:** 2026-03-11

## Overview

### Problem Statement

The game detector uses the `points` ROI (6x15px at 1080p, top center near the timer) for all detection. This tiny ROI sits adjacent to the colored objective icons (B/C capture points). On certain I-frames, the 4x10px ROI at 720p lands on saturated objective icon colors instead of white text, causing false end detections mid-game. Confirmed 3 false ends in a single video (`lvlaste.mkv`) at 26m31s, 31m31s, and 39m01s — all frames where the game HUD was fully visible but the ROI pixels hit colored icons.

### Solution

Replace `points` ROI with `kda` ROI (10x16px at 1080p, bottom HUD) for all detection (start, end, score offset). KDA reliably shows white text during gameplay at 720p (7x11px — enough pixels for white detection) and is not adjacent to any colored UI elements.

### Scope

**In Scope:**
- Change the ROI used in `game_detector.py` from `points` to `kda`

**Out of Scope:**
- Changing thresholds, confirmation frame counts, or score_offset logic
- Modifying `points_state_detector.py` or any other tool
- Adding minimum game duration or other safety nets

## Context for Development

### Codebase Patterns

- **Config-driven ROI**: ROIs defined at 1920x1080 reference in `config/config.yaml`, scaled via `scale_roi()` to processing resolution (720px). The `kda` ROI is already defined alongside `points`.
- **ROI lookup by name**: `game_detector.py` iterates `config["black_detection"]["roi_zones"]` and matches by `roi["name"]`. Changing the target name is a single string change.
- **Variable naming**: Current code uses `points_roi_raw` and `points_roi` variable names — should be renamed to `kda_roi_raw`/`kda_roi` for clarity.

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `tools/game_detector.py` | Only file to modify — ROI name on line 77, variable names, print statement |
| `config/config.yaml` | `kda` ROI defined at lines 72-76 (x:1197, y:1000, 10x16 @1080p) |
| `utils/image.py` | `has_white_pixels()` — no changes needed, same thresholds apply |

### Technical Decisions

- **KDA ROI validated at 720p**: Prior analysis confirmed 7x11px at 720p is sufficient for white detection with current thresholds (sat_max=12, val_min=230, min_ratio=0.01). See memory `roi-white-detection.md`.
- **KDA known occlusion risk**: KDA can be occluded by killcam replays, VFX, and victory screens — but these are transient and the 3-frame `end_confirm_frames` filters them out. The `points` ROI had the worse problem of sitting next to permanently-colored objective icons.
- **No threshold changes needed**: Same `points_detection` config section applies — the thresholds were designed for white text detection regardless of which ROI is used.

## Implementation Plan

### Tasks

- [x] Task 1: Change ROI lookup from `points` to `kda`
  - File: `tools/game_detector.py`
  - Action: On line 77, change `if roi["name"] == "points":` to `if roi["name"] == "kda":`
  - Notes: The `kda` ROI is already defined in `config/config.yaml` at `x:1197, y:1000, 10x16`

- [x] Task 2: Rename variables from `points_roi` to `kda_roi`
  - File: `tools/game_detector.py`
  - Action: Rename `points_roi_raw` → `kda_roi_raw` and `points_roi` → `kda_roi` throughout `run()`. Update all references (lines 75-76, 80-83, 98-100, 126-127, 144).
  - Notes: Pure rename for clarity — no logic change

- [x] Task 3: Update error message and print output
  - File: `tools/game_detector.py`
  - Action: Update the ValueError message on line 82 from `'points'` to `'kda'`. Update the ROI print statement on line 126 from `"points"` to `"kda"`.
  - Notes: Ensures CLI output correctly identifies which ROI is in use

### Acceptance Criteria

- [x] AC 1: Given a video with game rounds, when `game_detector.py` is run, then it uses the `kda` ROI (x:1197, y:1000, 10x16 @1080p) instead of the `points` ROI for white pixel detection
- [x] AC 2: Given the video `lvlaste.mkv`, when `game_detector.py` is run, then the false ends at 26m31s, 31m31s, and 39m01s no longer appear
- [x] AC 3: Given a config without a `kda` ROI zone defined, when `game_detector.py` is run, then it raises a ValueError naming `kda` as the missing ROI
- [x] AC 4: Given the `--profile` flag, when `game_detector.py` completes, then the profile report prints correctly (no regression)
- [x] AC 5: Given a video that ends mid-game, when `game_detector.py` is run, then the end-of-video warning still fires correctly

## Additional Context

### Dependencies

- No new dependencies — `kda` ROI already exists in `config/config.yaml`
- Same shared utilities (`scale_roi`, `extract_roi`, `has_white_pixels`) work unchanged

### Testing Strategy

- **Primary validation**: Re-run `game_detector.py` on `source/lvlaste.mkv` and verify the 3 false ends (26m31s, 31m31s, 39m01s) are eliminated
- **Regression check**: Compare total start/end count against expected game count for the video
- **Score screen check**: Verify exported score screen PNGs still show the correct score overlay

### Notes

- **KDA occlusion during killcam/victory**: KDA ROI can temporarily lose white during killcam replays or victory screens. The existing `end_confirm_frames: 3` (~25s at ~8s I-frame spacing) should filter these transient losses. If future videos show false ends from prolonged KDA occlusion, `end_confirm_frames` can be bumped — but that's out of scope here.
- **Config section naming**: The config section is still called `points_detection` even though we now use `kda` ROI. This is intentional — the thresholds are generic white-text detection parameters, not ROI-specific. Renaming the config section would be a broader refactor.

## Review Notes
- Adversarial review completed
- Findings: 13 total, 2 fixed, 11 skipped (noise/pre-existing)
- Resolution approach: auto-fix
- F1 (High/Real): Fixed stale config comment — "points frame" → "KDA frame" in score_offset comment
- F2 (Medium/Real): Normalized casing to lowercase `kda` throughout user-facing strings
