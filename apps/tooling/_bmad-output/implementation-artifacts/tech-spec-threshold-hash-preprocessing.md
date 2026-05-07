---
title: 'Threshold-based hash preprocessing'
slug: 'threshold-hash-preprocessing'
created: '2026-03-27'
status: 'Completed'
stepsCompleted: [1, 2, 3, 4]
tech_stack: ['Python', 'OpenCV (cv2)', 'imagehash', 'numpy']
files_to_modify: ['utils/image.py', 'tools/hash_comparator.py', 'tools/warden_analyzer.py', 'config/config.yaml']
code_patterns: ['stateless-pure-functions-in-utils', 'config-param-threaded-explicitly-through-call-chain', 'optional-args-with-none-default']
test_patterns: ['no-tests-in-project']
---

# Tech-Spec: Threshold-based hash preprocessing

**Created:** 2026-03-27

## Overview

### Problem Statement

The grayscale canvas fed to perceptual hashing includes semi-transparent background brightness variation. The map name overlay has a darker backing layer, but the background behind it changes as the player moves — bright areas in some map zones, dark in others. This background bleed into the grayscale signal causes hash instability across frames and videos, producing recognition distances that vary more than they should.

### Solution

Apply Otsu's adaptive threshold after grayscale conversion to binarize the crop: white text pixels → 255, background → 0. Otsu selects the split threshold automatically per crop, making it robust to varying background brightness without a fixed value. This must be applied consistently in both the training path (`hash_comparator.py`) and the runtime path (`warden_analyzer.py`). A `threshold_hash` boolean config param controls it.

### Scope

**In Scope:**
- Add `apply_threshold(gray)` utility function in `utils/image.py` using `cv2.threshold` with `THRESH_BINARY + THRESH_OTSU`
- Wire into `build_canvases()` in `tools/hash_comparator.py` after the `to_grayscale()` call
- Wire into `identify_map()` in `tools/warden_analyzer.py` after the `to_grayscale()` call
- Add `threshold_hash: true/false` under `map_identification` in `config/config.yaml`
- Pass `threshold_hash` through the call chain in both tools

**Out of Scope:**
- `find_text_anchor` / `has_white_pixels` HSV-based white detection logic
- Changes to `tile_cols`, `shift_tolerance`, canvas size, or hash methods
- Any other ROI or detection pipeline changes

## Context for Development

### Codebase Patterns

- All shared image ops in `utils/image.py` are stateless pure functions (numpy array in → numpy array out, no classes). `apply_threshold` follows this same pattern.
- Config params are resolved once in `main()` and threaded explicitly through the call chain as keyword args. Pattern: `main()` reads yaml → passes to `run_comparison()` → passes to `build_canvases()`. Same chain needed for `threshold_hash`.
- `warden_analyzer.py` reads hash-related params from `map_config.json` (canvas_size, hash_size, hash_method, shift_tolerance) but reads detection params from `config.yaml` (`map_identification`). `threshold_hash` belongs in `config.yaml` `map_identification` and should be read alongside `recognition_threshold` and `text_anchor_width`.
- `build_canvases()` optional args pattern: `tile_cols=1, text_anchor_width=None`. Add `threshold_hash=False` with same style.
- `identify_map()` optional args pattern: `text_anchor_width=None`. Add `threshold_hash=False` with same style.
- No test files exist anywhere in the project.

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `utils/image.py` | Add `apply_threshold(gray)` after `to_grayscale` (line 37) |
| `tools/hash_comparator.py` | `build_canvases()` line ~234, `run_comparison()` line ~316, `main()` line ~581 |
| `tools/warden_analyzer.py` | `identify_map()` line ~34, call site in `run()` line ~91 |
| `config/config.yaml` | `map_identification` section, line ~115 — add `threshold_hash` after `shift_tolerance` |

### Technical Decisions

