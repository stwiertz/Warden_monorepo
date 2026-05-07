---
title: 'BSD Neutral Start & Vertical ROI Enhancement'
slug: 'bsd-neutral-start-vertical-roi'
created: '2026-02-25'
status: 'completed'
stepsCompleted: [1, 2, 3, 4]
tech_stack: ['Python 3', 'OpenCV (cv2)', 'PyYAML']
files_to_modify: ['tools/black_screen_detector.py']
code_patterns: ['three-state machine: undetermined / waiting_for_end / waiting_for_start', 'minimap_roi and vertical_roi extracted by name from scaled_rois', 'is_black() threshold check on extracted ROI regions', 'prev_all_black tracks previous frame for undetermined transition detection']
test_patterns: ['no test files — manual testing via visual inspection of exported frames']
---

# Tech-Spec: BSD Neutral Start & Vertical ROI Enhancement

**Created:** 2026-02-25

## Overview

### Problem Statement

The black screen detector makes assumptions about game state from the very first frame, using only the minimap ROI to decide whether the video starts in `waiting_for_start` or `waiting_for_end`. This can misclassify lobbies with black skies where the minimap area is black but the game hasn't actually started. Additionally, start detection (`waiting_for_start`) only checks the minimap ROI — it doesn't verify the vertical ROI, so lobbies with a black sky can fool the detector into thinking the game hasn't started yet (or has started prematurely).

### Solution

1. **Neutral initial state**: Replace the first-frame state assumption with an `"undetermined"` initial state. The detector watches for the first actual transition of either type (all-ROIs-black for end, or minimap+vertical becoming non-black for start) to establish the alternation rotation. This requires observing at least two frames to detect a change.

2. **Vertical ROI in start detection**: Extend the `waiting_for_start` check to require both `minimap` AND `vertical` ROIs to become non-black before declaring a game start.

### Scope

**In Scope:**

- New `"undetermined"` initial state in the state machine
- Vertical ROI added to start detection checks (alongside minimap)
- Removal of first-frame state determination logic

**Out of Scope:**

- End detection logic (all-ROIs-black check unchanged)
- Config/ROI coordinate changes
- Profiling changes
- CLI interface changes

## Context for Development

### Codebase Patterns

- State machine in `run()` uses `state` variable — now three states: `"undetermined"`, `"waiting_for_end"`, `"waiting_for_start"`
- `minimap_roi` and `vertical_roi` extracted by name from `scaled_rois` list
- Start detection (`waiting_for_start`) checks both `minimap` and `vertical` ROIs via `is_black(extract_roi(gray, roi), threshold)`
- End detection checks ALL `scaled_rois` — all must be black simultaneously. Result stored in `all_black` bool
- `prev_timestamp` tracks the previous frame's timestamp for end-event exports
- `prev_all_black` tracks previous frame's all-black status for undetermined state transition detection
- ROI zones defined in config: `minimap`, `map_name`, `vertical` — all three participate in end detection, `minimap` + `vertical` in start detection
- Profiling uses conditional `time.perf_counter()` deltas accumulated in `profile_stats` dict — new ROI checks in `undetermined` and `waiting_for_start` are wrapped in the `roi_check` timing block
- `is_black(region, threshold)` returns `True` if `np.mean(region) <= threshold`
- `extract_roi(frame, roi)` crops a named ROI region from the frame with bounds clamping

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `tools/black_screen_detector.py` | Main detector with state machine — the only file modified |
| `config/config.yaml` | ROI zone definitions (minimap, map_name, vertical) — read-only reference |
| `utils/image.py` | `is_black()`, `extract_roi()`, `to_grayscale()`, `scale_roi()` — used unchanged |

### Technical Decisions

- **Vertical ROI extracted by name**: Same pattern as existing `minimap_roi` extraction. `vertical_roi = next(r for r in scaled_rois if r["name"] == "vertical")` alongside the minimap extraction.
- **Undetermined state uses `prev_all_black`**: In `"undetermined"` state, the all-ROIs-black check already runs every frame. Track `prev_all_black` to detect transitions: if `prev_all_black is False` and `all_black is True` → end detected. If `prev_all_black is True` and start ROIs become non-black → start detected.
- **Start ROI group**: Both `minimap` and `vertical` must be non-black to trigger a start detection. Checked as: `not is_black(minimap_region, threshold) and not is_black(vertical_region, threshold)`.
- **No new dependencies**: All changes use existing helpers from `utils/image.py`. No new imports or packages needed.

## Implementation Plan

### Tasks

- [x] Task 1: Extract `vertical_roi` alongside `minimap_roi`
  - File: `tools/black_screen_detector.py`
  - Action: Add `vertical_roi = next(r for r in scaled_rois if r["name"] == "vertical")` after the existing `minimap_roi` extraction. Update comment to mention both ROIs are used for start detection.

