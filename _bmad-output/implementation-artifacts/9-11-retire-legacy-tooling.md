# Story 9.11: Retire Legacy Tooling

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As **Stephane**,
I want **the 9 retired tool files/packages deleted in one atomic commit — along with their `wardentooling.py` registrations, their `.md` docs, and their tests — with the few shared primitives that surviving tools still need relocated to a durable home first**,
so that **`apps/tooling/tools/` mirrors the operator workflow with no incidental tools, dead code, or stale docs, and the surviving tools (Tool 6 labeler, Tool 9 ROI tester) plus the test suite stay green by construction.**

## Acceptance Criteria

> All ACs `[x]`. AC1–AC7 implemented + validated in the /bmad-dev-story 9.11 run; AC8/AC9 closed by the `story-9-11-postmerge` Two-PR follow-up (post-merge of `main` merge `aca0906`) per [[feedback_two_pr_docs_execution]].

- [x] **AC1 — Retire list deleted.** All 9 of the following are removed from the working tree (plus their sibling `.md` docs where they exist):
  1. `apps/tooling/tools/auto_roi_discoverer/` — entire package (9 modules: `__init__`, `__main__`, `app`, `discoverer`, `exclusions`, `export`, `loader`, `model`, `validator`) **+ sibling `apps/tooling/tools/auto_roi_discoverer.md`**
  2. `apps/tooling/tools/minimap_zone_selector/` — entire package (9 modules: `__init__`, `__main__`, `app`, `config_manager`, `data_loader`, `hsv_editor`, `stats_panel`, `validator`, `zone_model`) — no sibling `.md`
  3. `apps/tooling/tools/overlay_stack_analyzer.py` **+ sibling `apps/tooling/tools/overlay_stack_analyzer.md`**
  4. `apps/tooling/tools/game_detector.py`
  5. `apps/tooling/tools/black_screen_detector.py`
  6. `apps/tooling/tools/bsd_roi_debugger.py`
  7. `apps/tooling/tools/frame_labeler.py`
  8. `apps/tooling/tools/warden_analyzer.py`
  9. `apps/tooling/tools/points_state_detector.py`

  Verification: `git status` shows all 9 (plus the 2 `.md` siblings) deleted; `git ls-files apps/tooling/tools/ | grep -E 'auto_roi_discoverer|minimap_zone_selector|overlay_stack_analyzer|game_detector|black_screen_detector|bsd_roi_debugger|frame_labeler|warden_analyzer|points_state_detector'` returns zero.

