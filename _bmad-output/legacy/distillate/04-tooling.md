> This section covers the Python CLI suite (`apps/tooling`) — pipeline tools, orchestrator, visualizers, and detection/hashing subsystems. Part 4 of 8 of the Warden legacy distillate.

## Tooling Mission & Scope
- `apps/tooling` (legacy `Warden-tooling`) is the Python desktop CLI suite that turns recorded gameplay video into structured per-round data and produces `map_config.json` consumed by the mobile app
- Subsystem roles: (1) round/segment detection (BSD + game_detector); (2) frame labeling (Tool 2 / frame_labeler); (3) map identification via perceptual hashing (hash_comparator + hash_validator + map_config_generator); (4) end-to-end validation (warden_analyzer Tool 5); (5) interactive visualization tools (image_inspector, minimap_zone_selector, minimap_view_mode, match_preview)
- Primary user: developer running pipeline locally; run when iterating on a new video or re-running prior step
- Tooling is also reference impl for mobile detector port: `run()` detection loop + `identify_map()` are exact logic to port to mobile (TypeScript/Kotlin)
- Pipeline goal success criteria: 100% black-screen transition detection with 0 false positives; 100% map ID on training set; ≥95% (target 100%) on unseen test set; reproducibility across sessions/players; all validated via Tool 4 reports

## Tech Stack
- Python 3.8+ throughout
- FFmpeg via subprocess for I-frame extraction (NOT OpenCV for video decode in pipeline path); OpenCV used for image processing only
- No UI in core pipeline (CLI tools); tkinter GUI for interactive tools
- Core deps: `opencv-python>=4.8,<5`, `numpy>=1.24,<2`, `pyyaml>=6.0,<7`, `imagehash>=4.2,<5` (pulls Pillow + scipy), `Pillow>=10.0` (image_inspector), `opencv-python-headless>=4.8` (image_inspector requirements), `questionary>=2.0,<3` (TUI launcher)
- Module layout: each tool standalone CLI script in `tools/` OR sub-package `tools/<tool>/` with `__main__.py`+`app.py`+helpers; shared helpers in `utils/` (`utils/video.py`, `utils/image.py`, `utils/config.py`, `utils/format.py`); config in `config/config.yaml`; output in `output/`; shared interactive widgets in `tools/common/` (e.g. `video_player.py`)
- Command surface: argparse (NOT Typer/click); consistent conventions — positional `video`, `-o/--output-dir`, `-c/--config` (default `config/config.yaml`), `--threshold`, `--profile`, `--roi`; mutually-exclusive groups for input modes
- `sys.path.insert(0, ...)` pattern: each tool inserts project root into path to allow `utils.*` imports
- No automated test framework in repo; manual smoke tests; pure functions testable in isolation but no harness exists; introducing a framework would exceed scope of any individual sprint item
- All shared utils stateless pure functions (np in → np out); no classes (Tk-based interactive tool `minimap_zone_selector` is the only stateful UI; all other tools CLI)
- Monorepo target: apps/tooling joins as Python workspace member via uv (see `05-architecture-cross-cutting.md`)

## Output & Naming Conventions
- Output folder: per-video subfolder via `os.path.splitext(os.path.basename(video))[0]` appended to output_dir (decided in `video-named-output-subfolders` spec, default behavior, no toggle); BSD adopts this; `bsd_roi_debugger.py` does NOT (intentional carve-out)
- Tool 5 output: `output/warden_<video_stem>/` containing only score frames + `rounds.json` + optional `unrecognized/<score_stem>_roi.png`
- Frame filename convention from Tool 1/BSD: `{timestamp}_{type}_{seqnum}.png` e.g. `00m14s_start_001.png`; seqnums global chronological
- ROI convention: ROIs defined at reference resolution 1920×1080 in `config.yaml` as `{name, x, y, width, height}`; scaled at runtime via `utils/image.py:scale_roi(roi, scale_factor)` to processing/source resolution
- Reference-resolution scaling math: `scale_x = REF_W / video_w`, `scale_y = REF_H / video_h`; canvas/image coords → reference coords via `round(coord × scale)`

## Shared Utilities (used across all tools)
- `utils/image.py` (stateless pure): `extract_roi`, `to_grayscale`, `downscale` (aspect-preserving NOT for fixed-canvas), `scale_roi`, `find_text_anchor`, `has_white_pixels`, `is_black`, `has_team_color`, `apply_threshold` (Otsu)
- `utils/video.py`: `extract_iframes_scaled()` (single-pipe FFmpeg `-skip_frame nokey` + timestamp parsing on stderr via background thread), `get_video_info() -> (w,h)`, `extract_frame_at_timestamp()`, `extract_frames_at_interval`, `get_keyframe_timestamps`, `get_gop_interval`, `check_ffmpeg`
- `utils/config.py`: `load_config()`
- `utils/format.py`: `format_timestamp()` (extracted from triple-duplication)
- Generator pattern: `extract_iframes_scaled()` yields `(frame, timestamp)` tuples to avoid loading whole video; same frame reused for both detection and inline map-ID (zero extra I/O)

## Pipeline Order & Tool Inventory
- Sprint plan (project-sprint.md): Tool 1 Black Screen Detector → extracted frames; Tool 2 Frame Labeling → organized labeled folders; Tool 3 Pixel Finder → map-id JSON; Tool 4 Validation → accuracy reports
- Realized inventory expands beyond original 4-tool plan: Tool 1 game_detector / BSD, Tool 2 frame_labeler, Tool 3 map_config_generator (later evolved to hash_comparator/hash_validator), Tool 4 hash validation, Tool 5 warden_analyzer (round analyzer, end-to-end), plus dev/diagnostic tools (image_inspector, bsd_roi_debugger, points_state_detector) and visualization (minimap_zone_selector, minimap_view_mode, match_preview)
- Original "Tool 3 Discriminating Pixel Finder" superseded by hash-based approach (map_config_generator + hash_comparator) — sprint tracker not yet updated to reflect actual implementation path

## TUI Launcher (`wardentooling.py`)
- File at project root; single entry point `python wardentooling.py`
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
- Status: Completed
- Out of scope: modifying underlying tool scripts, `pyproject.toml` packaging, shell aliases, GUI beyond terminal TUI
- Future considerations (deferred): `--no-tui` headless flag mirroring underlying tool args for scripting; "new source" extension to non-video inputs (Tool 2 source dir, Tool 3 images dir)

