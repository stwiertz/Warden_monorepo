---
title: 'Map Config Generator'
slug: 'map-config-generator'
created: '2026-03-03'
status: 'completed'
stepsCompleted: [1, 2, 3, 4]
tech_stack: ['python', 'opencv', 'ffmpeg', 'imagehash', 'pillow', 'numpy', 'pyyaml']
files_to_modify: ['tools/map_config_generator.py', 'config/config.yaml', 'requirements.txt']
code_patterns: ['cli-tool-pattern', 'ffmpeg-subprocess', 'roi-at-reference-resolution', 'config-driven', 'stateless-image-utils', 'generator-pattern']
test_patterns: ['manual-regression', 'collision-check-as-validation']
---

# Tech-Spec: Map Config Generator

**Created:** 2026-03-03

## Overview

### Problem Statement

Need a lightweight, portable config file that maps each of the 15 EVA maps to a perceptual hash for real-time map identification — without requiring OpenCV on mobile. The current pipeline (Tool 1: BSD) can extract start-of-round frames showing the map name, but there is no automated way to generate a fingerprint config from those frames.

### Solution

A CLI tool that extracts I-frames from reference videos (or accepts pre-extracted images), crops the map-name ROI, runs them through a standard canvas pipeline (crop → grayscale → 64×64 resize), generates 64-bit perceptual hashes, checks for hash collisions via Hamming Distance, and outputs a `map_config.json`.

### Scope

**In Scope:**
- I-frame extraction reusing existing `utils/video.py` infrastructure
- ROI crop using existing pixel-at-1920x1080 pattern from `config/config.yaml`
- Standard canvas pipeline: crop → grayscale → resize to fixed 64×64
- 64-bit perceptual hash generation (new dependency: `imagehash`)
- Collision check via Hamming Distance (warn if any pair < 12)
- Preview function: write processed 64×64 image to disk for visual verification
- Flexible input: accept video files OR pre-extracted frame images
- Output: `map_config.json` with ROI coordinates + map-name-to-hash dictionary

**Out of Scope:**
- Mobile integration / porting
- Pixel Finder (Tool 3) — separate effort
- Interactive GUI preview (Image Inspector is its own spec)
- Automated map labeling

## Context for Development

### Codebase Patterns

- **CLI tool pattern**: Each tool is a standalone script in `tools/` with `argparse`, adds parent dir to `sys.path` for imports. Uses `sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))` to avoid stdlib shadowing.
- **FFmpeg subprocess**: All video decoding via `utils/video.py` subprocess wrappers, not OpenCV. `extract_iframes_scaled()` yields `(frame, timestamp)` using `-skip_frame nokey` with timestamp parsing from stderr via background thread.
- **ROI at reference resolution**: ROIs defined at 1920×1080 in `config.yaml`, scaled at runtime via `utils/image.py:scale_roi()`. ROI dicts have keys: `name`, `x`, `y`, `width`, `height`.
- **Config-driven**: All tunable parameters live in `config/config.yaml`, zero hardcoded constants.
- **Stateless image functions**: `utils/image.py` functions are pure — `extract_roi()` crops with bounds checking, `to_grayscale()` converts BGR→gray, `downscale()` preserves aspect ratio.
- **Generator pattern**: Video frame extraction yields `(frame, timestamp)` tuples to avoid loading full videos into memory.
- **Output convention**: Tools create output directories with `os.makedirs(output_dir, exist_ok=True)`.

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `utils/video.py` | `extract_iframes_scaled()` — single-pipe I-frame extraction with `-skip_frame nokey`, yields `(BGR_frame, timestamp)`. `get_video_info()` — returns `(width, height)`. |
| `utils/image.py` | `extract_roi(frame, roi)` — crop with bounds checking. `to_grayscale(frame)` — BGR→gray. `scale_roi(roi, scale_factor)` — scale ROI from reference to processing resolution. `downscale()` preserves aspect ratio (NOT suitable for fixed canvas). |
| `utils/config.py` | `load_config(path)` — returns parsed YAML dict via `yaml.safe_load()`. |
| `config/config.yaml` | `reference_resolution` (1920×1080), `processing.target_height` (360), existing `map_name` ROI at `x:827, y:79, w:264, h:22`. |
| `tools/black_screen_detector.py` | Reference for: CLI argparse pattern, `sys.path` setup, config loading, ROI scaling, video info retrieval, output directory creation. |
| `requirements.txt` | Current deps: `opencv-python>=4.8,<5`, `pyyaml>=6.0,<7`, `numpy>=1.24,<2`. |

### Technical Decisions

