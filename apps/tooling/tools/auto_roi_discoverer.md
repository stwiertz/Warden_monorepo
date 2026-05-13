# Tool 8 — Auto ROI/HSV Discoverer

Consumes Tool 7's per-`(version, class)` overlay-stack statistics (`stats.npz` + `overlay_stacks_summary.json`) and **automates the by-eye ROI/HSV pick** — for both the *game-state detector* (lobby / in-match / score / transition) **and** the *per-map fingerprints* (one selectable target per map). Proposes candidate ROI rectangles + HSV bands, scores them (size × stability × discriminativeness), validates their separability, and exports a **hand-merge config fragment** + a report + per-class previews. Interactive Tk review tool (headed — like Tool 6 and `minimap_zone_selector`). The human still reviews, tweaks, accepts/rejects, and draws exclusion masks; Tool 8 just does the proposing/scoring/validating. It **never** writes `config/config.yaml`.

This is the third and last link of the new-HUD tooling chain: **Tool 6** label → **Tool 7** stack → **Tool 8** discover.

## Launch

From `apps/tooling/`:

```powershell
# Via the TUI (recommended — picks up "Tool 8 — Discover Game-State ROIs")
uv run python wardentooling.py

# Or direct (module — Tool 8 is a package, not a single file)
uv run python -m tools.auto_roi_discoverer [--input INPUT_DIR] [--config CONFIG_PATH] [--exclusions EXCLUSIONS_PATH]
```

Defaults:

| Flag | Default | Meaning |
|---|---|---|
| `--input` | `apps/tooling/output/overlay_stacks` (= Tool 7's default `--output`) | Tool 7's output root: `overlay_stacks_summary.json` + `v<ver>/<class>/stats.npz`. |
| `--config` | `config/config.yaml` | **READ-ONLY.** Only used to draw the legacy HUD-1.0 ROIs (`black_detection.roi_zones`, `minimap_identification`) as a faded reference overlay so you can see where the old elements sat. Never written; the tool works without it (missing/unparseable → a warning, no overlay). |
| `--exclusions` | `apps/tooling/output/auto_rois/exclusions.yaml` if it exists, else none | A hand-editable `exclusions.yaml` — see below. Parse errors degrade to "no exclusions". |

On startup the loader reads the summary, loads each `"ok"` cell's `stats.npz`, and builds the target classes — in two groups:

**Game-state classes** (for the game-state detector cascade):

- **`lobby`** / **`score`** / **`transition`** — each directly from its own `(version, class)` cell;
- **`in_match`** — a **derived/pooled** class: the 14 `frame_labeler.MAP_LABELS` cells combined (frame-count-weighted mean-of-means; Chan/parallel variance pooling; the circular Hue channel is the frame-count-weighted circular mean of the per-cell circular means — a documented V1 approximation). The in-match HUD chrome (map-independent) comes out sharp while the per-map scenery averages to haze.

`transition` is kept as a target class so the future detector cascade learns to **recognize and reject** transition frames — its stacked output is incoherent by design, so its candidates rank last on their own (low-discriminativeness) merits. **No `transition` special-casing in the engine.**

**Per-map classes** (for the map-identification / minimap fingerprints): each loaded `MAP_LABELS` cell — `artefact`, `atlantis`, … `the_rock` — is *also* exposed as its own selectable target (these are the same cells the pooled `in_match` is built from; this just surfaces them individually). So Tool 8 is a one-stop ROI picker for **both** the game-state cascade **and** the per-map fingerprints. The target-class picker lists the 4 game-state classes, then the present per-map cells.

**Containment-aware comparison set.** The "other classes" used for a candidate's *discriminativeness* score (and the validator's *FP-proxy*) respect the pool/member relationship: a **game-state** class compares only against the *other game-state* classes — so the actual best in-match marker (a fixed HUD element present identically on every map) still scores high on discriminativeness *vs. lobby/score/transition* instead of being penalised for "looking like all the maps"; a **per-map** class compares against the *other per-map* classes **plus** `{lobby, score, transition}`, but **not** `in_match` (which contains it). (Tunable per-call; this is just the GUI default.)

If `overlay_stacks_summary.json` is missing/empty → a clean message ("run Tool 7 first"); if an `"ok"` cell has no `stats.npz` → "re-run Tool 7" (your output predates the Tool 7 amendment); if the target-class cells disagree on `frame_shape` → "re-run Tool 7 with `--ref-height` (e.g. `--ref-height 1080`)". All of these print to stderr and exit non-zero **before** Tk loads — no traceback.

## Coordinate-frame caveat

