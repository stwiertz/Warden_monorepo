---
title: 'Minimap View Mode Tool'
slug: 'minimap-view-mode'
created: '2026-04-20'
status: 'review'
stepsCompleted: [1, 2, 3]
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

### Deep Investigation — ROI Drawing Pattern (from `tools/image_inspector/modes.py:234-467`)

The canonical click-drag ROI pattern used elsewhere in the repo is:

1. On `<ButtonPress-1>`: store canvas-space `(start_cx, start_cy)`; clear any
   previous preview rect.
2. On `<B1-Motion>`: redraw a dashed preview rectangle from the press point to
   the current cursor position (see `ROIMode._on_drag`, `modes.py:430-436`).
3. On `<ButtonRelease-1>`: convert both corners canvas→image coords, compute
   the bounding rect, reject zero-size selections, then convert image→reference
   resolution via:

```python
scale_x = REF_W / img_w   # 1920 / video_w
scale_y = REF_H / img_h   # 1080 / video_h
ref_xywh = (round(x * scale_x), round(y * scale_y),
            round(w * scale_x), round(h * scale_y))
```

4. Persistent ROIs are drawn on an "overlay" Tk-tag layer and repositioned via
   an overlay-redraw callback when the canvas zooms / pans / resizes.

**Translation to `VideoPlayer`:**

- Use `VideoPlayer.canvas.bind(...)` directly — the binding API is standard Tk.
- Coord conversion: `VideoPlayer.canvas_to_video()` and `video_to_canvas()` are
  already implemented in `tools/common/video_player.py` and mirror
  `ImageCanvas.canvas_to_image` / `image_to_canvas`.
- Overlay persistence: the player already calls `canvas.tag_raise("overlay")`
  after each frame render, so rectangles tagged `"overlay"` remain visible.
  For *repositioning* after resize, subscribe via
  `VideoPlayer.add_frame_listener(fn)`; the callback fires after every render.
- No zoom/pan in the video player (frame fills canvas aspect-preserved), so
  the overlay math is simpler: only resize events need handling.

### Deep Investigation — Config Manager Pattern (from `tools/minimap_zone_selector/config_manager.py`)

The pattern to follow for `hud_versions[]` load/save:

- `_read_yaml()` uses `yaml.safe_load` and returns `{}` on empty file
- `_write_yaml(data)` uses `yaml.dump(..., default_flow_style=False,
  allow_unicode=True)` — **preserves** all unrelated top-level keys in the file
- `load()` returns a list of typed dataclass objects
- `save(list)` writes back, replacing only the owned key
- `upsert(cfg)` = insert or replace by id
- `delete(id)` filters by id and rewrites
- `clone(src_id, new_id)` deepcopies and renames

The new `HudConfigManager` should mirror this exactly, owning the
`hud_versions` top-level key and leaving `minimap_identification`, `roi_zones`,
etc. untouched.

### Confirmed Dependencies

- `cv2` (OpenCV 4.8+) — already in `requirements.txt`
- `PIL/Pillow` — already used by `image_inspector`
- `PyYAML` — already in `requirements.txt`
- `numpy` — already in `requirements.txt`
- No new dependencies needed.

### Confirmed Clean Slate

- `tools/minimap_view_mode/` directory does not yet exist — no legacy
  constraints from prior attempts.
- `hud_versions` key in `config/config.yaml` does not yet exist — free to
  design the schema.
- The `VideoPlayer` widget at `tools/common/video_player.py` was created during
  Step 1 of this workflow and is already committed (`5c50d74`).

### No `project-context.md`

A repo-wide glob for `**/project-context.md` returned no results. No
additional cross-cutting conventions to absorb beyond what's captured above.

---

## Implementation Plan

### Tasks

Tasks are ordered bottom-up: schema → data layer → pure-function renderer →
interactive overlays → UI shell → entry point → manual smoke test. Each task
is independently completable by a fresh developer.

- [ ] **Task 1: Add `hud_versions` schema stub + comments to `config/config.yaml`**
  - File: `config/config.yaml`
  - Action: Append a new top-level `hud_versions:` key to the end of the file
    (after `output:`). Seed with a single default entry showing the full nested
    shape via comments — no actual ROI values yet. See "Notes" for exact YAML.
  - Notes: Document the reference resolution 1920×1080 in a top-of-section
    comment matching the style of `roi_zones` (`config.yaml:33-34`).

