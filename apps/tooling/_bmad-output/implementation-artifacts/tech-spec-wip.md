---
title: 'Minimap Zone Selector Tool'
slug: 'minimap-zone-selector'
created: '2026-03-30'
status: 'in-progress'
stepsCompleted: [1, 2]
tech_stack: ['Python 3.8+', 'Tkinter', 'PIL/Pillow', 'OpenCV 4.8+', 'NumPy', 'PyYAML']
files_to_modify:
  - config/config.yaml
files_to_create:
  - tools/minimap_zone_selector/__init__.py
  - tools/minimap_zone_selector/__main__.py
  - tools/minimap_zone_selector/app.py
  - tools/minimap_zone_selector/data_loader.py
  - tools/minimap_zone_selector/zone_model.py
  - tools/minimap_zone_selector/validator.py
  - tools/minimap_zone_selector/config_manager.py
  - tools/minimap_zone_selector/hsv_editor.py
  - tools/minimap_zone_selector/stats_panel.py
code_patterns: []
test_patterns: []
---

# Tech-Spec: Minimap Zone Selector Tool

**Created:** 2026-03-30

---

## Overview

### Problem Statement

The current map identification method uses a 64-bit perceptual hash (pHash) of the
map-name text ROI (`x:827, y:79, w:264, h:22`). This is unreliable in practice.
The minimap (top-left HUD element) displays a unique structural layout per map —
walls, terrain, furniture, trees — that is stable across game sessions and does not
depend on text rendering.

### Solution

An interactive Tkinter + PIL + OpenCV GUI tool (`tools/minimap_zone_selector/`) that
lets the developer:

1. Draw rectangular zones on the minimap over structurally stable features (walls,
   terrain — not player positions).
2. Define an HSV color range + tolerance per zone to handle compression artifacts.
3. Validate each zone against **all** labeled images for every map, measuring true
   positive rate (same-map images) and false positive rate (other-map images).
4. Auto-compute a confidence weight per zone from those stats, with manual override.
5. Iteratively add zones until 100% identification accuracy is reached.
6. Store zone sets under **named config versions** in `config.yaml` so that HUD
   updates or map reworks can be tracked without losing prior working configs.

### Scope

**In Scope:**

- Tkinter + PIL + OpenCV GUI following `image_inspector` / `frame_labeler` patterns
- Config version manager: create, clone, rename, delete named configs
- Load **all** labeled images per map from `<labeled-dir>/<map>/` (start + end frames)
- Zoomed minimap canvas using the existing `ImageCanvas` widget for zone drawing
- Per-zone HSV editor: H/S/V center + tolerance (same approach as `HSVFilterMode`)
- Zone match rule: `pixels_in_hsv_range / total_zone_pixels >= min_ratio`
- Auto-computed weight per zone: `TP_rate × (1 − max_FP_rate_across_maps)`
- Manual weight override slider per zone
- Live validation panel: per-zone TP%, FP%, weight; overall accuracy table per map
- Coverage simulation: knock out one zone at a time, report worst-case accuracy
- Identification logic: `sum(weight_i for zones_i that fire) >= identification_threshold`
- Export: write active config into `minimap_identification.configs[]` in `config.yaml`

**Out of Scope:**

- Runtime map identifier (config-generation tool only)
- Automatic / computer-vision zone discovery
- Player dot color masking / exclusion
- Multi-image averaging per map for zone parameter tuning

---

## Context for Development

### Codebase Patterns

- **GUI pattern:** `tk.Tk` subclass with toolbar frame + main canvas area, as in
  `tools/frame_labeler.py` and `tools/image_inspector/app.py`.
- **Canvas widget:** `tools/image_inspector/canvas.py` — `ImageCanvas(tk.Canvas)`
  supports zoom/pan, `canvas_to_image()` / `image_to_canvas()` coordinate conversion,
  `set_overlay_redraw(cb)` for persistent overlays. **Reuse directly.**
- **HSV filter pattern:** `tools/image_inspector/modes.py` — `HSVFilterMode` uses
  H center (0–360) ± tolerance, S center (0–100) ± tolerance, V center (0–100) ±
  tolerance. Converts to OpenCV scale internally (`H×179/360`, `S/V×255/100`).
  Handles hue wraparound with two-range `cv2.inRange`. **Replicate this pattern.**
- **ROI utilities:** `utils/image.py` — `extract_roi(frame, roi)`, `scale_roi(roi,
  scale_factor)`. Use for cropping zone regions during validation.