## Black Screen Detector (BSD) — `tools/black_screen_detector.py`
- Position in pipeline: video file → BSD round segmentation → per-round outputs (end-of-round PNGs, start-of-round PNGs, pre-end snapshots, miss reports)
- BSD is reference impl for the same algorithm intended to run on mobile; threshold/ROI values tuned here transfer directly to mobile
- Detection driven by ROI zones: `minimap` (top-left), `map_name` (top-center), `vertical` (vertical strip), `team_bar` (bottom 65px wide center bar), `points` (small score region near top)
- End-of-round detection (`is_end_loading`): all three of minimap + map_name + vertical simultaneously black
- Start-of-round detection: minimap + vertical both transition from black → non-black (map_name deliberately excluded; the original `all_black` → `is_end_loading` rename was tied to a fix where some videos start mid-loading with bright map_name)
- Three-state machine: `undetermined` (initial — no assumption from first frame), `waiting_for_end` (in-game), `waiting_for_start` (loading/lobby); rejected earlier two-state design (using only `minimap` ROI to assume initial state) — misclassified lobbies with black sky
- `start_confirm_frames` (default 2): consecutive non-black frames before firing start event (suppresses transient flickers); `saw_black_in_wait` gate ensures we witnessed loading screen before accepting a start
- `skip_until` mechanism: after end detection, skip ~15s of frames to avoid duplicate detections from consecutive loading screens
- `detection_seq`: monotonic sequence counter for unique filenames
- Dual-state recovery: while in `waiting_for_end`, also monitor for start-like transitions (and vice versa); when fired, emit RECOVERY event AND log `miss_report` entry — solves cascading missed detections
- Miss report: `[{type: "missed_end"|"missed_start", window_start, window_end}]`; window bounded by last known event and capped at `max_game_duration` (~600s); printed in summary in both MMmSSs and raw seconds (paste directly into ROI debugger `--range`)
- `run()` returns 4-tuple `(exported, frame_count, profile_stats, miss_reports)`
- Pre-end snapshot: at `end_timestamp - pre_end_offset` (default 10s) per end detection; named `MMmSSs_end-10s_NNN.png`; skipped (not clamped) if pre_end_ts < 0 or earlier than `last_event_timestamp + skip_duration`
- Status: Not Started in project-sprint, but reference impl for mobile, well-iterated

## BSD Algorithm Iterations
- v0: ffprobe enumerates all I-frame PTS timestamps → ffmpeg pipes full-resolution I-frames → per-frame downscale + grayscale + ROI black check; two-state machine assuming initial state
- "neutral-start + vertical-ROI": fixed false starts in lobbies with black sky by introducing `undetermined` initial state and requiring both minimap AND vertical non-black for start
- "profiling": added `--profile` per-phase timing (ffprobe_info, ffprobe_keyframes, ffmpeg_read, downscale, grayscale, roi_check, frame_copy, imwrite); revealed FFmpeg I/O dominated wall time (~93%)
- "single-pass optimization": replaced two-pass with one ffmpeg pass at 360p using `-vf showinfo,scale=-1:H`; threading reads stderr for `pts_time:` regex while main thread reads scaled BGR24 frames from stdout via `queue.Queue`; ~12x reduction in pipe bandwidth; full-resolution re-extraction deferred to post-loop batch via `extract_frame_at_timestamp` (input-seek `-ss` before `-i`)
- "undetermined-start fix": renamed `all_black` → `is_end_loading`; in `undetermined` state, track `start_rois_black` (minimap+vertical only) independently from `is_end_loading` (first reproducer: astera.mp4 startLoading at ~14s)
- "dual-state detection": after observing cascade-failure modes in frozen.mp4 and lvlaste.mkv, added recovery branches in both wait states with miss-report logging; introduced golden JSON fixtures (`tests/fixtures/astera_expected.json`)
- "adaptive frame sampling" (debugger only): MKV files with large GOPs (~8s) yielded too few frames; added `get_gop_interval` (median of keyframe spacings via ffprobe `-read_intervals`); when GOP > 2s, switch to interval mode (one frame per ~2s) with hybrid I-frame snapping (within `snap_tolerance` ~0.5s); deduplicate
- "two-pass team-bar prescan": when adaptive interval mode generalized to main BSD, large-GOP videos spawned ~2000 per-frame ffmpeg subprocesses; pass 1 single-pipe I-frame scan classifies frames in/out-of-game via `team_bar` ROI HSV-saturation check (in-game S=136-156 vs scoreboard/loading S=50-54; threshold ~90); pass 1 collects transitions; `build_scan_windows` pads each transition (~30s) and merges overlaps; pass 2 runs interval extraction only inside windows → >5x speedup; if prescan finds 0 transitions, fallback to whole video
- "pre-end frame export": paired snapshot at `end - pre_end_offset`
- "points white detection" (alternative classifier): standalone parallel tool `tools/points_state_detector.py` that classifies every frame as in-game/lobby via white-text presence in `points` ROI (HSV S<=12, V>=230, white-pixel ratio >= 5%); independent of catching a specific black frame, so naturally handles high-GOP videos without two-pass; intended for direct comparison, not yet a replacement

## ROI Debugger (`tools/bsd_roi_debugger.py`)
- Standalone CLI for ROI/threshold tuning and investigating false positives/negatives
- Inputs: video, `--range START:END` (supports open-ended `:N` and `N:`), `-o output dir`, `-c config`, `--threshold` override
- Per-frame output: console line with timestamp + each ROI mean brightness + black/not-black verdict + overall ALL BLACK / NOT ALL BLACK with failing ROI names; annotated PNG per frame at processing resolution (360p) with colored rectangles (green=black/pass, red=not-black/fail) and ROI-name + brightness labels
- Adaptive frame sampling integrated: probes GOP via `get_gop_interval`, prints "Sampling: I-frame mode" or "Sampling: interval mode (GOP=Xs > 2.0s, extracting every 2.0s)"
- Iterates `extract_iframes_scaled()` and filters by range in consumer (early break)