- [ ] **Task 2: Create `hud_config.py` with dataclass model + config manager**
  - File: `tools/minimap_view_mode/hud_config.py` (new)
  - Action:
    - Define `@dataclass ROIRect` with `x: int, y: int, width: int, height: int`
      (all at reference resolution).
    - Define `@dataclass MinimapROI` with `tight: ROIRect, padding_px: int = 0`.
    - Define `@dataclass SharedROIs` with `scores: ROIRect | None = None,
      health_left: ROIRect | None = None, health_right: ROIRect | None = None`.
    - Define `@dataclass HudVersion` with `id: str, shared_rois: SharedROIs,
      maps: dict[str, MinimapROI]`.
    - Define `class HudConfigManager(config_path)` mirroring
      `tools/minimap_zone_selector/config_manager.py` with methods `load()`,
      `save(list[HudVersion])`, `upsert(HudVersion)`, `delete(id)`,
      `clone(src_id, new_id)`.
  - Notes: `_read_yaml` / `_write_yaml` must preserve all unrelated top-level
    keys, same `yaml.dump(default_flow_style=False, allow_unicode=True)` call
    as `minimap_zone_selector/config_manager.py:24-26`.

- [ ] **Task 3: Create `view_renderer.py` — pure shader**
  - File: `tools/minimap_view_mode/view_renderer.py` (new)
  - Action:
    - Expose `VIEW_MODE_NORMAL = "normal"`, `VIEW_MODE_MINIMAP_HUD =
      "minimap_hud"`, `VIEW_MODE_MINIMAP_ONLY = "minimap_only"`.
    - Pure function `render(bgr_frame, mode, hud_version, map_name, ref_w=1920,
      ref_h=1080) -> bgr_frame`. `hud_version` is a `HudVersion` dataclass,
      `map_name` is a string, `bgr_frame` is a numpy BGR array at any
      resolution.
    - `normal`: return `bgr_frame` unchanged.
    - `minimap_only`: create black canvas same size as input; crop effective
      minimap ROI (tight + padding, clamped to frame bounds); scale to fit the
      canvas preserving aspect ratio; paste centered.
    - `minimap_hud`:
      - Create black canvas same size as input.
      - Compute target minimap size = 80% of canvas width (aspect-preserved),
        centered vertically and horizontally.
      - Scale minimap ROI → target size, paste at center.
      - If `shared_rois.scores` defined: crop at native size, paste at top
        centered horizontally. If missing: leave black.
      - If `shared_rois.health_left` defined: crop at native size, paste on
        left side centered vertically. If missing: leave black.
      - If `shared_rois.health_right` defined: crop at native size, paste on
        right side centered vertically. If missing: leave black.
      - If `map_name` minimap ROI missing: leave center black.
    - Use `utils.image.scale_roi` to convert ref-resolution ROIs to the native
      frame resolution before cropping, and `utils.image.extract_roi` for the
      actual crop (both exist at `utils/image.py:49-101`).
  - Notes: All operations pure NumPy / cv2.resize — no Tk imports here.
    Function must accept a standalone `HudVersion` so it's testable in
    isolation.

- [ ] **Task 4: Create `roi_overlay.py` — click-drag drawer + persistent overlays**
  - File: `tools/minimap_view_mode/roi_overlay.py` (new)
  - Action:
    - `class ROIDrawer(video_player)` holds a reference to the `VideoPlayer`.
    - Method `start_draw(color, on_commit, on_cancel)`:
      - Pauses the player via `video_player.pause()`.
      - Binds `<ButtonPress-1>`, `<B1-Motion>`, `<ButtonRelease-1>` on
        `video_player.canvas`; binds `<Escape>` on the player.
      - During drag, draws a dashed preview rectangle using
        `create_rectangle(..., outline=color, dash=(4,4), tags="overlay")`
        (mirror `ROIMode._on_drag`).
      - On release: convert canvas corners → video coords via
        `video_player.canvas_to_video()`; clamp to frame bounds; reject
        zero-area; convert video→reference-resolution via
        `scale_x = ref_w / video_w, scale_y = ref_h / video_h`; call
        `on_commit(ROIRect)`. Unbind all handlers.
      - On Escape: clear the preview rect, unbind, call `on_cancel()`.
    - Method `draw_persistent(ref_roi, color, label)`: compute the video-pixel
      rectangle for the ROI (via `scale_roi` in reverse), store it in an
      internal list, draw on the canvas tagged `"overlay"`, and subscribe to
      `video_player.add_frame_listener()` so the rectangle is repositioned
      after every render (useful on window resize — the video coord conversion
      changes).
    - Method `clear_persistent()`: delete overlay items, unsubscribe.
  - Notes: mirror `ROIMode._on_press / _on_drag / _on_release` in
    `tools/image_inspector/modes.py:423-466`. The player's `tag_raise("overlay")`
    call in `_render` keeps rectangles on top without further work here.

