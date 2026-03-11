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
from utils.image import extract_roi, scale_roi, to_grayscale
from utils.video import check_ffmpeg, extract_iframes_scaled, get_video_info


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
    canvas = cv2.resize(gray, (canvas_size, canvas_size), interpolation=cv2.INTER_AREA)
    return canvas


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

    Extracts the first I-frame from each video at source resolution.

    Args:
        video_entries: List of [map_name, video_path] pairs.

    Returns:
        dict: {map_name: BGR numpy array} for each map.

    Raises:
        ValueError: If no frames could be extracted from any video.
    """
    check_ffmpeg()
    maps = {}

    for map_name, video_path in video_entries:
        src_w, src_h = get_video_info(video_path)
        # Extract at source resolution for crisp text in the ROI
        for frame, timestamp in extract_iframes_scaled(video_path, src_h):
            maps[map_name] = frame
            print(f"  Loaded: {map_name} <- {os.path.basename(video_path)} "
                  f"(I-frame at {timestamp:.1f}s, {src_w}x{src_h})")
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


def run(map_frames, config, output_dir, preview=False):
    """Main orchestrator — process frames, generate hashes, check collisions, write output.

    Args:
        map_frames: Dict of {map_name: BGR numpy array}.
        config: Parsed YAML config dict.
        output_dir: Directory for output files.
        preview: If True, write processed canvas images.

    Returns:
        dict: The output config dictionary written to map_config.json.
    """
    map_id_config = config["map_identification"]
    roi_config = map_id_config["roi"]
    canvas_size = map_id_config["canvas_size"]
    hash_size = map_id_config["hash_size"]
    collision_threshold = map_id_config["collision_threshold"]
    ref_h = config["reference_resolution"]["height"]
    ref_w = config["reference_resolution"]["width"]
    ref_aspect = ref_w / ref_h

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

    print(f"\n  Config: canvas={canvas_size}x{canvas_size}, hash_size={hash_size}, "
          f"collision_threshold={collision_threshold}")
    print(f"  ROI: {roi_config['name']} ({roi_config['x']},{roi_config['y']} "
          f"{roi_config['width']}x{roi_config['height']}) @ {ref_h}p "
          f"-> scaled ({scaled_roi['x']},{scaled_roi['y']} "
          f"{scaled_roi['width']}x{scaled_roi['height']}) @ {frame_h}p")

    # Process each map frame
    hash_dict = {}
    for map_name, frame in map_frames.items():
        canvas = process_frame(frame, scaled_roi, canvas_size)
        phash = compute_phash(canvas, hash_size)
        hash_dict[map_name] = phash
        print(f"  Hashed: {map_name} -> {str(phash)}")

        if preview:
            preview_path = os.path.join(output_dir, f"preview_{map_name}.png")
            if not cv2.imwrite(preview_path, canvas):
                print(f"Warning: Failed to write preview: {preview_path}", file=sys.stderr)
            else:
                print(f"  Preview: {preview_path}")

    # Check for collisions
    collisions = check_collisions(hash_dict, collision_threshold)

    # Build output
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
        "maps": {name: str(h) for name, h in hash_dict.items()},
    }

    output_path = os.path.join(output_dir, "map_config.json")
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    # Summary
    print(f"\n{'=' * 50}")
    print(f"Summary:")
    print(f"  Maps processed: {len(hash_dict)}")
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
        nargs=2,
        action="append",
        metavar=("MAP_NAME", "VIDEO_PATH"),
        help="Map name and video path pair (repeatable)",
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
        for map_name, video_path in args.video:
            if not os.path.isfile(video_path):
                print(f"Error: Video file not found: {video_path}", file=sys.stderr)
                sys.exit(1)

    config = load_config(args.config)

    # Resolve output directory — CLI arg > config default
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
        run(map_frames, config, output_dir, preview=args.preview)

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error during processing: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
