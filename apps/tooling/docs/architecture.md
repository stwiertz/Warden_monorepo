# Architecture — Warden-tooling

> Generated: 2026-02-25 | Project Type: CLI Toolchain | Scan Level: Quick

## Executive Summary

Warden-tooling is a Python-based desktop video analysis pipeline designed to validate detection algorithms and generate map identification datasets for the EVA mobile game companion app. It processes game session recordings to detect round transitions (via black screen analysis) and will ultimately produce a lightweight JSON config of discriminating pixels that the mobile app uses for map identification — eliminating any need for OpenCV on mobile.

The project follows a modular CLI pipeline architecture with four planned tools, of which Tool 1 (Black Screen Detector) is complete.

## Architecture Pattern

**Modular CLI Pipeline** — Each tool is an independent CLI entry point that reads from shared configuration and reuses common utility modules. Tools are designed to be run sequentially in a pipeline but are fully decoupled.

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Tool 1    │    │   Tool 2    │    │   Tool 3    │    │   Tool 4    │
│ Black Screen│───>│   Frame     │───>│   Pixel     │───>│ Validation  │
│  Detector   │    │  Labeling   │    │   Finder    │    │  & Testing  │
└──────┬──────┘    └──────┬──────┘    └──────┬──────┘    └──────┬──────┘
       │                  │                  │                  │
       ▼                  ▼                  ▼                  ▼
   PNG frames        Labeled dirs       JSON config      Accuracy report
```

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Video decoding | FFmpeg subprocess (not OpenCV VideoCapture) | OpenCV cannot selectively decode I-frames only |
| Frame processing | Downscale to 360p before analysis | Speed optimization — full resolution unnecessary for detection |
| ROI strategy | Dual-zone check (minimap + map_name) | Full-frame check produces false positives; specific regions are reliable |
| Configuration | External YAML file | All tunable parameters centralized, easily adjustable |
| State machine | Three-state (undetermined / waiting_for_end / waiting_for_start) | Neutral start handles first transition; prevents consecutive end detections |
| Skip logic | 15-second skip after end detection | Avoids duplicate detections from consecutive loading frames |
| Resolution scaling | Reference resolution (1920x1080) with proportional scaling | ROI coordinates defined once, scaled automatically |

## Technology Stack

| Category | Technology | Version | Purpose |
|----------|------------|---------|---------|
| Language | Python 3 | 3.8+ | Implementation language (prototyping speed, good FFmpeg/OpenCV bindings) |
| Computer Vision | OpenCV (`opencv-python`) | >=4.8, <5 | Image processing only: resize, grayscale, ROI extraction, pixel analysis |
| Video Processing | FFmpeg | System dependency | I-frame-only extraction via subprocess — avoids full-frame decoding |
| Array Processing | NumPy | >=1.24, <2 | Frame data manipulation and array operations |
| Configuration | PyYAML | >=6.0, <7 | YAML config file parsing |
| CLI | argparse (stdlib) | Built-in | Command-line argument parsing |

## Module Architecture

### tools/black_screen_detector.py
**Role:** CLI entry point for Tool 1 — black screen detection and frame export.

- Parses CLI arguments (video path, output dir, config path, threshold override)
- Loads YAML config and resolves output directory
- Iterates I-frames via `utils.video.extract_iframes_scaled()`
- Scales ROI coordinates from reference resolution to processing resolution
- Checks all ROI zones and caches per-zone results for state machine logic
- Uses a three-state machine (`undetermined` / `waiting_for_end` / `waiting_for_start`) to track round lifecycle
- Detects game ends (non-black → black): exports previous frame as `end_*.png`
- Detects game starts (black → non-black): exports current frame as `start_*.png`
- Prevents consecutive end detections without an intervening start (filters trailing dead air)
- Applies skip logic after end detections to avoid duplicates
- Prints summary report with start/end breakdown and exported filenames

### utils/video.py
**Role:** FFmpeg subprocess wrapper for I-frame extraction.

- `extract_iframes_scaled(video_path, target_height)` — Generator yielding `(frame, timestamp)` tuples, pre-scaled to target height
- `extract_frame_at_timestamp(video_path, timestamp, width, height)` — Extract a single full-resolution frame at a given timestamp
- `get_video_info(video_path)` — Returns `(width, height)` via ffprobe
- Uses `ffmpeg` with keyframe-only filter (`-skip_frame nokey`) and showinfo filter for timestamp parsing
- Parses raw frame bytes and timestamps from FFmpeg output via stderr reader thread

### utils/image.py (~117 lines)
**Role:** Stateless image processing functions.

- `downscale(frame, target_height)` — Resize preserving aspect ratio, returns scale factor
- `to_grayscale(frame)` — BGR to grayscale conversion via OpenCV
- `scale_roi(roi, scale)` — Scale ROI coordinates from reference to processing resolution
- `extract_roi(frame, roi)` — Extract ROI region with bounds checking and truncation warnings
- `is_black(region, threshold)` — Check if mean pixel value is below brightness threshold

### utils/config.py
**Role:** Shared configuration loading.

- `load_config(config_path)` — Load and return the YAML configuration dict

### config/config.yaml
**Role:** All tunable pipeline parameters.

- Reference resolution: 1920x1080
- Processing resolution: 360p target height
- Brightness threshold: 15 (0-255 scale)
- Skip duration: 15 seconds
- ROI zones: minimap (104,0,38x234) and map_name (827,79,264x22)
- Output settings: default directory, image format

## Data Flow

```
Input Video (MP4)
    │
    ▼
