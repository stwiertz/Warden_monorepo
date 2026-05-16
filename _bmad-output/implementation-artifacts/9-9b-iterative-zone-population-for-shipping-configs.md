# Story 9.9b: Iterative Zone Population for Shipping Configs

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As **Stephane** (post-V1, holding finalized labeled HUD-version datasets and shipped detection tooling),
I want **the empirical work of producing one populated `map_config.<hud_version>.json` per shipping HUD version — by iteratively running `zone_picker` (Story 9.12), `map_config_emitter` (Story 9.9c), `video_test` (Story 9.13), and the refit `roi_detection_tester` (Story 9.14) against the labeled datasets until per-class accuracy floors are met — captured as a tracked, gate-flippable story with documented accuracy data**,
so that **Story 1.13 (Hybrid `map_config.json` Delivery) and the eventual mobile consumer rewrite have a real, validated, version-controlled detection config to bundle, the `REL-006` ≥95% map-identification floor has empirical numbers behind it (per-HUD, per-classifier), and the legacy v1 pHash detection that ships in V1 — which won't fire on HUD 2.0 footage — is replaced by a per-HUD ROI+HSV config that actually works.**

**Strategic context.** 9.9b is the **operations / data-production** sibling of 9.9c. 9.9c shipped the schema + the fragment-driven emitter; 9.12 will ship the picker that writes fragments; 9.13 will ship the end-to-end video pipeline tester; 9.14 will refit Tool 9 to score against the unified schema. 9.9b is the **manual measurement loop** that turns those tools into a real shipping config: pick zones, emit, measure, adjust, repeat — per HUD version, until the accuracy targets hold. No new code. The deliverable is **empirical**: a committed `map_config.<hud_version>.json` plus the source-of-truth zone fragments plus a documented per-classifier floor table appended to this story's Completion Notes. The full split rationale lives in [`_bmad-output/sprint-change-proposal-2026-05-15.md`](../sprint-change-proposal-2026-05-15.md) §4.

**Why "iterative" and "multi-sprint."** Zone tuning is non-trivial: ROI + HSV bands that look discriminative on overlay stacks (Tool 8 / 9.12 helper) frequently mis-fire on edge frames the labeler caught (lighting changes, animation frames, partial occlusion). The realistic cycle per HUD version is **3–5 measurement passes** of zone-picker → emit → Tool 9 refit per-class scores → inspect worst-confused pairs → adjust the offending zones → re-emit. Each pass is ~hours of human work, not minutes. The story sits in `ready-for-dev` until 9.12/9.13/9.14 land, then runs in chunks aligned with sprint cadence. Set expectations on completion before dev-story kickoff: 1–2 weeks of focused work per HUD version, more if the data surfaces a class that won't converge.