- [ ] **Task 5: Create main app `app.py`**
  - File: `tools/minimap_view_mode/app.py` (new)
  - Action: `class MinimapViewModeApp(tk.Tk)` with:
    - **Menubar**: File → Open Video, File → Save, File → Quit.
    - **Top toolbar**:
      - HUD version `ttk.Combobox` + buttons `New` / `Clone` / `Delete`.
      - Map `ttk.Combobox` populated from `tools.frame_labeler.MAP_LABELS`.
      - View-mode `ttk.Radiobutton` group: `Normal` / `HUD` / `Minimap`.
    - **Center**: an instance of `tools.common.video_player.VideoPlayer` with
      controls visible. Install `view_renderer.render` as the frame processor
      via `set_frame_processor(self._shader)` where `_shader` closes over the
      current mode + hud_version + map.
    - **Right panel** (packed right, fixed width):
      - Button "Set Minimap ROI" (per current map).
      - Button "Set Scores ROI" (shared).
      - Button "Set Health Bar Left" (shared).
      - Button "Set Health Bar Right" (shared).
      - `ttk.Scale` padding slider (0–50 px), hidden until a minimap ROI
        exists for the active map. Bound to a live `IntVar`; any change
        triggers a re-render via the shader and updates the dirty flag.
      - "Save" button (shortcut for File → Save). Disabled when not dirty.
    - **Bottom status bar** showing last action / active hud_version + map.
    - **Dirty tracking**: any ROI commit, slider change, new/clone/delete sets
      `self._dirty = True` and appends `*` to `self.title()`.
    - **Close handler**: `self.protocol("WM_DELETE_WINDOW", self._on_close)`
      asks to save if dirty (Save / Discard / Cancel).
    - When a "Set …" button is clicked: pause playback, activate
      `ROIDrawer.start_draw(color, on_commit=self._commit_roi(slot, map),
      on_cancel=...)`.
    - Re-render on every state change that affects the shader (view mode,
      hud version, map, slider) by calling `player.set_frame_processor(self._shader)`
      (which re-renders the current paused frame) or `player._render(...)` if
      already paused.
  - Notes: Prefix the window title with `*` when dirty. First run creates
    `v1` automatically if `hud_versions` is empty.

- [ ] **Task 6: Create `__main__.py` entry point**
  - File: `tools/minimap_view_mode/__main__.py` (new)
  - Action: argparse for `--video PATH` (optional), `--config PATH` (default
    `config/config.yaml`). Instantiate `MinimapViewModeApp(config_path,
    video_path=...)`, call `app.mainloop()`. Validate paths with a clean
    error message if missing.
  - Notes: Match CLI conventions of `tools/minimap_zone_selector/__main__.py`.

- [ ] **Task 7: Create `__init__.py` package marker**
  - File: `tools/minimap_view_mode/__init__.py` (new)
  - Action: One-line docstring. No exports.

- [ ] **Task 8: Manual smoke test**
  - File: none
  - Action: Run `python -m tools.minimap_view_mode --video sample.mp4` and
    verify each AC below manually. Save, quit, relaunch, confirm persistence.
  - Notes: There is no automated test framework in this repo (confirmed in
    Step 2). Manual only, matching every other interactive tool.

### Acceptance Criteria

- [ ] **AC 1** — default version: *Given* `config/config.yaml` has no
  `hud_versions` section, *when* the tool starts, *then* it creates an
  in-memory default `HudVersion(id="v1", shared_rois=SharedROIs(),
  maps={})` and selects it as active. The YAML file is only written on Save.

