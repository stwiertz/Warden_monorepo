---
title: 'Consensus Reference Hash Generation'
slug: 'consensus-reference-hash'
created: '2026-03-27'
status: 'ready-for-dev'
stepsCompleted: [1, 2, 3, 4]
tech_stack: ['Python 3', 'numpy', 'imagehash', 'opencv-python', 'Pillow']
files_to_modify: ['tools/hash_comparator.py', 'tools/map_config_generator.py']
code_patterns: ['Google-style docstrings', 'ImageHash | None return type', 'stdout progress / stderr warnings', 'cross-module import via sys.path.insert']
test_patterns: ['no test suite exists']
---

# Tech-Spec: Consensus Reference Hash Generation

**Created:** 2026-03-27

## Overview

### Problem Statement

`map_config_generator.py` uses only the first frame per map subdirectory to generate the reference hash. The existing `representative_hash()` in `hash_comparator.py` uses mode (most common full hash string) across samples, but does not account for sub-pixel text anchor shift. Even after cropping from the first white column, that column can vary 1-2px frame-to-frame. A consistent 1-bit horizontal shift produces a completely different hash string, so the common ground between samples is never found — the mode approach degrades to essentially picking one arbitrary sample.

### Solution

Replace single-frame + mode logic with a shift-aligned bitwise majority vote:
1. Load all labeled frames for each map (full subdirectory, not just the first file)
2. Compute a hash per sample
3. For each sample, try ±shift_tolerance bit-shifts to align it against a reference (first sample)
4. After alignment, take a per-bit majority vote across all samples
5. Store the resulting consensus fingerprint as a single hex string in `map_config.json` (unchanged format)

### Scope

**In Scope:**
- New `consensus_hash(canvases, hash_size, method, shift_tolerance)` function in `hash_comparator.py`, replacing `representative_hash()`
- Update `map_config_generator.py` to load all frames per map subdirectory (not just the first) when `--images` points to a labeled-style directory with multiple frames
- Output format unchanged: single hex string per map in `map_config.json`

**Out of Scope:**
- Multi-method hash combination (ahash + dhash + phash ensemble)
- Multi-ROI fingerprint
- Changes to `hash_validator.py` matching/prediction logic

## Context for Development

### Codebase Patterns

- Functions return `imagehash.ImageHash | None`; callers check for `None` before using the result
- Google-style docstrings on all public functions
- Progress output via `print()` to stdout; warnings via `print(..., file=sys.stderr)`
- Cross-module imports use `sys.path.insert(0, ...)` at module top — `hash_validator.py` already imports from `hash_comparator.py` (line 27), establishing the pattern for `map_config_generator.py` to do the same
- `imagehash.ImageHash` objects wrap a `bool` numpy array in `.hash` attribute (shape `(hash_size, hash_size)`)
- `np.roll(bits, shift, axis=1)` already used in `hamming_shift_tolerant()` for per-row horizontal bit-shift — same mechanic used for alignment in consensus
- `config["map_identification"]["shift_tolerance"]` (value: `2`) is already read by `hash_comparator.py` and will be the alignment window for consensus

### Files to Reference

| File | Purpose |
| ---- | ------- |
| tools/hash_comparator.py | Contains `representative_hash()` to replace, `compute_hash()`, `build_canvases()`, `hamming_shift_tolerant()` (shift mechanic to reuse), and `run_comparison()` call site |
| tools/map_config_generator.py | Contains `load_maps_from_images()` (loads first file only — must load all), `process_frame()` (single-frame canvas+hash), and `run()` processing loop |
| tools/hash_validator.py | Reference only — shows established `from hash_comparator import ...` pattern |
| config/config.yaml | `map_identification.shift_tolerance: 2` (alignment window); `map_identification.text_anchor_width: 52` |

### Technical Decisions

- **`consensus_from_hashes(hashes, shift_tolerance)`** — core algorithm extracted as a standalone helper in `hash_comparator.py` that accepts a list of `ImageHash` objects. This allows both `hash_comparator.py` (which builds canvases then hashes them) and `map_config_generator.py` (which uses `process_frame()` to hash directly) to share the same consensus logic without duplicating it.
- **`consensus_hash(canvases, hash_size, method, shift_tolerance)`** — replaces `representative_hash()` in `hash_comparator.py`; wraps `compute_hash()` per canvas then delegates to `consensus_from_hashes()`.
- **Alignment target**: first sample in the list is the reference. Each subsequent hash is shift-aligned to the reference before voting. This is consistent with how `hamming_shift_tolerant()` works (one hash is fixed, the other is rolled).
- **Majority vote**: `np.sum(stacked_bits, axis=0) > n/2` where `n` = number of aligned samples. Ties (even n, exactly half) round to `False` — acceptable given that ties indicate a genuinely unstable bit, which should default to the more common value (0).
- **`map_config_generator.py` frame loading**: `load_maps_from_images()` changes return type from `{map_name: frame}` to `{map_name: [(fname, frame), ...]}`. `load_maps_from_videos()` also updated to same format (single-entry list per map) so `run()` has a uniform interface.
- **Output format unchanged**: `map_config.json` still stores a single hex string per map — consensus produces one `ImageHash` just like before.

