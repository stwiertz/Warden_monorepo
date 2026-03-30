---
title: 'Minimap Zone Selector Tool'
slug: 'minimap-zone-selector'
created: '2026-03-30'
status: 'review'
stepsCompleted: [1, 2, 3]
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
code_patterns:
  - 'tk.Tk subclass with toolbar + canvas layout (frame_labeler, image_inspector)'
  - 'ImageCanvas reuse from tools/image_inspector/canvas.py'
  - 'HSV center+tolerance pattern from HSVFilterMode (modes.py)'
  - 'extract_roi/scale_roi from utils/image.py'
  - 'yaml.safe_load + yaml.dump preserve-other-keys pattern'
  - 'MAP_LABELS list from frame_labeler.py'
test_patterns:
  - 'No test framework present — manual validation only'
  - 'zone_fires() is a pure function testable with synthetic numpy arrays'
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

- [ ] **T1: Create package skeleton**
  - File: `tools/minimap_zone_selector/__init__.py`
  - Action: Create empty file to make it a package.
  - File: `tools/minimap_zone_selector/__main__.py`
  - Action: `argparse` entry point — `--labeled <dir>` (required), `--config <path>`
    (default `config/config.yaml`). Construct `MinimapZoneSelectorApp`, call
    `mainloop()`. Run with `python -m tools.minimap_zone_selector --labeled <dir>`.

- [ ] **T2: Implement `data_loader.py`**
  - File: `tools/minimap_zone_selector/data_loader.py`
  - Action: Implement `MinimapDataLoader(labeled_dir, minimap_roi_ref, ref_w=1920,
    ref_h=1080)`.
    - On init: scan `<labeled_dir>/<map>/` for each of the 14 `MAP_LABELS` (import
      from `tools.frame_labeler`); load all PNGs as BGR numpy arrays via
      `cv2.imread`; print warning to stderr for missing dirs.
    - `get_frames(map_name) -> list[np.ndarray]` — all full-frame BGR arrays.
    - `get_all_frames() -> dict[str, list[np.ndarray]]` — all maps.
    - `get_reference_image(map_name, index=0) -> PIL.Image | None` — frame at index
      as PIL RGB (for canvas display).
    - `frame_count(map_name) -> int`.
    - `all_map_names() -> list[str]` — maps with ≥1 image found.

- [ ] **T3: Implement `zone_model.py`**
  - File: `tools/minimap_zone_selector/zone_model.py`
  - Action: Define the following dataclasses and helpers.
    ```python
    @dataclass
    class Zone:
        zone_id: str
        x: int; y: int; width: int; height: int  # full-frame ref coords (1920×1080)
        h_center: int; h_tol: int   # user-space: 0–360
        s_center: int; s_tol: int   # user-space: 0–100
        v_center: int; v_tol: int   # user-space: 0–100
        min_ratio: float
        weight: float
        weight_override: bool

    @dataclass
    class MinimapConfig:
        id: str
        roi: dict                          # {name, x, y, width, height} ref coords
        identification_threshold: float
        maps: dict[str, list[Zone]]        # map_label -> zones
    ```
    - `zone_fires(zone, bgr_frame, ref_w=1920, ref_h=1080) -> bool`:
      1. Compute `scale = frame_w / ref_w` (use `frame.shape[1]`).
      2. Build scaled ROI dict: `scale_roi({...zone coords...}, scale)`.
      3. `region = extract_roi(bgr_frame, scaled_roi)`.
      4. Convert region to HSV with `cv2.cvtColor(region, cv2.COLOR_BGR2HSV)`.
      5. Convert user-space HSV to OpenCV scale (reuse `_H_USER_TO_CV`,
         `_SV_USER_TO_CV` constants from `image_inspector/modes.py`).
      6. Build mask via `cv2.inRange`; handle hue wraparound same as
         `HSVFilterMode._apply` (split into two ranges when `h_lo < 0` or
         `h_hi > 179`).
      7. Return `np.count_nonzero(mask) / mask.size >= zone.min_ratio`.
  - Notes: Import `extract_roi`, `scale_roi` from `utils.image`.

