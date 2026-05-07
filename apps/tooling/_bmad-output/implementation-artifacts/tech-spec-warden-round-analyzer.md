---
title: 'Warden Round Analyzer (Tool 5)'
slug: 'warden-round-analyzer'
created: '2026-03-27'
status: 'Implementation Complete'
stepsCompleted: [1, 2, 3, 4]
tech_stack: ['python3.8+', 'opencv>=4.8', 'imagehash>=4.2', 'pillow', 'numpy', 'pyyaml', 'questionary']
files_to_modify: ['tools/warden_analyzer.py (new)', 'wardentooling.py', 'config/config.yaml']
code_patterns: ['modular CLI in tools/', 'shared utils in utils/', 'config-driven via YAML', 'ROI at 1920x1080 reference resolution', 'argparse CLI pattern', 'file-based I/O between tools', 'state machine detection loop', 'batch post-detection frame extraction']
test_patterns: ['none established']
---

# Tech-Spec: Warden Round Analyzer (Tool 5)

**Created:** 2026-03-27

## Overview

### Problem Statement

No single tool runs the full pipeline end-to-end (video → score screen + map identification + timers). The mobile Warden app needs this as a validated reference implementation before porting logic to mobile.

### Solution

A new `tools/warden_analyzer.py` that combines `game_detector.py`'s KDA-based round detection loop with inline map identification (using the hashing pipeline from `hash_comparator.py`/`hash_validator.py`), outputting only score screen PNGs and a single `rounds.json` per video.

### Scope

**In Scope:**
- New `tools/warden_analyzer.py` — takes a raw video + `--map-config` (default: `output/map_config.json`), outputs to `-o` (default: `output/warden_<video_stem>/`)
- Only score frames written to disk (start/end frames are NOT exported)
- Map ID done inline on the downscaled start candidate frame (already in memory during detection loop — no extra I/O)
- Unrecognized maps (`best_dist >= recognition_threshold`): `map_name` set to `"unrecognized"`, ROI crop saved to `<output_dir>/unrecognized/<score_stem>_roi.png`
- `rounds.json` written to `<output_dir>/rounds.json` with one entry per detected round
- `recognition_threshold: 10` added to `config/config.yaml` under `map_identification`
- Tool 5 registered in `wardentooling.py` with `flow_tool5()` and wired into main menu + `_TOOL_MAP` + `_reprompt_source`

**Out of Scope:**
- Mobile implementation
- Modifying existing detection algorithm in `game_detector.py`
- Batch processing multiple videos in one run

## Context for Development

### Codebase Patterns

- Modular CLI pipeline: each tool is an independent CLI in `tools/`, using `argparse`
- ROI defined at reference resolution 1920×1080, scaled at runtime via `utils/image.scale_roi()`
- Config-driven: all parameters in `config/config.yaml`, loaded via `utils/config.load_config()`
- Detection state machine (same as `game_detector.py`): `not_in_game` → `in_game`, driven by KDA ROI white detection with start/end confirmation counts
- Post-detection batch extraction: collect `(timestamp, seq)` during the detection loop, then extract full-res frames after — same pattern as `game_detector.py`
- `extract_iframes_scaled()` yields `(downscaled_frame_BGR, timestamp)` — downscaled frame is already in memory at detection time, enabling inline map ID with zero extra I/O
- `predict_map()` in `hash_validator.py` takes `(canvas, ref_hashes, hash_size, method, shift_tolerance)` — import directly
- `build_canvases()` behavior replicated inline for single-frame use: `scale_roi → extract_roi → find_text_anchor → to_grayscale → cv2.resize → compute_hash` (tiling disabled when `text_anchor_width` is set, matching line 237 of `hash_comparator.py`)
- Import pattern: both `sys.path.insert(0, project_root)` and `sys.path.insert(0, tools_dir)` needed — `hash_validator.py` is in `tools/` and itself imports from `hash_comparator.py`
- `wardentooling.py` pattern: `flow_toolN()` returns `(args_list, video_path | None)`, registered in `_TOOL_MAP`, wired into `menu_main()` with confirm prompt + `save_last_run()`, and a `_reprompt_source` handler

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `tools/game_detector.py` | Full detection state machine to replicate (lines 34–297): KDA/notkda ROI setup, start/end confirm logic, skip logic, batch extraction phase |
| `tools/hash_validator.py` | `predict_map()` at line 88 — import directly |
| `tools/hash_comparator.py` | `build_canvases()` at line 175 — replicate inline logic for single-frame; `hamming_shift_tolerant()` at line 251 (used by `predict_map`) |
| `utils/image.py` | `scale_roi()`, `extract_roi()`, `has_white_pixels()`, `find_text_anchor()`, `to_grayscale()`, `downscale()` |
| `utils/video.py` | `extract_iframes_scaled()`, `extract_frame_at_timestamp()`, `get_video_info()` |
| `utils/format.py` | `format_timestamp()` for score frame filenames |
| `utils/config.py` | `load_config()` |
| `config/config.yaml` | All tunable parameters; add `recognition_threshold: 10` under `map_identification` after `shift_tolerance` (line 161) |
| `output/map_config.json` | Reference map hashes structure: `{"roi": {x,y,width,height}, "canvas_size": 64, "hash_size": 8, "hash_method": "dhash", "tile_cols": 3, "maps": {name: hex_hash}}` |
| `wardentooling.py` | TUI launcher — add `flow_tool5()`, register in `_TOOL_MAP` at line 410, extend `choices_main`, add handler block in `menu_main()`, add branch in `_reprompt_source()` |

