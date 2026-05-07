## Subsystem Role
- BSD (Black Screen Detector) is the round/segment detection subsystem of `apps/tooling` (Python CLI); segments long EVA match recordings (~2hr) into rounds via loading-screen detection so downstream tools (map identification, frame labeling, validation, hash workflows) operate on per-round artifacts
- Position in pipeline: video file -> BSD round segmentation -> per-round outputs (end-of-round PNGs, start-of-round PNGs, pre-end snapshots, miss reports) -> consumed by map identification (Tool 3), frame labeling (Tool 2), accuracy validation (Tool 4), hash comparator/validator
- BSD is the reference implementation for the same algorithm intended to run on mobile; threshold/ROI values tuned here are meant to transfer directly to mobile

## Toolchain & Architecture
- Python 3.8+ CLI tools under `tools/`, shared stateless utilities under `utils/`, YAML config under `config/config.yaml`
- Video decoding via FFmpeg subprocess (not bindings): OpenCV's VideoCapture cannot selectively decode I-frames; FFmpeg + ffprobe required for keyframe-only iteration
- OpenCV (cv2) only for image processing (resize, grayscale, ROI crop, HSV conversion, drawing, imwrite); NumPy for pixel math; PyYAML for config; argparse for CLI; no external test framework — manual validation against known recordings + golden JSON fixtures
- File layout: `tools/black_screen_detector.py`, `tools/bsd_roi_debugger.py`, `tools/points_state_detector.py`, `tools/hash_comparator.py`, `tools/map_config_generator.py`, `utils/video.py`, `utils/image.py`, `utils/config.py`, `tests/fixtures/*.json`
- Generator pattern: video extractors yield `(frame, timestamp)` tuples consumed by detection loops; profiling via optional `profile_stats` mutable dict threaded through call chain (zero overhead when off)
- Output naming convention: `MMmSSs_type_seq.png` inside per-video subfolder of output dir (types: start, end, pre-end)

## Core Detection Concepts (ROI + Threshold)
- All detection driven by ROI zones defined at 1920x1080 reference resolution in `config/config.yaml`, scaled proportionally to processing height (typically 360p) via `scale_roi()`
- Stateless image helpers in `utils/image.py`: `downscale`, `to_grayscale`, `extract_roi`, `scale_roi`, `is_black` (mean grayscale <= threshold), `has_team_color` (mean HSV saturation > threshold), `has_white_pixels` (HSV S/V mask ratio >= threshold)
- ROI catalog: `minimap` (top-left), `map_name` (top-center), `vertical` (vertical strip), `team_bar` (bottom 65px wide center bar), `points` (small score region near top); each ROI participates in different detection roles
- End-of-round detection (`is_end_loading`): all three of minimap + map_name + vertical simultaneously black
- Start-of-round detection: minimap + vertical both transition from black -> non-black (map_name deliberately excluded; the original `all_black` -> `is_end_loading` rename was tied to a fix where some videos start mid-loading with bright map_name and never go all-black, causing first start to be missed)
- Aspect-ratio validation against 16:9 reference; ROI bounds clamping in `extract_roi` with truncation warnings
- Shared utils designed so Tools 2/3/4 reuse `extract_iframes_scaled`, `extract_frame_at_timestamp`, `downscale`, `extract_roi`, `scale_roi`

## State Machine (Three-State + Dual Detection)
- Three states: `undetermined` (initial — no assumption from first frame), `waiting_for_end` (in-game, looking for end loading screen), `waiting_for_start` (loading/lobby, looking for round start)
- Earlier two-state design (using only `minimap` ROI to assume initial state) was rejected: misclassified lobbies with black sky; the "neutral start" / vertical-ROI iteration introduced the `undetermined` state and added vertical ROI to start detection
- `start_confirm_frames` (default 2): consecutive non-black frames required before firing a start event (suppresses transient flickers); `saw_black_in_wait` gate ensures we witnessed the loading screen before accepting a start
- `skip_until` mechanism: after end detection, skip ~15s of frames to avoid duplicate detections from consecutive loading screens
- `detection_seq`: monotonic sequence counter for unique filenames across event types; preserves filename collision safety
- Dual-state recovery: while in `waiting_for_end`, also monitor for start-like transitions (and vice versa); when fired, emit a `RECOVERY` event AND log a `miss_report` entry — solves cascading missed detections where strict alternation would lose all subsequent events after a single miss
- Miss report: `[{type: "missed_end"|"missed_start", window_start, window_end}]`; window bounded by last known event and capped at `max_game_duration` (configurable, ~600s); printed in summary in both MMmSSs and raw seconds so the user can feed it directly into the ROI debugger `--range` flag
- `run()` returns 4-tuple `(exported, frame_count, profile_stats, miss_reports)`