- [ ] **AC 2** — draw minimap ROI: *Given* a video is loaded and paused on a
  frame, map `horizon` is selected, *when* the user clicks "Set Minimap ROI"
  and drags a rectangle on the canvas, *then* on mouse release the ROI is
  (a) converted from canvas pixels → video pixels → reference-resolution
  (1920×1080) pixels, (b) stored at `hud_version.maps["horizon"].tight`, (c)
  drawn as a persistent labeled overlay on the canvas, (d) the padding slider
  becomes visible defaulted to 0, and (e) the dirty flag is set.

- [ ] **AC 3** — padding slider: *Given* a minimap ROI exists for the active
  map, *when* the user drags the padding slider from 0 to 12, *then* the
  effective minimap ROI used by the `minimap_hud` and `minimap_only` shaders
  becomes `tight` inflated by 12 on all sides, clamped so it never extends
  past the source-frame bounds, and the preview re-renders immediately.

- [ ] **AC 4** — HUD composite render: *Given* all four ROIs are defined for
  HUD version `v1` + map `horizon` with non-empty rectangles, *when* the user
  toggles view mode to `HUD`, *then* each rendered frame contains (a) a black
  background, (b) the minimap scaled to ~80% of canvas width and centered,
  aspect preserved, (c) `health_left` at native size on the left vertically
  centered, (d) `health_right` at native size on the right vertically
  centered, (e) `scores` at native size across the top horizontally centered.

- [ ] **AC 5** — partial ROI fallback: *Given* only the minimap ROI is defined
  (scores + health ROIs are `None`), *when* the user toggles to `HUD`,
  *then* the minimap renders correctly and the missing regions remain black —
  no exception is raised.

- [ ] **AC 6** — close-confirm: *Given* unsaved ROI edits exist (dirty flag
  set), *when* the user closes the window, *then* a dialog prompts "Unsaved
  changes — save before closing?" with three options (Save / Discard /
  Cancel); choosing Save persists to YAML and closes; Discard closes without
  saving; Cancel returns to the app.

- [ ] **AC 7** — YAML preservation: *Given* `config.yaml` already contains
  `roi_zones`, `minimap_identification`, `points_detection`, and other
  sections, *when* the tool writes `hud_versions`, *then* all other top-level
  keys and their nested values remain semantically unchanged (yaml canonical
  reformatting is acceptable).

- [ ] **AC 8** — version isolation: *Given* a user clones `v1` to `v2`, edits
  the scores ROI in `v2`, and saves, *then* `hud_versions[id=v1].shared_rois.scores`
  in `config.yaml` is unchanged and `hud_versions[id=v2].shared_rois.scores`
  holds the new value.

- [ ] **AC 9** — resolution scaling: *Given* the loaded video is 1280×720,
  *when* the user draws an ROI whose canvas-bound rectangle maps to video
  pixels `(100, 50, 200, 100)`, *then* the persisted reference-resolution
  ROI is `(150, 75, 300, 150)` — i.e. scaled by `1920/1280 = 1.5`.

- [ ] **AC 10** — normal pass-through: *Given* view mode is `Normal`, *when*
  the video plays, *then* the canvas shows the input frames pixel-identical
  to the source (modulo the canvas fit-to-size resize which is
  display-only).

- [ ] **AC 11** — auto-pause on draw: *Given* the video is playing, *when*
  the user clicks "Set Scores ROI", *then* playback pauses before the user
  begins dragging.

- [ ] **AC 12** — Escape cancels: *Given* the user has started dragging a
  ROI, *when* they press Escape, *then* the preview rectangle disappears,
  the previous stored ROI (if any) is untouched, and no dirty state is
  recorded for the cancelled draw.

- [ ] **AC 13** — missing video file: *Given* `--video /does/not/exist.mp4`
  is passed, *when* the tool launches, *then* it prints a clean error and
  exits non-zero — no Tk window opens.

- [ ] **AC 14** — version switching: *Given* `v1` and `v2` exist with
  different ROIs for map `horizon`, *when* the user changes the HUD version
  combobox from `v1` to `v2`, *then* the persistent overlays update to reflect
  `v2`'s ROIs and the shader re-renders the current frame with `v2`.

## Additional Context

### Dependencies

**External libraries (no new deps):**

- `cv2` (OpenCV ≥ 4.8) — `requirements.txt` already lists it.
- `PIL/Pillow` — already used by other interactive tools.
- `numpy` — already a top-level dep.
- `PyYAML` — already a top-level dep.

**Internal modules:**