All ROI/zone coordinates Tool 8 works in — candidates, exclusions, the exported `x/y/w/h` — are in the **cells' pixel space**: the `--ref-height` resized space if Tool 7 ran with one, otherwise the single common modal shape the loader verified all cells share. **Running Tool 7 with `--ref-height 1080`** makes the coordinates line up directly with `config/config.yaml`'s 1080-reference ROIs — the recommended workflow. The exported fragment and `report.json` state the coordinate frame explicitly.

## The GUI

- **Toolbar** — a target selector (the 4 game-state classes `lobby` / `in_match` / `score` / `transition`, then the per-map cells `artefact` … `the_rock`, each annotated with its source frame count + stability score), an image-view selector (`mean` / `stddev` / `heatmap`), **Suggest zones**, **Save exclusions**, **Export**, and a "Draw exclusions (or hold Shift)" toggle.
- **Canvas (left)** — zoom (mouse-wheel) / pan (right-drag). Overlays: ranked candidate rects (numbered, colour-cycled); accepted zones (green; the selected one white + thicker); exclusion rects (red dashed); the faded legacy `config/config.yaml` ROIs. **Left-drag** draws a new manual zone (HSV-sampled from the class mean image) — or, with the toggle on / Shift held, an exclusion rect (you name it). A short click selects the candidate/zone under the cursor.
- **Right panel** — a reused **HSV editor** (`minimap_zone_selector.HSVEditor`: H/S/V center±tol in user space, `min_ratio`, Apply) for the selected accepted zone; a **Candidates** list (rank · score [size/stability/disc] · closest confuser · rect) with "Accept selected →"; an **Accepted zones** list (name · origin · rect · TP/FP proxy · OK/✗) with "Delete selected"; and a per-class **separability verdict** (`GameStateValidator` — see below).
- **Suggest zones** re-proposes candidates for the current class (honouring its exclusion mask) without discarding accepted zones. Accepted zones are what gets exported.

## What's a proxy

