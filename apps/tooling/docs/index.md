# Warden-tooling — Project Documentation Index

> Generated: 2026-02-25 | Mode: Initial Scan | Scan Level: Quick

## Project Overview

- **Type:** Monolith (single-part CLI toolchain)
- **Primary Language:** Python 3.8+
- **Architecture:** Modular CLI Pipeline
- **Status:** Early-stage — Tool 1 (Black Screen Detector) complete; Tools 2-4 planned

## Quick Reference

- **Tech Stack:** Python 3, OpenCV >=4.8, FFmpeg (system), NumPy >=1.24, PyYAML >=6.0
- **Entry Point:** `python tools/black_screen_detector.py <video> [-o DIR] [-c CONFIG] [--threshold N]`
- **Architecture Pattern:** Independent CLI tools connected by file-based I/O with shared utilities
- **Configuration:** `config/config.yaml` (all tunable parameters centralized)

## Generated Documentation

- [Project Overview](./project-overview.md) — Purpose, pipeline summary, tech stack, success criteria
- [Architecture](./architecture.md) — Module architecture, design decisions, data flow, robustness features
- [Source Tree Analysis](./source-tree-analysis.md) — Directory structure, critical folders, entry points, module dependencies
- [Development Guide](./development-guide.md) — Prerequisites, installation, configuration, running tools, conventions

## Existing Project Documentation

- [Algorithm Specification](../description.md) — Original pipeline design document with all 4 tools described
- [Tech Spec — Black Screen Detector](../_bmad-output/implementation-artifacts/tech-spec-black-screen-detector.md) — Detailed implementation spec for Tool 1 with acceptance criteria
- [Project Sprint](../_bmad-output/project-sprint.md) — Sprint planning and decision log

## Getting Started

### Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Ensure FFmpeg is on your PATH
ffmpeg -version

# 3. Run the black screen detector on a video
python tools/black_screen_detector.py source/astera.mp4 -o ./output/
```

### For New Tool Development

1. Review the [Architecture](./architecture.md) for module structure and design patterns
2. Read the [Algorithm Specification](../description.md) for the full pipeline design
3. Follow conventions in the [Development Guide](./development-guide.md) for adding new tools
4. Reuse `utils/video.py` and `utils/image.py` for common operations

## AI-Assisted Development Guidance

When using AI to develop new features or tools for this project:

1. **Provide this index** as the primary context entry point
2. **Reference the architecture doc** for understanding module boundaries and data flow
3. **Use the algorithm specification** (`description.md`) for detailed requirements of Tools 2-4
4. **Follow existing patterns** — new tools should mirror the structure of `black_screen_detector.py`
5. **Configuration-first** — add new parameters to `config/config.yaml` rather than hardcoding values

### Key Context for AI Agents

- This is a **desktop reference implementation** — the algorithms will be ported to mobile (React Native / Kotlin)
- The **JSON config output** from Tool 3 is the primary deliverable for mobile consumption
- **OpenCV is used for image processing only** — video decoding is handled by FFmpeg subprocess
- **I-frame-only processing** is a deliberate performance optimization
