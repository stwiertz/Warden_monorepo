---
title: 'Warden Image Inspector Tool'
slug: 'warden-image-inspector'
created: '2026-03-02'
status: 'in-progress'
stepsCompleted: [1, 2]
tech_stack: ['Python', 'tkinter', 'Pillow', 'OpenCV']
files_to_modify: []
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

_(To be completed in Step 3)_

### Acceptance Criteria

_(To be completed in Step 3)_

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

_(To be completed in Step 3)_

### Notes

- Tool placement: all UI controls in a top toolbar to avoid obscuring image content
- Zoom constraints: scroll-out stops at "full image fits in canvas", scroll-in allows pixel-level precision
- User is intermediate skill level — tool should be intuitive without documentation
