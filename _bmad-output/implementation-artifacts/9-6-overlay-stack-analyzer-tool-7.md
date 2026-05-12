# Story 9.6: Overlay Stack Analyzer (Tool 7)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As **Stephane** (sole tooling user; mining ROI/HSV signatures for the redesigned EVA HUD),
I want **a headless batch analyzer that walks the HUD-version-partitioned labeled dataset Tool 6 produces (`labeled/v<ver>/<class>/*.png`) and, for every `(version, class)` cell, emits a per-pixel `mean.png` + `stddev.png` (plus an optional HSV-variance heatmap) into a mirrored output tree, with a summary JSON ranking cells by visual stability**,
so that **I can eyeball which screen regions are stable HUD chrome (low stddev) versus volatile gameplay (high stddev) on HUD 2.0 content and rediscover the ROI rectangles + HSV bands that `gameDetector` / `mapIdentifier` need — closing the second half of the new-HUD re-fingerprinting prep that Story 9.5 (Tool 6) opened.**

**Strategic context:** Story 9.5 shipped Tool 6, the video-timeline labeler that produces a HUD-version-aware PNG dataset at `output/labeled/v<ver>/<class>/<seq>_<HHmMSs>.png`. Tool 7 is the consumer that Story 9.5's Dev Notes explicitly deferred ("DO NOT attempt the overlay/stacking analysis in this story — that's 9.6's scope, and we don't yet know the right ROI shape; ship Tool 6 first, label real data, then design 9.6 against the observed dataset shape"). The legacy KDA / map-bar ROIs in `apps/tooling/config/config.yaml` target the legacy HUD ("HUD 1.0"); EVA's redesign ("HUD 2.0") moved them, so `gameDetector` returns false-negatives and `mapIdentifier` returns null on new-HUD frames. Re-fingerprinting needs to know *where the new HUD elements sit* — and stacking dozens-to-hundreds of labeled frames per class, then looking at the per-pixel mean (the "average screen") and stddev (the "what moves" map), is the fastest way to find those rectangles by eye. The 14 map mean-stacks additionally surface the static map-bar / minimap chrome that perceptual-hash map ID keys on. This story backfills the other half of the "new-HUD work" prerequisite that `_bmad-output/sprint-status.yaml` line 2 originally bound to the (now-cancelled) Story 1.1.1.

**Type:** Standard tooling feature story. Track C (tooling chain). No spike-or-split flag. Single-PR delivery + a tiny post-merge follow-up commit/PR for the sprint-status `review → done` flip (Two-PR pattern, `feedback_two_pr_docs_execution.md`).

## Acceptance Criteria (checklist)

> **AC checkbox convention:** items whose endpoint depends on **post-merge actions** (sprint-status `review → done` flip, PR merge) are held `[ ]` with carve-out notes per the AC-checkbox-tighten convention (`feedback_ac_checkbox_tighten.md`). All other items flip to `[x]` on dev-agent completion.

1. [x] **AC1 — New tool file at `apps/tooling/tools/overlay_stack_analyzer.py`.** Headless CLI — **no Tk, no GUI** — `python tools/overlay_stack_analyzer.py [--input INPUT_DIR] [--output OUTPUT_DIR] [--min-frames N] [--ref-height H] [--heatmap]`. Default `INPUT_DIR` = the path `video_timeline_labeler._default_output_dir()` resolves to (`<repo_root>/output/labeled`) — copy that resolution logic verbatim so Tool 7's default input always equals Tool 6's default output regardless of where the repo checkout lives. Default `OUTPUT_DIR` = `<repo_root>/output/overlay_stacks`. Default `--min-frames` = `2`. `--ref-height` default = unset (per-cell modal shape). `--heatmap` default = off. Standalone CLI; also invokable from the TUI (AC9).

2. [x] **AC2 — Cell discovery.** The tool globs `<input>/v*/*/*.png` and groups matches into `(version_dir, class_dir)` cells (e.g. `("v2.0", "lobby")`). The literal directory names are kept (the `v` prefix stays — `v1.0`, `v2.0`, `vcustom`). Top-level directories not matching `v*` are ignored; non-`.png` files are ignored. On startup it prints `Discovered <C> cell(s) across <V> HUD version(s): <comma-list>`. If zero cells are found → clean message to stderr + `return 1` (no traceback).

