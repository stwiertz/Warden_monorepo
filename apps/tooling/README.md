# Warden Tooling

Desktop video analysis pipeline for the EVA mobile game. Detects round transitions in gameplay recordings and extracts start-of-round and end-of-round frames to build the map identification dataset used by the mobile app.

## Prerequisites

- Python 3.8+
- FFmpeg (must be on system PATH)

```bash
pip install -r requirements.txt
```

## Available Tools

### 1. Black Screen Detector

Detects black screen transitions in game recordings using a start/end state machine. Exports the end-of-round frame before each end blackscreen and the first game frame after each start blackscreen. Consecutive end detections without a start in between are filtered out (handles trailing dead air).

```bash
python tools/black_screen_detector.py <video_path> [options]
```

| Option | Default | Description |
|---|---|---|
| `-o, --output-dir` | `./output` | Directory for extracted frames |
| `-c, --config` | `config/config.yaml` | Path to config file |
| `--threshold` | `15` | Brightness threshold (0-255) |

**Examples:**

```bash
# Basic usage
python tools/black_screen_detector.py source/astera.mp4

# Custom output directory
python tools/black_screen_detector.py source/astera.mp4 -o ./frames/

# Override brightness threshold
python tools/black_screen_detector.py source/astera.mp4 --threshold 20
```

Output frames are saved as `end_MMmSSs_NNN.png` (end-of-round) and `start_MMmSSs_NNN.png` (start-of-round).

### 2. Frame Labeler *(planned)*

Categorize extracted frames by map into labeled folders.

### 3. Pixel Finder *(planned)*

Analyze labeled frames to find discriminating pixels that reliably distinguish maps. Outputs a JSON config with pixel coordinates, RGB values, and tolerances.

### 4. Validator *(planned)*

Validate the full pipeline accuracy against ground truth labels.

## Configuration

All parameters live in [config/config.yaml](config/config.yaml) — ROI zones, brightness threshold, skip duration, and output settings. ROI coordinates are defined at 1920x1080 and scaled automatically for other resolutions.

## Project Structure

```
tools/                  CLI entry points
utils/                  Shared modules (video I/O, image processing)
config/config.yaml      Centralized configuration
source/                 Input videos (git-ignored)
output/                 Extracted frames (default output dir)
docs/                   Project documentation
```
