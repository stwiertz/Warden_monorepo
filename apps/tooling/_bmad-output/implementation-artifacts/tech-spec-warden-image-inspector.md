---
title: 'Warden Image Inspector Tool'
slug: 'warden-image-inspector'
created: '2026-03-02'
status: 'completed'
stepsCompleted: [1, 2, 3, 4]
tech_stack: ['Python', 'tkinter', 'Pillow', 'OpenCV']
files_to_modify: ['tools/image_inspector/__main__.py', 'tools/image_inspector/app.py', 'tools/image_inspector/canvas.py', 'tools/image_inspector/modes.py', 'tools/image_inspector/logger.py', 'tools/image_inspector/requirements.txt']
code_patterns: []
test_patterns: []
---

# Tech-Spec: Warden Image Inspector Tool

**Created:** 2026-03-02

## Overview

### Problem Statement

When working with Warden tooling PNG outputs, there is no quick way to precisely pick HSV color values or define rectangular ROIs with exact pixel coordinates. Doing this manually is tedious and error-prone, especially when creating color filters or feeding coordinates to other Warden tools.

### Solution

A lightweight standalone Python tool with an image canvas (rescale-aware zoom/pan) and a top toolbar for HSV color picking, live HSV filter preview, and rectangle ROI selection. Results display in the UI and are logged to a file for later reference.

### Scope

**In Scope:**

- Load and display PNG images, rescaled to fit the window
- Scroll-wheel zoom (min = full image fit, max = pixel-level precision), pan when zoomed in
- **Color Picker mode:** click to get HSV values at that pixel, with a live swatch
- **HSV Filter Preview mode:** input HSV + tolerance values, everything outside the range is grayed out — helps design color filters visually
- **ROI mode:** draw rectangles, get pixel coordinates (x, y, width, height)
- Top toolbar with mode switching and HSV input fields
- Results displayed in UI for immediate use
- Log file to persist picked values/ROIs across sessions

**Out of Scope:**

- Non-rectangle ROI shapes (polygons, circles, freeform)
- Multi-image or batch processing
- Direct integration/piping to other Warden tools
- Image editing or modification

## Context for Development

### Codebase Patterns

- This is a new standalone tool — no existing application code to integrate with
- Keep it as simple as possible; prioritize ease of use over architecture
- Python with minimal dependencies (prefer standard library + one GUI toolkit)

### Files to Reference

| File | Purpose |
| ---- | ------- |

_(New tool — no existing files to reference)_

### Technical Decisions

- **GUI Toolkit:** **tkinter** (stdlib) — zero-install, sufficient canvas/widget support for this tool's needs. PyQt rejected as overkill (75-150 MB, GPL). OpenCV highgui rejected (no toolbar/text inputs). Dear PyGui rejected (no built-in image viewer, requires GPU).
- **Image loading & display:** **Pillow** — PNG loading, tkinter PhotoImage integration, canvas display
- **Image processing:** **OpenCV (headless)** — `cv2.cvtColor()` for full-image HSV conversion, `cv2.inRange()` for mask generation, NumPy compositing for overlay
- **Single-pixel HSV:** **colorsys** (stdlib) — `rgb_to_hsv()` for click-to-pick, scaled to H:0-360, S:0-100, V:0-100
- **Coordinate system:** All coordinates reported in original image pixel space, regardless of display scaling/zoom level
- **Zoom approach:** Tile-based — crop visible region from PIL Image at current zoom level, resize to canvas size. Pan via `canvas.scan_mark()`/`scan_dragto()`
- **Log format:** JSON lines (one JSON object per line) — structured, easy to parse, appendable
- **Module structure:** Package (`tools/image_inspector/`) with 5 modules instead of a single file. Separation: `__main__.py` (CLI entry), `app.py` (window + toolbar + mode switching), `canvas.py` (zoom/pan/coordinate mapping), `modes.py` (3 mode classes), `logger.py` (JSON-lines writer). Runnable via `python -m tools.image_inspector` or `python tools/image_inspector`.

## Implementation Plan

### Tasks

- [x] Task 1: Project scaffolding and dependencies
  - File: `tools/image_inspector/requirements.txt`
  - Action: Create `requirements.txt` with `Pillow>=10.0` and `opencv-python-headless>=4.8`
  - File: `tools/image_inspector/__main__.py`
  - Action: Create entry point with `argparse` for optional PNG path CLI arg. If no arg, fall back to `tkinter.filedialog.askopenfilename()`. Import and launch `InspectorApp` from `app.py`.
  - Notes: Runnable via `python -m tools.image_inspector` or `python tools/image_inspector`. Keep this file minimal (~30 lines) — just CLI parsing and app launch.