## Implementation Plan

### Tasks

Tasks are ordered dependency-first. Tasks 1–3 are in `hash_comparator.py`; Tasks 4–6 are in `map_config_generator.py` and depend on Task 1 being done first.

- [ ] Task 1: Add `consensus_from_hashes()` to `hash_comparator.py`
  - File: `tools/hash_comparator.py`
  - Action: Insert the new function immediately after `representative_hash()` (after line 96), before the `# Frame loading and canvas building` section comment. Do not remove `representative_hash()` yet — that happens in Task 2.
  - Implementation:
    ```python
    def consensus_from_hashes(hashes, shift_tolerance=0):
        """Compute a shift-aligned bitwise majority-vote hash from a list of ImageHash objects.

        Each hash after the first is shift-aligned to the first hash (the reference) by trying
        all horizontal bit-shifts in [-shift_tolerance, +shift_tolerance] and selecting the
        shift that minimises Hamming Distance to the reference. The aligned bit arrays are then
        majority-voted per bit position.

        Args:
            hashes: List of imagehash.ImageHash objects (all must have the same hash_size).
            shift_tolerance: Max horizontal bit-shift to try in either direction. 0 = no alignment.

        Returns:
            imagehash.ImageHash: Consensus hash, or None if hashes is empty.
        """
        if not hashes:
            return None
        if len(hashes) == 1:
            return hashes[0]

        ref_bits = hashes[0].hash  # shape: (hash_size, hash_size), dtype bool
        aligned = [ref_bits]

        for h in hashes[1:]:
            bits = h.hash
            best_shift = 0
            best_dist = int(np.sum(ref_bits != bits))
            for s in range(-shift_tolerance, shift_tolerance + 1):
                if s == 0:
                    continue
                d = int(np.sum(ref_bits != np.roll(bits, s, axis=1)))
                if d < best_dist:
                    best_dist = d
                    best_shift = s
            aligned.append(np.roll(bits, best_shift, axis=1))

        stacked = np.stack(aligned, axis=0)  # shape: (n, hash_size, hash_size)
        vote = np.sum(stacked, axis=0) > (len(aligned) / 2)
        return imagehash.ImageHash(vote)
    ```
  - Notes: `np.roll(bits, shift, axis=1)` rolls each row independently — same mechanic as `hamming_shift_tolerant()`. `imagehash.ImageHash(vote)` constructs a hash from a bool array directly.

- [ ] Task 2: Replace `representative_hash()` with `consensus_hash()` in `hash_comparator.py`
  - File: `tools/hash_comparator.py`
  - Action: Replace the entire `representative_hash()` function body (lines 73–96) with `consensus_hash()`. Keep the same location in the file.
  - Implementation:
    ```python
    def consensus_hash(canvases, hash_size, method, shift_tolerance=0):
        """Compute a consensus hash from multiple canvases using shift-aligned majority vote.

        Replaces representative_hash(). Computes a perceptual hash per canvas, then calls
        consensus_from_hashes() to produce a single stable fingerprint that is robust to
        sub-pixel text anchor shift between samples.

        Args:
            canvases: List of (filename, grayscale canvas numpy array) tuples.
            hash_size: Hash dimension (8 = 64-bit hash).
            method: Hash method string ('ahash', 'dhash', 'phash').
            shift_tolerance: Max horizontal bit-shift for alignment. 0 = no alignment.

        Returns:
            imagehash.ImageHash: The consensus hash, or None if no canvases.
        """
        if not canvases:
            return None
        hashes = [compute_hash(canvas, hash_size, method) for _, canvas in canvases]
        return consensus_from_hashes(hashes, shift_tolerance)
    ```
  - Notes: `consensus_from_hashes` must exist before this function is called (Task 1). The `collections` import is still used elsewhere in the file (`run_comparison` stats) — do not remove it.