## Hybrid Game Detector (`tools/game_detector.py`)
- Supersedes `points_state_detector.py` and `black_screen_detector.py` (kept as fallback/reference; eventual move to `tools/legacy/` deferred)
- Approach: white-pixel detection on a HUD text ROI to drive 2-state machine (`not_in_game` / `in_game`); on confirmed end transition, queue a score-screen frame extraction at fixed offset
- Replaces team-bar prescan + black-screen detection (dropped — superseded by points/KDA white detection)
- State machine: `start_confirm_count` (2 frames) and `end_confirm_count` (3 frames) filter transient flicker
- Score screen capture: extract a full-resolution I-frame at `last_in_game_timestamp + score_offset` (default 14.5s); rationale = last in-game I-frame can lag actual end by up to ~9s GOP, then 5s team-only screen; 14.5s lands inside 10s individual+team score window
- Output: `MMmSSs_type_seq.png` PNGs (type ∈ start/end/score) into video-named subdir under output dir; shared `format_timestamp()` extracted to `utils/format.py`
- CLI: positional video, `-o` output, `-c` config, `--profile`; no `--roi` (ROI hardcoded to HUD KDA region)
- Edge cases: video that ends mid-game (warn, no score export), score timestamp past end-of-video (catch ffmpeg error, log warning rather than crash), 0 transitions (clean exit)
- ROI evolution: original `points` ROI (tiny 6x15px @1080p, top-center near timer) — failure: ROI sat next to colored objective icons (B/C capture points); on certain I-frames the 4x10px @720p crop landed on saturated icon colors → false ends in `lvlaste.mkv` at 26m31s/31m31s/39m01s
- Decision: switch to `kda` ROI (10x16px @1080p, bottom HUD); 7x11px @720p still sufficient for white-text detection; KDA known transient occlusion (killcam, VFX, victory) filtered by 3-frame end confirm window
- Config-section name kept as `points_detection` deliberately even after KDA switch — thresholds are generic white-text params, not ROI-specific
- HUD verifier: KDA ROI alone produces false positives on score screens (background bright enough to pass white-pixel HSV thresholds; e.g. `21m10s_end_008` had gray_mean=155 in notkda region vs 22-68 during real gameplay); fix = AND-gate `white_detected` with brightness check on `notkda` ROI (dark HUD background immediately right of KDA digits); frame counts as in-game only if KDA has white pixels AND notkda gray-mean is below `hud_brightness_max` threshold
- Gray-mean over notkda chosen instead of HSV white-ratio: simpler, sufficient
- Threshold tunable per-map via config; gameplay/score-screen brightness gap on tested footage wide enough that one global threshold works; failure mode (future map with bright HUD background in notkda) documented as risk

## Frame Labeler (Tool 2) — `tools/frame_labeler.py`
- Status: Done; tkinter GUI; scope expanded from manual to full GUI
- Consumes Tool 1 output dir; recursive glob `**/*score*.png`; user keystroke labels score frame into one of 14 per-map dirs; auto co-exports start+end frames linked by sequence number
- Pairing rule: for `score_P`: start = max seq among starts with seq<P; end = max seq among ends with start_seq<seq<P
- Output: flat in `labeled/<map>/` named `{counter:03d}_{type}.png`; per-map counter; undo removes all three files
- Grouped export adds: `parse_seq_num(filename) -> int|None` (regex `_(\d+)\.png$`), `find_linked_frames(score_path) -> (start_path, end_path)` (scans `os.path.dirname(score_path)` not source root), `next_game_counter(dest_dir)` (counts `*_score.png` for per-map counter robust to undo)
- Modified `_label_current()` copies all three (score+start+end) with names `{counter:03d}_{type}.png`; missing start/end → console warning, copy what exists, do not block; `_last_action` becomes list of dest paths
- Modified `_undo()` iterates list and removes all copied files
- `shutil.copy2` (non-destructive); source files preserved
- Why grouped export: Tool 3 hashing experimentation needs all three frame types (start/end/score) so any combination can be tried without re-labeling
- Map labels (canonical, 14): `MAP_LABELS = [horizon, engine, outlaw, ceres, artefact, silva, bastion, polaris, coliseum, the_cliff, helios, atlantis, the_rock, lunar_outpost]` at `tools/frame_labeler.py:19-34` — single source of truth, do NOT duplicate; minimap-zone-selector and minimap-view-mode import from this list
- Status: completed (grouped-export spec)

## Map Config Generator (legacy) — `tools/map_config_generator.py`
- Purpose: produce `map_config.json` (portable map-identification fingerprint config consumed by mobile)
- Inputs: `config/config.yaml` (`map_identification` section: `roi`, `canvas_size`, `hash_size`, `collision_threshold`, later additions `shift_tolerance`, `recognition_threshold`, `text_anchor_width`, `hash_method`, `tile_cols`); manual ROI coordinates at 1920×1080; reference videos OR pre-extracted PNGs per map subdirectory
- Pipeline: extracts I-frames from reference videos OR accepts pre-extracted images; crops map-name ROI; runs standard canvas pipeline (crop → grayscale → 64×64 resize via `cv2.INTER_LINEAR`/`INTER_AREA`); generates 64-bit phash via `imagehash.phash(PIL.Image.fromarray(gray), hash_size=hash_size)`; checks Hamming-Distance collisions; writes JSON
- Output schema (fields): top-level `roi: {x, y, width, height}`, `canvas_size: int`, `hash_size: int`, `hash_method: string` ('dhash'/'ahash'/'phash'), `tile_cols: int`, `maps: {map_name: hex_hash_string}`; later evolution added `reference_resolution` echo and `text_anchor_width`
- Default output path: `output/map_config.json`; written via `json.dump(..., indent=2)`
- Regenerated on demand via `python tools/map_config_generator.py --images DIR` or `--video MAP PATH [--video MAP PATH …]` with optional `--preview` (writes 64×64 grayscale `preview_<map>.png` per map for visual verification) and `-o`/`-c`
- Validation: collision check via Hamming Distance — warns if any pair below `collision_threshold` (default 12); collisions printed to stderr with sorted pairwise distances; collision check serves as built-in self-test
- Hash internals: `imagehash.phash()` internally resizes to `(hash_size*4)²` before DCT; canvas at 64×64 ensures downscale rather than upscale
- Source-resolution extraction: video input mode pulls I-frames at native resolution (NOT downscaled like BSD) — hash quality depends on crisp text in ROI
- Coexists with newer `hash_comparator.py`; not unified to avoid breaking legacy path
- Status: completed

