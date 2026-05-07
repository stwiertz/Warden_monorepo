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
from utils.image import apply_threshold, extract_roi, find_text_anchor, has_white_pixels, scale_roi, to_grayscale
from utils.video import extract_frame_at_timestamp, extract_iframes_scaled, get_video_info
from hash_validator import predict_map

REF_HEIGHT = 1080


def _load_minimap_config(config):
    """Parse the first minimap_identification config from config dict, or None."""
    from tools.minimap_zone_selector.zone_model import MinimapConfig, Zone
    mi = config.get("minimap_identification", {})
    cfgs = mi.get("configs", [])
    if not cfgs:
        return None
    c = cfgs[0]
    maps = {}
    for map_label, map_data in c.get("maps", {}).items():
        zones = []
        for z in map_data.get("zones", []):
            hsv = z["hsv"]
            zones.append(Zone(
                zone_id=z["id"],
                x=z["x"], y=z["y"], width=z["width"], height=z["height"],
                h_center=hsv["h_center"], h_tol=hsv["h_tol"],
                s_center=hsv["s_center"], s_tol=hsv["s_tol"],
                v_center=hsv["v_center"], v_tol=hsv["v_tol"],
                min_ratio=z["min_ratio"],
                weight=z["weight"],
                weight_override=z.get("weight_override", False),
            ))
        maps[map_label] = zones
    return MinimapConfig(
        id=c["id"],
        roi=c.get("roi", {}),
        identification_threshold=c.get("identification_threshold", 0.6),
        maps=maps,
    )


def identify_map_minimap(frame, minimap_cfg):
    """Identify map using minimap zone HSV matching.

    Args:
        frame: BGR numpy array at any resolution (zone coords scale automatically).
        minimap_cfg: MinimapConfig instance.

    Returns:
        tuple: (map_name, score) where map_name is 'unrecognized' if below threshold.
    """
    from tools.minimap_zone_selector.zone_model import zone_fires
    best_map = "unrecognized"
    best_score = 0.0
    for map_label, zones in minimap_cfg.maps.items():
        score = sum(z.weight for z in zones if zone_fires(z, frame))
        if score > best_score:
            best_score = score
            best_map = map_label
    if best_score < minimap_cfg.identification_threshold:
        return "unrecognized", best_score
    return best_map, best_score


