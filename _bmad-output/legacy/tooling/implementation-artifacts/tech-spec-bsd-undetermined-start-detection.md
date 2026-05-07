---
title: 'BSD State Machine — Rename all_black and Fix Undetermined Start Detection'
slug: 'bsd-undetermined-start-detection'
created: '2026-03-01'
status: 'completed'
stepsCompleted: [1, 2, 3, 4]
tech_stack: [python, opencv, ffmpeg]
files_to_modify: [tools/black_screen_detector.py]
code_patterns: [three-state-machine, deferred-batch-extraction, roi-zone-check, minimap+vertical-for-start]
test_patterns: [none — no test directory exists]
---

# Tech-Spec: BSD State Machine — Rename all_black and Fix Undetermined Start Detection

**Created:** 2026-03-01

## Overview

### Problem Statement

The `undetermined` state in the black screen detector relies on `all_black` (all ROI zones simultaneously black) to detect the first transition. Start detection only needs minimap+vertical to go from black to non-black, but the undetermined state gates start detection behind `all_black` which also requires `map_name` to be black. When a video starts mid-loading where `map_name` stays bright (e.g. astera.mp4 at 0-14s), the detector never sees `all_black=True` and misses the first startLoading event entirely. Additionally, the variable name `all_black` is opaque — it doesn't communicate that an all-black frame represents an endLoading screen.

### Solution

Rename `all_black` to `is_end_loading` for semantic clarity. In the `undetermined` state, track minimap+vertical blackness separately to detect startLoading transitions, matching the logic already used in `waiting_for_start`. This allows the detector to find the first startLoading even when `map_name` never goes black.

### Scope

**In Scope:**
- Rename `all_black` → `is_end_loading` throughout the detector
- Fix `undetermined` state to detect startLoading using minimap+vertical independently
- Ensure astera.mp4 correctly finds a startLoading as its first event

**Out of Scope:**
- Changes to ROI zone definitions or config
- Threshold tuning
- Changes to `waiting_for_end` / `waiting_for_start` state behavior beyond naming

## Context for Development

### Codebase Patterns

- State machine uses three states: `undetermined`, `waiting_for_end`, `waiting_for_start`
- `waiting_for_start` already checks only minimap+vertical ROIs — the undetermined state should mirror this for start detection
- End detection (all ROIs black) uses all 3 zones: minimap, map_name, vertical
- Start detection uses only minimap+vertical (both non-black after being black)
- `prev_all_black` tracks previous frame's all-ROIs-black status for undetermined transitions
- Deferred batch extraction: detection phase collects requests, extraction phase runs at the end
- `bsd_roi_debugger.py` uses "ALL BLACK" as display string only — no variable rename needed there

### Files to Reference

| File | Purpose | Lines of Interest |
| ---- | ------- | ----------------- |
| tools/black_screen_detector.py | Main detector with state machine | L112-231 (state machine), L117 (prev_all_black), L145-152 (all_black check), L155-195 (undetermined) |
| utils/image.py | `is_black()`, `extract_roi()` helpers | L104-116 (is_black) |
| config/config.yaml | ROI zone definitions (minimap, map_name, vertical) and thresholds | L27-44 (roi_zones) |
| tools/bsd_roi_debugger.py | Debug tool — uses "ALL BLACK" string in output only | L124-127 (display only) |

### Technical Decisions

- Rename `all_black` → `is_end_loading` for semantic clarity (all ROIs black = end loading screen)
- Add `start_rois_black` tracking in undetermined state (minimap+vertical both black)
- Remove first-frame shortcut (line 159-161) — "not all black" doesn't mean "in game," stay undetermined until a real transition
- Undetermined state must check BOTH transition types each frame independently

## Implementation Plan

### Tasks

- [x] Task 1: Rename `all_black` → `is_end_loading` throughout `run()`
  - File: `tools/black_screen_detector.py`
  - Action: Replace all occurrences of `all_black` variable with `is_end_loading` (lines 145, 149, 158, 167, 176, 195, 198)
  - Action: Rename `prev_all_black` → `prev_is_end_loading` (lines 117, 156, 158, 167, 176, 195)
  - Notes: Pure rename — no logic changes in this task. The `waiting_for_end` and `waiting_for_start` states keep identical behavior.

- [x] Task 2: Add `start_rois_black` computation per frame in the main loop
  - File: `tools/black_screen_detector.py`
  - Action: After the `is_end_loading` ROI check loop (line ~152), compute `start_rois_black` by checking minimap and vertical ROIs specifically:
    ```python
    minimap_region = extract_roi(gray, minimap_roi)
    vertical_region = extract_roi(gray, vertical_roi)
    start_rois_black = is_black(minimap_region, threshold) and is_black(vertical_region, threshold)
    ```
  - Notes: This extracts minimap/vertical regions once per frame. The `waiting_for_start` state (lines 209-229) already does this extraction inline — after this task, it can reuse the already-extracted regions or keep its existing pattern. This task only adds the computation; Task 3 wires it into the undetermined state.