### Technical Decisions

- **Map ID on start candidate frame, not score frame:** The `map_name_hud` ROI (x=827, y=81, w=267, h=22 @1080p) is only visible during gameplay. At start confirmation time (`start_confirm_count >= start_confirm_frames`), the first-white-frame (`start_candidate_frame`) is saved in memory via `.copy()` — it's guaranteed in-game with HUD visible.
- **Inline map ID — no extra I/O:** Run `scale_roi → extract_roi → find_text_anchor → to_grayscale → cv2.resize → predict_map` directly on the downscaled frame. The `map_name_hud` ROI from `map_config["roi"]` is used (not from `config["map_identification"]["rois"]`), consistent with `hash_validator.py` line 139.
- **`tile_cols` disabled when `text_anchor_width` is set:** Matches `build_canvases()` line 237 — `text_anchor_width` active → plain `cv2.resize` to `canvas_size×canvas_size`.
- **`recognition_threshold: 10`:** If `best_dist >= 10`, map is `"unrecognized"`. Below `collision_threshold: 12` (min distance between any two valid map hashes), providing a safety margin.
- **ROI crop for unrecognized:** Save the full `map_name_hud` ROI crop (before anchor) from the start candidate frame at 720p (≈178×15px). Stored in-memory per round as `roi_crop` (BGR numpy array); written to `<output_dir>/unrecognized/<score_stem>_roi.png` post-extraction when score filename is known.
- **Round state dict:** `{"seq", "start_ts", "end_ts", "score_ts", "map_name", "best_dist", "roi_crop"}`. Accumulated in `pending_rounds` list; `current_round` is the in-progress round (set at start confirmation, completed at end confirmation).
- **`rounds.json` fields:** `round` (1-indexed), `map_name` (string or `"unrecognized"`), `start_timer` (float seconds), `end_timer` (float seconds), `score_timer` (float seconds or `null`), `recognition_distance` (int or `null` if anchor not found). Top-level keys: `video`, `map_config`, `rounds`.
- **Output dir default:** `output/warden_<video_stem>/` where `video_stem = os.path.splitext(os.path.basename(video_path))[0]`.
- **Score filename pattern:** `<ts_str>_score_<seq:03d>.png` — same as `game_detector.py`. `seq` is shared detection counter (incremented only at start confirmation, matching round identity).
- **Unrecognized ROI filename:** `<score_stem>_roi.png` in `<output_dir>/unrecognized/`. `unrecognized/` dir created only when needed (lazy `os.makedirs`).
- **`identify_map()` helper function:** Encapsulates single-frame map identification. Signature: `identify_map(frame, ref_roi, ref_hashes, canvas_size, hash_size, hash_method, shift_tolerance, recognition_threshold, text_anchor_width) → (map_name, best_dist, roi_crop_bgr)`. Returns `("unrecognized", None, None)` on bounds error; `("unrecognized", None, roi_crop)` if anchor not found.

