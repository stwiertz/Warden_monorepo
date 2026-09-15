# Story 12.3: Engine Verdict + PERF-002 Re-baseline + Fallback-Ladder Re-arm

Status: done

Sprint fit: `fits-in-one-sprint` ([epics-and-stories.md:3319](../epics-and-stories.md#L3319)). **This is a decision-and-documents story. It writes no production code.** Every number it publishes was already measured by Stories 12.1 and 12.2 — 12.3 does not re-measure, it *rules*.

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As **Stephane (solo dev / product owner)**,
I want **the detection-engine question closed on 12.2's reference-device evidence — a published spike report, a PERF-002 number re-baselined from measurement, a fallback ladder whose every rung has a reachable trigger and a remedy that works under the bound engine, and the architecture's five stale engine-era rationales corrected**,
so that **the auto-slice FRs get their V1 safety net back, and Stories 9.16 / 9.9b / 9.10 / 1.13 / 12.4 — and behind them ~20 stories of Epics 5/6/7 — stop waiting on a verdict that does not exist.**

---

## ⚠️ Read This First — The Evidence Is In, and It Does Not Say What the Pivot Assumed

**Both POCs are `done`.** Read these two reports before writing a line:

- [apps/tooling/tools/keyframe_engine_bench/REPORT.md](../../apps/tooling/tools/keyframe_engine_bench/REPORT.md) — 12.1, PC (465 lines). §1, §4.
- [apps/mobile/bench/12-2/REPORT.md](../../apps/mobile/bench/12-2/REPORT.md) — 12.2, **reference device** (753 lines). **§1, §4, §5 and §9 are the whole basis of this story.** §9 is written explicitly as input to your four slots.

Four results define your job. All four are measured, on the Poco X5 Pro 5G, and all four are load-bearing:

1. **Correctness is settled and is not a reason to choose either engine.** The GLSL is bit-exact on Adreno: **0 disagreements across 357,244 rule-frame decisions**, with accuracy reproducing 12.1's pins down to the counts. *Parity is banked. It buys the GPU nothing, because the CPU arm produced the same bits.*
2. **🔴 The GPU LOST, and lost harder on device than on PC.** Decode excluded from both sides, same bytes, 400 frames, 134 rules: **device CPU 0.376 ms/frame vs device GPU 2.389 ms/frame = 0.157× — the GPU is 6.4× SLOWER.** On PC it was 0.51×. Zero-copy did exactly what 12.1 hoped (upload 1.72 → 0.37 ms) and it was nowhere near enough. Robust to composition: substituting Path Z's real forced-completion stages gives **6.85×**, slightly worse.
3. **The engine — either engine — is ~6–7% of the wall.** Disjoint GL stages are **2.021 ms of 33.428 (6.0%)** on Path Z, **3.068 of 42.299 (7.3%)** on Path P. Choosing CPU over GPU moves a 35 s run by ~2 s.
4. **🔴 The bottleneck is not decode, and it is fixable.** `flush()` **14.5 ms** + output wait **22.1 ms** (of which **10.6 ms is sleeping in a `TIMEOUT_US = 10_000` we chose**) + `seekTo` **4.4 ms**; storage ~0. Real decoding is **~4 ms — DERIVED, not instrumented**. **~25 ms of every keyframe is teardown-and-restart plus our own timeout.** 35 s is not a platform floor.

**The consequence for your verdict:** the pivot was launched on the premise that a GPU mega-shader would make rule evaluation cheap enough to fix PERF-002. Measurement says rule evaluation was **never the problem** — it is 6% of the wall on the GPU and 1% on the CPU — and the GPU makes it *worse*. **You are not choosing between a fast engine and a slow one. You are closing a question whose answer is "the engine barely matters; the decode loop does."** Say that plainly in the report. It is the most valuable thing Epic 12 produced.

**And one thing the pivot's own framing got wrong in the other direction — check the arithmetic yourself before you write it:** PERF-002 is *"≤ 5% of source duration"* ([prd.md:1029](../prd.md#L1029)). The capture is **4419.633 s** (1 h 13 min 40 s — *not* the "~2 h" 12.1/12.2's AC text says; corrected in 12.2's Dev Agent Record). 5% of it is **220.98 s**. Path Z measured **35.5 s = 0.80%**. **PERF-002 as literally written is met by a factor of ~6.** The `< 10 s` aspiration is missed — and `< 10 s` is *not* an acceptance criterion ([prd.md:1029](../prd.md#L1029), [12.2 AC15](12-2-android-poc-gles-port.md)). Do not let the missed aspiration be written up as a failed NFR, and do not let the met NFR be written up as a triumph of the shader.

---

## Acceptance Criteria

### AC0 — Kickoff decisions (resolve BEFORE Task 1; record verdicts in Dev Agent Record)

**This story exists to make decisions. Do not resolve AC0a silently — it is Stephane's, named as his in the SCP handoff ([sprint-change-proposal-2026-07-16.md:300](../sprint-change-proposal-2026-07-16.md#L300)).**

- [x] **AC0a — 🔴 THE VERDICT: which engine is bound.** Present the evidence, recommend, and get Stephane's call.
  - **Option A — REJECT the GPU mega-shader; bind CPU rule evaluation on the MediaCodec keyframe-decode path.** *What the measurement supports.* The Kotlin CPU arm is 6.4× faster, bit-identical in output, has no EGL context, no LUT upload, no `glReadPixels` sync, no driver-defined colour conversion, and no Android-only GLES surface (amendment 5c **lapses** — see AC9). Keeps everything 12.2 proved about MediaCodec keyframe decode, `WardenRulePacker`'s exact packing semantics, and the AC12 `WardenCpuBaseline.kt` arm, which is already written and already validated at 0 disagreements.
  - **Option B — BIND the GPU mega-shader anyway.** Requires an argument the measurement does not supply (e.g. headroom against a much larger future ruleset, or offloading the CPU for concurrent work). If chosen, AC0b becomes live and 5c activates permanently. **State the non-performance justification explicitly or do not choose this.**
  - **Option C — Bind the keyframe-decode architecture now, defer the rule-eval arm to 12.4.** Unblocks 9.16/9.9b/9.10 on the parts that do not depend on the arm. **Costs:** 9.16 cannot re-point Tool 9 at an engine that is not chosen, so REL-006 stays instrument-less. Weigh that before picking it.
  - Whatever is chosen, **rung-0's "with a real engine binding" is not yet true** — 12.2 shipped a *bench*, not a pipeline binding. Decide and record whether the rung verdict is **final** or **provisional pending 12.4** (Story 1.1's provisional-rung-0 is the precedent: [architecture-spike-perf-floor.md:160](../architecture-spike-perf-floor.md)).
- [x] **AC0b — Colour path (live only under Option B/C-with-GPU).** Path P (bit-parity, +8.9 ms/kf) vs Path Z (zero-copy, 27% faster, diverges on **0.888%** of decisions across **59.9%** of keyframes and **95 of 134** rules including **44 of 69** low-saturation ones). 12.2's input-not-verdict recommendation is **Path P**, on the grounds that Path Z's divergence is *driver-defined and unspecified by AOSP*, therefore unpredictable across devices ([REPORT.md §9](../../apps/mobile/bench/12-2/REPORT.md)). **Under Option A the fork dissolves** — the CPU arm reads the ByteBuffer path's bit-parity conversion. Record it as N/A with that reason, do not leave it blank.
- [x] **AC0c — Which ladder rung the verdict fires, and on what.** See AC5. Note that PERF-003/PERF-004 (rung 2) have **never been measured** and became soft targets on 2026-05-09 — a rung whose trigger has no instrument is exactly the defect this story exists to fix. Decide whether rung 2 is re-armed, retired, or explicitly marked un-instrumented.
- [x] **AC0d — Who owns the decode-loop fix.** [deferred-work.md:173-175](deferred-work.md) homes two items at *"Story 12.3 or 12.4, whichever first owns the decode loop"*: shorten `TIMEOUT_US` (two lines, reclaims ~10.6 ms/kf) and stop flushing per keyframe (reclaims up to ~14.5 ms/kf). **Recommended: 12.4.** 12.3 is `fits-in-one-sprint` and writes no production code; taking a Kotlin change here breaks that and re-opens a device-measurement loop. If deferred, the report MUST quantify the headroom they represent (AC2) so the deferral is an informed one rather than an omission.

### The deliverable

- [x] **AC1 — `_bmad-output/architecture-spike-gpu-megashader.md` is published.** The artifact named by [architecture.md:840](../architecture.md#L840), [:1052](../architecture.md#L1052), [prd.md:1029](../prd.md#L1029) and [:1037](../prd.md#L1037). Filename exactly as written — four documents already link it. Follow the `architecture-spike-<topic>.md` convention ([architecture.md:1052](../architecture.md#L1052)) and mirror the H2 structure of [architecture-spike-perf-floor.md](../architecture-spike-perf-floor.md), whose header explicitly says *"Reviewers grep for the H2 sections below."* Required H2s, per [architecture.md:868](../architecture.md#L868)'s four-slot contract (*measured numbers · device profile · ladder-rung verdict · fixtures used*):
  - `## Device profile` — from [12.2 REPORT §2](../../apps/mobile/bench/12-2/REPORT.md). Poco X5 Pro 5G `22101320G` / SM7325 / **Adreno 642L** / Android 14 API 34 / `OpenGL ES 3.2 V@0530.57`. **Adreno 642L, never 619** — 619 is the pre-re-anchor SD695 ([[project_warden_reference_device]]).
  - `## Measured results` — the numbers in AC2.
  - `## Engine verdict` — AC0a's decision **and its reasoning**, stated as a decision, not a summary.
  - `## Ladder rung verdict` — AC0c + AC5.
  - `## Fixtures` — capture, config, parity corpus, PC reference, with the exact paths from [12.2 REPORT §10](../../apps/mobile/bench/12-2/REPORT.md).
  - `## What this does NOT bind` — mirror 12.2's AC15 block. In-sample parity ≠ accuracy-in-the-world; **REL-006's ≥95% floor is not gated here** (9.9b's, instrumented by Tool 9 via 9.16).
  - `## Follow-up work required` — AC0d's deferrals and the downstream story unblocks.
- [x] **AC2 — Every number in the report is traceable to a delivered artifact, and its measurement status is labelled.** No figure may be re-derived, rounded differently, or restated from an AC's prose. Cite the JSON: `device_report_timing.json`, `device_report_all.json`, `ac13_pathZ_vs_pathP.json`, `parity_comparison.json`, `ac3_frame_diff.json`, `device_probe_flush.json{,_run2,_run3}` under [apps/mobile/bench/12-2/](../../apps/mobile/bench/12-2/). **Tag derived figures as derived.** Specifically: the *"real decoding is ~4 ms"* figure is **DERIVED (`62.8 − 58.5`), not instrumented**, with ~11.5 ms of the output wait unattributed — 12.2's §9 item 4 was corrected on exactly this point; do not re-introduce the error. Two numbers that have already been corrected once and must be carried in their corrected form:
  - AC0b's decode-strategy comparison is **32.937 / 62.820** ms/kf (A / A-prime), **not** 33.68 / 116.45.
  - The GL share of the wall is **6.0% / 7.3%**, **not** 1% — the "99% decode" figure nests the GL stages inside `decode`.
- [x] **AC3 — 🔴 PERF-002 is re-baselined, and the re-baseline states what is inside the number and what is not.** Amend [prd.md:1029](../prd.md#L1029) (currently `RE-BASELINE PENDING`) with the measured figure. The arithmetic, to be re-verified by you and shown in the report:

  | | value |
  |---|---|
  | source duration | **4419.633 s** (1 h 13 min 40 s) — `ffprobe`, corroborated by 1061 × 4.1667 s GOP |
  | PERF-002 budget @ ≤5% | **220.98 s** |
  | measured, Path Z | **35.5 s = 0.80%** (~125× real time) |
  | measured, Path P | **44.9 s = 1.02%** (~98× real time) |

  **The honesty requirement:** the 35.5 s is a *detection-pass bench*. The one-off keyframe index (**2.29 s** by seek; the 62.07 s ground-truth scan is a bench assertion that **MUST NEVER SHIP**) is reported *outside* every wall clock, and the bench does not include segmentation, thumbnail export, or the rest of the auto-slice pipeline PERF-002 actually scopes. **State explicitly what the re-baselined number covers and what a full auto-slice run would add.** Re-baselining PERF-002 off a number that excludes stages the NFR includes is the single most likely way to get this story wrong.
- [x] **AC4 — PERF-010 disposition recorded.** [prd.md:1037](../prd.md#L1037) re-points its binding gate from Story 1.1 to this story. PERF-010 is a **soft target, not a measured floor** (2026-05-09 ship-and-observe, [[project_warden_ar_spike_binding_only]]); the pivot re-points which spike *would* report one, it does not re-arm a measured floor. **Decide and state: does 12.2's reference-device run bind a number here, or does PERF-010 stay TBD/soft?** Either answer is acceptable; leaving it ambiguous is not. Cascade: [architecture.md:2091](../architecture.md#L2091) still says *"PERF-010: TBD pending spike — architecture's load-bearing first deliverable"*.

### The ladder — amendment 5b, and the rung nobody has noticed yet

- [x] **AC5 — 🔴 Every rung has a reachable trigger AND a remedy that works under the bound engine.** The ladder is [architecture.md:861-866](../architecture.md#L861-L866). The 2026-07-16 pass re-armed **rung 3's trigger only**. Audit all five rows; at minimum:
  - **Rung 1 — `Rung 1: lower auto-slice frame-sampling rate`. 🔴 This remedy is INERT under a keyframe-only engine and nobody has recorded it.** The sampling rate *is* the GOP (4.1667 s, 1061 keyframes); you cannot lower it without skipping keyframes outright, and rule evaluation is **6% of the wall**, so lowering it recovers almost nothing. This is the *same class of defect* as rung 3's unreachable "JSI binding does not ship" trigger — a rung that reads armed and is not. Re-arm it with a remedy that engages the measured cost (the decode loop: timeout, per-keyframe flush, IDR pipelining — AC0d), or retire it and say why. **Note its PRD cascade:** [prd.md](../prd.md) `mobile-AUTO-SLICE-001`'s *"with reduced sampling on weak hardware"* clause is attached to this rung.
  - **Rung 2 (PERF-003 / PERF-004)** — per AC0c, no instrument exists.
  - **Rung 3** — trigger was re-armed in wording 2026-07-16; state the verdict against it now that evidence exists.
  - **Pass row** — its condition is *"all 4 PERF NFRs met on reference device **with a real engine binding**"*. Only PERF-002 is measured, and the binding is 12.4's. Say so.
  - **🔴 The FORBIDDEN row (cloud CV) is carried VERBATIM.** [architecture.md:866](../architecture.md#L866). It is the only absolute prohibition in the ladder; [INVARIANT 3] holds either way because both candidate engines are on-device. **Do not re-word it, do not "modernize" it, do not fold it into another row.**
  - Cascades to update once the ladder moves: [architecture.md:936](../architecture.md#L936), [:2049](../architecture.md#L2049), [:2213](../architecture.md#L2213), [prd.md:213](../prd.md#L213).

### Architecture amendments this story owns

- [x] **AC6 — Amendment 5d: the Foreground Service rationale is RE-DERIVED from 12.2's measured threading model.** [architecture.md:810-815](../architecture.md#L810-L815) carries a `RATIONALE RE-DERIVATION REQUIRED` banner naming 12.2 → 12.3 as the owners; 12.2 supplied the model and wrote *"12.3 rewrites the architecture prose."* The model: EGL context created and made current on a plain worker thread (`warden-bench`) with a **pbuffer** surface — no Activity, no SurfaceView, no UI thread; `MediaCodec` callbacks and `SurfaceTexture.updateTexImage()` on that same thread. **EGL contexts are THREAD-bound, not JS-context-bound.** The conclusion survives — a Foreground Service is still the right host — **but because the process must stay alive at foreground importance for a multi-minute run, not because the JS context must be co-located.** Rewrite the rationale bullets at `:810-811` and the coherence sentence at [:2047](../architecture.md#L2047) (*"the foreground service hosts the main JS context where the JSI binding lives"*). Then **remove the banner** — a re-derivation that leaves the "REQUIRED" flag standing has not landed. If Option A is chosen, note that the thread-affinity argument narrows (no EGL context) but the process-lifetime argument is unchanged and is now the load-bearing one.
- [x] **AC7 — Amendment 5g: the fifth-native-module decision entry is written.** [architecture.md:2207](../architecture.md#L2207) says verbatim *"the decision entry lands with Story 12.3."* Add a `#### Decision #N — <title> [RESOLVED]` entry following the house shape used by the existing entries ([architecture.md:350](../architecture.md#L350), [:377](../architecture.md#L377)): **Choice / Rationale / Implementation**, plus the alternatives rejected. Content is AC0a's verdict and its measured basis — the Kotlin CPU arm and the GLES mega-shader are each other's rejected alternative, and the rejection is on measurement.
  - **🔴 The numbering trap.** The `Decision #N` register is **shared across three documents and is not contiguous in any one of them.** `architecture.md` carries `####` entries for **#1, #2, #3, #6, #7, #8, #9** only; **#4 and #5 are PRD decisions** with no architecture entry ([architecture.md:153](../architecture.md#L153), [:689](../architecture.md#L689)); **#10, #11, #12 are product-brief decisions resolved in the PRD** ([prd.md:208](../prd.md#L208), [:468](../prd.md#L468), [:608](../prd.md#L608)). **#1–#12 are all taken. The next free number is #13.** Do not read the architecture doc's gaps as free slots. Re-verify with `grep -o "Decision #[0-9]\+" _bmad-output/{prd,architecture,epics-and-stories}.md | sort -u` before you write the heading.
- [x] **AC8 — SEC-007 entry 5/5a disposition matches the verdict.** The allowlist block ([architecture.md:2057](../architecture.md#L2057)) carries a standing note: *"It does not authorize the GPU engine architecturally — Story 12.3 owns that decision, and if 12.3 rejects the engine, entry 5 and 5a are removed along with the plugin."* Act on it. **Under Option A, decide explicitly whether the Kotlin engine module survives in reduced form** (MediaCodec + `WardenCpuBaseline` but no GLES/EGL) — if it does, entry 5's text must be corrected rather than deleted, and 5a's `ffmpeg-kit-main-16kb` compile-time coordinate re-evaluated (it exists only for AC0b Option C's decode control). **The physical plugin/Kotlin removal is NOT this story's** (AC12) — record the decision, leave the code to 12.4.
- [x] **AC9 — Amendment 5c is resolved: activate permanently, or lapse.** [architecture.md:894](../architecture.md#L894) states the iOS-Phase-2 cost amendment *"lapses and the original assertion stands unmodified"* if 12.3 rejects the shader engine. Under Option A, MediaCodec still makes decode Android-only (iOS = VideoToolbox) even without GLES — **so "lapse" is very likely the wrong answer even under rejection; re-scope rather than revert.** Under Option B it activates permanently. Write the resolution into the amendment block; do not leave it conditional.
- [x] **AC10 — Amendment 5f is FINISHED.** The 2026-07-16 pass re-pointed REL-006's instrument at **one** of its three named sites. [architecture.md:120](../architecture.md#L120) is amended; **[:855](../architecture.md#L855)** (*"the legacy `hash_validator` regression suite is the measurement tool"*, inside the spike scope) and **[:2093](../architecture.md#L2093)** (*"REL-006 (accuracy floors) covered by `hash_validator` regression suite"*) are **not**. `hash_validator.py` measures Hamming distance between perceptual hashes and cannot measure either candidate engine. This is 12.3's, not 9.10's — Story 9.10's own scope note records that 5f was *"pulled forward into the SCP rather than deferred here, because [it leaves] live gaps."* Re-point both to Tool 9 via Story 9.16.
- [x] **AC11 — Housekeeping that falls out of publishing a new artifact.** (a) Add `architecture-spike-gpu-megashader.md` to the `_bmad-output/` tree listing at [architecture.md:1651](../architecture.md#L1651), beside `architecture-spike-perf-floor.md`. (b) Leave [architecture.md:836-894](../architecture.md#L836)'s preserved JSI record and Story 1.1's rung-0 verdict **FROZEN** — per [[project_warden_ar_spike_binding_only]] and 9.10's FROZEN-block discipline, 12.3 *supersedes*, 1.1 *records*. Add a forward pointer; do not edit the record.

### Fences, downstream, and delivery

- [x] **AC12 — Scope fence.** 12.3 does **NOT**: write or delete production code · touch `apps/mobile/plugins/**` or any `Warden*.kt` · touch `gameDetector.ts` / `mapIdentifier.ts` / `blackScreenDetector.ts` / `segmentation.ts` / `processingPipeline.ts` (**12.4's**) · re-point Tool 9 or `video_test.py` (**9.16's**) · touch zone data, `map_config*`, or `contracts/map-config.schema.json` · bump `schema_version` (**E1**) · re-measure anything on the device · run the exhaustive pHash→engine prose sweep (**9.10's** — you amend only the ~10 sites this story's ACs name, all of which are live gaps rather than stale prose) · re-open Story 1.1 (**FROZEN**). Verify with `git status --porcelain` before delivery: the diff should be `_bmad-output/**` only.
- [x] **AC13 — Downstream unblocks executed in `sprint-status.yaml`.** The epic names five: `9-16`, `9-9b`, `9-10`, `1-13` (create-story), `12-4`. For each, set the status the verdict implies and **record why in the entry comment** — `9-16` and `12-4` are *conditional on the verdict* and a rejection changes what they mean, not just when they run. Set **12.4's sprint fit**, which the epic leaves as *"TBD at create-story (conditional on the 12.3 verdict)"* ([epics-and-stories.md:3326](../epics-and-stories.md#L3326)). Note `blocked` is a held state outside the STATUS DEFINITIONS enum (Story 1.9's precedent) — releasing from it returns a story to `backlog` unless a file already exists.
- [x] **AC14 — Epic-level sequencing note updated.** Epics 5/6/7 are *"held behind 12.3 + 12.4"* ([sprint-change-proposal-2026-07-16.md:222](../sprint-change-proposal-2026-07-16.md#L222)); the hold is recorded in the epics doc, not as a status. Update the Epic List sequencing note to reflect that 12.3 has landed and only 12.4 remains between them and start. Update Epic 12's charter block at [epics-and-stories.md:3279](../epics-and-stories.md#L3279) with the verdict.
- [x] **AC15 — The three deferred-work items are disposed, not inherited silently.** [deferred-work.md:157](deferred-work.md) (stale thumbnails in Tool 12's output dir — *"the output dir is an evidence artifact 12.3 reads"*), [:173](deferred-work.md) (`TIMEOUT_US`), [:175](deferred-work.md) (per-keyframe flush). Per AC0d, record each as taken-here or re-homed-to-12.4 with a line of reasoning.
- [x] **AC16 — Gates green.** `pnpm typecheck && pnpm test && pnpm format:check` from the repo root. **Re-verify the baseline first — do not trust the numbers below, they are a starting point, not a gate.** Post-12.2 state was: mobile jest **20 suites / 161 passed + 10 todo**; tooling pytest **305**; root typecheck **3 errors, all `web` (pre-existing)**; web vitest **132 failed / 193 passed — inherited red, a duplicate-React-under-pnpm fault, not introduced** (Story 1.10's finding); `format:check` clean. A docs-only diff should move none of them; if one moves, that is a finding. **`format:check` covers markdown — run it, this story is all markdown.**
- [x] **AC17 — Committed to `main`.** ✅ Done 2026-09-15 on Stephane's go-ahead. Direct to `main`, no branch, no PR ([[project_warden_main_branch_workflow]]); lowercase subject, scope `docs(bmad)` per the `13f21fb` precedent; **not pushed** (`main` is not auto-pushed). `sprint-status.yaml`, `epics-and-stories.md`, `prd.md`, `architecture.md` and `deferred-work.md` all ride in the **same** commit — [[feedback_two_pr_docs_execution]]'s two-PR sequencing retired with the branch workflow, and the tree was clean of foreign edits so [[project_warden_shared_doc_commit_boundary]] does not bite. Work happens directly on `main` — no branch, no PR ([[project_warden_main_branch_workflow]]). Commitlint requires a **lowercase subject**; scope `bmad` or `docs` per the recent docs-commit precedent (`13f21fb docs(bmad): close Stories 9.15 and 12.1 …`). `main` is **not** auto-pushed. `sprint-status.yaml` and `epics-and-stories.md` ride in the same commit — [[feedback_two_pr_docs_execution]]'s two-PR sequencing was retired with the branch workflow, and the working tree is clean so [[project_warden_shared_doc_commit_boundary]] does not bite.
- [x] **AC18 — `sprint-status.yaml`: `12-3-…` `review → done`.** ✅ Done 2026-09-15, **in the same commit as AC17**. Per [[feedback_ac_checkbox_tighten]] this is `[x]` rather than demoted **because there is no post-merge action left**: working directly on `main` removes the merge boundary the Two-PR pattern existed to bridge, so the commit *is* the delivery and the flip is atomic with it. The two ACs that genuinely depended on a later action — these — are now satisfied by the action itself. Original text: **AC18 —**, per [[feedback_ac_checkbox_tighten]] — demote any AC whose endpoint depends on a post-merge action rather than leaving it `[x]` on precedent.

---

## Tasks / Subtasks

- [x] **Task 1 — Resolve AC0.** (AC: 0a–0d)
  - [x] Read [12.2 REPORT §1/§4/§5/§9](../../apps/mobile/bench/12-2/REPORT.md) and [12.1 REPORT §1/§4](../../apps/tooling/tools/keyframe_engine_bench/REPORT.md) in full.
  - [x] Present AC0a's three options to Stephane with the measured basis for each. **Do not proceed without his call.**
  - [x] Record all four verdicts in the Dev Agent Record table.
- [x] **Task 2 — Assemble and verify the numbers.** (AC: 2, 3)
  - [x] Pull every figure from the JSON artifacts in `apps/mobile/bench/12-2/`, not from prose.
  - [x] Re-compute the PERF-002 percentages yourself. Confirm 4419.633 s and the 5% budget.
  - [x] Label each figure measured / derived.
- [x] **Task 3 — Write `_bmad-output/architecture-spike-gpu-megashader.md`.** (AC: 1, 2, 3)
  - [x] Mirror `architecture-spike-perf-floor.md`'s H2 shape; include all seven required sections.
  - [x] Include the "What this does NOT bind" block.
- [x] **Task 4 — Audit and re-arm the ladder.** (AC: 5, 0c)
  - [x] Walk all five rows. For each: is the trigger reachable, and does the remedy engage the measured cost?
  - [x] Carry the FORBIDDEN row verbatim.
  - [x] Update the four cascade sites.
- [x] **Task 5 — PRD amendments.** (AC: 3, 4)
  - [x] `prd.md:1029` PERF-002 re-baseline, with the coverage caveat.
  - [x] `prd.md:1037` PERF-010 disposition.
  - [x] `prd.md:213` ladder-safety-net sentence.
- [x] **Task 6 — Architecture amendments 5d / 5g / 5f-completion / 5c / SEC-007.** (AC: 6, 7, 8, 9, 10, 11)
  - [x] 5d: rewrite `:810-811` + `:2047`; **remove the RE-DERIVATION REQUIRED banner**.
  - [x] 5g: new `#### Decision #N` entry; verify the next free number on disk.
  - [x] 5f: finish at `:855` and `:2093`.
  - [x] 5c: resolve activate-or-rescope at `:894`.
  - [x] SEC-007: correct or mark entries 5/5a per the verdict.
  - [x] Add the new spike artifact to the tree listing at `:1651`.
- [x] **Task 7 — Downstream + epic housekeeping.** (AC: 13, 14, 15)
- [x] **Task 8 — Fence check, gates, delivery.** (AC: 12, 16, 17, 18)
  - [x] `git status --porcelain` → `_bmad-output/**` only. ✅ verified.
  - [x] Re-verify the gate baseline, then run the gates. ✅ baseline re-verified, gates run — see Completion Notes.
  - [x] Commit; flip `review → done`. ✅ Done 2026-09-15 — one atomic commit on `main`, not pushed.

---

## Dev Notes

### The measured record, in one place

All from [apps/mobile/bench/12-2/REPORT.md](../../apps/mobile/bench/12-2/REPORT.md) unless marked 12.1.

**Fixtures.** Capture `videos/V2/2026-04-27 22-05-34.mp4` — 2.3 GB, **4419.633 s**, GOP **4.1667 s**, **1061 keyframes**. Config `apps/tooling/output/map_configs/map_config.v2.json` — **134 rules** (10 hud / 3 in_match / 121 map across 13 maps), mode distribution 68 full-circle / 9 wrap / 57 normal. Parity corpus `apps/tooling/output/labeled/v2/` — 2666 PNGs / 16 classes. PC reference `apps/mobile/bench/12-2/pc_reference_fires.json`.

**Wall clock, per keyframe:**

| stage | Path Z (zero-copy) | Path P (bit-parity) |
|---|---|---|
| decode | 33.105 | 42.085 |
| upload / bind | 0.378 | 1.569 |
| resolve | 0.256 | 0.144 |
| shader | 0.108 | 0.048 |
| readback | 1.279 | 1.307 |
| **wall** | **33.428** | **42.299** |
| whole capture | **35.5 s** | **44.9 s** |
| GL share (disjoint) | **6.0%** | **7.3%** |

*(The naive `decode` row nests the GL stages inside itself — summing the rows exceeds the wall. Use the disjoint GL share, 2.021 / 33.428 and 3.068 / 42.299.)*

**Forced-completion medians (`glFinish()` per stage, 200 reps):** Path Z bind **0.367** / resolve 1.306 / shader 0.598 / readback 0.305 → GPU total **2.576**. Path P upload **1.720** / resolve 1.267 / shader 0.268 / readback 0.136 → **3.391**.

**CPU vs GPU (AC12 — the epic's decisive number):** device CPU **0.376 ms/frame**, device GPU **2.389 ms/frame**, ratio **0.157× (GPU 6.4× slower)**, **0 fire-bit disagreements between the arms**. 12.1 on PC: 0.51×.

> ⚠️ **The CPU figures are not a hardware comparison.** 12.1's PC CPU number (1.667 ms) is Python driving 134 separate `cv2.inRange` calls; the device number (0.376 ms) is a tight Kotlin loop. The phone's CPU is not faster than a desktop's — the implementation is leaner. What survives either implementation: *evaluating 134 tiny rects is a trivially cheap CPU task, and routing it through a GPU costs more than it saves.* **Quote it that way in the report.**

**Parity:** 0 disagreements / **357,244** rule-frame decisions (2666 × 134); 0 frames with any disagreement. Accuracy reproduced exactly: hud **2614/2666 = 0.980495**, in_match **2666/2666 = 1.0000**, map_id **2286/2286 = 1.0000** — **in-sample, no holdout**, a parity target and never a generalization claim.

**Decode decomposition** (ByteBuffer path, 100 kf × 3 runs, ±0.4 ms): `seekTo` **4.4 (10%)** · **`flush()` 14.5 (34%)** · queue IDR → first output **22.1 (52%)**, of which **10.6 sleeping in `TIMEOUT_US = 10_000`** · accounted 41.0 / 42.3 = 97% · real decoding **~4 ms [DERIVED]**, ~11.5 ms unattributed. `flush()` is 14.5 ms in-loop vs **1.8 ms idle** — the cost is the `END_OF_STREAM` → flush transition, not the firmware round trip. Storage **~0** (5 KB/kf). Hardware decode buys only ~8% (ffmpeg-kit software **38.1 s** vs MediaCodec **35.1 s**) — *which is itself the proof that the time is not going into decoding.*

**Colour (AC3), OpenCV HSV units, vs FFmpeg `rgb24`:** Path P ΔS **2.46** (all 134 rects) / **2.86** (69 low-sat); Path Z ΔS **5.64** / **5.62**. Neither shows the range-error signature (12.1 measured a range error at ΔS ≈ 19.68). Residual is a chroma-upsampling policy difference (nearest vs swscale interpolation), ≤3 units of 255.

**Path Z vs Path P divergence:** **1262 of 142,174** decisions (**0.888%**), **635 of 1061** keyframes (**59.9%**), **95 of 134** rules, incl. **44 of 69** low-saturation.

**Thermal:** `Thermal Status: 0`, every cooling device at 0, across an ~8-minute run. **No throttling observed.** Two independent full runs agree (Path Z wall 33.428 vs 33.117).

### What "the engine" turned out to be about

The pivot's founding chain was: *PERF-002 is unacceptable → the per-frame CPU `cv2.inRange` path is the ceiling → a GPU mega-shader removes the ceiling.* Link 2 is now falsified on the reference device. Rule evaluation was **never the ceiling**: it is 0.376 ms/frame on the CPU against a 33–42 ms wall. The wall is a per-keyframe **pipeline teardown-and-restart**, ~25 ms of which is `flush()` plus a timeout we chose ourselves.

**This does not make Epic 12 a waste, and the report should not read as if it were.** It produced: a measured decode decomposition nobody had; a bit-exact integer HSV rule evaluator validated on Adreno across 357k decisions; `WardenRulePacker` with byte-identical semantics to `lut.py`; a working MediaCodec keyframe-decode path with a count assertion that caught a silent 2-vs-1061 failure; and a ~6× headroom target with two concrete, cheap fixes. **What it refutes is a mechanism, not the pivot's judgment that the engine question had to be answered before ~20 UI stories were built on top of it.**

### The five architecture amendments and their current state — verify each, do not trust this table

| # | Target | State on disk | 12.3's obligation |
|---|---|---|---|
| **5a** | Spike scope [:840](../architecture.md#L840) | ✅ banner applied 2026-07-16 | Cascade at [:2091](../architecture.md#L2091) (PERF-010 TBD) still open — AC4 |
| **5b** | Ladder [:861-866](../architecture.md#L861) | ⚠️ **rung 3's trigger only**; rung 1's remedy is inert, rung 2 has no instrument | **AC5 — the core of this story** |
| **5c** | iOS [:894](../architecture.md#L894) | ⚠️ applied but **conditional** on 12.3's verdict | AC9 — resolve activate-or-rescope |
| **5d** | FGS rationale [:810-815](../architecture.md#L810), [:2047](../architecture.md#L2047) | ❌ banner only; prose unchanged | AC6 — 12.2 supplied the model, **you write the prose** |
| **5e** | Decision #2 [:386](../architecture.md#L386) | ✅ applied 2026-07-16 | Verify only |
| **5f** | REL-006 instrument | ⚠️ **1 of 3 sites** — [:120](../architecture.md#L120) done; [:855](../architecture.md#L855), [:2093](../architecture.md#L2093) open | AC10 |
| **5g** | 5th native module [:2207](../architecture.md#L2207) | ⚠️ invariant note + SEC-007 entry 5 exist; **the Decision entry does not** | AC7 — `:2207` literally says it lands here |

### Conventions that bind

- **Spike artifact path:** `_bmad-output/architecture-spike-<topic>.md` ([architecture.md:1052](../architecture.md#L1052)). The filename `architecture-spike-gpu-megashader.md` is **already referenced by four documents** — it is not yours to rename.
- **Spike report content contract:** *"measured numbers, the device profile, the ladder-rung verdict, and the regression-test fixtures used"* ([architecture.md:868](../architecture.md#L868)).
- **Reports live beside the code; verdicts live in `_bmad-output/`.** 12.1 and 12.2 each wrote a `REPORT.md` next to their implementation and explicitly withheld the verdict for you. **Do not duplicate their measurement sections into the spike report — cite them.** The spike report is a decision document with the numbers that support the decision, not a third copy of the data.
- **FROZEN blocks are audit trail, not stale prose.** Story 1.1's JSI record, cancelled 9.1–9.4, superseded 9.9a, the preserved 9.9 stub. Supersede and point forward; never edit.
- **Commit:** lowercase subject, commitlint-enforced. Direct to `main`, not auto-pushed.

### Project Structure Notes

Files 12.3 creates or edits — **all under `_bmad-output/`**:

| File | Action |
|---|---|
| `_bmad-output/architecture-spike-gpu-megashader.md` | **NEW** — the deliverable |
| `_bmad-output/architecture.md` | UPDATE — ladder `:861-866`; 5d `:810-815` + `:2047`; 5f `:855` + `:2093`; 5c `:894`; 5g new Decision entry + `:2207`; SEC-007 `:2057`; tree `:1651`; cascades `:936`, `:2049`, `:2091`, `:2213` |
| `_bmad-output/prd.md` | UPDATE — `:1029` PERF-002, `:1037` PERF-010, `:213` ladder sentence |
| `_bmad-output/epics-and-stories.md` | UPDATE — Epic 12 charter `:3279`, Story 12.3 `:3320`, Epic List sequencing note, 12.4 sprint fit `:3326` |
| `_bmad-output/sprint-status.yaml` | UPDATE — 12.3 lifecycle + five downstream unblocks |
| `_bmad-output/implementation-artifacts/deferred-work.md` | UPDATE — three items disposed |
| `_bmad-output/implementation-artifacts/12-3-*.md` | UPDATE — this file's Dev Agent Record |

**Line numbers in this story were read on 2026-09-15 and will drift as you edit.** Grep for the quoted phrase, not the number.

### References

- [epics-and-stories.md:3279-3332](../epics-and-stories.md#L3279) — Epic 12 charter, founding constraints E1–E7, Stories 12.1–12.4
- [sprint-change-proposal-2026-07-16.md](../sprint-change-proposal-2026-07-16.md) — the pivot; §4.2 amendments 5a–5g, §4.3 PRD targets, §4.4 sprint-status, §Sequencing, §Success criteria
- [apps/mobile/bench/12-2/REPORT.md](../../apps/mobile/bench/12-2/REPORT.md) — **§9 is written as input to your four slots**
- [apps/tooling/tools/keyframe_engine_bench/REPORT.md](../../apps/tooling/tools/keyframe_engine_bench/REPORT.md) — 12.1 PC baseline
- [12-2-android-poc-gles-port.md](12-2-android-poc-gles-port.md) — AC15 (what 12.2 does not bind), AC16 (threading model), Dev Agent Record corrections
- [12-1-pc-poc-gpu-megashader-bench.md](12-1-pc-poc-gpu-megashader-bench.md)
- [keyframe-decode-perf-research.md](keyframe-decode-perf-research.md) — the independent decode-cost investigation; §6 marks its section-2 decomposition as derived
- [architecture-spike-perf-floor.md](../architecture-spike-perf-floor.md) — **the format precedent**; H2 structure, decision-banner style, rung-verdict section
- [architecture.md:836-894](../architecture.md#L836) — spike + ladder + iOS assertion
- [architecture.md:2057](../architecture.md#L2057) — SEC-007 allowlist, entries 5/5a and their standing note
- [prd.md:1029](../prd.md#L1029), [:1037](../prd.md#L1037), [:1056](../prd.md#L1056) — PERF-002 / PERF-010 / REL-006
- [deferred-work.md:157,173,175](deferred-work.md) — the three items homed here
- Memory: [[project_warden_engine_first_pivot]] · [[project_warden_reference_device]] · [[project_warden_ar_spike_binding_only]] · [[project_warden_main_branch_workflow]] · [[feedback_ac_checkbox_tighten]] · [[feedback_batch_manual_checks_epic_end]]

---

## Change Log

| Date | Change |
| --- | --- |
| 2026-09-15 | Story created (`/bmad-create-story`, claude-opus-5[1m]). `backlog → ready-for-dev`. |
| 2026-09-15 | **Delivered.** Committed to `main` on Stephane's go-ahead (`docs(bmad)`, lowercase subject, not pushed); `sprint-status.yaml` flipped `review → done` in the same commit. AC17 + AC18 closed — no post-merge tail, because the main-branch workflow removes the merge boundary. **Status: `review → done`.** |
| 2026-09-15 | **Executed** (`/bmad-dev-story`, Amelia, claude-opus-5[1m]). `ready-for-dev → in-progress → review`. **AC0a verdict: Option A — the GPU mega-shader is REJECTED; Kotlin CPU rule evaluation on the MediaCodec keyframe-decode path is BOUND.** `architecture-spike-gpu-megashader.md` published; PERF-002 re-baselined; PERF-010 disposition recorded; the Innovation #1 ladder re-armed across all five rungs; amendments 5b/5c/5d/5f/5g + SEC-007 closed; `Decision #13` written; five downstream unblocks executed. **Delivery HELD at AC17/AC18** — nothing committed. |

---

## Dev Agent Record

### Agent Model Used

`claude-opus-5[1m]` (Amelia, `/bmad-dev-story`), 2026-09-15.

### AC0 — Kickoff decisions (resolved before Task 1)

| AC | Verdict | Notes |
| --- | --- | --- |
| **AC0a — engine bound** | 🔴 **Option A — REJECT the GPU mega-shader. Bind CPU rule evaluation on the MediaCodec keyframe-decode path.** | Stephane's call, taken on the measured evidence. Basis: device CPU **0.375807** vs device GPU **2.389213** ms/frame = **0.157293× (6.4× slower)** with **0 fire-bit disagreements** between the arms, and **0 disagreements across 357,244 rule-frame decisions** against the PC reference. Robust to composition — substituting Path Z's real forced-completion stages gives **2.5770305 ms = 6.86×**, slightly worse. The engine is **6.0% / 7.3%** of the wall, so the whole choice is worth **~2.7 s** on a 35–45 s run. **Rung verdict: PROVISIONAL pending Story 12.4** (Story 1.1's provisional-rung-0 is the precedent) — 12.2 shipped a *bench*, not a pipeline binding, so *"with a real engine binding"* is not yet true. |
| **AC0b — colour path** | **N/A — the fork dissolves.** Recorded with its reason, not left blank. | Path Z exists only to hand a `samplerExternalOES` texture to a shader. With no shader there is no OES conversion and no divergence to weigh; the bound engine reads the **ByteBuffer path's bit-parity conversion**. For the record, 12.2's input-not-verdict recommendation was **Path P**, because Path Z's **0.888%** divergence (1262 / 142,174 decisions, 635 / 1061 keyframes, 95 / 134 rules, **44 of 69** low-saturation) is *driver-defined and unspecified by AOSP* — unpredictable across devices, landing where the accepted `h_tol = 180` tuning is most fragile. **Option A reaches the same colour behaviour by removing the choice instead of making it.** |
| **AC0c — ladder rung** | **Rung 2 explicitly marked `TRIGGER UN-INSTRUMENTED`; rung RETAINED.** Rung 1 **re-armed**; rung 3 **answered**; Pass row **provisional**; FORBIDDEN row **verbatim**. | Not retired (the remedy is sound and should exist the day a number does) and not re-armed (arming it means building a view-mode / cold-start timing instrument, which no story owns). PERF-003 / PERF-004 have never been measured, the surfaces do not exist, and both became soft targets on 2026-05-09. Natural home for the instrument: Stories 5.4 / 5.5 / 6.6. |
| **AC0d — decode-loop fix owner** | **Story 12.4** (the story's own recommendation), with the headroom quantified so the deferral is informed. | `TIMEOUT_US` ~**10.6 ms/kf** (~11.2 s) + per-keyframe `flush()` up to ~**14.5 ms/kf** (~15.4 s) = **~25.1 of the 42.2 ms/kf wall**, a projected **~2.5×** decode-loop speedup, ~18 s whole-capture. 12.3 is `fits-in-one-sprint` and writes no production code; a Kotlin change here breaks that fence and re-opens a device-measurement loop. |

### Debug Log References

- **Every figure was pulled from JSON, not from prose** (AC2 / Task 2), and the derived ones were recomputed: the 5% budget (`4419.633333 × 0.05 = 220.98`), both percentages (`35.4668 / 4419.633 = 0.8025%`, `44.8793 / 4419.633 = 1.0155%`), both real-time factors (×124.6, ×98.5), both disjoint GL shares (`2.0206 / 33.428 = 6.04%`, `3.0685 / 42.299 = 7.25%`), the divergence rates, and `1061 × 134 = 142,174` / `2666 × 134 = 357,244`.
- **Baseline gates re-verified before any edit** (AC16 explicitly says not to trust the story's numbers). Results below.
- **`git status --porcelain` verified twice** — before and after the edits. `_bmad-output/**` only, both times.
- **`Decision #N` register re-verified on disk** with `grep -o "Decision #[0-9]\+" _bmad-output/{prd,architecture,epics-and-stories}.md | sort -u` → `#1–#12` all taken across the three documents. **Next free is #13**, as the story warned. `architecture.md`'s own gaps at #4/#5/#10–12 are PRD and product-brief decisions, not free slots.
- **`hash_validator.py` was checked for existence** rather than assumed: `apps/tooling/tools/` contains no such file. It was retired by Story 9.11.
- **Prettier coverage was checked rather than assumed**: `npx prettier --file-info _bmad-output/architecture-spike-gpu-megashader.md` → `{ "ignored": true }`.

### Completion Notes List

#### The verdict

**Option A. The GPU mega-shader is rejected; Kotlin CPU rule evaluation on the MediaCodec keyframe-decode path is bound.** Recorded as `architecture.md` **Decision #13** and published in **`_bmad-output/architecture-spike-gpu-megashader.md`** with all seven required H2 sections plus an eighth (`## NFR re-baseline (PERF-002 / PERF-010)`) so the re-baseline is greppable.

The report says plainly what the story asked it to say: **the engine barely matters; the decode loop does.** Rule evaluation is 6–7% of the wall on the GPU and ~1% on the CPU, so the entire engine question was worth **~2.7 s** on a 35–45 s run, while `flush()` plus a timeout we chose ourselves is worth **~26 s**. The pivot's founding chain is falsified at link 2 — and the report also states why that does not make Epic 12 a waste: it refutes **a mechanism, not the judgment that the question had to be answered** before ~20 stories were built on top of it.

#### 🔴 A second way to get the PERF-002 re-baseline wrong, which the story did not anticipate

The story warned against re-baselining off a number that excludes stages the NFR includes. **There is a second trap, and it is the one I hit first and backed out of.**

The story's AC3 table offers **Path Z, 35.5 s = 0.80%** as the measured figure. **Path Z is a zero-copy decode into a GL texture. It exists solely to feed the shader — the configuration this story just rejected.** A CPU rule evaluator needs the pixels on the CPU, which is the ByteBuffer path, **Path P**. Re-baselining PERF-002 at 0.80% would have quoted a throughput the bound engine cannot produce.

**PERF-002 is therefore re-baselined at the measured Path P figure — `44.879 s = 1.02%` against a `220.98 s` budget, MET by ~4.9×.** That is a *conservative upper bound* on the bound configuration, because Option A removes work from the path that produced it. The composed figure (`42.299 − 3.068 GL + 0.376 CPU = 39.607 ms/kf → ~42.0 s = 0.95%`) is carried **labelled `[P]` and is used nowhere as the binding number** — it describes a configuration that was never run end to end.

Both caveats are stated in the PRD amendment and in the report: the number covers the **detection pass only**, and **Story 12.4 must re-measure end to end**.

#### Every planted finding confirmed, and what each cost

1. **PERF-002 as written is met** — by ~4.9× on the bound configuration (~6.2× on Path Z). The missed `< 10 s` is written up as an **aspiration**, never as a failed NFR, and the met NFR is explicitly **not** credited to the shader.
2. **Rung 1 was inert** — and re-arming it needed more than a replacement. The remedy is now **two steps**: (1a) decode-loop overhead, which engages the measured cost at no accuracy cost, and (1b) **keyframe decimation**, which is what *"lower the sampling rate"* can honestly mean under a keyframe-only engine. Step 1b is what **preserves the `mobile-AUTO-SLICE-001` PRD clause** — replacing the remedy outright would have orphaned it.
3. **Amendment 5f was 1-of-3** — both remaining sites now name Tool 9 via Story 9.16. **And a fourth claim survives elsewhere** (below).

#### Findings this run added

- **🔴 `hash_validator.py` does not exist.** It was retired by Story 9.11, yet `architecture.md` still references it **four more times** beyond 5f's three named sites — and one of them still calls it *"Tool 4 — accuracy reporter (**REL-006 regression suite**)"*, the exact claim amendment 5f exists to refute. **Flagged, not fixed** — AC12 fences the exhaustive sweep to Story 9.10, and fixing the tree row means deciding whether to delete it, which is retired-tooling bookkeeping. Logged in `deferred-work.md` under a new *"Deferred BY Story 12.3"* section so it cannot be lost.
- **🔴 AC16's premise is wrong: `format:check` does NOT cover this story's files.** `.prettierignore` excludes `_bmad-output/` outright (*"BMad install + output (planning artifacts have their own conventions)"*). Verified with `prettier --file-info` → `{ "ignored": true }`. The gate was run and is clean, but **it checked none of this diff**; the markdown here is unformatted by tooling and was hand-checked instead.
- **🔴 The web vitest suite is non-deterministic, not merely red.** Two runs on the **identical** tree produced **134 failed / 191 passed** and then **132 failed / 193 passed**. AC16 says *"if one moves, that is a finding"* — the finding is that **this suite moves on its own**, by ±2, so its count cannot serve as a regression signal at that resolution. The second run reproduces the story's stated baseline exactly.
- **The mobile jest baseline in AC16 was stale by one.** `main` HEAD is **162 passed + 10 todo**, not 161 + 10. No mobile file appears in this diff, so the story could not have moved it.
- **12.2's forced-completion sum is 2.5770305, which rounds to 2.577, not the 2.576 its REPORT quotes** (→ 6.86×, not 6.85×). A ≤ 0.001 ms prose-rounding slip, not a data difference. The report quotes the JSON and says so.
- **`ac3_frame_diff.json`'s `diagnosis` string is stale** — it still reads *"MATRIX-ERROR-scale discrepancy (709 vs 601)"*, a heuristic label superseded by 12.2 §6's exhaustive offline constants proof. The report warns readers off it.
- **Thermal was collected, but not on the runs that produced the headline numbers.** `device_report_timing.json` and `device_report_all.json` carry no populated `thermal` key; only the later `device_seektest.json` does (status 0 / `NONE` / not throttled). The report states this and falls back to the two full runs' close agreement (33.428 vs 33.117) as corroboration, rather than implying a per-run thermal measurement.
- **The three per-classifier accuracy figures are unbacked by any artifact** — `parity_comparison.json` has no `ac14_classifier_accuracy` key. Carried as **`[U]`** throughout; no conclusion rests on them.

#### Discipline observed

- **The FORBIDDEN cloud-CV row is byte-identical.** Not re-worded, not modernized, not folded. Verified by diff.
- **Story 1.1's FROZEN JSI record and rung-0 verdict were not edited.** A forward pointer was added above them. 12.3 supersedes; 1.1 records.
- **No production code, no device re-measurement, no prose sweep, no schema change.** The diff is `_bmad-output/**` only.
- **`Decision #13`** follows the house shape (Choice / Rationale / Implementation / Cascading implications) and adds an explicit **alternatives-rejected** block — the CPU arm and the GLES mega-shader are each other's rejected alternative, and the rejection is on measurement.

#### Gates (AC16) — baseline re-verified first, then re-run

| gate | baseline (re-verified on `main`) | after this story | moved? |
| --- | --- | --- | --- |
| root `typecheck` | **3 errors, all `web`** (`EmailSignInForm.tsx`, `RegistrationForm.tsx`, `user-doc-strict.test.ts`) | **3 errors, identical** | **no** ✅ |
| mobile jest | 20 suites / **162 passed + 10 todo** *(story said 161; `main` HEAD is 162)* | unchanged — no mobile file in the diff | **no** ✅ |
| tooling pytest | **305 passed** | **305 passed** | **no** ✅ |
| web vitest | inherited red, **and flaky**: 134/191 then 132/193 on the same tree | same tree, same flake band; **132 / 193 reproduces the stated baseline** | **no** ✅ |
| `format:check` | clean | clean — **but `_bmad-output/` is `.prettierignore`d, so it checked none of this diff** | **no** ⚠️ |

#### Delivery status — DELIVERED

**Committed to `main` on 2026-09-15**, on Stephane's explicit go-ahead. One atomic commit, scope `docs(bmad)`, lowercase subject, **not pushed** (`main` is not auto-pushed — that stays Stephane's call). All seven files ride together; the fence held to `_bmad-output/**` through delivery.

**There is no post-merge tail.** Working directly on `main` removes the merge boundary that the Two-PR pattern existed to bridge, so `sprint-status.yaml`'s `review → done` flip is atomic with the commit rather than chasing it. AC17 and AC18 are `[x]` because the action that was their endpoint has been taken — not on precedent.

**Story status: `done`.** Next in the chain: **Story 12.4** (`ready-for-dev`, `needs-spike-or-split` — split it at create-story) and **Story 9.16**, whose landing is what gives REL-006 an instrument again.

### File List

| File | Action |
| --- | --- |
| `_bmad-output/architecture-spike-gpu-megashader.md` | **NEW** — the deliverable: the verdict, the traceable measured record, the PERF-002 / PERF-010 re-baseline, the five-row ladder audit, fixtures, the does-not-bind block, and follow-up work. |
| `_bmad-output/architecture.md` | MODIFIED — ladder rows (Pass / rung 1 / rung 2 / rung 3; FORBIDDEN untouched) + ladder-audit block; **`Decision #13`** (new); amendment 5d (rationale bullets rewritten, implementation bullet, coherence sentence, **banner removed**); amendment 5c (resolved — re-scoped); amendment 5f (2 remaining sites); SEC-007 entries 5 / 5a + status note; tree listing; PERF-010 NFR-coverage line; Decision Impact bullet; First Implementation Priority; FROZEN-record forward pointer; 5g handoff pointer. |
| `_bmad-output/prd.md` | MODIFIED — PERF-002 re-baselined (`RE-BASELINE PENDING` → measured figure + coverage caveat); PERF-010 disposition; Technical Success engine/ladder milestone. |
| `_bmad-output/epics-and-stories.md` | MODIFIED — Epic List sequencing note; Epic 12 title, status + verdict block, NFR line; Story 12.3 entry; **Story 12.4 sprint fit set to `needs-spike-or-split`** + re-scope. |
| `_bmad-output/sprint-status.yaml` | MODIFIED — `12-3` `ready-for-dev → in-progress → review`; **`9-16` and `12-4` → `ready-for-dev`**; **`9-9b` and `9-10` `blocked` → `backlog`**; `1-13` create-story unblocked (status unchanged); header + `last_updated` comment. |
| `_bmad-output/implementation-artifacts/deferred-work.md` | MODIFIED — the three homed items disposed with reasoning; `countSyncSamplesByScan()` carried forward; new *"Deferred BY Story 12.3"* section (5 items). |
| `_bmad-output/implementation-artifacts/12-3-engine-verdict-and-perf-rebaseline.md` | MODIFIED — this file: Status, AC checkboxes, Tasks/Subtasks, Dev Agent Record, File List, Change Log. |
