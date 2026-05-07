## Group Scope
- G3 distillate: orchestrator + visualization/inspection layer of the Python desktop tooling app (legacy `Warden-tooling`, now `apps/tooling`); user-facing wrappers + central `map_config.json` artifact + frame-labeling and minimap GUI tools
- Sources: project-sprint.md (sprint tracker), tech specs for warden-tui-launcher, map-config-generator, warden-round-analyzer (Tool 5), warden-image-inspector, minimap-view-mode, minimap-zone-selector, frame-labeler-grouped-export, video-named-output-subfolders, tech-spec-wip (match-preview)

## Pipeline & Tool Inventory
- Pipeline goal: validate video analysis on desktop and emit map-identification JSON consumed by the mobile app; desktop tooling is a prerequisite to React Native / Kotlin mobile impl
- Pipeline order (project-sprint.md): Tool 1 Black Screen Detector → extracted frames; Tool 2 Frame Labeling → organized labeled folders; Tool 3 Pixel Finder → map-id JSON; Tool 4 Validation → accuracy reports
- Sprint state: Tool 1 BSD (Not Started, ref impl for mobile, I-frame iteration + ROI black detection + 15s skip); Tool 2 Frame Labeling (Done, tkinter GUI `frame_labeler.py`, scope expanded from manual to full GUI); Tool 3 Discriminating Pixel Finder (Not Started, intra-map compositing + cross-map comparison + resolution sweep — most complex); Tool 4 Validation & Accuracy Testing (Not Started, end-to-end + map-ID-only modes)
- Realized tool inventory (from specs, expands beyond original 4-tool plan): Tool 1 game_detector, Tool 2 frame_labeler, Tool 3 map_config_generator (later evolved to hash_comparator/hash_validator), Tool 4 hash validation, Tool 5 warden_analyzer (round analyzer, end-to-end), plus dev/diagnostic tools (image_inspector, bsd_roi_debugger, points_state_detector) and visualization tools (minimap_zone_selector, minimap_view_mode, match_preview)
- Top-level orchestrator: `wardentooling.py` (Python TUI launcher at project root); single entry point `python wardentooling.py`
- Status of orchestrator/visualizer specs: warden-tui-launcher (Completed); map-config-generator (completed); warden-round-analyzer Tool 5 (Implementation Complete); warden-image-inspector (completed); minimap-zone-selector (completed); frame-labeler-grouped-export (completed); video-named-output-subfolders (completed); minimap-view-mode (ready-for-dev, not yet implemented); match-preview (in-progress, Step 1 only — DEFERRED/WIP)
- Pipeline goal success criteria (from sprint): 100% black-screen transition detection with 0 false positives; 100% map ID on training set; ≥95% (target 100%) on unseen test set; reproducibility across sessions/players; all validated via Tool 4 reports

