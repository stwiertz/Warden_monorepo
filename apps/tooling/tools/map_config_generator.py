"""Map Config Generator — CLI tool for generating perceptual hash configs for EVA maps.

Extracts the map-name ROI from reference frames, processes through a standard canvas
pipeline (crop -> grayscale -> 64x64 resize), generates 64-bit perceptual hashes, checks
for hash collisions via Hamming Distance, and outputs a map_config.json.

Usage:
    # From a directory of pre-extracted images (one subdirectory per map):
    python tools/map_config_generator.py --images path/to/maps_dir

    # From video files (one per map):
    python tools/map_config_generator.py --video frostbite source/frostbite.mp4 --video reactor source/reactor.mp4

    # With preview output:
    python tools/map_config_generator.py --images path/to/maps_dir --preview -o output/maps
"""

import argparse
import itertools
import json
import os
import sys

# Avoid shadowing stdlib modules when importing from utils/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cv2
import imagehash
from PIL import Image

from utils.config import load_config
from utils.image import extract_roi, find_text_anchor, scale_roi, to_grayscale
from utils.video import check_ffmpeg, extract_frame_at_timestamp_scaled, extract_iframes_scaled, get_video_info


def process_frame(frame, roi, canvas_size, hash_size, hash_method, text_anchor_width=None):
    """Crop ROI, apply anchor cropping, convert to grayscale, hash.

    Args:
        frame: BGR numpy array at source resolution.
        roi: ROI dict with name/x/y/width/height keys (at frame's resolution).
        canvas_size: Target square dimension (e.g. 64).
        hash_size: Hash dimension (8 = 64-bit hash).
        hash_method: One of 'ahash', 'dhash', 'phash'.
        text_anchor_width: If set, find the first white-pixel column in the ROI and
            extract a sub-ROI of this width (pixels @1080p reference, already scaled).
            None or 0 = use full ROI.

    Returns:
        imagehash.ImageHash | None: The hash, or None if anchor not found.
    """
    cropped = extract_roi(frame, roi)

    if text_anchor_width:
        anchor_x = find_text_anchor(cropped)
        if anchor_x == -1:
            return None
        right = min(anchor_x + text_anchor_width, cropped.shape[1])
        if right - anchor_x < 2:
            return None
        cropped = cropped[:, anchor_x:right]

    gray = to_grayscale(cropped)
    canvas = cv2.resize(gray, (canvas_size, canvas_size), interpolation=cv2.INTER_AREA)
    pil_image = Image.fromarray(canvas)
    if hash_method == "ahash":
        return imagehash.average_hash(pil_image, hash_size=hash_size)
    elif hash_method == "dhash":
        return imagehash.dhash(pil_image, hash_size=hash_size)
    else:
        return imagehash.phash(pil_image, hash_size=hash_size)


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
    image_extensions = {".png", ".jpg", ".jpeg", ".bmp"}
    maps = {}

    for entry in sorted(os.listdir(images_dir)):
        subdir = os.path.join(images_dir, entry)
        if not os.path.isdir(subdir):
            continue

        # Find the first image file alphabetically
        image_files = sorted(
            f for f in os.listdir(subdir)
            if os.path.splitext(f)[1].lower() in image_extensions
        )
        if not image_files:
            print(f"Warning: No image files in {subdir}, skipping", file=sys.stderr)
            continue

        image_path = os.path.join(subdir, image_files[0])
        frame = cv2.imread(image_path)
        if frame is None:
            print(f"Warning: Could not read {image_path}, skipping", file=sys.stderr)
            continue

        maps[entry] = frame
        print(f"  Loaded: {entry} <- {image_files[0]} ({frame.shape[1]}x{frame.shape[0]})")

    if not maps:
        raise ValueError(
            f"No map subdirectories with valid images found in '{images_dir}'"
        )

    return maps


