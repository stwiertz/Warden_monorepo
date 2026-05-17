# Deferred Work

Cross-story register of items deliberately deferred — pre-existing issues, out-of-scope findings, and items the team consciously decided to address later.

Each entry: bullet with the finding + brief reason.

---

## Deferred from: code review of 9-13-video-detection-tester (2026-05-17)

- **Per-map empty `zones` among otherwise-populated maps is not individually surfaced** (`apps/tooling/tools/video_test.py:309-334` — `_load_config`) — AC8 only mandates a per-classifier global note (`minimap_identification.maps unpopulated — ...` fires only when *zero* maps are populated). A config with map A populated and map B `"zones": []` emits no note about B; B simply never appears in scores — a misauthored single empty map among many is invisible. Tool 9's precedent is matched (per-classifier granularity), so this is hardening beyond AC8, not a spec violation. Fold into Story 9.9b's iterative zone-population loop (which will repeatedly emit/test partially-populated configs and is the natural place a per-map coverage report earns its keep) rather than reopen 9.13.

---

## Deferred from: code review of 9-9c-schema-unification (2026-05-16, second pass)

- **Residual boundary-coverage gaps in the rewritten pytest suite** (`apps/tooling/tests/test_map_config_emitter.py`) — Even after the 2026-05-15 first pass added P5–P11 (slug-regex, boolean-`weight_override`, extra-unknown-field, parametrized missing-key), no test exercises exact inclusive schema bounds (`Hsv.h_center` 0 and 360, `h_tol` 180, `s/v_center`/`tol` 100, `Zone.weight` 0), negative `weight`, zero-map `minimap_identification.maps: {}`, or an empty-object `{}` fragment crossing the assemble→validate boundary. AC8's per-bucket case-count floors are met and verified, so these are hardening beyond spec — an off-by-one at an inclusive bound would currently pass CI. Fold into Story 9.14 (Tool 9 refit for the unified schema), which re-exercises the same schema surface, rather than reopen 9.9c.

---

## Deferred from: code review of 9-9c-schema-unification (2026-05-15)

- **`emit()` write is not crash-atomic — partial file possible on mid-`json.dump` kill** (`apps/tooling/tools/map_config_emitter.py:132-135`) — AC2's "atomic refusal" guarantees validation-before-write only, not crash-resistance. The pattern is inherited verbatim from 9.9a. Standard fix: write to a sibling `.tmp` file then `os.replace()`. Defer until either (a) a real crash-during-emit incident surfaces, or (b) the 9.9b iteration loop accumulates enough re-emits that mid-write crashes become statistically likely.
- **Existing `map_config.<hud>.json` silently overwritten on re-emit** (`apps/tooling/tools/map_config_emitter.py:133-135`) — No `--force` / `--backup` / `--no-overwrite` flag. Story 9.9b's iteration loop (zone_picker → emitter → video_test → adjust → repeat) actually wants overwrite-by-default, so this isn't a bug today — but a `--backup` opt-in would let an operator preserve a known-good baseline before testing a new zone set. Revisit at 9.9b create-story time.
- **Filename-from-`hud_version` tight coupling to enum-extensibility** (`apps/tooling/tools/map_config_emitter.py:133`) — Today's enum (`v1`, `v2`) has no path-traversal characters. A future enum extension to `"v2.1"` or `"v2/beta"` would create subdirectories in `--output-dir`. Flag at the schema-evolution checkpoint (whenever `hud_version` enum is next extended) or pre-emptively extend `hud_version`'s schema with a `pattern: "^v[0-9]+$"` constraint.

---

## Deferred from: code review of 9-7-auto-roi-discoverer-tool-8 + 9-8-roi-detection-tester-tool-9 (2026-05-14)

