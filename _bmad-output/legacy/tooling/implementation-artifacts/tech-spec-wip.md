---
title: 'Match Preview Tool'
slug: 'match-preview'
created: '2026-04-20'
status: 'in-progress'
stepsCompleted: [1]
tech_stack:
  - 'Python 3.8+'
  - 'Tkinter + ttk'
  - 'OpenCV 4.8+ (cv2.VideoCapture for interactive playback)'
  - 'PIL/Pillow (display bridge inside VideoPlayer)'
  - 'NumPy'
  - 'PyYAML'
  - 'imagehash (perceptual-hash map identification)'
files_to_modify:
  - tools/black_screen_detector.py
files_to_create:
  - tools/match_preview/__init__.py
  - tools/match_preview/__main__.py
  - tools/match_preview/app.py
  - tools/match_preview/match_detector.py
  - tools/match_preview/sidecar.py
code_patterns:
  - 'Reuse tools/common/video_player.VideoPlayer as-is — set_time_range + seek + pause driven by the app'
  - 'Refactor pattern: split a CLI run() into detect_X()/export_X() so detection is reusable without file-export side-effects'
  - 'Shared low-level primitives: utils.video.extract_iframes_scaled, utils.image.scale_roi/extract_roi, utils.image.is_black'
  - 'Perceptual-hash map identification: imagehash.phash against map_config.json (schema from tools/map_config_generator.py)'
  - 'REF_W, REF_H = 1920, 1080 reference-resolution scaling via utils.image.scale_roi'
  - 'MAP_LABELS canonical map-name list (tools/frame_labeler.py:19-34)'
  - 'Tkinter modal progress dialog pattern — Toplevel + ttk.Progressbar, grab_set() to block main window'
test_patterns:
  - 'No test framework — manual validation only (matches existing tools)'
  - 'match_detector.detect_matches() is importable/CLI-callable so detection can be sanity-checked headlessly'
---

# Tech-Spec: Match Preview Tool

**Created:** 2026-04-20

---

## Overview

### Problem Statement

Warden analysts reviewing EVA replays have no desktop equivalent of the mobile
app's per-match browsing workflow: load a recording, pick one of the detected
matches from a list, and watch only that match inside a player whose timeline
is clamped to the match's bounds. Currently analysts must scrub a long
recording manually, guess where each match starts and ends, and risk seeking
past segment boundaries. The underlying ingredients are already in the repo —
round-transition detection (`tools/black_screen_detector.py`) and
perceptual-hash map identification (`tools/map_config_generator.py` +
`map_config.json`) — but they're plumbing that only the CLI exposes, and
`black_screen_detector.run()` couples detection with full-resolution PNG
export, making the detection events awkward to reuse in a GUI.

### Solution

A Tkinter + OpenCV desktop tool (`tools/match_preview/`) that:

1. Loads a gameplay video via File → Open or `--video` CLI arg.
2. Synchronously runs a match-detection pipeline (blocking UI with a modal
   progress dialog) that produces
   `[(map_name, confident, start_s, end_s), ...]`:
   - **Round transitions** come from a refactored
     `black_screen_detector.detect_transitions()` (split out from the
     existing `run()` with the PNG-export side-effect moved to a sibling
     `export_frames()`). The `run()` CLI is preserved by composing both.
   - **Map identification** per segment: pick a representative frame inside
     each segment, run the same `imagehash.phash` pipeline as
     `map_config_generator`, compare against `map_config.json`. Nearest
     Hamming neighbour wins; flag low-confidence below a configurable
     threshold.
3. Caches the detection result in a **sidecar** `<video>.matches.json`
   adjacent to the video. Re-opens skip re-detection when the sidecar's
   recorded `video_mtime` matches the file's current mtime.
4. Presents a match-selector `ttk.Combobox` labeled
   `"Match N: <map_name or 'Map N' fallback> (MM:SS — MM:SS)"` and reuses
   the existing `tools/common/video_player.VideoPlayer` widget with its
   timeline clamped to the selected match via `set_time_range(start, end)`.
5. On match switch, calls `set_time_range(start, end)`, then explicit
   `seek(start)` + `pause()` — new match begins at its start, paused, waiting
   for the user to press play.

### Scope

**In Scope:**

- Refactor of `tools/black_screen_detector.py`:
  - Extract a pure `detect_transitions(video_path, config, threshold_override=None, profile=False) -> (events, frame_count, profile_stats, miss_reports)` function returning the same transition-event shape currently held in `extraction_requests` (dicts with `timestamp`, `type` in `{start, end, pre-end}`, `filename`). No PNG writing inside.
  - Extract `export_frames(events, video_path, output_dir, src_w, src_h) -> exported_list` that does the existing full-res extraction + `cv2.imwrite` loop.
  - `run()` becomes a thin composition: `events, ... = detect_transitions(...)`; `exported = export_frames(events, ...)`. CLI behaviour (filenames, summary output, profile report) must be byte-identical on representative inputs.
