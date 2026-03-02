---
title: 'Warden Image Inspector Tool'
slug: 'warden-image-inspector'
created: '2026-03-02'
status: 'in-progress'
stepsCompleted: [1]
tech_stack: ['Python']
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

- **GUI Toolkit:** TBD — to be determined in Step 2 investigation (candidates: tkinter, PyQt, OpenCV highgui)
- **Image handling:** OpenCV or Pillow for PNG loading and HSV conversion
- **Coordinate system:** All coordinates reported in original image pixel space, regardless of display scaling/zoom level
- **Log format:** TBD — simple text or structured (JSON/CSV)

## Implementation Plan

### Tasks

_(To be completed in Step 3)_

### Acceptance Criteria

_(To be completed in Step 3)_

## Additional Context

### Dependencies

_(To be determined in Step 2)_

### Testing Strategy

_(To be completed in Step 3)_

### Notes

- Tool placement: all UI controls in a top toolbar to avoid obscuring image content
- Zoom constraints: scroll-out stops at "full image fits in canvas", scroll-in allows pixel-level precision
- User is intermediate skill level — tool should be intuitive without documentation
