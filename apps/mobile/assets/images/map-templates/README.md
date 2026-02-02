# Map End-Screen Templates

Place EVA After-h map end-screen template images here.

## Format
- Resolution: ~320px wide (must match keyframe extraction resolution)
- Format: JPEG
- Naming: `{map-name}.jpg` (e.g., `ascent.jpg`, `bind.jpg`, `haven.jpg`)

## Usage
These templates are used by the template matcher (`src/features/video-processing/templateMatcher.ts`)
to identify map end screens via OpenCV template matching.

Currently stubbed — real detection will be integrated from an external script.
