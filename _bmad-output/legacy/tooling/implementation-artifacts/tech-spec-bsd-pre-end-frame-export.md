---
title: 'BSD Score Snapshot — Pre-End Frame Export'
slug: 'bsd-pre-end-frame-export'
created: '2026-03-11'
status: 'completed'
stepsCompleted: [1, 2, 3, 4]
tech_stack: [python, opencv, ffmpeg]
files_to_modify: [tools/black_screen_detector.py, config/config.yaml]
code_patterns: [deferred-batch-extraction, extract_frame_at_timestamp, format_timestamp]
test_patterns: []
---

# Tech-Spec: BSD Score Snapshot — Pre-End Frame Export

**Created:** 2026-03-11

## Overview

### Problem Statement

When reviewing game endings, the user wants to see team score progression — but the BSD only exports the frame immediately before the black screen. There's no way to see the score from earlier in the round without manually scrubbing the video.

### Solution

For each end detection, also extract and export the full-resolution frame at `end_timestamp - 10s`, producing a two-frame carousel (10s before + right before black screen).

### Scope

**In Scope:**
- Extract an additional full-res frame at T-10s for every end detection
- Export it alongside the existing end frame with a clear naming convention
- Handle edge case: if T-10s < 0 or falls before the previous start detection, skip or clamp

**Out of Scope:**
- No OCR / score reading
- No ROI cropping
- No changes to start detection logic

## Context for Development

### Codebase Patterns

- End detections are collected as deferred `extraction_requests` during the state machine loop, then batch-extracted in a post-detection phase using `extract_frame_at_timestamp()`.
- Each extraction request is a dict: `{"timestamp": float, "type": str, "filename": str}`.
- Filenames follow the pattern `MMmSSs_type_seq.png` (e.g., `07m12s_end_001.png`).
- `extract_frame_at_timestamp()` from `utils/video.py` handles full-res frame extraction via ffmpeg input-seek. Works for any timestamp (not just keyframes).
- End detections occur in 3 state machine branches: `undetermined`, `waiting_for_end`, and `waiting_for_start` (recovery). All append to the same `extraction_requests` list.
- `last_event_timestamp` tracks the most recent detection — useful as a lower bound for the T-10s clamp.
- No existing tests in the project.

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `tools/black_screen_detector.py:115` | `run()` — state machine + batch extraction |
| `tools/black_screen_detector.py:439-451` | Batch extraction loop — where T-10s requests get extracted |
| `tools/black_screen_detector.py:35` | `format_timestamp()` — filename timestamp formatting |
| `utils/video.py:276` | `extract_frame_at_timestamp()` — full-res single-frame extraction |
| `config/config.yaml` | Config — new `pre_end_offset` param goes here |

### Technical Decisions

- The 10s offset should be configurable in `config/config.yaml` under `black_detection` as `pre_end_offset`.
- Naming convention: `MMmSSs_end-10s_seq.png` to pair visually with the existing `MMmSSs_end_seq.png`.
- Edge case: if `end_timestamp - offset < 0` or `< last_event_timestamp`, skip the pre-end frame (don't clamp — a clamped frame from a different round/transition is misleading).
- The pre-end extraction request uses `type: "pre-end"` to distinguish from regular end frames in the exported list and summary output.

## Implementation Plan

### Tasks

- [x] Task 1: Add `pre_end_offset` config parameter
  - File: `config/config.yaml`
  - Action: Add `pre_end_offset: 10.0` under `black_detection` section, with a comment explaining it
  - Notes: Placed after `skip_duration` for logical grouping

- [x] Task 2: Read `pre_end_offset` from config in `run()`
  - File: `tools/black_screen_detector.py`
  - Action: At line ~151 (config extraction block), add `pre_end_offset = config["black_detection"].get("pre_end_offset", 10.0)`
  - Notes: Default to 10.0 for backward compatibility if key is missing

- [x] Task 3: Inject pre-end extraction requests at each end detection site
  - File: `tools/black_screen_detector.py`
  - Action: After each of the 3 places where an end `extraction_requests.append(...)` occurs, add logic to also append a `"pre-end"` request:
    1. **`undetermined` branch** (~line 327): after the end request append
    2. **`waiting_for_end` branch** (~line 355): after the end request append
    3. **`waiting_for_start` recovery branch** (~line 419): after the end request append
  - Logic for each site:
    ```python
    pre_end_ts = prev_timestamp - pre_end_offset
    if pre_end_ts >= 0 and pre_end_ts > last_event_timestamp:
        pre_ts_str = format_timestamp(pre_end_ts)
        pre_fname = f"{pre_ts_str}_end-{int(pre_end_offset)}s_{detection_seq:03d}.png"
        extraction_requests.append({"timestamp": pre_end_ts, "type": "pre-end", "filename": pre_fname})
    ```
  - Notes: Uses the same `detection_seq` as the paired end frame so they sort together. The `last_event_timestamp` guard ensures we don't extract a frame from a previous round.

- [x] Task 4: Handle `"pre-end"` type in the batch extraction loop
  - File: `tools/black_screen_detector.py`
  - Action: In the extraction loop (~line 443-451), add an `elif` branch for `"pre-end"` type to print an appropriate log line:
    ```python
    elif req["type"] == "pre-end":
        print(f"  PRE-END -> exported {req['filename']} (frame at {req['timestamp']:.1f}s) [{i}/{len(extraction_requests)}]")
    ```
  - Notes: The actual extraction + write logic is already type-agnostic (lines 444-447), only the print needs a new branch.

- [x] Task 5: Add `"pre-end"` to the summary output
  - File: `tools/black_screen_detector.py`
  - Action: In the summary section (~line 586-595), add a count for pre-end frames:
    ```python
    pre_end_count = sum(1 for e in exported if e["type"] == "pre-end")
    print(f"  Pre-end snapshots: {pre_end_count}")
    ```

### Acceptance Criteria

- [ ] AC 1: Given a video with at least one end detection where `end_timestamp > pre_end_offset`, when BSD runs, then two frames are exported per end event: `MMmSSs_end_NNN.png` and `MMmSSs_end-10s_NNN.png`.
- [ ] AC 2: Given `pre_end_offset: 10.0` in config, when an end is detected at timestamp 45.0s, then the pre-end frame is extracted at 35.0s.
- [ ] AC 3: Given an end detection at timestamp 5.0s (less than `pre_end_offset`), when BSD runs, then no pre-end frame is exported for that event (skipped, not clamped).
- [ ] AC 4: Given two consecutive detections where `end_timestamp - pre_end_offset < last_event_timestamp`, when BSD runs, then the pre-end frame is skipped to avoid capturing a frame from the previous round.
- [ ] AC 5: Given `pre_end_offset` is absent from config, when BSD runs, then it defaults to 10.0s (backward compatible).
- [ ] AC 6: Given a run with pre-end frames exported, when the summary prints, then the count of pre-end snapshots is displayed.

## Review Notes
- Adversarial review completed
- Findings: 7 total, 3 fixed, 4 skipped (1 undecided, 3 low-severity)
- Resolution approach: auto-fix
- F1 (High): Fixed pre-end guard to use `pre_end_safe_after` variable that accounts for loading screen duration after end detections (`timestamp + skip_duration`) vs gameplay start (`timestamp`)
- F2 (Medium): Fixed strict `>` to `>=` (addressed by the `pre_end_safe_after` refactor)
- F3 (Medium): Added `extraction_requests.sort()` by timestamp before batch loop for sequential ffmpeg seeking