- **HSV bands fire on grayscale/white pixels** (`apps/tooling/tools/auto_roi_discoverer/validator.py:82` — `band_inrange_ratio`; also exercised via `apps/tooling/tools/roi_detection_tester.py:289+` zone-fire path). Saturation=0 makes hue mathematically undefined but OpenCV returns hue=0, so any band centred near hue=0 with a wide `s_tol` (`s_tol ≥ s_center` pushes lower bound ≤ 0) matches pure white/gray pixels. Concept-level limitation of HSV-band detection, not specific to this work; would need either a saturation floor in the band (`s_lo = max(s_lo, MIN_S)`) or a separate gray-pixel exclusion in the discoverer to address. Defer to a future tuning pass once the user accumulates real "false-fire on gray HUD elements" examples from Tool 9 reports.

---

## Deferred from: code review of 9-5-video-timeline-labeler-tool-6 (2026-05-10)

- **Multiple `tk.Tk()` roots per process (picker → HUD prompt → player)** (`apps/tooling/tools/video_timeline_labeler.py`) — Blind Hunter flagged this as undefined-behavior risk (fonts, `_default_root`, image refs). A single-boot-root refactor was attempted on 2026-05-10 (Toplevel of a withdrawn root + `transient()`) but **reverted on 2026-05-12**: that exact combination renders the HUD-version prompt invisible/behind on Windows — the same regression the dev agent already hit and fixed on 2026-05-09. The roots are created and destroyed strictly sequentially (never overlapping), which is fine in practice. Revisit only if a concrete cross-root bug surfaces; the empirical Windows-visibility constraint trumps the theoretical concern.
- ~~**`_default_output_dir` resolves four levels above `tools/`**~~ — **RESOLVED 2026-05-12.** Changed in both `apps/tooling/tools/video_timeline_labeler.py` (`_default_output_dir`) and `apps/tooling/tools/overlay_stack_analyzer.py` (`_default_input_dir`/`_default_output_dir`) to resolve **one** level up from `tools/` → `apps/tooling/output/{labeled,overlay_stacks}/` (the tooling app root, which is already gitignored via `.gitignore` `apps/tooling/output/` + `apps/tooling/.gitignore`). The two tools' path math stays in lockstep (`Tool7._default_input_dir() == Tool6._default_output_dir()`). Tool docs (`*.md`) and argparse help updated to match.
- **`_session_counts` rollback corruption on partial-undo failure** (`apps/tooling/tools/video_timeline_labeler.py:656-664`) — if AV/OneDrive races `_undo`'s `os.remove`, returning False, the per-class count stays high and overstates the dataset. Edge-case dataset-accounting drift; not user-visible in the typical session.
- **`glob.glob` UnicodeDecodeError on non-UTF8 filenames** (`apps/tooling/tools/video_timeline_labeler.py:107-113`) — Windows default codepage on Stephane's machine doesn't trigger this; only relevant if the output dir grows pre-existing non-UTF8 PNG names.
- **`_prompt_hud_version` raises TclError in headless environment** (`apps/tooling/tools/video_timeline_labeler.py:790-793`) — Tk-based GUI tool; SSH/headless use is out of scope per Dev Notes ("No GUI testing").
- **Pillow declared as transitive dep only (via `imagehash` → `pillow v12.2.0`)** — works today; declaring `pillow>=10` directly in `pyproject.toml` would be belt-and-suspenders insurance against `imagehash` ever dropping the dep. Revisit on the next dependency audit.

---

## Deferred from: code review of 1-1-pre-prd-performance-spike-ar-spike (2026-05-09)

- **`clearCheckpoint` doesn't delete `events` / `gameSegments` / `mapIdentifications` / `perf002` MMKV keys** — pre-existing tech debt (`apps/mobile/src/features/video-processing/processingPipeline.ts:104-106`). Only the `stage` key is cleared on a successful run; the per-stage data keys leak across sessions. This story extends the pattern (adds `perf002`) but does not cause it. Defer to a dedicated MMKV-cleanup pass.
- **Per-stage `__perfMark` labels embed unbounded counts** — `keyframes_done_count=${keyframes.length}` etc. produce a different MMKV key per run, defeating cross-run aggregation. Design choice for the spike scaffolding; Story 1.1.1 may want stable keys + sidecar count fields when running real measurement workloads.
- **`[PERF-009]` log only emitted when detection runs this invocation** — `if (!detectionDone)` guard skips PERF-009 on resumed sessions. Story 1.1.1's measurement is cold-launch with cleared MMKV per spec, so this won't bite the actual measurement, but a researcher comparing partial-runs would notice a gap.
- **Base64 round-trip + `Uint8ClampedArray(buffer)` copy = ~2-3× memory per frame in `loadFrameFromPath`** — `react-native-fast-opencv` only exposes `base64ToMat`, so the JPEG must be string-base64 in JS before the JSI bounce. Plus `Uint8ClampedArray(uint8array)` constructor copies. Story 1.1.1's measurement to assess whether the cost is V1-acceptable; if not, escalate to lib upstream or alternate decode path.

