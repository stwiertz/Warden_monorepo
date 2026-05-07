---
title: 'BSD Dual-State Detection & Regression Fixtures'
slug: 'bsd-dual-state-detection'
created: '2026-03-01'
status: 'completed'
stepsCompleted: [1, 2, 3, 4]
tech_stack: [python, opencv, ffmpeg, numpy, pyyaml]
files_to_modify: [tools/black_screen_detector.py, tests/fixtures/astera_expected.json]
code_patterns: [state-machine, deferred-extraction, roi-detection, three-state-alternation]
test_patterns: [golden-fixture-regression, manual-video-regression]
---

# Tech-Spec: BSD Dual-State Detection & Regression Fixtures

**Created:** 2026-03-01

## Overview

### Problem Statement

The black screen detector's strict alternation state machine causes cascading missed detections. When a transition is missed in one state, the detector stays stuck — missing one end in `waiting_for_end` means the next start is also missed (since we never enter `waiting_for_start`), and vice versa. This results in lost event pairs in frozen.mp4 and lvlaste.mkv (e.g., lvlaste misses an end at ~17:19s, cascading into a missed start, with the next detected end at 24:10s being the wrong round).

### Solution

1. **Dual detection in each state** — while in `waiting_for_end`, also monitor for start-like patterns (minimap+vertical black → non-black). If detected, it means we missed an end and should self-correct by emitting a recovery event and transitioning appropriately. Similarly, while in `waiting_for_start`, also monitor for end-like patterns.
2. **Miss report** — when recovery fires, log the estimated timeframe window (last known event → recovery point, capped by 10-minute max game duration) so the user can target the ROI debugger at the approximate miss location.
3. **Golden regression fixtures** — save astera.mp4 detection results as a JSON fixture to use as a known-good reference while iterating on detection logic.

### Scope

**In Scope:**
- Dual-detection logic in `waiting_for_end` and `waiting_for_start` states
- Miss report with estimated timeframe window for each recovery event
- JSON fixture generation from astera.mp4 current output
- Use astera as regression test while fixing frozen/lvlaste

**Out of Scope:**
- Changing ROI zones or threshold tuning
- Investigating WHY specific frames fail the ROI check (separate investigation)
- Automated test harness / CI integration
- Auto-running the debugger on missed windows

## Context for Development

### Codebase Patterns

- State machine with three states: `undetermined`, `waiting_for_end`, `waiting_for_start` (lines 160-235)
- Deferred batch extraction: detection phase collects timestamps into `extraction_requests` list, then extracts full-res frames in a post-loop batch (lines 243-257)
- ROI-based detection: `is_end_loading` = ALL ROIs black; start detection uses minimap+vertical subset only
- `start_confirm_frames` pattern: consecutive frame confirmation before firing start events (configurable, default 2)
- `saw_black_in_wait` gate: must witness loading screen (minimap+vertical black) before accepting start
- `skip_until` mechanism: after end detection, skip frames for `skip_duration` seconds to avoid duplicate detections
- `detection_seq` counter: monotonic sequence for unique filenames across all event types
- `run()` returns `(exported, frame_count, profile_stats)` — exported is list of `{filename, type, timestamp}` dicts
- Inconsistency: `undetermined` state checks for transition (`not prev_is_end_loading and is_end_loading`), but `waiting_for_end` fires on any single frame where `is_end_loading` is True (no transition check)

### Files to Reference

| File | Purpose |
| ---- | ------- |
| tools/black_screen_detector.py | Main detection tool — state machine lives in `run()` lines 96-266 |
| tools/bsd_roi_debugger.py | ROI debugger — consumes miss window timeframes for investigation |
| config/config.yaml | ROI zones (minimap, map_name, vertical), thresholds, skip_duration |
| utils/image.py | Stateless helpers: `is_black()`, `extract_roi()`, `scale_roi()`, `to_grayscale()` |
| utils/video.py | FFmpeg I-frame extraction: `extract_iframes_scaled()`, `extract_frame_at_timestamp()` |
| utils/config.py | `load_config()` — YAML loader |

### Technical Decisions