3. [x] **AC3 — Per-cell streaming stack → mean + stddev.** For each cell with effective `frame_count >= --min-frames`:
   - Frames are read **one at a time** via `cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)` — **not** `cv2.imread` (which returns `None` silently on Windows non-ASCII paths; same hazard the Tool 6 review fixed for the write side). A frame that decodes to `None` is skipped with a stderr warning and does not count toward `frame_count`. `IMREAD_COLOR` forces 3-channel even if a stray grayscale PNG turns up.
   - Frames whose `.shape` ≠ the cell's **target shape** are resized to it (`cv2.resize`; `INTER_AREA` when downscaling, `INTER_LINEAR` when upscaling). Target shape = the **modal** shape across the cell's readable frames when `--ref-height` is unset; otherwise `(H, round(H * w_modal / h_modal), 3)`. The count of resized frames is recorded per cell.
   - Per-pixel-per-channel **mean** and **population stddev** are accumulated in a **single streaming pass** (Welford's online algorithm) on `float64` accumulators. The tool **MUST NOT** hold all frames in memory simultaneously — a long-video same-class span (Tool 6's same-class auto-backfill writes one PNG per keyframe between two labels) can be hundreds of 1080p frames → multi-GB if stacked. Peak RAM is a few hundred MB per cell (2–3 `float64` images for 1080p); cells process sequentially so it does not accumulate.
   - `mean.png` = `mean.round().clip(0, 255).astype(np.uint8)` written as BGR. `stddev.png` = `stddev.clip(0, 255).astype(np.uint8)` written as BGR (dark = stable; bright channels = volatile). Both written via `cv2.imencode(".png", arr)` + `Path(dest).write_bytes(buf.tobytes())` (Windows non-ASCII path safety — same pattern as Tool 6's write path), after `os.makedirs(dirname, exist_ok=True)`.
   - Cells with effective `frame_count < --min-frames` are skipped (recorded in the summary, `reason = "too_few_frames"`); a cell where every frame failed to decode is skipped (`reason = "no_readable_frames"`).

4. [x] **AC4 — Optional HSV variance heatmap.** When `--heatmap` is passed, the tool additionally streams a second statistic per cell: per-pixel-per-channel stddev in **HSV** space (each decoded BGR frame `cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)` before a second Welford update set, on the same target shape). The scalar variance map = the per-pixel mean of the 3 HSV-channel stddevs, min-max normalized to `0..255` uint8 (constant map → all-zero, no div-by-zero), then false-coloured via `cv2.applyColorMap(scalar, cv2.COLORMAP_JET)`. Written to `variance_heatmap.png` in the cell's output dir. Without `--heatmap` the file is not produced and the HSV pass is skipped entirely (no perf cost).

5. [x] **AC5 — Mirrored output tree.** For each processed cell, outputs land at `<output>/<version_dir>/<class_dir>/{mean.png, stddev.png[, variance_heatmap.png]}` — the output tree mirrors the input tree's `v*/<class>/` structure. Re-runs overwrite (outputs are deterministic for a given input set). A `makedirs` / write / decode failure that aborts one cell is logged to stderr and the tool **continues with the next cell** — one bad cell does not abort the batch.

6. [x] **AC6 — Summary JSON.** `<output>/overlay_stacks_summary.json` is written with run metadata (`input_dir`, `output_dir`, `generated_at` ISO-8601 timestamp, `heatmap` bool, `ref_height` int-or-`null`, `min_frames` int) and a `cells` array — one entry per discovered cell: `{version, class, status ("ok"|"skipped"), reason (null|"too_few_frames"|"no_readable_frames"|"error"), frame_count, frame_shape ([h,w,3] or null), resized_count, stability_score (mean of the BGR stddev map over all pixels & channels — lower = more stable; null if skipped), outputs ({mean, stddev, heatmap?} as paths relative to `<output>`, or null if skipped)}`. The `cells` array is sorted ascending by `stability_score` (most-stable cells first; skipped cells sort last). On stdout the tool prints a compact aligned table of the same `(version, class, n, stability_score, status)` so a run is legible without opening the JSON.

7. [x] **AC7 — Pure helpers (top-level module functions, testable with no image I/O).**
   - `_default_input_dir() -> str` — mirrors `video_timeline_labeler._default_output_dir()`'s resolution → `<repo_root>/output/labeled`.
   - `_default_output_dir() -> str` — `<repo_root>/output/overlay_stacks` (same `__file__`-relative math).
   - `_discover_cells(input_root: str) -> list[tuple[str, str, list[str]]]` — returns `[(version_dir, class_dir, sorted_png_paths), ...]`, sorted by `(version_dir, class_dir)`; skips top-level dirs not matching `v*` and non-`.png` files; missing/empty `input_root` → `[]`.
   - `_modal_shape(shapes: list[tuple[int, int, int]]) -> tuple[int, int, int]` — most-common shape; tie-break by largest `h*w`, then lexicographic. Empty list → raises `ValueError`.
   - `_target_shape(modal: tuple[int, int, int], ref_height: int | None) -> tuple[int, int, int]` — `modal` if `ref_height is None`, else `(ref_height, round(ref_height * w / h), 3)`.
   - `_welford_init(shape) -> tuple[int, np.ndarray, np.ndarray]` → `(0, np.zeros(shape, np.float64), np.zeros(shape, np.float64))`; `_welford_update(state, x: np.ndarray) -> tuple[int, np.ndarray, np.ndarray]`; `_welford_finalize(state) -> tuple[np.ndarray, np.ndarray]` returning `(mean, population_stddev)` — `count == 0` raises `ValueError`; `count == 1` → stddev all-zero.
   - `_normalize_uint8(arr: np.ndarray) -> np.ndarray` — min-max normalize a float array to `0..255` uint8; a constant array → all-zero (no div-by-zero).
   - `_stability_score(stddev_bgr: np.ndarray) -> float` — `float(stddev_bgr.mean())`.
   - `_cell_output_paths(output_root: str, version_dir: str, class_dir: str, heatmap: bool) -> dict[str, str]` — exact `{"mean": ..., "stddev": ...[, "heatmap": ...]}` paths.

8. [x] **AC8 — Pytest at `apps/tooling/tests/test_overlay_stack_analyzer.py`.** No-GUI unit tests for every pure helper above plus a small data smoke:
   - `_welford_*` — feed `[1, 2, 3, 4]` (as scalars and as tiny `(2, 2, 3)` arrays): `mean == 2.5`, population `stddev == sqrt(1.25)`; cross-check against `numpy.mean` / `numpy.std` on the same data; `count == 1` → stddev `0`; `count == 0` finalize → `ValueError`.
   - `_modal_shape` — `[(1080,1920,3)]*3 + [(1440,2560,3)]` → `(1080,1920,3)`; 2-vs-2 tie → larger-area shape wins; empty → `ValueError`.
   - `_target_shape` — `ref_height=None` → returns `modal`; `ref_height=720` on `(1080,1920,3)` → `(720,1280,3)`.
   - `_discover_cells` — build a `tmp_path` tree (`v1.0/lobby/001_00h00m01s.png`, `v2.0/lobby/001_…png`, `v2.0/horizon/001_…png`, plus a stray `notes.txt` and a non-`v` dir `scratch/with.png`) using `cv2.imencode`-written 4×4 PNGs; assert exactly the 3 valid cells, correct ordering, stray file & dir ignored; nonexistent root → `[]`.
   - `_normalize_uint8` — `[[0., 127.5, 255.]]` → `[[0, 127-or-128, 255]]`; constant array → all-zero; integer/float dtype both accepted.
   - `_stability_score` — known array → known mean.
   - `_cell_output_paths` — exact strings, with and without `heatmap`.
   - **Data smoke** (still no GUI): a 2-cell `tmp_path` tree — cell A = 3× solid `(0,0,255)` 8×8 PNGs, cell B = a 3-frame gradient with one frame at a different size (16×16) — run `main(["--input", <tmp_in>, "--output", <tmp_out>])`, then assert cell-A `mean.png` ≈ red & `stddev.png` ≈ all-zero; cell-B `stddev.png` has nonzero pixels & `resized_count == 1`; `overlay_stacks_summary.json` exists with 2 `"ok"` cells sorted ascending by `stability_score` (cell A first). One run with `--heatmap` asserts `variance_heatmap.png` exists and is 3-channel.
   - All FS-touching tests use `tmp_path`. `apps/tooling/tests/conftest.py` already prepends `apps/tooling/` to `sys.path` (added in Story 9.5), so `from tools.overlay_stack_analyzer import ...` resolves under pytest — **no new conftest needed**.
   - Run command: `cd apps/tooling && uv run pytest tests/test_overlay_stack_analyzer.py -v`. The full-suite gate (`cd apps/tooling && uv run pytest` / `pnpm --filter tooling test`) must stay green — currently 35 tests; this story adds the new module's tests.

9. [x] **AC9 — TUI registration.** `apps/tooling/wardentooling.py`:
   - Adds `flow_tool7() -> tuple[list[str], str | None]` mirroring `flow_tool4` (the other headless, directory-driven tool): optional `--input` text prompt (blank = default), optional `--output` text prompt (blank = default), optional `--min-frames` text prompt (blank = `2`; only appended when a positive integer is entered, else warn & re-prompt), optional `--ref-height` text prompt (blank = unset; only appended when a positive integer is entered), and `questionary.confirm("Produce HSV variance heatmaps too (--heatmap)?", default=False)`. Returns `([], None)` if the user Ctrl-C's any prompt (questionary returns `None`).
   - Inserts `"Tool 7 — Analyze Overlay Stacks"` into `choices_main` in `menu_main` between `"Tool 6 — Label Frames from Video Timeline"` and `"Dev Tools"`.
   - Adds the `elif choice == "Tool 7 — Analyze Overlay Stacks":` branch in `menu_main`'s while-loop, shaped like the Tool 4 / Tool 6 branches: collect args → confirm → `run_tool` → `save_last_run("overlay_stack_analyzer", "Tool 7 — Analyze Overlay Stacks", args, None)` on `returncode == 0` (`video_path` is `None`, like Tools 2 and 4).
   - Adds `"overlay_stack_analyzer": ("Tool 7 — Analyze Overlay Stacks", flow_tool7)` to `_TOOL_MAP`.
   - Adds a `_reprompt_source` branch for `tool_key == "overlay_stack_analyzer"` that just re-runs `flow_tool7()` (directory-driven; the same approach as the `hash_validator` branch which calls `flow_tool4()`).

10. [x] **AC10 — Sibling usage doc `apps/tooling/tools/overlay_stack_analyzer.md`.** Concise launch + output-interpretation guide, mirroring the existing `apps/tooling/tools/video_timeline_labeler.md` shape: CLI invocation; what each output file means (`mean.png` = "average screen"; `stddev.png` = "what moves" — **dark** regions are stable HUD chrome → ROI candidates; `variance_heatmap.png` = HSV-volatility false-colour); how to read `overlay_stacks_summary.json` (lower `stability_score` = more stable cell); the **coordinate-frame caveat** (ROI rectangles you read off the mean/stddev image are in the cell's *target-shape* pixel space — pass `--ref-height 1080` if you want them to line up directly with `config/config.yaml`'s 1080-reference ROIs); and the recommended workflow (Tool 6 to label → Tool 7 → open the 14 map `mean.png`s + `lobby`/`score` `stddev.png`s → eyeball ROI rects → feed into a future `map_config.json` v2 regeneration + `config/config.yaml` ROI/HSV update — both **out of this story's scope**). Like `video_timeline_labeler.md`, this is a sibling doc — do **NOT** expand the stale `apps/tooling/README.md`, and do **NOT** edit `docs/architecture-tooling.md` (the as-built doc still predates Tool 6; Tools 6 and 7 are both tracked via their sibling docs + story files until a dedicated docs-refresh story).

11. [x] **AC11 — Sprint-status entry + lifecycle flip.** `_bmad-output/sprint-status.yaml` gains a `9-6-overlay-stack-analyzer-tool-7` entry under `epic-9`, added at create-story time and set to `ready-for-dev` (`epic-9` is already `in-progress`, so no epic flip — verify this happened before the dev agent reads this file). The entry then flows `ready-for-dev → in-progress → review` across the dev work, and `review → done` post-merge. _✅ Done 2026-05-12 — the `review → done` flip ships in this follow-up commit (branch `story-9.6-postmerge`) after main PR #8 merged to `main` (Two-PR pattern, `feedback_two_pr_docs_execution.md`); `last_updated` bumped; `epic-9` stays `in-progress` (9.1–9.4 still `backlog`)._

12. [x] **AC12 — Single-PR delivery + follow-up flip.** All file changes ship in **one PR** titled `feat: Tool 7 — overlay stack analyzer (Story 9.6)`, branch `tool-7-overlay-stack-analyzer`. PR body links: this story file; the Epic 9 charter at `_bmad-output/epics-and-stories.md` (with the note that Stories 9.5/9.6 were added post-planning via the new-HUD initiative and are not yet enumerated in the charter — known doc-debt, tracked, not corrected here); `apps/tooling/tools/video_timeline_labeler.md` (the upstream Tool 6 doc). The `review → done` sprint-status flip is a separate tiny follow-up commit/PR per AC11. _✅ Done 2026-05-12 — PR #8 (commit `ceae136`; subject lowercased to `feat: tool 7 — overlay stack analyzer (Story 9.6)` to satisfy commitlint's `subject-case`, matching the Tool 6 precedent; base `main`, since Tool 6 had landed via PR #7 by then — a normal PR, not the hedged stacked-on-tool-6 one) merged to `main`. The `review → done` flip is this follow-up (branch `story-9.6-postmerge`)._

## Tasks / Subtasks

> **Implementation order:** pure helpers + tests first (the math core is the highest-value, easiest-to-verify part), then the streaming per-cell processor, then `main()` + CLI + summary, then a real-data manual smoke run, then the sibling doc + TUI registration, then PR + sprint-status. Run the tool against `output/labeled/` on the box (whatever Story 9.5's smoke run left there) before declaring done — eyeball that a `mean.png` actually looks like an averaged EVA screen.

- [x] **Task 1: Module skeleton + imports + CLI parsing (AC: 1)**
  - [x] Create `apps/tooling/tools/overlay_stack_analyzer.py` with a module docstring in the `frame_labeler.py:1-10` / `video_timeline_labeler.py:1-10` style (one-liner + 2–3 sentence elaboration + `Usage:` block).
  - [x] `sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))` to lift `utils/` onto the import path (same pattern as `game_detector.py:21` / `video_timeline_labeler.py:22`). This tool has **no** required `utils.*` import (it's pure cv2 + numpy + stdlib), but keep the insert for consistency.
  - [x] Imports: `argparse`, `datetime`, `glob`, `json`, `os`, `sys`, `from collections import Counter`, `from pathlib import Path`, `cv2`, `numpy as np`. **No** Tkinter, **no** Pillow — headless. (`LABEL_DISPLAY` polish skipped — raw dir names in the stdout table; spec said optional.)
  - [x] `argparse`: `--input` (default `None` → `_default_input_dir()`), `--output` (default `None` → `_default_output_dir()`), `--min-frames` (`type=int`, default `2`), `--ref-height` (`type=int`, default `None`), `--heatmap` (`action="store_true"`). `main()` calls `os.path.abspath()` on whatever's passed for `--input` / `--output`.

- [x] **Task 2: Pure helpers — discovery, shape, Welford, normalize, paths (AC: 2, 3, 7)**
  - [x] `_default_input_dir()` / `_default_output_dir()` — copied the `__file__`-relative resolution from `video_timeline_labeler._default_output_dir()`; a docstring states `_default_input_dir` is intentionally identical to Tool 6's default output.
  - [x] `_discover_cells(input_root)` — `if not os.path.isdir(input_root): return []`; `sorted(os.listdir(...))` for `v*` dirs, then sorted class subdirs; `sorted(glob.glob(.../*.png))`; skip empty-PNG cells; return `[(v, cls, paths), ...]` sorted by `(v, cls)`.
  - [x] `_modal_shape(shapes)` — `Counter`; `max(counter.items(), key=lambda kv: (kv[1], kv[0][0]*kv[0][1], kv[0]))[0]`; `ValueError("no shapes")` on empty.
  - [x] `_target_shape(modal, ref_height)` — `modal` if `ref_height is None`; else `(ref_height, round(ref_height * w / h), c)`.
  - [x] `_welford_init/_update/_finalize` — textbook Welford on `np.float64` arrays; population variance; `n == 0` → `ValueError`; `n == 1` → all-zero stddev.
  - [x] `_normalize_uint8(arr)` — `np.asarray(arr, np.float64)`; constant array (`hi <= lo`) → all-zero `uint8`; else min-max → `0..255`.
  - [x] `_stability_score(stddev_bgr)` — `float(np.asarray(stddev_bgr).mean())`.
  - [x] `_cell_output_paths(output_root, version_dir, class_dir, heatmap)` — `mean`/`stddev` always; `heatmap` key only when `heatmap=True`.

- [x] **Task 3: Streaming per-cell processor — decode → resize → Welford → write (AC: 3, 4, 5)**
  - [x] `_read_bgr(path) -> np.ndarray | None` — `cv2.imdecode(np.fromfile(path, np.uint8), cv2.IMREAD_COLOR)`; `None` on empty/`OSError`/`cv2.error`/decode failure.
  - [x] `_process_cell(version_dir, class_dir, paths, output_root, ref_height, want_heatmap, min_frames) -> dict` — **two cheap passes**: pass 1 reads & discards each PNG, recording `.shape` for readable ones (→ `_modal_shape`); pass 2 re-reads & feeds Welford. Memory bounded (two/three `float64` images per cell, cells run sequentially). Empty pass-1 → `no_readable_frames`.
  - [x] Pass 2: `_welford_init(target_shape)`; per path: `_read_bgr`; `None` → skip (warned in pass 1). `frame.shape != target_shape` → `cv2.resize` (`INTER_AREA` downscale, `INTER_LINEAR` upscale); `resized_count += 1`. `bgr_state = _welford_update(bgr_state, frame.astype(np.float64))`. If `want_heatmap`: `cv2.cvtColor(frame, COLOR_BGR2HSV)` → second Welford set.
  - [x] After pass 2: `n == 0` → `no_readable_frames`; `n < min_frames` → `too_few_frames` (with `frame_count=n`, `frame_shape`, `resized_count`).
  - [x] `mean, stddev = _welford_finalize(bgr_state)`; `mean_u8 = clip(round(mean),0,255).astype(uint8)`; `std_u8 = clip(stddev,0,255).astype(uint8)`. `_write_png` = `makedirs` + `cv2.imencode(".png", arr)` + `Path(dest).write_bytes(...)`. Per-cell write/dir wrapped `try/except (OSError, RuntimeError, cv2.error)` → `reason="error"`, `main` keeps going.
  - [x] If `want_heatmap`: `_, hsv_std = _welford_finalize(hsv_state)`; `scalar = hsv_std.mean(axis=2)`; `cv2.applyColorMap(_normalize_uint8(scalar), COLORMAP_JET)` → `variance_heatmap.png`.
  - [x] Returns `{version, class, status:"ok", reason:None, frame_count, frame_shape:[h,w,3], resized_count, stability_score, outputs:{...forward-slash paths relative to output_root...}}`.

- [x] **Task 4: main() — discover, iterate cells, summary JSON + stdout table (AC: 1, 2, 5, 6)**
  - [x] `main(argv=None) -> int` — parse args; abspath/default-fill `input_dir`/`output_dir`. Prints `Input:`/`Output:`/`Heatmap:`/`Ref height:`/`Min frames:` with `flush=True`. Empty `_discover_cells` → `"No labeled cells found under <input>. Run Tool 6 first."` to stderr, `return 1`.
  - [x] Prints `Discovered <C> cell(s) across <V> HUD version(s): <list>`.
  - [x] Per cell: prints `[<v>/<cls>] <n> frame(s) — processing...` (flush), calls `_process_cell`, wraps in `try/except Exception` → unexpected error logged to stderr + `reason="error"` entry; appends to `results`.
  - [x] Sorts `results` by `(0 if status=="ok" else 1, stability_score if not None else inf)`.
  - [x] `os.makedirs(output_dir, exist_ok=True)`; writes `overlay_stacks_summary.json` with `input_dir`/`output_dir`/`generated_at` (ISO-8601 w/ tz)/`heatmap`/`ref_height`/`min_frames`/`cells`, `json.dump(..., indent=2)`.
  - [x] Prints an aligned `version`/`class`/`n`/`stability`/`status` table + `Summary: <path>`; `return 0`.
  - [x] `if __name__ == "__main__": sys.exit(main())`.

- [x] **Task 5: Tests (AC: 8)**
  - [x] Created `apps/tooling/tests/test_overlay_stack_analyzer.py` (no new `conftest.py`).
  - [x] Covers every pure helper per AC8 + `_read_bgr` round-trip; Welford tested as scalars and `(2,2,3)` arrays, cross-checked vs `numpy.mean`/`numpy.std`.
  - [x] `_discover_cells` test: `tmp_path` tree with `cv2.imencode`-written 4×4 PNGs, stray `notes.txt`, non-`v` `scratch/` dir → exactly 3 cells, correct order, strays ignored; missing root → `[]`.
  - [x] Data-smoke: cell A (`v2.0/lobby`) 3× solid red 8×8, cell B (`v2.0/horizon`) 3× 8×8 gradient + 1× 16×16 → `main([...])` asserts cell-A `mean.png` ≈ `(0,0,255)` & `stddev.png` all-zero; cell-B `stddev.png` nonzero & `resized_count == 1`; summary has 2 `"ok"` cells sorted ascending (cell A first). `--heatmap` run asserts `variance_heatmap.png` is 3-channel. Plus `too_few_frames` skip + no-cells `return 1` cases.
  - [x] `cd apps/tooling && uv run pytest tests/test_overlay_stack_analyzer.py -v` → **24 passed**. `cd apps/tooling && uv run pytest` (full suite) → **59 passed** (35 prior + 24 new).

- [x] **Task 6: Manual smoke run against the labeled dataset (AC: 1–6)**
  - [x] No real `output/labeled/` on this box (Story 9.5's smoke ran on a different machine), so per the AC's fallback clause built a synthetic `output/labeled/v2.0/{lobby,horizon,transition}/` tree (stable cyan/red HUD bars + RNG center; one off-size 360×640 horizon frame; single-frame `transition`) and ran the CLI: discovery printed `3 cell(s) across 1 HUD version(s)`; `lobby`/`horizon` produced `mean.png`+`stddev.png` under `output/overlay_stacks/v2.0/<class>/`; `transition` → `too_few_frames` and sorted last; stdout table rendered; re-run overwrote cleanly; `--heatmap` re-run added `variance_heatmap.png` (3-channel); `overlay_stacks_summary.json` well-formed & sorted ascending by `stability_score` (lobby 26.4 < horizon 44.6). Eyeballed `lobby/mean.png` — stable bars crisp, center averaged; `lobby/stddev.png` — bars/margins near-black, center bright. (See Debug Log.)
  - [x] (Dev-agent-executable — fell back to the synthetic tree as the AC permits since no real dataset is present locally; recorded in the Debug Log.)

- [x] **Task 7: Sibling doc `apps/tooling/tools/overlay_stack_analyzer.md` (AC: 10)**
  - [x] Written to the AC10 spec (launch, output-file meanings, summary-JSON layout, coordinate-frame caveat, recommended workflow, no-edit-to-README/architecture note); ≈ the length of `video_timeline_labeler.md`. In the File List.

- [x] **Task 8: TUI registration in `wardentooling.py` (AC: 9)**
  - [x] Added `flow_tool7` (questionary text prompts for `--input`/`--output`/`--min-frames` [warn+re-prompt on bad int]/`--ref-height` [warn+skip on bad int] + `confirm` for `--heatmap`; returns `([], None)` on any Ctrl-C), `_TOOL_MAP` entry, `choices_main` entry between Tool 6 and Dev Tools, `menu_main` branch (`save_last_run("overlay_stack_analyzer", ..., args, video_path)` where `video_path` is `None`, like Tool 4), and a `_reprompt_source` branch (`tool_key == "overlay_stack_analyzer"` → `flow_tool7()`). Module syntax + wiring verified.

- [x] **Task 9: PR + sprint-status flip (AC: 11, 12)**
  - [x] Branch `tool-7-overlay-stack-analyzer` created (cut off `tool-6-video-timeline-labeler` at dev-story time, since Tool 6 wasn't yet on `main` and Tool 7 depends on its directory contract / conftest / TUI registration). Committed (`ceae136` — deliverable + the `/bmad-code-review` patch pass, single batch), pushed, PR #8 opened against `main` (Tool 6 had landed on `main` via PR #7 by the time the PR opened, so a normal PR — not the hedged stacked-on-tool-6 one), merged 2026-05-12. Commit subject lowercased to `feat: tool 7 — overlay stack analyzer (Story 9.6)` to satisfy commitlint's `subject-case` (PR title kept the capitalized form).
  - [x] Flipped sprint-status `9-6-overlay-stack-analyzer-tool-7`: `ready-for-dev → in-progress` (work start) → `review` (dev work + tests + smoke done) → `done` (this post-merge follow-up). `last_updated` bumped each time.
  - [x] Opened PR #8, linked this story file + the Epic 9 charter + `apps/tooling/tools/video_timeline_labeler.md`.
  - [x] Post-merge follow-up — branch `story-9.6-postmerge`: flipped sprint-status `review → done`, bumped `last_updated`, flipped AC11/AC12 + these Task 9 boxes to `[x]`, Status → `done` (Two-PR pattern per `feedback_two_pr_docs_execution.md`). Also folded in the Tools-6/7 default-dir fix (`372383f` — `_default_*_dir` now resolves to `apps/tooling/output/…`, resolving the deferred-work "four levels above tools/" item) and a manual smoke run against the real 2,748-frame `apps/tooling/output/labeled/v2.0/` dataset (16 cells discovered — 14 maps + lobby + score + transition).

### Review Findings

> Code review 2026-05-12 (`/bmad-code-review` — Blind Hunter + Edge Case Hunter + Acceptance Auditor, Opus 4.7 1M). Acceptance Auditor: **zero AC violations** — AC1–AC10 + Tasks 1–8 verified satisfied, anti-patterns clean, the four dev-recorded "spec deviations" all accurate and within latitude. 2 decision-needed, 9 patch, 0 defer, ~16 dismissed as noise/spec-mandated/handled.

**Decision-needed** (resolved 2026-05-12 by Stephane):

- [x] [Review][Decision] `stddev.png` absolute `clip(0,255)` — high-variance cells saturate to a white ceiling, flattening the gradient. **Resolved: keep as spec'd (AC3).** Raw stddev already has enough dynamic range on game footage (stable chrome ≈ 0–5, gameplay ≈ 50–120); per-image normalization would amplify codec/sensor noise in the stable regions and break cross-cell comparability, and `variance_heatmap.png` already provides a min-max'd view. No code change.
- [x] [Review][Decision] `--heatmap` HSV-variance ignores Hue circularity — naive per-channel stddev on OpenCV's circular H (0–179) injects phantom variance on red regions. **Resolved: drop the Hue channel — the heatmap scalar = mean of the Saturation + Value stddevs only.** Converted to a Patch below.

**Patch** (unchecked):

- [x] [Review][Patch] `--heatmap` scalar = mean of the S and V stddev maps only (drop H, which is circular and meaningless under a naive stddev); update the `.md` heatmap description accordingly. [apps/tooling/tools/overlay_stack_analyzer.py: `_process_cell` heatmap branch; apps/tooling/tools/overlay_stack_analyzer.md] _(from resolved Decision 2)_

- [x] [Review][Patch] Validate `--ref-height` (`parser.error` if `< 1`) and clamp the derived width to `max(1, round(ref_height*w/h))` in `_target_shape` — a degenerate aspect or `--ref-height 0` otherwise builds a 0-dim target that makes `cv2.resize` raise for every cell. [apps/tooling/tools/overlay_stack_analyzer.py: `_parse_args` / `_target_shape`]
- [x] [Review][Patch] Validate `--min-frames` (`parser.error` if `< 1`) — the CLI currently accepts `0`/negative, silently disabling the skip gate (a 1-frame cell then gets a zero-variance `stddev.png` that sorts to the top of the stability ranking); the TUI flow already guards this. [apps/tooling/tools/overlay_stack_analyzer.py: `_parse_args`]
- [x] [Review][Patch] Guard `_welford_finalize` against tiny-negative variance from float-cancellation roundoff: `var = np.maximum(m2 / n, 0.0)` before `np.sqrt`, so `stddev.png` and the heatmap normalize can't be NaN'd. [apps/tooling/tools/overlay_stack_analyzer.py: `_welford_finalize`]
- [x] [Review][Patch] Wrap the `overlay_stacks_summary.json` write (`open(...,"w")` + `json.dump`) in `try/except OSError` → stderr + `return 1`, like every other write — a disk-full / path-is-a-dir failure after the images are written otherwise leaves a truncated "audit-trail" file plus an uncaught traceback. [apps/tooling/tools/overlay_stack_analyzer.py: `main`]
- [x] [Review][Patch] Wrap the two `os.listdir` calls in `_discover_cells` in `try/except OSError` (skip the unreadable version dir; `return []` for an unreadable root) so a permission error doesn't surface as a bare traceback. [apps/tooling/tools/overlay_stack_analyzer.py: `_discover_cells`]
- [x] [Review][Patch] `flow_tool7` — guard the `--min-frames` / `--ref-height` int parsing against strings where `.isdigit()` is True but `int()` raises (superscript digits): `s.isascii() and s.isdigit()` (or `try/except ValueError`). [apps/tooling/wardentooling.py: `flow_tool7`]
- [x] [Review][Patch] `flow_tool7` — `.strip()` the `--input` / `--output` text before the truthiness check so a whitespace-only entry falls back to the default instead of being passed through as a junk path. [apps/tooling/wardentooling.py: `flow_tool7`]
- [x] [Review][Patch] `overlay_stack_analyzer.md` — note that `stability_score` is an absolute mean-of-stddev value: only meaningful relative to other cells in the same run, and it shifts when `--ref-height` changes (resizing changes pixel values). [apps/tooling/tools/overlay_stack_analyzer.md]
- [x] [Review][Patch] Add a `--ref-height` end-to-end test through `main()` — the resize-to-ref-height path in `_process_cell` is currently exercised by no test (only `_target_shape` is unit-tested, with `None`/`720`). [apps/tooling/tests/test_overlay_stack_analyzer.py]

_All 10 patches applied 2026-05-12 (same code-review session). Full pytest suite **60 green** (was 59; +1 `--ref-height` end-to-end test); `--min-frames 0` / `--ref-height -5` now exit via `argparse.error`. Status stays `review` — the `review → done` flip is the post-merge follow-up per the Two-PR convention, and Task 9 (commit/push/PR-open) is still pending the user's go-ahead, so the code review did not auto-flip the story to `done`._

## Dev Notes

### Strategic context

Tool 7 is the **downstream consumer of Tool 6's output** — explicitly carved out of Story 9.5 ("DO NOT add the overlay/stacking analysis. That's Story 9.6"). Tool 6 writes `output/labeled/v<ver>/<class>/<seq:03d>_<HHmMSs>.png`; Tool 7 reads that tree and emits per-`(version, class)` stacked images. The point is **manual ROI rediscovery for HUD 2.0**: KDA / map-bar / minimap ROIs in `apps/tooling/config/config.yaml` target the legacy HUD and no longer fire; the per-pixel mean ("average screen") + stddev ("what moves") views make it fast to find where the new HUD elements sit by eye. This story produces the analysis images; the actual `config/config.yaml` ROI/HSV update and the `map_config.json` v2 regeneration that follow are **out of scope** (future stories, TBD post-9.6).

### Key code patterns to reuse (NOT reinvent)

| Need | Source | Notes |
|---|---|---|
| Default-dir resolution (`__file__`-relative `<repo_root>/output/...`) | [`video_timeline_labeler.py:849-854 _default_output_dir`](apps/tooling/tools/video_timeline_labeler.py#L849) | Copy verbatim for `_default_input_dir`/`_default_output_dir` so Tool 7's default input == Tool 6's default output. |
| Windows non-ASCII-path-safe PNG **read** | `cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)` | The mirror of the Tool-6-review write fix (P3). `cv2.imread` returns `None` silently on such paths. |
| Windows non-ASCII-path-safe PNG **write** | `ok, buf = cv2.imencode(".png", arr); Path(dest).write_bytes(buf.tobytes())` | Same pattern Tool 6 uses in `_write_label_png`. |
| Headless directory-driven CLI shape (argparse + path defaults + `os.path.abspath`) | [`hash_validator.py:288-330 main`](apps/tooling/tools/hash_validator.py#L288) | Tool 4 is the closest precedent — labeled-dir input, report output, no video. |
| TUI flow / `_TOOL_MAP` / `menu_main` branch / `_reprompt_source` | [`wardentooling.py:277 flow_tool4`](apps/tooling/wardentooling.py#L277), [`wardentooling.py:473 _TOOL_MAP`](apps/tooling/wardentooling.py#L473), [`wardentooling.py:627 Tool 4 branch`](apps/tooling/wardentooling.py#L627), [`wardentooling.py:501 _reprompt_source hash_validator`](apps/tooling/wardentooling.py#L501) | Mirror Tool 4's directory-driven shape (Tool 6's branch is also a good template for the `menu_main`/`save_last_run` wiring — `video_path=None` for both Tool 4 and Tool 7). |
| Sibling-doc convention (don't bloat README / architecture doc) | [`apps/tooling/tools/video_timeline_labeler.md`](apps/tooling/tools/video_timeline_labeler.md) | Tool 6 added a sibling `.md` instead of touching `apps/tooling/README.md` or `docs/architecture-tooling.md`; do the same. |
| pytest layout / `conftest.py` already lifts `apps/tooling/` onto `sys.path` | [`apps/tooling/tests/conftest.py`](apps/tooling/tests/conftest.py) + [`apps/tooling/tests/test_video_timeline_labeler.py`](apps/tooling/tests/test_video_timeline_labeler.py) | No new conftest. Pure helpers top-level → testable without GUI/heavy I/O; tiny `cv2.imencode`-written PNGs for the data-smoke test. |
| Streaming online mean/stddev | Welford's algorithm (textbook) | numpy vectorized over the whole `(H,W,3)` array; `float64` accumulators. **Do not** `np.stack` all frames. |

### Anti-patterns / disasters to avoid

- **DO NOT `np.stack` / load all frames into one array.** A long-video same-class span (Tool 6's same-class auto-backfill writes one PNG per keyframe between two labels) can be hundreds of 1080p frames — that's multi-GB stacked. Stream with Welford; two `float64` images per stat (+ HSV doubles it when `--heatmap`). Re-reading PNGs in a second pass to learn the modal shape is the correct memory/IO trade.
- **DO NOT use `cv2.imread` / `cv2.imwrite` with bare paths.** Both fail silently on Windows non-ASCII paths (the Tool-6 review caught `imwrite`; the same applies to `imread`). Use `np.fromfile`+`cv2.imdecode` / `cv2.imencode`+`Path.write_bytes`.
- **DO NOT add a GUI.** Tool 7 is a headless batch tool — no Tk, no Pillow. (Interactive HSV-band / zone editing already exists as `tools/minimap_zone_selector/` — Tool 7 produces the *static analysis images* that inform that work; it doesn't replace or duplicate the interactive editor.)
- **DO NOT crash the whole run on one bad cell / corrupt PNG / write failure.** Warn to stderr, record `status:"skipped"`/`reason`, move on. The summary JSON is the audit trail.
- **DO NOT silently divide by zero** in `_normalize_uint8` (constant image) or `_welford_finalize` (`count == 0` → raise; `count == 1` → all-zero stddev, not a NaN).
- **DO NOT add `transition` special-casing.** It's the discard bucket; its stacked output is expected to be high-variance noise, and the `stability_score` ranking will naturally push it to the bottom of the summary. Keep the tool dumb — it stacks whatever folders it finds.
- **DO NOT touch `apps/tooling/config/config.yaml`, `map_config.json`, or `contracts/`.** Tool 7 only reads PNGs and writes images + a JSON summary. The ROI/HSV update those analysis images inform is a separate future story.
- **DO NOT modify `docs/architecture-tooling.md` or `apps/tooling/README.md`** — both predate Tool 6; add the sibling `.md` instead (Story 9.5 precedent). A docs-refresh story will catch the as-built docs up to Tools 6+7 later.

### File structure

```
apps/tooling/
  tools/
    overlay_stack_analyzer.py        # NEW (this story)
    overlay_stack_analyzer.md         # NEW (this story — sibling usage/interpretation doc)
    video_timeline_labeler.py         # UNCHANGED (Tool 6 — produces this tool's input)
    frame_labeler.py                  # UNCHANGED (optional LABEL_DISPLAY import for the stdout table)
  tests/
    test_overlay_stack_analyzer.py   # NEW (this story)
    conftest.py                       # UNCHANGED (added in Story 9.5; lifts apps/tooling/ onto sys.path)
  wardentooling.py                    # UPDATED (TUI registration: flow_tool7 + _TOOL_MAP + choices_main + menu_main branch + _reprompt_source branch)

# Input — produced by Tool 6 (not committed; under the existing `output/` gitignore):
output/labeled/v<ver>/<class>/<seq:03d>_<HHmMSs>.png

# Output — produced by this tool (not committed; `output/` already gitignored — no .gitignore change needed):
output/overlay_stacks/
  overlay_stacks_summary.json
  v1.0/
    lobby/      { mean.png, stddev.png[, variance_heatmap.png] }
    horizon/    { mean.png, stddev.png[, variance_heatmap.png] }
    ...
  v2.0/
    lobby/      ...
    ...
```

### Testing standards

- `pytest` 8.0+ already in `apps/tooling/pyproject.toml` `[project.optional-dependencies] dev`; run via `uv run pytest`. `apps/tooling/tests/conftest.py` already prepends `apps/tooling/` to `sys.path` — no new conftest.
- **No GUI testing** needed (the tool is headless). Pure helpers (`_discover_cells`, `_modal_shape`, `_target_shape`, `_welford_*`, `_normalize_uint8`, `_stability_score`, `_cell_output_paths`, `_default_*_dir`) get full unit coverage; one small `tmp_path` data-smoke test exercises `_process_cell`/`main` end-to-end with tiny `cv2.imencode`-written PNGs (no real video, no ffmpeg).
- Run commands: `cd apps/tooling && uv run pytest tests/test_overlay_stack_analyzer.py -v` (this module) and `cd apps/tooling && uv run pytest` (full suite — must stay green; currently 35 tests). Pre-commit/CI: `pnpm --filter tooling test` is the orchestrator wrapper and picks up new `test_*.py` files automatically.

### Library / framework requirements

- **Python ≥ 3.11** (pyproject baseline).
- **OpenCV** (`opencv-python ≥ 4.8, < 5`) — already a dep. Used for `imdecode`/`imencode`, `cvtColor`, `resize`, `applyColorMap`.
- **NumPy** (`numpy ≥ 1.24, < 2`) — already a dep. The whole stat core (`float64` accumulators, Welford, clipping, normalization).
- **No Pillow, no Tkinter, no ffmpeg.** Headless image-math tool. **No new dependencies** — do not add any to `pyproject.toml`.

### Sprint-fit + dependencies

- **Track C** (tooling chain) per [sprint-plan.md:111](_bmad-output/sprint-plan.md#L111). Parallel with Tracks A/B; independent of the AR-SPIKE outcome.
- **Upstream:** Story 9.5 (Tool 6) — produces this tool's input dataset. Story 9.5 is in `review` (deliverable + code-review patch pass landed; smoke test PASSED on a 127.7-min real EVA capture). Tool 7 can be built against Tool 6's actual output now; it does not depend on Story 9.5 being `done` (no shared code, just a directory contract).
- Stories 9.1–9.4 neither block nor are blocked by this.
- **Downstream:** a future re-fingerprinting story (TBD, post-9.6) consumes Tool 7's mean/stddev images to update `config/config.yaml` ROIs/HSV bands and regenerate `map_config.json` v2 (with its own `schema_version: 1` + new-HUD-partition AC) — **out of this story's scope**.

### Project Structure Notes

- Naming: `overlay_stack_analyzer.py` follows the snake_case + descriptive-noun convention (`game_detector.py`, `frame_labeler.py`, `map_config_generator.py`, `hash_validator.py`, `warden_analyzer.py`, `video_timeline_labeler.py`).
- Tool 7 sits next to Tool 6 in `tools/`; both are additive to the legacy Tools 1–5 pipeline. Tool 7 is "Tool 7" everywhere user-facing (TUI label `"Tool 7 — Analyze Overlay Stacks"`, `save_last_run` key `"overlay_stack_analyzer"`), consistent with Tool 6's `"video_timeline_labeler"` registration.
- Output root `output/overlay_stacks/` is a new sibling of Tool 6's `output/labeled/` and Tool 2's `output/labeled/`. It's covered by the existing `output/` gitignore entry — **no `.gitignore` change** (unlike Story 9.5, which had to add `videos/`).
- `_default_input_dir`/`_default_output_dir` inherit Tool 6's `__file__`-relative resolution deliberately, so the known deferred-work item "_default_output_dir resolves four levels above tools/" (see `_bmad-output/implementation-artifacts/deferred-work.md`) applies here too by design — keeping the two tools' path math identical is worth more than "fixing" it in only one of them.
- The Epic 9 charter in `_bmad-output/epics-and-stories.md` enumerates Stories 9.1–9.4 only; 9.5 and 9.6 were added post-planning via the new-HUD initiative (recorded in `_bmad-output/sprint-status.yaml`'s header and in `project_warden_new_hud_labeler.md`). This story does **not** retro-edit the charter — that's known doc-debt for a future docs-refresh, same as Story 9.5.

### References

- [Source: _bmad-output/epics-and-stories.md#Epic-9](_bmad-output/epics-and-stories.md#L2614) — Epic 9 charter (Tooling — V1 Pipeline Hardening); 9.5/9.6 not yet enumerated there
- [Source: _bmad-output/sprint-status.yaml](_bmad-output/sprint-status.yaml#L2) — `last_updated` history; "new-HUD work" prerequisite; Tool 6/7 provenance
- [Source: _bmad-output/sprint-plan.md#Track-C](_bmad-output/sprint-plan.md#L111) — Track C tooling chain
- [Source: _bmad-output/implementation-artifacts/9-5-video-timeline-labeler-tool-6.md](_bmad-output/implementation-artifacts/9-5-video-timeline-labeler-tool-6.md) — Tool 6 story (this tool's input producer); see its Dev Notes "DO NOT add the overlay/stacking analysis" carve-out and its output-path spec (AC6)
- [Source: apps/tooling/tools/video_timeline_labeler.py:849-854](apps/tooling/tools/video_timeline_labeler.py#L849) — `_default_output_dir` resolution to copy
- [Source: apps/tooling/tools/video_timeline_labeler.md](apps/tooling/tools/video_timeline_labeler.md) — sibling-doc template
- [Source: apps/tooling/tools/hash_validator.py:288-330](apps/tooling/tools/hash_validator.py#L288) — headless directory-driven CLI precedent (Tool 4)
- [Source: apps/tooling/tools/frame_labeler.py:23-56](apps/tooling/tools/frame_labeler.py#L23) — `MAP_LABELS` / `LABEL_DISPLAY` (optional for the stdout table only)
- [Source: apps/tooling/wardentooling.py:277-312](apps/tooling/wardentooling.py#L277) — `flow_tool4` shape; [wardentooling.py:473-480](apps/tooling/wardentooling.py#L473) `_TOOL_MAP`; [wardentooling.py:501-502](apps/tooling/wardentooling.py#L501) `_reprompt_source` hash_validator branch; [wardentooling.py:656-671](apps/tooling/wardentooling.py#L656) Tool 6 `menu_main` branch
- [Source: apps/tooling/tests/conftest.py](apps/tooling/tests/conftest.py) — existing `sys.path` shim (no new conftest)
- [Source: docs/architecture-tooling.md](docs/architecture-tooling.md) — tooling pipeline architecture (predates Tools 6/7; do not edit)
- [Source: _bmad-output/implementation-artifacts/deferred-work.md](_bmad-output/implementation-artifacts/deferred-work.md) — `_default_output_dir` four-levels-up deferral (inherited by design)
- Memory: `project_warden_new_hud_labeler.md` — Tool 6/7 locked plan + design decisions
- Memory: `feedback_ac_checkbox_tighten.md` — AC checkbox convention for post-merge items
- Memory: `feedback_two_pr_docs_execution.md` — Two-PR pattern for sprint-status `review → done` flips

## Dev Agent Record

### Agent Model Used

`claude-opus-4-7[1m]` (Claude Opus 4.7, 1M context) — via `/bmad-dev-story 9.6`.

### Debug Log References

- **Test runs.** `cd apps/tooling && uv run pytest tests/test_overlay_stack_analyzer.py -v` → 24 passed (0.5 s). `cd apps/tooling && uv run pytest` (full suite) → 59 passed (0.5 s), up from 35 — no regressions.
- **Manual smoke (Task 6) — synthetic-tree fallback.** No real `output/labeled/` on this box (Story 9.5's smoke ran on a different machine; the AC explicitly allows a synthetic fallback). Built `output/labeled/v2.0/{lobby,horizon,transition}/` with `cv2.imencode`-written PNGs: `lobby` = 5× 180×320 frames (stable cyan top bar + stable red bottom bar + RNG-noise center), `horizon` = 4× 180×320 (stable orange bar + RNG center) + 1× 360×640 odd-size frame, `transition` = 1× RNG frame. Ran:
  - `uv run python tools/overlay_stack_analyzer.py` → `Discovered 3 cell(s) across 1 HUD version(s): v2.0/horizon, v2.0/lobby, v2.0/transition`; `lobby` & `horizon` → `mean.png`+`stddev.png` under `output/overlay_stacks/v2.0/<class>/`; `transition` → `skipped (too_few_frames)` and sorted last; stdout table rendered (`lobby` 26.436, `horizon` 44.625, `transition` —); `overlay_stacks_summary.json` well-formed, `cells` sorted ascending by `stability_score`; `horizon` entry has `resized_count: 1` (the 360×640 frame), `frame_shape: [180,320,3]`.
  - re-run → outputs overwritten cleanly (deterministic).
  - `uv run python tools/overlay_stack_analyzer.py --heatmap` → added `variance_heatmap.png` (3-channel) per `ok` cell; `summary["heatmap"] == true`.
  - Eyeballed `output/overlay_stacks/v2.0/lobby/mean.png` — stable cyan/red bars crisp, center a blended haze, margins dark (looks like a plausibly-averaged screen, not garbage). `output/overlay_stacks/v2.0/lobby/stddev.png` — bars & margins near-black (= stable HUD chrome → ROI candidates), center bright (= volatile). Semantics confirmed.
- **TUI wiring check.** `python -c "import wardentooling as w; assert w._TOOL_MAP['overlay_stack_analyzer'] == ('Tool 7 — Analyze Overlay Stacks', w.flow_tool7)"` → OK. `ast.parse` on both `wardentooling.py` and `tools/overlay_stack_analyzer.py` → syntax OK.
- **Non-ASCII path safety.** Decode is `np.fromfile` + `cv2.imdecode` (not `cv2.imread`); write is `cv2.imencode` + `Path.write_bytes` (not `cv2.imwrite`) — mirrors the Tool 6 review fix; the test box's path (`C:\Users\stwie\…`) is ASCII so this is by-construction, verified via the round-trip test.
- **Encoding cosmetic.** The em-dash in `[v/cls] N frame(s) — processing...` renders as `?` on the cp1252 Windows console (same as Tool 6's `→`/`⚠`/`✓` glyphs) — display-only, files are UTF-8.

### Completion Notes List

- **Tool 7 (`overlay_stack_analyzer.py`)** — headless batch analyzer. Walks `output/labeled/v*/<class>/*.png`, groups into `(version, class)` cells, streams per-pixel mean + population stddev (Welford's online algorithm on `float64` accumulators — never `np.stack`s all frames; peak RAM a few hundred MB per cell, cells run sequentially), writes `mean.png` + `stddev.png` (+ optional `variance_heatmap.png` from an HSV-space second Welford pass under `--heatmap`) into a mirrored `output/overlay_stacks/` tree, plus `overlay_stacks_summary.json` (run metadata + a `cells[]` array sorted ascending by `stability_score`; skipped cells sort last). CLI: `[--input] [--output] [--min-frames N=2] [--ref-height H] [--heatmap]`; defaults `--input` = `<repo>/output/labeled` (path math copied verbatim from `video_timeline_labeler._default_output_dir()`), `--output` = `<repo>/output/overlay_stacks`.
- **Robustness.** Off-shape frames are resized to the cell's modal shape (`INTER_AREA`/`INTER_LINEAR`; `--ref-height` overrides to a fixed height keeping modal aspect). `cv2.imdecode`-fail / write-fail / unexpected per-cell errors are logged to stderr and recorded as `skipped` (`no_readable_frames` / `too_few_frames` / `error`) — one bad cell never aborts the batch. `_normalize_uint8` and `_welford_finalize` guard against div-by-zero (constant array → all-zero; `count == 0` → `ValueError`; `count == 1` → all-zero stddev). No `transition` special-casing — it stacks whatever folders it finds; the `stability_score` ranking naturally floors the discard bucket.
- **Out of scope (per the story).** Tool 7 only reads PNGs and writes images + a JSON summary. It does **not** touch `apps/tooling/config/config.yaml`, `map_config.json`, or `contracts/`; the ROI/HSV update and `map_config.json` v2 regen those analysis images inform are a separate future re-fingerprinting story. `docs/architecture-tooling.md` and `apps/tooling/README.md` were **not** edited (both predate Tools 6 & 7) — Tool 7 ships a sibling `overlay_stack_analyzer.md` instead, same as Story 9.5.
- **Spec deviations / notes.** (1) `flow_tool7` warns + re-prompts on a bad `--min-frames` (per AC9) and warns + skips on a bad `--ref-height` (AC9 only said "appended when a positive integer is entered" — chose a warning over silent drop). (2) `LABEL_DISPLAY` pretty-name polish for the stdout table was skipped (AC1/Task 1 said optional) — raw dir names. (3) Two-pass modal-shape approach used as spec'd (not the first-frame-as-target alternative). (4) Branch `tool-7-overlay-stack-analyzer` was cut off `tool-6-video-timeline-labeler` (not `main`) because Tool 6 isn't merged yet and Tool 7 depends on its `conftest.py`, the `output/labeled/` directory contract, and the Tool 6 TUI registration it inserts next to.
- **Held `[ ]` (post-merge admin, per the AC-checkbox-tighten + Two-PR conventions):** AC11 (`review → done` sprint-status flip), AC12 (single-PR delivery + the follow-up flip), and Task 9's PR sub-boxes. Also pending the user's go-ahead: `git commit` of the deliverable on the branch, `git push`, and opening the PR (`/bmad-dev-story` left the changes in the working tree; commit/push/PR are the natural handoff but were not done autonomously).
- **Tests:** 24 new (every pure helper + `_read_bgr` round-trip + a `tmp_path` data smoke through `main()` incl. `--heatmap`, `too_few_frames`, and the no-cells `return 1` path). Full suite green at 59.

### File List

- **Added** `apps/tooling/tools/overlay_stack_analyzer.py`
- **Added** `apps/tooling/tools/overlay_stack_analyzer.md`
- **Added** `apps/tooling/tests/test_overlay_stack_analyzer.py`
- **Modified** `apps/tooling/wardentooling.py` (Tool 7 flow + `_TOOL_MAP` + `_reprompt_source` + `choices_main` + `menu_main` branch)
- **Modified** `_bmad-output/sprint-status.yaml` (`9-6-overlay-stack-analyzer-tool-7` entry added under `epic-9` at `ready-for-dev`; lifecycle flips across dev work; `last_updated` bumped — final `review → done` flip is the post-merge follow-up)
- **Modified** `_bmad-output/implementation-artifacts/9-6-overlay-stack-analyzer-tool-7.md` (this file: status, ACs, tasks, Dev Agent Record, File List, Change Log)

### Change Log

| Date       | Author                  | Summary |
|------------|-------------------------|---------|
| 2026-05-12 | post-merge follow-up (Opus 4.7 1M) | Two-PR post-merge follow-up (branch `story-9.6-postmerge`, after main PR #8 merged to `main`). Status `review → done`; AC11/AC12 + Task 9's PR sub-boxes → `[x]`; sprint-status `9-6-overlay-stack-analyzer-tool-7: review → done`, `last_updated` bumped, `epic-9` stays `in-progress` (9.1–9.4 still `backlog`). Folded in (commit `372383f`): Tools 6 & 7 `_default_*_dir` now resolve **one** level up from `tools/` → `apps/tooling/output/{labeled,overlay_stacks}/` (already gitignored) instead of an un-ignored repo-root `output/`; lockstep `Tool7._default_input_dir() == Tool6._default_output_dir()` preserved; `*.md` + argparse help updated; the deferred-work "four levels above tools/" entry marked RESOLVED. Manual smoke run against the real 2,748-frame `apps/tooling/output/labeled/v2.0/` dataset: zero-arg run discovered all **16 cells** (14 maps + lobby + score + transition); `--heatmap` / `--ref-height 1080` exercised; the earlier review-patch CLI guards (`--min-frames 0` / `--ref-height < 1` → `argparse` error) confirmed live; full pytest suite 60 green. |
| 2026-05-12 | code-review (Opus 4.7 1M) | Code review (`/bmad-code-review` — Blind Hunter + Edge Case Hunter + Acceptance Auditor). Acceptance Auditor: zero AC violations. 2 decision-needed (D1 `stddev.png` absolute-clip → keep as spec'd; D2 `--heatmap` Hue circularity → drop H, scalar = mean of S+V stddev), 9 patch + 1 from D2 = 10 patches, all applied: `--ref-height`/`--min-frames` `argparse` validation (`< 1` → error) + `_target_shape` width clamp `max(1, …)`; `_welford_finalize` `var = np.maximum(m2/n, 0.0)`; `overlay_stacks_summary.json` write wrapped in `try/except OSError → return 1`; `_discover_cells` `os.listdir` wrapped in `try/except OSError`; `flow_tool7` ASCII-digit guard + `.strip()` on text prompts; heatmap scalar drops Hue; `.md` notes (Hue-drop rationale, `stability_score` is absolute/per-run/`--ref-height`-dependent); +1 `--ref-height` end-to-end test. Full pytest suite 59 → 60 green. ~16 findings dismissed (spec-mandated / handled / noise). Status stays `review` (the `review → done` flip is the post-merge Two-PR follow-up; Task 9 commit/push/PR still pending the user's go-ahead). |
| 2026-05-12 | dev-story (Opus 4.7 1M) | Tool 7 implemented. Added `apps/tooling/tools/overlay_stack_analyzer.py` (headless batch analyzer: streaming Welford mean/stddev per `(version,class)` cell, optional HSV variance heatmap, mirrored `output/overlay_stacks/` tree, stability-ranked `overlay_stacks_summary.json`; `imdecode`/`imencode` for Windows non-ASCII path safety; modal-shape resize via two cheap passes — no `np.stack` of all frames), `apps/tooling/tools/overlay_stack_analyzer.md` (sibling usage/interpretation doc), `apps/tooling/tests/test_overlay_stack_analyzer.py` (24 tests — every pure helper + `_read_bgr` round-trip + a `tmp_path` data smoke through `main()`). Wired Tool 7 into `apps/tooling/wardentooling.py` (`flow_tool7` + `_TOOL_MAP` + `choices_main` + `menu_main` branch + `_reprompt_source` branch). Full pytest suite 35 → 59, green. Manual smoke (Task 6) run against a synthetic labeled tree (no real dataset on the box — the AC's permitted fallback): discovery/processing/summary/table/re-run-overwrite/`--heatmap` all verified; `mean.png`/`stddev.png` eyeballed and semantically correct. AC1–AC10 + Tasks 1–8 → `[x]`; sprint-status flipped `ready-for-dev → in-progress → review`, `last_updated` bumped; Status → `review`. AC11/AC12 + Task 9's PR sub-boxes held `[ ]` (post-merge admin per the AC-checkbox-tighten + Two-PR conventions); `git commit`/`push`/PR-open of the deliverable on branch `tool-7-overlay-stack-analyzer` (cut off `tool-6-video-timeline-labeler` — Tool 6 not yet on `main`) left for the user's go-ahead. |
| 2026-05-12 | create-story (Opus 4.7 1M) | Story 9.6 drafted — Tool 7 (Overlay Stack Analyzer): headless batch tool that walks Tool 6's `output/labeled/v<ver>/<class>/*.png` dataset and emits per-`(version,class)` `mean.png` + `stddev.png` (+ optional HSV `variance_heatmap.png`) into a mirrored `output/overlay_stacks/` tree, plus an `overlay_stacks_summary.json` ranked by visual stability. Streaming Welford accumulators (no `np.stack` of all frames), `imdecode`/`imencode` for Windows non-ASCII path safety, modal-shape resize within a cell, TUI registration mirroring Tool 4/6, pytest for the pure helpers + a tiny `tmp_path` data-smoke test. AC11/AC12 + Task 9's final box held `[ ]` per the AC-checkbox-tighten convention (post-merge admin: `review → done` flip via the Two-PR follow-up). No new deps (numpy/opencv already present). Added the `9-6-overlay-stack-analyzer-tool-7` entry to `_bmad-output/sprint-status.yaml` under `epic-9` (already `in-progress`) and flipped it `→ ready-for-dev`. |