## Algorithm Evolution (Why Each Iteration)
- v0 (initial BSD): ffprobe enumerates all I-frame PTS timestamps -> ffmpeg pipes full-resolution I-frames -> per-frame downscale + grayscale + ROI black check -> on detection, write previous full-res frame; two-state machine assuming initial state from first frame
- Iteration "neutral-start + vertical-ROI": fixed false starts in lobbies with black sky by introducing `undetermined` initial state and requiring both minimap AND vertical ROIs non-black for start
- Iteration "profiling": added `--profile` flag with per-phase timing (ffprobe_info, ffprobe_keyframes, ffmpeg_read, downscale, grayscale, roi_check, frame_copy, imwrite); revealed FFmpeg I/O dominated wall time (~93% in two FFmpeg/ffprobe calls)
- Iteration "single-pass optimization": replaced two-pass (ffprobe scan + ffmpeg full-res pipe) with one ffmpeg pass at 360p using `-vf showinfo,scale=-1:H`; threading reads stderr for `pts_time:` regex while main thread reads scaled BGR24 frames from stdout via `queue.Queue`; eliminates `ffprobe_keyframes` phase and ~12x reduction in pipe bandwidth; full-resolution re-extraction deferred to post-detection batch via `extract_frame_at_timestamp` (input-seek `-ss` before `-i` snaps to keyframe — exact for keyframe PTS values)
- Iteration "undetermined-start fix": renamed `all_black` -> `is_end_loading` for clarity; in `undetermined` state, track `start_rois_black` (minimap+vertical only) independently from `is_end_loading`, so first event can fire as a start even when `map_name` never goes black (first reproducer: astera.mp4 startLoading at ~14s)
- Iteration "dual-state detection": after observing cascade-failure modes in frozen.mp4 and lvlaste.mkv (one missed end blocks all subsequent detections), added recovery branches in both wait states with miss-report logging; introduced golden JSON fixtures (`tests/fixtures/astera_expected.json`) as regression baseline
- Iteration "adaptive frame sampling" (debugger only): MKV files with large GOPs (~8s) yielded only ~5 frames over a 40s window via I-frame mode, making the debugger ineffective; added `get_gop_interval` (median of keyframe spacings via ffprobe `-read_intervals`); when GOP > 2s, switch to interval mode (one frame per ~2s) with hybrid I-frame snapping (within `snap_tolerance` ~0.5s of an I-frame, snap to that I-frame; deduplicate); main detector path NOT changed by this — debugger only
- Iteration "two-pass team-bar prescan": when adaptive interval mode was generalized to the main BSD path, large-GOP videos spawned ~2000 per-frame ffmpeg subprocesses (~99.6% subprocess overhead, ~700s on a 70min video); pass 1 single-pipe I-frame scan classifies each frame in/out-of-game via `team_bar` ROI HSV-saturation check (in-game bar mean S=136-156 vs scoreboard/loading S=50-54; threshold ~90 separates cleanly); pass 1 collects transition timestamps; `build_scan_windows` pads each transition (~30s either side) and merges overlaps so paired end->start gaps (46-77s) collapse to single windows; pass 2 runs interval extraction only inside windows -> >5x speedup; if prescan finds 0 transitions, fallback to scanning whole video
- Iteration "pre-end frame export": adds a paired snapshot at `end_timestamp - pre_end_offset` (default 10s) per end detection so user can see score progression before the black screen; named `MMmSSs_end-10s_NNN.png`; skipped (not clamped) if pre_end_ts < 0 or earlier than `last_event_timestamp + skip_duration` (clamping risks pulling a frame from a previous round)
- Iteration "points white detection" (alternative classifier): standalone parallel tool (`tools/points_state_detector.py`) that classifies every frame as in-game/lobby via white-text presence in `points` ROI (HSV S<=12, V>=230, white-pixel ratio >= 5%); independent of catching a specific black frame, so naturally handles high-GOP videos without two-pass; produces same output format as BSD; intended for direct comparison, not yet a replacement

