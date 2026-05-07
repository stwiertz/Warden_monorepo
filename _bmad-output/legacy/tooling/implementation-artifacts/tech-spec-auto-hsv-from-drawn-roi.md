---
title: 'Auto-HSV from Drawn ROI'
slug: 'auto-hsv-from-drawn-roi'
created: '2026-03-31'
status: 'Completed'
stepsCompleted: [1, 2, 3, 4]
tech_stack: ['Python', 'tkinter', 'OpenCV (cv2)', 'NumPy', 'Pillow']
files_to_modify: ['tools/minimap_zone_selector/app.py']
code_patterns: ['module-level constants for tunable values', 'private _method helpers on class']
test_patterns: ['no tests exist in project']
---

# Tech-Spec: Auto-HSV from Drawn ROI

**Created:** 2026-03-31

## Overview

### Problem Statement

When drawing a zone in the minimap zone selector, the zone is created with hardcoded default HSV values (h_center=0, h_tol=180, s_center=0, s_tol=12, v_center=100, v_tol=15) that have no relation to the actual colors in the drawn region. The user has to manually dial in HSV from scratch every time.

### Solution

On draw release, sample the pixels from the current frame within the drawn rectangle, compute a circular mean for hue (to handle wraparound) and regular mean for S/V, derive std-based tolerances with a minimum floor, and auto-populate the zone with those values — then auto-load the zone into the HSV editor.

### Scope

**In Scope:**
- Pixel sampling from the current frame on draw release
- Circular mean hue computation (handles wraparound at 0°/360°)
- Std-based tolerance derivation with a minimum floor
- Auto-selecting the newly drawn zone in the HSV editor

**Out of Scope:**
- Multi-frame averaging across all frames for a zone
- Sampling from frames other than the currently displayed one

## Context for Development

### Codebase Patterns

- HSV user-space: H 0–360, S 0–100, V 0–100. OpenCV HSV: H 0–179, S 0–255, V 0–255.
- Zone ref coords are in 1920×1080 reference resolution. The displayed canvas shows a cropped minimap ROI.
- `get_reference_image()` returns PIL RGB; `get_frames()` returns raw BGR `np.ndarray` list — use `get_frames()` for HSV computation to avoid the RGB roundtrip.
- Module-level constants used for tunable values (`ZONE_COLORS`, `DEFAULT_ROI`, `REF_W/REF_H`).
- Private helpers follow `_method_name` convention on the class.
- No tests exist in the project.

### Files to Reference

| File | Purpose |
| ---- | ------- |
| tools/minimap_zone_selector/app.py | Only file modified — add imports, constants, `_compute_zone_hsv` helper, update `_on_draw_release` |
| tools/minimap_zone_selector/hsv_editor.py | `load_zone(zone)` called to auto-select after draw |
| tools/minimap_zone_selector/zone_model.py | Zone dataclass reference |
| tools/minimap_zone_selector/data_loader.py | `get_frames(map_name)` returns `list[np.ndarray]` (BGR) |

### Technical Decisions

- Use **circular mean** for hue: convert OpenCV H (0–179, each unit = 2°) to radians, compute sin/cos mean, `atan2` back. Circular std dev = `sqrt(-2 * log(R))` where R = mean resultant length.
- Tolerances = `max(MIN_TOL, ceil(std_in_user_space * 1.5))`. Constants: `_MIN_H_TOL = 10`, `_MIN_SV_TOL = 5`.
- Access BGR frame via `self._loader.get_frames(self._selected_map)[self._current_frame_index]` rather than re-converting from PIL.
- After appending zone, call `self._hsv_editor.load_zone(zone)` to auto-select it in the editor.

## Implementation Plan

### Tasks

- [x] Task 1: Add imports and tolerance constants to app.py
  - File: `tools/minimap_zone_selector/app.py`
  - Action: Add `import math`, `import cv2`, `import numpy as np` at the top (after existing imports). Add two module-level constants below the existing ones: `_MIN_H_TOL = 10` and `_MIN_SV_TOL = 5`.
  - Notes: cv2 and numpy are already project dependencies (used in data_loader.py and zone_model.py). math is stdlib.

- [x] Task 2: Add `_compute_zone_hsv` private method to `MinimapZoneSelectorApp`
  - File: `tools/minimap_zone_selector/app.py`
  - Action: Add the following method to the class (e.g. after `_get_active_roi`):
    ```python
    def _compute_zone_hsv(self, bgr_frame: np.ndarray, ref_x: int, ref_y: int, ref_w: int, ref_h: int) -> tuple[int, int, int, int, int, int]:
        """Compute HSV center/tolerance from pixels in the zone's reference-coord crop.

        Uses circular mean for hue to handle wraparound at 0°/360°.
        Returns (h_center, s_center, v_center, h_tol, s_tol, v_tol) in user space
        (H 0-360, S 0-100, V 0-100).
        """
        region = bgr_frame[ref_y:ref_y + ref_h, ref_x:ref_x + ref_w]
        hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)

        h = hsv[:, :, 0].astype(np.float32)
        s = hsv[:, :, 1].astype(np.float32)
        v = hsv[:, :, 2].astype(np.float32)

        # Circular mean for hue (OpenCV H: 0-179, each unit = 2°)
        angles = h * (2.0 * math.pi / 180.0)
        sin_mean = float(np.mean(np.sin(angles)))
        cos_mean = float(np.mean(np.cos(angles)))
        R = math.sqrt(sin_mean ** 2 + cos_mean ** 2)
        h_mean_deg = math.degrees(math.atan2(sin_mean, cos_mean)) % 360
        h_std_deg = math.degrees(math.sqrt(-2.0 * math.log(max(R, 1e-9)))) if R < 1.0 else 0.0

        h_center = round(h_mean_deg)
        h_tol = max(_MIN_H_TOL, math.ceil(h_std_deg * 1.5))

        # Regular mean/std for S and V, convert to user space (0-100)
        s_center = round(float(np.mean(s)) * 100 / 255)
        s_tol = max(_MIN_SV_TOL, math.ceil(float(np.std(s)) * 100 / 255 * 1.5))
        v_center = round(float(np.mean(v)) * 100 / 255)
        v_tol = max(_MIN_SV_TOL, math.ceil(float(np.std(v)) * 100 / 255 * 1.5))

        return h_center, s_center, v_center, h_tol, s_tol, v_tol
    ```
  - Notes: `R < 1e-9` guard prevents log(0) when all pixels are identical hue. `% 360` on atan2 result ensures H is always positive.

