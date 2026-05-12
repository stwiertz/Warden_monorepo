# Deferred Work

Cross-story register of items deliberately deferred — pre-existing issues, out-of-scope findings, and items the team consciously decided to address later.

Each entry: bullet with the finding + brief reason.

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
