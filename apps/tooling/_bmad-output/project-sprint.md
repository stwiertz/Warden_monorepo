# Warden Desktop Pipeline — Sprint Tracker

## Goal

Validate video analysis algorithms on desktop and generate the map identification JSON config that the mobile app will consume. This tool is a prerequisite to the React Native / Kotlin mobile implementation.

## Tech Stack

- Python 3 | FFmpeg (I-frame extraction) | OpenCV (image processing only)
- Output: JSON config + validation reports
- No UI — CLI tools only

## Pipeline Overview

Tools are sequential. Each tool's output feeds the next.

```
[Tool 1: Black Screen Detector] → extracted frames
        ↓
[Tool 2: Frame Labeling]        → organized labeled folders (manual)
        ↓
[Tool 3: Pixel Finder]          → map-identification JSON config
        ↓
[Tool 4: Validation]            → accuracy reports
```

## Sprint Items

| #  | Tool                         | Status      | Quick-Spec | Notes |
|----|------------------------------|-------------|------------|-------|
| 1  | Black Screen Detector        | Not Started | —          | I-frame iteration, ROI-based black detection, 15s skip logic. Reference impl for mobile. |
| 2  | Frame Labeling (manual step) | Not Started | —          | Manual folder organization. May only need a helper script or instructions, not a full tool. |
| 3  | Discriminating Pixel Finder  | Not Started | —          | Intra-map compositing, cross-map comparison, resolution sweep, pixel set selection. Most complex tool. |
| 4  | Validation & Accuracy Testing| Not Started | —          | End-to-end and map-ID-only modes. Generates accuracy reports. |

## Shared Decisions

Decisions made during development that affect multiple tools. Update as specs are created.

| Decision                  | Value       | Decided In |
|---------------------------|-------------|------------|
| Source video resolution   | TBD         | Tool 1     |
| Target downscale res      | TBD         | Tool 3     |
| Color mode (RGB/gray)     | TBD         | Tool 3     |
| Black detection ROI zones | TBD         | Tool 1     |
| HUD exclusion mask        | TBD         | Tool 3     |
| Brightness threshold      | TBD         | Tool 1     |
| Skip duration after black | ~15s        | Tool 1     |

## Success Criteria

- [ ] Black screen detection: 100% transitions, 0 false positives
- [ ] Map ID: 100% accuracy on training set
- [ ] Map ID: >=95% accuracy on unseen test set (target 100%)
- [ ] Results reproducible across sessions and players
- [ ] All validated via Tool 4 reports

## How to Use This Document

When creating a quick-spec for any tool above:
1. Reference this file for overall context and where the tool fits in the pipeline
2. Check **Shared Decisions** for any values already locked in by prior tools
3. After completing a spec or implementation, update the **Status** column and fill in any new shared decisions
