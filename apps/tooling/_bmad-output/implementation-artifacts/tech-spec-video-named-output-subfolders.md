---
title: 'Video-named output subfolders'
slug: 'video-named-output-subfolders'
created: '2026-03-01'
status: 'completed'
stepsCompleted: [1, 2, 3, 4]
tech_stack: ['Python 3', 'OpenCV (cv2.imwrite)', 'os.path / pathlib']
files_to_modify: ['tools/black_screen_detector.py']
code_patterns: ['output_dir resolved in main() then passed to run()', 'os.makedirs(output_dir, exist_ok=True) in run()', 'os.path.join(output_dir, filename) for image writes']
test_patterns: ['no automated tests — manual CLI verification']
---

# Tech-Spec: Video-named output subfolders

**Created:** 2026-03-01

## Overview

### Problem Statement

The black screen detector saves all extracted images flat into the output directory (default `./output`). When processing multiple videos, outputs from different videos mix together with no way to distinguish which video produced which images.

### Solution

Extract the video filename stem (without extension) and automatically create a subfolder inside the output directory. All images for that video are saved into this subfolder (e.g., `./output/match_replay_2026/`). This is the default behavior — no config toggle needed.

### Scope

**In Scope:**
- `black_screen_detector.py` output path construction — derive subfolder from video filename

**Out of Scope:**
- `bsd_roi_debugger.py` — no changes
- Config toggles or options to disable this behavior
- Filename format changes (timestamps remain as-is)

## Context for Development

### Codebase Patterns

- Output dir is resolved in `main()` (line 366): CLI `-o` arg overrides config `output.default_dir`
- `run()` receives `output_dir` as a parameter and calls `os.makedirs(output_dir, exist_ok=True)` (line 95)
- Image write path constructed with `os.path.join(output_dir, req["filename"])` (line 247)
- Summary prints absolute path via `os.path.abspath(output_dir)` (line 386)
- Video path is a positional CLI arg (`args.video`), available in `main()`

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `tools/black_screen_detector.py` | Only file to modify — output dir resolution in `main()` |
| `config/config.yaml` | Defines `output.default_dir: ./output` — no changes needed |

### Technical Decisions

- Use `os.path.splitext(os.path.basename(video_path))[0]` to extract video stem — standard library, no new dependencies
- Append video stem to `output_dir` in `main()` before passing to `run()` — `run()` already handles `makedirs`
- No config toggle — this is the new default behavior

## Implementation Plan

### Tasks

- [x] Task 1: Extract video stem and append to output directory
  - File: `tools/black_screen_detector.py`
  - Action: In `main()`, after resolving `output_dir` (line 366), extract the video filename stem using `os.path.splitext(os.path.basename(args.video))[0]` and append it to `output_dir` with `os.path.join(output_dir, video_stem)`
  - Notes: This must happen before `output_dir` is passed to `run()`. The existing `os.makedirs(output_dir, exist_ok=True)` inside `run()` will automatically create the subfolder.

### Acceptance Criteria

- [ ] AC 1: Given a video `source/match_replay.mp4` with default output config, when the detector runs, then images are saved to `./output/match_replay/` (not flat in `./output/`)
- [ ] AC 2: Given a video path with nested directories like `source/season1/match.mp4`, when the detector runs, then only the filename stem `match` is used (not the full path), producing `./output/match/`
- [ ] AC 3: Given the `-o custom_dir` CLI flag is used, when the detector runs, then the video subfolder is created inside the custom dir (e.g., `custom_dir/match_replay/`)
- [ ] AC 4: Given the output subfolder does not exist yet, when the detector runs, then the subfolder is created automatically without error
- [ ] AC 5: Given the output subfolder already exists from a previous run, when the detector runs again, then it reuses the existing folder and overwrites matching filenames without error

## Additional Context

### Dependencies

- No new dependencies. Uses `os.path.basename` and `os.path.splitext` from the standard library, both already imported.

### Testing Strategy

- Manual CLI verification:
  1. Run detector on a video and confirm images appear in `./output/<video_stem>/`
  2. Run with `-o custom_out` and confirm subfolder is created inside custom dir
  3. Run twice on the same video and confirm no errors on existing folder

### Notes

- If a video filename contains special characters (spaces, dots), `os.path.splitext(os.path.basename(...))` handles them correctly — only the final extension is stripped
- Future consideration: the ROI debugger (`bsd_roi_debugger.py`) could adopt the same pattern later if desired

## Review Notes

- Adversarial review completed
- Findings: 12 total, 3 fixed, 9 skipped (noise/uncertain/not actionable)
- Resolution approach: auto-fix
- Fixed: stale docs/architecture.md references (F1/F12), added explanatory comment for ROI loop caching (F3)
- Acknowledged: commit bundling concern (F10) — pre-existing changes not actionable in this workflow