- [ ] **T4: Implement `validator.py`**
  - File: `tools/minimap_zone_selector/validator.py`
  - Action: Implement the following dataclasses and validator.
    ```python
    @dataclass
    class ZoneStats:
        tp_rate: float      # fraction of same-map frames where zone fires
        fp_rate: float      # fraction of all other-map frames where zone fires
        auto_weight: float  # tp_rate × (1 − max FP rate across any single other map)

    @dataclass
    class MapStats:
        accuracy: float              # fraction of same-map frames correctly identified
        coverage_sim_accuracy: float # worst-case accuracy with one zone knocked out

    @dataclass
    class ValidationResult:
        zone_stats: dict[str, ZoneStats]  # keyed by zone_id
        map_stats: dict[str, MapStats]
        overall_accuracy: float           # mean of per-map accuracies
    ```
    - `ZoneValidator.compute(config: MinimapConfig, loader: MinimapDataLoader)
      -> ValidationResult`:
      1. Pre-compute `zone_fires()` results for every (zone, frame) pair.
      2. Per zone: `tp_rate` = fires on same-map / total same-map; per other map
         compute fp_rate; `auto_weight = tp_rate × (1 − max_other_fp_rate)`.
      3. Per map per frame: sum `zone.weight` for zones that fire → correct if
         sum ≥ `config.identification_threshold`.
      4. Coverage sim: for each map, for each zone index i, recompute per-frame
         accuracy excluding zone i; `coverage_sim_accuracy = min over all i`.
      5. `overall_accuracy = mean(map_stats[m].accuracy for all m)`.

- [ ] **T5: Implement `config_manager.py`**
  - File: `tools/minimap_zone_selector/config_manager.py`
  - Action: Implement `ConfigManager(config_path: str)`.
    - `load() -> list[MinimapConfig]` — `yaml.safe_load`; read
      `minimap_identification.configs`; deserialise each entry into `MinimapConfig`
      (zones as `Zone` dataclasses); return `[]` if key absent.
    - `save(configs: list[MinimapConfig])` — load full YAML dict, set
      `data['minimap_identification']['configs']` to serialised list, write with
      `yaml.dump(..., default_flow_style=False, allow_unicode=True)`. Preserves all
      other top-level keys.
    - `upsert(config: MinimapConfig)` — replace entry with matching `id` or append.
    - `delete(config_id: str)` — remove entry by id; no-op if not found.
    - `clone(src_id: str, new_id: str) -> MinimapConfig` — deep copy src config,
      set `id = new_id`, return without saving.

- [ ] **T6: Implement `hsv_editor.py`**
  - File: `tools/minimap_zone_selector/hsv_editor.py`
  - Action: Implement `HSVEditor(parent, on_change: Callable[[Zone], None])`.
    - Build inline `tk.LabelFrame` with grid of entry widgets matching
      `HSVFilterMode._build_ui`: rows for center and ± tolerance for H, S, V; plus
      a `min_ratio` entry and a `weight` display (read-only, shows auto or manual
      value).
    - `load_zone(zone: Zone)` — populate all fields from zone.
    - `[Apply]` button: validate ranges (H 0–360, S/V 0–100, tols ≥ 0,
      min_ratio 0–1); call `on_change(updated_zone)`.
    - Shows `"(manual)"` label next to weight when `weight_override=True`.

- [ ] **T7: Implement `stats_panel.py`**
  - File: `tools/minimap_zone_selector/stats_panel.py`
  - Action: Implement `StatsPanel(parent, on_delete_zone, on_weight_override_change)`.
    - Overall accuracy label at top: `"Overall: {x:.1f}%"`.
    - Zone list (`tk.Frame` with scrollbar): one row per zone showing
      `zone_id | TP% | FP% | weight | Override ☐ | weight entry | [Delete]`.
    - Map accuracy table (`tk.Frame`): columns `Map | Accuracy% | Coverage Sim%`;
      highlight rows where accuracy < 100% in red.
    - `update(result: ValidationResult, config: MinimapConfig, selected_map: str)`
      — rebuild zone list for `selected_map` and refresh full map table.

