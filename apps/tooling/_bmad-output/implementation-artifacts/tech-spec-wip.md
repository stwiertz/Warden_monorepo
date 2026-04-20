---
title: 'Minimap View Mode Tool'
slug: 'minimap-view-mode'
created: '2026-04-20'
status: 'in-progress'
stepsCompleted: [1]
tech_stack:
  - 'Python 3.8+'
  - 'Tkinter'
  - 'OpenCV 4.8+ (cv2.VideoCapture for interactive playback)'
  - 'PIL/Pillow (ImageTk display bridge)'
  - 'NumPy'
  - 'PyYAML'
files_to_modify:
  - config/config.yaml
files_to_create:
  - tools/common/__init__.py
  - tools/common/video_player.py
  - tools/minimap_view_mode/__init__.py
  - tools/minimap_view_mode/__main__.py
  - tools/minimap_view_mode/app.py
  - tools/minimap_view_mode/hud_config.py
  - tools/minimap_view_mode/view_renderer.py
  - tools/minimap_view_mode/roi_overlay.py
code_patterns:
  - 'tk.Tk subclass with toolbar + canvas layout (image_inspector/app.py, minimap_zone_selector/app.py)'
  - 'Versioned config entries in config.yaml (minimap_identification.configs[]) applied to hud_versions[]'
  - 'yaml.safe_load + yaml.dump preserve-other-keys pattern (minimap_zone_selector/config_manager.py)'
  - 'ROI dict schema: {name, x, y, width, height} at reference_resolution (config/config.yaml:35-82)'
  - 'REF_W, REF_H = 1920, 1080 constants for reference-resolution scaling (image_inspector/modes.py, minimap_zone_selector/app.py)'
  - 'MAP_LABELS list as canonical map name source (tools/frame_labeler.py:19-34)'
  - 'extract_roi / scale_roi from utils/image.py for ROI cropping & resolution scaling'
  - 'Frame processor hook pattern — VideoPlayer.set_frame_processor(fn) takes (bgr, ts) -> bgr'
test_patterns:
  - 'No test framework present — manual validation only (matches existing tools)'
  - 'view_renderer.render() is a pure function testable with synthetic numpy arrays + ROI dicts'
---

# Tech-Spec: Minimap View Mode Tool

**Created:** 2026-04-20

---

## Overview

### Problem Statement

Warden gameplay videos contain small, scattered HUD elements (minimap, team scores,
timer, capture-point ownership, team health bars) that carry most of the match-critical
information. Reviewing replays to study those elements is hard at native scale — the
minimap alone occupies roughly 234×264px in a 1920×1080 frame (~3% of the screen).
Analysts need a way to re-composite the HUD into focused "view modes" for replay
study, but the raw ROI coordinates that the composite needs don't exist yet for the
new elements (scores strip, team health bars), and the minimap ROI varies per map.

### Solution

An interactive Tkinter + OpenCV tool (`tools/minimap_view_mode/`) with two purposes:

1. **ROI authoring**: load a gameplay video, scrub to a representative frame, and
   draw the required ROIs. Per-map ROIs (minimap) are drawn once per map; shared
   ROIs (team scores, health-bar-left, health-bar-right) are drawn once per HUD
   version. All ROIs are persisted to `config/config.yaml` under a new
   `hud_versions[]` section, versioned the same way the existing
   `minimap_identification.configs[]` entries are.

2. **Live view-mode preview**: a pluggable per-frame "shader"
   (`view_renderer.py`) re-composites each video frame into one of three modes:
   - `normal` — pass-through (original frame).
   - `minimap_hud` — minimap scaled to occupy ~80% of the output centered, with
     team health bars at their native pixel size flanking the minimap and the
     scores strip across the top, rendered on a black canvas the same size as the
     source frame.
   - `minimap_only` — minimap scaled to fit the output area with aspect ratio
     preserved, rest of the canvas black.

   The view-mode toggle is a live radio/segmented control that re-renders in
   real time during playback — the same video can be scrubbed in any mode without
   reloading.

### Scope

**In Scope:**

- Tkinter + OpenCV GUI reusing the shared `VideoPlayer` widget in
  `tools/common/video_player.py`
