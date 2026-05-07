---
title: 'Warden TUI Launcher'
slug: 'warden-tui-launcher'
created: '2026-03-19'
status: 'Completed'
stepsCompleted: [1, 2, 3, 4]
tech_stack: ['Python 3', 'questionary>=2.0,<3', 'subprocess (stdlib)', 'json (stdlib)']
files_to_modify: ['requirements.txt', '.gitignore']
files_to_create: ['wardentooling.py']
code_patterns: ['subprocess.run for all tool invocations', 'questionary for all prompts/menus', 'JSON file for last-run state']
test_patterns: ['manual smoke test per tool path']
---

# Tech-Spec: Warden TUI Launcher

**Created:** 2026-03-19

## Overview

### Problem Statement

Running Warden pipeline tools requires memorizing exact script names, argparse argument syntax, and option flags across 6+ tools. There is no unified entry point — every invocation must be typed from scratch, making the toolset hard to use without constantly consulting `--help` output.

### Solution

A single `python wardentooling.py` entry point that launches a `questionary`-based TUI. The TUI presents the 3 pipeline tools in a top-level menu plus a Dev/Diagnostics submenu, handles file/directory selection filtered by correct type, and persists the last command so the user can re-run it on a new source with one keystroke.

### Scope

**In Scope:**
- `wardentooling.py` root entry point
- Main menu: Tool 1 (game_detector), Tool 2 (frame_labeler), Tool 3 (map_config_generator)
- Dev/Diagnostics submenu: image_inspector, bsd_roi_debugger, points_state_detector
- File selection: manual path entry OR interactive folder browse filtered by `.mp4` (video tools) or directory (labeler, config gen)
- Last-run persistence: save last tool + args to `.warden_last_run.json`; on next launch offer "run again on new source / same source / skip"
- Library: `questionary` (lightweight, terminal-native)

**Out of Scope:**
- Modifying underlying tool scripts
- `pyproject.toml` packaging or shell alias installation
- Any GUI beyond the terminal TUI

## Context for Development

### Codebase Patterns

- All tools use `sys.path.insert(0, ...)` to allow imports from project root — `wardentooling.py` at project root does NOT need this
- Every tool follows consistent argparse conventions: `video` (positional), `-o/--output-dir`, `-c/--config` (default `config/config.yaml`), `--threshold`, `--profile`, `--roi`
- `frame_labeler.py` scans for PNG files with `score` in filename — expects Tool 1 output directory as its source
- `map_config_generator.py` uses a mutually exclusive group: `--images DIR` OR `--video MAP_NAME VIDEO_PATH` (repeatable)
- `image_inspector` is a package launched as `python -m tools.image_inspector [image_path]`
- All tools stream stdout/stderr to terminal naturally when invoked via `subprocess.run`

### Tool Invocation Reference

| Tool | Command | Key args |
| ---- | ------- | -------- |
| Tool 1 — game_detector | `python tools/game_detector.py <video>` | `-o`, `-c`, `--profile` |
| Tool 2 — frame_labeler | `python tools/frame_labeler.py <source_dir>` | `-o` |
| Tool 3 — map_config_generator (images) | `python tools/map_config_generator.py --images <dir>` | `-o`, `-c`, `--preview` |
| Tool 3 — map_config_generator (video) | `python tools/map_config_generator.py --video MAP PATH [...]` | `-o`, `-c`, `--preview` |
| Dev — image_inspector | `python -m tools.image_inspector [image]` | image optional |
| Dev — bsd_roi_debugger | `python tools/bsd_roi_debugger.py <video>` | `--range START:END`, `-o`, `-c`, `--threshold` |
| Dev — points_state_detector | `python tools/points_state_detector.py <video>` | `-o`, `-c`, `--roi`, `--profile` |

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `tools/game_detector.py:353` | argparse block — positional `video`, `-o`, `-c`, `--profile` |
| `tools/frame_labeler.py:242` | argparse block — optional positional `source`, `-o` |
| `tools/map_config_generator.py:288` | argparse block — mutex group `--images`/`--video`, `-o`, `-c`, `--preview` |
| `tools/image_inspector/__main__.py:15` | argparse block — optional positional `image` |
| `tools/bsd_roi_debugger.py:169` | argparse block — `--range` default `0:15`, `--threshold` |
| `tools/points_state_detector.py:305` | argparse block — `--roi` default `points` |
| `requirements.txt` | Add `questionary>=2.0,<3` |
| `.gitignore` | Add `.warden_last_run.json` |

