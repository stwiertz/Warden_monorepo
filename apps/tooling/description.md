# Warden — Desktop Analysis Tooling Pipeline

## Context

Before implementing the video analysis pipeline on mobile (React Native / Kotlin), the detection logic must be validated on desktop first. This tool serves two purposes:

1. **Validate the detection algorithms** (black screen detection, map identification) in isolation, so failures on mobile can be attributed to platform-specific issues rather than logic errors.
2. **Generate the map identification dataset** — a JSON config of discriminating pixels that the mobile app will use instead of template matching, eliminating the need for OpenCV on mobile.

## Tool 1 — Black Screen Detector

### Input

- Raw EVA session recordings (video files, up to 2 hours each)

### Process

1. Iterate through I-frames only
2. Downscale each frame (e.g. 270p–360p)
3. Convert to grayscale
4. Apply brightness threshold **only within defined ROI zones** to detect black screens
5. When a black screen is detected, export the **previous I-frame** (the end-of-round screen)

### Black Detection ROI Zones

Not the entire frame goes black during transitions — only specific regions. Checking the full frame would produce false positives. Two ROI zones are used:

- **Top-left corner:** `(x1, y1, x2, y2)` — TODO: fill exact coordinates
- **Bottom-center:** `(x1, y1, x2, y2)` — TODO: fill exact coordinates

Both zones must be black simultaneously to confirm a transition frame. Coordinates are defined at source resolution and scaled proportionally when downscaling.

### Black Screen Grouping

Transitions between rounds produce **multiple consecutive black I-frames** (loading screens between lobby, end game, etc.). Only the **first black I-frame in a sequence** is a valid transition marker. After detecting a black screen:

- Record the transition
- **Skip forward ~15 seconds** of I-frames before resuming detection — there won't be another valid transition during loading
- This reduces both false duplicate detections and total processing time

### Output

- Extracted end-of-round frames as image files, named with their timestamp in the source video

### Notes

- This is the same algorithm that will run on mobile — the desktop version serves as the reference implementation
- Threshold values validated here should transfer directly to mobile

## Tool 2 — Frame Labeling (Manual Step)

### Process

- Organize exported frames into folders, one per map (15 maps currently)
- Each folder should contain multiple frames from different recordings (different scores, players, sessions) to capture variance

### Folder Structure

```
/labeled-frames
  /frostbite
    frame_00032.png
    frame_01245.png
    ...
  /reactor
    frame_00187.png
    frame_00890.png
    ...
  /...
```

### Notes

- More recordings per map = more robust pixel selection
- Should include frames from different session conditions (different teams, scores, results) to ensure selected pixels are independent of game state

## Tool 3 — Discriminating Pixel Finder

### Step 1 — Intra-Map Composite (at full resolution first)

For each map folder:

1. Load all frames at **full source resolution** in RGB
2. Compute per-pixel **mean** and **variance** across all frames in the folder (per channel: R, G, B)
3. Pixels with **low variance** within a map are stable candidates (not affected by scores, player names, dynamic HUD elements)

### Step 2 — HUD Zone Exclusion

- Define a mask of HUD/dynamic zones to exclude from candidate selection
- Only pixels **outside** the HUD are considered, to avoid glow, pulse effects, and game-state-dependent color changes

### Step 3 — Cross-Map Comparison

- Compare the per-pixel means across all 15 map composites
- Select pixels with **high inter-map variance** (maps look different at that pixel) AND **low intra-map variance** (stable within a map)
- Rank candidates by discriminating power

### Step 4 — Resolution and Color Mode Sweep

Starting from full resolution, repeat Steps 1–3 at progressively lower resolutions (e.g. 1080p → 720p → 540p → 360p → 270p) and in both color modes (RGB and grayscale):

- At each combination, re-evaluate discriminating pixel quality (inter-map vs intra-map variance)
- Lower resolutions smooth out compression artifacts and noise — pixels that are unreliable at high res may become more stable at lower res
- RGB provides 3 channels of discrimination (maps with distinct color ambiances — cold blue vs warm orange — are easier to separate). Grayscale reduces to 1 channel but simplifies mobile processing
- Find the **lowest resolution and simplest color mode where discrimination is still 100% reliable** — this is the target configuration for mobile
- It's likely that color (RGB) is needed to reliably distinguish maps with similar brightness but different color palettes

### Step 5 — Pixel Set Selection