- **Config I/O:** Load with `yaml.safe_load`, write with `yaml.dump(...,
  default_flow_style=False, allow_unicode=True)`. Existing tools read config at
  startup; this tool also writes back.
- **Map labels:** 14 maps defined in `tools/frame_labeler.py`:
  `horizon, engine, outlaw, ceres, artefact, silva, bastion, polaris, coliseum,
  the_cliff, helios, atlantis, the_rock, lunar_outpost`
- **Labeled folder structure** (output of `frame_labeler.py`):
  `<labeled-dir>/<map_label>/*.png` — one subdirectory per map, any number of PNGs.
- **HSV scale:** All user-facing values stored and displayed in user space
  (H: 0–360, S: 0–100, V: 0–100). Converted to OpenCV space only during pixel
  operations. Store user-space values in config.yaml.

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `tools/image_inspector/canvas.py` | Reuse `ImageCanvas` for minimap display + zone overlays |
| `tools/image_inspector/modes.py` | Replicate `HSVFilterMode` HSV input pattern and hue-wraparound logic |
| `tools/frame_labeler.py` | Source of `MAP_LABELS` list; labeled folder convention |
| `utils/image.py` | `extract_roi()`, `scale_roi()` for zone pixel extraction during validation |
| `config/config.yaml` | Target file; add `minimap_identification:` section |

### Technical Decisions

- **Zone coordinates** are stored in **full-frame reference resolution (1920×1080)**,
  consistent with all other ROI definitions in `config.yaml`. The canvas displays only
  the minimap crop, so coordinate conversion adds the minimap ROI offset before
  scaling to reference resolution.
- **Validation is eager:** recomputes on every zone add/modify/delete. With ~14 maps
  × ~10 images × ~10 zones this is fast enough for synchronous execution.
- **Weight auto-formula:** `w = TP_rate × (1 − max_FP_rate)` where `max_FP_rate` is
  the highest FP rate across all other maps. A zone that fires on 100% of same-map
  images and 0% of other-map images gets weight 1.0.
- **Coverage simulation:** for each map, for each zone of that map, compute weighted
  sum of remaining zones. Report the fraction of same-map images still correctly
  identified. Worst-case (minimum) across all single-zone knockouts is the sim score.
- **Config versioning:** `minimap_identification.configs` is a YAML list. Each entry
  has a unique `id` string. The tool reads all entries on load; the active config is
  selected via a dropdown. Export adds or replaces the entry matching the active `id`.

---

## Config Output Format

```yaml
minimap_identification:
  configs:
    - id: "v1.0"
      roi:
        name: minimap
        x: 104
        y: 0
        width: 234
        height: 264
      identification_threshold: 0.6
      maps:
        horizon:
          zones:
            - id: zone_0
              x: 130        # full-frame reference coords (1920×1080)
              y: 45
              width: 25
              height: 20
              hsv:
                h_center: 0
                h_tol: 180
                s_center: 0
                s_tol: 12
                v_center: 100
                v_tol: 15
              min_ratio: 0.30
              weight: 0.85        # auto-computed unless weight_override: true
              weight_override: false
        engine:
          zones: []
```

---

## Implementation Plan

### Tasks (dependency order — lowest level first)

**T1 — Package skeleton**
- Create `tools/minimap_zone_selector/__init__.py` (empty)
- Create `tools/minimap_zone_selector/__main__.py`: parse args, construct app, call
  `mainloop()`. CLI: `python -m tools.minimap_zone_selector --labeled <dir>
  [--config <path>]` (config default: `config/config.yaml`)

**T2 — `data_loader.py`**
- `MinimapDataLoader(labeled_dir, minimap_roi_ref, ref_w=1920, ref_h=1080)`
- On init: scan `<labeled_dir>/<map>/` for each label in `MAP_LABELS`; load all PNGs
  as BGR numpy arrays via `cv2.imread`; skip missing map dirs with a warning.
- `get_frames(map_name) -> list[np.ndarray]` — all full-frame BGR arrays for that map
- `get_minimap_crops(map_name) -> list[np.ndarray]` — each frame cropped to minimap
  ROI (scaled to frame resolution with `scale_roi`)
- `get_reference_image(map_name) -> PIL.Image | None` — first image as PIL RGB, for
  canvas display
- `all_map_names() -> list[str]` — maps with ≥1 image found