### Technical Decisions

- **Invocation:** `subprocess.run(["python", ...], cwd=<project_root>)` — streams output naturally, avoids tkinter import side-effects
- **TUI library:** `questionary` — `questionary.select()` for menus, `questionary.text()` for path input, `questionary.confirm()` for confirmations, `questionary.checkbox()` for optional flags
- **Last-run state schema:**
  ```json
  {
    "tool": "game_detector",
    "label": "Tool 1 — Extract Rounds",
    "args": ["tools/game_detector.py", "path/to/video.mp4", "-o", "output/"],
    "video_path": "path/to/video.mp4"
  }
  ```
- **File browsing:** List `.mp4` files in CWD; if none found go straight to manual entry. Directories: list immediate subdirs of CWD. Always append a "[ Enter path manually ]" option at the bottom of any list.
- **`wardentooling.py` internal structure:**
  - `load_last_run() -> dict | None`
  - `save_last_run(tool, label, args, video_path)`
  - `run_tool(args: list[str])` — calls `subprocess.run`
  - `browse_video_file(prompt) -> str` — `.mp4` picker + manual fallback
  - `browse_directory(prompt) -> str` — subdir picker + manual fallback
  - `flow_tool1() -> list[str]` — collects game_detector args
  - `flow_tool2() -> list[str]` — collects frame_labeler args
  - `flow_tool3() -> list[str]` — collects map_config_generator args
  - `flow_dev_roi_debugger() -> list[str]`
  - `flow_dev_points_detector() -> list[str]`
  - `flow_dev_image_inspector() -> list[str]`
  - `menu_dev()` — dev submenu loop
  - `menu_main()` — main menu loop with last-run offer
  - `main()` — entry point with KeyboardInterrupt handling

## Implementation Plan

### Tasks

- [x] Task 1: Add `questionary` dependency
  - File: `requirements.txt`
  - Action: Append `questionary>=2.0,<3` as a new line

- [x] Task 2: Gitignore last-run file
  - File: `.gitignore` (create if missing)
  - Action: Append `.warden_last_run.json`

- [x] Task 3: Create `wardentooling.py` — core skeleton
  - File: `wardentooling.py` (new, at project root)
  - Action: Add module docstring, imports (`os`, `sys`, `json`, `subprocess`, `questionary`), define `LAST_RUN_FILE = ".warden_last_run.json"` and `PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))` constants, implement `load_last_run()`, `save_last_run()`, and `run_tool(args)` functions
  - Notes:
    - `run_tool` calls `subprocess.run(["python"] + args, cwd=PROJECT_ROOT)` — no return value check, exit code is ignored (tool output already visible)
    - `load_last_run` returns `None` if file missing or JSON invalid (never crash on corrupt state)

- [x] Task 4: File selection helpers
  - File: `wardentooling.py`
  - Action: Implement `browse_video_file(prompt) -> str` and `browse_directory(prompt) -> str`
  - Notes:
    - `browse_video_file`: scan CWD for `*.mp4` with `glob.glob`; if results found, present as `questionary.select` with `"[ Enter path manually ]"` appended; validate selected/entered path exists, re-prompt on failure
    - `browse_directory`: scan CWD immediate subdirs with `os.scandir`; same pattern
    - Both functions loop until a valid path is returned

