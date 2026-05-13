# Tool 9 — ROI Detection Tester

Per-frame validation of Tool 8's discovered zones against Tool 6's labeled PNG dataset. Replays every labeled frame through every zone's hue-wrap `cv2.inRange` band test, aggregates fires into TP/FP/FN/TN per zone, and reports precision/recall/F1 per zone + per class + a confusion matrix per classifier — for **both** the 4-way *game-state classifier* (`lobby` / `in_match` / `score` / `transition`) **and** the N-way *map-ID classifier* (per-map zones). Headless batch tool — no GUI.

This closes the per-frame validation gap Tool 8's `GameStateValidator` deliberately punts on (see `auto_roi_discoverer.md`'s "What's a proxy" section + `auto_roi_discoverer/validator.py:18-20`: that one's a mean/std proxy; this one's per-frame). The new-HUD tooling chain end-to-end: **Tool 6 label → Tool 7 stack → Tool 8 discover → Tool 9 measure.**

## Launch

From `apps/tooling/`:

```powershell
# Via the TUI (recommended — picks up `Tool 9 — Test ROI Detection on Labeled Frames`)
uv run python wardentooling.py

# Or direct CLI
uv run python tools/roi_detection_tester.py [--zones PATH] [--labeled DIR] [--output DIR] \
    [--version v2.0] [--limit N] [--ref-height H] \
    [--game-state-threshold 0.5] [--map-threshold 0.5] [--save-frame-predictions]
```

Defaults:

| Flag | Default | Meaning |
|---|---|---|
| `--zones` | newest `apps/tooling/output/auto_rois/v*/discovered_zones.yaml` (lexicographic; mtime tie-break) | Tool 8's hand-merge fragment. `.json` and `.yaml` both accepted by suffix. No such file → clean stderr error `"run Tool 8 first"` + exit `1`. |
| `--labeled` | `apps/tooling/output/labeled` (= Tool 7's `--input` default = Tool 6's default output) | Tool 6's labeled-dataset root: `v<ver>/<class>/*.png`. |
| `--output` | `apps/tooling/output/roi_detection_tests` | Report root. A new sibling of `output/labeled/`, `output/overlay_stacks/`, `output/auto_rois/` under the existing `apps/tooling/output/` gitignore — **no `.gitignore` change.** |
| `--version` | from `_metadata.hud_version` in the zones yaml, else inferred from its parent directory name | HUD version override (e.g. `v2.0`). Recorded with its inference source in `report.json["run_metadata"]`. |
| `--limit` | unset (process all frames per class) | Cap frames per class at N (positive int) for fast-iteration smoke runs. |
| `--ref-height` | from `_metadata.frame_shape[0]` in the zones yaml | Override the reference row-count. Required if the zones yaml has no `frame_shape` metadata. |
| `--game-state-threshold` | `0.5` | Min max-class-score for the game-state classifier to commit a prediction; below → `"unknown"`. |
| `--map-threshold` | `0.5` | Min max-class-score for the map-ID classifier to commit a prediction; below → `"unknown"`. |
| `--save-frame-predictions` | off | Also emit `frame_predictions.csv` (one row per evaluated frame; ~3k rows on the live v2.0 dataset). |

## What the tool does

For every PNG under `<labeled>/<version>/<class>/*.png`:

1. Read the frame Windows-safely (`cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)` — Tools 6/7/8 use the same pattern).
2. Resize **once** to `--ref-height` rows (aspect-preserving; `INTER_AREA` for downscale, `INTER_LINEAR` for upscale) so the zone rects — which live in `--ref-height`-row cell pixel space — apply directly without per-zone scaling.
3. For every zone in the fragment: clip its rect to the frame, convert the region to HSV, apply the **hue-wrap-aware `cv2.inRange`** band, compute the in-range ratio, and fire = `ratio ≥ zone.min_ratio`.

The hue-wrap math is **reused** from `auto_roi_discoverer.validator.band_inrange_ratio` (line 82 of that file) — same logic Tool 8's `GameStateValidator` already runs on the mean image. Tool 9 just calls it on labeled frames instead.

### Two classifiers, one tool

Tool 8 emits both kinds of zone in the same `discovered_zones.yaml` (per the Story 9.7 AC15 correct-course). Tool 9 evaluates both in one pass over the labeled dataset:

**Game-state classifier (4-way).** For each frame, compute a per-class score = `fires_count / n_zones` for each of the four game-state classes whose `zone_list` is non-empty. The predicted game state = argmax, **provided** max-score `≥ --game-state-threshold`; otherwise `"unknown"`. Tie-break: prefer the class with more zones; secondary tie-break by `TARGET_CLASSES` order (`lobby > in_match > score > transition`).

**Map-ID classifier (N-way).** Only evaluated on `MAP_LABELS` folders. Same arg-max rule with `--map-threshold` and `MAP_LABELS` order as the secondary tie-break.

### Folder → ground-truth mapping

The labeled folder name **is** the ground truth (Tool 6 sorted those PNGs into the right folder):

| Labeled folder | Game-state GT | Map-ID GT |
|---|---|---|
| `lobby` | `lobby` | (skip — not a map folder) |
| `score` | `score` | (skip) |
| `transition` | `transition` | (skip) |
| any `MAP_LABELS` folder (`artefact` / `atlantis` / …) | `in_match` | the folder name itself |
| anything else | (skip + warn to stderr; recorded in `report["run_metadata"]["skipped_folders"]`) | (skip) |

So a frame in `output/labeled/v2.0/artefact/003.png` contributes to **two** classifier evaluations: positive for the game-state `in_match` class, and the ground-truth example for the map-ID `artefact` class.

## Output

```
output/roi_detection_tests/
  v<ver>/
    YYYY-MM-DDTHHMMSS/
      report.json
      summary.md
      frame_predictions.csv     # only when --save-frame-predictions
```

Each run drops a fresh timestamped subdir — re-runs don't overwrite, by design. The user iterates **Tool 8 → Tool 9** repeatedly during the hand-merge prep; comparing runs is the point.

### `report.json` (machine-readable)

```jsonc
{
  "tool": "roi_detection_tester (Tool 9)",
  "generated_at": "<ISO-8601>",
  "run_metadata": {
    "zones_path": "...", "labeled_path": "...",
    "version": "v2.0", "version_source": "metadata|path|--version",
    "ref_height": 1080, "ref_height_source": "metadata|--ref-height",
    "game_state_threshold": 0.5, "map_threshold": 0.5, "limit_per_class": null,
    "frame_count_by_class": {"lobby": 296, "score": 41, "artefact": 432, ...},
    "n_zones_by_class": {"lobby": 0, "in_match": 0, ..., "artefact": 11, ...},
    "skipped_folders": []
  },
  "game_state": {
    "accuracy": 0.967, "n_evaluated": 2748, "n_correct": 2659,
    "confusion": {"lobby": {"lobby": ..., "in_match": ..., "unknown": ...}, ...},
    "per_class": {"lobby": {"precision": ..., "recall": ..., "f1": ..., "support": ...}, ...}
  },
  "map_id": { /* same shape; only MAP_LABELS folders contribute */ },
  "per_zone": [
    {"name": "artefact_z1", "owning_class": "artefact", "kind": "map",
     "tp": ..., "fp": ..., "fn": ..., "tn": ...,
     "precision": ..., "recall": ..., "f1": ...,
     "fire_rate_on_owning": ..., "fire_rate_on_others": ...},
    ...
  ]
}
```

