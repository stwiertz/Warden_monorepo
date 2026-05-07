# Project Overview — Warden-tooling

> Generated: 2026-02-25 | Scan Level: Quick

## Purpose

Warden-tooling is a desktop video analysis pipeline for **EVA** (a mobile game) session recordings. It serves two critical functions:

1. **Validate detection algorithms** — Black screen detection and map identification are prototyped and validated on desktop before being ported to mobile (React Native / Kotlin). Desktop serves as the reference implementation so mobile failures can be attributed to platform-specific issues rather than logic errors.

2. **Generate the map identification dataset** — A JSON config of discriminating pixels that the mobile app uses for map identification, eliminating the need for OpenCV on mobile devices.

## Project Summary

| Property | Value |
|----------|-------|
| **Project Name** | Warden-tooling |
| **Type** | CLI Toolchain (Python) |
| **Repository** | Monolith (single-part) |
| **Status** | Early-stage — Tool 1 complete, Tools 2-4 planned |
| **Primary Language** | Python 3.8+ |
| **Key Dependencies** | OpenCV, FFmpeg (system), NumPy, PyYAML |
| **Architecture** | Modular CLI Pipeline |
| **Source Code** | ~520 lines across 3 Python modules |

## Tool Pipeline

| # | Tool | Status | Input | Output |
|---|------|--------|-------|--------|
| 1 | Black Screen Detector | **Complete** | Video recording (MP4) | End-of-round frame PNGs |
| 2 | Frame Labeler | Planned | Extracted frames | Organized folders (one per map) |
| 3 | Pixel Finder | Planned | Labeled frames | JSON config (pixel coords, RGB, tolerance) |
| 4 | Validator | Planned | Recordings + ground truth | Accuracy report per map |

## Tech Stack Summary

| Category | Technology | Version |
|----------|------------|---------|
| Language | Python | 3.8+ |
| Computer Vision | OpenCV | >=4.8, <5 |
| Video Processing | FFmpeg | System dependency |
| Array Processing | NumPy | >=1.24, <2 |
| Configuration | PyYAML | >=6.0, <7 |
| CLI | argparse | stdlib |

## Architecture Type

**Modular CLI Pipeline** — Independent CLI tools connected by file-based I/O. Each tool reads inputs, processes them, and writes outputs that the next tool consumes. Shared utility modules (`utils/video.py`, `utils/image.py`) provide common functionality.

## Repository Structure

- `tools/` — CLI entry points (one per tool)
- `utils/` — Shared reusable modules
- `config/` — External YAML configuration
- `source/` — Test video data (git-ignored)
- `docs/` — Generated project documentation

## Success Criteria

- Black screen detection: 100% transition detection with 0 false positives
- Map identification: 100% accuracy on training set, >=95% on unseen test set
- Results reproducible across different sessions and players
- All validated via Tool 4 reports

## Related Documentation

- [Architecture](./architecture.md) — Detailed architecture, module descriptions, data flow
- [Source Tree Analysis](./source-tree-analysis.md) — Directory structure and critical folders
- [Development Guide](./development-guide.md) — Setup, prerequisites, and usage instructions
- [Algorithm Specification](../description.md) — Original algorithm design document
- [Tech Spec — Black Screen Detector](../_bmad-output/implementation-artifacts/tech-spec-black-screen-detector.md) — Detailed implementation spec for Tool 1
