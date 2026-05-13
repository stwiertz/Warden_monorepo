# Story 9.8: Per-frame ROI Detection Tester (Tool 9)

Status: review

## Story

As **Stephane** (sole tooling user; rebuilding the EVA game-state detector for the redesigned HUD),
I want **a headless batch tool that consumes Tool 8's `discovered_zones.yaml` and Tool 6's labeled PNG dataset, replays every labeled frame through every discovered zone's HSV band per-frame, and reports per-zone, per-class, and confusion-matrix accuracy for both the *game-state classifier* (lobby / in_match / score / transition) and the *map-ID classifier* (artefact / atlantis / … / the_rock)**,
so that **I can see, with concrete numbers, whether the ROIs Tool 8 picked actually recognize the labeled maps + game states on real frames — closing the per-frame validation gap Tool 8's `GameStateValidator` deliberately punted on (mean/std proxy only) and providing the empirical accept/iterate signal for hand-merging the fragment into `config/config.yaml`.**

**Strategic context.** This is the per-frame validation Tool 8 explicitly defers in two places: `apps/tooling/tools/auto_roi_discoverer.md` ("Exact per-frame validation against the labeled PNG dataset (re-streaming Tool 6's frames through the band) is **out of scope here** — it's part of the future re-fingerprinting story") and `auto_roi_discoverer/validator.py:18-20`. Tool 8 reads Tool 7's aggregates (`stats.npz` mean/std) by design — its `GameStateValidator` is a **mean/std proxy**, not per-frame. Tool 9 is the consumer Tool 8 was waiting for: it re-streams the labeled PNGs (Tool 8's "DO NOT" is now the right thing — Tool 9's whole point), applies each zone's hue-wrap-aware `cv2.inRange` + `min_ratio` test per frame, aggregates fires into TP/FP/FN/TN per zone, derives precision/recall/F1 per zone and per class, and writes both a machine-readable `report.json` and a human-readable `summary.md`. Closes the new-HUD tooling chain validation loop: **Tool 6 label → Tool 7 stack → Tool 8 discover → Tool 9 measure.** Tool 9 still **never** writes `config/config.yaml`; the hand-merge into config + `map_config.json` v2 regen remain a future re-fingerprinting story.

**Two classifiers, one tool.** The `discovered_zones.yaml` Tool 8 emits carries two zone groups (per the AC15 correct-course on Story 9.7): four game-state classes (`lobby`, `in_match`, `score`, `transition`) feeding the game-state detector cascade, and N per-map classes (`artefact`, `atlantis`, … — whichever `MAP_LABELS` cells the dataset had) feeding the map-ID fingerprints. Tool 9 evaluates **both** in one pass over the labeled dataset, with distinct decision rules per classifier (documented in AC4/AC5), and emits one merged report covering both. The labeled folder maps to ground truth: `lobby/` → game-state `lobby` (map-ID skipped); `score/` → game-state `score` (map-ID skipped); `transition/` → game-state `transition` (map-ID skipped); any `MAP_LABELS` folder → game-state `in_match` *and* map-ID = the folder name.

**Type:** Standard tooling feature story. Track C (tooling chain). No spike-or-split flag — smaller than Tools 6/7/8 (headless batch + reporting; no GUI; no engine math beyond reusing `cv2.inRange` + the discovered-zones-yaml parse). Single-file shape like Tool 7 (`overlay_stack_analyzer.py`) — pure logic + a thin `main()`. Single-PR delivery + a tiny post-merge follow-up commit/PR for the sprint-status `review → done` flip (Two-PR pattern, `feedback_two_pr_docs_execution.md`).

## Acceptance Criteria (checklist)

> **AC checkbox convention:** items whose endpoint depends on **post-merge actions** (sprint-status `review → done` flip, PR merge) are held `[ ]` with carve-out notes per the AC-checkbox-tighten convention (`feedback_ac_checkbox_tighten.md`). All other items flip to `[x]` on dev-agent completion.

1. [x] **AC1 — New Tool 9 single-file module at `apps/tooling/tools/roi_detection_tester.py`.** Headless batch tool (no Tk), single file, shaped like `overlay_stack_analyzer.py`: module-level pure helpers (`load_zones_fragment`, `iter_labeled_frames`, `zone_fires_on_frame`, `evaluate_frame`, `aggregate_metrics`, `write_report`, `write_summary`), an `argparse`-driven `main(argv) -> int` returning a process exit code, and `if __name__ == "__main__": sys.exit(main(sys.argv[1:]))`. **No GUI**; **no Tk import**; invoked as `python tools/roi_detection_tester.py [args]` (and from the TUI per AC9). Pure logic is importable + unit-testable without any GUI subsystem.