## Tech Stack & Architectural Patterns
- Python 3 / 3.8+ throughout; FFmpeg via subprocess for I-frame extraction (NOT OpenCV for video decode in the pipeline path); OpenCV used for image processing only; no UI in core pipeline (CLI tools), tkinter GUI for interactive tools
- Core deps: `opencv-python>=4.8,<5`, `numpy>=1.24,<2`, `pyyaml>=6.0,<7`, `imagehash>=4.2,<5` (transitively pulls Pillow + scipy), `Pillow>=10.0` (image_inspector), `opencv-python-headless>=4.8` (image_inspector requirements), `questionary>=2.0,<3` (TUI launcher)
- Module layout: each tool is a standalone CLI script in `tools/` OR a sub-package `tools/<tool>/` with `__main__.py`+`app.py`+helpers; shared helpers in `utils/` (`utils/video.py`, `utils/image.py`, `utils/config.py`, `utils/format.py`); config in `config/config.yaml`; output in `output/`; shared interactive widgets in `tools/common/` (e.g. `video_player.py`)
- Command surface: argparse (NOT Typer/click); consistent conventions — positional `video`, `-o/--output-dir`, `-c/--config` (default `config/config.yaml`), `--threshold`, `--profile`, `--roi`; mutually-exclusive groups for input modes (e.g. `--images DIR` vs `--video MAP PATH` repeatable)
- `sys.path.insert(0, ...)` pattern: each tool inserts project root into path to allow `utils.*` imports (avoids stdlib shadowing); orchestrator at project root does not need this
- Output folder convention: per-video subfolder via `os.path.splitext(os.path.basename(video))[0]` appended to output_dir (decided in `video-named-output-subfolders` spec, default behavior, no toggle); BSD adopts this; `bsd_roi_debugger.py` does NOT (intentional carve-out)
- Tool 5 output convention: `output/warden_<video_stem>/` containing only score frames + `rounds.json` + optional `unrecognized/<score_stem>_roi.png`
- ROI convention: ROIs defined at reference resolution 1920×1080 in `config.yaml` as dicts `{name, x, y, width, height}`; scaled at runtime via `utils/image.py:scale_roi(roi, scale_factor)` to processing/source resolution
- Reference-resolution scaling math: `scale_x = REF_W / video_w`, `scale_y = REF_H / video_h`; canvas/image coords → reference coords via `round(coord × scale)`
- Generator pattern: `extract_iframes_scaled()` yields `(frame, timestamp)` tuples to avoid loading whole video; same frame is reused for both detection and inline map-ID (zero extra I/O)
- Detection pattern: state machine `not_in_game` ↔ `in_game` driven by KDA ROI white-pixel detection with start/end confirmation counts and post-detection batch full-res frame extraction (used by game_detector and warden_analyzer)
- Stateless image utils: `utils/image.py` is pure (`extract_roi`, `to_grayscale`, `downscale` aspect-preserving NOT for fixed-canvas, `scale_roi`, `find_text_anchor`, `has_white_pixels`, `is_black`)
- `utils/video.py`: `extract_iframes_scaled()` (single-pipe FFmpeg `-skip_frame nokey` + timestamp parsing on stderr via background thread), `get_video_info() -> (w,h)`, `extract_frame_at_timestamp()`
- Test patterns: no automated test framework in repo; manual smoke tests; pure functions (e.g. `view_renderer.render`, `zone_fires`, `ZoneValidator.compute`) are testable in isolation but no harness exists; introducing a framework would exceed scope

## Cross-cutting integrations
### map_config.json — central artifact
- Purpose: portable map-identification fingerprint config consumed by mobile (mobile cannot run OpenCV); 64-bit perceptual hash (pHash) of map-name text ROI per map
- Producer: `tools/map_config_generator.py` (Tool 3 / hashing variant) — extracts I-frames from reference videos OR accepts pre-extracted images; crops map-name ROI; runs standard canvas pipeline (crop → grayscale → 64×64 resize via `cv2.INTER_LINEAR`/`INTER_AREA`); generates 64-bit phash via `imagehash.phash(PIL.Image.fromarray(gray), hash_size=hash_size)`; checks Hamming-Distance collisions; writes JSON
- Consumers: `warden_analyzer.py` (Tool 5) reads `output/map_config.json` (default) for inline map ID via `predict_map(canvas, ref_hashes, hash_size, method, shift_tolerance)` from `hash_validator.py`; `match_preview` reads it for per-segment map ID
- Inputs to generator: `config/config.yaml` (`map_identification` section: `roi`, `canvas_size`, `hash_size`, `collision_threshold`, later additions `shift_tolerance`, `recognition_threshold`, `text_anchor_width`, `hash_method`, `tile_cols`); manual ROI coordinates at 1920×1080; reference videos OR pre-extracted PNGs per map subdirectory; later: `minimap_zone_selector` outputs HSV zone configs into `minimap_identification.configs[]` in the same `config.yaml`
- Output schema (fields, not values): top-level `roi: {x, y, width, height}`, `canvas_size: int`, `hash_size: int`, `hash_method: string` ('dhash'/'ahash'/'phash'), `tile_cols: int`, `maps: {map_name: hex_hash_string}`; later evolution added `reference_resolution` echo and `text_anchor_width`
- Default output path: `output/map_config.json`; written via `json.dump(..., indent=2)`
- Regenerated: on demand via `python tools/map_config_generator.py --images DIR` or `--video MAP PATH [--video MAP PATH …]` with optional `--preview` (writes 64×64 grayscale `preview_<map>.png` per map for visual verification) and `-o`/`-c`
- Map enumeration: 14 maps per project-sprint.md; spec text says "15 EVA maps" in map-config-generator (minor inconsistency); canonical list of 14 in `tools/frame_labeler.py:19-34` `MAP_LABELS = [horizon, engine, outlaw, ceres, artefact, silva, bastion, polaris, coliseum, the_cliff, helios, atlantis, the_rock, lunar_outpost]` — single source of truth, do NOT duplicate; minimap-zone-selector and minimap-view-mode import from this list
- Validation: collision check via Hamming Distance — warns if any pair below `collision_threshold` (default mentioned 12); `recognition_threshold` (default 10) added later for warden_analyzer to mark `"unrecognized"` when `best_dist >= recognition_threshold`; thresholds tunable via config; collisions printed to stderr with sorted pairwise distances; collision check serves as built-in self-test
- Schema enforcement (legacy state): NOT formally enforced — JSON shape is implicit, defined by producer + replicated in consumer reads; no JSON Schema document or runtime validator in legacy tooling repo
- Schema enforcement (monorepo target): `contracts/map-config.schema.json` is the unified schema location going forward (cross-app contract for tooling↔mobile↔web); legacy validation is best-effort/by convention only
- Map-name ROI coordinates (illustrative — values tunable in config, not load-bearing): originally `x:827, y:79, w:264, h:22` at 1920×1080, reused from existing `black_detection.roi_zones.map_name`; tunable; `--preview` exists specifically to visually verify the crop
- Hash internals (preserved fact, not values): `imagehash.phash()` internally resizes to `(hash_size*4)²` before DCT; canvas at 64×64 ensures a downscale rather than upscale at hash-time
- Source-resolution extraction: video input mode pulls I-frames at native resolution (NOT downscaled like BSD) — hash quality depends on crisp text in ROI