**T3 — `zone_model.py`**
- `Zone` dataclass:
  ```python
  @dataclass
  class Zone:
      zone_id: str
      x: int; y: int; width: int; height: int  # full-frame ref coords
      h_center: int; h_tol: int   # 0–360
      s_center: int; s_tol: int   # 0–100
      v_center: int; v_tol: int   # 0–100
      min_ratio: float
      weight: float               # auto-computed or manual
      weight_override: bool
  ```
- `zone_fires(zone, bgr_frame, frame_w, frame_h, ref_w=1920, ref_h=1080) -> bool`:
  1. Scale zone coords to frame resolution
  2. `extract_roi(bgr_frame, scaled_zone)`
  3. Convert region to HSV; build mask via `cv2.inRange` (with hue wraparound)
  4. Return `mask.sum() / mask.size >= zone.min_ratio`
- `MinimapConfig` dataclass: `id`, `roi` (dict), `identification_threshold` (float),
  `maps` (dict[str, list[Zone]])

**T4 — `validator.py`**
- `ZoneStats` dataclass: `tp_rate`, `fp_rate`, `auto_weight`
- `MapStats` dataclass: `accuracy` (fraction of images correctly identified),
  `coverage_sim_accuracy` (worst-case with one zone knocked out)
- `ValidationResult` dataclass: `zone_stats: dict[str, ZoneStats]` (keyed by
  `zone_id`), `map_stats: dict[str, MapStats]`, `overall_accuracy: float`
- `ZoneValidator.compute(config: MinimapConfig, loader: MinimapDataLoader)
  -> ValidationResult`:
  1. For each zone of each map: compute TP rate over same-map frames; FP rate over
     all other-map frames combined; auto_weight = TP × (1 − max_FP_per_other_map)
  2. For each frame of each map: sum weights of firing zones → compare to threshold
     → correct if sum >= threshold. `map_stats[m].accuracy` = fraction correct.
  3. Coverage sim: for each map, for each zone index i, recompute accuracy with
     zone i removed. `coverage_sim_accuracy` = min over all i.
  4. `overall_accuracy` = mean of all per-map accuracies.

**T5 — `config_manager.py`**
- `ConfigManager(config_path)`
- `load() -> list[MinimapConfig]` — parse `minimap_identification.configs` list;
  return empty list if key absent
- `save(configs: list[MinimapConfig])` — load full YAML, replace
  `minimap_identification.configs`, write back preserving all other keys
- `get_config(id) -> MinimapConfig | None`
- `upsert(config: MinimapConfig)` — add if new id, replace if existing
- `delete(id)` — remove by id
- `clone(src_id, new_id) -> MinimapConfig` — deep copy with new id

**T6 — `hsv_editor.py`**
- `HSVEditor(parent, zone: Zone, on_change: Callable[[Zone], None])`
- Inline `tk.Frame` with entry widgets for H center/tol, S center/tol, V center/tol,
  min_ratio (replicating `HSVFilterMode._build_ui` layout)
- "Apply" button calls `on_change` with updated zone; validates ranges before firing
- `load_zone(zone)` — populate fields from existing zone

**T7 — `stats_panel.py`**
- `StatsPanel(parent)` — right-side `tk.Frame` with scrollable zone list + accuracy table
- `update(result: ValidationResult, config: MinimapConfig, selected_map: str)`:
  - Zone list rows: zone_id | TP% | FP% | weight | `[Override]` checkbox +
    entry | `[Delete]` button
  - Map accuracy table: map name | accuracy% | coverage sim%
  - Overall accuracy label at top
- Callbacks: `on_delete_zone`, `on_weight_override_change`

**T8 — `app.py`**
- `MinimapZoneSelectorApp(tk.Tk)`:
  - **Toolbar:** version selector `ttk.Combobox` + `[New]` `[Clone]` `[Delete]`
    buttons; map selector `ttk.Combobox`; `[Export]` button
  - **Left panel:** `ImageCanvas` loaded with minimap crop of first reference image
    for selected map; zone overlays drawn as colored rectangles (cycling colors,
    same as `ROIMode._COLORS`); `[Browse ◀ ▶]` buttons to step through reference
    images for the current map
  - **Right panel:** `StatsPanel`; `HSVEditor` below zone list (updates when zone
    selected in list)
  - Zone drawing: `<ButtonPress-1>` / `<B1-Motion>` / `<ButtonRelease-1>` on canvas
    → compute ref coords (canvas → image → add minimap ROI offset → scale to 1920×1080)
    → create `Zone` with defaults (H:0±180, S:0±12, V:100±15, min_ratio:0.3,
    weight:0.0, weight_override:False) → append to active config's zone list for
    selected map → revalidate → refresh stats panel
  - After any zone change: call `ZoneValidator.compute(...)`, update `StatsPanel`,
    update auto-weights on zones where `weight_override=False`
  - `[Export]` → `ConfigManager.upsert(active_config)` → `ConfigManager.save()`