- `tools/match_preview/match_detector.py`:
  - Public `detect_matches(video_path, config, map_config, progress_cb=None) -> list[MatchSegment]` where `MatchSegment` is a dataclass/namedtuple `(map_name: str, confident: bool, start_s: float, end_s: float, hamming_distance: int)`.
  - Pairs `start`/`end` events from `detect_transitions` into contiguous match intervals. Unpaired terminal events (start without end, or end without start) are handled deterministically — spec'd in Step 3.
  - For each pair, samples a representative frame (~5s after `start_s`, clamped into range) via `cv2.VideoCapture.set(CAP_PROP_POS_MSEC) + read()`, crops the `map_identification.roi` scaled to the source resolution, computes `imagehash.phash`, finds the nearest map in `map_config.json` by Hamming distance. `confident = hamming_distance < confidence_threshold` (threshold sourced from config, default in Step 3).
  - `progress_cb(stage: str, current: int, total: int)` lets the GUI drive the progress bar during both the transition-scan phase and the per-match map-ID phase.
- `tools/match_preview/sidecar.py`:
  - `load(video_path) -> Optional[list[MatchSegment]]`: returns `None` if the sidecar is missing or `video_mtime`/`video_size` mismatch.
  - `save(video_path, matches)`: writes `<video>.matches.json` with `{video_mtime, video_size, schema_version: 1, matches: [...]}`.
- `tools/match_preview/app.py`:
  - `tk.Tk` subclass. Top bar: `File` menu (`Open…`, `Quit`), match-selector `ttk.Combobox` (disabled until a video is loaded), a small metadata label showing map name + duration of the current match.
  - Center: a `VideoPlayer` instance (its built-in controls supply play/pause/restart/timeline — no duplication).
  - Load flow: open dialog → sidecar check → if miss/stale, spawn a modal `Toplevel` progress dialog (`grab_set()`), run `detect_matches` synchronously driving the progress bar via the callback, close modal, populate combobox, auto-select Match 1, `video_player.load(path)` → `set_time_range(start, end)` → `seek(start)` → leave paused.
  - Match switch: combobox `<<ComboboxSelected>>` handler → `set_time_range(new_start, new_end)` → `seek(new_start)` → `pause()`.
  - Detection failure modes (no matches found, map_config.json missing, video unreadable) surface via `tkinter.messagebox.showerror` — the app stays open with controls disabled.
- `tools/match_preview/__main__.py`: argparse front door; `--video PATH` optional, falls back to `File → Open` dialog when omitted. `--config` path overridable (default `config/config.yaml`). `--map-config` overridable (default `output/map_config.json`).
- `match_detector.py` must also be runnable as `python -m tools.match_preview.match_detector <video> [--config] [--map-config] [--write-sidecar]` — prints `Match N: <label> (start_s=... end_s=...)` and optionally writes the sidecar. No UI dependency in that code path.
- Match label formatting:
  - Confident: `f"Match {N}: {map_name} ({start_mmss} — {end_mmss})"` (e.g. `"Match 1: horizon (02:15 — 06:43)"`).
  - Low-confidence fallback: `f"Match {N}: Map {N} ({start_mmss} — {end_mmss})"` (e.g. `"Match 4: Map 4 (19:30 — 23:50)"`).
  - MM:SS uses the existing formatter style from `VideoPlayer._format_time`.
- Sidecar sits adjacent to the video: if video is `/path/to/game.mp4`, sidecar is `/path/to/game.mp4.matches.json`. Sidecar invalidation: recompute when `os.stat(video).st_mtime != sidecar['video_mtime']` or `.st_size != sidecar['video_size']`.

**Out of Scope:**

- ROI authoring, view-mode rendering, or any HUD compositing (Tool 1's
  domain). Tool 2 never installs a `frame_processor` on `VideoPlayer`.
- Background-threaded detection — blocking the UI with a modal progress
  dialog is a locked design decision.
- Editing or authoring `config/config.yaml`, `map_config.json`, or
  `hud_versions[]`. Tool 2 reads these as inputs only.
- Per-match thumbnail previews in the dropdown.
- Multi-video or session-wide browsing; one video at a time.
- Automated tests (repo has no framework).
- Use of `game_detector.py` as the round-transition source —
  `black_screen_detector.py` is the chosen detector because (a) its
  start/end event semantics map 1:1 to match boundaries, (b) its recovery
  windows handle missing transitions more gracefully, and (c) refactoring
  its `run()` produces a single reusable detection entry point that
  future tools can also reuse.