- **Reuse existing pixel-based ROI pattern** at 1920×1080 reference resolution for consistency with the rest of the codebase. Normalized (0.0–1.0) coordinates can be explored later if needed.
- **`imagehash` library** for perceptual hashing — well-maintained, provides `phash()` out of the box with configurable `hash_size` parameter. Requires `Pillow` for PIL Image conversion. Conversion from OpenCV: `Image.fromarray(gray_frame)` (grayscale numpy array → PIL Image).
- **Flexible input** — the tool should accept either video files (extract I-frames automatically) or a directory of pre-extracted images, since the input workflow is still being determined.
- **64×64 standard canvas** with `cv2.INTER_LINEAR` interpolation for the resize step. Note: `utils/image.py:downscale()` preserves aspect ratio and is NOT suitable here — use `cv2.resize(frame, (64, 64))` directly.
- **No changes to `utils/`** — the standard canvas resize and phash logic are specific to this tool and don't need to be shared utilities.
- **New config section** `map_identification` in `config.yaml` — keeps map hashing parameters separate from `black_detection`.

## Implementation Plan

### Tasks

- [x] Task 1: Add `imagehash` dependency
  - File: `requirements.txt`
  - Action: Append `imagehash>=4.2,<5` (this pulls in `Pillow` and `scipy` transitively)

- [x] Task 2: Add `map_identification` config section
  - File: `config/config.yaml`
  - Action: Add new top-level section after `team_bar_detection`:
    ```yaml
    # Map identification — perceptual hashing for map name recognition
    map_identification:
      # ROI for the map name text (at reference_resolution 1920x1080)
      roi:
        name: map_name_hash
        x: 827
        y: 79
        width: 264
        height: 22

      # Standard canvas: ROI is resized to this fixed square before hashing
      canvas_size: 64

      # Perceptual hash size (hash_size=8 produces a 64-bit hash)
      hash_size: 8

      # Minimum Hamming Distance between any two map hashes.
      # Below this threshold, maps are considered "too similar" and a warning is emitted.
      collision_threshold: 12
    ```
  - Notes: Reuses the same coordinates as the existing `map_name` ROI in `black_detection.roi_zones`. Defined separately so each tool's config is self-contained.

- [x] Task 3: Create `tools/map_config_generator.py` — imports and CLI scaffolding
  - File: `tools/map_config_generator.py` (NEW)
  - Action: Create the file with:
    1. Module docstring explaining purpose and usage examples
    2. `sys.path.insert(0, ...)` pattern from `black_screen_detector.py`
    3. Imports: `argparse`, `os`, `sys`, `json`, `cv2`, `numpy`, `imagehash`, `PIL.Image`, `utils.config.load_config`, `utils.video.extract_iframes_scaled`, `utils.video.get_video_info`, `utils.image.extract_roi`, `utils.image.to_grayscale`, `utils.image.scale_roi`
    4. `main()` with `argparse`:
       - Mutually exclusive input group (required):
         - `--images DIR` — directory with subdirectories per map, each containing reference images
         - `--video MAP_NAME VIDEO_PATH` — repeatable, add one map from a video file (use `nargs=2`, `action='append'`)
       - Optional flags:
         - `-o, --output-dir` — output directory for `map_config.json` and previews (default: from config `output.default_dir`)
         - `-c, --config` — path to config file (default: `config/config.yaml`)
         - `--preview` — write processed 64×64 canvas images to output dir
       - Input validation: check that paths exist before processing
    5. `if __name__ == "__main__": main()` block

- [x] Task 4: Implement `process_frame()` — standard canvas pipeline
  - File: `tools/map_config_generator.py`
  - Action: Add function:
    ```python
    def process_frame(frame, roi, canvas_size):
        """Crop ROI, convert to grayscale, resize to fixed canvas.

        Args:
            frame: BGR numpy array at source resolution.
            roi: ROI dict with name/x/y/width/height keys (at frame's resolution).
            canvas_size: Target square dimension (e.g. 64).

        Returns:
            numpy array: Single-channel grayscale image of shape (canvas_size, canvas_size).
        """
        cropped = extract_roi(frame, roi)
        gray = to_grayscale(cropped)
        canvas = cv2.resize(gray, (canvas_size, canvas_size), interpolation=cv2.INTER_LINEAR)
        return canvas
    ```
  - Notes: ROI must already be scaled to match the frame's resolution before calling this function.