- Video loading via CLI arg (`--video PATH`) and File → Open menu item
- Playback controls already provided by VideoPlayer: play/pause, restart, seek
  slider, current-time / total-time label
- Versioned `hud_versions[]` section in `config/config.yaml`. Each version contains:
  - `id` (string, e.g. `v1`)
  - `shared_rois`: `{scores, health_left, health_right}`, each an ROI dict
  - `maps`: map_name → `{minimap: {tight_roi, padding_px}}` (padding applied on top
    of the tight ROI at render time, clamped to frame bounds)
- HUD-version selector combobox with New / Clone / Delete buttons (matches the
  config-version UX in `minimap_zone_selector`)
- Map selector combobox populated from `MAP_LABELS` (`tools/frame_labeler.py`)
- ROI authoring workflow:
  - User pauses on a frame, clicks one of: "Set Minimap ROI (map)",
    "Set Scores ROI", "Set Health Bar Left", "Set Health Bar Right"
  - Canvas enters draw mode; click-drag draws a rectangle
  - Esc cancels, Enter / mouse-up commits
  - For minimap ROIs: after commit, a padding slider appears (0 to N pixels)
    that expands the ROI on all sides at render time, clamped so it never
    extends past the source frame edges. This lets the user draw the tightest
    possible rectangle containing the full minimap and then try different padding
    visually without redrawing.
- ROI overlay renderer: all defined ROIs for the current hud_version + selected
  map are drawn on the paused frame as colored rectangles with labels, so the
  author sees what's already captured at any time
- View-mode shader (`view_renderer.py`):
  - Pure function `render(bgr_frame, mode, hud_version, map_name) -> bgr_frame`
  - Three modes: `normal`, `minimap_hud`, `minimap_only`
  - Live-hooked into VideoPlayer via `set_frame_processor()`
- View-mode toggle (radio buttons): `Normal | HUD | Minimap` — re-renders
  immediately, keeps playing if the video was playing
- Explicit "Save" button that writes the in-memory HUD version to
  `config/config.yaml`. Unsaved edits are kept in memory and indicated with a
  `*` in the window title
- "Unsaved changes — save before closing?" confirmation dialog on window close
- Reference resolution is 1920×1080 (hardcoded, matches other tools). ROIs are
  stored at reference resolution and scaled to the video's native resolution for
  rendering via `utils/image.scale_roi`

**Out of Scope:**

- Map detection / timeline match splitting (that's Tool 2 `match_preview`, a
  separate spec)
- Migration of existing `roi_zones` in `config.yaml` into `hud_versions`. The
  two sections coexist; existing tools continue using `roi_zones`
- Exporting a re-rendered video file (preview is on-screen only)
- Multi-monitor / fullscreen kiosk mode
- OCR on scores / timer / health values (ROI extraction only — values are
  consumed visually)
- HSV zone definitions (those stay in `minimap_identification.configs[]`)
- Keyboard shortcuts beyond Space = play/pause, Esc = cancel-draw
- Automatic ROI detection (users draw them manually)
- Undo/redo history (only the last-drawn ROI per slot is kept)

## Context for Development

### Codebase Patterns

The tool must follow established conventions observed in the existing codebase:

- **Tk app structure**: `tk.Tk` subclass with a toolbar at top, a main canvas in
  the center (via `pack`), optional side panel on the right. See
  `tools/minimap_zone_selector/app.py:27-68` and `tools/image_inspector/app.py`
  for reference layouts.
- **Versioned config entries**: the `ConfigManager` pattern in
  `tools/minimap_zone_selector/config_manager.py` is the canonical way to
  read/write versioned entries in `config.yaml`. `hud_versions[]` should mirror
  its load / save / upsert / delete / clone API.
- **YAML preservation**: `yaml.safe_load` + `yaml.dump(default_flow_style=False)`
  preserves other top-level keys when writing. See
  `tools/minimap_zone_selector/config_manager.py:20-26`.
- **ROI schema**: `{name: str, x: int, y: int, width: int, height: int}` at
  reference resolution 1920×1080, as used throughout `config/config.yaml:35-82`
  and `utils/image.py`.