- [x] Task 5: Tool 1 argument flow
  - File: `wardentooling.py`
  - Action: Implement `flow_tool1() -> list[str]`
  - Notes:
    - Collect: `video` via `browse_video_file`, optional `-o` via `questionary.text` (blank = skip), `--profile` via `questionary.confirm` default No
    - Config `-c` always defaults to `config/config.yaml` — do not ask unless user explicitly needs override (out of scope for now)
    - Returns: `["tools/game_detector.py", video_path, ...]` — relative paths, run from PROJECT_ROOT

- [x] Task 6: Tool 2 argument flow
  - File: `wardentooling.py`
  - Action: Implement `flow_tool2() -> list[str]`
  - Notes:
    - Collect: `source` dir via `browse_directory` (hint: "select Tool 1 output folder"), optional `-o` via `questionary.text`
    - Returns: `["tools/frame_labeler.py", source_dir, ...]`

- [x] Task 7: Tool 3 argument flow
  - File: `wardentooling.py`
  - Action: Implement `flow_tool3() -> list[str]`
  - Notes:
    - First ask input mode: `questionary.select(["From image directory (--images)", "From video files (--video)"])`
    - `--images` path: collect dir via `browse_directory`
    - `--video` path: loop — collect map name (`questionary.text`) + video path (`browse_video_file`), ask "Add another map? (y/n)" — build `["--video", map, path, "--video", map2, path2, ...]`
    - Both paths: ask optional `--preview` flag and `-o` output dir
    - Returns: `["tools/map_config_generator.py", ...]`

- [x] Task 8: Dev tool argument flows
  - File: `wardentooling.py`
  - Action: Implement `flow_dev_roi_debugger()`, `flow_dev_points_detector()`, `flow_dev_image_inspector()`
  - Notes:
    - `flow_dev_roi_debugger`: collect `video` via `browse_video_file`, `--range` via `questionary.text` default `"0:15"` (validate format `N:N` with regex `^\d+:\d+$`), optional `--threshold` int, optional `-o`
    - `flow_dev_points_detector`: collect `video`, optional `--roi` (default `points`), optional `--profile`
    - `flow_dev_image_inspector`: collect optional image via `browse_video_file` adapted for `*.png` OR skip; returns `["-m", "tools.image_inspector"]` + optional path
    - Note: image_inspector uses `-m tools.image_inspector` not a direct `.py` path

- [x] Task 9: Dev submenu
  - File: `wardentooling.py`
  - Action: Implement `menu_dev()`
  - Notes:
    - `questionary.select` with choices: "Image Inspector", "ROI Debugger", "Points State Detector", "← Back"
    - Loop until "Back" selected
    - Each choice calls its flow function, then calls `run_tool()`

- [x] Task 10: Main menu + last-run offer + entry point
  - File: `wardentooling.py`
  - Action: Implement `menu_main()` and `main()`
  - Notes:
    - `main()` wraps everything in `try/except KeyboardInterrupt` — prints `"\nBye."` and exits cleanly
    - On start: `load_last_run()` — if not None, show `questionary.select` with `["Run on new source", "Run with same args", "Skip"]`; "new source" calls the matching flow with video pre-skipped (re-prompt video only), "same args" calls `run_tool` directly, "Skip" proceeds to main menu
    - Main menu choices: "Tool 1 — Extract Rounds", "Tool 2 — Label Frames", "Tool 3 — Generate Map Config", "Dev Tools", "Quit"
    - Each pipeline tool choice: call flow → confirm args summary → `run_tool` → `save_last_run`
    - Loop main menu until Quit

### Acceptance Criteria