**HUD-version scope.** **v2.0 is the only HUD version with labeled data today** — `apps/tooling/output/labeled/v2.0/` (~2,748 frames across 16 classes per the Story 9.8 dev-story log on `sprint-status.yaml:188`). v1.0 has no labeled data and no allocated labeling effort. Default scope for 9.9b: **populate `map_config.v2.json` only**. v1.0 stays on the legacy v1 pHash detection that ships in V1 (the bundled `apps/mobile/assets/map_config.json` doesn't exist yet; Story 1.13 owns its creation and will decide whether to also emit a v1 config from any future labeling). If v1.0 labeling appears, 9.9b's iterative loop applies identically — just append a `v1/` zones directory.

**V1 posture.** **Out-of-V1-scope** at the deliverable level. V1 ships with no `apps/mobile/assets/map_config.json` (the asset bundle path is empty; Story 1.13 stays `backlog`). The mobile pipeline runs with `Object.entries(config.maps)` against the handwritten `DetectionConfig` type from `detectionConfig.ts` (Firestore-driven, legacy pHash). HUD 2.0 footage produces `unknown` map labels — accepted regression because the post-V1 work (1.13 + the consumer rewrite + 9.9b's outputs) is the unified fix. **V1-safe at the code level:** 9.9b touches no Python, no TypeScript, no schemas. The only files modified are the zone fragments (data) + the emitted per-HUD config (data) + this story file.

**Type:** Operations / data-production story. Track C (tooling chain). No spike-or-split flag. **Multi-sprint** — sized at "weeks per HUD version" rather than the standard "fits-in-one-sprint." Dev-story kickoff is held until **all four hard dependencies have landed on `main`** (9.9c, 9.11, 9.12, 9.14; 9.13 strongly preferred but not strictly blocking for the in-pixel measurement loop — see Sprint-fit). Single-PR delivery for each completed HUD version's data set + a tiny post-merge follow-up commit/PR for the sprint-status `review → done` flip (Two-PR pattern, [[feedback_two_pr_docs_execution]]).

## Acceptance Criteria

> **AC checkbox convention:** items whose endpoint depends on **post-merge actions** (sprint-status `review → done` flip, PR merge) or on data not yet collected (per-class accuracy floors only knowable after measurement) are held `[ ]` per [[feedback_ac_checkbox_tighten]]. All other items flip to `[x]` on dev-agent completion.
>
> **Scope-conditioning ACs:** ACs that describe per-HUD-version deliverables (AC4–AC9) apply once per HUD version in scope. Default scope is `v2` only; if `v1` labeling appears later, the same ACs apply to it. AC numbering does not re-fork by HUD.

1. [ ] **AC1 — Hard-dependency landed gate.** Before any zone-picking work begins, verify on `main`:
   - Story 9.9c (`9-9c-schema-unification`) is `done` (schema unified; emitter fragment-driven; `python apps/tooling/tools/map_config_emitter.py --zones-dir <dir>` works end-to-end).
   - Story 9.11 (`9-11-retire-legacy-tooling`) is `done` (legacy `auto_roi_discoverer/`, `minimap_zone_selector/`, `overlay_stack_analyzer.py`, `game_detector.py`, `black_screen_detector.py`, `bsd_roi_debugger.py`, `frame_labeler.py` ← deleted; `MAP_LABELS` no longer importable from `tools.frame_labeler`).
   - Story 9.12 (`9-12-unified-zone-picker`) is `done` (`apps/tooling/tools/zone_picker.py` exists; runnable in 3 modes — HUD-version / in-match / per-map; writes the 4-fragment shape under `apps/tooling/output/zones/v<hud_version>/`).
   - Story 9.14 (`9-14-roi-detection-tester-refit-for-unified-schema`) is `done` (Tool 9 reports HUD-version + binary `in_match` + per-map classifiers against the unified schema).
   - Story 9.13 (`9-13-video-detection-tester`) is **recommended `done`** but not strictly blocking for in-pixel iteration; required by AC8 (real-video smoke). If 9.13 is not done, AC8 holds `[ ]` and the iteration loop runs without end-to-end validation — flag in Change Log.
   - Record commit SHAs for each upstream story's merge in this AC's sub-bullet at gate-pass time.

2. [ ] **AC2 — Labeled dataset coverage confirmed.** For each HUD version in scope, verify on disk:
   - `apps/tooling/output/labeled/v<hud_version>/lobby/*.png` exists (≥ 200 frames).
   - `apps/tooling/output/labeled/v<hud_version>/score/*.png` exists (≥ 200 frames).
   - `apps/tooling/output/labeled/v<hud_version>/transition/*.png` exists (≥ 50 frames; transition is short).
   - `apps/tooling/output/labeled/v<hud_version>/<map_slug>/*.png` exists for **at least 10 of the 14 production maps** (≥ 100 frames each). The slug regex `^[a-z][a-z0-9_]*$` matches every folder name (else `minimap_identification.maps` schema validation will reject downstream).
   - Record exact per-folder frame counts in the iteration log (see AC7).
   - If any of the above fail: HALT. Backfill labeling via Tool 6 (Story 9.5) before continuing. Tool 6 is `done` and stays on `main`; 9.11 does not touch it.

3. [ ] **AC3 — Per-HUD `manifest.json` written.** For each HUD version in scope, the human authors `apps/tooling/output/zones/v<hud_version>/manifest.json` once (these three fields cannot be inferred from labeled PNGs):
   - `hud_version`: matches the enum in `contracts/map-config.schema.json` (today `"v1"` or `"v2"`; the schema's `hud_version` enum is the canonical list — if a new HUD ships, extend the schema first, then this manifest).
   - `score_screen_duration_ms`: integer ≥ 0. **Calibration procedure:** sample ≥ 5 EVA captures, measure the time between the `in_match` falling edge and the next `not_in_match` rising edge (via Tool 6's timeline or manually in any video player). Take the **median** rounded up to the nearest 500 ms. Document the sample and the chosen value in the iteration log.
   - `reference_resolution`: `{width: 1920, height: 1080}` for standard EVA HUD captures (default). Override only if the labeled dataset was sourced at a different reference resolution.
   - The 4-fragment layout is the contract; any deviation (extra keys in `manifest.json`, missing required keys) will be rejected by `_assemble_output`'s clean-error gate (`apps/tooling/tools/map_config_emitter.py` post-9.9c) — verify by running the emitter with the manifest alone (other fragments can be empty `[]` arrays for this dry-run).

4. [ ] **AC4 — Zone fragments populated via `zone_picker` (Story 9.12), per HUD version.** Run `zone_picker` in all 3 modes per HUD version; each mode writes its own fragment file under `apps/tooling/output/zones/v<hud_version>/`:
   - **HUD-version mode** → `hud_version_detection.json` (JSON array of Zone dicts; matches the unified schema's `Zone` shape — `{id, x, y, width, height, hsv, min_ratio, weight, weight_override}`). Picked against cross-HUD labeled samples (any frame from `labeled/v<hud>/` distinguishes from any frame in `labeled/v<other_hud>/`). Empty array (`[]`) is schema-valid but operationally useless — the classifier will short-circuit to `"unknown"` and Tool 9 will report accuracy 0.000. Document zero-zone fragments in the iteration log as "deferred until cross-HUD labeling" but do not commit them as final.
   - **In-match mode** → `in_match_detection.json` (JSON array of Zone dicts). Positive class = any `labeled/v<hud>/<map_slug>/` frame; negative class = any `labeled/v<hud>/{lobby,score,transition}/` frame. Same empty-fragment caveat applies.
   - **Per-map mode** → `minimap_identification.json` (`{id, identification_threshold, roi, maps: {<slug>: {zones: Zone[]}}}`). Slug regex must match (`^[a-z][a-z0-9_]*$`); use `lowercase_with_underscores` for any new map. `identification_threshold` is the per-map confidence cutoff (default `0.5` — tune empirically based on Tool 9 refit's argmax-vs-threshold behavior). `roi` is the minimap region of interest in `Rect` shape; standard EVA-HUD-v2 minimap ROI is `{name: "minimap", x: <TBD>, y: <TBD>, width: <TBD>, height: <TBD>}` — measure on a representative frame.
   - **Pre-flight:** `python apps/tooling/tools/map_config_emitter.py --zones-dir apps/tooling/output/zones/v<hud_version>` MUST succeed (zero exit code; writes `<output_dir>/map_config.v<hud_version>.json`). If validation fails: read the stderr error, fix the offending fragment, retry. Atomic-refusal guarantee from 9.9c means no partial config is ever written.

5. [ ] **AC5 — Emitted `map_config.v<hud_version>.json` validates against the unified schema.** After every zone-picker pass, run `python apps/tooling/tools/map_config_emitter.py --zones-dir apps/tooling/output/zones/v<hud_version>` and verify:
   - Exit code 0.
   - File written at `apps/tooling/output/map_configs/map_config.v<hud_version>.json`.
   - File round-trips through `python -c "import json; from jsonschema import Draft202012Validator; from pathlib import Path; s = json.loads(Path('contracts/map-config.schema.json').read_text(encoding='utf-8')); d = json.loads(Path('apps/tooling/output/map_configs/map_config.v<hud_version>.json').read_text(encoding='utf-8-sig')); Draft202012Validator(s).validate(d); print('OK')"`.
   - First key of the file is `schema_version` (`head -1` of the file shows `"schema_version": 1,` — the readable-diff invariant from 9.9c's `TestEmit::test_first_key_in_written_file_is_schema_version`).
   - Re-running the emitter overwrites the previous file silently (per 9.9c's review-deferred decision — overwrite-by-default is the 9.9b iteration ergonomic; do NOT add `--no-overwrite` / `--force`).

6. [ ] **AC6 — Per-classifier accuracy floors measured via Tool 9 refit (Story 9.14).** Run the refit `roi_detection_tester` against the labeled dataset for each HUD version. Capture the report at `apps/tooling/output/roi_detection_tests/v<hud_version>/<timestamp>/`:
   - **HUD-version classifier:** target **≥ 99.0%** on cross-HUD samples (small problem surface; high contrast between HUD generations). If only one HUD version is in scope, the classifier short-circuits — document "single-HUD scope; HUD-version classifier accuracy not measurable" in the iteration log.
   - **In-match (binary) classifier:** target **≥ 97.0%** (high-stakes — a wrong binary state breaks the entire state machine downstream; per-map ID won't fire on `not_in_match` frames).
   - **Per-map ID classifier:** target **≥ 95.0%** (anchored to PRD `REL-006` — "Map identification accuracy ≥ 95% on a held-out test set," [prd.md:1042](../prd.md#L1042)). Held-out cohort definition: if labeled dataset has > 100 frames per map, hold out the **last 20 frames per map (by filename sort)** as the test cohort; if ≤ 100 per map, document as "small-sample; full dataset used" and accept the variance.
   - **Confidence cutoff:** `roi_detection_tester` defaults to argmax-above-threshold = 0.5 → predicted class; below → `"unknown"`. Document per-class threshold choices in the iteration log if any are tuned.
   - **If any floor missed:** identify the worst-confused pair from Tool 9's `summary.md` (top 5 confused pairs section), inspect the offending zone(s) via `zone_picker`'s overlay-preview, adjust HSV bands or zone geometry, re-emit, re-measure. Loop. Cap iterations at **8 passes per HUD version** before declaring a class non-convergent; at that point either (a) accept the measured floor with a documented variance note, or (b) escalate to a separate "data quality" story.

7. [ ] **AC7 — Iteration log written.** Per HUD version, append a section to this story's **Completion Notes** at dev-story-finalization time with the following table per HUD version:

   ```
   ### v<hud_version> iteration log

   | Pass | Date | Zone changes | HUD-version acc | In-match acc | Per-map acc | Notes |
   |---|---|---|---|---|---|---|
   | 0 (baseline) | YYYY-MM-DD | initial zone_picker output | 0.000 | 0.000 | 0.000 | empty fragments |
   | 1 | YYYY-MM-DD | + 3 HUD zones, + 5 in-match zones, + 12 map zones | 0.92 | 0.87 | 0.78 | confused: artefact↔atlantis (16%); per-map below floor |
   | 2 | YYYY-MM-DD | tightened artefact_z2 hue band; added atlantis_z4 | 0.92 | 0.91 | 0.89 | confused: helios↔engine (4%); per-map still below floor |
   | … | … | … | … | … | … | … |
   | N (final) | YYYY-MM-DD | … | 0.99 | 0.98 | 0.96 | all floors met |
   ```
   - Each row corresponds to one zone-picker → emit → Tool 9 measurement cycle.
   - "Zone changes" column: terse (verb + zone IDs); the actual zone state lives in the committed fragment files.
   - "Notes" column: top-confused pairs from Tool 9 summary, any threshold tweaks, any data-quality observations.
   - **Score-screen duration calibration sub-section:** record the sample (5+ captures), the per-capture measured durations, the median, the chosen `score_screen_duration_ms`.

8. [ ] **AC8 — End-to-end video pipeline validated via `video_test` (Story 9.13).** For each HUD version, run `python apps/tooling/tools/video_test.py <real_video.mp4> --config apps/tooling/output/map_configs/map_config.v<hud_version>.json --output <results.json>` against **at least one representative real EVA capture** (5+ minutes; covers ≥ 2 maps; includes ≥ 1 round transition). Verify:
   - HUD-version classifier fires the correct version (once per session).
   - State machine produces plausible `in_match` → `score_screen` → `not_in_match` transitions (manually cross-check against the video timeline — `video_test`'s `results.json` lists `{frame_idx, timestamp_ms, state}` per i-frame).
   - Each `in_match` span carries a `matches` entry with a `map_id` that matches the actual map in that span (verify against ground truth either from Tool 6's labeling or by visual inspection).
   - Score-screen window length (frames flagged after `in_match` falling edge) corresponds to `score_screen_duration_ms` divided by i-frame interval.
   - **Failures** (wrong HUD, missing `in_match` span, wrong map_id, score-screen too long/short): document in iteration log; treat as a measured-floor regression; re-iterate via AC6. Cap at the same 8-pass ceiling.
   - **If Story 9.13 is not done:** this AC holds `[ ]` and the iteration loop runs without end-to-end validation. Flag in Change Log; flip `[x]` once 9.13 lands and the smoke run completes.

9. [ ] **AC9 — Source-of-truth zone fragments committed to version control.** **Decision required (committed at dev-story kickoff):** the populated zone fragments (the human's manual work product) currently live under `apps/tooling/output/zones/v<hud_version>/` which is gitignored per [`.gitignore:63`](../../.gitignore#L63) (`apps/tooling/output/`). Pick one path:
   - **Option A (recommended): `.gitignore` exception.** Add `!apps/tooling/output/zones/` to `.gitignore` (immediately after line 63's `apps/tooling/output/`). Commit the populated `apps/tooling/output/zones/v<hud_version>/*.json` files. Pros: zero path change; `zone_picker` and the emitter already point here; matches the "fragments are the source-of-truth, the emitted config is regenerable" framing. Cons: one minor `.gitignore` exception per output subfolder.
   - **Option B: move to a committed config dir.** Promote the finalized fragments from `apps/tooling/output/zones/v<hud_version>/` to a new committed location (e.g., `apps/tooling/config/zones/v<hud_version>/`). Update `wardentooling.py:flow_tool3` blank-default zones-dir to point there. Pros: clean separation between "working draft" and "shipped." Cons: requires a Python-side change (out of the no-code-changes spirit of 9.9b — would re-open 9.9c's emitter); contradicts 9.9c's Project Structure Notes section ("Fragment-dir convention: `apps/tooling/output/zones/v<hud_version>/`").
   - **Default if undecided:** Option A. Lower risk; preserves 9.9c's path convention; one `.gitignore` line.
   - Record the chosen option in the iteration log and Change Log. Commit the populated fragments accordingly.

10. [ ] **AC10 — No code changes outside the data/config surface.** Verify with `git diff main --stat`:
    - Modified: `_bmad-output/sprint-status.yaml`, `_bmad-output/implementation-artifacts/9-9b-iterative-zone-population-for-shipping-configs.md`, `.gitignore` (one line, only if AC9 Option A), `apps/tooling/output/zones/v<hud_version>/{manifest,hud_version_detection,in_match_detection,minimap_identification}.json` (4 files per HUD version), `apps/tooling/output/map_configs/map_config.v<hud_version>.json` (per HUD version; or gitignored — decide alongside AC9).
    - **Untouched:** `contracts/map-config.schema.json`, `apps/tooling/tools/*.py`, `apps/tooling/tests/test_*.py`, `apps/tooling/wardentooling.py`, `apps/mobile/**`, `apps/web/**`, `packages/**`. If `git diff` shows any change in these paths, STOP — 9.9b's scope has been violated; the offending change belongs in a separate story.
    - **Test suite gate:** `cd apps/tooling && uv run pytest` and `pnpm --filter tooling test` MUST stay green at the same count they were at when 9.9c + 9.14 merged. 9.9b does not add or modify tests.

11. [ ] **AC11 — Sprint-status entry + lifecycle flip.** `_bmad-output/sprint-status.yaml` `9-9b-iterative-zone-population-for-shipping-configs` flows `ready-for-dev → in-progress → review → done`. The `review → done` flip ships in the tiny post-merge follow-up PR per [[feedback_two_pr_docs_execution]]. Update `last_updated` header in both the dev-story commit and the post-merge follow-up. Epic 9 stays `in-progress`. **NOTE:** If 9.9b's deliverable spans multiple HUD versions delivered in separate PRs across multiple sprints, each HUD-version-completion PR flips `in-progress → review` and the post-merge follow-up flips `review → ready-for-dev` (NOT `done`) until the final HUD version's PR; only the final PR's post-merge follow-up flips to `done`. Document the chosen rollout (single-PR vs. multi-HUD-staged) at dev-story kickoff in the Change Log.

12. [ ] **AC12 — Single-PR delivery + Two-PR follow-up per HUD-version cohort.** Each completed HUD version's data set ships in one PR titled `data: populate map_config.v<hud_version>.json (Story 9.9b)` (subject lowercased on the commit; capitalized in the PR title). Branch `story-9-9b-v<hud_version>` off `main`. PR body links: this story file; [`_bmad-output/sprint-change-proposal-2026-05-15.md`](../sprint-change-proposal-2026-05-15.md) (full rationale); Story 9.9c's story file (predecessor — schema + emitter contract); the relevant Tool 9 refit report directory under `apps/tooling/output/roi_detection_tests/v<hud_version>/<timestamp>/` (for accuracy floor evidence). After each PR merges: post-merge follow-up branch `story-9-9b-v<hud_version>-postmerge` with the sprint-status flip per AC11 + AC11/AC12 box flips here (or per-HUD-version row checkboxes if multi-HUD-staged).

## Tasks / Subtasks

> **Implementation order:** the dependencies (AC1) gate the entire story — DO NOT begin Task 2 until they're all `done` on `main`. Once unblocked, the per-HUD-version loop (Tasks 3–6) repeats for each HUD version in scope (today: just v2). Task 7 (commit + PR) bookends each HUD version's cohort.

- [ ] **Task 1: Pre-flight verification (AC: 1, 2)**
  - [ ] Pull `main`. Verify the four hard-dependency stories are all `done` in `sprint-status.yaml` and on disk: `python apps/tooling/tools/map_config_emitter.py --help` shows `--zones-dir` (not `--config`); `apps/tooling/tools/zone_picker.py` exists; `apps/tooling/tools/roi_detection_tester.py` reports the refit 3-classifier output shape (HUD-version + binary in_match + per-map; see Story 9.14's AC5–AC8); `apps/tooling/tools/auto_roi_discoverer/`, `apps/tooling/tools/minimap_zone_selector/`, `apps/tooling/tools/overlay_stack_analyzer.py`, `apps/tooling/tools/game_detector.py`, etc. ← NOT present (deleted by 9.11). Record each merge SHA in AC1's sub-bullet.
  - [ ] Verify 9.13 (`video_test`) status; if not `done`, document the deferral on AC8 and proceed (iteration loop still works; end-to-end smoke is the only gap).
  - [ ] Inventory labeled dataset under `apps/tooling/output/labeled/v<hud_version>/`. For each HUD version in scope, count frames per class folder (`ls apps/tooling/output/labeled/v<hud_version>/<class>/ | wc -l` per class). Verify the minimums in AC2. If labeling is short on any class, HALT and run Tool 6 (Story 9.5, still `done` on `main` post-9.11) to backfill.
  - [ ] Decide AC9 (zone-fragment commit location) at the **start** of this task, before any zone-picking work. Default: Option A (`.gitignore` exception). If Option B (committed config dir), record the path-change plan in the Change Log + flag the cross-cutting change to `wardentooling.py` (which 9.9b normally does NOT touch — Option B re-opens 9.9c, which the team should explicitly accept before continuing).

- [ ] **Task 2: Per-HUD manifest authoring (AC: 3)** — runs once per HUD version
  - [ ] Create `apps/tooling/output/zones/v<hud_version>/` (mkdir).
  - [ ] Write `manifest.json` with `hud_version`, `score_screen_duration_ms`, `reference_resolution` per AC3.
  - [ ] **Score-screen calibration sub-task:** open ≥ 5 EVA captures in a video player; for each, measure the elapsed time from the moment the in-match HUD vanishes (falling edge) to the moment the lobby/transition UI returns (rising edge); record per-capture durations + median + chosen `score_screen_duration_ms`. Document the sample in the iteration log under "v<hud_version> score-screen calibration."
  - [ ] Dry-run the emitter with manifest + 3 empty-array fragments: `python apps/tooling/tools/map_config_emitter.py --zones-dir apps/tooling/output/zones/v<hud_version>/` — should write `map_config.v<hud_version>.json` with empty zone arrays and minimap_identification with no maps. Validates that the manifest shape is correct independent of any zone work.

- [ ] **Task 3: Initial zone-picking pass (AC: 4, 5)** — runs once per HUD version
  - [ ] Run `zone_picker` in **HUD-version mode** (or skip if single-HUD scope per AC6). Output → `apps/tooling/output/zones/v<hud_version>/hud_version_detection.json`.
  - [ ] Run `zone_picker` in **in-match mode**. Output → `apps/tooling/output/zones/v<hud_version>/in_match_detection.json`.
  - [ ] Run `zone_picker` in **per-map mode** for each labeled map slug. Output → merged into `apps/tooling/output/zones/v<hud_version>/minimap_identification.json` under `maps.<slug>.zones`. zone_picker's design (Story 9.12 AC TBD) handles the merge; if not, manually concatenate JSON.
  - [ ] Run the emitter; verify per AC5 (exit 0, file written, jsonschema validates, `schema_version` is the first key).
  - [ ] Record this as "Pass 1" in the iteration log (table per AC7).

- [ ] **Task 4: Measurement-and-adjust iteration loop (AC: 6, 7)** — repeats until all per-class floors met OR 8-pass ceiling hit
  - [ ] Run `python apps/tooling/tools/roi_detection_tester.py --config apps/tooling/output/map_configs/map_config.v<hud_version>.json --labeled-dir apps/tooling/output/labeled/v<hud_version>/ --output apps/tooling/output/roi_detection_tests/v<hud_version>/<timestamp>/` (exact CLI shape per Story 9.14's CLI; adjust as 9.14 finalizes).
  - [ ] Read `summary.md`: HUD-version accuracy, in-match accuracy, per-map accuracy, top-5 confused pairs per classifier.
  - [ ] **If all 3 classifier floors met:** advance to Task 5.
  - [ ] **If any floor missed:** open the worst-confused pair's zone(s) in `zone_picker`'s overlay-preview mode (Story 9.12 should support this). Adjust HSV bands (tighten H tolerance, narrow S/V range), zone geometry (shift, shrink), or `min_ratio`. Re-emit. Re-measure. Add a new row to the iteration-log table.
  - [ ] **At the 8-pass ceiling per HUD version:** stop iterating. Document the achieved floors as "best-effort with current data" + the worst-confused pair(s) that prevented further convergence. Decide: (a) accept and continue to Task 5 with documented variance, OR (b) HALT and escalate as a separate "data quality" follow-up story (e.g., add labeled frames; refine the labeler ROI; revisit zone_picker's HSV-band-suggestion algorithm).

- [ ] **Task 5: End-to-end real-video validation (AC: 8)** — runs once per HUD version (deferrable if 9.13 not done)
  - [ ] Pick at least one representative real EVA capture (5+ minutes; ≥ 2 maps; ≥ 1 round transition). Source: `apps/tooling/source/` (gitignored per `.gitignore:62`) OR a fresh capture.
  - [ ] Run `python apps/tooling/tools/video_test.py <video.mp4> --config apps/tooling/output/map_configs/map_config.v<hud_version>.json --output apps/tooling/output/video_tests/v<hud_version>/<timestamp>/results.json` (exact CLI shape per Story 9.13's CLI; adjust as 9.13 finalizes).
  - [ ] Open `results.json`; cross-check HUD-version classification, `in_match` spans, `map_id` assignments, score-screen window length against the actual video timeline.
  - [ ] **If smoke pass:** record under iteration log "v<hud_version> end-to-end smoke" — PASS, with the 1-line verification summary.
  - [ ] **If smoke fail:** treat as a measured-floor regression. Loop back to Task 4 with the smoke-test findings as the next iteration's adjustment target.
  - [ ] **If 9.13 not done:** skip this task; hold AC8 `[ ]`; flag in Change Log; will be backfilled when 9.13 lands (could be in a separate sub-PR).

- [ ] **Task 6: Story closure for this HUD version (AC: 7, 9, 10)** — runs once per HUD version
  - [ ] Finalize the iteration log section under Completion Notes (full table + score-screen calibration + per-classifier final floors).
  - [ ] Commit the populated zone fragments per AC9's chosen path (Option A or B; default A).
  - [ ] Verify `git diff main --stat` matches AC10's allowed-files-only invariant.
  - [ ] Verify test suite stays green: `cd apps/tooling && uv run pytest` (count = post-9.14 baseline) and `pnpm --filter tooling test` (count = post-9.14 baseline).

- [ ] **Task 7: PR + sprint-status flips (AC: 11, 12)** — runs once per HUD version (or once for the whole story if single-PR rollout chosen at kickoff)
  - [ ] Branch `story-9-9b-v<hud_version>` off `main`. Stage chunks: (a) `manifest.json` + 4 fragment files at `apps/tooling/output/zones/v<hud_version>/`; (b) `apps/tooling/output/map_configs/map_config.v<hud_version>.json` (or omit if gitignored per AC9 Option A's sub-decision); (c) `.gitignore` change if Option A; (d) this story file (iteration log + Dev Agent Record + File List + Change Log); (e) `_bmad-output/sprint-status.yaml` flip `ready-for-dev → in-progress → review` (or `review` only if this is mid-cohort + AC11 multi-PR rollout). Push.
  - [ ] Open PR `data: populate map_config.v<hud_version>.json (Story 9.9b)` against `main`. PR body per AC12; include Tool 9 refit report directory path in the body.
  - [ ] After merge: branch `story-9-9b-v<hud_version>-postmerge` off `main`. Flip sprint-status per AC11 (typically `review → done` for final HUD version, or `review → ready-for-dev` for intermediate cohorts). Flip this story's AC11 + AC12 + Task 7 sub-boxes to `[x]`. Open tiny follow-up PR `chore: Story 9.9b v<hud_version> post-merge follow-up`.

## Dev Notes

### Strategic context

9.9b sits in a peculiar slot in the 9.9 family: 9.9a and 9.9c are **code stories** that ship structure (schema, emitter, validation gate); 9.9b is the **data story** that gives the structure its real-world payload. Until 9.9b runs, the schema is empty calories — no app can detect a single map, no Tool 9 run has any zones to score, no video flowing through the pipeline produces useful classification. After 9.9b runs, the project has an *actual* shipping map_config per HUD version with empirical accuracy data behind it. The deliverable is **dat**a + **measurement** + **documentation**, not code.

The story is paired with Story 1.13 (Hybrid map_config Delivery, currently `backlog` with anchor flipped from 9.9a → 9.9c, see `sprint-status.yaml:71`). 1.13 decides the **bundling** strategy (manifest + per-HUD files vs. single union file) and ships the bundle into `apps/mobile/assets/`. 9.9b decides the **content** of each per-HUD file. They run independently; 1.13 can pick up whatever 9.9b has produced at any point.

The 8-pass-per-HUD ceiling in Task 4 is calibrated from prior iteration cycles documented for Tool 8 / Tool 9 (see `sprint-status.yaml:178`'s 2026-05-12 entry: "Worst-performing zones top-10 are uniformly very-loose-band exclusion-style zones with low precision/high recall…"). Real-world convergence with the in-match game-state classifier was slow when zones were empty (`0.000` accuracy until lambda zones populated); with `zone_picker` (9.12) replacing Tool 8's auto-suggestion, the human-driven loop should converge faster but is not instant.

**Why no code:** 9.9b's whole point is to be the **first story in the new pipeline where the tools are mature enough to use without modification**. If the dev finds themselves touching `map_config_emitter.py` to "fix" something, that's a 9.9c amendment (re-open the story) or a separate bug-fix story. If the dev finds themselves touching `zone_picker.py` to add a feature, that's a 9.12 amendment. 9.9b stays pure: data files in, accuracy floors out.

**Why "ready-for-dev" with unresolved deps:** the BMad workflow convention is that a story's spec is "ready" once it's been written; the dev cycle stays in `ready-for-dev` until the dev is ready to start. With 9.9c at `review` (Task 7 PR pending), 9.11 / 9.12 / 9.13 / 9.14 at `backlog`, the realistic dev-story kickoff is weeks out. The spec being `ready-for-dev` does NOT mean the work can begin tomorrow — it means the spec is comprehensive enough that when the deps land, the dev can pick this up cold and start measuring without further create-story work.

### Key code patterns to reuse (NOT reinvent)

| Need | Source | Notes |
|---|---|---|
| Fragment-dir layout convention | [`_bmad-output/implementation-artifacts/9-9c-schema-unification.md#AC3`](9-9c-schema-unification.md) | 4 files: `manifest.json`, `hud_version_detection.json`, `in_match_detection.json`, `minimap_identification.json` — exact JSON shape per Story 9.9c AC3. 9.9b's manifest authoring (Task 2) follows this contract verbatim. |
| Unified Zone shape | [`contracts/map-config.schema.json` `$defs.Zone`](../../contracts/map-config.schema.json) | `{id, x, y, width, height, hsv, min_ratio, weight, weight_override}`. User-space HSV (H 0-360, S/V 0-100); `weight_override` is `number | null`, NOT boolean. `zone_picker` writes this shape directly. |
| Emitter CLI | [`apps/tooling/tools/map_config_emitter.py`](../../apps/tooling/tools/map_config_emitter.py) (post-9.9c) | `python tools/map_config_emitter.py --zones-dir <dir> [--output-dir <dir>]`. Validates against schema before any write (atomic refusal); output filename derives from `manifest.hud_version` (`map_config.v<hud_version>.json`). |
| Tool 9 refit run shape | Story 9.14 (TBD on land) | Per-classifier report at `apps/tooling/output/roi_detection_tests/v<hud_version>/<timestamp>/{report.json, summary.md}` — same structure as the pre-9.14 Tool 9 output (see `sprint-status.yaml:188` for the original Tool 9 dev-story log). 9.14 adds the HUD-version classifier and collapses the 4-way game-state to binary `in_match`. |
| Video pipeline run shape | Story 9.13 (TBD on land) | `python tools/video_test.py <video.mp4> --config <map_config.v<hud>.json> --output <results.json>` — pipeline stages per the sprint-status entry at `sprint-status.yaml:187` (i-frame extract → HUD-version → state machine → per-`in_match`-span map ID). |
| Score-screen calibration approach | This story Task 2 + AC3 | Manual measurement; median of ≥ 5 captures; integer ms; the schema enforces `score_screen_duration_ms: { type: integer, minimum: 0 }` (no upper bound). |
| Held-out test cohort definition | This story AC6 | Last 20 frames per map by filename sort (if > 100 per map); else "small-sample; full dataset" with documented variance. The `roi_detection_tester` CLI may or may not support `--holdout-cohort`; if not, run the test twice (full + manual filename-filter) and document the held-out result. |
| Slug regex for `minimap_identification.maps` | [`contracts/map-config.schema.json` `patternProperties`](../../contracts/map-config.schema.json) | `^[a-z][a-z0-9_]*$`. Uppercase, hyphens, dots, spaces are rejected. Match the labeled folder name (`apps/tooling/output/labeled/v<hud>/<slug>/`) to the slug exactly. |
| Two-PR pattern | [[feedback_two_pr_docs_execution]] | Main PR ships data + flips `backlog → review`; tiny post-merge follow-up flips `review → done` (or `review → ready-for-dev` for mid-cohort PRs). Both PRs link this story file. |

### Anti-patterns / disasters to avoid

- **DO NOT touch any `.py` file.** 9.9b is data + config. If a Python change is needed (e.g., emitter doesn't handle a fragment shape, picker has a bug), STOP — that's a 9.9c / 9.12 / 9.13 / 9.14 amendment. Re-open the appropriate story and ship the code change there, then come back to 9.9b. Crossing the data/code line means 9.9b is no longer in scope.
- **DO NOT touch `contracts/map-config.schema.json`.** If a zone shape needs to change (e.g., adding a new `Zone` field), that's a schema-evolution story (likely a new 9.9d, or fold into 9.10's editorial pass with a separate code-change story upstream of it). Not 9.9b's lane.
- **DO NOT manually hand-edit `apps/tooling/output/zones/v<hud>/*.json`.** Use `zone_picker` exclusively. Hand-edits drift from picker state, break the picker's resume-from-disk capability (if 9.12 supports it), and bypass the schema-shape guarantees. The only exception is `manifest.json` (Task 2 — the picker doesn't author it because the three fields aren't derivable from labeled PNGs).
- **DO NOT manually hand-edit `apps/tooling/output/map_configs/map_config.v<hud>.json`.** This file is regenerated by `map_config_emitter` from the fragments. Editing it directly creates drift that's invisible to the pipeline (`zone_picker` and the picker workflow don't read the assembled config, only the fragments) and silently disappears at the next emit. If a fix is needed: fix the fragment, re-emit.
- **DO NOT skip the schema validation gate.** Every `zone_picker` run must be followed by an `emit` run before moving on. The atomic-refusal guarantee from 9.9c (validate before any write) means a failing emit surfaces problems immediately. If validation fails: read stderr, fix the fragment, re-emit. DO NOT proceed to Tool 9 measurement with an unvalidated fragment.
- **DO NOT measure against the full labeled dataset only.** Per AC6, the per-map ID accuracy is measured on a **held-out** cohort (last 20 frames per map, if available). Measuring on the same frames the picker was tuned against produces an inflated number — that's how zone fragments overfit silently. Tool 9 may or may not expose `--holdout`; if not, run twice (full + manually filtered) and report the held-out number.
- **DO NOT chase the floor below diminishing returns.** Tighten the 8-pass ceiling per Task 4. If pass 6 shows 0.94 and pass 7 shows 0.945, declare convergence and document the floor variance. Endless re-iteration on the same data is a sign that either (a) the data isn't sufficient (more labeling needed) or (b) the zone-picker's HSV-band-suggestion algorithm has a structural blind spot (9.12 amendment). Either is a separate follow-up.
- **DO NOT bundle to mobile in this story.** `apps/mobile/assets/map_config.json` (single file) or `apps/mobile/assets/map_configs/` (per-HUD layout) is Story 1.13's deliverable. 9.9b stops at `apps/tooling/output/map_configs/map_config.v<hud>.json`. The committed location for fragments (per AC9) is the only commit 9.9b makes into version control beyond the story file + sprint-status.
- **DO NOT mix HUD versions in one PR if multi-HUD rollout was chosen at kickoff.** Each HUD version's data set is its own atomic unit. Mixing them in one PR makes per-HUD review impossible. Single-HUD rollout (one PR for all of v2 today) is fine; multi-HUD rollout is one PR per HUD.
- **DO NOT skip the iteration log.** The accuracy floors documented in Completion Notes are 9.9b's deliverable on equal footing with the populated config. No log = no story closure.
- **DO NOT add an `accuracy_floor` field to the schema.** Tempting because "the floor is per-config, per-HUD." But that's metadata about the config-tuning process, not configuration the runtime needs. The runtime reads the zones and runs the classifier; the floor lives in this story's documentation only.
- **DO NOT change `score_screen_duration_ms` after Task 2 without re-running Task 5.** The state machine's score-screen window length is timing-derived; changing it mid-iteration invalidates all prior end-to-end smoke tests. If Task 2's median estimate turns out wrong (Task 5 surfaces a state-machine mismatch): redo Task 2's calibration, then redo Task 5.
- **DO NOT cancel 9.9b prematurely.** If 9.12 or 9.14 lands and the team decides "we'll just ship without empirical floors," that's a decision to take with a /bmad-correct-course, not a silent skip. 9.9b's status flip belongs in sprint-status.yaml with rationale.

### File structure

```
apps/tooling/
  output/
    zones/
      v2.0/                                  # NEW (post-9.12 zone_picker first run): committed (AC9 Option A) or promoted (Option B)
        manifest.json                        # NEW: human-authored (Task 2)
        hud_version_detection.json           # NEW: zone_picker HUD-version mode output
        in_match_detection.json              # NEW: zone_picker in-match mode output
        minimap_identification.json          # NEW: zone_picker per-map mode output (merged across maps)
    map_configs/
      map_config.v2.json                     # NEW: emitter output (per-HUD); decide commit-vs-gitignore alongside AC9
    labeled/
      v2.0/                                  # UNTOUCHED: Tool 6 (Story 9.5) labeling dataset
        lobby/*.png
        score/*.png
        transition/*.png
        <map_slug>/*.png  (≥10 maps)
    roi_detection_tests/                     # UNTOUCHED at story level (subdir written by Tool 9 refit per iteration)
      v2.0/<timestamp>/report.json + summary.md
    video_tests/                             # UNTOUCHED at story level (subdir written by video_test per smoke run, if 9.13 done)
      v2.0/<timestamp>/results.json

.gitignore                                   # MODIFIED if AC9 Option A: add `!apps/tooling/output/zones/` after line 63

_bmad-output/
  implementation-artifacts/
    9-9b-iterative-zone-population-for-shipping-configs.md   # THIS FILE: iteration log + Dev Agent Record + File List + Change Log
  sprint-status.yaml                         # MODIFIED: 9-9b lifecycle flips (ready-for-dev → in-progress → review → done per AC11 cadence)

# UNTOUCHED — out of 9.9b's scope:
contracts/                                   # schema is finalized by 9.9c
apps/tooling/tools/                          # Python code is finalized by 9.9c + 9.11 + 9.12 + 9.13 + 9.14
apps/tooling/tests/                          # tests are owned by the code stories
apps/tooling/wardentooling.py                # TUI registration is owned by 9.9c + 9.11 + 9.12 + 9.13 + 9.14
apps/mobile/                                 # bundling is Story 1.13's deliverable
apps/web/                                    # no consumer
packages/                                    # no consumer
```

### Library / framework requirements

- **No new dependencies of any kind.** 9.9b is a data-production story; the tooling it uses (`zone_picker`, `map_config_emitter`, `roi_detection_tester`, `video_test`) ships its dependencies via the code stories that build them.
- **Tooling versions to verify before kickoff:** `apps/tooling/pyproject.toml` carries `jsonschema >= 4.23.0`, `numpy`, `opencv-python`, `pyyaml`. `packages/contracts/package.json` carries `json-schema-to-zod ^2.6.1`. None of these are touched by 9.9b; they're listed here for the dev's pre-flight sanity check that the deps are still in place after 9.11's retirement pass.
- **Test runtime:** 9.9b does NOT add or modify tests. Existing `cd apps/tooling && uv run pytest` and `pnpm --filter tooling test` MUST stay green at the same count they were at when 9.14 merged — AC10's "untouched code" invariant guarantees this; the green-test gate verifies it.

### Testing standards

- 9.9b has no unit tests of its own. The deliverable is empirical data, not code logic. **Tool 9 refit (Story 9.14) is the test for 9.9b's output.** The per-class accuracy report **is** the success criterion (AC6).
- **No synthetic data.** 9.9b runs against the **real** labeled dataset at `apps/tooling/output/labeled/v<hud_version>/`. No `tmp_path` fixtures. No `pytest`-driven fragments. The point is real-world calibration.
- **Held-out cohort discipline.** Per AC6: last 20 frames per map by filename sort (if > 100 per map) form the held-out test set. The non-held-out frames form the "training" set (i.e., the cohort the human visually inspects while picking zones in `zone_picker`). Reporting the held-out number, not the full-dataset number, is the integrity guarantee against overfitting.
- **Reproducibility.** The Tool 9 refit report directory under `apps/tooling/output/roi_detection_tests/v<hud_version>/<timestamp>/` is the audit trail. Each iteration in the log corresponds to one timestamped subdir on disk (`apps/tooling/output/` is gitignored per AC9 Option A's exception scope — `roi_detection_tests/` stays gitignored). The story's iteration log table is the human-readable summary; the on-disk reports are the raw evidence; the PR links the final report directory's path in the body.
- **End-to-end smoke.** Per AC8: at least one real EVA capture per HUD version through `video_test` (Story 9.13). The smoke test is mostly visual cross-check (i.e., does the state-machine output match what the human sees in the video player). No automated assertions; the dev signs off in the iteration log.

### Sprint-fit + dependencies

- **Track C** (tooling chain). Parallel-safe with Tracks A/B; independent of the AR-SPIKE outcome.
- **Hard upstream (all must be `done` before dev-story kickoff):** 9.9c (schema + emitter), 9.11 (legacy retirement), 9.12 (`zone_picker`), 9.14 (`roi_detection_tester` refit). All four were created via the 2026-05-15 correct-course; all four are currently `backlog` or `review` (9.9c only) — see `sprint-status.yaml:184-188`.
- **Strongly recommended upstream:** 9.13 (`video_test`) — needed for AC8 (end-to-end smoke). If 9.13 hasn't landed when 9.9b's iteration loop converges (AC6 met), 9.9b can ship with AC8 held `[ ]` and a flag in Change Log; AC8 backfills once 9.13 lands.
- **Downstream:** Story 1.13 (Hybrid `map_config.json` Delivery) — consumes the per-HUD `map_config.v<hud_version>.json` files 9.9b produces. Story 9.10 (PRD/architecture editorial pass for ROI+HSV pivot) — anchors its measured-accuracy citations to 9.9b's floors; can't run until 9.9b reports.
- **Cross-epic:** Story 1.13 in Epic 1. No cross-epic blocker; 1.13's `backlog` status is fine — it picks up 9.9b's deliverable when it eventually runs.
- **Sequencing constraint:** strict dependency order. The five-story dep chain (9.9c → 9.11 → 9.12 + 9.14 → optionally 9.13 → 9.9b) means 9.9b is the **last** story in the new-HUD initiative's code+data critical path. The 2026-05-15 correct-course's recommended sequence (`sprint-status.yaml:39` and proposal §5) was "9-9c → 9-11 (parallel) → 9-12 + 9-14 (parallel) → 9-13 → 9-9b" — match it.
- **Sprint fit:** **multi-sprint.** ~1–2 weeks of focused work per HUD version (3–5 iteration passes × ~½ day per pass × 1–2 days of slack for the smoke test + log writeup). Today's scope (v2 only): ~1.5 weeks dev-story duration. If v1 labeling appears: another 1.5 weeks for v1.
- **Branch off:** `main` for each HUD-version cohort PR (branch name `story-9-9b-v<hud_version>`). If multi-HUD rollout was chosen at kickoff, each cohort is its own branch off `main`; intermediate cohorts flip sprint-status `in-progress → review → ready-for-dev` (NOT `done`) on each PR cycle until the final cohort flips to `done`.

### Project structure notes

- **Naming:** `9-9b-iterative-zone-population-for-shipping-configs` continues the 9.9a / 9.9c suffix convention. Path: `_bmad-output/implementation-artifacts/9-9b-iterative-zone-population-for-shipping-configs.md`. Sprint-status key: `9-9b-iterative-zone-population-for-shipping-configs` (renamed from the original `9-9b-tool-8-fragment-hand-merge-and-config-regen` during the 2026-05-15 correct-course — see `sprint-status.yaml:182`). PR branch: `story-9-9b-v<hud_version>` (per-HUD-version cohort).
- **Zone-fragment commit location decision (AC9):** Option A (`.gitignore` exception) is the default — preserves 9.9c's path convention. Option B (committed config dir) is a 9.9c amendment route — requires explicit team sign-off + a follow-up code change to `wardentooling.py:flow_tool3` + `map_config_emitter` default. Document the chosen path in Change Log at dev-story kickoff.
- **Emitted-config commit decision:** independent sub-decision from AC9. Options: (i) commit the assembled `map_config.v<hud_version>.json` alongside the fragments (audit trail; downstream consumers can read it directly); (ii) leave it gitignored under `apps/tooling/output/map_configs/` (regenerable from fragments via emitter; lower commit churn). **Default (i)** if AC9 Option A — natural pairing. **Default (ii)** if AC9 Option B — fragments live in a committed config dir, assembled output stays in output/.
- **Per-HUD-version iteration partitioning:** each HUD version's iteration loop is independent. Cross-HUD work happens only at the `hud_version_detection` zone-picker mode (which compares frames across HUDs) and at the PRD-level "≥1 HUD config exists for V1.5" goal-setting (out of 9.9b's lane). Within 9.9b, treat each HUD version as a self-contained measurement campaign.
- **Iteration log committed alongside the data:** the iteration-log table at the bottom of Completion Notes is the **audit trail**. Every iteration row is permanent (not amended away as the next iteration starts); this is how the story documents convergence and floor history. Future Stephane-or-engineer looking at the v2 config a year from now reads the table to understand which zones changed when and why.
- **Slug normalization:** map folder names under `apps/tooling/output/labeled/v<hud>/` must match `^[a-z][a-z0-9_]*$` exactly (the schema's `patternProperties` regex). If the labeled dataset uses different casing or hyphens, normalize the folder names before 9.9b begins (a `mv` operation; document in Change Log).
- **HUD-version enum extension:** if a HUD version beyond `v1` / `v2` ever appears, the schema's `hud_version: enum` (currently `["v1", "v2"]`) must be extended **before** 9.9b's per-HUD manifest gets written for the new version. That extension is a schema-evolution change (out of 9.9b's lane); fold it into a separate small code-change story or amend 9.10's editorial pass. Manifest authoring (Task 2) for an unknown HUD version will fail at emit-time with a clean schema-validation error.

### References

- [Source: _bmad-output/sprint-change-proposal-2026-05-15.md](../sprint-change-proposal-2026-05-15.md) — full schema unification + tooling consolidation rationale; §4 covers Stories 9.9b/9.9c/9.10 and the new tools (9.11–9.14).
- [Source: _bmad-output/implementation-artifacts/9-9c-schema-unification.md](9-9c-schema-unification.md) — predecessor / contract-shape supplier. AC1 (schema), AC3 (fragment layout), AC4 (CLI shape), AC5 (`flow_tool3` retarget) define the contract surface 9.9b operates against.
- [Source: _bmad-output/implementation-artifacts/9-9a-schema-v2-and-map-config-generator.md](9-9a-schema-v2-and-map-config-generator.md) — earlier predecessor (now SUPERSEDED by 9.9c); preserves the original `_validate_against_schema` + atomic-refusal pattern carried forward by 9.9c.
- [Source: _bmad-output/sprint-status.yaml:182](../sprint-status.yaml#L182) — sprint-status entry for 9.9b with the 2026-05-15 mechanism-rewrite note (renamed + rewired to depend on 9.12/9.13/9.14).
- [Source: _bmad-output/sprint-status.yaml:184](../sprint-status.yaml#L184) — sprint-status entry for 9.9c (schema/emitter contract source).
- [Source: _bmad-output/sprint-status.yaml:185-188](../sprint-status.yaml#L185) — sprint-status entries for 9.11 / 9.12 / 9.13 / 9.14 (the four hard upstream dependencies).
- [Source: _bmad-output/sprint-status.yaml:71](../sprint-status.yaml#L71) — Story 1.13 entry (downstream consumer; anchor flipped 9.9a → 9.9c per the 2026-05-15 correct-course).
- [Source: _bmad-output/epics-and-stories.md](../epics-and-stories.md) — Epic 9 charter + Story 9.9 split section.
- [Source: contracts/map-config.schema.json](../../contracts/map-config.schema.json) — unified schema (post-9.9c). `$defs.Zone` shape; `patternProperties` slug regex; `hud_version` enum; `score_screen_duration_ms` integer constraint.
- [Source: apps/tooling/tools/map_config_emitter.py](../../apps/tooling/tools/map_config_emitter.py) — fragment-driven emitter (post-9.9c). The `--zones-dir` CLI + the per-HUD output filename convention.
- [Source: apps/tooling/wardentooling.py:215-271](../../apps/tooling/wardentooling.py#L215) — `flow_tool3` (CLI shim that 9.9c retargeted to `--zones-dir`).
- [Source: apps/tooling/output/labeled/v2.0/](../../apps/tooling/output/labeled) — labeled dataset (Tool 6, Story 9.5); the AC2 inventory target. Path is gitignored per `.gitignore:62-64`.
- [Source: prd.md:1042](../prd.md#L1042) — `REL-006` "Map identification accuracy ≥ 95% on a held-out test set" (the AC6 per-map floor anchor).
- [Source: prd.md:868-869](../prd.md#L868) — `mobile-AUTO-SLICE-002/003` (downstream mobile FRs that 9.9b's accuracy floors validate; the consumer rewrite is a separate post-V1 story).
- [Source: prd.md:955-956](../prd.md#L955) — `tooling-HASH-001/002` (legacy pHash framing; out of 9.9b's scope; flagged for Story 9.10 editorial pass).
- [Source: architecture.md:390-393](../architecture.md#L390) — Decision #2 (map_config.json runtime delivery), the architectural anchor that 9.9b's per-HUD output and 1.13's bundling decision implement.
- [Source: .gitignore:62-64](../../.gitignore#L62) — `apps/tooling/output/`, `apps/tooling/source/`, `apps/tooling/labeled/` all gitignored. AC9 Option A is one `.gitignore` exception (`!apps/tooling/output/zones/`); Option B moves the source-of-truth out of `output/` entirely.
- [Source: _bmad/bmm/config.yaml](../../_bmad/bmm/config.yaml) — `user_name: Stephane`, `project_name: Warden_monorepo`.
- Memory: [[feedback_two_pr_docs_execution]] (Two-PR pattern — main PR + post-merge follow-up); [[feedback_ac_checkbox_tighten]] (AC checkbox tighten — `[ ]` for post-merge-dependent ACs); [[project_warden_new_hud_labeler]] (new-HUD labeler initiative — Epic 9 schema-unification + tooling-consolidation context, including the 6-step operator workflow this story closes).

## Dev Agent Record

### Agent Model Used

_(populated at dev-story kickoff)_

### Debug Log References

_(populated per iteration pass; iteration log table goes here per AC7)_

### Completion Notes List

_(populated at dev-story finalization — final per-classifier floors, score-screen calibration sample, iteration log, AC9 decision record)_

### File List

_(populated at dev-story finalization — list of modified zone fragments, emitted configs, sprint-status, this story file, optional .gitignore exception)_

### Change Log

| Date       | Change                                                                                                       |
|------------|--------------------------------------------------------------------------------------------------------------|
| 2026-05-15 | Story created via /bmad-create-story (Stephane) — split-derived from the 2026-05-15 /bmad-correct-course that renamed/rewired 9.9b's mechanism (was: Tool-8 fragment hand-merge into config.yaml + map_config.json regen; now: iterative zone_picker → map_config_emitter → video_test/Tool 9 refit loop, no config.yaml touch). Initial spec at `ready-for-dev`. AC1–AC12 held `[ ]` per [[feedback_ac_checkbox_tighten]] — every AC's endpoint depends on either (a) upstream story completion (AC1), (b) empirical measurement not yet performed (AC2–AC9), or (c) post-merge admin (AC10–AC12). |
