# Architecture — apps/tooling

> Part `tooling` (Python CLI). Imported from the legacy `Warden-tooling` repo at Phase 1 with full git history (64 commits). Joins the monorepo as a **uv workspace member** with a thin Turborepo `package.json` wrapper for unified `pnpm test`/`pnpm build` orchestration.

## Executive summary

Desktop video analysis pipeline. Two purposes:

1. **Validate the detection algorithms** (black-screen detection, KDA / map-bar detection, perceptual-hash map ID) on desktop, before they ship to mobile. Threshold values, ROI zones, and HSV bands tuned here transfer directly to the mobile pipeline.
2. **Generate the map identification dataset** — emit a [`map_config.json`](../contracts/map-config.schema.json) of perceptual hashes per EVA map. Mobile bundles or fetches this and uses it to identify the map shown in a clip without running OpenCV on device.

The repo is a CLI lab — five "user-facing" tools (numbered 1–5) plus three diagnostic dev tools, all reachable from a single questionary-driven TUI launcher.

## Architecture pattern

**Modular CLI pipeline + interactive launcher.** Each tool is an independent CLI entry point that reads from shared `config/config.yaml` and reuses `utils/{video,image,config,format}.py`. Tools are designed to compose sequentially but are individually invokable.

```
              ┌─────────────────────────────────┐
              │  wardentooling.py  (TUI)        │
              │  questionary launcher,          │
              │  last-run persistence to        │
              │  .warden_last_run.json          │
              └────────────────┬────────────────┘
                               │  subprocess.run
       ┌───────────────┬───────┴────────┬───────────────┬────────────────┐
       ▼               ▼                ▼               ▼                ▼
┌─────────────┐ ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│   Tool 1    │ │   Tool 2    │  │   Tool 3    │  │   Tool 4    │  │   Tool 5    │
│ game_       │ │ frame_      │  │ map_config_ │  │ hash_       │  │ warden_     │
│ detector    │ │ labeler     │  │ generator   │  │ validator   │  │ analyzer    │
└──────┬──────┘ └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
       │               │                │                │                │
       ▼               ▼                ▼                ▼                ▼
   PNG frames     Labeled dirs   map_config.json   Accuracy report   Per-round CSV/JSON
                                 + previews        + collisions      + thumbnails

  Dev tools: tools/bsd_roi_debugger.py, tools/points_state_detector.py,
             tools/image_inspector (module), tools/minimap_zone_selector (module)
```

## Tooling pipeline (intended sequence)

| #   | Tool                                                                     | Reads                                       | Writes                                                 |
| --- | ------------------------------------------------------------------------ | ------------------------------------------- | ------------------------------------------------------ |
| 1   | [game_detector.py](../apps/tooling/tools/game_detector.py)               | Raw EVA session video                       | End-of-round + start-of-round PNG frames               |
| 2   | [frame_labeler.py](../apps/tooling/tools/frame_labeler.py)               | Tool 1 output                               | Labeled directory tree (one folder per map)            |
| 3   | [map_config_generator.py](../apps/tooling/tools/map_config_generator.py) | Labeled images **OR** per-map source videos | `map_config.json` (cross-language contract)            |
| 4   | [hash_validator.py](../apps/tooling/tools/hash_validator.py)             | `map_config.json` + ground-truth labels     | Accuracy report + per-pixel/per-map confidence margins |
| 5   | [warden_analyzer.py](../apps/tooling/tools/warden_analyzer.py)           | Raw video + `map_config.json`               | Full pipeline run — round timestamps + identified maps |

## Technology stack

| Category        | Tech          | Version                                                      | Purpose                                                                                                                                      |
| --------------- | ------------- | ------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------- |
| Language        | Python        | ≥3.11 (per [pyproject.toml](../apps/tooling/pyproject.toml)) |                                                                                                                                              |
| Package manager | uv            | n/a                                                          | Workspace member of root `pyproject.toml`                                                                                                    |
| CV              | opencv-python | ≥4.8, <5                                                     | Image processing only — resize, ROI, grayscale, HSV. Not for video decoding.                                                                 |
| Hashing         | imagehash     | ≥4.2, <5                                                     | ahash / dhash / phash / whash perceptual hashes                                                                                              |
| Numeric         | numpy         | ≥1.24, <2                                                    | Frame arrays                                                                                                                                 |
| Config          | pyyaml        | ≥6.0, <7                                                     | YAML config loader (single `config/config.yaml`)                                                                                             |
| TUI             | questionary   | ≥2.0, <3                                                     | Interactive launcher                                                                                                                         |
| Schema          | jsonschema    | ≥4.23.0                                                      | (Implicit) validates emitted JSON against `contracts/*.schema.json`                                                                          |
| Test            | pytest        | ≥8.0 (dev extras)                                            | `uv run pytest` — wired through `pnpm --filter tooling test`                                                                                 |
| Video decode    | FFmpeg        | system dependency                                            | I-frame-only extraction via subprocess (`-skip_frame nokey` + `showinfo`). OpenCV's `VideoCapture` cannot selectively decode keyframes only. |