`GameStateValidator` is **mean/std-based, not per-frame**. For each accepted zone it applies the HSV band to its assigned class's *mean* BGR image (the hue-wrap `cv2.inRange` + `min_ratio` test) → an in-range pixel ratio, scales it by a frame-coverage estimate derived from how many σ (per-pixel temporal stddev, from `std_hsv`) the band spans → **TP-proxy**; does the same on each other class's mean image (the worst is **FP-proxy**); marks the zone *separable* if `tp_proxy ≥ 0.5` and `fp_proxy ≤ 0.30`; a class is *separable* if it has ≥ 1 separable zone. **Exact per-frame validation** against the labeled PNG dataset (re-streaming Tool 6's frames through the band) is **out of scope here** — it's part of the future re-fingerprinting story. (Tool 8 reads Tool 7's aggregates by design; loading hundreds of 1080p frames per class would defeat the architecture.)

## The discoverer engine (V1)

Deliberately simple — fancier segmentation is future polish:

1. per-pixel **instability** = mean of the BGR stddev channels (lower ⇒ more stable HUD chrome); excluded pixels are `+inf`;
2. threshold to a **stable mask** (pixels ≤ the 25th-percentile cutoff of the finite pixels — tunable), find 8-connected components, take each above-min-area component's bounding box → a candidate rect;
3. derive an **HSV band**: `h_center` = circular-mean H, `s/v_center` = mean S/V over the rect (all from `mean_hsv`); tolerances = `1.5 ·` the in-quadrature combination of the across-pixel spread and the across-frame `std_hsv`, each clamped to `_MIN_H_TOL = 10` / `_MIN_SV_TOL = 5` (user space, the `minimap_zone_selector` convention); `min_ratio = 0.3`;
4. **score** = geometric mean of `size_score` (a `log1p(area)/log1p(2000)` curve — diminishing returns), `stability_score = 1 / (1 + rect_mean_instability)`, and `discriminativeness_score` = the minimum, over the other target classes, of the rect's circular-HSV distance (a zone is only as discriminative as its worst confuser), normalised to `[0, 1]`.

Candidates are returned sorted by descending score, each carrying its rect, HSV band, the three sub-scores, and its closest-confuser class.

## `exclusions.yaml`

An optional, hand-editable file of per-HUD-version → per-target-class **named** rectangles to mask out before discovery (their pixels are never proposed), plus an `_all` bucket applied to every class of that version. Coords are in the cell pixel space.

```yaml
exclusions:
  v2.0:
    _all:
      - {name: ko_counter, x: 1700, y: 40, width: 120, height: 50}
    lobby:
      - {name: rotating_banner, x: 200, y: 880, width: 1520, height: 120}
    in_match: []
    score: []
    transition: []
```

The GUI's **Save exclusions** writes this back to the `--exclusions` path — or, if `--exclusions` wasn't given, to `apps/tooling/output/auto_rois/exclusions.yaml`. A missing file is fine.

## Output

```
output/auto_rois/
  exclusions.yaml                     # hand-editable; also written by "Save exclusions"
  v2.0/
    discovered_zones.json
    discovered_zones.yaml             # the hand-merge fragment (config-shaped zone dicts, user-space HSV)
    report.json                       # all ranked candidates + scores + GameStateValidator proxy + run metadata
    lobby_preview.png                  # mean + accepted zones (faded exclusions) — one per target
    in_match_preview.png               #   (game-state classes first, then one per per-map cell)
    score_preview.png
    transition_preview.png
    artefact_preview.png               # ... one per per-map cell present in the dataset
    atlantis_preview.png
    ...
```

Re-runs overwrite. `apps/tooling/output/` is gitignored — nothing here is committed.

### What each file means

- **`discovered_zones.json` / `discovered_zones.yaml`** — the **hand-merge fragment**: a mapping `class → [ {name, x, y, width, height, hsv: {h_center, h_tol, s_center, s_tol, v_center, v_tol}, min_ratio}, ... ]` (HSV in **user space** — H 0–360, S/V 0–100 — the same zone-dict shape `minimap_zone_selector` writes for `minimap_identification` zones), keys ordered `_metadata` → game-state classes (in `lobby/in_match/score/transition` order) → per-map classes (in `MAP_LABELS` order). The `_metadata` block / comment header states: this is **NOT** auto-merged into `config/config.yaml` — Tool 8 never edits it; the coordinate frame; that the **game-state classes** feed the **game-state detector cascade**; and that the **per-map classes** are candidate **map-identification fingerprints** (the `minimap_identification` / map-ID config). The hand-merge into `config/config.yaml` (+ a `map_config.json` v2 regen) is the future re-fingerprinting story's job.
- **`report.json`** — per-class (`"kind": "game_state"` or `"map"`) **all** proposed candidates (rect, HSV band, the three score components + total, closest-confuser class), the `GameStateValidator` separability report for the accepted set (with the rule + the "proxy only" caveat spelled out), and run metadata (`input_dir`, `generated_at`, `ref_height`, source `overlay_stacks_summary.json` path, exclusions path, per-class source `frame_count`).
- **`<class>_preview.png`** — that class's `mean.png` (the pooled mean for `in_match`; the map's own mean for a per-map cell) with the **accepted** zones drawn + labelled, and exclusions faded.

## Recommended end-to-end workflow

1. **Tool 6** (`video_timeline_labeler.py`) — label real EVA captures → `output/labeled/v<ver>/<class>/*.png`, tagging each video's HUD version.
2. **Tool 7** (`overlay_stack_analyzer.py`) — `uv run python tools/overlay_stack_analyzer.py --ref-height 1080` → `output/overlay_stacks/v<ver>/<class>/{mean.png, stddev.png, stats.npz}` + `overlay_stacks_summary.json`. (Use `--ref-height 1080` so Tool 8's coords align with `config/config.yaml`.)
3. **Tool 8** (`auto_roi_discoverer`, this tool) — `uv run python -m tools.auto_roi_discoverer` → for each target (the game-state classes and/or the per-map cells) review the suggested zones, tweak/accept, draw exclusions, **Export** the fragment.
4. **Future re-fingerprinting story (TBD)** — hand-merge `output/auto_rois/<ver>/discovered_zones.{json,yaml}` into `config/config.yaml` (the new game-state config section *and* the `minimap_identification` / map-ID config), and regenerate `map_config.json` v2 (with its own `schema_version: 1`). **Out of this story's scope** — and out of Tool 8's: Tool 8 only produces the raw material.

## Tests (no GUI)

```powershell
uv run pytest tests/test_auto_roi_discoverer.py -v
uv run pytest tests/test_overlay_stack_analyzer.py -v   # incl. the Tool 7 stats.npz amendment cases
```

All pure logic (`loader`, `discoverer`, `validator`, `exclusions`, `export`, plus Tool 7's circular-Hue accumulator + `stats.npz` round-trip) is unit-tested with `tmp_path` synthetic `stats.npz` + summary JSON — no real video, no ffmpeg, no Tk. The GUI (`app.py` / `__main__.py`) is **not** unit-tested (Tool 6 / `minimap_zone_selector` precedent — pure logic is tested instead). The full suite (`uv run pytest` / `pnpm --filter tooling test`) must stay green.

> Note: the as-built `docs/architecture-tooling.md` and `apps/tooling/README.md` predate Tools 6, 7 and 8; all three are documented via these sibling `.md` files + their story specs until a dedicated docs-refresh story catches the architecture doc up.