- Recovery detections emit the detected event normally (start or end) and additionally log a miss report entry for the event that was skipped
- Miss report is a separate list: `[{type: "missed_end"|"missed_start", window_start: float, window_end: float}, ...]`
- Window calculation: `window_start = last_known_event_timestamp`, `window_end = recovery_detection_timestamp`, capped at 600s (10 min max game duration)
- Miss report is printed in the summary section and returned from `run()` as a 4th return value
- Recovery events are printed with a `RECOVERY` tag in console output to distinguish from normal detections
- `waiting_for_end` dual-detection: track `prev_start_rois_black` to detect start-like transitions (black → non-black on minimap+vertical). If fired → missed end, emit start, log missed end window
- `waiting_for_start` dual-detection: track `prev_is_end_loading` to detect end-like transitions (non-black → all-black). If fired → missed start, emit end, log missed start window
- Golden fixture: JSON array matching the `exported` list structure from astera.mp4 current output
- No test framework exists yet — fixture is for manual regression comparison during development

## Implementation Plan

### Tasks

- [x] Task 1: Create golden fixture from astera.mp4 output
  - File: `tests/fixtures/astera_expected.json`
  - Action: Create a JSON file containing the current astera.mp4 detection results as an array of `{filename, type, timestamp}` objects. This captures the known-good baseline before any code changes.
  - Notes: Must be done FIRST, before any state machine modifications. Use the existing output data:
    ```json
    [
      {"filename": "00m14s_start_001.png", "type": "start", "timestamp": 14.0},
      {"filename": "07m12s_end_002.png", "type": "end", "timestamp": 432.0},
      ...
    ]
    ```
    Exact timestamps should be extracted by running the detector once and capturing the `exported` list output. The filenames above are illustrative — use actual values.

- [x] Task 2: Add `miss_reports` list and `last_event_timestamp` tracking
  - File: `tools/black_screen_detector.py` — `run()` function, initialization block (around line 97)
  - Action: Add two new variables alongside the existing state machine variables:
    ```python
    miss_reports = []  # list of dicts: {type, window_start, window_end}
    last_event_timestamp = 0.0  # timestamp of most recent detection (normal or recovery)
    ```
  - Notes: `last_event_timestamp` must be updated every time a detection fires (normal or recovery). It serves as the `window_start` for the next miss report.

- [x] Task 3: Move prev-frame tracking to global scope
  - File: `tools/black_screen_detector.py` — `run()` main loop
  - Action: Currently `prev_is_end_loading` and `prev_start_rois_black` are only updated inside the `if state == "undetermined"` block (line 193-194). Move these two assignments to the END of the loop body (just before `prev_timestamp = timestamp` at line 237), outside any state block, so they are updated on every frame regardless of state. Remove the two assignments from inside the undetermined block.
  - Notes: The first-frame guard (`if prev_is_end_loading is None`) in undetermined state still works because the variables are initialized to `None` and only get updated at the end of the first iteration. This is a prerequisite for Tasks 4 and 5 — dual-detection in other states needs accurate previous-frame values.

- [x] Task 4: Add dual-detection in `waiting_for_end` state
  - File: `tools/black_screen_detector.py` — `waiting_for_end` block (lines 196-209)
  - Action: After the existing `if is_end_loading` check (which handles normal end detection), add an `elif` branch that detects start-like transitions — the same pattern used in the `undetermined` state:
    ```python
    elif state == "waiting_for_end":
        if is_end_loading and prev_timestamp is not None:
            # --- existing normal end detection (unchanged) ---
            detection_seq += 1
            ts_str = format_timestamp(prev_timestamp)
            fname = f"{ts_str}_end_{detection_seq:03d}.png"
            extraction_requests.append({"timestamp": prev_timestamp, "type": "end", "filename": fname})
            state = "waiting_for_start"
            skip_until = timestamp + skip_duration
            start_confirm_count = 0
            start_candidate_timestamp = None
            saw_black_in_wait = False
            last_event_timestamp = prev_timestamp

        elif prev_start_rois_black and not start_rois_black:
            if not minimap_black and not vertical_black:
                # RECOVERY: detected a start while waiting for end.
                # This means we missed an end transition.
                window_start = max(last_event_timestamp, timestamp - 600)
                miss_reports.append({
                    "type": "missed_end",
                    "window_start": window_start,
                    "window_end": timestamp,
                })
                detection_seq += 1
                ts_str = format_timestamp(timestamp)
                fname = f"{ts_str}_start_{detection_seq:03d}.png"
                extraction_requests.append({"timestamp": timestamp, "type": "start", "filename": fname})
                last_event_timestamp = timestamp
                # Stay in waiting_for_end — we just detected a start, next should be an end
                start_confirm_count = 0
                start_candidate_timestamp = None
                print(f"  RECOVERY: startLoading at {timestamp:.1f}s (missed end in [{window_start:.1f}s, {timestamp:.1f}s])")
    ```
  - Notes: The recovery uses the same De Morgan's guard (`not minimap_black and not vertical_black`) as the undetermined state. No `start_confirm_frames` confirmation — single-frame detection like undetermined. The state remains `waiting_for_end` because we just emitted a start (next expected event is an end). `last_event_timestamp` is also updated on normal end detection (add `last_event_timestamp = prev_timestamp` to the existing normal end block).