## ROI Debugger
- Standalone CLI `tools/bsd_roi_debugger.py` for ROI/threshold tuning and investigating false positives/negatives
- Inputs: video, `--range START:END` (supports open-ended `:N` and `N:`), `-o output dir`, `-c config`, `--threshold` override
- Per-frame output: console line with timestamp + each ROI mean brightness + black/not-black verdict + overall ALL BLACK / NOT ALL BLACK with failing ROI names; annotated PNG per frame at processing resolution (360p) with colored rectangles (green = black/pass, red = not-black/fail) and ROI-name + brightness labels
- Iterates `extract_iframes_scaled()` and filters by range in the consumer (early break)
- Adaptive frame sampling integrated: probes GOP via `get_gop_interval`, prints "Sampling: I-frame mode" or "Sampling: interval mode (GOP=Xs > 2.0s, extracting every 2.0s)"; in interval mode calls `extract_frames_at_interval` with snapping tolerance
- Miss-report output from BSD (printed in raw seconds) is designed to be pasted directly into the debugger `--range` flag for investigation

## Outputs (Integration Surface)
- Per-round PNGs at full source resolution: end-of-round (`MMmSSs_end_NNN.png`), start-of-round (`MMmSSs_start_NNN.png`), optional pre-end snapshot (`MMmSSs_end-10s_NNN.png`)
- All exports collected as deferred extraction requests `[{timestamp, type, filename}]` during the detection loop, then batch-extracted full-res in a post-loop phase via `extract_frame_at_timestamp` (`-ss` input seek)
- Programmatic outputs from `run()`: exported list, frame_count, profile_stats (or None), miss_reports list
- Console summary: counts per type (starts, ends, pre-end snapshots, recovery events), output dir, exported file list, profile report when `--profile`
- Golden fixture: `tests/fixtures/astera_expected.json` (array of `{filename,type,timestamp}` plus `miss_reports: []`) used as regression baseline; current known-good baseline is astera.mp4 (clean alternation, 9 starts + 9 ends or 10/10 depending on iteration)
- Consumers: Tool 2 (Frame Labeling) consumes exported PNGs; Tool 3 (Map Identification) consumes end-of-round PNGs (map name visible); Tool 4 (Validation) consumes both PNGs and timestamps and reuses `utils/video.py` end-to-end; hash comparator/validator consumes labeled directories of per-map frames

## Profiling
- `--profile` flag instruments wall time + per-phase totals + per-frame averages + percentage breakdown (sorted descending); zero overhead when off
- Phases (varies per iteration): `ffprobe_info`, `ffprobe_keyframes` (removed in single-pass), `ffmpeg_read`, `downscale` (removed when frames pre-scaled), `grayscale`, `roi_check`, `frame_copy` (removed in single-pass), `imwrite`, `fullres_extract` (added in single-pass), `prescan` (added in two-pass team-bar)
- Report shows Accounted vs Unaccounted to capture loop overhead; per-frame divisor is `frames_processed` for compute phases and `frame_count` for `frame_copy` (which fires on skipped frames too)
- Non-functional constraint: BSD must process long-form match recordings (multi-hour) in a runtime small enough that round segmentation is not the pipeline bottleneck; iterations were driven by profile-revealed dominators (FFmpeg I/O, then per-frame subprocess spawn for interval mode)