- [x] Task 2: Replace initial state with `"undetermined"`
  - File: `tools/black_screen_detector.py`
  - Action: Change `state = None` to `state = "undetermined"`. Add `prev_all_black = None` variable. Update state machine comment block to describe three states. Remove the entire first-frame state determination block (`if state is None:` block that checked minimap and set initial state).

- [x] Task 3: Add `"undetermined"` state handler in state machine
  - File: `tools/black_screen_detector.py`
  - Action: Add `if state == "undetermined":` block before the existing `waiting_for_end`/`waiting_for_start` handlers. On first frame (`prev_all_black is None`), record `all_black` and print status. On subsequent frames: check for end transition (`not prev_all_black and all_black`) or start transition (`prev_all_black and start_rois_non_black`). Update `prev_all_black` each frame.
  - Notes: Start ROI check in undetermined state is profiled under `roi_check`. End transition uses `prev_timestamp` guard (same as `waiting_for_end`).

- [x] Task 4: Update `waiting_for_start` to check both minimap + vertical
  - File: `tools/black_screen_detector.py`
  - Action: Replace minimap-only check with both ROIs: extract both `minimap_region` and `vertical_region`, compute `start_rois_non_black = not is_black(minimap) and not is_black(vertical)`. Trigger start detection only when both are non-black.

- [x] Task 5: Update docstring and comments
  - File: `tools/black_screen_detector.py`
  - Action: Update module docstring to say "three-state machine". Update state machine comment block. Update `waiting_for_start` comment to mention both ROIs.

### Acceptance Criteria

- [x] AC 1: Given a video where the first frame is not a black screen, when the detector runs, then the initial state is `"undetermined"` and no detection fires until an actual transition is observed.
- [x] AC 2: Given a video where the first frame IS a black screen, when the detector runs, then the initial state is `"undetermined"` and a start detection fires when both minimap AND vertical ROIs become non-black.
- [x] AC 3: Given a video in `waiting_for_start` state, when only the minimap becomes non-black but the vertical ROI remains black, then no start detection fires.
- [x] AC 4: Given a video in `waiting_for_start` state, when both minimap AND vertical become non-black, then a start detection fires and state transitions to `waiting_for_end`.
- [x] AC 5: Given a video where all ROIs transition from non-black to all-black while in `undetermined` state, when the transition occurs, then an end detection fires and state transitions to `waiting_for_start`.
- [x] AC 6: Given the end detection logic, when checking for end transitions, then the behavior is unchanged (all ROIs must be black simultaneously).
- [x] AC 7: Given `--profile` flag is passed, when the detector runs, then all new ROI checks are accounted for under the existing `roi_check` profiling phase.

## Additional Context

### Dependencies

- No new external dependencies. All changes use existing helpers from `utils/image.py` (`is_black`, `extract_roi`).
- Requires `vertical` ROI to be defined in `config/config.yaml` (already present).

### Testing Strategy

- **Regression test**: Run against a known test recording. Compare exported filenames and timestamps against previous output. End detections should match exactly; start detections may shift if vertical ROI was previously black during lobby.
- **Black-sky lobby test**: Run against a recording with a black-sky lobby. Verify that start detection correctly waits for both minimap and vertical to become non-black.
- **Visual inspection**: Spot-check exported start frames to confirm they show actual gameplay (not lobby with black sky).
- **Profile check**: Run with `--profile` to verify `roi_check` timing still accounts for all ROI checks.

### Notes

- The `undetermined` state's `prev_all_black` variable is only used while in that state. Once the state transitions to `waiting_for_end` or `waiting_for_start`, `prev_all_black` is no longer read or updated.
- If a video contains no transitions at all (e.g., entirely black or entirely non-black), the detector stays in `undetermined` and exports nothing. This is correct behavior.
- The `vertical` ROI config entry must exist. A `ValueError` with a clear message is raised if either `minimap` or `vertical` is missing from config.

## Review Notes

- Adversarial review completed
- Findings: 13 total (5 in-scope, 8 out-of-scope from other specs in same diff)
- In-scope: 3 fixed, 2 skipped (1 undecided, 1 noise)
- Resolution approach: auto-fix
- F1+F3 fixed: Added `elif prev_all_black and not all_black:` guard to eliminate redundant ROI extraction when no black-to-non-black transition occurs
- F4 fixed: Wrapped ROI name lookup in try/except with descriptive ValueError
- F2 skipped: Asymmetric preconditions are intentional (undetermined lacks implicit guarantee)
- F5 skipped: prev_all_black scoped to undetermined state by design
