# Tool 7 — Overlay Stack Analyzer

Stacks Tool 6's labeled PNGs into per-`(version, class)` **mean** and **stddev** images so you can eyeball where the redesigned EVA HUD lives. Headless batch tool — no GUI. Consumes `output/labeled/v<ver>/<class>/*.png` (Tool 6's output), writes a mirrored `output/overlay_stacks/` tree plus a stability-ranked `overlay_stacks_summary.json`.

## Launch

From `apps/tooling/`:

```powershell
# Via the TUI (recommended — picks up `Tool 7 — Analyze Overlay Stacks`)
uv run python wardentooling.py

# Or direct CLI
uv run python tools/overlay_stack_analyzer.py [--input INPUT_DIR] [--output OUTPUT_DIR] [--min-frames N] [--ref-height H] [--heatmap]
```

Defaults:

| Flag | Default | Meaning |
|---|---|---|
| `--input` | `apps/tooling/output/labeled` (= Tool 6's default output) | Labeled dataset root: `v<ver>/<class>/*.png`. |
| `--output` | `apps/tooling/output/overlay_stacks` | Where the stacked images + summary land. |
| `--min-frames` | `2` | Cells with fewer readable frames are recorded as `skipped` (`too_few_frames`) — no images. |
| `--ref-height` | unset | If set, every cell is resized to this pixel height (width keeps the modal aspect ratio). Unset → per-cell modal shape, no resize. |
| `--heatmap` | off | Also emit `variance_heatmap.png` (HSV-volatility, false-coloured). Adds a second streaming pass; skipped entirely when off. |

It globs `<input>/v*/*/*.png`, groups matches into `(version_dir, class_dir)` cells (the `v` prefix is kept: `v1.0`, `v2.0`, `vcustom`), and processes each cell **sequentially** with bounded memory (Welford's online algorithm — frames are never all stacked in one array, so a hundreds-of-1080p-frames span is fine). One bad cell (corrupt PNG, write failure) is logged to stderr and the batch continues; the summary JSON is the audit trail. Zero cells found → a clean stderr message and exit code `1` (no traceback).

## Output

```
output/overlay_stacks/
  overlay_stacks_summary.json
  v2.0/
    lobby/      { mean.png, stddev.png, stats.npz[, variance_heatmap.png] }
    horizon/    { mean.png, stddev.png, stats.npz[, variance_heatmap.png] }
    ...
```

Re-runs overwrite (outputs are deterministic for a given input set). `output/` is gitignored — nothing here is committed.

### What each file means

- **`mean.png`** — the "average screen": every pixel is the per-channel mean across that cell's frames. Static HUD chrome stays crisp; moving gameplay blurs to mush.
- **`stddev.png`** — the "what moves" map: per-channel population stddev, written `clip(0,255)→uint8`. **Dark** regions barely changed across the stack → **stable HUD chrome → ROI candidates** (KDA panel, map bar, minimap frame, score plate). **Bright** channels are volatile (gameplay, particles, scrolling text).
- **`variance_heatmap.png`** (only with `--heatmap`) — the per-pixel mean of the **Saturation and Value** stddev maps (Hue is deliberately dropped *from the heatmap*: OpenCV's H wraps in `0..179`, so a naive per-pixel stddev there is meaningless — 179 vs 0 looks like huge variance for adjacent reds; the real per-pixel circular-Hue stat lives in `stats.npz`), min-max normalized and false-coloured (`COLORMAP_JET`: blue = stable, red = volatile). Catches saturation/brightness churn that a BGR stddev under-weights.
- **`stats.npz`** — the **machine-readable companion** to the eyeball PNGs (always written, no flag needed; the `--heatmap`-only piece is just the false-colour PNG above). A NumPy `.npz` (compressed) with `float32` arrays `mean_bgr`, `std_bgr`, `mean_hsv`, `std_hsv` (each `(h, w, 3)`), plus a scalar `frame_count` and a 1-D `frame_shape`. **HSV-space stats are always computed**: the Saturation and Value channels use an ordinary streaming mean/stddev, and the **Hue** channel uses a *circular* accumulator (running sums of `sin`/`cos` of the per-pixel hue angle — OpenCV H ∈ `0..179`, each unit = 2°) finalized to a circular mean (`mean_hsv[..., 0]`, back in `0..179`) and a circular stddev (`std_hsv[..., 0]`, in H units) — the same circular-statistics math `minimap_zone_selector` uses. **Tool 8 (`auto_roi_discoverer`) reads these `.npz` files** — `std_hsv` says how tight an HSV tolerance each pixel can safely carry (not recoverable from the `clip(0,255)` BGR `stddev.png`), and the most-stable pixel's HSV seeds candidate band-centers.

### `overlay_stacks_summary.json`

Run metadata (`input_dir`, `output_dir`, `generated_at`, `heatmap`, `ref_height`, `min_frames`) plus a `cells` array — one entry per discovered cell:

```jsonc
{
  "version": "v2.0", "class": "lobby",
  "status": "ok",            // "ok" | "skipped"
  "reason": null,            // null | "too_few_frames" | "no_readable_frames" | "error"
  "frame_count": 87,
  "frame_shape": [1080, 1920, 3],   // the cell's target shape, or null if skipped
  "resized_count": 3,        // frames that didn't match the target shape and were resized
  "stability_score": 12.7,   // mean of the BGR stddev map — LOWER = more stable; null if skipped
  "most_stable_hsv": [118.0, 240.0, 200.0],   // OpenCV HSV at the cell's single most-stable
                                              //   pixel (min mean-of-BGR-stddev) — the band-center
                                              //   seed; absent/null on skipped cells
  "stability_percentiles": { "p10": 1.4, "p50": 9.0, "p90": 31.2 },  // of the per-pixel
                                              //   mean-of-BGR-stddev; absent/null on skipped cells
  "outputs": { "mean": "v2.0/lobby/mean.png", "stddev": "v2.0/lobby/stddev.png",
               "stats": "v2.0/lobby/stats.npz" }   // paths relative to <output>, or null
}
```

`cells` is sorted **ascending by `stability_score`** — most-stable cells first; skipped cells sort last. (`transition` is the discard bucket; its stack is expected high-variance noise and will land near the bottom.) stdout prints the same `(version, class, n, stability, status)` as an aligned table so a run is legible without opening the JSON.

`stability_score` is an **absolute** number (mean of the BGR stddev map over all pixels & channels), not a 0–1 ratio — it's only meaningful *relative to the other cells in the same run*, and it shifts if you change `--ref-height` (resizing alters pixel values via interpolation). Don't compare scores across runs that used different `--ref-height`.

## Coordinate-frame caveat

ROI rectangles you read off a `mean.png` / `stddev.png` are in **that cell's target-shape pixel space** — i.e. the modal shape of the labeled frames, unless you passed `--ref-height`. If you want the rectangles to line up directly with `apps/tooling/config/config.yaml`'s 1080-reference ROIs, run with `--ref-height 1080` so every cell is normalized to 1080-row space first.

## Recommended workflow

1. **Tool 6** — label real EVA captures → `output/labeled/v<ver>/<class>/*.png` (tag each video's HUD version).
2. **Tool 7** — `uv run python tools/overlay_stack_analyzer.py` (add `--heatmap` for the false-colour HSV view; **add `--ref-height 1080`** if you want config-aligned coordinates — recommended).
3. Open the 14 map `mean.png`s (static map-bar / minimap chrome that perceptual-hash map ID keys on) and the `lobby` / `score` `stddev.png`s (dark = stable HUD elements).
4. **Tool 8 (`auto_roi_discoverer`)** — reads this run's `stats.npz` + `overlay_stacks_summary.json` and auto-suggests / scores / validates game-state ROI candidates (interactive Tk review), then exports a hand-merge config fragment. See `tools/auto_roi_discoverer.md`.
5. Hand-merge Tool 8's fragment into `config/config.yaml` + regenerate `map_config.json` v2 — **out of scope** here and in Tool 8 (a separate re-fingerprinting story, TBD).

(Interactive HSV-band / zone editing for *per-map minimap fingerprints* lives in `tools/minimap_zone_selector/`; Tool 8 is the game-state-detection analogue that consumes Tool 7's output. Tool 7 produces the *static analysis images + `stats.npz`* that feed both — it doesn't replace either interactive editor.)

## Tests (no GUI)

```powershell
uv run pytest tests/test_overlay_stack_analyzer.py -v
```

Covers every pure helper (`_discover_cells`, `_modal_shape`, `_target_shape`, `_welford_*`, the circular-Hue accumulator `_circ_hue_*`, the `stats.npz` build/round-trip `_stats_npz_bytes` / `load_stats_npz`, `_normalize_uint8`, `_stability_score`, `_cell_output_paths`, `_default_*_dir`, `_read_bgr`) plus a small `tmp_path` data smoke that runs `main()` end-to-end on tiny `cv2.imencode`-written PNGs (no real video, no ffmpeg) and asserts the `stats.npz` side-car + `most_stable_hsv` / `stability_percentiles` summary fields. The full suite (`uv run pytest`) must stay green.

> Note: the as-built `docs/architecture-tooling.md` and `apps/tooling/README.md` predate Tools 6, 7 and 8; all three are documented via these sibling `.md` files + their story specs until a dedicated docs-refresh story catches the architecture doc up.