- [ ] Task 3: Update `run_comparison()` call site in `hash_comparator.py`
  - File: `tools/hash_comparator.py`
  - Action: In `run_comparison()`, replace the call to `representative_hash()` with `consensus_hash()`, passing `shift_tolerance`.
  - Change (line ~407):
    ```python
    # Before:
    rep = representative_hash(canvases, hash_size, method)

    # After:
    rep = consensus_hash(canvases, hash_size, method, shift_tolerance)
    ```
  - Notes: `shift_tolerance` is already a parameter of `run_comparison()` — it is in scope at this call site. Also update the `print` on the following line to show sample count, since it already does: `print(f"    {map_name}: {str(rep)}  ({len(canvases)} frame(s))")` — no change needed there.

- [ ] Task 4: Update `load_maps_from_images()` in `map_config_generator.py` to load all frames
  - File: `tools/map_config_generator.py`
  - Action: Change `load_maps_from_images()` to load ALL image files per map subdirectory (not just the first). Change the return type from `{map_name: frame}` to `{map_name: [(fname, frame), ...]}`.
  - Implementation (replace full function body):
    ```python
    def load_maps_from_images(images_dir):
        """Load all reference frames per map from subdirectories.

        Expects: images_dir/map_name_1/image1.png, image2.png, ...
        Loads all image files (sorted alphabetically) in each subdirectory.

        Args:
            images_dir: Path to directory containing map-named subdirectories.

        Returns:
            dict: {map_name: [(filename, BGR numpy array), ...]} for each map found.

        Raises:
            ValueError: If no map subdirectories with images are found.
        """
        image_extensions = {".png", ".jpg", ".jpeg", ".bmp"}
        maps = {}

        for entry in sorted(os.listdir(images_dir)):
            subdir = os.path.join(images_dir, entry)
            if not os.path.isdir(subdir):
                continue

            image_files = sorted(
                f for f in os.listdir(subdir)
                if os.path.splitext(f)[1].lower() in image_extensions
            )
            if not image_files:
                print(f"Warning: No image files in {subdir}, skipping", file=sys.stderr)
                continue

            frames = []
            for fname in image_files:
                image_path = os.path.join(subdir, fname)
                frame = cv2.imread(image_path)
                if frame is None:
                    print(f"Warning: Could not read {image_path}, skipping", file=sys.stderr)
                    continue
                frames.append((fname, frame))

            if frames:
                maps[entry] = frames
                print(f"  Loaded: {entry} <- {len(frames)} frame(s)")

        if not maps:
            raise ValueError(
                f"No map subdirectories with valid images found in '{images_dir}'"
            )

        return maps
    ```

- [ ] Task 5: Update `load_maps_from_videos()` in `map_config_generator.py` to return uniform format
  - File: `tools/map_config_generator.py`
  - Action: Change the return type from `{map_name: frame}` to `{map_name: [(fname, frame)]}` (single-entry list) so `run()` has a uniform interface for both loaders.
  - Change: replace `maps[map_name] = frame` with `maps[map_name] = [(os.path.basename(video_path), frame)]` in both branches (the `ts is not None` branch and the I-frame extraction branch). Also update the print lines to reflect the new format (no functional impact).
  - There are two assignment sites:
    1. Line ~163: `maps[map_name] = frame` → `maps[map_name] = [(os.path.basename(video_path), frame)]`
    2. Line ~169: `maps[map_name] = frame` → `maps[map_name] = [(os.path.basename(video_path), frame)]`

- [ ] Task 6: Update `run()` in `map_config_generator.py` to use consensus
  - File: `tools/map_config_generator.py`
  - Action: Three sub-changes in `run()`:

  **6a. Add import at module top** (after the existing `sys.path.insert` block, alongside other tool imports — but since `hash_comparator.py` is in the same `tools/` directory, this import needs the path already set):
  ```python
  from hash_comparator import consensus_from_hashes
  ```
  Place this alongside the other `from utils.*` imports at the top of the file.

  **6b. Add `shift_tolerance` to config resolution** in `run()`, immediately after the `threshold_hash` line:
  ```python
  shift_tolerance = map_id_config.get("shift_tolerance", 0)
  ```

  **6c. Fix resolution validation** — the block starting at `first_name = next(iter(map_frames))` currently does `first_frame = map_frames[first_name]` and calls `.shape` on it directly. With the new format, change to:
  ```python
  first_name = next(iter(map_frames))
  first_frame = map_frames[first_name][0][1]  # first (fname, frame) tuple, frame element
  frame_h, frame_w = first_frame.shape[:2]

  for map_name, frames in map_frames.items():
      fh, fw = frames[0][1].shape[:2]  # check first frame of each map
      ...
  ```

  **6d. Replace the per-map processing loop** (the loop currently at `for map_name, frame in map_frames.items(): h = process_frame(...)`):
  ```python
  for map_name, frames in map_frames.items():
      hashes = []
      for fname, frame in frames:
          h = process_frame(frame, scaled_roi, canvas_size, hash_size, hash_method, scaled_anchor_w)
          if h is not None:
              hashes.append(h)
      if not hashes:
          print(f"  Warning: No valid hashes for '{map_name}', skipping", file=sys.stderr)
          continue
      h = consensus_from_hashes(hashes, shift_tolerance)
      hash_dict[map_name] = h
      print(f"  Hashed: {map_name} -> {str(h)}  ({len(hashes)} sample(s))")
  ```
  - Notes: `process_frame()` itself is unchanged — it still returns `ImageHash | None` for a single frame. The preview block (`if preview:`) that follows can be removed or kept as a no-op (it currently only prints a message, never writes anything).

