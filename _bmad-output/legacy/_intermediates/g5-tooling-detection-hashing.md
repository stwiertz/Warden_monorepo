## Subsystem Role
- Tooling-app subsystem (Python CLI under `apps/tooling`) that turns a recorded gameplay video into structured per-round data: detect game-state transitions (start/end), capture score screen frames, identify which map was played by perceptual-hashing a HUD ROI against reference hashes
- Pipeline scope here = round boundary detection + per-round map identification; downstream tools consume the labeled frames + `map_config.json`
- Game targeted: EVA / Valorant-style FPS; 14 maps currently labelled (15 listed elsewhere — discrepancy unresolved)
- Two cooperating CLI tool families: (1) game_detector (round boundary + score capture), (2) hash workflow tools 3/4 + warden_analyzer (map identification + accuracy validation)

## Hybrid Game Detector (round boundaries + score capture)
- Tool: `tools/game_detector.py` — supersedes `points_state_detector.py` and `black_screen_detector.py` (kept as fallback/reference; eventual move to `tools/legacy/` deferred)
- Approach: white-pixel detection on a HUD text ROI to drive a 2-state machine (`not_in_game` / `in_game`); on confirmed end transition, queue a score-screen frame extraction at fixed offset
- Replaces team-bar prescan + black-screen detection (dropped — superseded by points/KDA white detection)
- State machine: `start_confirm_count` (2 frames) and `end_confirm_count` (3 frames) filter transient flicker; same machine kept across all detector iterations, only the input signal changed
- Score screen capture: extract a full-resolution I-frame at `last_in_game_timestamp + score_offset` (default 14.5s); rationale = last in-game I-frame can lag actual end by up to ~9s GOP, then 5s team-only screen; 14.5s lands inside the 10s individual+team score window
- Output: `MMmSSs_type_seq.png` PNGs (type ∈ start/end/score) into a video-named subdir under output dir; shared `format_timestamp()` extracted to `utils/format.py` to remove triple-duplication
- CLI surface: positional video, `-o` output, `-c` config, `--profile` timing breakdown; no `--roi` (ROI hardcoded to HUD KDA region)
- Edge cases handled: video that ends mid-game (warn, no score export), score timestamp past end-of-video (catch ffmpeg error, log warning rather than crash), 0 transitions (clean exit)

### ROI evolution: points → KDA → KDA + notkda HUD verifier
- Original detector used `points` ROI (tiny 6x15px @1080p, top-center near timer). Failure: ROI sat next to colored objective icons (B/C capture points); on certain I-frames the 4x10px @720p crop landed on saturated icon colors, producing false ends. Confirmed 3 false ends in `lvlaste.mkv` at 26m31s/31m31s/39m01s
- Decision: switch detection ROI to `kda` (10x16px @1080p, bottom HUD); 7x11px @720p still sufficient for white-text detection at existing thresholds. KDA known transient occlusion (killcam, VFX, victory) is filtered by the existing 3-frame end confirm window
- Config-section name kept as `points_detection` deliberately even after KDA switch — thresholds are generic white-text params, not ROI-specific; renaming would be a broader refactor
- HUD verification problem: KDA ROI alone produces false positives on score screens (score-screen background is bright enough to pass white-pixel HSV thresholds → state machine believes gameplay ongoing → end frame captured is actually a score screen, e.g. `21m10s_end_008` had gray_mean=155 in notkda region vs 22-68 during real gameplay)
- Decision: AND-gate `white_detected` with a brightness check on the existing `notkda` ROI (dark HUD background immediately right of KDA digits). Frame counts as in-game only if KDA has white pixels AND notkda gray-mean is below `hud_brightness_max` threshold
- Gray-mean over notkda chosen instead of HSV white-ratio: simpler, sufficient — region just needs a brightness check
- Threshold kept tunable per-map via config; gameplay/score-screen brightness gap on tested footage is wide enough that one global threshold works, but failure mode (future map with bright HUD background in notkda) is documented as risk