## Hash Comparator (Tool 3) — `tools/hash_comparator.py`
- Purpose: from labeled per-map start/end/score frames produce (a) comparative report of hash methods/ROIs and (b) production `map_config.json` containing reference hashes
- Replaces a prior pixel-by-pixel approach (rejected: too sensitive to background variation behind HUD transparency)
- Multi-hash comparison via `imagehash`: aHash, dHash, pHash — all return `ImageHash` supporting `-` operator for Hamming distance
- Pipeline per frame: `downscale → scale_roi → extract_roi → (optional anchor crop) → to_grayscale → (optional Otsu threshold) → tile_into_canvas → compute_hash`
- Median/mode hash across multiple frames per map used as representative reference; intra-map hash variance exposed as stability diagnostic
- Collision detection: per-method, all pairwise Hamming distances; flag pairs below `collision_threshold`
- ROI strategies tested: `map_name_hud` (HUD text zone, present on every in-game I-frame) vs score-screen map zone (more stable but depends on score capture)
- Optional resolution sweep: when enabled, repeats hash gen at e.g. [1080,720,540,360] and includes resolution as a report dimension; default disabled
- Auto-selection: pick (roi, resolution, method) tuple with highest minimum pairwise distance ("best separation"); writes that combo into `map_config.json`
- Override: `--force-method` CLI flag and `preferred_method` config key bypass auto-selection for the `map_config.json` write only — comparison report still runs all methods. CLI > config > auto. Rationale: pHash optimizes training-frame metric but proved cross-video inconsistent (same map `the_cliff` hashed dist=0 with dhash but dist=90 with phash on a different recording)
- `--preview` CLI flag: writes processed canvases as PNGs for visual inspection
- Tool 2 dependency: `frame_labeler.py` extended from score-only to also label `*_start*` / `*_end*` frames so Tool 3 has complete training data; labeled output structure `<output>/labeled/<map_name>/`

## Map-Name Anchor Sub-ROI
- Problem: HUD text is sometimes "Silva", sometimes "Silva - BO3" / " - BO5"; suffix bleeds into hash → unstable hashes for same map across contexts → collisions / false negatives
- Solution: scan the cropped ROI column-by-column for the first column containing a white pixel (HSV whiteness check identical to `has_white_pixels` thresholds), then crop a fixed-width sub-ROI starting at that anchor; width sized to fit shortest map names (Silva, Ceres) and exclude BO3/BO5 suffix
- New util: `find_text_anchor(bgr_crop, sat_max, val_min)` in `utils/image.py`; vectorised with numpy column-any over HSV mask; returns -1 if no white col found
- Wired into `build_canvases()` between `extract_roi` and `to_grayscale`; threaded through `run_comparison` → `main` (read `text_anchor_width` from config)
- Anchor width expressed at 1080p reference and scaled proportionally `int(width * fh/1080)` like other ROIs; `tile_cols` continues to apply on resulting sub-ROI
- Behaviours: anchor not found → frame skipped silently with stderr warning (no fallback to full ROI by design); sub-ROI clamped to right edge if `anchor_x + width` overflows; sub-ROI < 2px wide → skipped (degenerate hash)
- Backward compatible: `text_anchor_width=None`/0/absent disables the feature, preserving full-ROI behaviour

## Threshold-Hash Preprocessing (Otsu Binarization)
- Hypothesis: binarize grayscale crop via `cv2.THRESH_BINARY + cv2.THRESH_OTSU` to remove background brightness variation behind semi-transparent HUD
- New util: `apply_threshold(gray)` in `utils/image.py`; threaded through both training (`hash_comparator.build_canvases`) and runtime (`warden_analyzer.identify_map`) so reference and inference pipelines stay byte-identical
- Config flag `threshold_hash` under `map_identification`; consistency between generation and inference is mandatory (mismatch = bad accuracy)
- EMPIRICAL OUTCOME (negative result): Binarization is HARMFUL for perceptual hashing on this use case — dhash/phash rely on pixel gradients, Otsu destroys gradient information; the anchored ~34×15px crop @720p is also too small for reliable bimodal histogram splitting. Tested on 10 labeled maps with dhash + 52px text anchor: `threshold_hash:true` → min dist 0, 3 collisions; `threshold_hash:false` → min dist 21, 0 collisions
- Resolution: default flipped to `false`; plumbing kept (CLI flag, util, config wiring) for future experimentation
- Degenerate Otsu (uniform/black crop) returns valid array (all-0 or all-255) — recognition_threshold gates downstream as `unrecognized`

## Hash Validator (Tool 4) — `tools/hash_validator.py`
- Purpose: regression/coverage check — load `map_config.json`, iterate every `*_start.png`/`*_end.png` in `output/labeled/<map>/`, predict map per frame via shift-tolerant nearest-hash, report per-frame and per-map accuracy
- Reuses `build_canvases`, `hamming_shift_tolerant`, `compute_hash`, `IMAGE_EXTENSIONS` from `hash_comparator.py` via second `sys.path.insert` for `tools/`
- Score frames excluded (`*_score.png`) — Tool 4 measures HUD-based identification, score-screen ID is separate concern
- Maps in `labeled/` not present in `map_config["maps"]` → reported under `no_reference` section, excluded from accuracy math (currently 4 such: `bastion`, `coliseum`, `lunar_outpost`, `the_rock`)
- Prediction logic: lowest `hamming_shift_tolerant` distance wins; alphabetical tie-break; "unknown" threshold optional (omitted in V1)
- Output: `output/accuracy_report.json` with `summary` (overall accuracy, frame counts, evaluated maps, no_reference list), `by_map` (per-map accuracy + frame list with predicted/distance/correct), `no_reference` array
- CLI: `--images`, `--map-config`, `--shift-tolerance` (default 2), `--resolution` (default 720, must match generation resolution), `-o/--output-dir`
- Known gap: `map_config.json` does not store the processing resolution — if Tool 3 is re-run at different resolution, validator must be invoked with matching `--resolution`. Persisting resolution into `map_config.json` is a future enhancement
- Future flag idea: `--fail-on-incorrect` for CI gating
- Goal: as new labeled frames are added, accuracy stays ≥ target on known maps; regressions caught before they reach mobile runtime

## Pipeline Parity Fix (validator vs generator alignment)
- Failure mode: `hash_validator` was hardcoded to `text_anchor_width=None` and `threshold_hash=False` while reference hashes in `map_config.json` may have been generated with `text_anchor_width=52` / `threshold_hash=True`. Validator therefore hashed a different crop/binarization than generation → near-random distances (300–450 of 1024 max) and 8% accuracy
- Root cause: generation-time pipeline params were read from config but never persisted into `map_config.json`
- Fix: persist `text_anchor_width` and `threshold_hash` into `map_config.json` at generation time (both `hash_comparator.py` and `map_config_generator.py`); validator reads them back and passes through to `build_canvases`
- Persistence rules: `text_anchor_width` written only when truthy (non-zero/non-None); `threshold_hash` written only when True — keeps configs minimal and `.get()` defaults safe
- Backward compat: `.get("text_anchor_width")` → None and `.get("threshold_hash", False)` → False reproduce pre-change validator behaviour
- Patch-mode: `map_config_generator.py` patch-loop preserves these fields when present in existing config but live config takes precedence when re-run
- Existing `map_config.json` must be regenerated after the code fix or accuracy will remain broken — code fix alone is insufficient