- [x] Task 3: Rewrite `undetermined` state to use dual-track detection
  - File: `tools/black_screen_detector.py`
  - Action: Replace the entire `undetermined` block (lines 155-195) with new logic:
    1. Add `prev_start_rois_black = None` alongside `prev_is_end_loading = None` in the initialization block (line ~117)
    2. **First frame**: Record `prev_is_end_loading` and `prev_start_rois_black`, do NOT assume any state. Remove the shortcut that jumps to `waiting_for_end` when first frame is non-black.
    3. **Subsequent frames — endLoading detection**: If `not prev_is_end_loading and is_end_loading` → end detected. Record extraction request for `prev_timestamp`, set state to `waiting_for_start`, set `skip_until`.
    4. **Subsequent frames — startLoading detection**: If `prev_start_rois_black and not start_rois_black` → check that minimap and vertical are both non-black (same validation as `waiting_for_start`). If confirmed, record extraction request for current `timestamp`, set state to `waiting_for_end`.
    5. Update both `prev_is_end_loading` and `prev_start_rois_black` at end of undetermined block.
  - Notes: Both checks run independently each frame. The first transition to fire wins and sets the state. Log messages should use "endLoading" / "startLoading" terminology.

- [x] Task 4: Update log messages to use new terminology
  - File: `tools/black_screen_detector.py`
  - Action: Update all `print()` statements in the state machine to use `endLoading`/`startLoading` instead of "all black"/"not all black":
    - First frame log: `"First frame: recording state"` (no assumption)
    - First transition logs: `"First transition: endLoading at {t}s"` / `"First transition: startLoading at {t}s"`
  - Notes: Console output should clearly communicate which event type was detected.

- [x] Task 5: Validate with astera.mp4
  - Action: Run `python tools/black_screen_detector.py source/astera.mp4 --profile` and verify:
    - First event is a startLoading (not an endLoading)
    - startLoading timestamp is around 14s (where minimap+vertical go non-black)
    - Subsequent end/start alternation continues correctly
    - Total event count is 20 (10 starts + 10 ends) or 21 (start + 10 end/start pairs)

### Acceptance Criteria

- [x] AC 1: Given a video that starts mid-loading (minimap+vertical non-black, then black, then non-black) where `map_name` never goes black, when the detector runs, then the first detected event is a startLoading at the frame where minimap+vertical transition from black to non-black.

- [x] AC 2: Given a video that starts mid-game (all ROIs non-black, then all go black), when the detector runs, then the first detected event is an endLoading at the last non-black frame before the all-black transition.

- [x] AC 3: Given a video that starts with all ROIs already black, when the detector runs, then the detector stays in `undetermined` until a transition occurs (no premature state assumption).

- [x] AC 4: Given the rename is applied, when searching the codebase for `all_black` as a variable name, then zero occurrences are found in `tools/black_screen_detector.py`.

- [x] AC 5: Given astera.mp4 as input, when the detector runs, then the first event is a startLoading (not endLoading), and the subsequent events alternate correctly (end, start, end, start...).

- [x] AC 6: Given any video input, when the detector runs, then the `waiting_for_end` and `waiting_for_start` states continue to function identically to before (no behavioral regression beyond the undetermined state fix).

## Additional Context

### Dependencies

None — self-contained change within `tools/black_screen_detector.py`. No new imports, no config changes, no external dependencies.

### Testing Strategy

- **Manual validation with astera.mp4**: Run detector and verify first event is startLoading at ~14s. Compare total event count to previous run (should be previous count + 1 start event at the beginning).
- **Manual validation with other videos**: If available, test a video that starts mid-game to verify endLoading detection still works as first event.
- **ROI debugger cross-reference**: Use `python tools/bsd_roi_debugger.py source/astera.mp4 --range 0:20` to confirm the minimap+vertical transition timestamps match the detector's startLoading timestamp.

### Notes

- Debug output from astera.mp4 (0-15s) shows map_name stays at ~55 brightness throughout, never going black. minimap+vertical do go black at 10-12s and return non-black at 14s — this is the startLoading the detector should catch.
- The `start_rois_black` computation in Task 2 extracts minimap/vertical regions that `waiting_for_start` also extracts. A future optimization could avoid double-extraction, but that's out of scope for this change.
- The first-frame shortcut removal means the detector will process 1-2 extra frames in undetermined before transitioning. This has negligible performance impact since the undetermined state is only active for the first few frames.

## Review Notes
- Adversarial review completed
- Findings: 8 total, 6 fixed (real), 2 skipped (noise/undecided)
- Resolution approach: auto-fix
- Key fixes applied: eliminated double ROI extraction in waiting_for_start, moved start_rois_black inside undetermined block, added De Morgan's law clarifying comment, removed unnecessary f-string prefix