- [x] Task 2: Main window and image canvas with fit-to-window display
  - File: `tools/image_inspector/app.py`
  - Action: Create `InspectorApp(tk.Tk)` class. Set up window with toolbar `tk.Frame` (top) and `ImageCanvas` widget (filling remaining space). Load PNG via Pillow, pass to `ImageCanvas`. Store original PIL Image reference for modes to read pixels from.
  - File: `tools/image_inspector/canvas.py`
  - Action: Create `ImageCanvas(tk.Canvas)` class. Accept PIL Image, compute scale factor to fit canvas, display with `ImageTk.PhotoImage`. Track zoom/offset state. Expose `canvas_to_image(cx, cy)` method for coordinate mapping.
  - Notes: Canvas should expand on window resize. `ImageCanvas` owns all rendering; `InspectorApp` owns toolbar and mode orchestration.

- [x] Task 3: Zoom and pan
  - File: `tools/image_inspector/canvas.py`
  - Action: Bind `<MouseWheel>` (and `<Button-4>`/`<Button-5>` for Linux) to zoom centered on cursor. Implement tile-based redraw: crop visible region from PIL Image at current zoom level, resize to canvas size. Bind middle-click or right-click drag for pan via `canvas.scan_mark()`/`scan_dragto()`. Clamp zoom-out to fit-to-window minimum.
  - Notes: Track `zoom_level` (float, 1.0 = fit-to-window) and `offset_x`/`offset_y` (image pixel coords of canvas top-left). Redraw on zoom/pan/resize.

- [x] Task 4: Top toolbar with mode switching
  - File: `tools/image_inspector/app.py`
  - Action: Build toolbar in `InspectorApp`: three `tk.Radiobutton` widgets for mode selection ("Color Picker", "HSV Filter", "ROI"), a status `tk.Label` for results, and a color swatch `tk.Canvas` rectangle. Mode variable triggers `on_mode_change()` which calls `deactivate()` on previous mode and `activate()` on new mode.
  - File: `tools/image_inspector/modes.py`
  - Action: Define base interface: each mode class has `activate(canvas, toolbar)`, `deactivate()`, and event handler methods. Create stubs for `ColorPickerMode`, `HSVFilterMode`, `ROIMode`.
  - Notes: Default mode = Color Picker. Each mode registers/unregisters its own canvas bindings on activate/deactivate.

- [x] Task 5: Color Picker mode
  - File: `tools/image_inspector/modes.py`
  - Action: Implement `ColorPickerMode`. On left-click: use `ImageCanvas.canvas_to_image(cx, cy)` to get image coords, read RGB from PIL Image, convert to HSV via `colorsys.rgb_to_hsv()` (scaled H:0-360, S:0-100, V:0-100). Update status label with HSV + RGB + (x, y). Update color swatch in toolbar. Call `logger.log_entry()` for the pick.
  - Notes: Also display the image pixel coordinates (x, y) alongside the color values.

- [x] Task 6: HSV Filter Preview mode
  - File: `tools/image_inspector/modes.py`
  - Action: Implement `HSVFilterMode`. On `activate()`: show 6 `tk.Entry` widgets (H, S, V center + tolerance) and "Apply"/"Clear" buttons in a filter frame within the toolbar. On "Apply": convert full image to HSV via `cv2.cvtColor()`, generate mask with `cv2.inRange()`, composite (pixels outside mask grayed at 30% opacity via NumPy blend), pass composited PIL Image to `ImageCanvas.set_display_image()`. On "Clear": restore original. On `deactivate()`: hide the filter frame. Call `logger.log_entry()` for filter applications.
  - Notes: Pre-populate H/S/V fields from last color pick if available (read from app state). Tolerance defaults: H±10, S±40, V±40.

- [x] Task 7: ROI selection mode
  - File: `tools/image_inspector/modes.py`
  - Action: Implement `ROIMode`. On left-click-drag: draw rectangle on `ImageCanvas` via `canvas.create_rectangle()` with `dash` option. On release: use `ImageCanvas.canvas_to_image()` for both corners, compute (x, y, width, height) in image pixel space, display in status label. Delete previous ROI canvas item before drawing new one. Call `logger.log_entry()` for the ROI.
  - Notes: Coordinates must be in original image pixel space. Contrasting color (e.g., red or cyan dashed outline).

- [x] Task 8: JSON-lines log file
  - File: `tools/image_inspector/logger.py`
  - Action: Create `log_entry(image_path, entry_type, data)` function. Appends a JSON object to `inspector_log.jsonl` in the same directory as the inspected image. Format: `{"timestamp": "ISO8601", "image": "filename.png", "type": "color_pick"|"roi"|"hsv_filter", "data": {...}}`. For color picks: `{"x": N, "y": N, "rgb": [R,G,B], "hsv": [H,S,V]}`. For ROIs: `{"x": N, "y": N, "width": N, "height": N}`. For HSV filters: `{"h": [lo,hi], "s": [lo,hi], "v": [lo,hi]}`.
  - Notes: Use `json` stdlib module. Open file in append mode for each write. Include image filename (not full path) in each entry. Keep this module standalone with no tkinter imports — pure I/O.