## Map ID — Force Method & Threshold Calibration
- Failure mode 1 (auto-selection wrong metric): comparator's `select_best_combination` favours method with largest min pairwise distance on training frames, picking phash@hash_size=16 (min 92 vs dhash min 76); but phash is cross-video inconsistent. Fixed via `--force-method` CLI flag + `preferred_method` config (CLI wins over config wins over auto)
- Failure mode 2 (threshold not tied to hash size): `recognition_threshold` is fixed in `config.yaml` (calibrated for 64-bit hashes at hash_size=8). When hash_size scales to 16 (256-bit), Hamming distances scale ~4×, threshold doesn't, all maps get flagged `unrecognized`
- Fix: scale and persist `recognition_threshold` into `map_config.json` at generation. Formula: `round(base_threshold * (hash_size/8)**2)` (e.g. 8→10, 12→22, 16→40)
- Runtime (`warden_analyzer.py`) reads `recognition_threshold` from `map_config.json` first; falls back to `config.yaml` with stderr warning if absent. Log line shows source for debugging
- Terminology: `recognition_threshold_base` = raw user-controlled value in config.yaml; `recognition_threshold` (no suffix) = scaled value persisted to map_config.json and used at runtime

## Consensus Reference Hash
- Lives in `tools/hash_comparator.py` (algorithm) and `tools/map_config_generator.py` (writer); produces per-map fingerprints stored in `map_config.json` as a single hex string per map (schema unchanged across iterations)
- Problem solved: text anchor sub-pixel shift (1-2px frame-to-frame) makes single-frame or mode-of-frames hash unstable — a 1-bit horizontal shift produces a completely different hash string
- Algorithm: load all labeled frames per map subdirectory → compute perceptual hash per frame (`ahash`/`dhash`/`phash`) → shift-align each subsequent hash to first sample by trying horizontal bit-shifts in `[-shift_tolerance, +shift_tolerance]` (selecting min Hamming distance, reusing `np.roll(bits, s, axis=1)` from `hamming_shift_tolerant`) → per-bit majority vote across aligned samples → single `imagehash.ImageHash`
- Two public functions: `consensus_from_hashes(hashes, shift_tolerance)` (low-level helper, used by both tools) and `consensus_hash(canvases, hash_size, method, shift_tolerance)` (replaces prior `representative_hash()`); single-sample passthrough; empty-list returns None; ties (even-count exact half) round to False
- Config: `map_identification.shift_tolerance` (=2), `map_identification.text_anchor_width` (=52)
- `load_maps_from_images` updated to load all PNG/JPG/JPEG/BMP files per subdirectory (sorted) and return `{map_name: [(fname, frame), ...]}`; `load_maps_from_videos` updated to same uniform shape

## Warden Round Analyzer (Tool 5) — `tools/warden_analyzer.py`
- Status: Implementation Complete; AC unchecked (validation pending real-footage testing)
- Purpose: end-to-end pipeline (video → score screens + map ID + timers); validated reference impl for mobile port
- Combines `game_detector.py` KDA-based round detection state machine with inline map ID using hashing pipeline from `hash_comparator.py`/`hash_validator.py`
- Output: `output/warden_<video_stem>/` containing only score PNGs (NO start/end frames) + `rounds.json` + `unrecognized/<score_stem>_roi.png` (lazy mkdir)
- Map ID inline on downscaled start-candidate frame (already in memory at start confirmation, `.copy()` cached) — zero extra I/O; uses `map_name_hud` ROI from `map_config["roi"]`; `text_anchor_width` active disables `tile_cols`
- Unrecognized criterion: `best_dist >= recognition_threshold` (default 10) OR anchor not found → `map_name = "unrecognized"`; `recognition_threshold` below `collision_threshold` (12) by safety margin
- `rounds.json` schema: top-level `{video, map_config, rounds:[{round, map_name, start_timer, end_timer, score_timer, recognition_distance}]}`; round 1-indexed; timers float seconds; `score_timer` may be null; `recognition_distance` int or null
- `identify_map(frame, ref_roi, ref_hashes, canvas_size, hash_size, hash_method, shift_tolerance, recognition_threshold, text_anchor_width) -> (map_name, best_dist, roi_crop_bgr)` — returns `("unrecognized", None, None)` on bounds error; `("unrecognized", None, roi_crop)` if anchor not found
- Round state dict accumulates `{seq, start_ts, end_ts, score_ts, map_name, best_dist, roi_crop}`; in-progress in `current_round`, completed entries pushed to `pending_rounds`
- Score frame extraction: post-detection batch via `extract_frame_at_timestamp` at `score_offset` (e.g. 14.5s) past `last_in_game_timestamp`; if exceeds video duration → caught (`RuntimeError` / `subprocess.CalledProcessError`), warning, round still in JSON with score_filename null
- Aspect ratio warning if `abs((src_w/src_h) − (ref_w/ref_h)) > 0.01`
- TUI integration: `flow_tool5()` returns `(args, video_path)`; registered in `_TOOL_MAP` as `warden_analyzer`; `_reprompt_source` branch preserves all flags except video path
- End-of-video warnings: stderr for partial start/end confirmation frames at video end, in-game termination → incomplete round discarded
- Future: `run()` detection loop + `identify_map()` are exact logic to port to mobile