2. [x] **AC2 — CLI arguments + input resolution.**
   - `--zones` — path to a Tool 8 `discovered_zones.yaml` (or `.json`; the loader accepts both based on suffix). **Default** = `apps/tooling/output/auto_rois/v<latest>/discovered_zones.yaml` — i.e. the most-recent `v*/` under `apps/tooling/output/auto_rois/` (sorted lexicographically on the directory name; ties → most-recent `mtime`); if no `v*/` directory exists → clean error `"run Tool 8 first"`. Define a `_default_zones_path()` helper computing this `__file__`-relative (mirroring Tool 7's `_default_output_dir` / Tool 8's `default_input_dir` patterns) so the default tracks the layout regardless of checkout location.
   - `--labeled` — path to Tool 6's labeled-dataset root (the directory containing `v<ver>/<class>/*.png`). **Default** = `apps/tooling/output/labeled` — the directory Tool 6 writes to and Tool 7 reads from; reuse `overlay_stack_analyzer._default_input_dir()` (which already resolves to it) rather than re-deriving the path.
   - `--output` — path to the report-output root. **Default** = `apps/tooling/output/roi_detection_tests` — a new sibling of `output/labeled/`, `output/overlay_stacks/`, `output/auto_rois/`, under the existing `apps/tooling/output/` gitignore. **No `.gitignore` change.**
   - `--version` — HUD version override (`v2.0`, `v3.0`, …). When omitted, auto-detect: prefer `_metadata.hud_version` from the zones yaml; if absent, derive from the zones-yaml path's parent directory name (`auto_rois/v2.0/discovered_zones.yaml` → `v2.0`); record the chosen version + how it was inferred in `report.json["run_metadata"]`.
   - `--limit N` — cap frames per class at N (for fast-iteration smoke runs; default = no cap, process all frames in each class folder).
   - `--ref-height H` — override the reference resolution to scale each frame to before applying the zone rects. When omitted: take `_metadata.frame_shape[0]` from the zones yaml (the height in cell pixel space — `1080` for the user's current dataset). If neither is available → clean error `"--ref-height required (zones yaml has no _metadata.frame_shape)"`.
   - `--game-state-threshold T` (default `0.5`) — minimum max-class-score for the game-state classifier to commit a prediction; below threshold → `"unknown"`. Documented in the `.md`.
   - `--map-threshold T` (default `0.5`) — same for the map-ID classifier.
   - `--save-frame-predictions` — also write `frame_predictions.csv` (one row per evaluated frame). Default = off (it's ~3k rows on the current dataset; keep it opt-in).
   - **Argparse validation guards** (mirror Tool 7's `argparse.error` style): `--limit` must be a positive int; `--ref-height` must be `≥ 1`; thresholds must be in `[0.0, 1.0]`; non-existent `--zones` / `--labeled` paths → `argparse.error` with the offending path; invalid combos → exit before any work starts.

3. [x] **AC3 — Zones-fragment loader (`load_zones_fragment(path) -> ZonesFragment`).** Pure helper. Reads the yaml/json Tool 8 emits (the shape `discovered_zones.yaml` already on disk — see `apps/tooling/output/auto_rois/v2.0/discovered_zones.yaml` for the live example): a `_metadata` block + one key per class → list of zone dicts `{name, x, y, width, height, hsv: {h_center, h_tol, s_center, s_tol, v_center, v_tol}, min_ratio}` with HSV in **user space** (H 0–360, S/V 0–100). Returns a `ZonesFragment` dataclass with `metadata: dict`, `game_state_zones: dict[str, list[ZoneSpec]]` (the four game-state classes only, in `TARGET_CLASSES` order — `lobby/in_match/score/transition`; missing classes default to empty list), `map_zones: dict[str, list[ZoneSpec]]` (every present `MAP_LABELS` class, in `MAP_LABELS` order; missing classes default to empty list), and an `ignored_classes: list[str]` for any top-level key that's neither game-state nor a `MAP_LABELS` map (warn to stderr — empty per the AC15 contract, but tolerated). `ZoneSpec` mirrors `auto_roi_discoverer.model.HsvBand` + `Rect` shape; reuse the dataclasses from `tools.auto_roi_discoverer.model` (`Rect`, `HsvBand`) rather than re-defining — same import path the test suite already uses. Empty zone lists are fine; the loader does NOT error on a class with zero zones (the user may legitimately export `lobby: []` etc.). Parse errors → clean error to stderr + exit 1 *before* the main batch loop.

4. [x] **AC4 — Game-state classifier (4-way).** For each labeled frame, compute a per-class **score** ∈ `[0, 1]` = `fires_count / n_zones` for each of the four game-state classes whose `zone_list` is non-empty (a class with 0 zones contributes score `0` / never wins). The **predicted game-state** = the class with the highest score, **provided** that max-score `≥ --game-state-threshold` (default `0.5`); otherwise the prediction is `"unknown"`. **Tie-break** when two classes tie on max-score: prefer the class with more zones (more confidence); secondary tie-break by `TARGET_CLASSES` order (`lobby > in_match > score > transition`); document both rules in the `.md`. The ground-truth game-state per labeled folder: `lobby` → `lobby`; `score` → `score`; `transition` → `transition`; any `MAP_LABELS` folder → `in_match`; any other folder name → skip the frame for the game-state classifier (warn once to stderr per unrecognised folder name). Excludes `frame_labeler.MAP_LABELS` membership check — reuse `from tools.frame_labeler import MAP_LABELS`.

5. [x] **AC5 — Map-ID classifier (N-way).** Only applies when the labeled folder is in `MAP_LABELS`. For each such frame, compute a per-class **score** ∈ `[0, 1]` = `fires_count / n_zones` for each of the per-map classes whose `zone_list` is non-empty. **Predicted map** = argmax with `≥ --map-threshold` (default `0.5`); otherwise `"unknown"`. **Tie-break** by `MAP_LABELS` order. (No score is computed for a map class whose `zone_list` is empty — that map just can't win on this frame.) Map-ID prediction is skipped (`predicted_map = None` in the per-frame record) when the labeled folder is `lobby` / `score` / `transition`.

6. [x] **AC6 — Per-frame band-fire test (`zone_fires_on_frame(zone, frame_bgr_at_ref) -> tuple[bool, float]`).** Pure helper, vectorised, mirrors the existing hue-wrap `cv2.inRange` logic. Approach: **resize each labeled frame once** to the reference resolution (`(ref_w, ref_h)` derived as `frame.shape[1] * ref_h / frame.shape[0]` width-scale to preserve aspect ratio + `cv2.resize` with `INTER_AREA` for downscale / `INTER_LINEAR` for upscale) so the zone rects (in 1080-row cell pixel space) apply directly to the frame's pixel space without per-zone scaling. Then for each zone: clip its rect to the frame; `cv2.cvtColor(region, COLOR_BGR2HSV)`; convert the user-space HSV band to OpenCV space; apply the hue-wrap-aware `cv2.inRange` + `bitwise_or` for hue-wrap; compute the in-range ratio; return `(ratio >= zone.min_ratio, ratio)`. **Reuse the existing logic** from `apps/tooling/tools/auto_roi_discoverer/validator.py:82 band_inrange_ratio` — extracted/imported, NOT reinvented. Bind once: `from tools.auto_roi_discoverer.validator import band_inrange_ratio` and add the `>= min_ratio` check + the bool wrapper in `roi_detection_tester.py`. Windows non-ASCII-path-safe frame **read**: `cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)` — the same pattern Tools 6/7/8 use; never bare `cv2.imread`.

7. [x] **AC7 — Per-zone, per-class metrics.** Aggregate over the full evaluation pass:
   - **Per zone:** TP = frame's ground-truth class is this zone's owning class AND zone fired; FP = ground-truth ≠ owning class AND zone fired; FN = ground-truth = owning class AND zone did NOT fire; TN = ground-truth ≠ owning class AND zone did NOT fire. Compute `precision = TP / (TP + FP)`, `recall = TP / (TP + FN)`, `F1 = 2·P·R / (P + R)` (each guarded against `/0` → `precision/recall/F1 = 0.0` when denominator is zero, documented). Owning class for a game-state zone = the game-state class it belongs to (frames from the matching folder count as positives — using the AC4 folder→game-state mapping, so frames from any `MAP_LABELS` folder are positives for an `in_match` zone). Owning class for a per-map zone = the map name (frames from that map folder are positives; all other folders — incl. `lobby/score/transition` and other maps — are negatives).
   - **Per class:** macro-average precision/recall/F1 over the class's zones; the classifier-level confusion matrix from AC4/AC5 (rows = ground-truth class, columns = predicted class incl. `"unknown"`); per-class precision/recall/F1 derived from the confusion matrix.
   - **Top-line numbers in `summary.md`:** game-state accuracy = `Σ correct / Σ evaluated` (excluding folders the AC4 mapping rejects); map-ID accuracy = same but only over the `MAP_LABELS` folders; per-class P/R/F1 tables (game-state 4-way + per-map N-way); top-10 worst-performing zones by F1; top-5 worst-confused class pairs by off-diagonal count.

8. [x] **AC8 — Report outputs.** Write under `<output>/v<ver>/<timestamp>/` (where `<timestamp>` = `YYYY-MM-DDTHHMMSS` from `datetime.now().astimezone()` formatted to filesystem-safe; `os.makedirs(..., exist_ok=True)`):
   - **`report.json`** — machine-readable. Keys:
     ```
     {
       "tool": "roi_detection_tester (Tool 9)",
       "generated_at": "<ISO-8601>",
       "run_metadata": {
         "zones_path": <abs>, "labeled_path": <abs>, "version": "v2.0", "version_source": "metadata|path|--version",
         "ref_height": 1080, "ref_height_source": "metadata|--ref-height",
         "game_state_threshold": 0.5, "map_threshold": 0.5, "limit_per_class": null|N,
         "frame_count_by_class": {"lobby": 296, "score": 41, "transition": 44, "artefact": 432, ...},
         "n_zones_by_class": {"lobby": 0, "in_match": 0, "score": 0, "transition": 0, "artefact": 11, ...},
         "skipped_folders": []  # any unrecognised folder names encountered
       },
       "game_state": {
         "accuracy": 0.97, "n_evaluated": N, "n_correct": M,
         "confusion": {"lobby": {"lobby": ..., "in_match": ..., "score": ..., "transition": ..., "unknown": ...}, ...},
         "per_class": {"lobby": {"precision": ..., "recall": ..., "f1": ..., "support": ...}, ...}
       },
       "map_id": {
         "accuracy": 0.92, "n_evaluated": N, "n_correct": M,
         "confusion": {"artefact": {"artefact": ..., "atlantis": ..., ..., "unknown": ...}, ...},
         "per_class": {"artefact": {"precision": ..., "recall": ..., "f1": ..., "support": ...}, ...}
       },
       "per_zone": [
         {"name": "artefact_z1", "owning_class": "artefact", "kind": "map",
          "tp": ..., "fp": ..., "fn": ..., "tn": ..., "precision": ..., "recall": ..., "f1": ..., "fire_rate_on_owning": ..., "fire_rate_on_others": ...},
         ...
       ]
     }
     ```
   - **`summary.md`** — human-readable, ≤ 200 lines. Sections: **Run** (paths, version, frame counts), **Game-state classifier** (accuracy + 4×5 confusion table + per-class P/R/F1), **Map-ID classifier** (accuracy + N×(N+1) confusion table + per-class P/R/F1), **Worst-performing zones** (top-10 by F1, table: name, owning class, kind, TP, FP, FN, precision, recall, F1), **Worst-confused class pairs** (top-5 by off-diagonal count: ground-truth → predicted, count, fraction).
   - **`frame_predictions.csv`** (only when `--save-frame-predictions`) — one row per evaluated frame: `frame_path, ground_truth_folder, ground_truth_game_state, predicted_game_state, gs_max_score, ground_truth_map, predicted_map, map_max_score`. UTF-8, comma-separated, header row.
   - Re-runs do NOT overwrite (the `<timestamp>` subdir keeps them distinct). Write failures → logged to stderr; the tool exits non-zero. Windows non-ASCII-path-safe writes: `Path(...).write_text(..., encoding="utf-8")` for JSON / MD / CSV (no `cv2.imencode` needed — Tool 9 writes no images for V1).

9. [x] **AC9 — TUI registration in `apps/tooling/wardentooling.py`.**
   - Add `flow_tool9() -> tuple[list[str], str | None]` mirroring `flow_tool7`'s directory-driven shape: optional `--zones` text prompt (blank = default), optional `--labeled` text prompt (blank = default), optional `--output` text prompt (blank = default), optional `--limit` text prompt with positive-int validation (blank = no cap), confirm `--save-frame-predictions` (default `False`). Returns `(["tools/roi_detection_tester.py", *extra_args], None)` — invoked as a single file like Tool 7 (NOT `-m`). Returns `([], None)` on Ctrl-C.
   - Insert `"Tool 9 — Test ROI Detection on Labeled Frames"` into `choices_main` in `menu_main`, between `"Tool 8 — Discover Game-State ROIs"` and `"Dev Tools"`.
   - Add the `elif choice == "Tool 9 — Test ROI Detection on Labeled Frames":` branch in `menu_main`'s while-loop, shaped like the Tool 7 branch: collect args → `run_tool` → `save_last_run("roi_detection_tester", "Tool 9 — Test ROI Detection on Labeled Frames", args, None)` on `returncode == 0` (`video_path` is `None`, like Tools 4/7/8).
   - Add `"roi_detection_tester": ("Tool 9 — Test ROI Detection on Labeled Frames", flow_tool9)` to `_TOOL_MAP`.
   - Add a `_reprompt_source` branch for `tool_key == "roi_detection_tester"` that just re-runs `flow_tool9()` (directory-driven; same as the `hash_validator` / `overlay_stack_analyzer` / `auto_roi_discoverer` branches).

10. [x] **AC10 — Pytest.** `apps/tooling/tests/test_roi_detection_tester.py` (new) — pure-logic coverage, all `tmp_path`-based, no Tk, no real video, no ffmpeg:
    - **`load_zones_fragment`:** parse a synthetic yaml with both game-state + per-map keys + a `_metadata` block; assert game-state/map split + ordering (`TARGET_CLASSES` order, `MAP_LABELS` order); empty class lists tolerated; unknown top-level key warns + lands in `ignored_classes`; bad-shape zone dict → clean error.
    - **`zone_fires_on_frame`:** hand-build a synthetic 100×100 BGR frame with a 10×10 solid-coloured rect at known coords + a known HSV band → assert fires=True and ratio is close to 1.0; same frame + a band that misses → fires=False; hue-wrap band crossing 0/360 → fires correctly; rect partially off-frame → clipped, no crash.
    - **Frame resize:** a 720-row frame + `ref_height=1080` → resized to 1080-row with preserved aspect, zone rect at (x=100, y=100, w=10, h=10) lands on the corresponding scaled region (cross-check via a marker-coloured pixel that survives the resize).
    - **`evaluate_frame`:** on a fixture frame + a 3-zone synthetic fragment, the returned per-zone fire bools, the game-state score per class, and the predicted class match a hand-computed expectation.
    - **`aggregate_metrics`:** feed a hand-built list of per-frame results → assert per-zone TP/FP/FN/TN + precision/recall/F1 (including the `/0` guard), per-class confusion matrix (rows + columns incl. `"unknown"`), and top-line accuracy.
    - **End-to-end smoke (`main([...])` on `tmp_path`):** synthesize a 2-class labeled tree (e.g. 3× `lobby/*.png` solid-blue + 3× `artefact/*.png` solid-red) + a 2-zone yaml fragment (one `lobby` zone matching blue, one `artefact` zone matching red) → `main(["--zones", ..., "--labeled", ..., "--output", str(tmp_path)])` returns 0 + writes `report.json` + `summary.md`; assert `report["game_state"]["accuracy"] == 1.0` and `report["map_id"]["accuracy"] == 1.0` (perfect-recognition fixture).
    - **CLI guards:** `--limit -1`, `--ref-height 0`, `--game-state-threshold 1.5`, non-existent `--zones`, missing `--labeled` → `argparse.error` / non-zero exit; no `report.json` written.
    - Run commands: `cd apps/tooling && uv run pytest tests/test_roi_detection_tester.py -v`; full suite gate (`cd apps/tooling && uv run pytest` / `pnpm --filter tooling test`) must stay green — currently **92 tests** (post Story 9.7); this story adds the new module's tests.

11. [x] **AC11 — Manual smoke run against the real labeled dataset + the live Tool 8 fragment.** Run `python tools/roi_detection_tester.py` (zero-arg → defaults; picks up `apps/tooling/output/auto_rois/v2.0/discovered_zones.yaml` + `apps/tooling/output/labeled/v2.0/`). Confirm: the run completes without errors; `report.json` + `summary.md` land under `apps/tooling/output/roi_detection_tests/v2.0/<timestamp>/`; the game-state classifier reports a sane confusion matrix (≥ ~90% on `lobby`/`score`/`transition`, given that those classes' zone lists are empty per the live yaml the room game-state classifier scores 0 → predicted "unknown" — record the observed numbers); the map-ID classifier reports an accuracy per the per-map zones (the user's actual goal — surface which maps the discovered zones recognize properly and which don't). **Numeric expectations are descriptive (record what's observed), not gating** — Tool 9's V1 job is to *measure*, not to guarantee a floor. Record the observed accuracy + the worst-confused class pairs in the Debug Log. (If the real dataset isn't on the box at dev time, fall back to a synthetic `output/labeled/v2.0/` + `output/auto_rois/v2.0/discovered_zones.yaml` tree as Tool 7/8's ACs permitted — record which path was taken.)

12. [x] **AC12 — Sibling usage doc `apps/tooling/tools/roi_detection_tester.md`.** Concise launch + workflow + output-interpretation guide, mirroring `apps/tooling/tools/overlay_stack_analyzer.md` / `apps/tooling/tools/auto_roi_discoverer.md`'s shape: CLI invocation + the TUI path; what the tool does (per-frame replays Tool 6's labeled PNGs through Tool 8's discovered zones; reports per-zone / per-class / confusion-matrix accuracy for both classifiers); the two classifiers + their decision rules + ground-truth mapping (`lobby/score/transition` folder → game-state ground truth; `MAP_LABELS` folder → game-state `in_match` + map-ID ground truth); what each output file means (`report.json` = full machine-readable; `summary.md` = human-readable top-line + tables; `frame_predictions.csv` = opt-in per-frame log); the **coordinate-frame contract** (frames resized once to `_metadata.frame_shape[0]` so the zones-yaml rects apply directly; override via `--ref-height`); the **threshold semantics** (`--game-state-threshold` / `--map-threshold` → arg-max score below threshold → `"unknown"`); the **anti-pattern** spelt out (Tool 9 reads Tool 8's exported fragment **never** `config/config.yaml`; never writes `config/config.yaml` either); the recommended end-to-end workflow (Tool 6 label → Tool 7 stack `--ref-height 1080` → Tool 8 discover/accept/export → **Tool 9 measure** → human reviews + iterates the zones via Tool 8 → re-Tool-9 → hand-merge the fragment into `config/config.yaml` + regenerate `map_config.json` v2 — the last step **out of this story's scope**). Like Tools 6/7/8, this is a **sibling doc** — do **NOT** expand `apps/tooling/README.md`, and do **NOT** edit `docs/architecture-tooling.md` (still predates Tools 6/7/8/9; a dedicated docs-refresh story will catch them all up).

13. [ ] **AC13 — Sprint-status entry + lifecycle flip.** `_bmad-output/sprint-status.yaml` gains a `9-8-roi-detection-tester-tool-9` entry under `epic-9`, added at create-story time and set to `ready-for-dev` (`epic-9` is already `in-progress`, so no epic flip — verify this happened before the dev agent reads this file). The entry then flows `ready-for-dev → in-progress → review` across the dev work, and `review → done` post-merge. _Held `[ ]` — the `review → done` flip ships in the post-merge Two-PR follow-up (`feedback_two_pr_docs_execution.md`); `last_updated` bumped each transition; `epic-9` stays `in-progress` (9.1–9.4 still `backlog`)._

14. [ ] **AC14 — Single-PR delivery + follow-up flip.** All file changes ship in **one PR** titled `feat: Tool 9 — ROI detection tester (Story 9.8)` (subject lowercased to `feat: tool 9 — roi detection tester (Story 9.8)` on the commit to satisfy commitlint's `subject-case` — keep the capitalized form in the PR title — matching the Tool 6/7/8 precedent), branch `tool-9-roi-detection-tester` cut off `main` (Tool 8 is merged or merging concurrently — if Tool 8 hasn't merged yet, branch off `tool-8-auto-roi-discoverer` instead and rebase after Tool 8 lands; the dev confirms which case before pushing). PR body links: this story file; the Epic 9 charter at `_bmad-output/epics-and-stories.md` (with the note that Stories 9.5/9.6/9.7/9.8 were added post-planning via the new-HUD initiative and aren't yet enumerated in the charter — known doc-debt, tracked, not corrected here); `apps/tooling/tools/auto_roi_discoverer.md` (the Tool 8 producer doc — Tool 9's input source). The `review → done` sprint-status flip is a separate tiny follow-up commit/PR per AC13. _Held `[ ]` — post-merge admin per the AC-checkbox-tighten + Two-PR conventions; `git commit`/`push`/PR-open of the deliverable on the branch is the natural handoff but is left for the user's go-ahead (same as Stories 9.6/9.7)._

## Tasks / Subtasks

> **Implementation order:** Pure logic first (loader → band-fire test → frame iterator → classifier → aggregator → report writer), wired up via a thin `main(argv)`; then the TUI registration; then tests; then manual smoke; then the sibling doc; then PR + sprint-status. The headless shape means there's no GUI gate — full unit coverage of the math/IO core is achievable end-to-end before the smoke run.

- [x] **Task 1: Module skeleton + CLI + argparse guards (AC: 1, 2)**
  - [x] Create `apps/tooling/tools/roi_detection_tester.py` with the module docstring style of `overlay_stack_analyzer.py` (purpose, V1 scope, "consumes Tool 8 output / produces accuracy report" framing); `from __future__ import annotations` if needed.
  - [x] `_default_zones_path()` — `__file__`-relative resolution of `apps/tooling/output/auto_rois/v<latest>/discovered_zones.yaml`; missing → `None` (handled at argparse-default time → clean error in `main` before any work).
  - [x] `_default_labeled_dir()` / `_default_output_dir()` — import `overlay_stack_analyzer._default_input_dir` for the labeled root; resolve `apps/tooling/output/roi_detection_tests` for the report root.
  - [x] `_parse_args(argv)` — argparse with all flags per AC2, validation guards (positive-int / `[0,1]` thresholds / path existence) raised via `argparse.error` BEFORE main work; `--save-frame-predictions` as a `store_true` flag.
  - [x] `main(argv) -> int` — argparse → load fragment → resolve version + ref-height (record `*_source` for the report) → iterate frames → aggregate → write reports → return `0`; clean error → stderr + return non-zero exit code.

- [x] **Task 2: `load_zones_fragment` + the `ZonesFragment` dataclass (AC: 3)**
  - [x] `ZonesFragment` dataclass: `metadata: dict`, `game_state_zones: dict[str, list[ZoneSpec]]` (ordered `TARGET_CLASSES`), `map_zones: dict[str, list[ZoneSpec]]` (ordered `MAP_LABELS`), `ignored_classes: list[str]`. `ZoneSpec` = the existing `auto_roi_discoverer.model.HsvBand` + `Rect` pair plus a `name: str` and `owning_class: str` field — reuse the dataclasses, do NOT redefine.
  - [x] Loader honours both `.yaml` and `.json` based on suffix (`yaml.safe_load` / `json.load`); empty class lists tolerated; unknown top-level keys (not in `TARGET_CLASSES` ∪ `MAP_LABELS` and not `_metadata`) → warn to stderr + record in `ignored_classes`; bad-shape zone dict (missing `hsv` key, missing `x/y/width/height`, etc.) → clean error to stderr (one-shot, includes the offending zone path) + exit 1.

- [x] **Task 3: Per-frame band-fire test (`zone_fires_on_frame`) + frame iterator (`iter_labeled_frames`) (AC: 6)**
  - [x] Reuse `band_inrange_ratio` from `tools.auto_roi_discoverer.validator` — import + wrap with the `>= min_ratio` check returning `(bool, float)`. Add a `# reuses tools.auto_roi_discoverer.validator.band_inrange_ratio — same hue-wrap cv2.inRange logic, no reinvention` comment in the wrapper to anchor the reuse explicitly.
  - [x] `iter_labeled_frames(labeled_root, version, *, limit_per_class)` — yields `(frame_path: str, folder: str, frame_bgr: np.ndarray)` tuples by scanning `<labeled_root>/<version>/<class>/*.png`; uses `cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)` (Windows non-ASCII path safety); skips unreadable files with a warning (don't crash the batch).
  - [x] `_resize_to_ref(frame_bgr, ref_height)` — aspect-preserving resize so `frame.shape[0] == ref_height`; `INTER_AREA` for downscale, `INTER_LINEAR` for upscale.

- [x] **Task 4: Classifier + per-frame evaluator (`evaluate_frame`) (AC: 4, 5)**
  - [x] `evaluate_frame(frame_bgr_at_ref, fragment) -> FrameResult`: applies every zone in every class group; returns per-zone fires (`dict[str, bool]` keyed by `(class, zone_name)`), the game-state score-vector + predicted class (per AC4 rules incl. tie-break + threshold-or-unknown), and (if the folder is in `MAP_LABELS`) the map-ID score-vector + predicted map (per AC5 rules).
  - [x] Folder → game-state ground-truth mapping is a tiny pure helper: `_folder_to_gs(folder, map_labels) -> str | None` returning `lobby/score/transition/in_match/None`.

- [x] **Task 5: Aggregator + report writers (`aggregate_metrics`, `write_report`, `write_summary`) (AC: 7, 8)**
  - [x] `aggregate_metrics(per_frame_results, fragment) -> ReportData` — fold the per-frame `FrameResult`s into per-zone TP/FP/FN/TN (using the AC7 owning-class rule), per-zone P/R/F1 (with `/0` guards), per-classifier confusion matrices (rows = ground-truth, columns = predicted incl. `"unknown"`), per-class P/R/F1 from the confusion matrices, top-line accuracies.
  - [x] `write_report(report_data, run_metadata, out_dir)` → `report.json` per the AC8 schema (`json.dump` with `indent=2`, `ensure_ascii=False`).
  - [x] `write_summary(report_data, run_metadata, out_dir)` → `summary.md`: run-metadata header, two classifier sections (accuracy + Markdown confusion table + per-class P/R/F1 table), worst-zones table (top 10 by F1), worst-confused class pairs (top 5).
  - [x] `write_frame_predictions(per_frame_results, out_dir)` (opt-in) → `frame_predictions.csv` with the AC8 columns.

- [x] **Task 6: TUI registration in `wardentooling.py` (AC: 9)**
  - [x] `flow_tool9()` (questionary `--zones`/`--labeled`/`--output`/`--limit`/`--save-frame-predictions` prompts, `.strip()`'d, blank = default; positive-int validation for `--limit` reusing Tool 7's `_is_pos_int` pattern; returns `(["tools/roi_detection_tester.py", *extra], None)`; `([], None)` on Ctrl-C).
  - [x] `_TOOL_MAP["roi_detection_tester"]`; `"Tool 9 — Test ROI Detection on Labeled Frames"` inserted into `choices_main` between Tool 8 and Dev Tools; the matching `menu_main` branch (`save_last_run("roi_detection_tester", …, args, None)` on `returncode == 0`); a `_reprompt_source` branch (re-runs `flow_tool9()`).
  - [x] Run `python wardentooling.py` and `python -c "import ast; ast.parse(open('wardentooling.py').read())"` to confirm no syntax/import-time regression.

- [x] **Task 7: Tests (AC: 10)**
  - [x] `apps/tooling/tests/test_roi_detection_tester.py` — loader / band-fire / frame-resize / `evaluate_frame` / `aggregate_metrics` / `main(...)` end-to-end smoke + CLI guards (per AC10). All `tmp_path`-based; no Tk; no real video; no ffmpeg.
  - [x] `cd apps/tooling && uv run pytest` full suite green (92 → 121 = 29 new); also run `pnpm --filter tooling test` once to confirm the workspace task picks up the new file automatically.

- [x] **Task 8: Manual smoke run (AC: 11)**
  - [x] `python tools/roi_detection_tester.py` (zero-arg → defaults; picked up `apps/tooling/output/auto_rois/v2.0/discovered_zones.yaml` + `apps/tooling/output/labeled/v2.0/`).
  - [x] Eyeballed `summary.md` — see Debug Log. Game-state accuracy = 0.000 (0/2748) — every frame predicted "unknown" as expected from the live yaml's empty game-state zone lists (`lobby: []` / `in_match: []` / `score: []` / `transition: []`). Map-ID accuracy = 0.967 (2289/2367). Top worst-confused pairs are mostly map→"unknown" (silva 9.1%, coliseum 16.4%, the_cliff 5.1%, helios 2.2%, artefact 1.4%); cross-map confusion is minimal.
  - [x] Real dataset used (no fallback needed). Report dropped at `apps/tooling/output/roi_detection_tests/v2.0/2026-05-13T232117/`.

- [x] **Task 9: Sibling doc `apps/tooling/tools/roi_detection_tester.md` (AC: 12)**
  - [x] Written to the AC12 spec (launch / classifiers + decision rules / output-file meanings / coordinate-frame contract / threshold semantics / anti-pattern + no-config-edit / end-to-end workflow / no-edit-to-README/architecture note); ≈ the length of `auto_roi_discoverer.md`. In the File List.

- [ ] **Task 10: PR + sprint-status flip (AC: 13, 14)** — _held; commit/push/PR-open of the deliverable pending the user's go-ahead (Story 9.6/9.7 pattern)._
  - [ ] Branch `tool-9-roi-detection-tester` off `main` (or off `tool-8-auto-roi-discoverer` if Tool 8 hasn't merged yet — dev confirms before pushing). Commit (deliverable + any `/bmad-code-review` patch pass), push, open PR `feat: Tool 9 — ROI detection tester (Story 9.8)` (commit subject lowercased for commitlint), link this story file + the Epic 9 charter + `apps/tooling/tools/auto_roi_discoverer.md`.
  - [ ] Flip sprint-status `9-8-roi-detection-tester-tool-9`: `ready-for-dev → in-progress` (work start) → `review` (dev + tests + smoke done) → `done` (post-merge follow-up). `last_updated` bumped each time.
  - [ ] Post-merge follow-up — separate tiny branch/PR: flip sprint-status `review → done`, bump `last_updated`, flip AC13/AC14 + this Task's PR sub-boxes + the `[ ]` ACs to `[x]`, Status → `done` (Two-PR pattern per `feedback_two_pr_docs_execution.md`).

### Review Findings

_Generated 2026-05-14 by `/bmad-code-review` (Blind Hunter + Edge Case Hunter + Acceptance Auditor; full diff = Tool 8 + Tool 9 reviewed together since both were uncommitted on the same working tree)._

**Acceptance Auditor verdict — Story 9.8: 0 AC violations, 0 PARTIAL, 2 DEFERRED-OK (AC13, AC14).** All 12 functional ACs + Tasks 1–9 pass; Task 10 (PR + flip) held per Two-PR pattern. Single-file shape preserved, `band_inrange_ratio` reused (not reinvented), `Rect`/`HsvBand` imported from Tool 8, Windows-safe frame reads, `/0` guards in place, fresh-timestamp output paths, "never writes `config/config.yaml`" + "no new deps" constraints held.

#### Decision-needed (resolved 2026-05-14 → converted to patch below)

- [x] [Review][Decision] `_resize_to_ref` only normalizes height — non-16:9 footage gets aspect-preserved width that may not match the zones' coordinate frame, silently clipping rects at zone evaluation. **Resolution (Stephane, 2026-05-14): option (b)** — record cell `frame_shape` in `discovered_zones._metadata` on Tool 8 export; Tool 9 compares first-loaded frame's post-resize shape against that and prints a stderr warning on mismatch. No hard fail (preserve experimental flexibility). [`apps/tooling/tools/roi_detection_tester.py:289`]
  - [x] [Review][Patch] **From decision resolution:** export `frame_shape` (or `coord_frame_shape: [h, w]`) into `discovered_zones._metadata` from Tool 8 [`apps/tooling/tools/auto_roi_discoverer/export.py:56` + `apps/tooling/tools/auto_roi_discoverer/export.py:_build_metadata`]; load it in `load_zones_fragment` and emit a stderr warning from Tool 9's main() when post-resize first-frame shape differs from the zones' coord-frame shape [`apps/tooling/tools/roi_detection_tester.py:229` + `apps/tooling/tools/roi_detection_tester.py:main`]

#### Patches (HIGH)

- [x] [Review][Patch] `_default_zones_path` lexicographic sort over `v*` dirs — `v10.0 < v2.0` once two-digit HUD versions exist. Paired with the Tool 8 `_choose_version` finding in story 9.7 [`apps/tooling/tools/roi_detection_tester.py:84`]

#### Patches (MEDIUM)

- [x] [Review][Patch] `evaluate_frame` wipes `map_scores = {}` for non-map folders — `FrameResult.map_scores` contract is broken for `lobby`/`score`/`transition` CSV rows; downstream debug introspection can't see which map zones fired on those frames [`apps/tooling/tools/roi_detection_tester.py:400`]
- [x] [Review][Patch] `_argmax_with_threshold` uses exact `==` float equality to detect ties on `fires/n_zones` scores — non-deterministic across NumPy/Python float environments; switch to `math.isclose` with rel_tol or compare integer `(fires, n_zones)` cross-products [`apps/tooling/tools/roi_detection_tester.py:375`]
- [x] [Review][Patch] `_argmax_with_threshold` with `--game-state-threshold 0.0` (within the legal `[0.0, 1.0]` range) returns a real class on all-zero frames instead of `"unknown"` — silently inflates one class's confusion counts. Special-case `max_score == 0 → "unknown"` regardless of threshold, OR change comparison to `>` [`apps/tooling/tools/roi_detection_tester.py:375`]
- [x] [Review][Patch] `iter_labeled_frames` swallows `OSError` from `os.listdir` indistinguishably from "directory empty" — caller sees "no readable PNG frames" even on permission/transient errors [`apps/tooling/tools/roi_detection_tester.py:301`]
- [x] [Review][Patch] ~~`load_zones_fragment` calls `data.get("_metadata")` before the `isinstance(data, Mapping)` check — crashes with `AttributeError` on a list-typed YAML instead of the clean `ValueError("top-level of '...' must be a mapping")` it documents~~ [`apps/tooling/tools/roi_detection_tester.py:229`] — **Dismissed on review (false alarm).** The current code DOES have `isinstance(data, dict)` at L242 before any `.get` call at L245, so the documented `ValueError` path is correctly reached for list/string YAMLs. Edge Case Hunter was reading the diff line numbers (4556 vs 4562) and inverted their order. No code change needed.

#### Patches (LOW)

- [x] [Review][Patch] `_resize_to_ref` doesn't guard against `h == 0` — `ZeroDivisionError` crashes the whole run on a corrupt frame instead of skip+warn [`apps/tooling/tools/roi_detection_tester.py:289`]
- [x] [Review][Patch] `_default_zones_path` swallows `OSError` from `os.listdir` but not subsequent `os.path.isdir`/`getmtime` failures — a single weird filesystem entry aborts default discovery [`apps/tooling/tools/roi_detection_tester.py:84`]

#### Deferred

_(see Story 9.7's deferred entry — HSV gray-pixel concern covers Tool 9's reused `band_inrange_ratio` path too.)_

#### Dismissed

- `aggregate_metrics` `setdefault` allowing future-extended GS classes outside `TARGET_CLASSES` — dead-code defensive only.
- Worst-confused pairs dict-iteration tie order — cosmetic.
- `_resize_to_ref` integer-rounding collapse to width=1 for pathological 1×N frames — contrived, never happens with real footage.

## Dev Notes

### Strategic context

Tool 9 is the **fourth link of the new-HUD tooling chain** and closes the validation loop Tool 8 deliberately left open: Tool 6 (`video_timeline_labeler.py`, Story 9.5) produces the HUD-version-partitioned labeled PNG dataset; Tool 7 (`overlay_stack_analyzer.py`, Story 9.6) builds the per-cell `stats.npz` mean/std aggregates; Tool 8 (`auto_roi_discoverer/`, Story 9.7) consumes those aggregates and emits `discovered_zones.{json,yaml}` — a *hand-merge fragment* of candidate ROI+HSV zones for both the game-state classifier (4 classes) and the per-map classifier (up to 14 classes). Tool 8's separability check is a **mean/std proxy** (see `auto_roi_discoverer/validator.py:18-20` and `auto_roi_discoverer.md`'s "What's a proxy" section) — fast enough to score during interactive review, but not the same thing as "does this fire correctly on actual frames". Tool 9 is the per-frame measurer: re-streams every labeled PNG, applies every discovered zone's HSV band per-frame, aggregates fires into TP/FP/FN/TN, and reports precision/recall/F1 per zone + per class + a confusion matrix per classifier. Its output is the **empirical accept/iterate signal**: which zones (and which classes overall) the user can trust, and which need a Tool 8 revisit (tweak HSV / pick a different rect / draw an exclusion) before the hand-merge into `config/config.yaml`. The hand-merge itself + the `map_config.json` v2 regen + the new game-state config section remain a **future re-fingerprinting story** — out of this story's scope; Tool 9 only ever *reads* `config/config.yaml`'s producers (it never even has to read `config/config.yaml` itself — its inputs are the Tool 8 fragment + the Tool 6 labeled dataset).

The two classifiers + the labeled-folder→ground-truth mapping. The `discovered_zones.yaml` carries zone groups by class: four game-state classes (`lobby`, `in_match`, `score`, `transition`) and N per-map classes (`MAP_LABELS` ∩ what's present in the dataset). Tool 9 evaluates both classifiers from a single pass over the labeled dataset. The labeled folder name (under `output/labeled/v<ver>/`) is the ground truth, mapped per AC4: `lobby/` → game-state `lobby`; `score/` → game-state `score`; `transition/` → game-state `transition`; any folder in `MAP_LABELS` (`artefact`, `atlantis`, …, `the_rock`) → game-state `in_match` AND map-ID = the folder name itself. So a frame in `output/labeled/v2.0/artefact/003_00h00m08s.png` contributes to **two** classifier evaluations: it's a positive for game-state `in_match` + an evaluation example for the map-ID classifier (positive for `artefact`, negative for all other maps).

### Key code patterns to reuse (NOT reinvent)

| Need | Source | Notes |
|---|---|---|
| Hue-wrap-aware `cv2.inRange` + `min_ratio` band-fire on a frame region | [`auto_roi_discoverer/validator.py:82 band_inrange_ratio`](apps/tooling/tools/auto_roi_discoverer/validator.py#L82) | Reuse directly — same hue-wrap `bitwise_or` mask logic Tool 8's validator already uses on mean images. Tool 9 calls it on each labeled frame (already resized to ref height) and wraps the returned ratio in a `>= min_ratio` bool. |
| Zone-dict shape + dataclasses | [`auto_roi_discoverer/model.py:Rect / HsvBand / DiscoveredZone`](apps/tooling/tools/auto_roi_discoverer/model.py) | Reuse `Rect` + `HsvBand` (they already cover everything Tool 9 needs); the loader builds `ZoneSpec`s on top — do NOT redefine `Rect` / `HsvBand`. |
| `MAP_LABELS` (the 14 canonical maps) | [`frame_labeler.py:23 MAP_LABELS`](apps/tooling/tools/frame_labeler.py#L23) | Reuse — drives the folder→game-state mapping (`in_match` vs `lobby/score/transition/None`) AND the per-map classifier's class set + tie-break order. |
| `MAP_LABELS` + `_NON_POOL_GAME_STATE` ordering | [`auto_roi_discoverer/model.py:19 TARGET_CLASSES`](apps/tooling/tools/auto_roi_discoverer/model.py#L19) | Reuse the `TARGET_CLASSES` tuple for game-state ordering (`lobby/in_match/score/transition`) — same order Tool 8's export uses, so confusion-matrix rows/columns + per-class table order match Tool 8's output by default. |
| `_default_input_dir()` for the labeled root | [`overlay_stack_analyzer.py:46 _default_input_dir`](apps/tooling/tools/overlay_stack_analyzer.py#L46) | Reuse — Tool 9's `--labeled` default == Tool 7's `--input` default (`apps/tooling/output/labeled`). Same `__file__`-relative math; importing keeps them lockstep. |
| `_default_output_dir()` resolution math | [`overlay_stack_analyzer.py:52 _default_output_dir`](apps/tooling/tools/overlay_stack_analyzer.py#L52) | Replicate (one level up from `tools/` → `apps/tooling/output/roi_detection_tests`) — same convention Tools 6/7/8 settled on (commit `372383f`). |
| Default-zones-path resolution (Tool 9 input == Tool 8 export root) | [`auto_roi_discoverer/loader.py:58 default_export_root`](apps/tooling/tools/auto_roi_discoverer/loader.py#L58) | Replicate — Tool 9's `--zones` default scans `apps/tooling/output/auto_rois/v*/discovered_zones.yaml` (newest wins). |
| Windows non-ASCII-path-safe frame **read** | `cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)` | Same pattern Tools 6/7/8 use for `cv2.imread`-free image loading. |
| Single-file headless batch tool layout (argparse → pure helpers → `main(argv) -> int`) | [`overlay_stack_analyzer.py`](apps/tooling/tools/overlay_stack_analyzer.py) | Tool 7's shape — Tool 9 mirrors it. |
| Sibling-doc convention (don't bloat README / architecture doc) | [`auto_roi_discoverer.md`](apps/tooling/tools/auto_roi_discoverer.md), [`overlay_stack_analyzer.md`](apps/tooling/tools/overlay_stack_analyzer.md) | Add a sibling `tools/roi_detection_tester.md` (next to the `.py`, like Tools 6/7's `.md`s). Do not touch `apps/tooling/README.md` or `docs/architecture-tooling.md`. |
| TUI flow / `_TOOL_MAP` / `menu_main` branch / `_reprompt_source` (directory-driven, file-invoked) | [`wardentooling.py:383 flow_tool7`](apps/tooling/wardentooling.py#L383), [`wardentooling.py:590 _TOOL_MAP`](apps/tooling/wardentooling.py#L590), [`wardentooling.py:636-642 _reprompt_source overlay/auto_roi`](apps/tooling/wardentooling.py#L636), [`wardentooling.py:801 Tool 7 menu_main branch`](apps/tooling/wardentooling.py#L801) | Mirror Tool 7's directory-driven flow + file invocation (`["tools/roi_detection_tester.py", ...]`, NOT `-m` — Tool 9 is a single file, not a package). |
| pytest layout / `conftest.py` already lifts `apps/tooling/` onto `sys.path` | [`apps/tooling/tests/conftest.py`](apps/tooling/tests/conftest.py) + [`apps/tooling/tests/test_auto_roi_discoverer.py`](apps/tooling/tests/test_auto_roi_discoverer.py) | No new conftest. Pure logic top-level → testable without GUI; synthetic `discovered_zones.yaml` + tiny labeled trees on `tmp_path` for the smoke. |

### Anti-patterns / disasters to avoid

- **DO NOT auto-edit `config/config.yaml`.** Tool 9 *reads* the Tool 8 fragment (`discovered_zones.yaml`) and *writes a report*. It never reads or writes `config/config.yaml`. The hand-merge step is the human's, in the future re-fingerprinting story (same posture as Tool 8).
- **DO NOT reinvent the band-fire test.** The hue-wrap `cv2.inRange` + `min_ratio` logic already exists in `auto_roi_discoverer/validator.py:band_inrange_ratio` (line 82) — import and wrap. Re-implementing it here would silently diverge from Tool 8's own scoring math (and from `minimap_zone_selector/zone_model.py:zone_fires`'s reference implementation).
- **DO NOT reinvent `Rect` / `HsvBand` dataclasses.** Reuse the ones already in `auto_roi_discoverer/model.py`. Defining parallel shapes here would force test fixtures to round-trip between two near-identical types and invite drift.
- **DO NOT use `cv2.imread`/`cv2.imwrite` with bare paths.** Windows non-ASCII path hazard (the Tool 6/7 reviews caught this — see the `imdecode`+`np.fromfile` pattern). Tool 9 reads many thousands of PNGs; one Cyrillic/CJK path on the dev box would crash the entire smoke.
- **DO NOT silently divide by zero.** Per-zone P/R/F1, per-class accuracy, every aggregate score must guard `denom == 0 → 0.0` and document the convention in the `.md`. A zone with zero positives in the dataset has `recall = 0/0` mathematically; Tool 9 reports it as `0.0` with a note.
- **DO NOT load all frames into memory.** Stream them (`iter_labeled_frames` yields one at a time; no list-of-frames building). The 2,748-frame dataset at 1080p × 3 channels is ~18 GB raw — already enough to OOM modest dev boxes if `np.stack`'d. (Same hazard Tool 7's review flagged for the stacking pass.)
- **DO NOT special-case `transition`.** It's a regular game-state class in the discovered fragment; Tool 9 evaluates it the same way as `lobby`/`in_match`/`score`. (Same posture as Tool 8.)
- **DO NOT overwrite previous reports.** Each run drops a fresh `<timestamp>/` subdir under `<output>/v<ver>/`. The user iterates Tool 8 → Tool 9 repeatedly during the hand-merge prep; comparing runs is the point.
- **DO NOT modify `docs/architecture-tooling.md` or `apps/tooling/README.md`** — both predate Tools 6/7/8/9 (known doc-debt; deferred docs-refresh story).
- **DO NOT add new third-party dependencies.** `numpy` / `opencv-python` / `pyyaml` / stdlib `csv`/`json`/`argparse` are sufficient.

### File structure

```
apps/tooling/
  tools/
    roi_detection_tester.py            # NEW (this story — Tool 9 single-file module)
    roi_detection_tester.md            # NEW (this story — sibling usage/interpretation doc)
    auto_roi_discoverer/               # UNCHANGED (Tool 8 — reused: validator.band_inrange_ratio, model.Rect/HsvBand)
    overlay_stack_analyzer.py          # UNCHANGED (Tool 7 — reused: _default_input_dir, _default_output_dir math)
    frame_labeler.py                   # UNCHANGED (Tool 2 — reused: MAP_LABELS)
  tests/
    test_roi_detection_tester.py       # NEW (loader / band-fire / classifier / aggregator / main() smoke + CLI guards)
    conftest.py                        # UNCHANGED (added in Story 9.5; lifts apps/tooling/ onto sys.path)
  wardentooling.py                     # UPDATED (TUI: flow_tool9 + _TOOL_MAP + choices_main + menu_main branch + _reprompt_source branch)

# Input — produced by Tool 8 (not committed; under apps/tooling/output/ gitignore):
output/auto_rois/v<ver>/discovered_zones.yaml

# Input — produced by Tool 6 (not committed; under apps/tooling/output/ gitignore):
output/labeled/v<ver>/<class>/*.png

# Output — produced by Tool 9 (not committed; apps/tooling/output/ already gitignored — no .gitignore change):
output/roi_detection_tests/
  v<ver>/
    <YYYY-MM-DDTHHMMSS>/
      report.json                      # machine-readable: per-zone TP/FP/FN/TN/P/R/F1, per-class confusion + P/R/F1, run metadata
      summary.md                       # human-readable: accuracies + confusion tables + worst zones + worst-confused pairs
      frame_predictions.csv            # OPT-IN via --save-frame-predictions: one row per evaluated frame
```

### Library / framework requirements

- **Python ≥ 3.11** (pyproject baseline).
- **OpenCV** (`opencv-python ≥ 4.8, < 5`) — already a dep. `imdecode`, `cvtColor`, `inRange`, `bitwise_or`, `resize`.
- **NumPy** (`numpy ≥ 1.24, < 2`) — already a dep. The per-frame BGR/HSV math, fire-count aggregation.
- **PyYAML** (`pyyaml ≥ 6.0, < 7`) — already a dep. Reading `discovered_zones.yaml`.
- **stdlib** — `argparse`, `json`, `csv`, `datetime`, `dataclasses`, `pathlib`, `os`, `sys`. No `tkinter` (headless).
- **No new third-party dependencies.**

### Testing standards

- `pytest` 8.0+ already in `apps/tooling/pyproject.toml` `[project.optional-dependencies] dev`; run via `uv run pytest`. `apps/tooling/tests/conftest.py` already prepends `apps/tooling/` to `sys.path` — no new conftest.
- **All pure logic** is unit-tested with `tmp_path` synthetic labeled trees + synthetic `discovered_zones.yaml` — no real video, no ffmpeg, no Tk. The single end-to-end smoke (`main([...])` on a 2-class fixture) exercises the full pipeline including report writes.
- Run commands: `cd apps/tooling && uv run pytest tests/test_roi_detection_tester.py -v`; full suite `cd apps/tooling && uv run pytest` (must stay green — currently 92 post Story 9.7). Pre-commit/CI: `pnpm --filter tooling test` picks up new `test_*.py` files automatically.

### Sprint-fit + dependencies

- **Track C** (tooling chain). Parallel with Tracks A/B; independent of the AR-SPIKE outcome.
- **Upstream:** Story 9.7 (Tool 8 — `auto_roi_discoverer`), currently `review` — Tool 9 imports `tools.auto_roi_discoverer.validator.band_inrange_ratio` and `tools.auto_roi_discoverer.model.Rect / HsvBand`. The dev confirms Tool 8's branch status before starting: if `9-7-auto-roi-discoverer-tool-8` is still `review` (PR open, not yet merged), branch `tool-9-roi-detection-tester` off `tool-8-auto-roi-discoverer` and rebase against `main` once Tool 8 lands; if already merged, branch off `main` directly. Tool 6 (Story 9.5) is the dataset producer three links back (only the directory contract `output/labeled/v<ver>/<class>/*.png` matters; not blocked on its sprint-status state). Tool 7 (Story 9.6) is two links back — only its `_default_input_dir` resolution is reused.
- Stories 9.1–9.4 neither block nor are blocked by this.
- **Downstream:** the future **game-detector re-fingerprinting story** (TBD) consumes Tool 8's fragment + Tool 9's accuracy report to drive the hand-merge into `config/config.yaml` + the `map_config.json` v2 regen. **Out of this story's scope.** Tool 9's deliverable is the empirical accuracy signal; the human decides what to merge based on it.

### Project Structure Notes

- Naming: `roi_detection_tester` follows the snake_case + descriptive-noun convention (`frame_labeler`, `map_config_generator`, `hash_validator`, `warden_analyzer`, `overlay_stack_analyzer`, `video_timeline_labeler`, `auto_roi_discoverer`). Packaged as a single file (like Tool 7) — no GUI; pure-logic helpers + a thin `main(argv)`; no need for the package layout Tool 8 used (which existed because of GUI + engine + validator + export breadth).
- Tool 9 sits next to Tools 6/7/8 in `tools/`; all four are additive to the legacy Tools 1–5 pipeline. It's "Tool 9" everywhere user-facing (TUI label `"Tool 9 — Test ROI Detection on Labeled Frames"`, `save_last_run` key `"roi_detection_tester"`, module `tools.roi_detection_tester`), consistent with Tools 6/7/8's registrations. Like Tools 4/7 (headless tools), it lives in the **main** TUI menu after Tool 8, not in the Dev submenu.
- Output root `output/roi_detection_tests/` is a new sibling of `output/labeled/` (Tool 6), `output/overlay_stacks/` (Tool 7), `output/auto_rois/` (Tool 8), under the existing `apps/tooling/output/` gitignore entry — **no `.gitignore` change**.
- `_default_*` resolution: Tool 9 reuses Tool 7's `_default_input_dir` for the labeled root, replicates Tool 7's `__file__`-relative `apps/tooling/output/...` math for the report root, and replicates Tool 8's `default_export_root` math for the zones-fragment default (with the "newest `v*/`" scan added).
- The Epic 9 charter in `_bmad-output/epics-and-stories.md` enumerates Stories 9.1–9.4 only; 9.5/9.6/9.7 were added post-planning via the new-HUD initiative, and 9.8 is the fourth such addition (recorded in `_bmad-output/sprint-status.yaml`'s header and in `project_warden_new_hud_labeler.md`). This story does **not** retro-edit the charter — known doc-debt for a future docs-refresh, same as 9.5/9.6/9.7.

### References

- [Source: _bmad-output/epics-and-stories.md#Epic-9](_bmad-output/epics-and-stories.md#L2614) — Epic 9 charter (Tooling — V1 Pipeline Hardening); 9.5/9.6/9.7/9.8 not yet enumerated there (known doc-debt)
- [Source: _bmad-output/sprint-status.yaml](_bmad-output/sprint-status.yaml#L2) — `last_updated` history; "new-HUD work" prerequisite; Tools 6/7/8 provenance
- [Source: _bmad-output/sprint-plan.md#Track-C](_bmad-output/sprint-plan.md#L111) — Track C tooling chain
- [Source: _bmad-output/implementation-artifacts/9-7-auto-roi-discoverer-tool-8.md](_bmad-output/implementation-artifacts/9-7-auto-roi-discoverer-tool-8.md) — Tool 8 story (this tool's input producer); see its Dev Notes + the AC6 / AC15 / Dev-Notes-anti-patterns sections for the "per-frame validation is out of scope, future re-fingerprinting story's job" framing
- [Source: _bmad-output/implementation-artifacts/9-6-overlay-stack-analyzer-tool-7.md](_bmad-output/implementation-artifacts/9-6-overlay-stack-analyzer-tool-7.md) — Tool 7 story (the streaming/Welford + Windows-path-safety + directory-driven-TUI conventions Tool 9 reuses)
- [Source: _bmad-output/implementation-artifacts/9-5-video-timeline-labeler-tool-6.md](_bmad-output/implementation-artifacts/9-5-video-timeline-labeler-tool-6.md) — Tool 6 story (the labeled-PNG dataset producer; the folder-name=ground-truth contract Tool 9 reads)
- [Source: apps/tooling/tools/auto_roi_discoverer.md](apps/tooling/tools/auto_roi_discoverer.md) — Tool 8 sibling doc; see the "What's a proxy" section (the explicit deferral Tool 9 closes) + the `discovered_zones.{json,yaml}` shape (Tool 9's input format)
- [Source: apps/tooling/tools/auto_roi_discoverer/validator.py:82-105](apps/tooling/tools/auto_roi_discoverer/validator.py#L82) — `band_inrange_ratio` (the hue-wrap `cv2.inRange` band-fire test; reused in Tool 9's `zone_fires_on_frame` wrapper)
- [Source: apps/tooling/tools/auto_roi_discoverer/validator.py:18-20](apps/tooling/tools/auto_roi_discoverer/validator.py#L18) — "Exact per-frame validation … is the future re-fingerprinting story's job" (the explicit deferral Tool 9 honours by being a separate tool, not a Tool 8 amendment)
- [Source: apps/tooling/tools/auto_roi_discoverer/model.py:55-118](apps/tooling/tools/auto_roi_discoverer/model.py#L55) — `Rect`, `HsvBand`, `DiscoveredZone` (reused; Tool 9's `ZoneSpec` composes `Rect` + `HsvBand` + a `name`/`owning_class` pair)
- [Source: apps/tooling/tools/auto_roi_discoverer/model.py:19](apps/tooling/tools/auto_roi_discoverer/model.py#L19) — `TARGET_CLASSES` tuple (`lobby/in_match/score/transition` ordering used for game-state confusion-matrix rows/columns + tie-break)
- [Source: apps/tooling/tools/auto_roi_discoverer/loader.py:58-66](apps/tooling/tools/auto_roi_discoverer/loader.py#L58) — `default_export_root` (`apps/tooling/output/auto_rois`); Tool 9's `--zones` default scans below this
- [Source: apps/tooling/tools/overlay_stack_analyzer.py:46-58](apps/tooling/tools/overlay_stack_analyzer.py#L46) — `_default_input_dir` (`apps/tooling/output/labeled`) + `_default_output_dir` math (`apps/tooling/output/overlay_stacks`); Tool 9 reuses the labeled-dir resolver + replicates the output-dir math for `apps/tooling/output/roi_detection_tests`
- [Source: apps/tooling/tools/frame_labeler.py:23-38](apps/tooling/tools/frame_labeler.py#L23) — `MAP_LABELS` (the 14 canonical maps; drives the folder→game-state mapping + the map-ID class set)
- [Source: apps/tooling/tools/minimap_zone_selector/zone_model.py:41-96](apps/tooling/tools/minimap_zone_selector/zone_model.py#L41) — `zone_fires` (the reference implementation for the band-fire test in the legacy minimap pipeline; Tool 9 doesn't import this one because `band_inrange_ratio` is a closer fit, but it's documented here for the dev to cross-check the math if the test fails)
- [Source: apps/tooling/wardentooling.py:383-449](apps/tooling/wardentooling.py#L383) — `flow_tool7` shape (directory-driven, no video; the template for `flow_tool9`); [wardentooling.py:457-492](apps/tooling/wardentooling.py#L457) `flow_tool8` (also directory-driven; another shape reference); [wardentooling.py:590](apps/tooling/wardentooling.py#L590) `_TOOL_MAP`; [wardentooling.py:636-642](apps/tooling/wardentooling.py#L636) `_reprompt_source` directory-driven branch (where Tool 9's branch lands); [wardentooling.py:801-816](apps/tooling/wardentooling.py#L801) Tool 7 `menu_main` branch (template for Tool 9's branch)
- [Source: apps/tooling/output/auto_rois/v2.0/discovered_zones.yaml](apps/tooling/output/auto_rois/v2.0/discovered_zones.yaml) — the live Tool 8 output Tool 9 will consume; note `lobby: []` / `in_match: []` / `score: []` / `transition: []` (no game-state zones yet — game-state classifier will produce mostly `"unknown"` predictions on the live data; expected, not a bug)
- [Source: apps/tooling/output/labeled/v2.0/](apps/tooling/output/labeled/v2.0/) — the live Tool 6 labeled dataset (16 folders × ≈ 2,748 PNGs; `bastion` absent; `helios`, `silva`, etc. all present)
- [Source: apps/tooling/tests/conftest.py](apps/tooling/tests/conftest.py) — existing `sys.path` shim (no new conftest)
- [Source: apps/tooling/tests/test_auto_roi_discoverer.py](apps/tooling/tests/test_auto_roi_discoverer.py) — synthetic-`stats.npz` / synthetic-fragment fixture patterns to mirror for Tool 9's synthetic-labeled-tree + synthetic-yaml smoke
- [Source: docs/architecture-tooling.md](docs/architecture-tooling.md) — tooling pipeline architecture (predates Tools 6/7/8/9; do not edit)
- Memory: `project_warden_new_hud_labeler.md` — the new-HUD initiative; Tool 6/7/8/9 plan; the **locked decisions** for Tool 9 (per-frame validation; headless batch; two classifiers; output under `apps/tooling/output/roi_detection_tests/`) — this story is the authoritative spec from here
- Memory: `feedback_ac_checkbox_tighten.md` — AC checkbox convention for post-merge items
- Memory: `feedback_two_pr_docs_execution.md` — Two-PR pattern for sprint-status `review → done` flips

## Dev Agent Record

### Agent Model Used

Claude Opus 4.7 (1M context) — Amelia (bmad-dev-story).

### Debug Log References

- Initial pytest run (29 new tests) surfaced two issues: (a) `main()` was swallowing `SystemExit` from argparse — fixed by removing the `try/except SystemExit` wrapper so `argparse.error` propagates naturally (tests use `pytest.raises(SystemExit)` per the standard argparse-CLI test pattern); (b) the AC10 smoke-test fixture asserted 100% game-state accuracy with only `lobby` + `artefact` zones — the artefact frames have GT `in_match`, so an `in_match` zone matching red was added to the fixture for the assertion to make mathematical sense. All 29 tests then passed.
- Real-dataset manual smoke (Task 8, AC11): `apps/tooling/output/roi_detection_tests/v2.0/2026-05-13T232117/`. Game-state accuracy = 0.000 (0/2748) — all 2,748 frames predicted "unknown" because the live `discovered_zones.yaml` has all four game-state zone lists empty (`lobby: []` / `in_match: []` / `score: []` / `transition: []`). Map-ID accuracy = 0.967 (2289/2367). Worst-confused map-ID pairs: silva→unknown (15, 9.1%), coliseum→unknown (10, 16.4%), the_cliff→unknown (8, 5.1%), helios→unknown (7, 2.2%), artefact→unknown (6, 1.4%). Cross-map confusion is rare (1 artefact→atlantis, 5 artefact→lunar_outpost, 1 artefact→coliseum, 1 engine→horizon, 4 polaris→engine).
- Worst-performing zones (top by F1, all map-class) are uniformly very-loose-band exclusion-style zones firing on lots of off-map frames — e.g. `outlaw_z119` (P=0.121, R=0.823, F1=0.212), `coliseum_z36` (P=0.123, R=0.820, F1=0.213), `engine_z49` (P=0.142, R=0.814, F1=0.241). Diagnostic info for the user during the next Tool 8 hand-merge iteration — Tool 9's intended use.
- Full apps/tooling pytest suite: 92 → 121 green (29 new). `pnpm --filter tooling test` confirmed the workspace task picks up the new file automatically.

### Completion Notes List

- AC1-AC12 delivered as specced. AC13/AC14 held `[ ]` per the AC-checkbox-tighten convention (post-merge admin: the `review → done` sprint-status flip ships in the tiny follow-up commit/PR per the Two-PR pattern; Task 10's `git commit`/`push`/PR-open of the deliverable on branch `tool-9-roi-detection-tester` is the natural handoff but is left for the user's go-ahead — same as Stories 9.6/9.7).
- Single-file shape `apps/tooling/tools/roi_detection_tester.py` mirrors Tool 7's layout (pure helpers + thin `main(argv) -> int`); no GUI; no Tk import; no new third-party deps. Total ~600 LOC including the report writers.
- Reuses (per Dev Notes "Key code patterns to reuse"): `auto_roi_discoverer.validator.band_inrange_ratio` (hue-wrap `cv2.inRange`, no reinvention), `auto_roi_discoverer.model.Rect` / `HsvBand` / `TARGET_CLASSES`, `frame_labeler.MAP_LABELS`, `overlay_stack_analyzer._default_input_dir`. The `_resize_to_ref` and `_default_zones_path` helpers are new (single-purpose; the resize math is the same INTER_AREA/INTER_LINEAR pattern Tool 7 uses internally).
- TUI registration follows the directory-driven Tool 7/Tool 8 precedent: `flow_tool9` collects `--zones`/`--labeled`/`--output`/`--limit`/`--save-frame-predictions` via questionary prompts; entry added to `_TOOL_MAP` + `choices_main` between Tool 8 and Dev Tools; matching `menu_main` branch + `_reprompt_source` branch.
- Tool 9 never writes `config/config.yaml` — confirmed by code inspection (no `config/config.yaml` reference anywhere in `roi_detection_tester.py`). The hand-merge into config + `map_config.json` v2 regen remain the future re-fingerprinting story's job.
- Branch confirmation needed before push: Tool 8's PR (`tool-8-auto-roi-discoverer`) is still in `review`. Per AC14, Tool 9 branches off `tool-8-auto-roi-discoverer` and rebases against `main` after Tool 8 lands — the dev confirms with the user before pushing.

### File List

**Added**

- `apps/tooling/tools/roi_detection_tester.py` — Tool 9 single-file module (loader + band-fire test + frame iterator + classifier + aggregator + report writers + argparse `main`).
- `apps/tooling/tools/roi_detection_tester.md` — sibling usage/interpretation doc.
- `apps/tooling/tests/test_roi_detection_tester.py` — 29 pure-logic tests (`tmp_path`-based; no Tk, no real video, no ffmpeg).

**Modified**

- `apps/tooling/wardentooling.py` — `flow_tool9` + `_TOOL_MAP["roi_detection_tester"]` + `choices_main` entry + `menu_main` branch + `_reprompt_source` branch (Tool 9 — directory-driven, file-invoked).
- `_bmad-output/implementation-artifacts/9-8-roi-detection-tester-tool-9.md` — Status → review; AC1-AC12 + Task 1-9 + their subtasks → `[x]`; Dev Agent Record populated; File List populated; Change Log entry added.
- `_bmad-output/sprint-status.yaml` — `9-8-roi-detection-tester-tool-9: ready-for-dev → in-progress → review`; `last_updated` bumped.

**Not modified (per anti-patterns)**

- `apps/tooling/README.md` — sibling-doc convention; expansion would compound known doc-debt.
- `docs/architecture-tooling.md` — predates Tools 6/7/8/9; a dedicated docs-refresh story will catch them all up.
- `config/config.yaml` — Tool 9 only reads the Tool 8 fragment + writes a report; never touches `config/config.yaml` (the hand-merge is the human's, in the future re-fingerprinting story).
- `.gitignore` — `apps/tooling/output/` is already gitignored; the new `output/roi_detection_tests/` sibling sits under it. No change needed.

### Change Log

| Date       | Author                  | Summary |
|------------|-------------------------|---------|
| 2026-05-13 | Amelia (Opus 4.7 / dev) | Tool 9 — Per-frame ROI Detection Tester delivered. New `apps/tooling/tools/roi_detection_tester.py` (headless batch, single file like Tool 7) + sibling `.md` doc + 29 pytest tests + TUI registration in `wardentooling.py`. Reuses `auto_roi_discoverer.validator.band_inrange_ratio` (no reinvention), `Rect`/`HsvBand`/`TARGET_CLASSES`, `frame_labeler.MAP_LABELS`, Tool 7's `_default_input_dir`. Game-state classifier (4-way, argmax + `--game-state-threshold` else "unknown"; tie-break by zone-count then `TARGET_CLASSES` order) + map-ID classifier (N-way, only on `MAP_LABELS` folders) evaluated in one pass. Per-zone TP/FP/FN/TN + per-classifier confusion matrices + per-class P/R/F1 (with `/0` guards) → `report.json` + `summary.md` + opt-in `frame_predictions.csv` under `apps/tooling/output/roi_detection_tests/v<ver>/<timestamp>/`. Manual smoke against the real 2,748-frame v2.0 dataset: game-state 0.000 (expected — live yaml has empty game-state zone lists), map-ID 0.967 — exactly the empirical accept/iterate signal Tool 9 was built for. Full apps/tooling pytest suite 92 → 121 green. AC1-AC12 + Tasks 1-9 closed; AC13/AC14 + Task 10's PR sub-boxes held `[ ]` (post-merge admin via Two-PR pattern). Tool 9 still NEVER writes `config/config.yaml`. |
| 2026-05-13 | create-story (Opus 4.7 1M) | Story 9.8 drafted — Tool 9 (Per-frame ROI Detection Tester): headless batch tool that consumes Tool 8's `discovered_zones.yaml` + Tool 6's labeled PNG dataset, replays each frame through every zone's HSV band, and reports per-zone (TP/FP/FN/TN/P/R/F1) + per-class confusion-matrix accuracy for both the game-state classifier (4 classes) and the map-ID classifier (N classes). Closes the per-frame validation gap Tool 8 explicitly deferred (`auto_roi_discoverer/validator.py:18-20` + `auto_roi_discoverer.md`'s "What's a proxy" section). Single-file shape (`tools/roi_detection_tester.py`) like Tool 7 — no GUI; pure helpers + a thin `main(argv) -> int`. Reuses `auto_roi_discoverer.validator.band_inrange_ratio` (the hue-wrap `cv2.inRange` test) + `auto_roi_discoverer.model.Rect/HsvBand` + `frame_labeler.MAP_LABELS` + `overlay_stack_analyzer._default_input_dir`; no new dependencies (`numpy`/`opencv-python`/`pyyaml`/stdlib present). Output `apps/tooling/output/roi_detection_tests/v<ver>/<timestamp>/{report.json, summary.md, [frame_predictions.csv]}`, under existing `apps/tooling/output/` gitignore — **no `.gitignore` change**. Tool 9 still never writes `config/config.yaml`; the hand-merge into config + `map_config.json` v2 regen remain a future re-fingerprinting story. AC11/AC12 flip on dev completion; AC13/AC14 + Task 10's PR sub-boxes held `[ ]` per the AC-checkbox-tighten convention (post-merge admin: `review → done` flip via the Two-PR follow-up). Single-PR delivery (`feat: Tool 9 — ROI detection tester (Story 9.8)`, branch `tool-9-roi-detection-tester` off `main` or off `tool-8-auto-roi-discoverer` if Tool 8 hasn't merged yet) + a tiny post-merge follow-up for the `review → done` flip (Two-PR pattern). 92/92 pytest green at story-creation time. Added the `9-8-roi-detection-tester-tool-9` entry to `_bmad-output/sprint-status.yaml` under `epic-9` (already `in-progress` — no epic flip) and flipped it `→ ready-for-dev`. Not in the Epic 9 charter (9.1–9.4 only) — known doc-debt, same as 9.5/9.6/9.7. |