## Consensus Reference Hash
- Lives in `tools/hash_comparator.py` (algorithm) and `tools/map_config_generator.py` (writer); produces per-map fingerprints stored in `map_config.json` as a single hex string per map (schema unchanged across iterations)
- Problem solved: text anchor sub-pixel shift (1-2px frame-to-frame) makes single-frame or mode-of-frames hash unstable — a 1-bit horizontal shift produces a completely different hash string, so mode degrades to picking one arbitrary sample
- Algorithm: load all labeled frames per map subdirectory -> compute perceptual hash per frame (`ahash`/`dhash`/`phash`) -> shift-align each subsequent hash to the first sample by trying horizontal bit-shifts in `[-shift_tolerance, +shift_tolerance]` (selecting min Hamming distance, reusing `np.roll(bits, s, axis=1)` from `hamming_shift_tolerant`) -> per-bit majority vote across aligned samples -> single `imagehash.ImageHash`
- Two public functions: `consensus_from_hashes(hashes, shift_tolerance)` (low-level helper, used by both tools) and `consensus_hash(canvases, hash_size, method, shift_tolerance)` (replaces prior `representative_hash()`); single-sample passthrough; empty-list returns None; ties (even-count exact half) round to False
- Config: `map_identification.shift_tolerance` (=2), `map_identification.text_anchor_width` (=52)
- `load_maps_from_images` updated to load all PNG/JPG/JPEG/BMP files per subdirectory (sorted) and return `{map_name: [(fname, frame), ...]}`; `load_maps_from_videos` updated to same uniform shape (single-entry list)
- Validation: regression compare `map_config.json` schema preserved; accuracy report (`hash_validator.py` baseline 81.25%) should hold or improve

## Cross-cutting integrations
- BSD reads ROI zones (minimap, map_name, vertical, team_bar, points) and detection thresholds from `config/config.yaml`; ROI coordinates are at 1920x1080 reference, scaled at runtime — per-map overrides are managed via `map_config.json` (cross-link to map-id subsystem)
- BSD outputs feed downstream consumers: per-round PNGs -> Tool 2 (frame labeling), Tool 3 (map identification via end-of-round map_name), Tool 4 (validation/accuracy reporting), hash comparator/validator workflows; miss reports + raw timestamps feed the ROI debugger
- Shared `utils/video.py` (`extract_iframes_scaled`, `extract_frame_at_timestamp`, `extract_frames_at_interval`, `get_video_info`, `get_keyframe_timestamps`, `get_gop_interval`, `check_ffmpeg`) and `utils/image.py` (`downscale`, `to_grayscale`, `scale_roi`, `extract_roi`, `is_black`, `has_team_color`, `has_white_pixels`) reused across all tooling apps
- Consensus reference hash bridges BSD and the game-detector / map-id subsystem (other distillate group): the per-map consensus hashes in `map_config.json` are consumed by `hash_validator.py` to identify maps from end-of-round frames produced by BSD
- `points_state_detector.py` is a parallel classifier intended as a robustness alternative to BSD for high-GOP videos; same output format enables direct A/B comparison

## Open Questions / Known Issues / Deferred
- `waiting_for_end` fires on any single frame where `is_end_loading` is True (no transition check), unlike `undetermined` which checks `not prev_is_end_loading and is_end_loading` — flagged for future improvement, not addressed
- Recovery start detection in `waiting_for_end` uses single-frame detection (no `start_confirm_frames`) — consistent with `undetermined` but may need confirmation if false positives appear
- Threshold tuning is empirical (start conservative, increase as needed); no automated tuning
- Aspect-ratio assumption: ROI scaling assumes 16:9 source; non-1080p reference resolutions require config update
- showinfo regex `pts_time:(\S+)` is stable across FFmpeg versions but is a brittle external contract; mitigation is `queue.get(timeout=10)` raising on silent deadlock
- Frame/timestamp sync risk in raw-pipe approach with B-frame reordering; mitigated via `-vsync 0`
- Reference-frame choice in consensus hash: first sample as alignment reference; if outlier, skews result — mitigation is consistent alphabetical ordering
- `imagehash.ImageHash(bool_array)` constructor varies across versions — needs verification against installed version
- Future enhancements: parallelize batch full-res extraction with `ThreadPoolExecutor`; add `--mode iframe|interval|auto` CLI flag for debugger; recovery/miss logic for `points_state_detector`; multi-method hash ensemble; multi-ROI fingerprint; pre-normalize anchor crop width more aggressively if shift variance exceeds tolerance
- Out of scope across specs: any GUI, batch/directory processing, automated test harness/CI, memory profiling, OCR/score reading, replacing BSD with `points_state_detector` (parallel only), team colors beyond orange/blue
- Known-failure videos used as regression cases: frozen.mp4 (~9min cascade gaps at end_002->start_003 and end_006->start_007), lvlaste.mkv (70min, GOP ~8.3s, missed end at ~17:19s causing jump from start_003 at 10:41 to end_004 at 24:10)