FFmpeg I-frame extraction (utils/video.py)
    │  yields (BGR frame, timestamp) tuples
    ▼
Downscale to 360p (utils/image.py → downscale)
    │
    ▼
Grayscale conversion (utils/image.py → to_grayscale)
    │
    ▼
ROI extraction × 2 zones (utils/image.py → extract_roi)
    │
    ▼
Brightness check per zone (utils/image.py → is_black)
    │
    ├── State: waiting_for_end
    │   ├── All black? YES → END detected: export previous frame as end_*.png
    │   │                     Set state → waiting_for_start, apply 15s skip
    │   └── All black? NO  → Store frame, continue
    │
    └── State: waiting_for_start
        ├── All black? YES → Ignore (still in black region, prevents consecutive ends)
        └── All black? NO  → START detected: export current frame as start_*.png
                              Set state → waiting_for_end
```

## Testing Strategy

No formal test suite exists. The project's validation strategy is built into **Tool 4** (planned), which will serve as both the test harness and accuracy measurement tool:

- **Training set validation:** Confirm 100% accuracy on labeled frames
- **Test set validation:** Measure accuracy on unseen recordings (target: >=95%)
- **Per-map breakdown:** Identify weak discriminating pixels
- **Regression testing:** Re-run after config or game updates

## Robustness Features

- Aspect ratio validation with warning for non-standard source resolutions
- ROI bounds checking with truncation warnings when extraction exceeds frame dimensions
- Sequence counters in filenames prevent collisions when timestamps are identical
- Graceful handling of videos with zero transitions (prints summary, exits cleanly)

## Future Architecture (Tools 2-4)

| Tool | Expected Module | Dependencies | Output |
|------|----------------|--------------|--------|
| Tool 2: Frame Labeler | `tools/frame_labeler.py` | Manual/interactive | Organized folder structure (one per map) |
| Tool 3: Pixel Finder | `tools/pixel_finder.py` | `utils/image.py`, OpenCV, NumPy | JSON config (pixel coords, RGB values, tolerance) |
| Tool 4: Validator | `tools/validator.py` | `utils/video.py`, `utils/image.py` | Accuracy report per map with confidence margins |

All future tools will reuse `utils/video.py` and `utils/image.py`, following the same pattern of standalone CLI entry points in `tools/`.