- [x] AC 1: Given `wardentooling.py` exists at project root, when user runs `python wardentooling.py`, then a questionary menu appears with Tool 1, Tool 2, Tool 3, Dev Tools, Quit — no import errors
- [x] AC 2: Given no `.warden_last_run.json` exists, when TUI starts, then no last-run prompt is shown and main menu is displayed directly
- [x] AC 3: Given `.warden_last_run.json` contains a valid previous run, when TUI starts, then user is offered "Run [tool label] again?" with options: new source / same source / skip
- [x] AC 4: Given user selects Tool 1, when prompted for video file, then TUI lists `.mp4` files found in CWD; user can pick from list OR enter a custom path; non-existent paths trigger re-prompt, not a crash
- [x] AC 5: Given user selects Tool 2, when prompted for source directory, then TUI lists subdirectories of CWD and offers manual entry; selected path is validated to exist
- [x] AC 6: Given user selects Tool 3 and chooses `--video` mode, when adding map+video pairs, then user is repeatedly asked "Add another map?" until they answer No; at least one pair is required
- [x] AC 7: Given any tool flow completes and user confirms, when `run_tool` is called, then the tool process launches with output streaming visibly to terminal and control returns to TUI after completion
- [x] AC 8: Given a tool run completes, when control returns to TUI, then `.warden_last_run.json` is written/updated with `tool`, `label`, `args`, and `video_path`
- [x] AC 9: Given user selects Dev Tools, then a submenu appears with Image Inspector, ROI Debugger, Points State Detector, Back; selecting Back returns to main menu
- [x] AC 10: Given user selects ROI Debugger, when prompted for time range, then default `"0:15"` is pre-filled; non-`N:N` input is rejected with re-prompt
- [x] AC 11: Given user selects Image Inspector, when launched, then `python -m tools.image_inspector` is called (not `python tools/image_inspector/__main__.py`)
- [x] AC 12: Given user presses Ctrl+C at any prompt, then TUI exits with message `"Bye."` and no Python traceback

## Additional Context

### Dependencies

- `questionary>=2.0,<3` — new dependency, must be `pip install`ed before use
- All existing tool dependencies unchanged
- No dependency on any `tools/` module — `wardentooling.py` uses only stdlib + questionary

### Testing Strategy

Manual smoke test checklist (run after implementation):
1. `python wardentooling.py` — verify main menu appears
2. Select Tool 1 → pick a `.mp4` → accept defaults → confirm → verify game_detector launches and output streams
3. Exit and re-run — verify last-run prompt appears with correct tool label
4. Select "Run with same args" — verify tool re-runs without re-prompting
5. Select "Run on new source" — verify only video file is re-prompted
6. Select Tool 3 → `--video` mode → add 2 maps → verify both `--video` pairs appear in args
7. Select Dev Tools → ROI Debugger → enter invalid range `abc` → verify re-prompt
8. Press Ctrl+C mid-menu — verify clean exit, no traceback

### Notes

- **Risk:** `questionary` may behave differently in Windows Terminal vs VSCode integrated terminal — test both. On Windows, `questionary` requires a proper TTY; if run via pipe/redirect it may fail silently.
- **Risk:** `subprocess.run(["python", ...])` assumes `python` resolves to Python 3. If the user's environment uses `python3`, the command will fail. Consider `sys.executable` instead of `"python"` — use `subprocess.run([sys.executable, ...])` to always use the same interpreter that launched the TUI.
- **Future:** Could add a `--no-tui` flag to `wardentooling.py` that accepts the same args as the underlying tools for scripting use.
- **Future:** The "new source" last-run feature currently only re-prompts `video_path`. Tools with non-video inputs (Tool 2 source dir, Tool 3 images dir) would also benefit from a "new source" concept — left for a follow-up.

## Review Notes

- Adversarial review completed
- Findings: 10 total, 10 fixed, 0 skipped
- Resolution approach: auto-fix
- Key fixes applied: dead `skip_video` param removed; `last["args"]` KeyError guarded; `flow_tool3` None-mode cancel guarded; `run_tool` now returns exit code and last-run only saved on success; `browse_video_file` scans recursively (finds videos in `source/`); `browse_image_file` scans root only (no expensive recursive glob); `browse_directory` excludes code dirs; confirm prompt uses `sys.executable` basename; image inspector accepts all image formats; "Run on new source" re-prompts only the source path (video/dir) keeping other flags