**Per-zone owning class.** For a *game-state* zone, the owning class is its game-state class (so frames from any `MAP_LABELS` folder count as positives for an `in_match` zone, per the folder→GT mapping above). For a *per-map* zone, the owning class is the map name (only that folder's frames are positives; all other folders — incl. `lobby` / `score` / `transition` and other maps — are negatives).

**Divide-by-zero guards.** Per-zone P/R/F1 and per-class accuracy all guard `denom == 0 → 0.0`. A zone with zero positives in the dataset reports `recall = 0.0`, not `NaN`. (This is documented; if you see all-zeros on a class, check `n_zones_by_class` — the live `discovered_zones.yaml` ships with `lobby: []` / `in_match: []` / `score: []` / `transition: []`, so the game-state classifier reports 0% accuracy until those get populated.)

### `summary.md` (human-readable)

A ≤ 200-line markdown digest: run metadata, frame counts by folder, two classifier sections (top-line accuracy + confusion table + per-class P/R/F1), **worst-performing zones** (top 10 by F1 — useful for spotting overly-loose bands that fire on everything), and **worst-confused class pairs** (top 5 by off-diagonal count — useful for spotting which maps look like each other).

### `frame_predictions.csv` (opt-in, `--save-frame-predictions`)

One row per evaluated frame: `frame_path, ground_truth_folder, ground_truth_game_state, predicted_game_state, gs_max_score, ground_truth_map, predicted_map, map_max_score`. UTF-8, comma-separated, header row. Off by default — it's ~3k rows on the live v2.0 dataset.

## Coordinate-frame contract

Tool 9 reads the zone rects as already in the **reference-height cell pixel space** (`--ref-height` rows). The default `--ref-height` is taken from `_metadata.frame_shape[0]` in the zones yaml — which Tool 8 sets to the resolved working-resolution height it picked (currently `1080` for the v2.0 dataset, since Tool 7 ran with `--ref-height 1080`). Override with `--ref-height` only when the labeled frames live in a different resolution than the zones were drawn in. The decision is recorded in `report.json["run_metadata"]["ref_height_source"]` (`"metadata"` vs `"--ref-height"`).

## Threshold semantics

Both `--game-state-threshold` and `--map-threshold` default to `0.5`: the predicted class must fire on at least half of its zones to commit a prediction. Below the threshold → `"unknown"`. Tighten the threshold for sparse-zone classes (a class with only 2 zones still has fire-counts `0/2 = 0.0`, `1/2 = 0.5`, `2/2 = 1.0`; the default works fine but a single-zone class needs `0.5` to fire on its single zone — natural). Loosen if you're seeing too many `"unknown"`s from a class whose zones are individually weak. Both classifiers' confusion matrices include `"unknown"` as a possible prediction column.

## Anti-patterns

- **DO NOT auto-edit `config/config.yaml`.** Tool 9 **reads** the Tool 8 fragment and **writes a report**. It never reads or writes `config/config.yaml`. The hand-merge step is the human's, in the future re-fingerprinting story (same posture as Tool 8).
- **DO NOT reinvent the band-fire test.** The hue-wrap `cv2.inRange` + `min_ratio` logic already exists in `auto_roi_discoverer/validator.py:band_inrange_ratio` — import and wrap. Re-implementing it would silently diverge from Tool 8's own scoring math.
- **DO NOT reinvent `Rect` / `HsvBand` dataclasses.** Reuse the ones in `auto_roi_discoverer/model.py`.
- **DO NOT special-case `transition`.** It's a regular game-state class; Tool 9 evaluates it the same way as `lobby` / `in_match` / `score`.
- **DO NOT overwrite previous reports.** Each run drops a fresh `<timestamp>/` subdir — comparing runs is the point.
- **DO NOT load all frames into memory.** `iter_labeled_frames` streams one at a time; the 2,748-frame v2.0 dataset at 1080p × 3 channels is ~18 GB raw if `np.stack`'d.

## Recommended workflow

1. **Tool 6** — label your frames (HUD-version-partitioned PNG dataset).
2. **Tool 7** — `--ref-height 1080` so the per-cell coordinate space matches the legacy `config/config.yaml` 1080-reference ROIs.
3. **Tool 8** — discover, accept/reject, draw exclusions, export `discovered_zones.yaml`.
4. **Tool 9** — measure: `python tools/roi_detection_tester.py` (zero-arg → defaults).
5. Review `summary.md` — the worst-performing zones + worst-confused pairs surface what to fix.
6. Iterate Tool 8 → Tool 9 → Tool 8 → Tool 9 until you're happy with the per-class numbers.
7. Hand-merge the fragment into `config/config.yaml` + regenerate `map_config.json` v2 — **out of this story's scope**; that's the future re-fingerprinting story.

## Notes

- The Tool 9 module sits next to Tools 6/7/8 as a **single file** (no package layout), in keeping with Tool 7's precedent: pure helpers + a thin `main(argv) -> int`. The GUI-less, engine-less shape doesn't need package breadth.
- Like the other new-HUD tools, this is a **sibling doc**: do **not** expand `apps/tooling/README.md`, and do **not** edit `docs/architecture-tooling.md` (still predates Tools 6/7/8/9; a dedicated docs-refresh story will catch them all up).
- Pytest coverage: `apps/tooling/tests/test_roi_detection_tester.py` — loader, band-fire, frame resize, classifier, aggregator, `main()` end-to-end smoke, CLI guards. All `tmp_path`-based; no Tk, no real video, no ffmpeg. Run with `uv run pytest tests/test_roi_detection_tester.py -v`.