- [x] Task 5: Implement `compute_phash()` — hash generation
  - File: `tools/map_config_generator.py`
  - Action: Add function:
    ```python
    def compute_phash(canvas, hash_size):
        """Generate a perceptual hash from a grayscale canvas.

        Args:
            canvas: Single-channel grayscale numpy array.
            hash_size: Hash dimension (8 = 64-bit hash).

        Returns:
            imagehash.ImageHash: The perceptual hash object.
        """
        pil_image = Image.fromarray(canvas)
        return imagehash.phash(pil_image, hash_size=hash_size)
    ```
  - Notes: Returns `ImageHash` object (supports `str()` for hex, `-` for Hamming Distance).

- [x] Task 6: Implement `load_maps_from_images()` — image directory input
  - File: `tools/map_config_generator.py`
  - Action: Add function:
    ```python
    def load_maps_from_images(images_dir):
        """Load one reference frame per map from subdirectories.

        Expects: images_dir/map_name_1/image.png, images_dir/map_name_2/image.png, ...
        Uses the first image file (sorted alphabetically) in each subdirectory.

        Args:
            images_dir: Path to directory containing map-named subdirectories.

        Returns:
            dict: {map_name: BGR numpy array} for each map found.

        Raises:
            ValueError: If no map subdirectories with images are found.
        """
    ```
    - Scan `images_dir` for subdirectories
    - For each subdirectory, find the first image file (`.png`, `.jpg`, `.jpeg`, `.bmp`)
    - Read with `cv2.imread()` — these are already full-resolution images
    - Return `{subdir_name: frame}` dict
    - Raise `ValueError` if no maps found

- [x] Task 7: Implement `load_maps_from_videos()` — video input
  - File: `tools/map_config_generator.py`
  - Action: Add function:
    ```python
    def load_maps_from_videos(video_entries):
        """Load one reference frame per map from video files.

        Extracts the first I-frame from each video at source resolution.

        Args:
            video_entries: List of [map_name, video_path] pairs.

        Returns:
            dict: {map_name: BGR numpy array} for each map.
        """
    ```
    - For each `(map_name, video_path)`, call `extract_iframes_scaled()` with source height (full resolution) and take the first yielded frame
    - Use `get_video_info()` to get source height for extraction
    - Return `{map_name: frame}` dict

- [x] Task 8: Implement `check_collisions()` — Hamming Distance validation
  - File: `tools/map_config_generator.py`
  - Action: Add function:
    ```python
    def check_collisions(hash_dict, threshold):
        """Check all hash pairs for collisions and print warnings.

        Args:
            hash_dict: {map_name: ImageHash} dictionary.
            threshold: Minimum acceptable Hamming Distance.

        Returns:
            list: List of (map_a, map_b, distance) tuples that are below threshold.
        """
    ```
    - Iterate all unique pairs using `itertools.combinations()`
    - Compute Hamming Distance via `hash_a - hash_b`
    - Print warning to stderr for any pair below threshold
    - Print a summary of all pairwise distances (sorted ascending) for visibility
    - Return list of collision tuples

- [x] Task 9: Implement `run()` — main orchestrator
  - File: `tools/map_config_generator.py`
  - Action: Add function that ties everything together:
    1. Load config, extract `map_identification` section
    2. Get ROI from config, scale it to match source frame resolution:
       - For images: read one image to get its dimensions, compute `scale_factor = image_height / reference_height`
       - For videos: use `get_video_info()` to get source dimensions
    3. Load map frames (via `load_maps_from_images` or `load_maps_from_videos`)
    4. For each map frame: `process_frame()` → `compute_phash()`
    5. If `--preview`: write each canvas to `output_dir/preview_{map_name}.png`
    6. Run `check_collisions()`
    7. Build output dict:
       ```json
       {
         "roi": {"x": 827, "y": 79, "width": 264, "height": 22},
         "canvas_size": 64,
         "hash_size": 8,
         "maps": {
           "frostbite": "a1b2c3d4e5f6a7b8",
           "reactor": "1234567890abcdef"
         }
       }
       ```
    8. Write to `output_dir/map_config.json` with `json.dump(..., indent=2)`
    9. Print summary: number of maps, collisions found, output path

- [x] Task 10: Wire `main()` to `run()` and handle errors
  - File: `tools/map_config_generator.py`
  - Action: In `main()`, after parsing args:
    1. Validate input paths exist
    2. Load config
    3. Resolve output directory (CLI arg > config default)
    4. Create output directory
    5. Call `run()` with appropriate parameters
    6. Wrap in try/except for graceful error reporting to stderr

### Acceptance Criteria

- [x] AC 1: Given a directory with 2+ map subdirectories each containing at least one PNG, when running `python tools/map_config_generator.py --images DIR`, then `map_config.json` is written to the output directory containing ROI coordinates and a hex hash string for each map.