- [x] Task 3: Use computed HSV in `_on_draw_release` and auto-select in HSV editor
  - File: `tools/minimap_zone_selector/app.py`
  - Action: In `_on_draw_release`, replace the hardcoded Zone construction with computed values, then call `self._hsv_editor.load_zone(zone)` after appending.

    **Before** (lines ~330–341):
    ```python
    zone = Zone(
        zone_id=zone_id,
        x=ref_x, y=ref_y, width=ref_w, height=ref_h,
        h_center=0, h_tol=180,
        s_center=0, s_tol=12,
        v_center=100, v_tol=15,
        min_ratio=0.3,
        weight=0.0,
        weight_override=False,
    )
    zones.append(zone)
    ```

    **After**:
    ```python
    frames = self._loader.get_frames(self._selected_map)
    bgr_frame = frames[self._current_frame_index]
    h_c, s_c, v_c, h_t, s_t, v_t = self._compute_zone_hsv(bgr_frame, ref_x, ref_y, ref_w, ref_h)

    zone = Zone(
        zone_id=zone_id,
        x=ref_x, y=ref_y, width=ref_w, height=ref_h,
        h_center=h_c, h_tol=h_t,
        s_center=s_c, s_tol=s_t,
        v_center=v_c, v_tol=v_t,
        min_ratio=0.3,
        weight=0.0,
        weight_override=False,
    )
    zones.append(zone)
    self._hsv_editor.load_zone(zone)
    ```
  - Notes: `get_frames()` returns the already-loaded BGR list — no I/O. Frame index is guaranteed valid at this point (`frame_count > 0` is checked earlier in `_on_draw_release`).

### Acceptance Criteria

- [x] AC 1: Given a map with at least one frame loaded, when the user draws a zone rectangle on the canvas, then the zone's `h_center`, `s_center`, `v_center`, `h_tol`, `s_tol`, `v_tol` are populated from the actual pixel values in that region (not the old hardcoded defaults).
- [x] AC 2: Given a zone drawn over a red-toned area (hue near 0°/360°), when HSV is computed, then `h_center` correctly reflects the actual hue (e.g. ~355° or ~5°, not a midpoint artifact like 180°).
- [x] AC 3: Given a drawn zone, when the zone is created, then the HSV editor panel is automatically populated with the zone's computed values without requiring the user to manually click the zone in the stats panel.
- [x] AC 4: Given a drawn zone over a uniform-color area (low std dev), when tolerances are computed, then `h_tol >= 10`, `s_tol >= 5`, `v_tol >= 5` (minimum floor enforced).
- [x] AC 5: Given a single-pixel region or all-identical-hue region (R approaches 1.0), when computing circular hue std dev, then no math domain error (log of zero) occurs.

## Review Notes

- Adversarial review completed
- Findings: 11 total, 1 fixed, 10 skipped (9 noise/false-positive, 1 accepted per spec)
- Resolution approach: auto-fix
- F2 fixed: added empty-region guard in `_compute_zone_hsv` to return safe defaults if numpy slice yields zero pixels

## Additional Context

### Dependencies

- `cv2`, `numpy`, `math` — all available; cv2 and numpy already used elsewhere in the project, math is stdlib.
- No new package installations required.

### Testing Strategy

No automated tests exist in this project. Manual testing steps:
1. Launch the minimap zone selector with a map that has labeled frames loaded.
2. Navigate to a frame showing a distinctive-colored area (e.g. water, rock, grass).
3. Draw a zone rectangle over that area.
4. Verify the HSV editor auto-populates with values that visually match the region's color.
5. Draw a zone over a red-toned area on any map and verify `h_center` is near 0 or 360, not 180.
6. Draw a single-pixel-wide zone and verify no crash.

### Notes

- **Known limitation:** min_ratio is still hardcoded to 0.3 on draw. This is out of scope and was already the default before this change.
- **Future consideration:** Could sample across all frames for a map to get more robust HSV stats, but single-frame is sufficient for the intended use case (static map terrain).
- **Hue tolerance cap:** h_tol has no upper bound cap — for very heterogeneous hue regions it could approach 180. This is intentional; it signals to the user that the zone color is ambiguous.