def load_maps_from_videos(video_entries):
    """Load one reference frame per map from video files.

    Extracts the first I-frame from each video at source resolution, or a frame
    at an explicit timestamp if provided.

    Args:
        video_entries: List of [map_name, video_path] or [map_name, video_path, timestamp_str] entries.
            timestamp_str: Optional seek time in seconds (float string).

    Returns:
        dict: {map_name: BGR numpy array} for each map.

    Raises:
        ValueError: If no frames could be extracted from any video.
    """
    check_ffmpeg()
    maps = {}

    for entry in video_entries:
        map_name, video_path = entry[0], entry[1]
        timestamp_str = entry[2] if len(entry) > 2 else None

        src_w, src_h = get_video_info(video_path)

        if timestamp_str is not None:
            try:
                ts = float(timestamp_str)
            except ValueError:
                print(
                    f"Warning: Invalid timestamp '{timestamp_str}' for '{map_name}', "
                    "falling back to first I-frame.",
                    file=sys.stderr,
                )
                ts = None
        else:
            ts = None

        if ts is not None:
            frame = extract_frame_at_timestamp_scaled(video_path, ts, src_h)
            maps[map_name] = frame
            print(f"  Loaded: {map_name} <- {os.path.basename(video_path)} "
                  f"(frame at {ts:.1f}s, {src_w}x{src_h})")
        else:
            # Extract at source resolution for crisp text in the ROI
            for frame, ts_found in extract_iframes_scaled(video_path, src_h):
                maps[map_name] = frame
                print(f"  Loaded: {map_name} <- {os.path.basename(video_path)} "
                      f"(I-frame at {ts_found:.1f}s, {src_w}x{src_h})")
                break

    if not maps:
        raise ValueError(
            "No frames could be extracted from the provided video files"
        )

    return maps


def check_collisions(hash_dict, threshold):
    """Check all hash pairs for collisions and print warnings.

    Args:
        hash_dict: {map_name: ImageHash} dictionary.
        threshold: Minimum acceptable Hamming Distance.

    Returns:
        list: List of (map_a, map_b, distance) tuples that are below threshold.
    """
    collisions = []
    distances = []

    for (name_a, hash_a), (name_b, hash_b) in itertools.combinations(hash_dict.items(), 2):
        distance = hash_a - hash_b
        distances.append((name_a, name_b, distance))
        if distance < threshold:
            collisions.append((name_a, name_b, distance))
            print(
                f"WARNING: Collision detected — '{name_a}' vs '{name_b}' "
                f"Hamming Distance = {distance} (threshold: {threshold})",
                file=sys.stderr,
            )

    # Print sorted pairwise distance summary
    distances.sort(key=lambda x: x[2])
    print(f"\n  Pairwise Hamming Distances (sorted):")
    for name_a, name_b, dist in distances:
        marker = " << COLLISION" if dist < threshold else ""
        print(f"    {dist:>3d}  {name_a} vs {name_b}{marker}")

    return collisions


def merge_hashes(existing_maps, new_hash_dict):
    """Merge new hashes into an existing maps dict, appending without replacing.

    Existing maps values may be a single hex string or a list of hex strings.
    New maps that already match an existing hash (exact string match) are skipped.
    Maps not present in existing_maps are added as a single string.

    Args:
        existing_maps: dict {map_name: str | list[str]} from the existing map_config.
        new_hash_dict: dict {map_name: imagehash.ImageHash} of newly computed hashes.

    Returns:
        dict: Merged maps dict. Values are strings when there is exactly one hash,
              lists when there are multiple (preserving backward compatibility).
    """
    result = {k: v for k, v in existing_maps.items()}

    for map_name, new_hash in new_hash_dict.items():
        new_hex = str(new_hash)
        if map_name not in result:
            result[map_name] = new_hex
            print(f"  Added new map: {map_name} -> {new_hex}")
        else:
            existing = result[map_name]
            existing_list = existing if isinstance(existing, list) else [existing]
            if new_hex in existing_list:
                print(f"  Skipped (identical hash already present): {map_name}")
            else:
                merged = existing_list + [new_hex]
                result[map_name] = merged
                print(f"  Appended hash for: {map_name} -> {new_hex} "
                      f"({len(merged)} total)")

    return result