- **Map labels**: `MAP_LABELS` is the single source of truth for map names.
  Import from `tools.frame_labeler` — do **not** duplicate the list.
- **Reference-resolution scaling**: when the author draws on a frame at native
  resolution, convert canvas coords → video pixel coords → reference-resolution
  coords via the math in `utils/image.scale_roi` (used in reverse).
- **Frame-processor hook**: `VideoPlayer.set_frame_processor(fn)` is already
  implemented — install the shader by passing a bound method that closes over
  the current hud_version / map / mode.

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `tools/common/video_player.py` | Shared video player widget (already created) — provides playback, seeking, frame-processor hook, canvas↔video coord conversion |
| `tools/minimap_zone_selector/config_manager.py` | Reference for load / save / upsert pattern against `config.yaml` — mirror for `hud_versions[]` |
| `tools/minimap_zone_selector/zone_model.py` | Reference for dataclass-based config models |
| `tools/image_inspector/modes.py:234-467` | ROIMode — reference for click-drag rectangle drawing and canvas↔reference-resolution coordinate math |
| `tools/image_inspector/app.py` | Reference for toolbar + canvas layout |
| `tools/frame_labeler.py:19-34` | `MAP_LABELS` list — canonical map name source |
| `utils/image.py:49-101` | `extract_roi()` and `scale_roi()` — used by the shader to crop and scale HUD elements from the frame |
| `utils/config.py` | `load_config()` — used during tool startup |
| `config/config.yaml:35-82` | Existing `roi_zones` — format reference for new `hud_versions[].shared_rois` and `hud_versions[].maps[].minimap` |

### Technical Decisions

- **Video decode library**: `cv2.VideoCapture` rather than the ffmpeg subprocess
  helpers in `utils/video.py`. Rationale: interactive playback needs cheap random
  seeking and per-frame reads on the main thread; ffmpeg subprocess pipes are
  designed for streaming extraction workflows, not UI scrubbing.
- **UI framework**: Tkinter. Matches every existing GUI tool in the repo. No Qt
  / no web frontend.
- **Coordinate system**: ROIs are stored at reference resolution (1920×1080)
  regardless of the loaded video's native resolution. The shader scales ROIs at
  render time via `utils/image.scale_roi`.
- **HUD version scope**: per-map minimap ROIs live *inside* each hud_version
  (e.g. `hud_versions[v1].maps.horizon.minimap`). Rationale: a HUD patch can
  reposition the minimap, so nesting keeps historical configs intact — same
  reasoning as the existing `minimap_identification.configs[]`.
- **Padding storage**: the minimap ROI persisted in config is the tight
  rectangle drawn by the author *plus* the committed `padding_px` as a separate
  field. At render time, the effective ROI is `tight_roi` inflated by
  `padding_px` on all sides, then clamped to frame bounds. Storing padding
  separately (rather than folded into x/y/w/h) lets the author revisit the
  slider in a later session without having reverse-engineer the original tight
  rectangle.
- **Save semantics**: explicit Save button. In-memory edits are marked dirty
  with a `*` in the title bar. Close-window handler prompts to save if dirty.
- **Map detection**: the tool does **not** auto-detect the current map. The
  user selects it from a combobox. (Auto-detection belongs in Tool 2.)
- **Reference-resolution mismatch**: if the loaded video's aspect ratio differs
  from 16:9, log a warning and continue — matches the behaviour of
  `tools/map_config_generator.py:220-226`.
- **Error handling at boundaries**: missing video file, malformed
  `hud_versions` entry, missing required ROI when switching to a non-`normal`
  view mode — all surface as a user-visible error (messagebox or status bar).
  Missing ROIs in `minimap_hud` mode → fall back to a black region for that
  element so the view still renders.

---

## Implementation Plan

### Tasks

_To be filled in during Step 3 (Generation)._

### Acceptance Criteria

_To be filled in during Step 3 (Generation)._

## Additional Context

### Dependencies

_To be filled in during Step 3 (Generation)._

### Testing Strategy

_To be filled in during Step 3 (Generation)._

### Notes

_To be filled in during Step 3 (Generation)._