- `tools.common.video_player.VideoPlayer` — committed in `5c50d74`.
- `tools.frame_labeler.MAP_LABELS` — map name source of truth.
- `utils.image.extract_roi`, `utils.image.scale_roi` — ROI crop + scale.
- `utils.config.load_config` — YAML loader used at startup.

**Config preconditions:**

- None hard-required. First run seeds `hud_versions` in memory and only
  writes on Save.

### Testing Strategy

**Automated:** none. The repo has no test framework; its existing interactive
tools (`image_inspector`, `frame_labeler`, `minimap_zone_selector`) are
validated manually. Introducing a framework here would exceed scope.

**Pure-function sanity (optional, developer REPL):**

- `view_renderer.render()` can be exercised with a synthetic 1920×1080 BGR
  numpy array and a stubbed `HudVersion`. Save the output with `cv2.imwrite`
  to visually verify each mode. Because the function takes no Tk or video
  handles, it's trivial to drive from a notebook.

**Manual validation flow (maps 1-to-1 to the acceptance criteria):**

1. Launch `python -m tools.minimap_view_mode` with no args → verify the
   File → Open menu works (AC 13 negative test: bad `--video` path exits
   cleanly).
2. Open a Warden gameplay video → frame renders; play / pause / seek work
   (relies on the already-committed `VideoPlayer`).
3. Switch view mode to `Normal` → confirm pass-through (AC 10).
4. Draw minimap ROI for map `horizon`; verify overlay + slider (AC 2);
   adjust padding 0 → 12 → 0 (AC 3); press Escape mid-drag to verify cancel
   (AC 12).
5. Draw scores + health ROIs (AC 11 — click while playing auto-pauses).
6. Toggle to `HUD` mode — verify composite layout (AC 4); delete
   `shared_rois.scores` and re-toggle to verify graceful fallback (AC 5).
7. Save → reopen `config.yaml` with an editor → verify `roi_zones`,
   `minimap_identification`, and other sections unchanged (AC 7).
8. Close window without saving further edits → confirm dialog (AC 6).
9. Clone `v1` → `v2`, modify, save, re-inspect YAML (AC 8).
10. Load a 720p video and repeat AC 2 math to verify 1.5× scaling to
    reference coords (AC 9).
11. Switch HUD version mid-session and verify overlays refresh (AC 14).

### Notes

**Known risks:**

- **Codec quirks**: `cv2.VideoCapture` may fail to open certain H.265 or
  unusual containers. Surface a clean error; first-draft users can transcode.
- **VFR seek fuzziness**: `CAP_PROP_POS_MSEC` seeking is approximate on
  variable-framerate videos. Good enough for preview; exact-frame seek is out
  of scope.
- **Non-16:9 source**: if the video's aspect ratio isn't 16:9, the ROI
  coordinates stored at 1920×1080 reference may not correspond to a sensible
  HUD layout. Log a warning (mirror `tools/map_config_generator.py:220-226`)
  and continue.

**Known limitations:**

- No undo/redo — the most recent draw per slot wins.
- No keyboard shortcuts beyond Space (play/pause — already in `VideoPlayer`)
  and Esc (cancel draw).
- `view_renderer` does its compositing in Python/NumPy. Fine at 720p; a real
  GLSL shader would matter at 4K, which this tool does not target.

**Explicitly deferred to future tools / iterations:**

- Auto-detecting the active map from the current frame using the existing
  perceptual-hash pipeline (covered by Tool 2 `match_preview` — separate spec).
- Exporting the re-composited view as a video file (ffmpeg pipe-in).
- Migrating the existing `roi_zones` entries into `hud_versions` (kept
  disjoint for this draft, per the decision captured in Step 1).

**Sample YAML shape to seed Task 1 (for reference):**

```yaml
# HUD version configs — each versioned entry captures the ROIs needed by the
# minimap view-mode tool. Coordinates are at reference_resolution (1920x1080)
# and scaled at runtime to the loaded video's native resolution.
hud_versions:
  - id: v1
    shared_rois:
      scores:       {x: 0, y: 0, width: 0, height: 0}   # placeholder
      health_left:  {x: 0, y: 0, width: 0, height: 0}
      health_right: {x: 0, y: 0, width: 0, height: 0}
    maps:
      # horizon:
      #   tight: {x: 104, y: 0, width: 234, height: 264}
      #   padding_px: 0
```