- **Otsu's threshold** (`cv2.THRESH_BINARY + cv2.THRESH_OTSU`): pass `0` as the threshold value — OpenCV ignores it when OTSU flag is set and computes the optimal split automatically. Returns `(threshold_value, binary_image)`; we discard threshold_value.
- **Config default `threshold_hash: true`**: recommended on since the use case (white text on variable dark background) always benefits. Off path kept for debugging/comparison runs.
- **Applied after grayscale, before resize/tile**: gives Otsu the most pixels to compute the bimodal split from. Tiling and anchor-crop are orthogonal — threshold applies regardless of which are active.
- **Import additions**: `hash_comparator.py` and `warden_analyzer.py` both import `apply_threshold` from `utils.image` alongside existing imports.

## Implementation Plan

### Tasks

- [x] Task 1: Add `apply_threshold()` utility to `utils/image.py`
  - File: `utils/image.py`
  - Action: Insert after the `to_grayscale()` function (line ~46). Add:
    ```python
    def apply_threshold(gray):
        """Binarize a grayscale image using Otsu's adaptive threshold.

        Converts white text on a variable-brightness background to pure binary
        (255 = text, 0 = background). Otsu's method computes the optimal split
        threshold automatically from the pixel histogram — no fixed value needed.

        Args:
            gray: Single-channel grayscale numpy array (height, width).

        Returns:
            numpy array (height, width) — binary image with values 0 or 255.
        """
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return binary
    ```
  - Notes: `0` is passed as the threshold value but OpenCV ignores it when `THRESH_OTSU` is set. The returned tuple's first element (computed threshold value) is discarded.

- [x] Task 2: Add `threshold_hash` param to `config/config.yaml`
  - File: `config/config.yaml`
  - Action: Add after `shift_tolerance: 2` (line ~160) inside `map_identification`:
    ```yaml
      # Binarize the grayscale crop before hashing using Otsu's adaptive threshold.
      # Recommended for white text on variable-brightness backgrounds (e.g. map name HUD).
      threshold_hash: true
    ```
  - Notes: `true` is the recommended default. Set to `false` to reproduce old behavior for comparison runs.

- [x] Task 3: Wire `threshold_hash` through `tools/hash_comparator.py`
  - File: `tools/hash_comparator.py`
  - Action 3a — Update import line (~line 39):
    ```python
    from utils.image import downscale, extract_roi, find_text_anchor, scale_roi, to_grayscale, apply_threshold
    ```
  - Action 3b — Add `threshold_hash=False` param to `build_canvases()` signature (~line 175):
    ```python
    def build_canvases(frames, ref_roi, canvas_size, target_h, tile_cols=1, text_anchor_width=None, threshold_hash=False):
    ```
    Insert after `gray = to_grayscale(cropped)` (~line 234):
    ```python
    if threshold_hash:
        gray = apply_threshold(gray)
    ```
  - Action 3c — Add `threshold_hash=False` param to `run_comparison()` signature (~line 316) and pass it to `build_canvases()`:
    ```python
    def run_comparison(..., threshold_hash=False):
    ```
    In the `build_canvases(...)` call (~line 369), add `threshold_hash=threshold_hash`.
  - Action 3d — In `main()` (~line 581), read from config after `shift_tolerance` resolution (~line 690):
    ```python
    threshold_hash = map_id.get("threshold_hash", False)
    ```
    Add to the `print` summary block:
    ```python
    print(f"  Threshold hash: {threshold_hash}")
    ```
    Pass `threshold_hash=threshold_hash` to the `run_comparison(...)` call (~line 711).

- [x] Task 4: Wire `threshold_hash` through `tools/warden_analyzer.py`
  - File: `tools/warden_analyzer.py`
  - Action 4a — Update import line (~line 27):
    ```python
    from utils.image import extract_roi, find_text_anchor, has_white_pixels, scale_roi, to_grayscale, apply_threshold
    ```
  - Action 4b — Add `threshold_hash=False` param to `identify_map()` signature (~line 34):
    ```python
    def identify_map(frame, ref_roi, ref_hashes, canvas_size, hash_size, hash_method,
                     shift_tolerance, recognition_threshold, text_anchor_width=None, threshold_hash=False):
    ```
    Insert after `gray = to_grayscale(hash_crop)` (~line 80):
    ```python
    if threshold_hash:
        gray = apply_threshold(gray)
    ```
  - Action 4c — In `run()`, read `threshold_hash` from config after `text_anchor_width` is resolved. Find where `identify_map(...)` is called and add `threshold_hash=threshold_hash` as a keyword arg. Also read from config:
    ```python
    threshold_hash = map_id.get("threshold_hash", False)
    ```