## Key configs (`config/config.yaml`)

The single source of tunable parameters. Excerpt (full file is ~150 lines covering map fingerprints):

| Section                                               | Purpose                                                                                                                                     |
| ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `black_detection.brightness_threshold` (15)           | 0-255 mean-pixel cutoff per ROI to call a frame "black"                                                                                     |
| `black_detection.pre_end_offset` (10.0s)              | Offset before end blackscreen for score-screen capture                                                                                      |
| `black_detection.skip_duration` (15.0s)               | Skip after end detection to avoid duplicate triggers from loading-screen clusters                                                           |
| `black_detection.start_confirm_frames` (2)            | Consecutive non-black frames required to confirm a start                                                                                    |
| `black_detection.roi_zones[]`                         | Named rectangles at 1920×1080 reference: `minimap`, `map_name`, `vertical`, `team_bar`, `personnalbar`, `points`, `kda`, `notkda`           |
| `color.{bleu,orange,white}`                           | HSV centres for team-bar colour detection                                                                                                   |
| `map_identification`                                  | pHash params: `canvas_size: 128`, `hash_size: 16`, `collision_threshold: 12`, `text_anchor_width: 52`, `tile_cols: 3`, `shift_tolerance: 2` |
| `map_identification.preferred_method`                 | `dhash` (also computes ahash + phash for diagnostics)                                                                                       |
| `minimap_identification.configs[].maps.<map>.zones[]` | Per-map HSV-banded discriminator zones (per-zone H/S/V centre + tolerance + min_ratio + weight)                                             |

ROI coordinates are defined at the **reference resolution (1920×1080)** and scaled proportionally for other source resolutions in [utils/image.py:scale_roi](../apps/tooling/utils/image.py).

## Module map

| File                                                                             | Role                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| -------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [wardentooling.py](../apps/tooling/wardentooling.py)                             | TUI launcher. Per-tool flow functions (`flow_tool1` … `flow_tool5`) collect args via `questionary`, build `[*args]` lists, run via `subprocess.run([sys.executable] + args, cwd=PROJECT_ROOT)`. Persists last successful run to `.warden_last_run.json` and offers "Run with same args" / "Run on new source".                                                                                                                                                                                                                                             |
| [tools/game_detector.py](../apps/tooling/tools/game_detector.py)                 | KDA / hybrid round detector.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| [tools/black_screen_detector.py](../apps/tooling/tools/black_screen_detector.py) | Standalone BSD with 3-state machine (undetermined / waiting_for_end / waiting_for_start), 15s skip after end, dual-zone (minimap + map_name) check.                                                                                                                                                                                                                                                                                                                                                                                                        |
| [tools/map_config_generator.py](../apps/tooling/tools/map_config_generator.py)   | Tool 3. `--images <dir>` or `--video <name> <path> [<ts>]` (repeatable). Loads ref frames, downscales to `processing.target_height`, scales ROI, optionally crops to `text_anchor_width`, computes `imagehash.{ahash,dhash,phash}`, runs `consensus_from_hashes`, checks pairwise Hamming distance, supports `--patch <existing_map_config>` to merge into an existing config. Emits `map_config.json` with `reference_resolution`, `roi`, `canvas_size`, `hash_size`, `hash_method`, `maps`, optional `text_anchor_width`, `threshold_hash`, `tile_cols`. |
| [tools/hash_validator.py](../apps/tooling/tools/hash_validator.py)               | Tool 4. Accuracy report against labeled fixtures.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| [tools/warden_analyzer.py](../apps/tooling/tools/warden_analyzer.py)             | Tool 5. Full pipeline run.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| [tools/frame_labeler.py](../apps/tooling/tools/frame_labeler.py)                 | Tool 2 helper.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| [tools/hash_comparator.py](../apps/tooling/tools/hash_comparator.py)             | `consensus_from_hashes(hashes, shift_tolerance)` — used by Tool 3 to combine multiple ref hashes for one map into a single canonical hash.                                                                                                                                                                                                                                                                                                                                                                                                                 |
| [tools/points_state_detector.py](../apps/tooling/tools/points_state_detector.py) | Dev: per-frame point-colour state classifier with `--profile`.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| [tools/bsd_roi_debugger.py](../apps/tooling/tools/bsd_roi_debugger.py)           | Dev: ROI overlay viewer (`--range N:N` time slice, `--threshold` override).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| [tools/image_inspector/](../apps/tooling/tools/image_inspector/)                 | Dev GUI module — `python -m tools.image_inspector [image]`. Has `app.py`, `canvas.py`, `logger.py`, `modes.py`.                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| [tools/minimap_zone_selector/](../apps/tooling/tools/minimap_zone_selector/)     | Dev GUI module — HSV zone calibration. `app.py`, `config_manager.py`, `data_loader.py`, `hsv_editor.py`, `stats_panel.py`, `validator.py`, `zone_model.py`.                                                                                                                                                                                                                                                                                                                                                                                                |
| [tools/common/video_player.py](../apps/tooling/tools/common/video_player.py)     | Shared OpenCV preview window.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| [utils/config.py](../apps/tooling/utils/config.py)                               | `load_config(path)` — `yaml.safe_load`.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| [utils/video.py](../apps/tooling/utils/video.py)                                 | `extract_iframes_scaled`, `extract_frame_at_timestamp_scaled`, `get_video_info`, `check_ffmpeg`. FFmpeg subprocess wrappers with stderr-thread for showinfo timestamps.                                                                                                                                                                                                                                                                                                                                                                                    |
| [utils/image.py](../apps/tooling/utils/image.py)                                 | `downscale`, `to_grayscale`, `scale_roi`, `extract_roi`, `find_text_anchor` (used for the optional anchor-cropping step).                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| [utils/format.py](../apps/tooling/utils/format.py)                               | Print helpers.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |

## Map-config generation in detail

[map_config_generator.py](../apps/tooling/tools/map_config_generator.py) — the only tool that emits a contracts artifact:

1. Load reference frames per map. **Two input modes:**
   - `--images <dir>`: each subdirectory is a map; image filenames matching `*_start.{png,jpg,…}` and `*_end.{png,jpg,…}` are loaded.
   - `--video <name> <path> [<ts>]`: extract first I-frame at source resolution (or one I-frame at explicit `<ts>` seconds).
2. Validate aspect ratio against `reference_resolution` (warn if differs >0.01).
3. Downscale each frame to `processing.target_height` (defaults to ref height).
4. Scale ROI from reference to processing resolution. Scale `text_anchor_width` proportionally.
5. For each frame: `extract_roi` → optional `find_text_anchor` + sub-crop → `to_grayscale` → resize to `canvas_size × canvas_size` (INTER_AREA) → `imagehash.{method}(canvas, hash_size)`.
6. `consensus_from_hashes(hashes, shift_tolerance)` collapses N reference hashes into a single canonical hash per map.
7. `check_collisions(hash_dict, collision_threshold)` — pairwise Hamming distance; sorted summary, warnings for any pair below threshold.
8. **`--patch` mode** merges into an existing `map_config.json` instead of replacing — appends new hashes to existing maps (preserving as list when multiple), inherits `hash_method` + `tile_cols` from the existing config.
9. Write `map_config.json` validating against the schema shape from [contracts/map-config.schema.json](../contracts/map-config.schema.json).

## Cross-monorepo wiring

|                  | Mechanism                                                                                                                                                                                                                                          |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Turbo task graph | [package.json](../apps/tooling/package.json) declares `test`/`typecheck`/`lint`/`build` scripts so `turbo run test` includes tooling. `test` shells out to `uv run pytest`; the others are no-op echoes (no Python typecheck/lint configured yet). |
| pnpm filter      | Workspace name is `tooling`, invoked as `pnpm --filter tooling test` from root.                                                                                                                                                                    |
| Python deps      | Root [pyproject.toml](../pyproject.toml) declares `[tool.uv.workspace] members = ["apps/tooling"]`. Tooling's own [pyproject.toml](../apps/tooling/pyproject.toml) declares the actual dep list. `uv sync` from root installs both.                |
| Schema sharing   | Tooling validates emitted JSON against [contracts/map-config.schema.json](../contracts/map-config.schema.json) using `jsonschema`. (The TS side imports the auto-generated Zod from [@warden/contracts](../packages/contracts/).)                  |

## Conventions

- ROI coordinates **always** at 1920×1080 reference resolution. Scaling happens via `utils/image.scale_roi`.
- Tools accept `-c/--config` (default `config/config.yaml`) and `-o/--output-dir` (default from config or `./output`).
- The TUI's "Run on new source" path keeps non-source flags from the previous invocation (`_reprompt_source` in `wardentooling.py`).
- `last_run.json` lives at repo root (`.warden_last_run.json`) and is gitignored.

## Known gaps / debt

- **No Python typecheck or lint.** [package.json](../apps/tooling/package.json) `typecheck` and `lint` scripts are placeholder echoes. Phase 7 candidate: wire `mypy` + `ruff`.
- **`map_config.json` runtime delivery to mobile is undecided.** Tooling emits to `output/map_config.json`; mobile currently fetches `detection_config/latest` from Firestore (which contains map fingerprints + a great deal more — see legacy distillate). Phase 6 must clarify whether `map_config.json` ships as a Metro asset or via Firestore.
- **`apps/tooling/docs/`** holds older per-app docs from the legacy repo (architecture, dev guide, source tree, project overview, ROI detection method). They duplicate parts of this Phase 5b output but contain extra detail (ROI method explanation) — keep as legacy reference for Phase 6 inputs; do not auto-delete.
- **14 vs 15 maps.** Legacy notes flag a "14 vs 15 map count discrepancy" between artifacts. Resolve in Phase 6 — current `config/config.yaml` lists detector zones for `artefact` etc.; `map_config.json` is the running source of truth for which maps the mobile app can identify.