### Cross-tool data flow
- BSD (Tool 1) extracts start/end/score frames → `output/<video_stem>/` flat PNGs named `{timestamp}_{type}_{seqnum}.png` (e.g. `00m14s_start_001.png`); seqnum is global, chronological
- frame_labeler (Tool 2) consumes Tool 1 output dir; recursive glob `**/*score*.png`; user keystroke labels score frame into one of 14 per-map dirs; auto co-exports start+end frames linked by sequence number (seq < score_seq for start; start_seq < end_seq < score_seq for end); flat in `labeled/<map>/` named `{counter:03d}_{type}.png`; per-map counter; undo removes all three files
- frame-labeler-grouped-export rationale: Tool 3 hashing experimentation needs all three frame types (start/end/score) so any combination can be tried without re-labeling; previously only score was exported, wasting labeling sessions if score proved unreliable
- map_config_generator (Tool 3 hashing) consumes labeled directory (subdirs per map) OR direct video files; emits `map_config.json`
- warden_analyzer (Tool 5) consumes raw video + `map_config.json`; emits score frames + `rounds.json` `{video, map_config, rounds:[{round, map_name, start_timer, end_timer, score_timer, recognition_distance}]}`; unrecognized → `unrecognized/<score_stem>_roi.png`
- minimap_zone_selector consumes labeled directory (Tool 2 output) for all per-map images; emits versioned `minimap_identification.configs[]` into `config/config.yaml`
- minimap_view_mode consumes raw video + `config.yaml` `hud_versions[]`; emits new `hud_versions[]` entries (per-map minimap ROIs + shared scores/health-bar ROIs); does not write any artifact other than YAML
- match_preview consumes raw video + `config.yaml` + `map_config.json`; emits sidecar `<video>.matches.json` next to the video
- Sidecar pattern (match_preview): `{video_mtime, video_size, schema_version: 1, matches: [...]}`; invalidates when mtime or size differs