## Implementation Plan

### Tasks

- [x] Task 1: Add `recognition_threshold` to `config/config.yaml`
  - File: `config/config.yaml`
  - Action: Insert `recognition_threshold: 10` after `shift_tolerance: 2` (line 161) under `map_identification`. Add comment: `# Minimum Hamming Distance to accept a map match. Scores >= this are marked 'unrecognized'.`

- [x] Task 2: Create `tools/warden_analyzer.py`
  - File: `tools/warden_analyzer.py` (new file)
  - Action: Implement the full tool as described below. Structure:

  **Module docstring + imports:**
  ```python
  """Warden Round Analyzer (Tool 5) — End-to-end round detection and map identification.

  Processes a raw video: detects game rounds via KDA ROI white-pixel detection,
  identifies the map inline on the start frame using perceptual hashing, exports
  only the score screen frame, and writes a rounds.json summary.

  Usage:
      python tools/warden_analyzer.py <video_path>
      python tools/warden_analyzer.py <video_path> --map-config output/map_config.json
      python tools/warden_analyzer.py <video_path> -o output/my_run/
      python tools/warden_analyzer.py <video_path> -c config/config.yaml
  """
  import argparse
  import json
  import os
  import subprocess
  import sys

  sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
  sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

  import cv2
  import imagehash

  from utils.config import load_config
  from utils.format import format_timestamp
  from utils.image import extract_roi, find_text_anchor, has_white_pixels, scale_roi, to_grayscale
  from utils.video import extract_frame_at_timestamp, extract_iframes_scaled, get_video_info
  from hash_validator import predict_map

  REF_HEIGHT = 1080
  ```

  **`identify_map()` function:**
  ```python
  def identify_map(frame, ref_roi, ref_hashes, canvas_size, hash_size, hash_method,
                   shift_tolerance, recognition_threshold, text_anchor_width=None):
      """Identify the map from a single downscaled in-game frame.

      Args:
          frame: Downscaled BGR frame (already at target_height).
          ref_roi: ROI dict at reference resolution (from map_config["roi"]).
          ref_hashes: {map_name: imagehash.ImageHash} — reference hashes.
          canvas_size: Hash canvas dimension (e.g. 64).
          hash_size: Hash size (e.g. 8).
          hash_method: Hash method string ('dhash', 'ahash', 'phash').
          shift_tolerance: Max horizontal bit-shift for Hamming comparison.
          recognition_threshold: Max best_dist to accept a match.
          text_anchor_width: Sub-ROI width in px @1080p, or None to disable.

      Returns:
          tuple: (map_name, best_dist, roi_crop_bgr)
              map_name: identified map name, or 'unrecognized'.
              best_dist: Hamming distance of best match (int), or None.
              roi_crop_bgr: Full ROI crop before anchor (for diagnostics), or None.
      """
      fh = frame.shape[0]
      roi = scale_roi(ref_roi, fh / REF_HEIGHT)

      if roi["x"] + roi["width"] > frame.shape[1] or roi["y"] + roi["height"] > frame.shape[0]:
          return "unrecognized", None, None

      try:
          cropped = extract_roi(frame, roi)
      except ValueError:
          return "unrecognized", None, None

      roi_crop = cropped.copy()

      if text_anchor_width:
          scaled_anchor_w = max(1, int(text_anchor_width * (fh / REF_HEIGHT)))
          anchor_x = find_text_anchor(cropped)
          if anchor_x == -1:
              return "unrecognized", None, roi_crop
          right = min(anchor_x + scaled_anchor_w, cropped.shape[1])
          if right - anchor_x < 2:
              return "unrecognized", None, roi_crop
          hash_crop = cropped[:, anchor_x:right]
      else:
          hash_crop = cropped

      gray = to_grayscale(hash_crop)
      canvas = cv2.resize(gray, (canvas_size, canvas_size), interpolation=cv2.INTER_AREA)

      map_name, best_dist = predict_map(canvas, ref_hashes, hash_size, hash_method, shift_tolerance)

      if best_dist >= recognition_threshold:
          return "unrecognized", best_dist, roi_crop

      return map_name, best_dist, roi_crop
  ```

  **`run()` function:**
  ```python
  def run(video_path, output_dir, config, map_config, map_config_path):
      """Run round detection, map identification, and score screen export.

      Args:
          video_path: Path to the input video.
          output_dir: Directory to write score frames, rounds.json, unrecognized/.
          config: Parsed config.yaml dict.
          map_config: Parsed map_config.json dict.
          map_config_path: String path to map_config.json (for rounds.json metadata).

      Returns:
          list: rounds_output — list of round dicts written to rounds.json.
      """
      # --- Extract config values ---
      ref_h = config["reference_resolution"]["height"]
      ref_w = config["reference_resolution"]["width"]
      target_height = config["processing"]["target_height"]
      pd = config["points_detection"]
      sat_max = pd["sat_max"]
      val_min = pd["val_min"]
      min_ratio = pd["min_ratio"]
      skip_duration = pd["skip_duration"]
      start_confirm_frames = pd["start_confirm_frames"]
      end_confirm_frames = pd["end_confirm_frames"]
      score_offset = pd["score_offset"]
      hud_brightness_max = pd["hud_brightness_max"]

      mi = config["map_identification"]
      recognition_threshold = mi.get("recognition_threshold", 10)
      shift_tolerance = mi.get("shift_tolerance", 2)
      text_anchor_width = mi.get("text_anchor_width") or None

      canvas_size = map_config["canvas_size"]
      hash_size = map_config["hash_size"]
      hash_method = map_config["hash_method"]
      ref_roi = {**map_config["roi"], "name": "map_name_hud"}

      ref_hashes = {
          name: imagehash.hex_to_hash(h)
          for name, h in sorted(map_config["maps"].items())
      }

      # --- Resolve KDA / notkda ROIs ---
      roi_zones = config["black_detection"]["roi_zones"]
      kda_roi_raw = next((r for r in roi_zones if r["name"] == "kda"), None)
      notkda_roi_raw = next((r for r in roi_zones if r["name"] == "notkda"), None)
      if kda_roi_raw is None:
          raise ValueError("Config must define a 'kda' ROI zone.")
      if notkda_roi_raw is None:
          raise ValueError("Config must define a 'notkda' ROI zone.")

      # --- Aspect ratio warning ---
      src_w, src_h = get_video_info(video_path)
      if abs((src_w / src_h) - (ref_w / ref_h)) > 0.01:
          print(
              f"Warning: Source aspect ratio ({src_w}x{src_h}) differs from "
              f"reference ({ref_w}x{ref_h}). ROI positions may be inaccurate.",
              file=sys.stderr,
          )

      ref_scale = target_height / ref_h
      kda_roi = scale_roi(kda_roi_raw, ref_scale)
      notkda_roi = scale_roi(notkda_roi_raw, ref_scale)

      os.makedirs(output_dir, exist_ok=True)

      print(f"Processing: {video_path}")
      print(f"Map config: {map_config_path}  ({len(map_config['maps'])} maps)")
      print(f"Output: {output_dir}")
      print(f"Config: recognition_threshold={recognition_threshold}, "
            f"shift_tolerance={shift_tolerance}, score_offset={score_offset}s")
      print()

      # --- Detection state machine ---
      state = "not_in_game"
      start_confirm_count = 0
      start_candidate_timestamp = None
      start_candidate_frame = None
      end_confirm_count = 0
      end_candidate_timestamp = None
      last_in_game_timestamp = None
      skip_until = -1.0
      prev_timestamp = None
      detection_seq = 0

      pending_rounds = []
      current_round = None

      frame_count = 0
      for frame, timestamp in extract_iframes_scaled(video_path, target_height):
          frame_count += 1

          if timestamp < skip_until:
              prev_timestamp = timestamp
              continue

          region = extract_roi(frame, kda_roi)
          white_detected = has_white_pixels(region, sat_max, val_min, min_ratio)
          if white_detected:
              notkda_region = extract_roi(frame, notkda_roi)
              white_detected = cv2.cvtColor(notkda_region, cv2.COLOR_BGR2GRAY).mean() < hud_brightness_max

          if state == "not_in_game":
              if white_detected:
                  start_confirm_count += 1
                  if start_candidate_timestamp is None:
                      start_candidate_timestamp = timestamp
                      start_candidate_frame = frame.copy()
                  if start_confirm_count >= start_confirm_frames:
                      confirmed_ts = start_candidate_timestamp
                      detection_seq += 1

                      map_name, best_dist, roi_crop = identify_map(
                          start_candidate_frame, ref_roi, ref_hashes,
                          canvas_size, hash_size, hash_method,
                          shift_tolerance, recognition_threshold, text_anchor_width,
                      )

                      current_round = {
                          "seq": detection_seq,
                          "start_ts": confirmed_ts,
                          "end_ts": None,
                          "score_ts": None,
                          "map_name": map_name,
                          "best_dist": best_dist,
                          "roi_crop": roi_crop,
                      }

                      state = "in_game"
                      last_in_game_timestamp = timestamp
                      start_confirm_count = 0
                      start_candidate_timestamp = None
                      start_candidate_frame = None
                      end_confirm_count = 0
                      end_candidate_timestamp = None
                      print(f"  START at {confirmed_ts:.1f}s  |  map={map_name}  dist={best_dist}")
              else:
                  start_confirm_count = 0
                  start_candidate_timestamp = None
                  start_candidate_frame = None

          elif state == "in_game":
              if white_detected:
                  last_in_game_timestamp = timestamp
                  end_confirm_count = 0
                  end_candidate_timestamp = None
              else:
                  end_confirm_count += 1
                  if end_candidate_timestamp is None:
                      end_candidate_timestamp = prev_timestamp if prev_timestamp is not None else timestamp
                  if end_confirm_count >= end_confirm_frames:
                      confirmed_end_ts = end_candidate_timestamp
                      score_ts = (last_in_game_timestamp + score_offset
                                  if last_in_game_timestamp is not None else None)

                      if current_round is not None:
                          current_round["end_ts"] = confirmed_end_ts
                          current_round["score_ts"] = score_ts
                          pending_rounds.append(current_round)
                          current_round = None

                      state = "not_in_game"
                      skip_until = timestamp + skip_duration
                      start_confirm_count = 0
                      start_candidate_timestamp = None
                      start_candidate_frame = None
                      end_confirm_count = 0
                      end_candidate_timestamp = None
                      last_in_game_timestamp = None
                      print(f"  END at {confirmed_end_ts:.1f}s  |  SCORE at "
                            f"{score_ts:.1f}s" if score_ts else f"  END at {confirmed_end_ts:.1f}s  |  SCORE skipped")

          prev_timestamp = timestamp

      # --- End-of-video warnings ---
      if frame_count == 0:
          print("Warning: No keyframes found in video.", file=sys.stderr)
      if state == "in_game":
          print(
              "Warning: Video ended while in-game — incomplete round discarded, no score exported.",
              file=sys.stderr,
          )
      if start_confirm_count > 0:
          print(
              f"Warning: Video ended with {start_confirm_count} partial start confirmation frame(s) "
              f"(needed {start_confirm_frames}) — potential start discarded.",
              file=sys.stderr,
          )
      if end_confirm_count > 0:
          print(
              f"Warning: Video ended with {end_confirm_count} partial end confirmation frame(s) "
              f"(needed {end_confirm_frames}) — potential end discarded.",
              file=sys.stderr,
          )

      # --- Post-detection: batch extract score frames ---
      print(f"\n  Extracting {len(pending_rounds)} score frame(s)...")
      unrecognized_dir = os.path.join(output_dir, "unrecognized")
      rounds_output = []

      for i, rd in enumerate(pending_rounds, 1):
          score_ts = rd["score_ts"]
          seq = rd["seq"]
          score_filename = None

          if score_ts is not None:
              ts_str = format_timestamp(score_ts)
              score_filename = f"{ts_str}_score_{seq:03d}.png"
              try:
                  fullres = extract_frame_at_timestamp(video_path, score_ts, src_w, src_h)
                  cv2.imwrite(os.path.join(output_dir, score_filename), fullres)
                  print(f"  SCORE -> {score_filename}  [{i}/{len(pending_rounds)}]")
              except (RuntimeError, subprocess.CalledProcessError) as e:
                  print(
                      f"  Warning: Could not extract score frame at {score_ts:.1f}s: {e}",
                      file=sys.stderr,
                  )
                  score_filename = None

          if rd["map_name"] == "unrecognized" and rd["roi_crop"] is not None and score_filename is not None:
              os.makedirs(unrecognized_dir, exist_ok=True)
              score_stem = os.path.splitext(score_filename)[0]
              roi_path = os.path.join(unrecognized_dir, f"{score_stem}_roi.png")
              cv2.imwrite(roi_path, rd["roi_crop"])
              print(f"  UNRECOGNIZED ROI -> unrecognized/{score_stem}_roi.png")

          rounds_output.append({
              "round": i,
              "map_name": rd["map_name"],
              "start_timer": rd["start_ts"],
              "end_timer": rd["end_ts"],
              "score_timer": score_ts,
              "recognition_distance": rd["best_dist"],
          })

      # --- Write rounds.json ---
      json_path = os.path.join(output_dir, "rounds.json")
      with open(json_path, "w", encoding="utf-8") as f:
          json.dump(
              {"video": video_path, "map_config": map_config_path, "rounds": rounds_output},
              f, indent=2,
          )
      print(f"\nWrote {json_path}  ({len(rounds_output)} round(s))\n")

      return rounds_output
  ```

  **`main()` function:**
  ```python
  def main():
      parser = argparse.ArgumentParser(
          description="Warden Round Analyzer — detect rounds, identify maps, export score screens."
      )
      parser.add_argument("video_path", help="Path to the input video file.")
      parser.add_argument(
          "--map-config", default="output/map_config.json",
          help="Path to map_config.json (default: output/map_config.json).",
      )
      parser.add_argument("-o", "--output", help="Output directory (default: output/warden_<video_stem>/).")
      parser.add_argument("-c", "--config", default="config/config.yaml", help="Path to config.yaml.")
      args = parser.parse_args()

      config = load_config(args.config)

      with open(args.map_config, "r", encoding="utf-8") as f:
          map_config = json.load(f)

      if args.output:
          output_dir = args.output
      else:
          video_stem = os.path.splitext(os.path.basename(args.video_path))[0]
          output_dir = os.path.join("output", f"warden_{video_stem}")

      run(args.video_path, output_dir, config, map_config, args.map_config)


  if __name__ == "__main__":
      main()
  ```