def identify_map(frame, ref_roi, ref_hashes, canvas_size, hash_size, hash_method,
                 shift_tolerance, recognition_threshold, text_anchor_width=None, threshold_hash=False):
    """Identify the map from a single downscaled in-game frame.

    Args:
        frame: Downscaled BGR frame (already at target_height).
        ref_roi: ROI dict at reference resolution (from map_config["roi"]).
        ref_hashes: {map_name: list[imagehash.ImageHash]} — reference hashes (multiple per map supported).
        canvas_size: Hash canvas dimension (e.g. 64).
        hash_size: Hash size (e.g. 8).
        hash_method: Hash method string ('dhash', 'ahash', 'phash').
        shift_tolerance: Max horizontal bit-shift for Hamming comparison.
        recognition_threshold: Max best_dist to accept a match.
        text_anchor_width: Sub-ROI width in px @1080p, or None to disable.
        threshold_hash: If True, apply Otsu's adaptive threshold after grayscale conversion
                        before hashing. Must match the setting used in hash_comparator.py
                        when generating reference hashes.
                        Default False (function level); config default is True.

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
    if threshold_hash:
        gray = apply_threshold(gray)
    canvas = cv2.resize(gray, (canvas_size, canvas_size), interpolation=cv2.INTER_AREA)

    map_name, best_dist = predict_map(canvas, ref_hashes, hash_size, hash_method, shift_tolerance)

    if best_dist >= recognition_threshold:
        return "unrecognized", best_dist, roi_crop

    return map_name, best_dist, roi_crop


def run(video_path, output_dir, config, map_config=None, map_config_path=None):
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

    # Hash-based identification (optional fallback)
    ref_roi = ref_hashes = None
    canvas_size = hash_size = hash_method = shift_tolerance = recognition_threshold = None
    text_anchor_width = None
    threshold_hash = False

    if map_config is not None:
        mi = config["map_identification"]
        if "recognition_threshold" in map_config:
            recognition_threshold = map_config["recognition_threshold"]
            threshold_source = "map_config"
        else:
            recognition_threshold = mi.get("recognition_threshold", 10)
            threshold_source = "config.yaml"
            print(
                f"Warning: recognition_threshold not found in map_config.json — "
                f"using config.yaml value ({recognition_threshold}). "
                "Regenerate map_config.json with hash_comparator.py for a calibrated threshold.",
                file=sys.stderr,
            )
        shift_tolerance = mi.get("shift_tolerance", 2)
        text_anchor_width = mi.get("text_anchor_width") or None
        threshold_hash = mi.get("threshold_hash", False)

        canvas_size = map_config["canvas_size"]
        hash_size = map_config["hash_size"]
        hash_method = map_config["hash_method"]
        ref_roi = {**map_config["roi"], "name": "map_name_hud"}

        try:
            ref_hashes = {}
            for name, h in sorted(map_config["maps"].items()):
                if isinstance(h, list):
                    ref_hashes[name] = [imagehash.hex_to_hash(x) for x in h]
                else:
                    ref_hashes[name] = [imagehash.hex_to_hash(h)]
        except ValueError as e:
            print(f"Error: Invalid hash in map_config '{map_config_path}': {e}", file=sys.stderr)
            sys.exit(1)

    # Minimap zone-based identification
    minimap_cfg = _load_minimap_config(config)

    # --- Resolve KDA / notkda ROIs ---
    roi_zones = config["black_detection"]["roi_zones"]
    kda_roi_raw = next((r for r in roi_zones if r["name"] == "kda"), None)
    notkda_roi_raw = next((r for r in roi_zones if r["name"] == "notkda"), None)
    if kda_roi_raw is None:
        raise ValueError("Config must define a 'kda' ROI zone.")
    if notkda_roi_raw is None:
        raise ValueError("Config must define a 'notkda' ROI zone.")

    # --- Aspect ratio warning ---
    try:
        src_w, src_h = get_video_info(video_path)
    except (RuntimeError, subprocess.CalledProcessError) as e:
        print(f"Error: Could not read video info for '{video_path}': {e}", file=sys.stderr)
        sys.exit(1)
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
    print(f"Output: {output_dir}")
    if minimap_cfg is not None:
        print(f"Minimap config: '{minimap_cfg.id}'  ({len(minimap_cfg.maps)} maps configured)  [primary]")
    if map_config is not None:
        fallback_label = "fallback" if minimap_cfg is not None else "primary"
        print(f"Hash config: {map_config_path}  ({len(map_config['maps'])} maps)  [{fallback_label}]")
        print(f"  recognition_threshold={recognition_threshold}, shift_tolerance={shift_tolerance}, "
              f"score_offset={score_offset}s, threshold_hash={threshold_hash}")
        if threshold_hash:
            print(
                "Warning: threshold_hash=True — ensure map_config.json was generated with "
                "the same setting. Mismatched preprocessing degrades recognition accuracy.",
                file=sys.stderr,
            )
    if minimap_cfg is None and map_config is None:
        print("Warning: No identification method available — map names will be 'unrecognized'.", file=sys.stderr)
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

                    map_name, best_dist, roi_crop, map_method = "unrecognized", None, None, "none"

                    if minimap_cfg is not None:
                        map_name, mini_score = identify_map_minimap(
                            start_candidate_frame, minimap_cfg
                        )
                        if map_name != "unrecognized":
                            best_dist = round(mini_score, 3)
                            map_method = "minimap"

                    if map_name == "unrecognized" and ref_hashes is not None:
                        map_name, best_dist, roi_crop = identify_map(
                            start_candidate_frame, ref_roi, ref_hashes,
                            canvas_size, hash_size, hash_method,
                            shift_tolerance, recognition_threshold, text_anchor_width,
                            threshold_hash=threshold_hash,
                        )
                        if map_name != "unrecognized":
                            map_method = "hash"

                    current_round = {
                        "seq": detection_seq,
                        "start_ts": confirmed_ts,
                        "end_ts": None,
                        "score_ts": None,
                        "map_name": map_name,
                        "best_dist": best_dist,
                        "roi_crop": roi_crop,
                        "map_method": map_method,
                    }

                    state = "in_game"
                    last_in_game_timestamp = timestamp
                    start_confirm_count = 0
                    start_candidate_timestamp = None
                    start_candidate_frame = None
                    end_confirm_count = 0
                    end_candidate_timestamp = None
                    print(f"  START at {confirmed_ts:.1f}s  |  map={map_name}  [{map_method}]  score={best_dist}")
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
                    if score_ts:
                        print(f"  END at {confirmed_end_ts:.1f}s  |  SCORE at {score_ts:.1f}s")
                    else:
                        print(f"  END at {confirmed_end_ts:.1f}s  |  SCORE skipped")

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

        if rd["map_name"] == "unrecognized" and score_filename is not None:
            os.makedirs(unrecognized_dir, exist_ok=True)
            score_stem = os.path.splitext(score_filename)[0]
            if rd["roi_crop"] is not None:
                roi_path = os.path.join(unrecognized_dir, f"{score_stem}_roi.png")
                cv2.imwrite(roi_path, rd["roi_crop"])
                print(f"  UNRECOGNIZED ROI -> unrecognized/{score_stem}_roi.png")
            try:
                start_frame = extract_frame_at_timestamp(video_path, rd["start_ts"], src_w, src_h)
                start_path = os.path.join(unrecognized_dir, f"{score_stem}_start.png")
                cv2.imwrite(start_path, start_frame)
                print(f"  UNRECOGNIZED START -> unrecognized/{score_stem}_start.png")
            except (RuntimeError, subprocess.CalledProcessError) as e:
                print(
                    f"  Warning: Could not extract start frame at {rd['start_ts']:.1f}s: {e}",
                    file=sys.stderr,
                )

        rounds_output.append({
            "round": i,
            "map_name": rd["map_name"],
            "map_method": rd.get("map_method", "none"),
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
            f, indent=2, default=str,
        )
    print(f"\nWrote {json_path}  ({len(rounds_output)} round(s))\n")

    return rounds_output


def main():
    parser = argparse.ArgumentParser(
        description="Warden Round Analyzer — detect rounds, identify maps, export score screens."
    )
    parser.add_argument("video_path", help="Path to the input video file.")
    parser.add_argument(
        "--map-config", default=None,
        help="Path to map_config.json for hash-based identification (optional fallback).",
    )
    parser.add_argument("-o", "--output", help="Output directory (default: output/warden_<video_stem>/).")
    parser.add_argument("-c", "--config", default="config/config.yaml", help="Path to config.yaml.")
    args = parser.parse_args()

    config = load_config(args.config)

    map_config = None
    map_config_path = args.map_config
    if map_config_path is not None:
        with open(map_config_path, "r", encoding="utf-8") as f:
            map_config = json.load(f)

    if args.output:
        output_dir = args.output
    else:
        video_stem = os.path.splitext(os.path.basename(args.video_path))[0]
        output_dir = os.path.join("output", f"warden_{video_stem}")

    run(args.video_path, output_dir, config, map_config, map_config_path)


if __name__ == "__main__":
    main()