## Hashing Workflow — Tool 3 (`hash_comparator.py`)
- Purpose: from labeled per-map start/end/score frames produce (a) a comparative report of hash methods/ROIs and (b) the production `map_config.json` containing reference hashes for runtime map ID
- Replaces a prior pixel-by-pixel approach (rejected: too sensitive to background variation behind HUD transparency)
- Coexists with legacy `tools/map_config_generator.py` (unchanged); not unified to avoid breaking the legacy path
- Multi-hash comparison via `imagehash`: aHash, dHash, pHash — all return `ImageHash` supporting `-` operator for Hamming distance
- Pipeline per frame: `downscale → scale_roi → extract_roi → (optional anchor crop) → to_grayscale → (optional Otsu threshold) → tile_into_canvas → compute_hash`
- Median/mode hash across multiple frames per map used as the representative reference (more robust than single-frame); intra-map hash variance also exposed as a stability diagnostic
- Collision detection: per-method, all pairwise Hamming distances; flag pairs below `collision_threshold`
- ROI strategies tested: `map_name_hud` (HUD text zone, present on every in-game I-frame) vs score-screen map zone (more stable but depends on score capture); both defined in config, comparator can iterate
- Optional resolution sweep: when enabled, repeats hash gen at e.g. [1080,720,540,360] and includes resolution as a report dimension; default disabled
- Auto-selection: pick (roi, resolution, method) tuple with highest minimum pairwise distance ("best separation"); writes that combo into `map_config.json`
- Override: `--force-method` CLI flag and `preferred_method` config key bypass auto-selection for the `map_config.json` write only — comparison report still runs all methods. CLI > config > auto. Rationale: pHash optimizes the training-frame metric but proved cross-video inconsistent (same map `the_cliff` hashed dist=0 with dhash but dist=90 with phash on a different recording)
- `--preview` CLI flag: writes processed canvases as PNGs for visual inspection of the ROI/anchor/threshold pipeline
- Tool 2 dependency: `frame_labeler.py` extended from score-only to also label `*_start*` / `*_end*` frames (filename-suffix preserved) so Tool 3 has complete training data; labeled output structure `<output>/labeled/<map_name>/`

## Map-name anchor sub-ROI
- Problem: HUD text is sometimes "Silva", sometimes "Silva - BO3" / " - BO5"; suffix bleeds into hash → unstable hashes for same map across contexts → collisions / false negatives
- Solution: scan the cropped ROI column-by-column for the first column containing a white pixel (HSV whiteness check identical to `has_white_pixels` thresholds), then crop a fixed-width sub-ROI starting at that anchor; width sized to fit shortest map names (Silva, Ceres) and exclude the BO3/BO5 suffix
- New util: `find_text_anchor(bgr_crop, sat_max, val_min)` in `utils/image.py`; vectorised with numpy column-any over HSV mask; returns -1 if no white col found
- Wired into `build_canvases()` between `extract_roi` and `to_grayscale`; threaded through `run_comparison` → `main` (read `text_anchor_width` from config)
- Anchor width expressed at 1080p reference and scaled proportionally `int(width * fh/1080)` like other ROIs; `tile_cols` continues to apply on the resulting sub-ROI
- Behaviours: anchor not found → frame skipped silently with stderr warning (no fallback to full ROI by design); sub-ROI clamped to right edge if `anchor_x + width` overflows; sub-ROI < 2px wide → skipped (degenerate hash)
- Backward compatible: `text_anchor_width=None`/0/absent disables the feature, preserving full-ROI behaviour

## Threshold-hash preprocessing (Otsu binarization)
- Hypothesis: binarize grayscale crop via `cv2.THRESH_BINARY + cv2.THRESH_OTSU` (auto-selects split per crop) to remove background brightness variation behind semi-transparent HUD → more stable hashes
- New util: `apply_threshold(gray)` in `utils/image.py`; threaded through both training (`hash_comparator.build_canvases`) and runtime (`warden_analyzer.identify_map`) so reference and inference pipelines stay byte-identical
- Config flag `threshold_hash` under `map_identification`; consistency between generation and inference is mandatory (mismatch = bad accuracy)
- EMPIRICAL OUTCOME (negative result): Binarization is harmful for perceptual hashing on this use case — dhash/phash rely on pixel gradients, Otsu destroys gradient information; the anchored ~34×15px crop @720p is also too small for reliable bimodal histogram splitting. Tested on 10 labeled maps with dhash + 52px text anchor: `threshold_hash:true` → min dist 0, 3 collisions; `threshold_hash:false` → min dist 21, 0 collisions
- Resolution: default flipped to `false`; plumbing kept (CLI flag, util, config wiring) for future experimentation
- Degenerate Otsu (uniform/black crop) returns valid array (all-0 or all-255) — recognition_threshold gates downstream as `unrecognized`