## Image Inspector — `tools/image_inspector/`
- Path: package; runnable as `python -m tools.image_inspector [image_path]` or `python tools/image_inspector`
- Purpose: precise HSV color picking and rectangular ROI definition for designing color filters
- Three modes (radio toolbar, default = Color Picker): Color Picker (left-click → HSV at pixel + RGB + image coords + color swatch); HSV Filter Preview (H/S/V center + tolerance + Apply/Clear → grayscale composite outside range, 30% opacity blend); ROI (click-drag → dashed rectangle → status shows x/y/width/height in original-image pixel space)
- Module structure: `__main__.py` (CLI entry, optional PNG arg with file dialog fallback), `app.py` (`InspectorApp(tk.Tk)`, toolbar+canvas), `canvas.py` (`ImageCanvas(tk.Canvas)` zoom/pan/coord mapping), `modes.py` (`ColorPickerMode`, `HSVFilterMode`, `ROIMode` with `activate`/`deactivate`/event handlers), `logger.py` (JSON-lines writer)
- Tech decisions: tkinter (stdlib, zero-install — PyQt rejected as overkill 75-150MB GPL; OpenCV highgui rejected no toolbar; Dear PyGui rejected no built-in image viewer + GPU req); Pillow for PNG load + `ImageTk.PhotoImage`; opencv-python-headless for HSV conversion + `cv2.inRange`; `colorsys` stdlib for single-pixel RGB→HSV (scaled H:0-360, S:0-100, V:0-100)
- HSV scale convention: user-facing H 0-360, S 0-100, V 0-100; converted to OpenCV scale (`H×179/360`, `S/V×255/100`) only for pixel ops; stored in user space in config.yaml
- Coordinate system: all coords reported in original image pixel space regardless of zoom; `canvas_to_image(cx, cy)` mapping; tile-based zoom; pan via `canvas.scan_mark`/`scan_dragto`; min zoom = fit-to-window
- Persistence: `inspector_log.jsonl` next to inspected image; entries `{timestamp ISO8601, image, type:'color_pick'|'roi'|'hsv_filter', data:{...}}`; appendable
- Footprint: ~35-45 MB total added (Pillow ~3-5 MB, opencv-python-headless ~30-40 MB)
- Status: completed

## Minimap Zone Selector — `tools/minimap_zone_selector/`
- Runnable as `python -m tools.minimap_zone_selector --labeled <dir>`
- Purpose: replace unreliable map-name pHash with structurally stable minimap-zone identification; interactive HSV-zoned region matching per map; produces versioned configs for runtime map identifier
- Workflow: developer draws rectangular zones on minimap over stable features (walls/terrain — not players); per-zone HSV center+tolerance; eager validation against ALL labeled images for ALL 14 maps (TP rate same-map, FP rate other-maps); auto-computed weight per zone `tp_rate × (1 − max_fp_rate_other_maps)`; manual override slider; iteratively add zones until 100% accuracy; ID logic = sum of weights of firing zones ≥ `identification_threshold`
- Module structure: `__main__.py` (argparse), `app.py` (`MinimapZoneSelectorApp(tk.Tk)`), `data_loader.py` (`MinimapDataLoader` scans labeled dir, loads PNGs, warns on resolution mismatch), `zone_model.py` (`Zone`, `MinimapConfig` dataclasses, pure `zone_fires()` function), `validator.py` (`ZoneStats`, `MapStats`, `ValidationResult`, `ZoneValidator.compute`), `config_manager.py` (versioned load/save/upsert/delete/clone), `hsv_editor.py` (`HSVEditor` inline form), `stats_panel.py` (overall accuracy, per-zone TP/FP/weight rows with delete + override, per-map accuracy table)
- Reuses `ImageCanvas` from `tools/image_inspector/canvas.py` directly (zoom/pan + overlay redraw)
- Coordinate transform: canvas (minimap-crop space) → full-frame ref coords via `ref_x = round((crop_x + roi.x) × (1920 / frame_w))`
- Coverage simulation: per-map per-zone knockout → recompute weighted sum → fraction-correct → `coverage_sim_accuracy = min(per_knockout_accuracy)`; if 0 or 1 zones, sim equals accuracy (display "N/A")
- Config output: `minimap_identification.configs[]` in `config.yaml` — list of `{id, roi, identification_threshold, maps:{map_name:{zones:[...]}}}`; supports New/Clone/Delete via id-keyed upsert
- Default minimap ROI fallback (illustrative): minimap full gameplay area at `{name:minimap, x:104, y:0, width:234, height:264}` 1920×1080
- Default zone HSV (illustrative): near-white targeting walls — H:0±180, S:0±12, V:100±15, min_ratio:0.3
- Hue wraparound: `cv2.inRange` split into two ranges when h_lo<0 or h_hi>179
- Auto-HSV from drawn ROI: on draw release, sample BGR pixels from displayed frame within rectangle, derive HSV center/tolerance, auto-populate zone, auto-load into HSV editor — eliminates manual dial-in
- Hue uses circular mean (sin/cos → atan2) to handle wraparound at 0°/360° (red-toned regions correctly resolve to ~355°/~5°, not midpoint artefact 180°); hue std uses circular std `sqrt(-2 * log(R))` where `R` = mean resultant length, with `max(R, 1e-9)` guard
- S/V plain mean/std and convert OpenCV (0–255) → user space (0–100); tolerances = `max(MIN_TOL, ceil(std * 1.5))`; floors `_MIN_H_TOL=10`, `_MIN_SV_TOL=5`; sources BGR via `data_loader.get_frames(map)[frame_idx]`; empty-region guard returns safe defaults
- Out of scope: runtime map identifier (only config gen), automatic CV zone discovery, player-dot masking, multi-image averaging, multi-frame averaging across all frames per zone, sampling from non-displayed frames; `min_ratio` still hardcoded at 0.3
- Map labels: imports from `tools.frame_labeler.MAP_LABELS` — single source of truth
- Status: completed