- [x] Task 3: Register Tool 5 in `wardentooling.py`
  - File: `wardentooling.py`
  - Action: Three sub-changes:

  **3a. Add `flow_tool5()` function** — insert after `flow_tool4()` (after line 312), before the `# Dev tool flows` section:
  ```python
  # ---------------------------------------------------------------------------
  # Tool 5 — warden_analyzer
  # ---------------------------------------------------------------------------


  def flow_tool5() -> tuple[list[str], str | None]:
      """Collect arguments for warden_analyzer.py.

      Returns (args_list, video_path).
      """
      video_path = browse_video_file("Select video file for Tool 5 — Analyze Rounds:")
      args = ["tools/warden_analyzer.py", video_path]

      map_config = questionary.text(
          "Map config path (--map-config)  [blank = output/map_config.json]:"
      ).ask()
      if map_config:
          args += ["--map-config", map_config]

      output_dir = questionary.text("Output directory (-o)  [blank = default]:").ask()
      if output_dir:
          args += ["-o", output_dir]

      return args, video_path
  ```

  **3b. Register in `_TOOL_MAP`** — add entry after `hash_validator` entry (line 414):
  ```python
  "warden_analyzer":      ("Tool 5 — Analyze Rounds",          flow_tool5),
  ```

  **3c. Wire into `menu_main()`:**
  - Add `"Tool 5 — Analyze Rounds"` to `choices_main` list (after `"Tool 4 — Validate Hash Accuracy"`)
  - Add handler block after the Tool 4 elif block:
  ```python
  elif choice == "Tool 5 — Analyze Rounds":
      args, video_path = flow_tool5()
      if not args:
          continue
      confirmed = questionary.confirm(
          f"Run: {exe_name} {' '.join(args)}?", default=True
      ).ask()
      if confirmed:
          returncode = run_tool(args)
          if returncode == 0:
              save_last_run("warden_analyzer", "Tool 5 — Analyze Rounds", args, video_path)
  ```

  **3d. Add branch in `_reprompt_source()`** — add elif after `hash_validator` branch (line 436):
  ```python
  elif tool_key == "warden_analyzer":
      new_video = browse_video_file("Select new video file:")
      # last_args layout: ["tools/warden_analyzer.py", <video>, ...]
      new_args = [last_args[0], new_video] + last_args[2:]
      return new_args, new_video
  ```