## TUI Launcher (warden-tui-launcher)
- File: `wardentooling.py` at project root; primary user: developer running pipeline locally; run when iterating on a new video or re-running prior step
- Library: `questionary>=2.0,<3` — terminal-native; `select`, `text`, `confirm`, `checkbox` primitives
- Invocation pattern: `subprocess.run([sys.executable, ...], cwd=PROJECT_ROOT)` — streams output naturally, avoids tkinter import side-effects; uses `sys.executable` (not `"python"`) to match interpreter
- Main menu: Tool 1 Extract Rounds, Tool 2 Label Frames, Tool 3 Generate Map Config, Tool 4 Validate Hash Accuracy, Tool 5 Analyze Rounds, Dev Tools, Quit
- Dev/Diagnostics submenu: Image Inspector, ROI Debugger, Points State Detector, Back
- Last-run persistence: `.warden_last_run.json` at project root (gitignored); schema `{tool, label, args:[...], video_path}`; saved only on successful exit code; on next launch offers "Run on new source / Run with same args / Skip"
- "Run on new source" re-prompts only the source path (video or directory) and preserves all other flags (per-tool `_reprompt_source` handler)
- File browsing helpers: `browse_video_file()` recursive glob for `*.mp4` from CWD with manual fallback `[ Enter path manually ]`; `browse_image_file()` non-recursive (avoids expensive recursive glob); `browse_directory()` immediate subdirs of CWD, excludes code dirs; loops until valid path
- Tool registration: `_TOOL_MAP` dict keyed by tool key → `(label, flow_function)`; each `flow_toolN()` returns `(args_list, video_path | None)`; `menu_main()` dispatches via match on label, calls flow → confirm summary → `run_tool` → `save_last_run` (only on returncode 0)
- Image Inspector launches via `python -m tools.image_inspector` (NOT direct `.py` path) because it's a package
- ROI Debugger flow: `--range` defaults `0:15`, validated via regex `^\d+:\d+$`; rejects invalid input
- Ctrl+C / KeyboardInterrupt: `main()` wraps in try/except, prints `"Bye."`, exits cleanly without traceback
- Risk: questionary may behave differently across Windows Terminal vs VSCode integrated terminal; requires proper TTY (silent failure on pipe/redirect)
- Internal structure: `load_last_run`, `save_last_run`, `run_tool`, `browse_video_file`, `browse_directory`, `flow_toolN()`, `flow_dev_*()`, `menu_dev`, `menu_main`, `main`
- Out of scope: modifying underlying tool scripts, `pyproject.toml` packaging, shell aliases, GUI beyond terminal TUI
- Future considerations (deferred): `--no-tui` headless flag mirroring underlying tool args for scripting; "new source" extension to non-video inputs (Tool 2 source dir, Tool 3 images dir)

## Visualization & Inspection Tools
### warden-image-inspector
- Path: `tools/image_inspector/` package; runnable as `python -m tools.image_inspector [image_path]` or `python tools/image_inspector`
- Purpose: precise HSV color picking and rectangular ROI definition for designing color filters and feeding coordinates to other Warden tools
- Three modes (radio toolbar, default = Color Picker): Color Picker (left-click → HSV at pixel + RGB + image coords + color swatch); HSV Filter Preview (H/S/V center + tolerance + Apply/Clear → grayscale composite outside range, 30% opacity blend); ROI (click-drag → dashed rectangle → status shows x/y/width/height in original-image pixel space)
- Module structure: `__main__.py` (CLI entry, optional PNG arg with file dialog fallback), `app.py` (`InspectorApp(tk.Tk)`, toolbar+canvas), `canvas.py` (`ImageCanvas(tk.Canvas)` zoom/pan/coord mapping), `modes.py` (`ColorPickerMode`, `HSVFilterMode`, `ROIMode` with `activate`/`deactivate`/event handlers), `logger.py` (JSON-lines writer)
- Tech decisions: tkinter (stdlib, zero-install — PyQt rejected as overkill 75-150MB GPL; OpenCV highgui rejected no toolbar; Dear PyGui rejected no built-in image viewer + GPU req); Pillow for PNG load + `ImageTk.PhotoImage`; opencv-python-headless for HSV conversion + `cv2.inRange`; `colorsys` stdlib for single-pixel RGB→HSV (scaled H:0-360, S:0-100, V:0-100)
- HSV scale convention: user-facing H 0-360, S 0-100, V 0-100; converted to OpenCV scale (`H×179/360`, `S/V×255/100`) only for pixel ops; stored in user space in config.yaml
- Coordinate system: all coords reported in original image pixel space regardless of zoom; `canvas_to_image(cx, cy)` mapping; tile-based zoom (crop visible region from PIL Image at current zoom, resize to canvas); pan via `canvas.scan_mark`/`scan_dragto`; min zoom = fit-to-window
- Persistence: `inspector_log.jsonl` next to inspected image; entries `{timestamp ISO8601, image, type:'color_pick'|'roi'|'hsv_filter', data:{...}}`; appendable, easy to parse
- Out of scope: non-rect ROI shapes, multi-image batch, direct piping to other tools, image editing
- Footprint: ~35-45 MB total added (Pillow ~3-5 MB, opencv-python-headless ~30-40 MB)