- [x] AC 2: Given a video file and a map name, when running `python tools/map_config_generator.py --video frostbite source/frostbite.mp4`, then the tool extracts the first I-frame, processes it through the standard canvas pipeline, and includes the map's hash in the output JSON.

- [x] AC 3: Given `--video` is specified multiple times (e.g., `--video frostbite vid1.mp4 --video reactor vid2.mp4`), when running the tool, then all specified maps appear in the output JSON.

- [x] AC 4: Given the `--preview` flag is set, when the tool runs, then a `preview_{map_name}.png` file (64×64 grayscale) is written to the output directory for each map processed.

- [x] AC 5: Given two maps whose phash Hamming Distance is below the configured `collision_threshold`, when the tool runs, then a warning is printed to stderr identifying the colliding pair and their distance.

- [x] AC 6: Given all map pairs have Hamming Distance >= `collision_threshold`, when the tool runs, then no collision warnings are printed.

- [x] AC 7: Given `--images DIR` where DIR does not exist or contains no valid subdirectories with images, when running the tool, then it prints an error to stderr and exits with code 1.

- [x] AC 8: Given `--video MAP VIDEO` where VIDEO does not exist, when running the tool, then it prints an error to stderr and exits with code 1.

- [x] AC 9: Given neither `--images` nor `--video` is provided, when running the tool, then argparse shows a usage error.

- [x] AC 10: Given the output `map_config.json`, when parsed by `json.load()`, then it contains keys `roi` (dict with x/y/width/height), `canvas_size` (int), `hash_size` (int), and `maps` (dict of map_name → hex hash string).

## Additional Context

### Dependencies

- **New**: `imagehash>=4.2,<5` — perceptual hashing library. Transitively installs `Pillow` (PIL Image conversion) and `scipy` (DCT computation for phash).
- **Existing**: `opencv-python>=4.8,<5` (image I/O, resize, grayscale), `numpy>=1.24,<2` (array ops), `pyyaml>=6.0,<7` (config loading).

### Testing Strategy

**Manual testing:**
1. Prepare a test directory with 2-3 map subdirectories, each containing a start-of-round screenshot from BSD output.
2. Run `--images DIR --preview` and verify:
   - `map_config.json` is valid JSON with expected structure
   - Preview PNGs show the map name text cropped and scaled correctly
   - Hash strings are 16-character hex (64-bit)
3. Run the same input twice and verify hashes are deterministic (identical output).
4. Artificially create a collision scenario (duplicate an image under two map names) and verify the collision warning fires.

**Built-in validation:**
- The collision check function serves as a self-test — it validates that the ROI and hash parameters produce sufficiently discriminating hashes across all maps.

**Future (out of scope):**
- Automated regression tests comparing generated hashes against a golden fixture file (similar to `tests/fixtures/astera_expected.json` for BSD).

### Notes

- The `map_name` ROI at `x:827, y:79, w:264, h:22` was originally defined for black screen detection. It should work for hash generation since it targets the same UI element, but the crop dimensions may need tuning if the text doesn't fill the region consistently across all 15 maps. The `--preview` flag exists specifically to catch this.
- Hash collision threshold of 12 Hamming Distance provides a safety margin — random 64-bit hashes average ~32 distance. If collisions occur, the user should: (1) adjust the ROI to capture more discriminating text, or (2) increase `canvas_size` for higher resolution hashing.
- The `imagehash` library's `phash()` internally resizes the input to `(hash_size * 4) x (hash_size * 4)` before DCT. With `hash_size=8`, it resizes to 32×32. Our 64×64 canvas provides higher-than-needed resolution, ensuring the resize step in `phash()` downscales (good) rather than upscales (bad).
- For video input mode, the tool extracts I-frames at source resolution (not downscaled to 360p like BSD) because hash quality depends on having crisp text in the ROI. The `extract_iframes_scaled()` function is called with `target_height` set to the video's actual height.

## Review Notes
- Adversarial review completed
- Findings: 14 total, 7 fixed, 7 skipped (noise/undecided)
- Resolution approach: auto-fix
- Fixed: F1 (resolution validation), F2 (aspect ratio check), F3 (empty video error), F6 (check_ffmpeg), F7 (INTER_AREA), F9 (reference_resolution in output), F14 (imwrite check)
- Skipped: F4 (bare except — acceptable for CLI), F5 (duplicate ROI — intentional per spec), F8 (config validation — trust config), F10 (first I-frame — out of scope), F11 (threshold semantics — current behavior correct), F12 (no tests — manual per spec), F13 (sys.path — project pattern)