- Any change to `tools/common/video_player.py`. Its `set_time_range` API
  is used as-is.

## Context for Development

### Codebase Patterns

Captured during Step 2 investigation. Skeleton patterns already identified:

- Module shape: `tools/<tool>/app.py` (Tk subclass) + `tools/<tool>/__main__.py` (argparse entry) + optional helper modules, matching `tools/image_inspector/`, `tools/minimap_zone_selector/`, and Tool 1's planned layout.
- ROI scaling: all ROIs in `config/config.yaml` live at reference resolution `1920×1080`; scale to source via `utils.image.scale_roi(roi, source_h / ref_h)` then `utils.image.extract_roi(frame, scaled)`.
- Perceptual hashing pipeline for map ID: `cv2 → grayscale → cv2.resize to canvas_size²  → PIL Image → imagehash.phash(image, hash_size=hash_size)` (copied from `map_config_generator.process_frame` + `compute_phash`).
- Sidecar JSON schema lives next to the producing tool — Tool 2 owns `<video>.matches.json` format.

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `tools/common/video_player.py` | Reused as-is; `set_time_range(start, end)`, `seek`, `pause`, `restart`, built-in slider + time label. |
| `tools/black_screen_detector.py` | Refactor target: split `run()` into `detect_transitions()` + `export_frames()`. Existing state machine, scan-window logic, adaptive frame sampling preserved. |
| `tools/map_config_generator.py` | Reference implementation for the ROI-crop → grayscale → resize → `phash` pipeline that `match_detector` reuses per segment. |
| `tools/frame_labeler.py:19-34` | `MAP_LABELS` canonical 14-map list; used to validate `map_config.json` and to render labels. |
| `utils/video.py` | `extract_iframes_scaled`, `get_video_info`, `extract_frame_at_timestamp` — primitives reused by both the refactored detector and representative-frame sampling. |
| `utils/image.py` | `extract_roi`, `scale_roi`, `to_grayscale`, `is_black`. |
| `config/config.yaml` | Reads: `reference_resolution`, `processing.target_height`, `black_detection.*`, `team_bar_detection.*`, `map_identification.*`. May add a `match_preview.confidence_threshold` key in Step 3. |
| `_bmad-output/implementation-artifacts/tech-spec-minimap-view-mode.md` | Sibling tool's spec — pattern reference only. Do not import from `tools/minimap_view_mode/` at runtime. |

### Technical Decisions

Locked now (carried forward to Step 3):

- **Detection synchronous on load, UI blocked via modal progress dialog.** Background threading explicitly deferred.
- **BSD refactor (option A) over lean reimplement or temp-dir hack.** Gives Tool 2 a clean dependency and benefits any future tool that wants transitions without PNGs.
- **`black_screen_detector` chosen over `game_detector`.** Start/end semantics align with match boundaries; recovery-window logic handles dropped transitions more gracefully.
- **Sidecar adjacent to the video** (`<video>.matches.json`), mtime + size invalidation.
- **Match switch → jump to start + pause.** Relative-position preservation deemed meaningless across differing-length segments.
- **Reusable `match_detector.py` + CLI.** Ships with `python -m tools.match_preview.match_detector <video>` entry point that prints segments and optionally writes the sidecar.
- **Low-confidence labels use "Map N" fallback** (N = match ordinal), not "?" tag and not a separate group.
- **Reuse `tools/common/video_player.py` unchanged.** No fork, no edit.

Deferred to Step 3 (concrete values, thresholds, edge-case rules):

- Representative-frame sampling offset inside each segment.
- Confidence threshold (Hamming distance cutoff) + where it lives in config.
- Unpaired start / unpaired end handling rules.
- Progress-dialog cancel semantics.
- Exact sidecar schema version + field list.
- `detect_transitions()` return shape (dataclass vs dict-list) and how `run()` composes the two.

## Implementation Plan

### Tasks

_To be filled in Step 3 after deep investigation._

### Acceptance Criteria

_To be filled in Step 3 after deep investigation._

## Additional Context

### Dependencies

No new third-party packages. Uses only what's already in the repo:
`tkinter`, `cv2`, `numpy`, `PIL`, `yaml`, `imagehash`.

### Testing Strategy

Manual only. The repo has no automated test framework. A CLI entry point
(`python -m tools.match_preview.match_detector <video>`) gives a headless
way to sanity-check detection output without launching the Tk app.

### Notes

- `VideoPlayer.set_time_range` auto-seeks only when the current timestamp is outside the new range. The app must therefore follow `set_time_range` with an explicit `seek(start)` when switching matches — documented in the match-switch flow above.
- `black_screen_detector.run()` currently emits `pre-end` events (frame at `T - pre_end_offset`) in addition to `start`/`end`. `match_detector` ignores `pre-end` events when pairing match boundaries.