### minimap-zone-selector
- Path: `tools/minimap_zone_selector/`; runnable as `python -m tools.minimap_zone_selector --labeled <dir>`
- Purpose: replace unreliable map-name pHash with structurally stable minimap-zone identification; interactive HSV-zoned region matching per map; produces versioned configs for runtime map identifier
- Workflow: developer draws rectangular zones on minimap over stable features (walls/terrain — not players); per-zone HSV center+tolerance; eager validation against ALL labeled images for ALL 14 maps (TP rate same-map, FP rate other-maps); auto-computed weight per zone `tp_rate × (1 − max_fp_rate_other_maps)`; manual override slider; iteratively add zones until 100% accuracy; ID logic = sum of weights of firing zones ≥ `identification_threshold`
- Module structure: `__main__.py` (argparse), `app.py` (`MinimapZoneSelectorApp(tk.Tk)`), `data_loader.py` (`MinimapDataLoader` scans labeled dir, loads PNGs, warns on resolution mismatch), `zone_model.py` (`Zone`, `MinimapConfig` dataclasses, pure `zone_fires()` function), `validator.py` (`ZoneStats`, `MapStats`, `ValidationResult`, `ZoneValidator.compute`), `config_manager.py` (versioned load/save/upsert/delete/clone preserving other YAML keys), `hsv_editor.py` (`HSVEditor` inline form, validates ranges, inline red error label, no modals), `stats_panel.py` (overall accuracy, per-zone TP/FP/weight rows with delete + override, per-map accuracy table with red highlights for <100%)
- Reuses `ImageCanvas` from `tools/image_inspector/canvas.py` directly (zoom/pan + overlay redraw)
- Coordinate transform: canvas (minimap-crop space) → full-frame ref coords via `ref_x = round((crop_x + roi.x) × (1920 / frame_w))`
- Coverage simulation: per-map per-zone knockout → recompute weighted sum → fraction-correct → `coverage_sim_accuracy = min(per_knockout_accuracy)`; if 0 or 1 zones, sim equals accuracy (display "N/A")
- Config output: `minimap_identification.configs[]` in `config.yaml` — list of `{id, roi, identification_threshold, maps:{map_name:{zones:[...]}}}`; supports New/Clone/Delete via id-keyed upsert
- Default minimap ROI fallback (illustrative, not load-bearing): minimap full gameplay area at `{name:minimap, x:104, y:0, width:234, height:264}` 1920×1080
- Default zone HSV (illustrative): near-white targeting walls — H:0±180, S:0±12, V:100±15, min_ratio:0.3
- Hue wraparound: `cv2.inRange` split into two ranges when h_lo<0 or h_hi>179 (replicates `HSVFilterMode._apply`)
- Out of scope: runtime map identifier (only config gen), automatic CV zone discovery, player-dot masking, multi-image averaging
- Map labels: imports from `tools.frame_labeler.MAP_LABELS` — single source of truth
- Pure-function testability: `zone_fires(zone, bgr_frame)` testable with synthetic numpy arrays