- [x] Task 5: Add dual-detection in `waiting_for_start` state
  - File: `tools/black_screen_detector.py` — `waiting_for_start` block (lines 211-235)
  - Action: Add recovery check for end-like transitions. The condition: `saw_black_in_wait` was already True (we saw the loading screen), previous frame was not all-black (`not prev_is_end_loading`), and current frame is all-black (`is_end_loading`). This means a game started (we missed it), was played, and just ended:
    ```python
    elif state == "waiting_for_start":
        if start_rois_black:
            saw_black_in_wait = True
            start_confirm_count = 0
            start_candidate_timestamp = None
        elif saw_black_in_wait:
            if not minimap_black and not vertical_black:
                # --- existing start confirmation logic (unchanged) ---
                start_confirm_count += 1
                if start_candidate_timestamp is None:
                    start_candidate_timestamp = timestamp
                if start_confirm_count >= start_confirm_frames:
                    detection_seq += 1
                    ts_str = format_timestamp(start_candidate_timestamp)
                    fname = f"{ts_str}_start_{detection_seq:03d}.png"
                    extraction_requests.append({"timestamp": start_candidate_timestamp, "type": "start", "filename": fname})
                    state = "waiting_for_end"
                    start_confirm_count = 0
                    start_candidate_timestamp = None
                    last_event_timestamp = start_candidate_timestamp
            elif not prev_is_end_loading and is_end_loading:
                # RECOVERY: detected an end while waiting for start.
                # This means we missed a start transition (and possibly a full game).
                window_start = max(last_event_timestamp, prev_timestamp - 600)
                miss_reports.append({
                    "type": "missed_start",
                    "window_start": window_start,
                    "window_end": prev_timestamp,
                })
                detection_seq += 1
                ts_str = format_timestamp(prev_timestamp)
                fname = f"{ts_str}_end_{detection_seq:03d}.png"
                extraction_requests.append({"timestamp": prev_timestamp, "type": "end", "filename": fname})
                last_event_timestamp = prev_timestamp
                # Stay in waiting_for_start — we just detected an end, next should be a start
                skip_until = timestamp + skip_duration
                start_confirm_count = 0
                start_candidate_timestamp = None
                saw_black_in_wait = False
                print(f"  RECOVERY: endLoading at {prev_timestamp:.1f}s (missed start in [{window_start:.1f}s, {prev_timestamp:.1f}s])")
            else:
                start_confirm_count = 0
                start_candidate_timestamp = None
    ```
  - Notes: The recovery fires inside the `elif saw_black_in_wait` branch, meaning we already saw the loading screen. The condition `not prev_is_end_loading and is_end_loading` checks for a non-black → all-black transition. After recovery, state stays `waiting_for_start` (we just emitted an end), `skip_until` is set, and `saw_black_in_wait` resets. `last_event_timestamp` is also updated on normal start detection (add to the existing confirmed-start block).

- [x] Task 6: Update `run()` return signature and `main()` caller
  - File: `tools/black_screen_detector.py` — `run()` return statement (line 266) and `main()` function (line 375)
  - Action:
    1. Change `run()` return to: `return exported, frame_count, profile_stats, miss_reports`
    2. Update `main()` call site to unpack: `exported, frame_count, profile_stats, miss_reports = run(...)`
    3. Update docstring for `run()` to document the 4th return value

- [x] Task 7: Add miss report to summary output
  - File: `tools/black_screen_detector.py` — `main()` summary section (around lines 383-398)
  - Action: After the existing summary output, add a miss report section:
    ```python
    if miss_reports:
        print(f"  Recovery events: {len(miss_reports)}")
        print(f"  Missed transitions:")
        for mr in miss_reports:
            window_start_str = format_timestamp(mr['window_start'])
            window_end_str = format_timestamp(mr['window_end'])
            print(f"    - {mr['type']}: estimated between {window_start_str} ({mr['window_start']:.1f}s) and {window_end_str} ({mr['window_end']:.1f}s)")
    ```
  - Notes: Uses existing `format_timestamp()` helper for readable output. Also shows raw seconds for precision when feeding into the debugger `--range` flag.