### Acceptance Criteria

**AC1 — Zone drawing**
- *Given* the minimap canvas is loaded, *when* the user click-drags a rectangle,
  *then* a new zone is added to the current map with coordinates correctly translated
  to full-frame reference resolution (1920×1080); a colored overlay rectangle appears.

**AC2 — HSV edit + live update**
- *Given* a zone exists, *when* the user changes any HSV parameter and clicks Apply,
  *then* validation recomputes and the stats panel refreshes (TP%, FP%, weight updated).

**AC3 — Auto weight**
- *Given* a zone fires on 100% of same-map images and 0% of other-map images,
  *then* `auto_weight` = 1.0 and is displayed without "(manual)" indicator.
- *Given* a zone fires on 80% of same-map images and 10% of worst other-map,
  *then* `auto_weight` = 0.80 × (1 − 0.10) = 0.72.

**AC4 — Manual weight override**
- *Given* `weight_override=False`, *when* user checks Override and sets weight=0.9,
  *then* the zone uses 0.9 in all subsequent validations regardless of TP/FP stats;
  the stats panel shows "(manual)" next to the weight value.
- *Given* `weight_override=True`, *when* user unchecks Override,
  *then* weight reverts to the auto-computed value immediately.

**AC5 — Coverage simulation**
- *Given* map "horizon" has 3 zones with effective weights [0.8, 0.5, 0.3] and
  threshold=0.6, *when* coverage sim runs, *then* knocking out zone_0 (0.8) leaves
  sum=0.8 which still ≥ 0.6 so accuracy holds; the sim reports this correctly.

**AC6 — Config versioning**
- *Given* no existing `minimap_identification` in config.yaml, *when* user clicks New,
  enters id "v1.0", and exports, *then* `config.yaml` gains a valid
  `minimap_identification.configs` list with one entry id="v1.0".
- *Given* "v1.0" exists with zones, *when* user clicks Clone and enters "v1.5_hud",
  *then* a new config "v1.5_hud" is created as a deep copy; editing its zones does
  not affect "v1.0".

**AC7 — Export preserves config**
- *Given* a config.yaml with existing `black_detection`, `map_identification`, and
  other sections, *when* the user exports, *then* all other sections are unchanged
  and the file remains valid YAML.

**AC8 — Multi-image validation**
- *Given* a map folder has 5 images (e.g. 3 start frames, 2 end frames),
  *when* validation runs, *then* all 5 images are used for TP/FP computation —
  not just the first one.

**AC9 — Missing map folder**
- *Given* the labeled dir has no subfolder for map "lunar_outpost",
  *when* the tool starts, *then* a warning is printed to stderr; all other maps load
  normally; "lunar_outpost" appears in the map selector with a "(no images)" label.

---

## Additional Context

### Dependencies

No new packages required. All dependencies already in `requirements.txt`:
`opencv-python`, `pyyaml`, `numpy`. Tkinter and PIL/Pillow are used by existing tools
(`frame_labeler.py`, `image_inspector/`). Add `Pillow>=9.0` to `requirements.txt` if
not already pinned (it is an implicit dep of `imagehash`).

### Testing Strategy

Manual validation via the tool itself — load a labeled directory with known images,
draw zones, verify TP/FP numbers match expected values by visual inspection.
Unit-testable components: `zone_fires()` in `zone_model.py` (pure function, testable
with synthetic numpy arrays), `ZoneValidator.compute()` (testable with mock loader).

### Notes

- Zone coordinates in the canvas are in **minimap-crop image space**. The conversion
  to full-frame reference coords is:
  `ref_x = round((crop_x + roi['x']) * (1920 / frame_w))`
  `ref_y = round((crop_y + roi['y']) * (1080 / frame_h))`
- The minimap ROI stored in the config (`x:104, y:0, w:234, h:264`) is the full
  gameplay minimap. The `black_detection.roi_zones` entries named `minimap` and
  `vertical` cover only slices of this area (for black-screen detection); they are
  separate and unrelated.
- First default HSV values for a new zone (H:0±180, S:0±12, V:100±15, min_ratio:0.3)
  target near-white pixels (walls, bright terrain lines). The user is expected to
  refine these using the HSV editor after drawing.
