---
title: 'Game Detector HUD Verification via notkda ROI'
slug: 'game-detector-hud-verification'
created: '2026-03-17'
status: 'Completed'
stepsCompleted: [1, 2, 3, 4]
tech_stack: [python, opencv, numpy]
files_to_modify: [tools/game_detector.py, config/config.yaml]
code_patterns: [roi-lookup-by-name, scale_roi, extract_roi, grayscale-threshold, cv2.cvtColor-BGR2GRAY]
test_patterns: [manual-video-validation]
---

# Tech-Spec: Game Detector HUD Verification via notkda ROI

**Created:** 2026-03-17

## Overview

### Problem Statement

The game detector's KDA ROI white-pixel detection can produce false positives on score screens. The score screen background in the KDA region is bright enough to pass the white detection threshold (sat_max=12, val_min=230), causing the state machine to believe gameplay is still ongoing. This delays end detection — the "end" frame captured is actually a score screen (e.g., `21m10s_end_008` in the astera video has gray_mean=155 in the notkda region vs 22-68 during actual gameplay).

### Solution

Add a secondary HUD verification check using the existing `notkda` ROI (defined in config at x:1215, y:1000, 18x16 @1080p). During gameplay, the notkda region — the dark HUD background immediately right of the KDA digits — has a consistently low brightness (gray mean 22-68). On score screens, this same region is bright (gray mean 155+). Gate the `white_detected` result: only consider a frame as "in-game" if both KDA has white pixels AND notkda gray mean is below a configurable threshold.

### Scope

**In Scope:**
- Load the `notkda` ROI in `game_detector.py` alongside the `kda` ROI
- Add a gray-mean brightness check on the notkda region each frame
- Gate `white_detected`: true only if KDA has white AND notkda is dark
- Add configurable threshold to `points_detection` config section
- Update diagnostic print output to include notkda ROI info

**Out of Scope:**
- Changes to `points_state_detector.py` or other tools
- New ROI definitions (notkda already exists in `config/config.yaml`)
- Changes to the state machine logic itself (only the input signal changes)

## Context for Development

### Codebase Patterns

- ROI lookup: iterate `config["black_detection"]["roi_zones"]` and match by `roi["name"]`
- ROI scaling: `scale_roi(roi_raw, ref_scale)` from `utils/image.py`
- ROI extraction: `extract_roi(frame, scaled_roi)` returns BGR numpy array
- Grayscale conversion: `cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)` then `.mean()`
- Config values live under `points_detection` in `config/config.yaml`

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `tools/game_detector.py` | Main file to modify — KDA ROI loading, frame loop, white_detected gating |
| `config/config.yaml` | Add `hud_brightness_max` threshold under `points_detection`; notkda ROI already defined |
| `utils/image.py` | Existing utilities: `scale_roi`, `extract_roi`, `has_white_pixels` |

### Technical Decisions

- **Threshold value**: 100 gray mean provides clean separation. Gameplay peaks at 68, score screens start at 136+. Wide margin of safety.
- **Gray mean vs white ratio**: Gray mean is simpler and sufficient — the notkda region doesn't need HSV white-pixel analysis, just a brightness check.
- **Gating approach**: Modify `white_detected` in-place rather than adding a new state machine state. The state machine logic is unchanged; only its input signal becomes more precise.

## Implementation Plan

### Tasks

- [x] Task 1: Add `hud_brightness_max` config value
  - File: `config/config.yaml`
  - Action: Add `hud_brightness_max: 100` to the `points_detection` section, after the existing `score_offset` entry
  - Notes: Comment should read `# Max gray mean for notkda ROI to confirm HUD presence (gameplay: 22-68, score screen: 136+)`

- [x] Task 2: Load notkda ROI from config
  - File: `tools/game_detector.py`
  - Action: After the existing KDA ROI lookup loop (lines 74-84), add a second lookup for the `notkda` ROI using the same pattern. Raise `ValueError` if not found. Read `hud_brightness_max` from `pd_config`.
  - Notes: Follow the exact same pattern as the kda lookup — iterate `roi_zones`, match by `roi["name"] == "notkda"`, assign to `notkda_roi_raw`

- [x] Task 3: Scale notkda ROI
  - File: `tools/game_detector.py`
  - Action: After `kda_roi = scale_roi(kda_roi_raw, ref_scale)` (line 100), add `notkda_roi = scale_roi(notkda_roi_raw, ref_scale)`

- [x] Task 4: Update diagnostic print
  - File: `tools/game_detector.py`
  - Action: After the existing KDA ROI print (lines 126-127), add a line printing the notkda ROI coordinates and the `hud_brightness_max` threshold

- [x] Task 5: Gate white_detected with notkda brightness check
  - File: `tools/game_detector.py`
  - Action: After `white_detected = has_white_pixels(region, sat_max, val_min, min_ratio)` (line 145), add:
    1. Extract the notkda region: `notkda_region = extract_roi(frame, notkda_roi)`
    2. Convert to grayscale: `notkda_gray = cv2.cvtColor(notkda_region, cv2.COLOR_BGR2GRAY)`
    3. Check brightness: `hud_dark = notkda_gray.mean() < hud_brightness_max`
    4. Gate the result: `white_detected = white_detected and hud_dark`
  - Notes: Both checks run inside the existing profiling block (`profile_stats["roi_check"]`), so the notkda extraction is included in the timing

### Acceptance Criteria

- [x] AC 1: Given the astera video, when game_detector runs, then `21m10s_end_008` should no longer be a score screen — the end frame should be an actual last-gameplay frame with notkda gray mean < 100
- [x] AC2: Given the astera video, when game_detector runs, then all other start/end/score pairs remain unchanged (same count, same approximate timestamps)
- [x] AC3: Given a frame where KDA has white pixels but notkda gray mean >= 100 (score screen), when the state machine evaluates it, then `white_detected` is False and the frame is treated as non-game
- [x] AC4: Given a frame where KDA has white pixels and notkda gray mean < 100 (gameplay), when the state machine evaluates it, then `white_detected` is True and the frame is treated as in-game
- [x] AC5: Given config without `hud_brightness_max`, when game_detector runs, then it raises a KeyError pointing to the missing config key
- [x] AC6: Given config without a `notkda` ROI zone, when game_detector runs, then it raises a ValueError listing available ROI zones

## Additional Context

### Dependencies

None — all required utilities and ROI definitions already exist.

### Testing Strategy

Manual video validation:
1. Re-run `python tools/game_detector.py <astera_video>` and compare output frame list against previous run
2. Visually inspect the `end_008` frame to confirm it's now a gameplay frame, not a score screen
3. Verify total event count and timestamps for all other rounds remain stable

### Notes

**Empirical data from astera video (notkda ROI gray mean):**
- Start frames (in-game): 24-68
- End frames (last in-game): 22-58
- Score screens: 7-170 (problematic frame 21m10s_end_008: 155)
- Threshold at 100 cleanly separates gameplay from the bright score screen case

**Risk**: If future maps have a very bright HUD background in the notkda region during gameplay (gray mean > 100), this check would cause false end detections. The current 32-point margin (gameplay max 68 vs threshold 100) makes this unlikely. The threshold is configurable if adjustment is needed.

## Review Notes
- Adversarial review completed
- Findings: 12 total, 2 fixed, 10 skipped
- Resolution approach: auto-fix
- F4 fixed: simplified `white_detected = white_detected and hud_dark` → `white_detected = notkda_gray.mean() < hud_brightness_max`
- F8 fixed: removed trailing whitespace and excess blank lines in config.yaml
