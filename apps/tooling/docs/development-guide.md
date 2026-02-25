# Development Guide — Warden-tooling

> Generated: 2026-02-25 | Scan Level: Quick

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.8+ | f-strings, subprocess improvements required |
| FFmpeg | Any recent | Must be available on system PATH |
| pip | Any | For installing Python dependencies |

### Verifying Prerequisites

```bash
python --version    # Should show 3.8+
ffmpeg -version     # Should show FFmpeg version info
pip --version       # Should show pip version
```

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd Warden-tooling

# Install Python dependencies
pip install -r requirements.txt
```

### Dependencies Installed

| Package | Version Range | Purpose |
|---------|---------------|---------|
| `opencv-python` | >=4.8, <5 | Image processing (resize, grayscale, ROI) |
| `numpy` | >=1.24, <2 | Array operations for frame data |
| `pyyaml` | >=6.0, <7 | YAML configuration parsing |

## Configuration

All tunable parameters are in `config/config.yaml`. No `.env` files or environment variables are needed.

### Key Configuration Values

| Parameter | Default | Description |
|-----------|---------|-------------|
| `reference_resolution` | 1920x1080 | Resolution at which ROI coordinates are defined |
| `processing.target_height` | 360 | Downscale height for analysis (lower = faster) |
| `black_detection.brightness_threshold` | 15 | Pixel brightness cutoff (0-255, <=threshold = black) |
| `black_detection.skip_duration` | 15.0 | Seconds to skip after a detection |
| `black_detection.roi_zones` | minimap, map_name | Regions checked for simultaneous blackness |
| `output.default_dir` | ./output | Default output directory for extracted frames |

## Running Tools

### Tool 1 — Black Screen Detector

```bash
# Basic usage (uses default config and output directory)
python tools/black_screen_detector.py source/astera.mp4

# Specify output directory
python tools/black_screen_detector.py source/astera.mp4 -o ./my-output/

# Use custom config file
python tools/black_screen_detector.py source/astera.mp4 -c config/custom.yaml

# Override brightness threshold
python tools/black_screen_detector.py source/astera.mp4 --threshold 20

# All options combined
python tools/black_screen_detector.py source/astera.mp4 -o ./output/ -c config/config.yaml --threshold 15
```

### CLI Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `video` | Yes | — | Path to input video file |
| `-o, --output-dir` | No | From config | Output directory for extracted frames |
| `-c, --config` | No | `config/config.yaml` | Path to configuration file |
| `--threshold` | No | From config (15) | Brightness threshold override (0-255) |

### Expected Output

```
Processing: source/astera.mp4
Config: threshold=15, skip=15.0s, target_height=360px
ROI zones: ['minimap', 'map_name']

  END at 142.3s -> exported end_02m20s_001.png (prev frame at 140.1s)
  START at 157.5s -> exported start_02m37s_002.png
  END at 298.7s -> exported end_04m56s_003.png (prev frame at 296.5s)
  START at 313.2s -> exported start_05m13s_004.png

==================================================
Summary:
  I-frames processed: 847
  Game ends detected: 2
  Game starts detected: 2
  Total events: 4
  Output directory: /path/to/output
  Exported frames:
    - end_02m20s_001.png  (end at 140.1s)
    - start_02m37s_002.png  (start at 157.5s)
    - end_04m56s_003.png  (end at 296.5s)
    - start_05m13s_004.png  (start at 313.2s)
==================================================
```

## Testing

No formal test suite exists. Validation is planned as **Tool 4** which will:

- Run full pipeline tests (end-to-end: video → detection → map identification)
- Run isolated map identification tests (frame → pixel check)
- Generate accuracy reports per map with confidence margins
- Support training set and test set validation

## Adding New Tools

Follow the established pattern:

1. Create a new file in `tools/` (e.g., `tools/pixel_finder.py`)
2. Import shared utilities from `utils/video.py` and `utils/image.py`
3. Add argparse CLI with standard options
4. Use `config/config.yaml` for any tunable parameters (add new sections as needed)
5. Follow the stateless function design pattern — no global state

## Project Layout Conventions

- **One tool per file** in `tools/` — each is self-contained with its own `main()`
- **Stateless functions** in `utils/` — pure functions, no side effects except I/O
- **External config** in `config/` — no hardcoded values in source
- **Timestamps in filenames** — output files use `MMmSSs` format with `start_`/`end_` prefix
- **Sequence counters** — single monotonic counter across start/end events for chronological ordering