- [ ] **T8: Implement `app.py`**
  - File: `tools/minimap_zone_selector/app.py`
  - Action: Implement `MinimapZoneSelectorApp(tk.Tk)`.
    - **Toolbar (top):** `ttk.Combobox` version selector (populated from
      `ConfigManager.load()`); `[New]` `[Clone]` `[Delete]` version buttons;
      separator; `ttk.Combobox` map selector; `[Export]` button.
    - **Left panel:** `ImageCanvas` (imported from
      `tools.image_inspector.canvas`) showing minimap crop (`get_reference_image`)
      for the selected map; `[◀]` `[▶]` buttons to step through all images for that
      map (updates canvas only — does not affect zone data). Zone overlays as colored
      rectangles cycling `["cyan","lime","magenta","yellow","orange","red"]`.
    - **Right panel:** `StatsPanel` (top portion, expandable); `HSVEditor` (bottom
      portion, shown when a zone is selected in the zone list).
    - **Zone drawing:** bind `<ButtonPress-1>`, `<B1-Motion>`,
      `<ButtonRelease-1>` on `ImageCanvas`. On release: convert canvas coords →
      image-crop coords → full-frame ref coords (add minimap ROI x/y offset, scale
      to 1920×1080). Create `Zone` with defaults `(H:0±180, S:0±12, V:100±15,
      min_ratio:0.3, weight:0.0, weight_override:False)`, auto-assign
      `zone_id = f"zone_{n}"`. Append to active config's zone list for selected map.
      Trigger revalidation.
    - **Revalidation:** after every zone add/modify/delete: call
      `ZoneValidator.compute(config, loader)`, update `auto_weight` on all
      non-override zones, call `stats_panel.update(result, config, selected_map)`.
    - **Export:** `ConfigManager.upsert(active_config)` then `ConfigManager.save(configs)`.
    - **Version CRUD:**
      - `[New]` → prompt for id via `simpledialog.askstring`; create empty
        `MinimapConfig` with default ROI from config file.
      - `[Clone]` → prompt for new id; call `ConfigManager.clone(src_id, new_id)`;
        add to in-memory list; refresh combobox.
      - `[Delete]` → confirm via `messagebox.askyesno`; remove from list; refresh.

### Acceptance Criteria

- [ ] **AC1 — Zone drawing:** Given the minimap canvas is loaded with a reference
  image, when the user click-drags a rectangle on the canvas, then a new `Zone` is
  appended to the selected map's zone list with `x`, `y`, `width`, `height` correctly
  translated to full-frame reference resolution (1920×1080); a colored overlay
  rectangle appears on the canvas.

- [ ] **AC2 — HSV edit + live update:** Given a zone exists and is selected in the
  zone list, when the user modifies any HSV parameter in `HSVEditor` and clicks Apply,
  then `ZoneValidator.compute()` runs, `auto_weight` is recalculated, and the stats
  panel reflects updated TP%, FP%, and weight values.

- [ ] **AC3 — Auto weight formula:** Given a zone fires on 100% of same-map images
  and 0% of all other-map images, then `auto_weight` = 1.0, displayed without
  "(manual)". Given a zone fires on 80% of same-map and 10% worst-other-map images,
  then `auto_weight` = `0.80 × (1 − 0.10)` = 0.72.

- [ ] **AC4 — Manual weight override:** Given `weight_override=False`, when the user
  checks Override and enters 0.9 in the weight entry, then the zone's weight is 0.9
  in all validations and the stats panel shows "(manual)" beside it. Given
  `weight_override=True`, when the user unchecks Override, then the weight immediately
  reverts to the current `auto_weight` value.

- [ ] **AC5 — Coverage simulation:** Given map "horizon" has 3 zones with effective
  weights [0.8, 0.5, 0.3] and `identification_threshold=0.6`, when coverage sim runs,
  then for each single-zone knockout the remaining weighted sum is computed; the
  `coverage_sim_accuracy` reflects the worst-case scenario across all knockouts.

- [ ] **AC6 — Config versioning — new:** Given no `minimap_identification` key in
  `config.yaml`, when user clicks `[New]`, enters id "v1.0", and clicks `[Export]`,
  then `config.yaml` contains a valid `minimap_identification.configs` list with one
  entry where `id = "v1.0"` and all other sections are untouched.

- [ ] **AC7 — Config versioning — clone:** Given config "v1.0" exists with zones,
  when user clicks `[Clone]` and enters "v1.5_hud", then a new config "v1.5_hud" is
  created as a deep copy of "v1.0"; subsequently editing zones in "v1.5_hud" does not
  alter "v1.0".

- [ ] **AC8 — Export preserves other sections:** Given `config.yaml` contains
  `black_detection`, `map_identification`, and other sections, when the user exports,
  then all other top-level keys remain byte-for-byte equivalent and the file is valid
  YAML.

- [ ] **AC9 — Multi-image validation:** Given a map folder contains 5 images,
  when `ZoneValidator.compute()` runs, then all 5 images are included in the TP/FP
  computation — not only the first one.

- [ ] **AC10 — Missing map folder:** Given the labeled dir has no subfolder for
  "lunar_outpost", when the tool starts, then a warning is printed to stderr, all
  other 13 maps load normally, and "lunar_outpost (no images)" appears in the map
  selector but cannot have zones drawn for it.

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