### Acceptance Criteria

- [ ] AC 1: Given a video with N complete rounds, when `warden_analyzer.py` runs to completion, then `rounds.json` contains exactly N entries in the `rounds` array.
- [ ] AC 2: Given a round whose map is in `map_config.json` with `best_dist < recognition_threshold`, when the tool runs, then the round's `map_name` matches the correct map key and `recognition_distance` equals `best_dist`.
- [ ] AC 3: Given a round whose map is not recognized (`best_dist >= recognition_threshold` or anchor not found), when the tool runs, then `map_name` is `"unrecognized"` and `<output_dir>/unrecognized/<score_stem>_roi.png` is created.
- [ ] AC 4: Given a complete run, when the tool finishes, then `<output_dir>` contains only `*_score_*.png` image files and `rounds.json` (no `*_start_*` or `*_end_*` frames).
- [ ] AC 5: Given a complete run, when `rounds.json` is inspected, then each round entry has numeric `start_timer`, `end_timer`, `score_timer` (seconds as floats) and `recognition_distance` (int or null).
- [ ] AC 6: Given `--map-config` not specified, when the tool runs, then it reads from `output/map_config.json`.
- [ ] AC 7: Given `-o` not specified, when the tool runs, then output is written to `output/warden_<video_stem>/`.
- [ ] AC 8: Given a video that ends while in-game, when the tool runs, then a warning is printed to stderr and no score frame or JSON entry is produced for the incomplete round.
- [ ] AC 9: Given the TUI launcher (`wardentooling.py`), when "Tool 5 — Analyze Rounds" is selected, then the user is prompted for video path, optional `--map-config`, and optional `-o`, and the tool runs correctly.
- [ ] AC 10: Given a previous Tool 5 run was saved, when "Run on new source" is selected in the TUI, then only the video path is re-prompted while all other flags are preserved.