### Acceptance Criteria

- [x] AC 1: Given a PNG file path as CLI argument, when the tool launches, then the image is displayed fit-to-window in the canvas with the toolbar visible above it.
- [x] AC 2: Given no CLI argument, when the tool launches, then a file dialog opens allowing the user to select a PNG file.
- [x] AC 3: Given a loaded image, when the user scrolls the mouse wheel up over the canvas, then the image zooms in centered on the cursor position, revealing more pixel detail.
- [x] AC 4: Given a zoomed-in image, when the user scrolls the mouse wheel down, then the image zooms out, stopping at fit-to-window as the minimum zoom level.
- [x] AC 5: Given a zoomed-in image, when the user right-click-drags (or middle-click-drags) on the canvas, then the view pans to follow the drag.
- [x] AC 6: Given Color Picker mode is active, when the user left-clicks on the image, then the status label shows the pixel's HSV (H:0-360, S:0-100, V:0-100), RGB (0-255), and image coordinates (x, y), and a color swatch updates to show the picked color.
- [x] AC 7: Given HSV Filter mode is active and H/S/V + tolerance values are entered, when the user clicks "Apply", then pixels outside the HSV range appear grayed out while pixels inside the range appear at full color.
- [x] AC 8: Given ROI mode is active, when the user click-drags on the image, then a dashed rectangle is drawn and the status label shows the ROI as (x, y, width, height) in original image pixel coordinates.
- [x] AC 9: Given any color pick or ROI action, when the action completes, then a JSON line is appended to `inspector_log.jsonl` next to the image file with the correct data format.
- [x] AC 10: Given the window is resized, when the resize completes, then the image redraws correctly at the current zoom level without distortion or clipping artifacts.

## Additional Context

### Dependencies

```
# tools/image_inspector/requirements.txt
Pillow>=10.0
opencv-python-headless>=4.8
```

- **tkinter** — stdlib (may need `python3-tk` package on Linux)
- **colorsys** — stdlib
- **Pillow** ~3-5 MB — PNG loading, tkinter display integration
- **opencv-python-headless** ~30-40 MB — HSV conversion, mask generation (headless = no highgui, smaller install)
- **Total added footprint:** ~35-45 MB

### Testing Strategy

**Unit tests** (not strictly required for a GUI tool, but useful for core logic):
- Coordinate mapping: canvas coords → image pixel coords at various zoom/offset levels
- HSV conversion: verify `pixel_hsv(r, g, b)` output matches expected values for known colors (red, green, blue, white, black)
- JSON log entry format: verify structure and required fields

**Manual testing steps:**
1. Launch with a test PNG (~2000x1500 px) — verify fit-to-window display
2. Launch with no argument — verify file dialog appears
3. Zoom in/out with scroll wheel — verify cursor-centered zoom, min zoom = fit
4. Pan while zoomed in — verify smooth panning, no edge artifacts
5. Color Picker: click known-color regions, verify HSV/RGB values match expected
6. HSV Filter: enter range for a dominant color, apply — verify correct pixels highlighted vs. grayed
7. HSV Filter: clear — verify original image restored
8. ROI: drag rectangle, verify coordinates match expected pixel positions
9. Resize window — verify image redraws correctly
10. Check `inspector_log.jsonl` — verify entries written for picks and ROIs

### Notes

- Tool placement: all UI controls in a top toolbar to avoid obscuring image content
- Zoom constraints: scroll-out stops at "full image fits in canvas", scroll-in allows pixel-level precision
- User is intermediate skill level — tool should be intuitive without documentation
- **Risk: tkinter zoom performance on very large images.** Mitigation: tile-based approach crops only the visible region before resize, keeping canvas updates fast. If performance is still an issue, consider downsampled pyramid (out of scope for v1).
- **Risk: Linux scroll events differ from Windows/macOS.** Mitigation: bind both `<MouseWheel>` and `<Button-4>`/`<Button-5>` events.
- **Future consideration:** copy-to-clipboard for HSV values / ROI coords (out of scope, trivial to add later)

## Review Notes
- Adversarial review completed
- Findings: 15 total, 13 fixed, 2 skipped (noise/undecided)
- Resolution approach: auto-fix
- Fixed: F1 (missing __init__.py), F2 (numpy in requirements), F3 (ROI z-order via overlay tag), F4 (round() instead of int() for HSV scaling), F5 (clamped logged values), F6 (input validation), F7 (redraw throttling via after_idle), F8 (logger graceful error handling), F9 (single Tk root), F11 (corrupt image error handling), F12 (HSV scale constants documented), F13 (persistent canvas items), F14 (comment explaining custom pan)
- Skipped: F10 (unnecessary getattr — noise), F15 (set_display_image dimension guard — undecided, only called internally with same-size images)