- At the chosen resolution, select the minimum set of pixels that reliably distinguishes all 15 maps from each other
- Validate against all labeled frames (at that resolution) to confirm zero misclassifications

### Output

```json
{
  "resolution": { "width": 480, "height": 270 },
  "color_mode": "rgb",
  "maps": {
    "frostbite": [
      { "x": 120, "y": 45, "r": 45, "g": 120, "b": 200, "range": 15 },
      { "x": 200, "y": 80, "r": 180, "g": 60, "b": 30, "range": 10 }
    ],
    "reactor": [
      { "x": 120, "y": 45, "r": 95, "g": 85, "b": 70, "range": 12 },
      { "x": 200, "y": 80, "r": 40, "g": 190, "b": 210, "range": 10 }
    ]
  }
}
```

### Notes

- The `resolution` field is critical — the mobile app must downscale to this exact resolution before checking pixels
- The `color_mode` field indicates whether the mobile app should check RGB values or grayscale — determined by the sweep in Step 4
- `range` defines the acceptable tolerance around the expected values per channel, accounting for compression artifacts and minor variations
- This JSON is the only artifact the mobile app needs for map identification — no templates, no OpenCV

## Tool 4 — Validation & Accuracy Testing

### Purpose

Validate the full pipeline (black screen detection + pixel-based map identification) against both training data and unseen test data to measure accuracy and catch regressions.

### Test Datasets

- **Training set:** The labeled frames from Tool 2 — used during development to confirm the algorithm works on known data
- **Test set:** A separate folder of recordings/frames the pipeline has never seen — used to measure real-world accuracy and detect overfitting to training data

### Test Modes

**Mode A — Full pipeline test (end-to-end)**

Feed raw recordings into the pipeline (Tool 1 black detection → map identification via JSON config) and compare results against manually labeled ground truth:

- Did it detect all transitions? (no missed black screens)
- Did it detect only real transitions? (no false positives)
- Did it correctly identify every map?

**Mode B — Map identification only**

Feed pre-extracted frames directly into the pixel-check algorithm, bypassing black screen detection. Useful for isolating map identification accuracy from detection accuracy.

### Output — Validation Report

```
Resolution: 480x270 | Color mode: RGB | Pixels per map: 6

TRAINING SET (180 frames, 15 maps)
  Black screen detection:  60/60 transitions found, 0 false positives
  Map identification:      180/180 correct (100%)

TEST SET (45 frames, 12 maps represented)
  Black screen detection:  15/15 transitions found, 0 false positives
  Map identification:      44/45 correct (97.8%)
    ✗ frame_02341.png — expected: frostbite, got: aurora (confidence margin: 3)

Per-map accuracy:
  frostbite:   11/12 (91.7%)  ← review discriminating pixels
  reactor:     8/8   (100%)
  ...

Weakest pixel (lowest discrimination margin): pixel(200,80) between frostbite/aurora
```

### Notes

- The test set should include recordings from different players, sessions, and recording conditions to be representative
- If accuracy drops on the test set compared to training, the pixel selection may be overfitting — re-run Tool 3 with more diverse training data
- The confidence margin per pixel helps identify which pixels are close to failing and may need replacement
- This tool should be re-run after every JSON config update and after EVA game updates

## Maintenance Workflow

When EVA releases a new map or updates the UI:

1. Record a few sessions containing the new/updated content
2. Run Tool 1 to extract end-of-round frames
3. Label new frames (Tool 2)
4. Re-run Tool 3 with the updated frame set
5. Run Tool 4 to validate accuracy on both training and test sets
6. Ship updated JSON to mobile (app update or remote config)

## Tech Stack

- **Language:** Python (prototyping speed, good bindings for both FFmpeg and OpenCV)
- **FFmpeg** (via `ffmpeg-python` or subprocess): for video decoding and **I-frame-only extraction** — OpenCV's `VideoCapture` cannot selectively decode only keyframes
- **OpenCV:** for image processing only (resize, color conversion, pixel analysis) — not used for video decoding
- **Output:** JSON config file + validation report (accuracy per map, confidence margins)

## Success Criteria

- Black screen detection matches 100% of round transitions across test recordings with 0 false positives
- Pixel-based map identification achieves 100% accuracy on training set
- Pixel-based map identification achieves ≥95% accuracy on unseen test set (100% target)
- Results are reproducible across recordings from different sessions and players
- All validated via Tool 4 reports