## Additional Context

### Dependencies

- `imagehash>=4.2` — already installed (used by Tools 3 & 4)
- `opencv>=4.8` — already installed
- `output/map_config.json` — must exist and be generated by Tool 3 (`hash_comparator.py`) before running Tool 5
- `config/config.yaml` — must have `recognition_threshold` under `map_identification` (added in Task 1)

### Testing Strategy

- Run against a video with known rounds and known maps — verify `rounds.json` map names match expectations
- Run against a video containing a map not in `map_config.json` — verify `"unrecognized"` output and ROI file in `unrecognized/`
- Verify no `*_start_*` or `*_end_*` files in output dir
- Verify `rounds.json` top-level `video` and `map_config` fields match CLI args

### Notes

- **Risk — score frame timestamp may exceed video duration:** Inherited from `game_detector.py`. The `score_offset` (14.5s) added to `last_in_game_timestamp` can push past the end of a clipped video. The `except (RuntimeError, subprocess.CalledProcessError)` handler in the batch extraction phase covers this — the round entry is still written to `rounds.json` with `score_timer` set but `score_filename` null (score frame not exported).
- **`tile_cols` intentionally not read from `map_config` for single-frame hashing:** When `text_anchor_width` is active (which it is by default, value `52`), tiling is disabled — `tile_cols` is irrelevant. If `text_anchor_width` is 0/None, the full ROI is used and tiling would apply, but the current config has anchor enabled so this path won't be hit in practice.
- **Future:** Once validated against real footage, the `run()` function's detection loop and `identify_map()` helper are the exact logic to port to the mobile Warden app.

## Review Notes

- Adversarial review completed (2026-03-27)
- Findings: 12 total, 2 fixed, 10 skipped (noise / by-design / not-real)
- Resolution approach: auto-fix
- F2 fixed: `get_video_info()` call in `run()` wrapped in `try/except` with user-friendly error message and `sys.exit(1)`
- F8 fixed: `imagehash.hex_to_hash()` comprehension wrapped in `try/except ValueError` with clear map_config error message