## Hash Accuracy Validator — Tool 4 (`hash_validator.py`)
- Purpose: regression/coverage check — load `map_config.json`, iterate every `*_start.png`/`*_end.png` in `output/labeled/<map>/`, predict map per frame via shift-tolerant nearest-hash, report per-frame and per-map accuracy
- Reuses `build_canvases`, `hamming_shift_tolerant`, `compute_hash`, `IMAGE_EXTENSIONS` from `hash_comparator.py` via second `sys.path.insert` for `tools/`
- Score frames excluded (`*_score.png`) — Tool 4 measures HUD-based identification, score-screen ID is a separate concern
- Maps in `labeled/` not present in `map_config["maps"]` → reported under `no_reference` section, excluded from accuracy math (currently 4 such: `bastion`, `coliseum`, `lunar_outpost`, `the_rock`)
- Prediction logic: lowest `hamming_shift_tolerant` distance wins; alphabetical tie-break; "unknown" threshold optional (omitted in V1)
- Output: `output/accuracy_report.json` with `summary` (overall accuracy, frame counts, evaluated maps, no_reference list), `by_map` (per-map accuracy + frame list with predicted/distance/correct), `no_reference` array
- CLI: `--images`, `--map-config`, `--shift-tolerance` (default 2), `--resolution` (default 720, must match generation resolution), `-o/--output-dir`
- Known gap: `map_config.json` does not store the processing resolution — if Tool 3 is re-run at a different resolution, validator must be invoked with matching `--resolution`. Persisting resolution into `map_config.json` is a future enhancement
- Future flag idea: `--fail-on-incorrect` for CI gating
- Goal: as new labeled frames are added, accuracy stays ≥ target on known maps; regressions caught before they reach mobile runtime (specific accuracy numbers calibrated per release — not pinned in spec)

## Pipeline Parity Fix (validator vs generator alignment)
- Failure mode: `hash_validator` was hardcoded to `text_anchor_width=None` and `threshold_hash=False` while reference hashes in `map_config.json` may have been generated with `text_anchor_width=52` / `threshold_hash=True`. Validator therefore hashed a different crop/binarization than generation → near-random distances (300–450 of 1024 max) and 8% accuracy
- Root cause: generation-time pipeline params were read from config but never persisted into `map_config.json`, so validator could not reproduce them
- Fix: persist `text_anchor_width` and `threshold_hash` into `map_config.json` at generation time (both `hash_comparator.py` and `map_config_generator.py`); validator reads them back and passes through to `build_canvases`
- Persistence rules: `text_anchor_width` written only when truthy (non-zero/non-None); `threshold_hash` written only when True — keeps configs minimal and `.get()` defaults safe
- Backward compat: `.get("text_anchor_width")` → None and `.get("threshold_hash", False)` → False reproduce pre-change validator behaviour; legacy configs work unchanged
- Patch-mode: `map_config_generator.py` patch-loop preserves these fields when present in existing config but the live config takes precedence when re-run
- Existing `map_config.json` must be regenerated after the code fix or accuracy will remain broken — code fix alone is insufficient

## Map ID — Force Method & Threshold Calibration
- Failure mode 1 (auto-selection wrong metric): comparator's `select_best_combination` favours the method with the largest min pairwise distance on training frames, picking phash@hash_size=16 (min 92 vs dhash min 76); but phash is cross-video inconsistent (the_cliff dist=0 dhash vs dist=90 phash on different recording). Fixed via `--force-method` CLI flag + `preferred_method` config (CLI wins over config wins over auto). Comparison report still includes all methods
- Failure mode 2 (threshold not tied to hash size): `recognition_threshold` is fixed in `config.yaml` (calibrated for 64-bit hashes at hash_size=8). When hash_size scales to 16 (256-bit), Hamming distances scale ~4×, threshold doesn't, all maps get flagged `unrecognized`
- Fix: scale and persist `recognition_threshold` into `map_config.json` at generation. Formula: `round(base_threshold * (hash_size/8)**2)` (e.g. 8→10, 12→22, 16→40)
- Runtime (`warden_analyzer.py`) reads `recognition_threshold` from `map_config.json` first; falls back to `config.yaml` with stderr warning if absent. Log line shows source (`map_config` vs `config.yaml`) for debugging
- Terminology: `recognition_threshold_base` = raw user-controlled value in config.yaml; `recognition_threshold` (no suffix) = scaled value persisted to map_config.json and used at runtime — distinction must stay consistent in code