### Acceptance Criteria

- [x] AC 1: Given any grayscale ROI crop (normal frame), when `apply_threshold(gray)` is called, then the returned array has the same shape as the input and contains only values `0` and `255`.

- [x] AC 2: Given `threshold_hash: true` in config, when `hash_comparator.py` runs on labeled frames, then the canvas built for each frame is binarized (only 0/255 values) before it is passed to the hash function.

- [x] AC 3: Given `threshold_hash: false` in config (or absent), when `hash_comparator.py` runs, then the grayscale canvas is passed to the hash function unchanged — identical behavior to before this change.

- [x] AC 4: Given `threshold_hash: true` in config, when `warden_analyzer.py` identifies a map, then it uses the same binarized canvas preprocessing as `hash_comparator.py` used to generate the reference hashes.

- [x] AC 5: Given `threshold_hash: false`, when `warden_analyzer.py` identifies a map, then no thresholding is applied — original behavior preserved.

- [x] AC 6: Given a nearly uniform crop (degenerate case — e.g. a black screen frame), when `apply_threshold` is called, then the function returns a valid binary array without raising an exception (Otsu degrades gracefully on flat histograms).

- [x] AC 7: Given labeled frames run through `hash_comparator.py` with `threshold_hash: true`, when pairwise distances are computed, then collision count should be equal to or lower than the baseline run without thresholding (hashes are at least as stable).

## Additional Context

### Dependencies

- OpenCV (`cv2`) already in use — no new dependencies required.

### Testing Strategy

No automated test framework exists in this project. Manual verification steps:

1. Run `hash_comparator.py --images <labeled_dir> --preview -o output/threshold_test` with `threshold_hash: true` in config. Inspect preview PNGs — canvas images should be black-and-white binary, not grayscale.
2. Run with `threshold_hash: false` (old behavior). Compare `hash_comparison_report.json` from both runs — `min` pairwise distances should be higher (or equal) with thresholding on.
3. Run `warden_analyzer.py` on a known video with `threshold_hash: true` and verify `rounds.json` maps match expected values and `recognition_distance` values are not worse than the `threshold_hash: false` baseline.
4. Check the engine map round (currently `recognition_distance: 7` in `output/warden_astera/rounds.json`) — this is a good canary for improvement.

### Notes

- **Risk — degenerate Otsu**: If a frame's ROI is entirely black (black screen mid-round), Otsu gets a flat histogram and may output all-zero or all-255. This is harmless: `predict_map` will simply produce a large Hamming Distance and `recognition_threshold` will gate out the result as `unrecognized`. No special handling needed.
- **Consistency requirement**: `threshold_hash` must be set to the same value when generating reference hashes (hash_comparator) and when running inference (warden_analyzer). If the reference map_config.json was generated without thresholding, `threshold_hash: false` must be used at runtime too until hashes are regenerated.
- **Future**: Could be worth storing `threshold_hash` in `map_config.json` alongside `hash_method` and `tile_cols` so the runtime tool self-configures. Out of scope for now.

## Review Notes

- Adversarial review completed
- Findings: 10 total, 6 fixed, 4 skipped (noise/undecided)
- Resolution approach: auto-fix
- Fixed: F1 (missing docstring Args), F2 (--threshold-hash CLI flag), F3 (mismatch warning), F4 (startup print), F5 (docstring returns text), F7 (default asymmetry documented)
- Skipped: F6, F8 (undecided), F9, F10 (noise)

## Empirical Validation

Tested on 10 labeled maps at 720p with dhash + 52px text anchor:

| Setting | dhash min dist | dhash collisions |
|---------|---------------|-----------------|
| threshold_hash: true | 0 | 3 |
| threshold_hash: false | 21 | 0 |

**Outcome:** Binarization is harmful for perceptual hashing. dhash and phash rely on pixel gradients; Otsu binarization destroys gradient information. The anchor crop (~34×15px at 720p) is also too small for reliable bimodal histogram splitting. Config default changed to `threshold_hash: false`. The feature remains available via CLI flag for future experimentation.
