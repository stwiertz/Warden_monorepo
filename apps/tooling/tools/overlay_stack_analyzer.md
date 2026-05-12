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
    lobby/      { mean.png, stddev.png[, variance_heatmap.png] }
    horizon/    { mean.png, stddev.png[, variance_heatmap.png] }
    ...
```

Re-runs overwrite (outputs are deterministic for a given input set). `output/` is gitignored — nothing here is committed.

### What each file means

- **`mean.png`** — the "average screen": every pixel is the per-channel mean across that cell's frames. Static HUD chrome stays crisp; moving gameplay blurs to mush.
- **`stddev.png`** — the "what moves" map: per-channel population stddev, written `clip(0,255)→uint8`. **Dark** regions barely changed across the stack → **stable HUD chrome → ROI candidates** (KDA panel, map bar, minimap frame, score plate). **Bright** channels are volatile (gameplay, particles, scrolling text).
- **`variance_heatmap.png`** (only with `--heatmap`) — the per-pixel mean of the **Saturation and Value** stddev maps (Hue is deliberately dropped: OpenCV's H wraps in `0..179`, so a naive per-pixel stddev there is meaningless — 179 vs 0 looks like huge variance for adjacent reds), min-max normalized and false-coloured (`COLORMAP_JET`: blue = stable, red = volatile). Catches saturation/brightness churn that a BGR stddev under-weights.

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
  "outputs": { "mean": "v2.0/lobby/mean.png", "stddev": "v2.0/lobby/stddev.png" }  // paths relative to <output>, or null
}
```

`cells` is sorted **ascending by `stability_score`** — most-stable cells first; skipped cells sort last. (`transition` is the discard bucket; its stack is expected high-variance noise and will land near the bottom.) stdout prints the same `(version, class, n, stability, status)` as an aligned table so a run is legible without opening the JSON.

`stability_score` is an **absolute** number (mean of the BGR stddev map over all pixels & channels), not a 0–1 ratio — it's only meaningful *relative to the other cells in the same run*, and it shifts if you change `--ref-height` (resizing alters pixel values via interpolation). Don't compare scores across runs that used different `--ref-height`.

## Coordinate-frame caveat

ROI rectangles you read off a `mean.png` / `stddev.png` are in **that cell's target-shape pixel space** — i.e. the modal shape of the labeled frames, unless you passed `--ref-height`. If you want the rectangles to line up directly with `apps/tooling/config/config.yaml`'s 1080-reference ROIs, run with `--ref-height 1080` so every cell is normalized to 1080-row space first.

## Recommended workflow

1. **Tool 6** — label real EVA captures → `output/labeled/v<ver>/<class>/*.png` (tag each video's HUD version).
2. **Tool 7** — `uv run python tools/overlay_stack_analyzer.py` (add `--heatmap` for the HSV view; add `--ref-height 1080` if you want config-aligned coordinates).
3. Open the 14 map `mean.png`s (static map-bar / minimap chrome that perceptual-hash map ID keys on) and the `lobby` / `score` `stddev.png`s (dark = stable HUD elements).
4. Eyeball the ROI rectangles + HSV bands for `gameDetector` / `mapIdentifier` on HUD 2.0.
5. Feed those into a future `map_config.json` v2 regeneration + `config/config.yaml` ROI/HSV update — **both out of this story's scope** (a separate re-fingerprinting story, TBD).

(Interactive HSV-band / zone editing already lives in `tools/minimap_zone_selector/`. Tool 7 produces the *static analysis images* that inform that work — it doesn't replace the interactive editor.)

## Tests (no GUI)

```powershell
uv run pytest tests/test_overlay_stack_analyzer.py -v
```

Covers every pure helper (`_discover_cells`, `_modal_shape`, `_target_shape`, `_welford_*`, `_normalize_uint8`, `_stability_score`, `_cell_output_paths`, `_default_*_dir`, `_read_bgr`) plus a small `tmp_path` data smoke that runs `main()` end-to-end on tiny `cv2.imencode`-written PNGs (no real video, no ffmpeg). The full suite (`uv run pytest`) must stay green.

> Note: the as-built `docs/architecture-tooling.md` and `apps/tooling/README.md` predate Tools 6 and 7; both tools are documented via these sibling `.md` files + their story specs until a dedicated docs-refresh story catches the architecture doc up.