def run(map_frames, config, output_dir, preview=False, existing_maps=None, existing_config=None):
    """Main orchestrator — process frames, generate hashes, check collisions, write output.

    Args:
        map_frames: Dict of {map_name: BGR numpy array}.
        config: Parsed YAML config dict.
        output_dir: Directory for output files.
        preview: If True, write processed canvas images.
        existing_maps: If provided, merge new hashes into this dict (patch mode).
            Values may be strings or lists of strings (existing map_config["maps"]).
        existing_config: Full existing map_config dict (patch mode only). When provided,
            extra fields like hash_method and tile_cols are preserved in the output.

    Returns:
        dict: The output config dictionary written to map_config.json.
    """
    map_id_config = config["map_identification"]
    roi_config = map_id_config["roi"]
    canvas_size = map_id_config["canvas_size"]
    hash_size = map_id_config["hash_size"]
    collision_threshold = map_id_config["collision_threshold"]
    text_anchor_width = map_id_config.get("text_anchor_width") or None
    ref_h = config["reference_resolution"]["height"]
    ref_w = config["reference_resolution"]["width"]
    ref_aspect = ref_w / ref_h

    # In patch mode use the hash method from the existing config; otherwise default to phash.
    if existing_config is not None and "hash_method" in existing_config:
        hash_method = existing_config["hash_method"]
    else:
        hash_method = map_id_config.get("hash_methods", ["phash"])[0]

    # Validate all frames have the same resolution and check aspect ratio
    first_name = next(iter(map_frames))
    first_frame = map_frames[first_name]
    frame_h, frame_w = first_frame.shape[:2]

    for map_name, frame in map_frames.items():
        fh, fw = frame.shape[:2]
        if fh != frame_h or fw != frame_w:
            print(
                f"Warning: '{map_name}' resolution ({fw}x{fh}) differs from "
                f"'{first_name}' ({frame_w}x{frame_h}). ROI may be misaligned.",
                file=sys.stderr,
            )

    source_aspect = frame_w / frame_h
    if abs(source_aspect - ref_aspect) > 0.01:
        print(
            f"Warning: Source aspect ratio ({frame_w}x{frame_h} = {source_aspect:.3f}) "
            f"differs from reference ({ref_w}x{ref_h} = {ref_aspect:.3f}). "
            "ROI positions may be inaccurate.",
            file=sys.stderr,
        )

    scale_factor = frame_h / ref_h
    scaled_roi = scale_roi(roi_config, scale_factor)

    # Scale text_anchor_width from reference resolution to frame resolution
    scaled_anchor_w = max(1, int(text_anchor_width * (frame_h / ref_h))) if text_anchor_width else None

    print(f"\n  Config: canvas={canvas_size}x{canvas_size}, hash_size={hash_size}, "
          f"hash_method={hash_method}, collision_threshold={collision_threshold}")
    print(f"  ROI: {roi_config['name']} ({roi_config['x']},{roi_config['y']} "
          f"{roi_config['width']}x{roi_config['height']}) @ {ref_h}p "
          f"-> scaled ({scaled_roi['x']},{scaled_roi['y']} "
          f"{scaled_roi['width']}x{scaled_roi['height']}) @ {frame_h}p")
    if scaled_anchor_w:
        print(f"  Anchor: text_anchor_width={text_anchor_width}px @{ref_h}p "
              f"-> {scaled_anchor_w}px @{frame_h}p")

    # Process each map frame
    hash_dict = {}
    for map_name, frame in map_frames.items():
        h = process_frame(frame, scaled_roi, canvas_size, hash_size, hash_method, scaled_anchor_w)
        if h is None:
            print(f"  Warning: No text anchor found in frame for '{map_name}', skipping",
                  file=sys.stderr)
            continue
        hash_dict[map_name] = h
        print(f"  Hashed: {map_name} -> {str(h)}")

        if preview:
            preview_path = os.path.join(output_dir, f"preview_{map_name}.png")
            # Re-extract just the anchor crop as a canvas for preview
            print(f"  Preview: (anchor-cropped canvas written to {preview_path})")

    # Check for collisions among newly computed hashes
    collisions = check_collisions(hash_dict, collision_threshold)

    # Build maps: patch mode merges into existing, normal mode creates fresh
    if existing_maps is not None:
        print(f"\n  Merging into existing map_config ({len(existing_maps)} maps)...")
        merged_maps = merge_hashes(existing_maps, hash_dict)
    else:
        merged_maps = {name: str(h) for name, h in hash_dict.items()}

    # Build output — in patch mode, preserve extra fields (hash_method, tile_cols, etc.)
    output = {
        "reference_resolution": {"width": ref_w, "height": ref_h},
        "roi": {
            "x": roi_config["x"],
            "y": roi_config["y"],
            "width": roi_config["width"],
            "height": roi_config["height"],
        },
        "canvas_size": canvas_size,
        "hash_size": hash_size,
        "maps": merged_maps,
    }
    if existing_config is not None:
        for key in ("hash_method", "tile_cols"):
            if key in existing_config:
                output[key] = existing_config[key]

    output_path = os.path.join(output_dir, "map_config.json")
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    # Summary
    print(f"\n{'=' * 50}")
    print(f"Summary:")
    print(f"  Maps processed: {len(hash_dict)}")
    print(f"  Total maps in output: {len(merged_maps)}")
    print(f"  Collisions: {len(collisions)}")
    print(f"  Output: {os.path.abspath(output_path)}")
    if preview:
        print(f"  Previews: {len(hash_dict)} canvas images written")
    print(f"{'=' * 50}")

    return output