- [x] Task 8: Regression test — run astera.mp4 and compare against fixture
  - Action: After all code changes, run: `python tools/black_screen_detector.py source/astera.mp4`
  - Verify: Output must match `tests/fixtures/astera_expected.json` exactly — same events, same order, same timestamps, no recovery events. This confirms the dual-detection changes don't break existing correct behavior.

- [x] Task 9: Validation — run frozen.mp4 and lvlaste.mkv
  - Action: Run detector on both problem videos and verify:
    1. Recovery events fire in the known gap windows
    2. Miss reports provide actionable timeframes
    3. lvlaste.mkv: recovery should fire near the 17:19-24:10s gap
    4. frozen.mp4: recovery should fire near the ~9 min gaps (end_002→start_003, end_006→start_007)

### Acceptance Criteria

- [x] AC 1: Given astera.mp4 (known-good video), when the detector runs with dual-detection enabled, then the output matches the golden fixture exactly with zero recovery events.
- [x] AC 2: Given a video where `waiting_for_end` misses an end transition, when a start-like pattern (minimap+vertical black → non-black) is detected, then the detector emits the start event normally, logs a `missed_end` report with the timeframe window, prints a `RECOVERY` tag, and stays in `waiting_for_end`.
- [x] AC 3: Given a video where `waiting_for_start` misses a start transition, when an end-like pattern (non-black → all-black) is detected after the `saw_black_in_wait` gate, then the detector emits the end event normally, logs a `missed_start` report with the timeframe window, prints a `RECOVERY` tag, and stays in `waiting_for_start`.
- [x] AC 4: Given a recovery event fires, when the miss report is generated, then `window_start` equals the last known event timestamp and `window_end` equals the recovery detection timestamp, capped at a maximum span of 600 seconds.
- [x] AC 5: Given a completed detection run with miss reports, when the summary is printed, then each missed transition is listed with its type and estimated timeframe in both `MMmSSs` and raw seconds format.
- [x] AC 6: Given the `run()` function completes, when the caller unpacks the return value, then it receives a 4-tuple `(exported, frame_count, profile_stats, miss_reports)` where `miss_reports` is a list (empty if no recoveries occurred).

## Additional Context

### Dependencies

None — all changes are within existing codebase. No new packages required.

### Testing Strategy

- **Regression**: Run astera.mp4 through detector, compare output against `tests/fixtures/astera_expected.json` — must match exactly with zero recovery events
- **Recovery validation**: Run frozen.mp4 and lvlaste.mkv, verify recovery detections fire in the known gap windows
- **Miss report**: Verify miss report output provides actionable timeframes (can be directly used as `--range` values for the ROI debugger)
- **Manual spot-check**: Use ROI debugger on reported miss windows to confirm the missed transitions are real

### Notes

- lvlaste.mkv: first missed end is at ~17:19s, first blackscreen at ~19:20s. Current output jumps from start_003 (10:41) to end_004 (24:10).
- frozen.mp4: suspicious ~9 minute gaps at end_002→start_003 and end_006→start_007.
- astera.mp4: clean alternation, 9 starts + 9 ends, confirmed good — use as regression baseline.
- The `waiting_for_end` state currently has no transition check (fires on any frame where `is_end_loading` is True) unlike `undetermined` which checks `not prev_is_end_loading and is_end_loading`. This is not addressed in this spec but is worth noting for future improvement.
- Recovery start detection in `waiting_for_end` uses single-frame detection (no `start_confirm_frames`) — consistent with `undetermined` state behavior. If false positives appear, confirmation logic can be added later.

## Review Notes

- Adversarial review completed
- Findings: 14 total, 4 fixed, 10 skipped (by-design/noise/out-of-scope/cosmetic)
- Resolution approach: auto-fix
- F1 (High): Fixed `last_event_timestamp` not being set in `undetermined` state transitions
- F2 (High): Verified no other callers of `run()` exist — no breakage
- F7 (Low): Extracted magic number `600` to configurable `max_game_duration` from config
- F8 (Low): Updated fixture format to include `miss_reports: []` assertion