### Acceptance Criteria

- [ ] AC 1: Given `consensus_from_hashes([single_hash], shift_tolerance=2)`, when called, then the returned hash is equal to `single_hash` (no distortion from consensus on a single sample).

- [ ] AC 2: Given an empty list `[]`, when `consensus_from_hashes([], shift_tolerance=2)` is called, then `None` is returned.

- [ ] AC 3: Given a list of N identical `ImageHash` objects, when `consensus_from_hashes()` is called with any `shift_tolerance`, then the returned hash equals the input hash (majority vote of identical bits is identical).

- [ ] AC 4: Given `shift_tolerance=0`, when `consensus_from_hashes()` is called with multiple hashes, then no shift alignment is attempted and the result is the plain bitwise majority vote of the input bit arrays.

- [ ] AC 5: Given a labeled directory with multiple frames per map, when `python tools/hash_comparator.py --images labeled/` is run, then `map_config.json` is written with one hex string per map (same schema as before), and the console shows `(N frame(s))` reflecting the actual sample count.

- [ ] AC 6: Given a labeled directory where each map subdirectory has N > 1 images, when `python tools/map_config_generator.py --images labeled/` is run, then the output shows `(N sample(s))` in the progress for each map and `map_config.json` is written with one hex string per map.

- [ ] AC 7: Given a map subdirectory with exactly 1 image, when `python tools/map_config_generator.py --images labeled/` is run, then that map's hash equals the direct `process_frame()` hash of that single frame (consensus of 1 is a passthrough per AC 1).

- [ ] AC 8: Given a labeled directory, when `python tools/map_config_generator.py --images labeled/` is run with `shift_tolerance: 2` in `config.yaml`, then `consensus_from_hashes()` is called with `shift_tolerance=2` (verifiable by temporarily printing the value or tracing the call).

## Additional Context

### Dependencies

- `numpy` — already a project dependency; used for `np.roll`, `np.stack`, `np.sum`
- `imagehash` — already a project dependency; `imagehash.ImageHash(bool_array)` constructor is the standard way to build a hash from raw bits
- No new packages required

### Testing Strategy

No automated test suite exists in the project. Manual validation steps:

1. **Regression check**: Run `python tools/hash_comparator.py --images labeled/` before and after the change. Compare `map_config.json` output — hashes may differ (that is expected and desired), but the file schema must be identical and all maps must be present.
2. **Accuracy check**: Run `python tools/hash_validator.py` after generating the new `map_config.json`. Compare `accuracy_report.json` to the baseline (81.25%). The new consensus hash should maintain or improve accuracy.
3. **Single-frame parity**: Copy one map's labeled dir to a temp dir with only 1 image, run `map_config_generator.py`, confirm the output hash matches `process_frame()` output for that image directly.
4. **Shift alignment smoke test**: Given two hashes that differ by a known 1-bit horizontal shift, call `consensus_from_hashes([h1, h2], shift_tolerance=2)` in a Python REPL and verify the result matches the unshifted hash.

### Notes

- **Risk — reference frame choice**: The first sample is used as the alignment reference. If the first sample is an outlier (e.g., a frame with an unusually shifted anchor), all other samples are aligned to it, potentially skewing the consensus. Mitigation: order labeled frames consistently (e.g., alphabetically by filename, which is the current sort order).
- **Risk — `imagehash.ImageHash(bool_array)` constructor**: The `imagehash` library constructs a hash from a bool numpy array using `ImageHash(hash_=array)` in some versions but `ImageHash(array)` in others. Verify the constructor works with the installed version before finalising — the existing `hamming_shift_tolerant()` already reads `.hash` attribute successfully, so the version in use supports this interface.
- **Future**: If shift variance is larger than `shift_tolerance` allows (e.g., due to widescreen crops or different UI scaling), the consensus will still improve over mode but won't fully eliminate the shift noise. In that case, pre-normalising the anchor crop width more aggressively (rather than relying on the first white pixel) would be the next step.