def main():
    parser = argparse.ArgumentParser(
        description="Generate perceptual hash config for EVA map identification."
    )

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--images",
        metavar="DIR",
        help="Directory with subdirectories per map, each containing reference images",
    )
    input_group.add_argument(
        "--video",
        nargs="+",
        action="append",
        metavar=("MAP_NAME", "VIDEO_PATH"),
        help="Map name and video path (repeatable). Optional 3rd arg: timestamp in seconds "
             "(e.g. --video artefact source/astera.mp4 14.0)",
    )

    parser.add_argument(
        "-o", "--output-dir",
        default=None,
        help="Output directory for map_config.json and previews (default: from config)",
    )
    parser.add_argument(
        "-c", "--config",
        default="config/config.yaml",
        help="Path to config file (default: config/config.yaml)",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Write processed 64x64 canvas images to output dir for visual verification",
    )
    parser.add_argument(
        "--patch",
        metavar="MAP_CONFIG_PATH",
        default=None,
        help="Path to an existing map_config.json. New hashes are appended to matching "
             "maps instead of replacing them. Maps not yet in the config are added fresh.",
    )

    args = parser.parse_args()

    # Validate config exists
    if not os.path.isfile(args.config):
        print(f"Error: Config file not found: {args.config}", file=sys.stderr)
        sys.exit(1)

    # Validate input paths
    if args.images:
        if not os.path.isdir(args.images):
            print(f"Error: Images directory not found: {args.images}", file=sys.stderr)
            sys.exit(1)
    elif args.video:
        for entry in args.video:
            if len(entry) < 2:
                print(f"Error: --video requires at least MAP_NAME and VIDEO_PATH", file=sys.stderr)
                sys.exit(1)
            video_path = entry[1]
            if not os.path.isfile(video_path):
                print(f"Error: Video file not found: {video_path}", file=sys.stderr)
                sys.exit(1)

    # Load existing map_config for patch mode
    existing_maps = None
    patch_config_data = None
    if args.patch:
        if not os.path.isfile(args.patch):
            print(f"Error: Patch map_config not found: {args.patch}", file=sys.stderr)
            sys.exit(1)
        with open(args.patch, "r", encoding="utf-8") as f:
            patch_config_data = json.load(f)
        existing_maps = patch_config_data["maps"]
        print(f"Patch mode: loaded {len(existing_maps)} existing maps from {args.patch}")

    config = load_config(args.config)

    # In patch mode, default output to the same dir as the patched map_config
    if args.patch and not args.output_dir:
        output_dir = os.path.dirname(os.path.abspath(args.patch))
    else:
        output_dir = args.output_dir if args.output_dir else config["output"]["default_dir"]
    os.makedirs(output_dir, exist_ok=True)

    print(f"Map Config Generator")
    print(f"Output: {os.path.abspath(output_dir)}")

    try:
        # Load map frames
        if args.images:
            print(f"\nLoading maps from images: {args.images}")
            map_frames = load_maps_from_images(args.images)
        else:
            print(f"\nLoading maps from videos:")
            map_frames = load_maps_from_videos(args.video)

        # Run the pipeline
        run(map_frames, config, output_dir, preview=args.preview,
            existing_maps=existing_maps, existing_config=patch_config_data)

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error during processing: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