---

## Deferred from: code review of 0-1-conduct-per-story-conflict-audit-for-sprint-2-5-in-flight-mobile-work (2026-05-09)

- **AC 11 verbatim sentence not actually verbatim across all artifacts** — `_bmad-output/sprint-plan.md:1100` paraphrases the gate-block sentence (uses `Per Decision #ES-3, Stories 0.1 → 0.2 must close before any Sprint 3 story merges to main`) instead of the AC11-mandated verbatim text. AC 11 only binds the audit file (which does match exactly); sprint plan is reference text. Defer until next sprint-plan touch.
- **Scope-creep: PR #1 bundled unrelated docs work outside Story 0.1's declared File List** — Story 0.1's File List names 3 files; PR diff touches 7 (added: implementation-readiness-report-2026-05-09.md, sprint-plan.md; modified: architecture.md, epics-and-stories.md). Already shipped — flag for sprint retro / process learning, not corrective action.
- **Epics-and-stories file's status divergence on 7.4 / 7.5 persists post-PR** — `_bmad-output/epics-and-stories.md` Epic 0 Implementation Notes still claims 7.4 = `ready-for-dev` (legacy file says `done`) and 7.5 = `ready-for-dev` (legacy file says `in-progress`). The audit calls this stale but ships it stale. Story 0.2 owns the disposition tags on legacy files; epics-file status fixup belongs to a separate cleanup pass.
- **Story 2.7 CASCADE claim not grep-verified against `database.ts`** — Audit row for 2.7 asserts ON DELETE CASCADE for `map_segments` / `clip_exports` / `audio_comments` without a direct grep against `apps/mobile/src/shared/services/database.ts`. Story 0.1 AC explicitly delegates verification to Stephane's manual review step, so this is process-correct — but worth noting if anyone later needs the CASCADE evidence.
- **Audit Rule A negative-find evidence (zero `IAP` / `free-tier` / `cloud-encode` hits) not recorded in Debug Log References** — Story 0.1 Dev Notes describe the trigger-word search as the method; the Debug Log records "read fully" but no grep evidence. Process artifact (would strengthen reviewer-skepticism counter-evidence on a future audit) but not deliverable content.

## Deferred from: code review of 9-13-video-detection-tester (2026-05-17, second /bmad-code-review pass)

- **`int(score_screen_duration_ms)` truncates a float / rejects a `"500.0"`-style string** — `video_test.py:345`. Schema-gated upstream (the emitter writes an integer per `map-config.schema.json`), so this only bites a hand-corrupted config; low value, deferred until a robustness-pass on `_load_config`.
- **`test_frame_source` POS_MSEC fake models the just-read frame, not real cv2's next-frame `CAP_PROP_POS_MSEC` semantics** — `test_video_detection_tester.py`. A test-fidelity nuance against the documented AC4 fallback decision, not a code defect; the production `timestamp_ms` could be off-by-one-frame vs real video and the fake would not catch it. Revisit if a real-video smoke (AC12, with 9.9b) shows timestamp drift.
- **Default-discovery path has zero test coverage** — `test_video_detection_tester.py`. `_classify_hud_version` mismatch/WARN and the default `--config`/`--output` discovery branch (the only non-deterministic + collision-prone path) are unexercised; pre-existing test-debt, not caused by this change. Fold into the next test-coverage pass on Tool 11.