## Cross-cutting integrations — `map_config.json`
- File serves as serialized state of the entire hashing pipeline so the runtime (mobile or `warden_analyzer.py`) can reproduce generation-time behaviour byte-for-byte
- Fields read by detection subsystem at runtime: `reference_resolution` (1920×1080 baseline), `roi` (HUD map-name region), `canvas_size`, `hash_size`, `hash_method` (which of ahash/dhash/phash), `tile_cols`, `text_anchor_width` (omitted when disabled), `threshold_hash` (omitted when False), `recognition_threshold` (scaled), `maps` (dict of map_name → reference hash hex), `shift_tolerance` (Hamming-shift tolerance — value tunable per pipeline)
- Fields populated by detection subsystem during config generation: same set, written by `generate_map_config()` in `hash_comparator.py` and by `map_config_generator.py`; runtime params (`recognition_threshold` etc.) sourced from `config/config.yaml` `map_identification` block at generation time
- Resolution at which hashes were computed is NOT stored — known gap, validator must pass matching `--resolution` flag (future: store)
- Total maps targeted: 14–15 (frame_labeler lists 14, description.md says 15 — unresolved). Currently 10 maps have reference hashes in `map_config.json`; 4 (bastion, coliseum, lunar_outpost, the_rock) await labeled video data — adding a new map = capture/label start+end frames, re-run Tool 3, validate with Tool 4
- `config/config.yaml` `map_identification` is the source of truth for tunables: `rois` list (currently `map_name_hud` HUD zone + score-screen zone), `canvas_size`, `hash_size`, `hash_methods`, `preferred_method`, `text_anchor_width`, `threshold_hash`, `tile_cols`, `recognition_threshold`, `shift_tolerance`, `collision_threshold`, optional `resolutions` for sweep
- `points_detection` config section consumed by game_detector: white-detection HSV thresholds (sat_max/val_min/min_ratio), `start_confirm_count`/`end_confirm_count`, `score_offset`, `hud_brightness_max` (notkda gating)
- ROI naming convention: `points`, `kda`, `notkda`, `map_name_hud`, `score_screen_map`, `minimap`; defined under `black_detection.roi_zones` (legacy section name) at 1920×1080 reference, scaled at runtime via `utils/image.scale_roi()`

## Auto-HSV from Drawn ROI (tooling UX bootstrap)
- Tool: `tools/minimap_zone_selector/app.py` — interactive Tk app where user draws a rectangle on a minimap frame to define a zone for downstream HSV-based detection
- Old behaviour: drew zone → zone created with hardcoded HSV defaults (`h_center=0, h_tol=180, s_center=0, s_tol=12, v_center=100, v_tol=15`); user manually dialed HSV from scratch
- New behaviour: on draw release, sample BGR pixels from the displayed frame within the rectangle, derive HSV center/tolerance, auto-populate the zone, auto-load it into the HSV editor panel — eliminates manual dial-in
- Hue uses circular mean (sin/cos → atan2) to handle wraparound at 0°/360° (red-toned regions correctly resolve to ~355°/~5°, not midpoint artefact 180°)
- Hue std uses circular std `sqrt(-2 * log(R))` where `R` = mean resultant length, with `max(R, 1e-9)` guard against log(0) on uniform-hue regions
- S/V use plain mean/std and convert OpenCV (0–255) → user space (0–100)
- Tolerances = `max(MIN_TOL, ceil(std * 1.5))`; floors `_MIN_H_TOL=10`, `_MIN_SV_TOL=5`
- Sources BGR via `data_loader.get_frames(map)[frame_idx]` (no PIL roundtrip); empty-region guard added (returns safe defaults if numpy slice yields zero pixels)
- Out of scope: multi-frame averaging across all frames for a zone, sampling from non-displayed frames (single-frame is sufficient for static map terrain); `min_ratio` still hardcoded at 0.3; hue tolerance has no upper cap (heterogeneous regions can hit ~180, intentional signal of ambiguity)