## Minimap View Mode — `tools/minimap_view_mode/` (NOT YET IMPLEMENTED — ready-for-dev)
- Runnable as `python -m tools.minimap_view_mode [--video PATH] [--config PATH]`
- Purpose: ROI authoring + live HUD view-mode preview for replay study; minimap occupies ~3% of screen at native scale; analysts need re-composited HUD focus
- Two functions: (1) ROI authoring per HUD version — per-map minimap ROI + shared `scores`/`health_left`/`health_right`; (2) live frame "shader" with three modes — `normal` (pass-through), `minimap_hud` (minimap ~80% canvas-width centered + scores top-centered + health bars flanking, on black canvas), `minimap_only` (minimap fit-to-canvas aspect-preserved, rest black)
- Module structure: `app.py` (`MinimapViewModeApp(tk.Tk)`, menubar + toolbar + VideoPlayer + right-panel buttons + dirty tracking), `hud_config.py` (`ROIRect`, `MinimapROI {tight, padding_px}`, `SharedROIs`, `HudVersion`, `HudConfigManager` mirroring `minimap_zone_selector/config_manager.py`), `view_renderer.py` (PURE `render(bgr_frame, mode, hud_version, map_name) -> bgr_frame`, no Tk imports, testable in isolation, three mode constants), `roi_overlay.py` (`ROIDrawer` with start_draw/draw_persistent/clear_persistent, click-drag dashed rect via canvas tags `"overlay"`)
- Reuses `tools/common/video_player.VideoPlayer` (pre-existing, committed `5c50d74`); installs shader via `set_frame_processor(fn)`; `canvas_to_video()`/`video_to_canvas()` already implemented
- Video decode: `cv2.VideoCapture` (NOT FFmpeg subprocess) — interactive playback needs cheap random seek + per-frame read on main thread
- Config: new top-level `hud_versions:` key in `config.yaml` (coexists with `roi_zones`; no migration); each version `{id, shared_rois:{scores, health_left, health_right}, maps:{map_name:{tight_roi, padding_px}}}`; padding stored separately
- Padding: 0–N pixels expanding tight rectangle on all sides at render time, clamped to frame bounds
- HUD-version selector: combobox with New/Clone/Delete; mirrors `minimap_zone_selector` UX; first run seeds `v1` in memory, only writes on Save
- Save semantics: explicit Save button; in-memory edits dirty-flagged with `*` in title; close prompt Save/Discard/Cancel
- Map detection: NOT auto-detected — user picks from combobox; auto-detection deferred to match-preview / future tool
- Aspect-ratio mismatch: log warning + continue (mirrors `tools/map_config_generator.py:220-226`)
- Frame-processor hook: `VideoPlayer.set_frame_processor(fn)` takes `(bgr, ts) -> bgr`
- Status: ready-for-dev but Tasks 1–8 all unchecked; AC all unchecked
- Out of scope: timeline match splitting (match_preview's domain), `roi_zones` migration (kept disjoint), video file export, OCR on scores/timer/health, HSV zone defs (stay in `minimap_identification.configs[]`), keyboard shortcuts beyond Space + Esc, automatic ROI detection, undo/redo
- Risks: codec quirks (H.265 / unusual containers may fail to open), VFR seek fuzziness on `CAP_PROP_POS_MSEC`, non-16:9 source ROI mismatch, NumPy compositing fine at 720p but real GLSL shader would matter at 4K (out of scope)

## Match Preview — IN PROGRESS / WIP / DEFERRED
- tech-spec-wip.md status: only Step 1 of 4 complete; Implementation Plan tasks + Acceptance Criteria explicitly "_To be filled in Step 3 after deep investigation._"
- Locked decisions (Step 1): synchronous detection on load with modal progress dialog (background threading deferred); BSD refactor option A — split `run()` into pure `detect_transitions()` + side-effecting `export_frames()`; BSD chosen over `game_detector` (start/end semantics align with match boundaries, recovery windows handle dropped transitions); sidecar `<video>.matches.json` adjacent with mtime+size invalidation; match switch → seek-to-start + pause; reusable `match_detector.py` with CLI; low-confidence labels = "Map N" fallback (NOT "?" or separate group); reuse `tools/common/video_player.py` unchanged
- Sidecar pattern: `{video_mtime, video_size, schema_version: 1, matches: [...]}`; invalidates when mtime or size differs
- Deferred to Step 3: representative-frame sampling offset within segment, confidence threshold (Hamming cutoff) location in config, unpaired start/end handling rules, progress-dialog cancel semantics, sidecar schema version + field list, `detect_transitions()` return shape (dataclass vs dict-list), how `run()` composes the two

## Video-Named Output Subfolders
- Modifies `tools/black_screen_detector.py` only; status completed
- Default behavior — no toggle; uses `os.path.splitext(os.path.basename(args.video))[0]` to derive stem, appends to `output_dir` in `main()` before passing to `run()`
- `bsd_roi_debugger.py` intentionally NOT updated (could adopt later)

## Profiling
- `--profile` flag instruments wall time + per-phase totals + per-frame averages + percentage breakdown (sorted descending); zero overhead when off
- Phases (varies per iteration): `ffprobe_info`, `ffprobe_keyframes` (removed in single-pass), `ffmpeg_read`, `downscale` (removed when frames pre-scaled), `grayscale`, `roi_check`, `frame_copy` (removed in single-pass), `imwrite`, `fullres_extract` (added in single-pass), `prescan` (added in two-pass team-bar)
- Report shows Accounted vs Unaccounted to capture loop overhead
- Non-functional constraint: BSD must process long-form match recordings (multi-hour) in runtime small enough that round segmentation isn't pipeline bottleneck; iterations driven by profile-revealed dominators

## Outputs (Integration Surface)
- Per-round PNGs at full source resolution: end-of-round (`MMmSSs_end_NNN.png`), start-of-round (`MMmSSs_start_NNN.png`), optional pre-end snapshot (`MMmSSs_end-10s_NNN.png`)
- All exports collected as deferred extraction requests `[{timestamp, type, filename}]` during detection loop, then batch-extracted full-res in post-loop phase
- Programmatic outputs from `run()`: exported list, frame_count, profile_stats (or None), miss_reports list
- Console summary: counts per type (starts, ends, pre-end snapshots, recovery events), output dir, exported file list, profile report when `--profile`
- Golden fixture: `tests/fixtures/astera_expected.json` — array of `{filename,type,timestamp}` plus `miss_reports: []`; current known-good baseline is astera.mp4 (clean alternation, 9 starts + 9 ends or 10/10 depending on iteration)
- Consumers: Tool 2 (Frame Labeling) consumes exported PNGs; Tool 3 (Map Identification) consumes end-of-round PNGs; Tool 4 (Validation) consumes both PNGs and timestamps and reuses `utils/video.py` end-to-end; hash comparator/validator consumes labeled directories of per-map frames

## `points_state_detector.py` (parallel classifier)
- Standalone parallel tool that classifies every frame as in-game/lobby via white-text presence in `points` ROI (HSV S<=12, V>=230, white-pixel ratio >= 5%)
- Independent of catching specific black frame, so naturally handles high-GOP videos without two-pass
- Produces same output format as BSD; intended for direct A/B comparison, not yet a replacement
- Now superseded by `game_detector.py` (kept as fallback/reference)

## Tooling Codebase Patterns (Consumed by Detection/Hashing Tools)
- Modular CLI: each tool standalone in `tools/`, `argparse`-based, `sys.path.insert` for `utils/` access
- run()+main() split: core logic returns results, CLI entry parses args
- ROI definitions at 1920×1080 reference, scaled at runtime via `scale_roi()`
- Config-driven via YAML loaded with `load_config()`; CLI args override config (`arg if arg is not None else config.get(...)`)
- Deferred batch extraction: collect `extraction_requests` during I-frame scan, then ffmpeg-batch full-resolution frames at end → minimizes subprocess calls
- File-based I/O between tools: PNG outputs named `MMmSSs_type_seq.png`; labeled frames in `<output>/labeled/<map_name>/`; reports in `output/*.json`
- State machines with confirmation counters (start_confirm/end_confirm) to filter transient signal flicker
- "None = feature disabled" convention for optional pipeline params (`text_anchor_width`, `threshold_hash`) → backward compat free

## Cross-tool Data Flow
- BSD (Tool 1) extracts start/end/score frames → `output/<video_stem>/` flat PNGs `{timestamp}_{type}_{seqnum}.png`; seqnum global, chronological
- frame_labeler (Tool 2) consumes Tool 1 output dir; recursive glob `**/*score*.png`; user keystroke labels score frame; auto co-exports start+end frames; output `labeled/<map>/` named `{counter:03d}_{type}.png`; per-map counter; undo removes all three
- map_config_generator (Tool 3 hashing) consumes labeled directory (subdirs per map) OR direct video files; emits `map_config.json`
- warden_analyzer (Tool 5) consumes raw video + `map_config.json`; emits score frames + `rounds.json` `{video, map_config, rounds:[{round, map_name, start_timer, end_timer, score_timer, recognition_distance}]}`; unrecognized → `unrecognized/<score_stem>_roi.png`
- minimap_zone_selector consumes labeled directory (Tool 2 output) for all per-map images; emits versioned `minimap_identification.configs[]` into `config/config.yaml`
- minimap_view_mode consumes raw video + `config.yaml` `hud_versions[]`; emits new `hud_versions[]` entries
- match_preview consumes raw video + `config.yaml` + `map_config.json`; emits sidecar `<video>.matches.json` next to video

## Tooling Sprint State (per project-sprint.md)
- Tool 1 BSD: Not Started (project-sprint says Not Started; well-iterated reference impl exists in code; sprint tracker not updated to reflect actual state)
- Tool 2 Frame Labeling: Done (full GUI, scope expanded from manual)
- Tool 3 Discriminating Pixel Finder: Not Started — but actual implementation evolved into hash_comparator + map_config_generator (sprint tracker not updated)
- Tool 4 Validation & Accuracy Testing: Not Started — but `hash_validator.py` exists
- Spec-level statuses: warden-tui-launcher (Completed); map-config-generator (completed); warden-round-analyzer Tool 5 (Implementation Complete, AC unchecked); warden-image-inspector (completed); minimap-zone-selector (completed); frame-labeler-grouped-export (completed); video-named-output-subfolders (completed); minimap-view-mode (ready-for-dev, not yet implemented); match-preview (in-progress, Step 1 only — DEFERRED/WIP)
- Pipeline core tools all "Not Started" per project-sprint.md but hashing-based map-id approach evolved separately; original "Pixel Finder" likely superseded — sprint tracker not updated to reflect actual implementation path

## Tooling Risks & Known Issues
- questionary TTY requirement on Windows — silent failure if launched via pipe/redirect; needs proper terminal
- `cv2.VideoCapture` may fail on H.265 / unusual containers; user must transcode; surface clean error
- VFR seek via `CAP_PROP_POS_MSEC` is approximate; exact-frame seek out of scope
- Non-16:9 source aspect ratio: ROIs stored at 1920×1080 may not correspond to sensible HUD layout; warn + continue
- Map-name ROI dimensions may need tuning per-map (text doesn't fill region consistently across all maps); `--preview` flag exists for visual catch
- Hash collision risk: if collisions occur user should adjust ROI to capture more discriminating text OR increase canvas_size
- `score_offset` (14.5s) past `last_in_game_timestamp` can exceed clipped video duration — handled by exception catch, round still in JSON without score_filename
- Rendering compositing in Python/NumPy fine at 720p but inadequate at 4K (out of scope)
- No automated test framework — all tools manually validated
- Imagehash hex_to_hash failure → wrapped in try/except with clear error pointing to map_config corruption (Tool 5 review fix F8)
- showinfo regex `pts_time:(\S+)` is stable across FFmpeg versions but is brittle external contract; mitigation is `queue.get(timeout=10)` raising on silent deadlock
- Frame/timestamp sync risk in raw-pipe approach with B-frame reordering; mitigated via `-vsync 0`
- Reference-frame choice in consensus hash: first sample as alignment reference; if outlier, skews result — mitigation is consistent alphabetical ordering
- `imagehash.ImageHash(bool_array)` constructor varies across versions — needs verification against installed version
- HUD-brightness threshold (`hud_brightness_max`) is global; future map with bright HUD background near KDA could trigger false-end detections — mitigated by config-tunability
- KDA ROI vulnerable to prolonged occlusion (extended killcam, victory cinematics) → could bump `end_confirm_frames` if observed
- Threshold-hash binarization left in codebase as opt-in despite negative empirical result; may revisit if anchor crop is enlarged
- pHash cross-video inconsistency (same map dist=0 vs dist=90 across recordings) is the root reason for `--force-method dhash` operational default
- Known-failure videos used as regression cases: frozen.mp4 (~9min cascade gaps at end_002→start_003 and end_006→start_007), lvlaste.mkv (70min, GOP ~8.3s, missed end at ~17:19s causing jump from start_003 at 10:41 to end_004 at 24:10)

## Adversarial Review Outcomes (preservation of decisions)
- map-config-generator: 14 findings, 7 fixed (resolution validation, aspect ratio check, empty video error, ffmpeg check, INTER_AREA, reference_resolution echo in output, imwrite check), 7 skipped (bare except OK for CLI, duplicate ROI intentional, config validation = trust config, first I-frame OK, threshold semantics correct, no tests = manual per spec, sys.path = project pattern)
- warden-tui-launcher: 10/10 fixed (dead skip_video param removed, KeyError guarded, mode cancel guarded, run_tool returns exit code, recursive scan for videos, code-dir exclusions, sys.executable, image format expansion, source-only re-prompt)
- warden-image-inspector: 15 findings, 13 fixed (missing __init__.py, numpy in requirements, ROI z-order via overlay tag, round() not int() for HSV scaling, clamped logged values, input validation, redraw throttling via after_idle, logger graceful errors, single Tk root, corrupt image handling, HSV scale constants documented, persistent canvas items, custom-pan comment), 2 skipped
- minimap-zone-selector: 15 findings, 7 fixed (coord transform cleanup, zone ID collision, map name parsing, clone from in-memory, stale refs after export, delete persistence, tk.Frame.update shadow), 8 skipped
- frame-labeler-grouped-export: 7/7 fixed
- video-named-output-subfolders: 12 findings, 3 fixed (stale architecture.md refs, ROI loop caching comment), 9 skipped
- warden-round-analyzer: 12 findings, 2 fixed (get_video_info try/except, hex_to_hash try/except), 10 skipped (noise/by-design)
