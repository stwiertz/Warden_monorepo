# Source Tree Analysis — Warden-tooling

> Generated: 2026-02-25 | Scan Level: Quick | Project Type: CLI Toolchain

## Directory Tree

```
Warden-tooling/
├── config/                          # External configuration (YAML)
│   └── config.yaml                  # All tunable pipeline parameters
├── tools/                           # CLI entry points (one file per tool)
│   ├── __init__.py                  # Package marker
│   └── black_screen_detector.py     # [ENTRY] Tool 1: Black screen detection CLI
├── utils/                           # Shared reusable modules
│   ├── __init__.py                  # Package marker
│   ├── video.py                     # FFmpeg subprocess wrapper, I-frame extraction
│   └── image.py                     # Image processing: resize, grayscale, ROI ops
├── source/                          # Input video data (git-ignored, ~8.9 GB)
├── docs/                            # Generated project documentation
├── _bmad/                           # BMAD Method v6.0.2 framework (managed)
├── _bmad-output/                    # BMAD workflow artifacts
│   ├── implementation-artifacts/
│   │   └── tech-spec-black-screen-detector.md
│   └── project-sprint.md
├── .claude/                         # Claude Code command definitions
├── description.md                   # Algorithm specification & pipeline design
├── requirements.txt                 # Python dependencies (opencv, numpy, pyyaml)
└── .gitignore                       # Excludes source/ and __pycache__/
```

## Critical Folders

| Folder | Purpose | Key Files |
|--------|---------|-----------|
| `tools/` | CLI entry points — each tool is a standalone script with argparse | `black_screen_detector.py` (Tool 1, completed) |
| `utils/` | Shared modules reused across tools — decoupled from CLI logic | `video.py` (FFmpeg), `image.py` (OpenCV ops) |
| `config/` | External YAML configuration — all tunable parameters centralized | `config.yaml` (ROI zones, thresholds, resolution) |
| `source/` | Test video recordings (git-ignored) — large MP4 files for validation | Not tracked in git |

## Entry Points

| Entry Point | Type | Usage |
|-------------|------|-------|
| `tools/black_screen_detector.py` | CLI (argparse) | `python tools/black_screen_detector.py <video> [-o DIR] [-c CONFIG] [--threshold N]` |

## Module Dependencies

```
tools/black_screen_detector.py
  ├── utils/video.py        (FFmpeg I-frame extraction)
  ├── utils/image.py        (downscale, grayscale, ROI, brightness check)
  ├── config/config.yaml    (loaded via PyYAML at runtime)
  └── stdlib: argparse, os, pathlib
```

## Planned Additions (Not Yet Implemented)

| Tool | Expected Location | Purpose |
|------|-------------------|---------|
| Tool 2: Frame Labeler | `tools/frame_labeler.py` | Manual frame organization by map |
| Tool 3: Pixel Finder | `tools/pixel_finder.py` | Discriminating pixel selection for map ID |
| Tool 4: Validator | `tools/validator.py` | Accuracy testing against ground truth |

## File Organization Patterns

- **One tool per file** in `tools/` — each tool is self-contained with its own argparse CLI
- **Stateless utility functions** in `utils/` — no global state, pure function design
- **Config-driven behavior** — all tunable values externalized to `config/config.yaml`
- **Reference resolution scaling** — ROI coordinates defined at 1920x1080, scaled proportionally at runtime
