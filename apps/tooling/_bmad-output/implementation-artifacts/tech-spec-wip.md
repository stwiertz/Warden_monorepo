---
title: 'Warden Image Inspector Tool'
slug: 'warden-image-inspector'
created: '2026-03-02'
status: 'review'
stepsCompleted: [1, 2, 3]
tech_stack: ['Python', 'tkinter', 'Pillow', 'OpenCV']
files_to_modify: ['tools/image_inspector.py', 'tools/requirements.txt']
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

## Implementation Plan

### Tasks

- [ ] Task 1: Project scaffolding and dependencies
  - File: `tools/requirements.txt`
  - Action: Create `requirements.txt` with `Pillow>=10.0` and `opencv-python-headless>=4.8`
  - File: `tools/image_inspector.py`
  - Action: Create main script with imports, argument parsing (accept PNG path via CLI arg or file dialog), and `if __name__ == "__main__"` entry point
  - Notes: Single-file tool. Use `argparse` for optional CLI path, fall back to `tkinter.filedialog.askopenfilename()` if no arg provided.

- [ ] Task 2: Main window and image canvas with fit-to-window display
  - File: `tools/image_inspector.py`
  - Action: Create `InspectorApp(tk.Tk)` class with a `tk.Canvas` filling the window. Load PNG via Pillow, compute scale factor to fit canvas, display with `ImageTk.PhotoImage`. Store original PIL Image and current zoom/offset state.
  - Notes: Canvas should expand on window resize. Maintain mapping between canvas coords and image pixel coords at all times.

- [ ] Task 3: Zoom and pan
  - File: `tools/image_inspector.py`
  - Action: Bind `<MouseWheel>` (and `<Button-4>`/`<Button-5>` for Linux) to zoom centered on cursor. Implement tile-based redraw: crop visible region from PIL Image at current zoom level, resize to canvas size. Bind middle-click or right-click drag for pan via `canvas.scan_mark()`/`scan_dragto()`. Clamp zoom-out to fit-to-window minimum.
  - Notes: Track `zoom_level` (float, 1.0 = fit-to-window) and `offset_x`/`offset_y` (image pixel coords of canvas top-left). Redraw on zoom/pan/resize.

- [ ] Task 4: Top toolbar with mode switching
  - File: `tools/image_inspector.py`
  - Action: Create a `tk.Frame` toolbar at top of window. Add three `tk.Radiobutton` widgets for mode selection: "Color Picker", "HSV Filter", "ROI". Add a status `tk.Label` on the right side of the toolbar to show current results (HSV values, ROI coords). Mode variable controls which mouse bindings are active on the canvas.
  - Notes: Default mode = Color Picker. Switching modes should unbind previous mode's handlers and bind new ones.

- [ ] Task 5: Color Picker mode
  - File: `tools/image_inspector.py`
  - Action: On left-click, map canvas coords to image pixel coords, read RGB from original PIL Image at that pixel. Convert to HSV via `colorsys.rgb_to_hsv()`, scale to H:0-360, S:0-100, V:0-100. Display HSV + RGB in the status label. Draw a small color swatch rectangle on the toolbar (or update an existing `Canvas` rectangle) filled with the picked color.
  - Notes: Also display the image pixel coordinates (x, y) alongside the color values.

- [ ] Task 6: HSV Filter Preview mode
  - File: `tools/image_inspector.py`
  - Action: Add input fields to toolbar (visible when HSV Filter mode is active): H, S, V center values + tolerance for each (6 `tk.Entry` widgets + labels). Add an "Apply" button. On apply: convert full image to HSV via `cv2.cvtColor()`, generate mask with `cv2.inRange()` using the specified range. Composite: pixels outside mask are grayed (e.g., 30% opacity grayscale blend). Display the composited result on canvas. Add a "Clear" button to restore original view.
  - Notes: Pre-populate H/S/V fields from last color pick if available. Tolerance defaults: H±10, S±40, V±40. Use NumPy for the grayscale blend (no separate overlay layer needed — just rebuild the display image).

- [ ] Task 7: ROI selection mode
  - File: `tools/image_inspector.py`
  - Action: On left-click-drag, draw a rectangle on the canvas. On release, compute image-pixel coordinates (x, y, width, height) and display in status label. Draw the rectangle outline on the canvas (dashed line, contrasting color). Support redrawing — each new drag replaces the previous ROI rectangle.
  - Notes: Use `canvas.create_rectangle()` with `dash` option. Delete previous ROI item before drawing new one. Coordinates must be in original image pixel space.

- [ ] Task 8: JSON-lines log file
  - File: `tools/image_inspector.py`
  - Action: On each color pick or ROI selection, append a JSON object to `inspector_log.jsonl` in the same directory as the inspected image. Format: `{"timestamp": "ISO8601", "image": "filename.png", "type": "color_pick"|"roi", "data": {...}}`. For color picks: `{"x": N, "y": N, "rgb": [R,G,B], "hsv": [H,S,V]}`. For ROIs: `{"x": N, "y": N, "width": N, "height": N}`. Also log HSV filter ranges when applied: `{"type": "hsv_filter", "data": {"h": [lo,hi], "s": [lo,hi], "v": [lo,hi]}}`.
  - Notes: Use `json` stdlib module. Open file in append mode for each write. Include image filename (not full path) in each entry.

### Acceptance Criteria

- [ ] AC 1: Given a PNG file path as CLI argument, when the tool launches, then the image is displayed fit-to-window in the canvas with the toolbar visible above it.
- [ ] AC 2: Given no CLI argument, when the tool launches, then a file dialog opens allowing the user to select a PNG file.
- [ ] AC 3: Given a loaded image, when the user scrolls the mouse wheel up over the canvas, then the image zooms in centered on the cursor position, revealing more pixel detail.
- [ ] AC 4: Given a zoomed-in image, when the user scrolls the mouse wheel down, then the image zooms out, stopping at fit-to-window as the minimum zoom level.
- [ ] AC 5: Given a zoomed-in image, when the user right-click-drags (or middle-click-drags) on the canvas, then the view pans to follow the drag.
- [ ] AC 6: Given Color Picker mode is active, when the user left-clicks on the image, then the status label shows the pixel's HSV (H:0-360, S:0-100, V:0-100), RGB (0-255), and image coordinates (x, y), and a color swatch updates to show the picked color.
- [ ] AC 7: Given HSV Filter mode is active and H/S/V + tolerance values are entered, when the user clicks "Apply", then pixels outside the HSV range appear grayed out while pixels inside the range appear at full color.
- [ ] AC 8: Given ROI mode is active, when the user click-drags on the image, then a dashed rectangle is drawn and the status label shows the ROI as (x, y, width, height) in original image pixel coordinates.
- [ ] AC 9: Given any color pick or ROI action, when the action completes, then a JSON line is appended to `inspector_log.jsonl` next to the image file with the correct data format.
- [ ] AC 10: Given the window is resized, when the resize completes, then the image redraws correctly at the current zoom level without distortion or clipping artifacts.

## Additional Context

### Dependencies

```
# requirements.txt
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