- [x] **AC2 — Shared primitives relocated (scope-defining; do this BEFORE AC1's deletes).** The primitives that surviving tools depend on are moved behavior-preservingly into `apps/tooling/tools/common/` (D1 = `tools/common/`, confirmed), as a single source of truth (no duplication, no re-derivation):
  - `MAP_LABELS` + `LABEL_DISPLAY` ← currently ≈ `frame_labeler.py:23-56` (`MAP_LABELS` ≈ 23-39, `LABEL_DISPLAY` ≈ 41-56 — verify live; bare list + dict only, **no tkinter/PIL** must follow them) — the canonical 14-map source of truth, per [epics-and-stories.md:443](../epics-and-stories.md#L443) `tooling-LABEL-002`
  - `Rect` + `HsvBand` + `TARGET_CLASSES` ← currently `auto_roi_discoverer/model.py`
  - `band_inrange_ratio` + its **cross-module** closure ← `auto_roi_discoverer/validator.py` (`band_inrange_ratio` itself) **plus** `hsv_user_to_cv`, `tol_h_user_to_cv`, `tol_sv_user_to_cv` and the module constants `_H_CV_TO_USER`, `_SV_CV_TO_USER` from `auto_roi_discoverer/discoverer.py` (≈ lines 37-92 — verify live). The closure spans `discoverer.py`, not just `validator.py`. Do NOT drag `Candidate`/`comparison_classes`/`coverage_estimate`/`GameStateValidator` — `band_inrange_ratio` does not use them.
  - the labeled-dataset default-dir helper exposed as `_default_input_dir` ← `overlay_stack_analyzer.py` (≈ lines 49-58). **This helper is `__file__`-relative** (`dirname(__file__)/".."` → `apps/tooling/`). A literal copy into `tools/common/` is **behavior-changing** (one dir too shallow → wrong `tools/output/labeled`). "Behavior-preserving" here means **the returned absolute path must still resolve to `apps/tooling/output/labeled`** — add the extra `".."` for the new `tools/common/` depth (or re-anchor off a non-`__file__` base). Acceptance check: relocated helper returns the same absolute path the original did from `tools/`.

  `MAP_LABELS` remains exactly one definition repo-wide (no copy into Tool 6 and another into Tool 9). Relocated code is moved, not feature-rewritten — semantics identical (the `_default_input_dir` depth fix is the sole, mandated exception).

- [x] **AC3 — Survivor imports repointed; zero retired imports remain anywhere.** The surviving tools and the surviving test that import retired modules are repointed to the relocated `tools/common/...` symbols:
  - `apps/tooling/tools/video_timeline_labeler.py:35` (`from tools.frame_labeler import LABEL_DISPLAY, MAP_LABELS`)
  - `apps/tooling/tools/roi_detection_tester.py:50-57` (`auto_roi_discoverer.model`, `auto_roi_discoverer.validator`, `frame_labeler`, `overlay_stack_analyzer` imports)
  - `apps/tooling/tests/test_roi_detection_tester.py:23-24` (`auto_roi_discoverer.model`, `frame_labeler` imports)

  Note: surviving `roi_detection_tester.py` also carries **stale prose** naming retired modules — docstring/comment lines ≈ 6, 145, 368 (`auto_roi_discoverer.validator.band_inrange_ratio`, `tools.auto_roi_discoverer.model.Rect`). These must be scrubbed too (Task 3) or the verification grep is non-zero on comments alone.

  Verification: `grep -rn -E 'auto_roi_discoverer|minimap_zone_selector|overlay_stack_analyzer|game_detector|black_screen_detector|bsd_roi_debugger|frame_labeler|warden_analyzer|points_state_detector' apps/tooling --include='*.py'` returns **zero** matches in surviving files — code **and** docstrings/comments (all matches are in now-deleted files only).

- [x] **AC4 — `wardentooling.py` fully de-registered.** No string-search hit for any retired module name in `apps/tooling/wardentooling.py`; every flow-function, `_TOOL_MAP` entry, `choices_main` branch, `menu_main` handler, `menu_dev` handler, and `_reprompt_source` branch for a retired tool is removed. The TUI starts cleanly (`python wardentooling.py` import-loads with no error), the main + dev menus no longer list the retired tools, and a stale `.warden_last_run.json` pointing at a retired tool degrades gracefully — this is already satisfied by the existing `tool_key not in _TOOL_MAP` guard (≈ `wardentooling.py:708-710`, "Unknown tool … Skipping."); de-registered keys fall through it by construction, so this is a verify-only check, not new code.

- [x] **AC5 — Retired tests deleted; suite green.** Exactly `apps/tooling/tests/test_auto_roi_discoverer.py` and `apps/tooling/tests/test_overlay_stack_analyzer.py` are deleted (verified: no `test_minimap_zone_selector*`, `test_warden_analyzer*`, `test_frame_labeler*`, `test_game_detector*`, `test_black_screen_detector*`, `test_bsd_roi_debugger*`, or `test_points_state_detector*` files exist — nothing else to delete). `cd apps/tooling && uv run pytest` is green; final count == baseline count minus the **objectively pinned** case count of the 2 deleted files — capture both via `uv run pytest --collect-only -q tests/test_auto_roi_discoverer.py` and `… tests/test_overlay_stack_analyzer.py` (node-id count, not eyeballed totals) and record baseline + post in Completion Notes (9.9c's record had the apps/tooling suite at 168 green pre-merge — that is the expected baseline order of magnitude). Surviving suites `test_map_config_emitter.py`, `test_roi_detection_tester.py`, `test_video_timeline_labeler.py`, `conftest.py` show zero regressions.

- [x] **AC6 — Emitter survivor confirmed clean + cross-workspace test green.** `apps/tooling/tools/map_config_emitter.py` has zero imports of any retired module and does not read `config.yaml` (already true post-9.9c merge `9b9d4af` — verify; expect no patch needed, the AC4 caveat in the stub about "if 9.9c hasn't landed" is moot). `pnpm --filter tooling test` green from repo root.

- [x] **AC7 — `config.yaml` legacy block deleted (decision D2 = DELETE, Stephane 2026-05-16).** The legacy `minimap_identification` block in `apps/tooling/config/config.yaml` is **removed** (stub cites lines 87-907; live range verified ≈ 87-912 — dev re-confirms exact bounds before cutting). Justified: after retirement **no surviving tool reads it** (all readers — `game_detector`, `black_screen_detector`, `bsd_roi_debugger`, `points_state_detector`, `warden_analyzer`, `auto_roi_discoverer/__main__`, `minimap_zone_selector/__main__` — are in the retire list; the emitter stopped reading `config.yaml` in 9.9c); pre-production no-backward-compat posture makes deletion safe; git history preserves it. After removal, `config.yaml` must still parse (`python -c "import yaml; yaml.safe_load(open('apps/tooling/config/config.yaml'))"`). **Also report** (do NOT auto-act) whether `config.yaml` and `utils/config.py:load_config` are now *fully* orphaned (every `load_config` caller is retire-list) — surface as a candidate follow-up retirement in Completion Notes. `[ ]` because unimplemented (not decision-blocked).

- [x] **AC8 — Sprint-status lifecycle — [HELD].** `_bmad-output/sprint-status.yaml`: `9-11-retire-legacy-tooling` flows `ready-for-dev → in-progress → review → done`; `last_updated` bumped with a brief entry. `epic-9` stays `in-progress`. Downstream `9-12`/`9-13`/`9-14`/`9-9b` entries unchanged (they remain blocked on their own deps; 9.11 landing only removes the "don't import about-to-die modules" hazard). Held `[ ]` — `review → done` is post-merge.

- [x] **AC9 — Single-PR delivery + Two-PR follow-up — [HELD].** Per [[feedback_two_pr_docs_execution]]: branch `story-9-11-retire-legacy-tooling` off current `main` (which carries 9.9c `9b9d4af`). Single delivery; `gh` is unauthenticatable non-interactively → deliver as a local `git merge --no-ff story-9-11-retire-legacy-tooling → main` (per 9.9c Scope Adjustment #5 precedent). Title: `chore: retire legacy tooling (Story 9.11)`. Two-PR follow-up: branch `story-9-11-postmerge` off post-merge `main` flips sprint-status `review → done` + this story's `[HELD]` AC/Task boxes. Held `[ ]` — post-merge.

## Tasks / Subtasks

- [x] **Task 1: Pre-flight verification & dependency gate (AC: 1, 6)**
  - [x] Confirm upstream gate: `9-9c-schema-unification` is `done` in sprint-status (line ~186, merged `9b9d4af`). It is — proceed. (If it ever shows not-done, HALT: the emitter could still transitively need retired helpers.)
  - [x] Re-run the import-graph audit live (line numbers below are from create-story analysis and may have shifted): `grep -rn -E 'auto_roi_discoverer|minimap_zone_selector|overlay_stack_analyzer|game_detector|black_screen_detector|bsd_roi_debugger|frame_labeler|warden_analyzer|points_state_detector' apps/tooling --include='*.py'`. Confirm the ONLY surviving consumers are `video_timeline_labeler.py`, `roi_detection_tester.py`, `test_roi_detection_tester.py`, plus the retire-list files themselves (which all reference each other and die together).
  - [x] Record the pytest baseline: `cd apps/tooling && uv run pytest -q` → total passed count; pin the per-file delta basis with `uv run pytest --collect-only -q tests/test_auto_roi_discoverer.py` and `… tests/test_overlay_stack_analyzer.py` (node-id counts — the exact AC5 delta).

- [x] **Task 2: Relocate shared primitives into `tools/common/` (AC: 2)**
  - [x] Move the bare data structures VERBATIM: `MAP_LABELS` + `LABEL_DISPLAY` from `frame_labeler.py` (≈ `MAP_LABELS` 23-39, `LABEL_DISPLAY` 41-56 — verify live). Copy ONLY the list + dict; do **not** carry `frame_labeler`'s top-level `tkinter`/`PIL` imports — `common/labels.py` must stay GUI-free.
  - [x] Move VERBATIM: `Rect`, `HsvBand`, `TARGET_CLASSES` from `auto_roi_discoverer/model.py`.
  - [x] Move `band_inrange_ratio` **plus its cross-module closure**: from `auto_roi_discoverer/validator.py` take `band_inrange_ratio`; from `auto_roi_discoverer/discoverer.py` take `hsv_user_to_cv`, `tol_h_user_to_cv`, `tol_sv_user_to_cv` (≈ lines 71-92) and the module constants `_H_CV_TO_USER`, `_SV_CV_TO_USER` (≈ lines 37-38). `validator.py:28` does `from .discoverer import hsv_user_to_cv, tol_h_user_to_cv, tol_sv_user_to_cv` — so the closure is in `discoverer.py`, not `validator.py`. Do NOT drag `Candidate`/`comparison_classes`/`coverage_estimate`/`GameStateValidator`. After the move the relocated module must have **zero** `auto_roi_discoverer` imports.
  - [x] Move the `_default_input_dir` helper from `overlay_stack_analyzer.py` (≈ 49-58) **with the `__file__`-depth fix**: it currently does `dirname(__file__)/".."` to reach `apps/tooling/`; from `tools/common/` that needs an extra `".."` (or re-anchor off a non-`__file__` base). Add a unit assertion that the relocated helper returns the same absolute path (`apps/tooling/output/labeled`) the original returned from `tools/`. This is the ONE sanctioned non-verbatim change in this story.
  - [x] Place into `apps/tooling/tools/common/` (target package already exists: `__init__.py` + `video_player.py`). Suggested layout (dev finalizes names): `common/labels.py` (`MAP_LABELS`, `LABEL_DISPLAY` — GUI-free), `common/zones.py` (`Rect`, `HsvBand`, `TARGET_CLASSES`, `band_inrange_ratio` + the 3 conv helpers + 2 constants), `common/labeled_dataset.py` (the depth-fixed default-dir helper — consider a public `default_labeled_dir`).
  - [x] Keep `MAP_LABELS` as exactly ONE definition (single source of truth — no duplicate into Tool 6 / Tool 9).
  - [x] If the closure pulls numpy/opencv usage, preserve imports as-is (no new deps — numpy/opencv-python/pyyaml/stdlib already present per `apps/tooling/pyproject.toml`).

- [x] **Task 3: Repoint survivor + surviving-test imports (AC: 3)**
  - [x] `video_timeline_labeler.py:35`: `from tools.frame_labeler import LABEL_DISPLAY, MAP_LABELS` → import from the relocated `tools.common.labels`.
  - [x] `roi_detection_tester.py:50-57`: repoint the `auto_roi_discoverer.model` (`TARGET_CLASSES`, `HsvBand`, `Rect`), `auto_roi_discoverer.validator` (`band_inrange_ratio`), `frame_labeler` (`MAP_LABELS`), `overlay_stack_analyzer` (`_default_input_dir as _tool7_default_labeled`) imports to the relocated `tools.common.*` symbols. Preserve the `_tool7_default_labeled` local alias if it's referenced elsewhere in the file.
  - [x] `tests/test_roi_detection_tester.py:23-24`: repoint `auto_roi_discoverer.model` (`HsvBand`, `Rect`, `TARGET_CLASSES`) + `frame_labeler` (`MAP_LABELS`) imports to `tools.common.*`.
  - [x] Scrub stale prose in surviving `roi_detection_tester.py` so the AC3 grep is genuinely zero: docstring/comment lines ≈ 6, 145, 368 naming `auto_roi_discoverer.validator.band_inrange_ratio` / `tools.auto_roi_discoverer.model.Rect` → reword to the relocated `tools.common.*` names (verify live line numbers).
  - [x] Grep-verify zero retired-module references (imports **and** docstrings/comments) remain in any surviving `.py` (tools + tests).

- [x] **Task 4: Delete the 9 retire-list files/packages + `.md` siblings (AC: 1)**
  - [x] `git rm -r` the 9 entries in AC1, plus `auto_roi_discoverer.md` and `overlay_stack_analyzer.md`. Use `git rm` so deletions are staged.
  - [x] Confirm `git ls-files apps/tooling/tools/` no longer matches the retire-list regex.

- [x] **Task 5: Strip `wardentooling.py` registrations (AC: 4)**
  - [x] For EACH retired module name, grep `wardentooling.py` and remove every touchpoint. Create-story analysis found (line numbers indicative, re-verify live):
    - Tool 1 `game_detector`: section comment ~163; `flow_tool1()` ~167-185; `_TOOL_MAP` entry ~625; `_reprompt_source` branch ~645-649; `choices_main` ~733; `menu_main` handler ~751-761
    - Tool 2 `frame_labeler`: ~189; `flow_tool2()` ~193-207; `_TOOL_MAP` ~626; `_reprompt_source` ~650-654; `choices_main` ~734; `menu_main` ~763-773
    - Tool 5 `warden_analyzer`: ~282; `flow_tool5()` ~286-304; `_TOOL_MAP` ~629; `_reprompt_source` ~655-659; `choices_main` ~736; `menu_main` ~792-802
    - Tool 7 `overlay_stack_analyzer`: ~345; `flow_tool7()` ~349-415; `_TOOL_MAP` ~631; `_reprompt_source` ~669-672; `choices_main` ~738; `menu_main` ~821-836
    - **Tool 8 `auto_roi_discoverer`** (do NOT miss this — it is registered): section comment ~419; `flow_tool8()` ~423-458; `_TOOL_MAP` ~632; `_reprompt_source` ~673-675; `choices_main` ~739 (`"Tool 8 — Discover Game-State ROIs"`); `menu_main` handler ~838-853 (incl. `save_last_run("auto_roi_discoverer", …)`)
    - Dev menu `bsd_roi_debugger`: `flow_dev_roi_debugger()` ~534-555; `menu_dev` handler ~612-614
    - Dev menu `points_state_detector`: `flow_dev_points_detector()` ~558-573; `menu_dev` handler ~615-617
    - `black_screen_detector`: name-grep `wardentooling.py` — strip any reference if present (likely none; it was a library of the Tool 1 era).
  - [x] Scrub stale Tool-8 prose in **surviving** `wardentooling.py`: `flow_tool9`'s `--zones` prompt text (≈ line 478, "Tool 8 zones fragment … output/auto_rois/v*/discovered_zones.yaml") and the `_reprompt_source` comment (≈ 677, "consumes Tool 8's output") → reword so AC4's string-search is genuinely zero.
  - [x] Menu numbering: after Tool 8 removal `choices_main` jumps Tool 7 → Tool 9. **Leave the gap — do NOT renumber Tool 9** (renumbering would churn `save_last_run`/`_TOOL_MAP` keys for no benefit). Note this choice in Completion Notes.
  - [x] After stripping: `python -c "import wardentooling"` (from `apps/tooling/`) imports clean; launch the TUI far enough to confirm the main menu + dev submenu render without the retired entries and without exceptions.
  - [x] `.warden_last_run.json` edge case is verify-only: the existing `tool_key not in _TOOL_MAP` guard (≈ 708-710) already returns "Unknown tool … Skipping." for de-registered keys — confirm that guard still covers removed keys (it does by construction); no new code.

- [x] **Task 6: Delete retired tools' test files (AC: 5)**
  - [x] `git rm apps/tooling/tests/test_auto_roi_discoverer.py apps/tooling/tests/test_overlay_stack_analyzer.py`.
  - [x] Verify-before-not-deleting: confirm none of `test_minimap_zone_selector*`, `test_warden_analyzer*`, `test_frame_labeler*`, `test_game_detector*`, `test_black_screen_detector*`, `test_bsd_roi_debugger*`, `test_points_state_detector*` exist (create-story confirmed they do not).
  - [x] Check `conftest.py` + `fixtures/` for any fixture used ONLY by the 2 deleted test files; if a fixture is now dead and unused, remove it (keep anything shared by surviving suites — e.g. `fixtures/astera_expected.json` if still referenced).

- [x] **Task 7: Delete `config.yaml` legacy block + orphan report (AC: 7) — decision D2 = DELETE (Stephane 2026-05-16)**
  - [x] Re-confirm the live line range of the `minimap_identification` block in `apps/tooling/config/config.yaml` (stub: 87-907; create-story live: ≈87-912).
  - [x] Delete the block; ensure the YAML still parses (`python -c "import yaml; yaml.safe_load(open('apps/tooling/config/config.yaml'))"`).
  - [x] Report in Completion Notes whether ANY surviving code still calls `utils/config.py:load_config` / reads `config.yaml` post-retirement (create-story analysis: all `load_config` callers are retire-list). If fully orphaned, flag `config.yaml` + `utils/config.py` as a candidate follow-up retirement — do NOT delete them in this story.

- [x] **Task 8: Full validation (AC: 5, 6)**
  - [x] `cd apps/tooling && uv run pytest -q` → green; compute and record the count delta vs Task 1 baseline (== sum of cases in the 2 deleted files).
  - [x] `pnpm --filter tooling test` from repo root → green.
  - [x] Smoke: `python wardentooling.py` renders menus without retired entries; `python tools/video_timeline_labeler.py --help` and `python tools/roi_detection_tester.py --help` (or equivalent entrypoints) import-load cleanly (proves the relocation/repoint worked end-to-end).

- [x] **Task 9: PR + sprint-status flips + Two-PR follow-up (AC: 8, 9) — [HELD post-merge]**
  - [x] Branch `story-9-11-retire-legacy-tooling` off current `main` (verify `git log -1` shows `9b9d4af` 9.9c is an ancestor). Commit in reviewable chunks: (a) relocate primitives to `tools/common/`; (b) repoint survivor + test imports; (c) delete 9 retire-list entries + `.md` siblings; (d) strip `wardentooling.py`; (e) delete 2 test files; (f) config.yaml decision; (g) story file finalization (Dev Agent Record + File List + Change Log) + sprint-status `ready-for-dev → in-progress → review` flip.
  - [x] Deliver as a local `git merge --no-ff story-9-11-retire-legacy-tooling → main` (gh unauthenticatable non-interactively — 9.9c Scope Adjustment #5 precedent). Commit/PR title: `chore: retire legacy tooling (Story 9.11)`. Record the merge commit SHA + push range in Change Log as a Scope Adjustment.
  - [x] After merge: branch `story-9-11-postmerge` off post-merge `main`. Flip `_bmad-output/sprint-status.yaml` `9-11-retire-legacy-tooling: review → done`; bump `last_updated` with a brief merge entry; flip this story's `[HELD]` AC7/AC8/AC9 + Task 9 sub-boxes `[x]`; set Status `done`. Deliver the tiny follow-up as a second local `--no-ff` merge (`chore: Story 9.11 post-merge follow-up`). `epic-9` stays `in-progress`.

## Dev Notes

### Strategic context

Story 9.11 is the **tooling-consolidation cut** of the new-HUD detection initiative (Epic 9; see [[project_warden_new_hud_labeler]]). The 2026-05-15 correct-course ([sprint-change-proposal-2026-05-15.md:228-266](../sprint-change-proposal-2026-05-15.md)) decided the auto-suggest ROI layer (`auto_roi_discoverer`) never produced good-enough zones in practice — the manual picker wins — and that a pile of legacy/black-screen-era tools (`game_detector`, `black_screen_detector`, `bsd_roi_debugger`, `points_state_detector`, `warden_analyzer`, `frame_labeler`, `minimap_zone_selector`, `overlay_stack_analyzer`) are superseded by the new chain (Tool 6 labeler survives; `zone_picker` 9.12 absorbs the picker + variance signal; `in_match_detection` zones replace black-screen detection; Tool 9 ROI tester survives and is refit in 9.14). 9.11 deletes the dead set in one atomic PR so 9.12/9.13/9.14 are written against a clean tree.

**The stub under-scoped this.** Both the sprint-status stub and [epics-and-stories.md:2779-2782](../epics-and-stories.md#L2779) call it "~1 day mechanical deletion ... import sites are local to `apps/tooling/`, no cross-package imports." That cross-*workspace* claim is true, but **within `apps/tooling/` two surviving tools import retire-list modules** — the import-graph audit (done at create-story) is the load-bearing finding:

| Surviving consumer | Imports from retire-list | Fate |
|---|---|---|
| `roi_detection_tester.py` (Tool 9) | `auto_roi_discoverer.model` (`TARGET_CLASSES`,`HsvBand`,`Rect`), `auto_roi_discoverer.validator` (`band_inrange_ratio`), `frame_labeler` (`MAP_LABELS`), `overlay_stack_analyzer` (`_default_input_dir`) | survives; refit in **9.14** (lands *after* 9.11) |
| `video_timeline_labeler.py` (Tool 6) | `frame_labeler` (`LABEL_DISPLAY`, `MAP_LABELS`) | survives unchanged across Epic 9 (no refit story) |
| `tests/test_roi_detection_tester.py` | `auto_roi_discoverer.model`, `frame_labeler` | survives (Tool 9's suite) |

A naive 9-item delete reds Tool 6, Tool 9, and `test_roi_detection_tester.py`. Tool 9's refit (9.14) lands *after* 9.11 per the recommended sequence, and Tool 6 has **no** owning refit story — so 9.11 cannot defer this. **9.11 owns relocating the shared primitives to a surviving home (`tools/common/`) and repointing the survivors, then deleting.** This is the difference between a green and a red test suite at merge. Re-estimate: ~1.5-2 days (still fits-in-one-sprint), not the stub's ~1 day.

### Dependency / sequencing

- **Upstream gate satisfied:** `9-9c-schema-unification` is `done`, merged to `main` as `9b9d4af` (2026-05-16). 9.9c already decoupled `map_config_emitter.py` from `config.yaml` and from retired helpers ([9-9c story Dev Notes](9-9c-schema-unification.md), lines 139, 164, 173) — so AC4's stub caveat ("if 9.9c hasn't landed, patch the emitter") is moot; expect AC6 to be a pure verification.
- **Recommended order: 9.9c → 9.11 → 9.12 / 9.14 / 9.13** ([9-9c Dev Notes:225](9-9c-schema-unification.md), [proposal:264](../sprint-change-proposal-2026-05-15.md#L264)). 9.11 must land before 9.12/9.13/9.14 so the new tools are clean by construction.
- **Forward note for 9.14:** Tool 9's refit (9.14) must import `Rect`/`HsvBand`/`TARGET_CLASSES`/`band_inrange_ratio` from the **relocated `tools/common/`** location 9.11 creates — not from `auto_roi_discoverer` (gone). Likewise 9.12 `zone_picker` reuses `image_inspector/` + folds the `overlay_stack_analyzer` variance signal in-tool; it must not import the deleted `overlay_stack_analyzer`.
- **Downstream entries untouched:** 9.12/9.13/9.14/9.9b stay at their current sprint-status states; 9.9b stays `ready-for-dev` (still blocked on 9.11/9.12/9.13/9.14).

### Key code patterns / anti-patterns

- **Move, don't rewrite.** Relocated primitives are `git mv`-spirit moves: identical code, new module path. Do NOT "improve" `band_inrange_ratio`, re-type the dataclasses, or re-list `MAP_LABELS`. Behavior parity is the bar; `test_roi_detection_tester.py` + `test_video_timeline_labeler.py` passing unchanged is the proof.
- **Single source of truth for `MAP_LABELS`.** It is the canonical 14-map list ([epics-and-stories.md:443](../epics-and-stories.md#L443)). Exactly one definition post-move. Duplicating it into Tool 6 and Tool 9 is the disaster to avoid.
- **No new dependencies.** `apps/tooling/pyproject.toml`: numpy / opencv-python / pyyaml / stdlib + `pytest>=8.0` (dev). Relocation introduces none.
- **Atomic deletion discipline.** One branch, one delivery. Relocation + repoint + deletes ship together so `main` is never in a state where survivors are broken.
- **`git rm` not filesystem delete** — keep deletions staged and reviewable; git history preserves the retired code (the safety net the no-backward-compat posture relies on).
- **Don't widen scope.** `config.yaml` may turn out fully orphaned (Task 7) — *report it*, do not also delete `config.yaml`/`utils/config.py` in this story. Scope is the 9 tools + their wiring + the legacy `minimap_identification` block.

### Create-time decisions (surface to Stephane; defaults baked in)

- **D1 — Relocation target.** Default = `apps/tooling/tools/common/` (package already exists; `zone_picker` 9.12 also reuses `common/`). Alternative considered & rejected: inline into each survivor (duplicates `MAP_LABELS`, drift risk). This default is engineering-forced (Tool 6 has no other owner; Tool 9 refit lands later) and is baked into AC2/Task 2 — flag only if Stephane wants a different module home.
- **D2 — `config.yaml` `minimap_identification` block (AC7). RESOLVED 2026-05-16 (Stephane, at create-story): DELETE.** No surviving reader post-retirement; pre-production no-backward-compat; git preserves. AC7/Task 7 are now firm-delete (not decision-blocked); they stay `[ ]` only because unimplemented.

### Testing standards

- Test runner: `cd apps/tooling && uv run pytest` (pytest auto-discovers `tests/`; no `pytest.ini`/`setup.cfg`; config is `apps/tooling/pyproject.toml`). Cross-workspace: `pnpm --filter tooling test` from repo root.
- No GUI/Tk testing (Tool 6/8 precedent). The retirement's correctness test = surviving suites stay green after relocate+repoint+delete, with the count dropping by exactly the deleted files' case count.
- Surviving test inventory after this story: `test_map_config_emitter.py`, `test_roi_detection_tester.py`, `test_video_timeline_labeler.py`, `conftest.py` (+ `fixtures/`).

### Project Structure Notes

- Retire-list test coverage reality (verified): only `test_auto_roi_discoverer.py` + `test_overlay_stack_analyzer.py` exist for retired tools; the other 7 retired tools have no tests. AC5's "verify before delete" resolves to "delete these 2, confirm nothing else matches."
- `config.yaml` is 932 lines; `minimap_identification` block ≈ 87-912 (stub said 87-907 — dev re-confirms live).
- Branch/delivery follows the 9.9c precedent exactly: fresh branch off `main`, single delivery via local `--no-ff` merge (gh unauthenticatable non-interactively), Two-PR follow-up for the `review → done` flip ([[feedback_two_pr_docs_execution]]).
- AC checkbox convention per [[feedback_ac_checkbox_tighten]]: post-merge / decision-pending ACs tagged `[HELD]`, all `[ ]` at create time.

### References

- [sprint-change-proposal-2026-05-15.md:228-266](../sprint-change-proposal-2026-05-15.md) — canonical 9.11 spec (retire list, ACs skeleton, deferred config.yaml decision, sequencing)
- [epics-and-stories.md:2779-2782](../epics-and-stories.md#L2779) — Epic 9 charter 9.11 summary; [:443](../epics-and-stories.md#L443) `tooling-LABEL-002` (MAP_LABELS source of truth)
- [9-9c-schema-unification.md](9-9c-schema-unification.md) — predecessor (done, `9b9d4af`): emitter↔config.yaml decoupling (Dev Notes:139,164,173), sequencing constraint (:225), Two-PR + `--no-ff` delivery precedent (Task 7 Scope Adjustments #4/#5)
- sprint-status.yaml lines 186 (9.9c done), 187 (9.11 stub), 188-190 (9.12/9.13/9.14 deps)
- Memory: [[feedback_two_pr_docs_execution]], [[feedback_ac_checkbox_tighten]], [[project_warden_new_hud_labeler]]

## Dev Agent Record

### Agent Model Used

Amelia (dev-story), claude-opus-4-7[1m] — /bmad-dev-story 9.11, 2026-05-16.

### Debug Log References

- Pytest baseline (Task 1): `cd apps/tooling && uv run pytest -q` → **168 passed**. Per-file delta basis pinned via `pytest --collect-only -q`: `test_auto_roi_discoverer.py` = **30**, `test_overlay_stack_analyzer.py` = **33** (total 63).
- Post-implementation (Task 8): `uv run pytest -q` → **108 passed**; `pnpm --filter tooling test` → **108 passed**.
- Smoke: `python tools/roi_detection_tester.py --help` + `python tools/video_timeline_labeler.py --help` render cleanly under `PYTHONUTF8=1` (argparse builds → relocated `tools.common.*` imports resolve end-to-end). Note: without `PYTHONUTF8=1` both `--help` calls raise `UnicodeEncodeError` on the `→`/`←` glyphs in their help text — a **pre-existing Windows cp1252 console limitation**, not a Story 9.11 regression (the module imports/runs fine; 33 `test_roi_detection_tester` cases pass). `python -c "import wardentooling"` import-loads clean; main menu = `[Tool 3, Tool 6, Tool 9, Dev Tools, Quit]`, dev menu = `[Image Inspector, ← Back]` — zero retired entries; 0 retired-module tokens in `wardentooling.py`.

### Completion Notes List

- **AC5 delta accounting (exact):** baseline 168 − 30 (`test_auto_roi_discoverer.py`) − 33 (`test_overlay_stack_analyzer.py`) = 105 net deletions; **+3** from the mandated Task 2 depth-fix guard `tests/test_common_labeled_dataset.py` = **108 final**. The "−63 deleted" half of AC5 is exactly met; the +3 is the Task-2-sanctioned addition (the sole non-verbatim change in the story has its own regression guard), not test inflation.
- **AC2 relocation (single source of truth):** created `tools/common/labels.py` (`MAP_LABELS`+`LABEL_DISPLAY`, verbatim, GUI-free — no tkinter/PIL), `tools/common/zones.py` (`Rect`/`HsvBand`/`TARGET_CLASSES` + `band_inrange_ratio` + its cross-module closure `hsv_user_to_cv`/`tol_h_user_to_cv`/`tol_sv_user_to_cv` + `_H_CV_TO_USER`/`_SV_CV_TO_USER`, verbatim), `tools/common/labeled_dataset.py` (`default_labeled_dir` + `_default_input_dir` alias). The `_default_input_dir` depth-fix (extra `".."` for the deeper `tools/common/` location) is the **sole sanctioned non-verbatim change**; `test_common_labeled_dataset.py` asserts the resolved path is still `apps/tooling/output/labeled`. `MAP_LABELS` is exactly one definition repo-wide.
- **AC3/AC4 grep genuinely zero:** the relocation provenance docstrings/comments in the 3 new `common/` modules + `test_common_labeled_dataset.py` were reworded to avoid the literal retired-module-name tokens (referencing "Story 9.11" / tool-numbers; exact provenance lives in git history + this File List) — otherwise AC3's mechanical `--include='*.py'` grep would be non-zero on the new surviving files. Same for `wardentooling.py` REMOVED-tombstone comments and `video_timeline_labeler.py:43`'s stale `frame_labeler.py` comment. Final tree-wide grep: **zero** matches in all surviving `.py` (code + docstrings + comments).
- **AC4 menu numbering (E2 decision honored):** Tools 1/2/5/7/8 removed; surviving `_TOOL_MAP`/`choices_main` left non-contiguous (Tool 3 → Tool 6 → Tool 9). Tool 9's key/label/number preserved — no `save_last_run` churn. `.warden_last_run.json` pointing at a de-registered key still degrades via the existing `tool_key not in _TOOL_MAP` guard (verify-only, unchanged).
- **Same-file orphan cleanup (consequence of Task 5, not scope-widening):** removing the Tool 2 + Dev-ROI-Debugger flows orphaned `import re`, `_EXCLUDED_DIRS`, and `browse_directory()` inside `wardentooling.py` (zero remaining references, repo-wide). Removed all three (litter from this task's own edits; not a reach into other files). No lint gate exists (`pnpm --filter tooling test` == `uv run pytest`).
- **AC7 orphan report (do-not-act, surfaced per Task 7):** after retirement, **`apps/tooling/utils/config.py` (incl. `load_config`) and `apps/tooling/config/config.yaml` are FULLY ORPHANED** — `load_config` has zero callers in any surviving tracked `.py`; no surviving module imports `utils.config`; all surviving `config.yaml` string-hits are negative-prose ("does NOT read config.yaml"). **Candidate follow-up retirement** (a future story may delete `utils/config.py` + `config.yaml` + the now-empty `tests/fixtures/`). NOT deleted here per the story's "don't widen scope" anti-pattern. The `minimap_identification` block was lines **87–912** (826 lines) — confirmed live before cutting; `config.yaml` still parses (`yaml.safe_load` OK), top-level keys intact.
- **Extra orphan cleanup:** `tests/fixtures/astera_expected.json` (a BSD/black-screen-detector fixture, commit `1e3dc7b`) had zero references repo-wide post-retirement — removed per Task 6 ("remove dead unused fixtures"); `tests/fixtures/` is now empty (git untracks empty dirs). `conftest.py` has no fixtures (sys.path shim only) — nothing to prune there.
- **AC6 verify-only:** `map_config_emitter.py` imports only stdlib + `jsonschema`; zero retired imports; does not read `config.yaml` (already true post-9.9c `9b9d4af`) — no patch needed, exactly as the story predicted.

### File List

**Added**
- `apps/tooling/tools/common/labels.py`
- `apps/tooling/tools/common/zones.py`
- `apps/tooling/tools/common/labeled_dataset.py`
- `apps/tooling/tests/test_common_labeled_dataset.py`

**Modified**
- `apps/tooling/tools/video_timeline_labeler.py` (repoint import → `tools.common.labels`; scrub stale `frame_labeler.py` comment)
- `apps/tooling/tools/roi_detection_tester.py` (repoint 4 imports → `tools.common.*`; scrub 3 stale `auto_roi_discoverer` docstring/comment refs)
- `apps/tooling/tests/test_roi_detection_tester.py` (repoint imports → `tools.common.*`)
- `apps/tooling/wardentooling.py` (de-register Tools 1/2/5/7/8 + Dev ROI Debugger + Dev Points Detector; strip orphaned `import re`, `_EXCLUDED_DIRS`, `browse_directory`; scrub stale Tool-8 prose)
- `apps/tooling/config/config.yaml` (delete `minimap_identification` block, lines 87–912)
- `_bmad-output/implementation-artifacts/9-11-retire-legacy-tooling.md` (Dev Agent Record, File List, Change Log, AC/Task checkboxes, Status)
- `_bmad-output/sprint-status.yaml` (`9-11` `ready-for-dev → in-progress → review`; header `last_updated`)

**Deleted**
- `apps/tooling/tools/auto_roi_discoverer/` (9 modules: `__init__`, `__main__`, `app`, `discoverer`, `exclusions`, `export`, `loader`, `model`, `validator`) + `apps/tooling/tools/auto_roi_discoverer.md`
- `apps/tooling/tools/minimap_zone_selector/` (9 modules: `__init__`, `__main__`, `app`, `config_manager`, `data_loader`, `hsv_editor`, `stats_panel`, `validator`, `zone_model`)
- `apps/tooling/tools/overlay_stack_analyzer.py` + `apps/tooling/tools/overlay_stack_analyzer.md`
- `apps/tooling/tools/game_detector.py`
- `apps/tooling/tools/black_screen_detector.py`
- `apps/tooling/tools/bsd_roi_debugger.py`
- `apps/tooling/tools/frame_labeler.py`
- `apps/tooling/tools/warden_analyzer.py`
- `apps/tooling/tools/points_state_detector.py`
- `apps/tooling/tests/test_auto_roi_discoverer.py`
- `apps/tooling/tests/test_overlay_stack_analyzer.py`
- `apps/tooling/tests/fixtures/astera_expected.json`

## Change Log

| Date | Change | Author |
|---|---|---|
| 2026-05-16 | Story created via /bmad-create-story (Stephane). Ultimate context engine analysis: import-graph audit surfaced that the stub's "pure mechanical ~1-day deletion / no cross-package imports" framing under-scoped the work — surviving Tool 6 + Tool 9 (+ Tool 9's test) import retire-list modules, so AC2/AC3 add a mandatory relocate-to-`tools/common/` + repoint phase before deletion. 9 ACs, 9 Tasks. Upstream gate 9.9c confirmed `done` (`9b9d4af`). Create-time decisions resolved by Stephane: **D1** relocation target = `tools/common/` (confirmed); **D2** config.yaml `minimap_identification` block = **DELETE** (AC7/Task 7 made firm-delete). Status → ready-for-dev. | Bob (SM) |
| 2026-05-16 | Adversarial story-quality validation (checklist.md, fresh-context reviewer) — all findings applied: **C1** Task 5 was missing Tool 8 (`auto_roi_discoverer`) wardentooling registration (would fail AC3/AC4) — added; **C2** `_default_input_dir` is `__file__`-relative, verbatim move silently corrupts the path — AC2/Task 2 now mandate the depth fix as the sole sanctioned non-verbatim change; **C3** `band_inrange_ratio` closure spans `discoverer.py` (3 conv helpers + 2 constants) not just `validator.py` — made explicit; **E1** AC3/AC4 grep is non-zero on surviving stale Tool-8 docstrings/prompts — added scrub subtasks + verification now covers comments; **E2** menu-renumber decision (leave gap); **E3** AC5 delta pinned via `pytest --collect-only`; **E4** AC2 line refs corrected (`frame_labeler` ≈23-56); **N1** `common/labels.py` GUI-free; **N2** `.warden_last_run` edge case downgraded to verify-only (existing `_TOOL_MAP` guard ~708). Core thesis independently verified correct against live tree. | Bob (SM) |
| 2026-05-16 | **Post-merge Two-PR follow-up** (`story-9-11-postmerge`, Amelia). Main delivery landed on `main` via local `git merge --no-ff story-9-11-retire-legacy-tooling` → merge commit **`aca0906`** (41 files, +555/−9720; 7 chunked commits `19b3ec1`→`f6dbbcb`). Post-merge regression on `main` green: apps/tooling pytest **108 passed**, `pnpm --filter tooling test` **108 passed**. This follow-up flips sprint-status `9-11` `review → done`, Status `review → done`, AC8/AC9 + Task 9 sub-boxes `[x]`; delivered as a second local `--no-ff` merge `chore: Story 9.11 post-merge follow-up`. epic-9 stays `in-progress`; 9.12/9.13/9.14/9.9b unchanged. Story 9.11 COMPLETE. | Amelia (Dev) |
| 2026-05-16 | **Adversarial code review** (/bmad-code-review, 3 parallel layers: Blind Hunter / Edge Case Hunter / Acceptance Auditor; diff `19b3ec1~1..f6dbbcb`). Acceptance Auditor: **zero AC violations** — AC1–AC9 independently verified spec-faithful against merged tree. Blind+Edge: relocation byte-for-byte verbatim, no dangling imports, `wardentooling.py` symmetric, `config.yaml`/Python parse-clean (108/108). 4 dismissed as noise. **2 surviving findings** (1 decision-needed, 1 patch) recorded below. Post-merge — any fix is a new follow-up. | Code Review |

| 2026-05-16 | /bmad-dev-story 9.11 (Amelia). Tasks 1–8 complete; AC1–AC7 `[x]`. Relocated `MAP_LABELS`/`LABEL_DISPLAY` + `Rect`/`HsvBand`/`TARGET_CLASSES` + `band_inrange_ratio`+closure + the depth-fixed labeled-dir helper into `tools/common/{labels,zones,labeled_dataset}.py` (verbatim except the one sanctioned `_default_input_dir` depth fix, guarded by new `test_common_labeled_dataset.py`); repointed Tool 6 + Tool 9 + Tool 9's test; scrubbed all stale retired-module prose (tree-wide AC3 grep = 0 in surviving `.py`); `git rm` the 9 retire-list entries + 2 `.md` siblings + 2 retired test files + the orphaned `astera_expected.json` BSD fixture; fully de-registered Tools 1/2/5/7/8 + 2 Dev flows from `wardentooling.py` (+ removed same-file orphans `import re`/`_EXCLUDED_DIRS`/`browse_directory`); deleted `config.yaml` `minimap_identification` block (lines 87–912; YAML still parses). Pytest 168 → **108** (−63 deleted [30+33] +3 mandated depth-fix guard); `pnpm --filter tooling test` 108 green; smoke OK. **AC7 orphan report:** `utils/config.py`+`config.yaml` now FULLY ORPHANED → flagged as candidate follow-up retirement, NOT deleted (don't-widen-scope). Status `ready-for-dev → review`; sprint-status `ready-for-dev → in-progress → review`. AC8/AC9 + Task 9 `[ ]`/`[HELD]` — `review → done` + post-merge follow-up land via `story-9-11-postmerge` per [[feedback_two_pr_docs_execution]]. epic-9 stays `in-progress`. | Amelia (Dev) |

## Review Findings

_Adversarial code review 2026-05-16 (/bmad-code-review). Diff `19b3ec1~1..f6dbbcb`. Acceptance Auditor: zero AC violations. 4 findings dismissed as noise. Story was already `done`/merged (`aca0906`) at review time — any remediation is a NEW post-merge follow-up, not a re-open of 9.11._

- [x] [Review][Defer] **Tool 9 blank-`--zones` path dead-ends at deleted Tool 8** [apps/tooling/tools/roi_detection_tester.py:986-987; apps/tooling/wardentooling.py:272-273] — `roi_detection_tester.py:986-987` errors with `"No --zones provided and no v*/discovered_zones.yaml under {root} — run Tool 8 first."` and `wardentooling.py:272-273`'s Tool 9 prompt still advertises `[blank = newest output/auto_rois/v*/discovered_zones.yaml]`. Tool 8 (`auto_roi_discoverer`) was deleted by *this* story, so the default path is now a guaranteed error whose remediation references a tool that no longer exists and can't be launched. Not a crash; stale/misleading UX in a surviving tool. AC3's prose-scrub grep targeted retired *module/import* names, not the `"Tool 8"` user-facing string, so it slipped the gate. **Deferred to Story 9.14** (2026-05-16, Stephane): _Tool-9's entire input-resolution surface (incl. this default path + error text) is rewritten wholesale by the 9.14 refit; scrubbing it now is throwaway work._
- [x] [Review][Patch] **`common/zones.py` provenance docstring over-claims "byte-for-byte / verbatim"** [apps/tooling/tools/common/zones.py:1-16] — the relocation-provenance docstring asserted the move is *"byte-for-byte identical … verbatim"*, but the relocated `TARGET_CLASSES` block correctly dropped one now-stale Tool-8 comment line (`# (Tool 8 *also* exposes each loaded per-map cell…)`). Code is verbatim; only a defensibly-removed stale comment changed. **FIXED 2026-05-16:** removed the unqualified "verbatim"; docstring now states code/behaviour is byte-for-byte identical and explicitly names the one dropped stale Tool-8 comment line as the sole move-time edit.