## Reference / Storage / Versioning
- Reference hashes stored as hex strings in `output/map_config.json` under `maps: {map_name: hex}`
- Hashes loaded back via `imagehash.hex_to_hash(h)`
- Generation triggered manually via `wardentooling.py` → "Tool 3 — Generate Map Config" or `hash_comparator.py` direct
- No formal versioning of `map_config.json` — backward compat handled via additive fields and `.get()` defaults
- Adding new map workflow: capture video → Tool 1 frame extraction → Tool 2 frame labeler labels start/end/score per map → Tool 3 regenerates `map_config.json` (incrementally adds new map's hash) → Tool 4 validates accuracy ≥ target → ship config to mobile
- Cross-link: this distillate's `map_config.json` reference-hash set is the same artifact described in group G4 (consensus-reference-hash) — single source of truth for runtime map identification across tooling and mobile

## Tech Stack & Dependencies
- Python 3.8+ ; OpenCV ≥4.8 ; imagehash ≥4.2 ; numpy ; Pillow ; PyYAML ; ffmpeg (subprocess for I-frame and full-frame extraction)
- All deps already in `requirements.txt`; none added by any spec in this group
- Shared utils: `utils/image.py` (`scale_roi`, `extract_roi`, `has_white_pixels`, `find_text_anchor`, `apply_threshold`, `to_grayscale`, `downscale`), `utils/video.py` (`extract_iframes_scaled`, `extract_frame_at_timestamp`, `get_video_info`), `utils/config.py` (`load_config`), `utils/format.py` (`format_timestamp`)
- All shared utils are stateless pure functions (np in → np out); no classes
- Tk-based interactive tool (`minimap_zone_selector`) is the only stateful UI; all other tools are CLI

## Codebase Patterns (consumed by detection/hashing tools)
- Modular CLI: each tool standalone in `tools/`, `argparse`-based, `sys.path.insert` for `utils/` access
- run()+main() split: core logic returns results, CLI entry parses args
- ROI definitions at 1920×1080 reference, scaled at runtime via `scale_roi()`
- Config-driven via YAML loaded with `load_config()`; CLI args override config (`arg if arg is not None else config.get(...)`)
- Deferred batch extraction: collect `extraction_requests` during I-frame scan, then ffmpeg-batch full-resolution frames at the end → minimizes subprocess calls
- File-based I/O between tools: PNG outputs named `MMmSSs_type_seq.png`; labeled frames in `<output>/labeled/<map_name>/`; reports in `output/*.json`
- State machines with confirmation counters (start_confirm/end_confirm) to filter transient signal flicker
- "None = feature disabled" convention for optional pipeline params (`text_anchor_width`, `threshold_hash`) → backward compat free

## Open Questions / Deferred / Risks
- Map count: 14 vs 15 discrepancy between `frame_labeler.py` and `description.md` — unresolved
- 4 maps still missing reference hashes (bastion, coliseum, lunar_outpost, the_rock) pending labeled video data
- `map_config.json` does not persist generation resolution — silent mismatch risk if Tool 3 is re-run at non-default resolution; deferred enhancement
- HUD-brightness threshold (`hud_brightness_max`) is global; future map with bright HUD background near KDA could trigger false-end detections — mitigated by config-tunability, monitored as risk
- KDA ROI vulnerable to prolonged occlusion (extended killcam, victory cinematics) → could bump `end_confirm_frames` if observed; deferred
- Threshold-hash binarization left in codebase as opt-in despite negative empirical result; may revisit if anchor crop is enlarged
- pHash cross-video inconsistency (same map dist=0 vs dist=90 across recordings) is the root reason for `--force-method dhash` operational default
- No automated test framework anywhere in the project; all validation manual via Tool 4 reports + visual `--preview` inspection
- Failure modes documented: low-similarity hashes (mismatched pipeline params — fixed by parity work), occluded HUD (handled by HUD verifier + confirm windows), score-screen false positives (notkda gate), background-brightness instability (Otsu attempted, rejected), text suffix variation (anchor sub-ROI), score timestamp past EOF (caught + logged)
- Future: `map_config.json` could grow `resolution` field; `hash_validator.py` could grow `--fail-on-incorrect` for CI gating; multi-ROI composite hash (combining HUD + score-screen) if no single ROI achieves zero collisions; `map_config_generator.py` (legacy) eventual deprecation in favour of `hash_comparator.py`