### minimap-view-mode (NOT YET IMPLEMENTED — ready-for-dev)
- Path: `tools/minimap_view_mode/`; runnable as `python -m tools.minimap_view_mode [--video PATH] [--config PATH]`
- Purpose: ROI authoring + live HUD view-mode preview for replay study; minimap occupies ~3% of screen at native scale; analysts need re-composited HUD focus
- Two functions: (1) ROI authoring per HUD version — per-map minimap ROI + shared `scores`/`health_left`/`health_right`; (2) live frame "shader" with three modes — `normal` (pass-through), `minimap_hud` (minimap ~80% canvas-width centered + scores top-centered + health bars flanking, on black canvas), `minimap_only` (minimap fit-to-canvas aspect-preserved, rest black)
- Module structure: `app.py` (`MinimapViewModeApp(tk.Tk)`, menubar + toolbar + VideoPlayer + right-panel buttons + dirty tracking), `hud_config.py` (`ROIRect`, `MinimapROI {tight, padding_px}`, `SharedROIs`, `HudVersion`, `HudConfigManager` mirroring `minimap_zone_selector/config_manager.py`), `view_renderer.py` (PURE `render(bgr_frame, mode, hud_version, map_name) -> bgr_frame` — no Tk imports, testable in isolation, three mode constants), `roi_overlay.py` (`ROIDrawer` with start_draw/draw_persistent/clear_persistent, click-drag dashed rect via canvas tags `"overlay"`)
- Reuses `tools/common/video_player.VideoPlayer` (pre-existing, committed `5c50d74`); installs shader via `set_frame_processor(fn)`; `canvas_to_video()`/`video_to_canvas()` coord conversion already implemented
- Video decode: `cv2.VideoCapture` (NOT FFmpeg subprocess) — interactive playback needs cheap random seek + per-frame read on main thread
- Config: new top-level `hud_versions:` key in `config.yaml` (coexists with `roi_zones`; no migration); each version `{id, shared_rois:{scores, health_left, health_right}, maps:{map_name:{tight_roi, padding_px}}}`; padding stored separately so author can revisit slider in later session
- Padding: 0–N pixels expanding tight rectangle on all sides at render time, clamped to frame bounds
- HUD-version selector: combobox with New/Clone/Delete; mirrors `minimap_zone_selector` UX; first run seeds `v1` in memory, only writes on Save
- Save semantics: explicit Save button; in-memory edits dirty-flagged with `*` in title; close prompt Save/Discard/Cancel
- Map detection: NOT auto-detected — user picks from combobox; auto-detection deferred to match-preview / future tool
- Aspect-ratio mismatch: log warning + continue (mirrors `tools/map_config_generator.py:220-226`)
- Frame-processor hook: `VideoPlayer.set_frame_processor(fn)` takes `(bgr, ts) -> bgr`
- Out of scope: timeline match splitting (match_preview's domain), `roi_zones` migration (kept disjoint), video file export, OCR on scores/timer/health, HSV zone defs (stay in `minimap_identification.configs[]`), keyboard shortcuts beyond Space + Esc, automatic ROI detection, undo/redo
- Risks: codec quirks (H.265 / unusual containers may fail to open), VFR seek fuzziness on `CAP_PROP_POS_MSEC`, non-16:9 source ROI mismatch, NumPy compositing fine at 720p but a real GLSL shader would matter at 4K (out of scope)

## Frame Labeler — Grouped Export
- Modifies `tools/frame_labeler.py`; status completed
- Adds `parse_seq_num(filename) -> int|None` (regex `_(\d+)\.png$`), `find_linked_frames(score_path) -> (start_path, end_path)` (scans `os.path.dirname(score_path)` not source root, uses chronological seq linkage), `next_game_counter(dest_dir)` (counts `*_score.png` for per-map counter robust to undo)
- Modified `_label_current()` copies all three (score+start+end) with names `{counter:03d}_{type}.png`; missing start/end → console warning, copy what exists, do not block; `_last_action` becomes list of dest paths
- Modified `_undo()` iterates list and removes all copied files
- `shutil.copy2` (non-destructive); source files preserved
- Frame filename convention from Tool 1: `{timestamp}_{type}_{seqnum}.png` e.g. `00m14s_start_001.png`; seqnums global chronological; game session = `start_N → end_M (M>N) → score_P (P>M)`
- Pairing rule: for `score_P`: start = max seq among starts with seq<P; end = max seq among ends with start_seq<seq<P
- Why: Tool 3 hashing experimentation needs all three frame types; previously losing labeling work if score proved unreliable

## Video-named Output Subfolders
- Modifies `tools/black_screen_detector.py` only; status completed
- Default behavior — no toggle; uses `os.path.splitext(os.path.basename(args.video))[0]` to derive stem, appends to `output_dir` in `main()` before passing to `run()`
- `run()` already calls `os.makedirs(output_dir, exist_ok=True)`; nested dirs in video path → only stem used
- `bsd_roi_debugger.py` intentionally NOT updated (could adopt later)

## Warden Round Analyzer (Tool 5)
- Path: `tools/warden_analyzer.py`; status Implementation Complete
- Purpose: end-to-end pipeline (video → score screens + map ID + timers); validated reference impl for mobile port
- Combines `game_detector.py` KDA-based round detection state machine with inline map ID using hashing pipeline from `hash_comparator.py`/`hash_validator.py`
- Output: `output/warden_<video_stem>/` containing only score PNGs (NO start/end frames) + `rounds.json` + `unrecognized/<score_stem>_roi.png` (lazy mkdir)
- Map ID inline on downscaled start-candidate frame (already in memory at start confirmation, `.copy()` cached) — zero extra I/O; uses `map_name_hud` ROI from `map_config["roi"]`; `text_anchor_width` active disables `tile_cols` (matches `build_canvases()` line 237)
- Unrecognized criterion: `best_dist >= recognition_threshold` (default 10) OR anchor not found → `map_name = "unrecognized"`; `recognition_threshold` below `collision_threshold` (12) by safety margin
- `rounds.json` schema: top-level `{video, map_config, rounds:[{round, map_name, start_timer, end_timer, score_timer, recognition_distance}]}`; round 1-indexed; timers float seconds; `score_timer` may be null; `recognition_distance` int or null
- `identify_map(frame, ref_roi, ref_hashes, canvas_size, hash_size, hash_method, shift_tolerance, recognition_threshold, text_anchor_width) -> (map_name, best_dist, roi_crop_bgr)` — returns `("unrecognized", None, None)` on bounds error; `("unrecognized", None, roi_crop)` if anchor not found
- Round state dict accumulates `{seq, start_ts, end_ts, score_ts, map_name, best_dist, roi_crop}`; in-progress in `current_round`, completed entries pushed to `pending_rounds`
- Score frame extraction: post-detection batch via `extract_frame_at_timestamp` at `score_offset` (e.g. 14.5s) past `last_in_game_timestamp`; if exceeds video duration → caught (`RuntimeError` / `subprocess.CalledProcessError`), warning, round still in JSON with score_filename null
- Aspect ratio warning if `abs((src_w/src_h) − (ref_w/ref_h)) > 0.01`
- TUI integration: `flow_tool5()` returns `(args, video_path)`; registered in `_TOOL_MAP` as `warden_analyzer`; `_reprompt_source` branch preserves all flags except video path
- End-of-video warnings: stderr for partial start/end confirmation frames at video end, in-game termination → incomplete round discarded
- Future: `run()` detection loop + `identify_map()` are exact logic to port to mobile

## WIP / Deferred / In-flight (flag prominently)
- match-preview tool (tech-spec-wip.md): IN-PROGRESS — only Step 1 of 4 complete; Implementation Plan tasks + Acceptance Criteria explicitly "_To be filled in Step 3 after deep investigation._"
- match-preview locked decisions (Step 1): synchronous detection on load with modal progress dialog (background threading deferred); BSD refactor option A — split `run()` into pure `detect_transitions()` + side-effecting `export_frames()`; BSD chosen over `game_detector` (start/end semantics align with match boundaries, recovery windows handle dropped transitions); sidecar `<video>.matches.json` adjacent with mtime+size invalidation; match switch → seek-to-start + pause; reusable `match_detector.py` with CLI; low-confidence labels = "Map N" fallback (NOT "?" or separate group); reuse `tools/common/video_player.py` unchanged
- match-preview deferred to Step 3: representative-frame sampling offset within segment, confidence threshold (Hamming cutoff) location in config, unpaired start/end handling rules, progress-dialog cancel semantics, sidecar schema version + field list, `detect_transitions()` return shape (dataclass vs dict-list), how `run()` composes the two
- minimap-view-mode: ready-for-dev but Tasks 1–8 all unchecked; not yet implemented; Acceptance Criteria all unchecked
- warden-round-analyzer: implementation marked complete but Acceptance Criteria all unchecked (validation pending real-footage testing)
- Pipeline core tools (Tool 1 BSD, Tool 3 Discriminating Pixel Finder, Tool 4 Validation): all "Not Started" per project-sprint.md (NOTE: hashing-based map-id approach evolved separately into `map_config_generator` + `hash_comparator` + `hash_validator`; original "Pixel Finder" likely superseded — sprint tracker not updated to reflect actual implementation path)

## Open Questions / Decisions / Conflicts
- Map count discrepancy: project-sprint.md says 14, map-config-generator says 15, MAP_LABELS list contains 14 — canonical = 14 from `tools/frame_labeler.py:19-34`
- Map ID approach pivot: original plan was Tool 3 Discriminating Pixel Finder (per-pixel comparison); actual implementation is perceptual-hash based (map_config_generator) + later HSV-zone based (minimap_zone_selector) replacing pHash for unreliability — pHash unreliable in practice was the documented motivation for zone selector
- Decision: ROI coords stored at fixed reference resolution 1920×1080 instead of normalized 0.0-1.0; rationale = consistency with rest of codebase; normalized exploration deferred
- Decision: 64×64 standard canvas with `cv2.INTER_LINEAR` (NOT aspect-preserving `downscale()`); rationale = phash needs fixed square canvas, ensures phash internal resize (32×32 with hash_size=8) downscales rather than upscales
- Decision: separate `map_identification` config section from `black_detection` despite shared ROI; rationale = each tool's config self-contained
- Decision: `imagehash` library + Pillow over hand-rolled phash; rationale = well-maintained, configurable `hash_size`, simple PIL conversion
- Decision: tkinter (stdlib) over PyQt/Dear PyGui/OpenCV highgui; rationale = zero-install, sufficient widget support, no GPU req, no GPL
- Decision: `cv2.VideoCapture` for interactive playback tools (minimap-view-mode, match-preview) vs FFmpeg subprocess for batch pipeline tools; rationale = cheap random seek + per-frame read on main thread vs designed-for-streaming
- Decision: `hud_versions[]` and `roi_zones` coexist in config.yaml with NO migration; rationale = existing tools continue to work unmodified
- Decision: `minimap_identification.configs[]` versioned list (id-keyed, supports clone) — rationale = HUD updates / map reworks tracked without losing prior working configs
- Rejected: own platform-specific GUI; tkinter chosen for portability
- Rejected: PyQt (overkill 75-150MB GPL), OpenCV highgui (no toolbar/text inputs), Dear PyGui (no built-in image viewer + GPU req)
- Rejected: background-threaded detection in match-preview (locked decision: modal block)
- Rejected: `game_detector.py` as match-preview transition source; BSD chosen for cleaner start/end semantics + recovery windows
- Rejected: temp-dir hack or lean reimplement for BSD reuse; chose proper refactor (split `run()` into `detect_transitions()` + `export_frames()`)
- Rejected: relative-position preservation across match switches; deemed meaningless for differing-length segments
- Rejected: per-match thumbnail previews in match-preview combobox (deferred)
- Open question (cross-app contract): `contracts/map-config.schema.json` is unified target — what's the schema-version field strategy? Currently sidecar uses `schema_version: 1` but `map_config.json` has no version field
- Open question: when does `bsd_roi_debugger.py` adopt the per-video output subfolder convention?
- Open question: future "new source" extension for non-video Tool 2/Tool 3 inputs in TUI launcher

## Risks / Known Issues
- questionary TTY requirement on Windows — silent failure if launched via pipe/redirect; needs proper terminal
- `cv2.VideoCapture` may fail on H.265 / unusual containers; user must transcode; surface clean error
- VFR seek via `CAP_PROP_POS_MSEC` is approximate; exact-frame seek out of scope
- Non-16:9 source aspect ratio: ROIs stored at 1920×1080 may not correspond to sensible HUD layout; warn + continue
- Map-name ROI dimensions may need tuning per-map (text doesn't fill region consistently across all maps); `--preview` flag exists for visual catch
- Hash collision risk: if collisions occur user should adjust ROI to capture more discriminating text OR increase canvas_size
- `score_offset` (14.5s) past `last_in_game_timestamp` can exceed clipped video duration — handled by exception catch, round still in JSON without score_filename
- Rendering compositing in Python/NumPy is fine at 720p but inadequate at 4K (out of scope)
- No automated test framework — all tools manually validated; introducing a framework would exceed scope of any individual sprint item
- Imagehash hex_to_hash failure → wrapped in try/except with clear error pointing to map_config corruption (Tool 5 review fix F8)
- Source video resolution / target downscale res / color mode (RGB/gray) / black detection ROI zones / HUD exclusion mask / brightness threshold — all sprint shared decisions still TBD per project-sprint.md (skip duration locked at ~15s)

## Adversarial Review Outcomes (preservation of decisions)
- map-config-generator: 14 findings, 7 fixed (resolution validation, aspect ratio check, empty video error, ffmpeg check, INTER_AREA, reference_resolution echo in output, imwrite check), 7 skipped (bare except OK for CLI, duplicate ROI intentional, config validation = trust config, first I-frame OK, threshold semantics correct, no tests = manual per spec, sys.path = project pattern)
- warden-tui-launcher: 10/10 fixed (dead skip_video param removed, KeyError guarded, mode cancel guarded, run_tool returns exit code, recursive scan for videos, code-dir exclusions, sys.executable, image format expansion, source-only re-prompt)
- warden-image-inspector: 15 findings, 13 fixed (missing __init__.py, numpy in requirements, ROI z-order via overlay tag, round() not int() for HSV scaling, clamped logged values, input validation, redraw throttling via after_idle, logger graceful errors, single Tk root, corrupt image handling, HSV scale constants documented, persistent canvas items, custom-pan comment), 2 skipped
- minimap-zone-selector: 15 findings, 7 fixed (coord transform cleanup, zone ID collision, map name parsing, clone from in-memory, stale refs after export, delete persistence, tk.Frame.update shadow), 8 skipped
- frame-labeler-grouped-export: 7/7 fixed
- video-named-output-subfolders: 12 findings, 3 fixed (stale architecture.md refs, ROI loop caching comment), 9 skipped
- warden-round-analyzer: 12 findings, 2 fixed (get_video_info try/except, hex_to_hash try/except), 10 skipped (noise/by-design)
