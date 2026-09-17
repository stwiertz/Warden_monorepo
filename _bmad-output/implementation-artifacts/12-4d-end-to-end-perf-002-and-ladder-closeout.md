# Story 12.4d: End-to-End PERF-002 Re-measurement + Ladder Closeout

Status: backlog

Sprint fit: `fits-in-one-sprint`. **One device measurement over the real pipeline, then documents.** Split out of Story 12.4 on 2026-09-17 (`/bmad-create-story` on 12.4). **Depends on Story 12.4c** — flip to `ready-for-dev` when 12.4c reaches `review`. **This story closes Epic 12 and releases Epics 5/6/7.**

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As **Stephane (solo dev / product owner)**,
I want **PERF-002 measured once over the real auto-slice pipeline — segmentation and thumbnail export included — and the Innovation #1 ladder's two outstanding rungs closed on that evidence**,
so that **the NFR stops resting on a detection-pass bench that excludes stages it actually scopes, provisional rung-0 resolves, rung 3 retires, and the ~20 stories of Epics 5/6/7 that have been held behind Epic 12 since 2026-07-16 are released.**

---

## ⚠️ Read This First — You Are Closing Three Things That Were Deliberately Left Open

Story 12.3 was scrupulous about what its numbers did and did not cover. **Three of its open items are yours, and each was left open for a stated reason, not by omission.**

### 1. 🔴 PERF-002's re-baseline covers the DETECTION PASS ONLY

The published figure is **44.879 s = 1.02% of a 4419.633 s source against a 220.98 s budget — MET by ~4.9×**. But [`architecture-spike-gpu-megashader.md`](../architecture-spike-gpu-megashader.md) → *PERF-002* states the honesty requirement plainly:

> The 44.9 s is a **detection-pass bench**, not an auto-slice run. PERF-002 scopes *auto-slice processing time*.

| excluded from every published wall clock | measured cost |
|---|---|
| keyframe index build | **2.290 s** by seek — *reported outside the wall by construction* |
| engine / EGL one-off setup | 4.846–15.202 ms engine, 47.042 ms EGL — *excluded by construction* |
| **segmentation** (round-boundary detection → round list) | **never measured** |
| **thumbnail export** | **never measured** |
| the rest of the pipeline (`processingPipeline.ts` stages, MMKV checkpointing, clip metadata) | **never measured** |

> *"**Story 12.4 must re-measure PERF-002 end to end over the real pipeline** before the NFR is treated as closed."*

**The margin is genuinely wide** — the excluded stages would have to cost roughly **four times the entire detection pass** to breach the NFR, which is why the re-baseline is defensible rather than optimistic. **That is a reason to expect a pass, not a reason to skip the measurement.** ~176 s of the 220.98 s budget is unused; measure it and find out.

### 2. 🔴 Rung-0 is PROVISIONAL, and it is provisional pending an INTEGRATION, not a measurement

The current Pass-row text, verbatim:

> `rung-0 provisional — engine bound on measurement (CPU rule evaluation on MediaCodec keyframe decode); PERF-002 MET and re-baselined at ≤ 1.02%; PERF-003 / PERF-004 UN-INSTRUMENTED; PERF-005 unmeasured; the pipeline binding is Story 12.4's. Cloud-fallback remains FORBIDDEN regardless.`

Three things were true together and had to be said together: only PERF-002 is measured; PERF-003/004/005 have no instrument; and *"with a real engine binding" was not yet true* — **12.2 shipped a bench, not a pipeline binding.** Stories 12.4a–c make it true.

**🔴 The precedent matters and cuts against sloppiness here.** Story 1.1's rung-0 was also provisional and was later *"accepted as final **without a measurement run**"* (2026-05-09, ship-and-observe). **This one is different:** *"provisional pending **an integration**, not a measurement — and Story 12.4 is scheduled, so it resolves rather than lapses."* **You are the scheduled resolution. Do not let it lapse into a second ship-and-observe acceptance** — the integration now exists, so the honest move is to state what is and is not met, with the same care 12.3 used.

### 3. 🔴 Rung 3 does not fire — but it retires only when the binding LANDS

> **Rung 3 does not fire. It is not yet retired**, because the *binding* — wiring the engine into `processingPipeline.ts` — is **Story 12.4's**, and the trigger is about shipping a real binding *within the V1 timeline*. **Rung 3 retires when Story 12.4 lands.** If 12.4 does not land in the V1 timeline, this rung fires on its own terms and auto-slice defers to V2.

12.4c landed it. **Retire the rung and say so on the evidence.**

### 🔴 And the one row you must not touch

> **FORBIDDEN — fall back to cloud CV. NEVER.** Breaks Innovation #1 (privacy + lower marginal cost). Architecture asserts this is forbidden regardless of spike outcome.

**Carried VERBATIM.** *"Do not re-word it, do not 'modernize' it, do not fold it into another row."* It is the only absolute prohibition in the ladder; every other rung has now been re-armed, re-labelled or answered, and **this one has not moved since it was written.** [INVARIANT 3] holds — the bound engine is on-device by construction.

---

## Acceptance Criteria

### AC0 — Kickoff decisions (resolve BEFORE Task 2; record verdicts in the Dev Agent Record)

- [ ] **AC0a — What "end to end" means, stated before you measure it.** PERF-002 scopes *"auto-slice processing time"*. **Decide and record the boundaries:** does the clock start at `runProcessingPipeline()` entry or at user tap? Does it include session-row I/O, MMKV checkpoint writes, SQLite `insertMapSegments`, and thumbnail export? **It must include segmentation and thumbnail export — those are the named gaps.** Does the one-off keyframe index sit inside or outside the wall (12.2 reported it **outside, by construction**; if you now report it inside, the number is not comparable to 44.879 s and you must say so). **Whatever you choose, the report states what is inside the number and what is not** — that discipline is why the 12.3 re-baseline is trustworthy, and it is the single most likely way to get this story wrong.
- [ ] **AC0b — Does PERF-002 close, or does it close with a caveat?** Either answer is acceptable; **leaving it ambiguous is not** (the standard 12.3 set for AC4/PERF-010). If the measured end-to-end figure is within budget, say the NFR is **closed** and strike the *"Story 12.4 must re-measure"* clause from `prd.md`. If something is still uncovered, name it and re-home it.
- [ ] **AC0c — Rung-0's final wording.** Resolve `provisional` → a final Pass-row verdict. **It cannot simply become "PASS":** PERF-003 / PERF-004 remain **UN-INSTRUMENTED** and PERF-005 **unmeasured** (the clip-export surface does not exist yet), and the Pass row's condition is *"all 4 PERF NFRs met on reference device with a real engine binding"*. **The binding half is now true; the four-NFR half is not.** Write a verdict that says both, the way the provisional one did. **Retiring a caveat you did not earn is exactly the defect 12.3 existed to remove.**
- [ ] **AC0d — Is Epic 12 `done`?** 12.4d is its last story. Decide and record: does `epic-12` flip `in-progress → done`, and is `epic-12-retrospective` run or left `optional`? *(Per STATUS DEFINITIONS, `in-progress → done` is manual when all stories reach `done`. Note 12.4a/b/c will be at `review` or `done` depending on delivery order — check, do not assume.)*

### The measurement

- [ ] **AC1 — 🔴 PERF-002 is measured end to end on the reference device, over the real pipeline.** Per AC0a. Reference device: **Poco X5 Pro 5G `22101320G` / SM7325 / Adreno 642L / Android 14 API 34** ([[project_warden_reference_device]] — **642L, never 619**; 619 is the pre-re-anchor SD695). Same fixture as every Epic 12 number: `videos/V2/2026-04-27 22-05-34.mp4`, **4419.633 s / 1061 keyframes**, against a **220.98 s** budget @ ≤5%.
  - **≥3 runs, report the median.** Run-to-run spread on this device is documented and real: the ffmpeg-kit control varied **13%** (38.068 s vs 33.660 s); idle `flush()` varied 1.786–3.555 ms.
  - **Collect thermal state per run.** Precedent: Story 12.2 (`1d4cc7a feat(mobile): evidence the ac0b amendment, collect thermal per run`). Prior observation: no throttling over an ~8-minute run — **recorded as a capability point, not a floor.** An end-to-end run is longer than a detection pass; do not assume it still holds.
- [ ] **AC2 — The three previously-unmeasured stages get their own numbers.** Segmentation, thumbnail export, and the remaining orchestration (checkpointing, SQLite, session I/O) reported **individually**, not just inside a total. The point of this story is to replace *"never measured"* with figures — a single end-to-end wall clock that does not decompose leaves the same question open one level up.
- [ ] **AC3 — 12.4a's decode-loop gain is confirmed at the pipeline level.** 12.4a measured the loop in isolation. The projection was **42.2 → ~17.1 ms/kf (~2.5×, ≈ 18.1 s whole capture, ≈ 0.41% of source)**, tagged **`[P]`**. Report what the real pipeline shows. **If the isolated gain did not survive integration, that is a finding worth more than a clean number** — say so and re-home it.
- [ ] **AC4 — 🔴 Every figure is traceable to a delivered artifact and labelled `[M]` / `[D]` / `[P]`.** Story 12.3's AC2 standard, and it is the reason Epic 12's evidence has held up under review. **No figure may be re-derived, rounded differently, or restated from an AC's prose.** Archive the raw JSON (suggest `apps/mobile/bench/12-4d/`). Carry these in their corrected form and **do not restate the superseded versions**:
  - decode strategy A / A′ = **32.937 / 62.820** ms/kf — **not** 33.68 / 116.45
  - GL share of the wall was **6.0% / 7.3%** — **not** 1% (that figure nested the GL stages inside `decode`)
  - *"real decoding is ~4 ms"* is **`[D]`, derived** (`62.8 − 58.5`), with **~11.5 ms of the 22.1 ms output wait unattributed** — it is *not* all decoding
  - the capture is **1 h 13 min 40 s**, **not** the "~2 h" the 12.1/12.2 AC text says

### The documents

- [ ] **AC5 — `prd.md`'s PERF-002 is updated with the end-to-end figure.** Per AC0b. The current entry carries the detection-pass number plus *"🔴 Read what is inside this number"* and the explicit *"Story 12.4 must re-measure PERF-002 end to end over the real pipeline before this NFR is treated as closed."* **Replace the caveat with the measurement; do not simply append.** Keep the `< 10 s` framing intact: it is an **aspiration, not an acceptance criterion**, it is **missed**, and it *"is not written up here as a failed NFR"* — **and do not write the met NFR up as a triumph of the engine either**, which is the symmetric error 12.3 guarded against.
- [ ] **AC6 — Rung-0 resolves in both places it is written.** Per AC0c. [architecture.md](../architecture.md) → *Pre-PRD performance spike* → *Spike outcomes & ladder* (the Pass row) **and** [`architecture-spike-gpu-megashader.md`](../architecture-spike-gpu-megashader.md) → *Ladder rung verdict* → *Rung-0 (Pass row)*. **Both, with the same words.** A resolved verdict in one document and a provisional one in the other is the class of drift Epic 12 spent three stories removing.
- [ ] **AC7 — Rung 3 is retired, on the evidence.** Per point 3. Both documents. Record **what landed** (the pipeline binding, by Stories 12.4a–c) and **when**, so the retirement is auditable rather than asserted.
- [ ] **AC8 — Rung 1's re-armed remedy is re-checked against the measurement, and rung 2 stays labelled.**
  - **Rung 1** was re-armed by 12.3 with a two-step remedy: **1a** reduce per-keyframe decode-loop overhead (*"try this first"*, no product cost) and **1b** decimate keyframes (real cost: granularity falls from 4.17 s to N × 4.17 s). **🔴 Story 12.4a has now SPENT step 1a.** The rung must say so — a remedy already applied is not available as a remedy. **Re-check that 1b is still armed and still engages the measured cost** (decode is ~94% of the wall and scales linearly with keyframe count). `mobile-AUTO-SLICE-001`'s *"with reduced sampling on weak hardware"* clause attaches to **1b** and survives intact.
  - **Rung 2** stays `TRIGGER UN-INSTRUMENTED (2026-09-15)`. PERF-003 / PERF-004 have never been measured, the surfaces do not exist, and arming it means building a view-mode / cold-start timing instrument **which no story owns**. Its natural home is **Stories 5.4 / 5.5 / 6.6**, with the surfaces. **Do not arm it here, and do not quietly drop the label.**
- [ ] **AC9 — The FORBIDDEN row is carried VERBATIM.** Per the box above. Byte-identical. Not re-worded, not modernized, not folded into another row. Verify it byte-for-byte before delivery — 12.3 did.
- [ ] **AC10 — PERF-010 is NOT re-opened.** It **stays a soft target**. *"A single-device run cannot bind a minimum-supported-device floor"* — a floor is a claim about the device **population**; binding it needs a device matrix **which no story owns and none is proposed**. The 2026-05-09 ship-and-observe softening is a **product decision, not a measurement outcome**, and nothing you measure here reverses it ([[project_warden_ar_spike_binding_only]]). **Your end-to-end run adds a second capability point, recorded as evidence. That is all it does.**
- [ ] **AC11 — The spike report's *Follow-up work required* table is closed out.** All six rows were re-homed to Story 12.4: `TIMEOUT_US` · per-keyframe `flush()` · `countSyncSamplesByScan()` · GLES/EGL removal · end-to-end PERF-002 · wire the engine. **Mark each with the story that took it (12.4a / 12.4b / 12.4c / this one) and its outcome.** A follow-up table that still reads *"Story 12.4 will"* after Story 12.4 has landed is the exact stale-pointer defect Epic 12 kept finding.

### Downstream

- [ ] **AC12 — 🔴 Epics 5 / 6 / 7 are released in the epics doc.** They are *"HELD behind Story 12.3 (engine verdict) + Story 12.4 (mobile consumer rewrite)"* — **order, not state**, recorded as prose, not as a status (`blocked` is a story-level status only; Story 1.9's precedent). The 2026-09-15 update already narrowed it to *"The hold on Epics 5/6/7 is now single-gated on Story 12.4."* **Lift the hold** in [epics-and-stories.md](../epics-and-stories.md)'s Epic List sequencing addendum and in Epic 12's charter block. ~20 stories start on this AC.
- [ ] **AC13 — Downstream statuses set in `sprint-status.yaml`, with the reason in the comment.** At minimum: `epic-12` per AC0d; the four `12-4*` keys; and the Epics 5/6/7 release. **Also check, do not assume:** `9-16` (`ready-for-dev` — it re-points Tool 9 and `video_test.py` at the bound engine, and **without it REL-006 has no instrument at all**), `9-9b` and `9-10` (both released to `backlog` by 12.3), and `1-13` (released for create-story; **12.4c left it a named seam** — carry that forward in the comment).
- [ ] **AC14 — deferred-work items disposed.** [deferred-work.md](deferred-work.md) → *Deferred BY Story 12.3*: **"PERF-002 has not been measured end to end"** is this story's, close it with the measured outcome. **"Ladder rung 2 has no instrument"** — confirm it is still re-homed to 5.4/5.5/6.6, not closed. Check the `min_ratio` float32-vs-float64 item (12.4c's) and the three `[U]` per-classifier accuracy figures were disposed by 12.4c; if not, re-home rather than inherit silently.

### Fences, gates, delivery

- [ ] **AC15 — Scope fence.** 12.4d does **NOT**: write production code (this is a measurement-and-documents story — **if you find yourself editing Kotlin or a detector, stop: it belongs in 12.4a/b/c or in a new story**) · re-open Story 1.1's FROZEN JSI record or its rung-0 verdict (**12.3 supersedes, 1.1 records** — add a forward pointer, do not edit the record; [[project_warden_ar_spike_binding_only]]) · bind PERF-010 (AC10) · arm rung 2 (AC8) · claim REL-006 (**9.9b's, instrumented via 9.16**) · run the exhaustive pHash→engine prose sweep (**9.10's**) · re-point Tool 9 or `video_test.py` (**9.16's**) · touch `map_config*`, zone data or `contracts/`. Verify with `git status --porcelain`: outside `apps/mobile/bench/12-4d/`, the diff should be `_bmad-output/**` and `docs/**` only.
- [ ] **AC16 — Gates green.** `pnpm typecheck && pnpm test && pnpm format:check` from the repo root. **Re-verify the baseline first** — take 12.4c's recorded numbers, not 12.3's; 12.4b and 12.4c both legitimately moved the jest count. **🔴 `format:check` does NOT cover `_bmad-output/`** — `.prettierignore` excludes it (`npx prettier --file-info` on any file there returns `{"ignored": true}`). This story is nearly all markdown under `_bmad-output/`, so **a green `format:check` says nothing about your diff.** Do not record it as evidence that the deliverable is clean; run it only to confirm you did not disturb something outside that tree. **The web vitest suite is FLAKY, not merely red** — 134/191 then 132/193 on the *identical* tree — so its count cannot be a regression signal at ±2.
- [ ] **AC17 — Committed to `main`.** Direct to `main`, no branch, no PR ([[project_warden_main_branch_workflow]]). Lowercase subject; scope `docs(bmad)` per the `43df5a9 docs(bmad): bind the cpu detection engine, reject the gpu mega-shader (story 12.3)` precedent. **Not pushed** — `main` is not auto-pushed. `sprint-status.yaml`, `epics-and-stories.md`, `prd.md`, `architecture.md`, `architecture-spike-gpu-megashader.md` and `deferred-work.md` all ride in the **same** commit: working directly on `main` removes the merge boundary the Two-PR pattern existed to bridge ([[feedback_two_pr_docs_execution]]), so there is no post-merge tail. **Check `git status` for foreign edits first** ([[project_warden_shared_doc_commit_boundary]]).
- [ ] **AC18 — `sprint-status.yaml`: `12-4d-…` `in-progress → review → done`**, flipped in the same commit as the deliverable. Per [[feedback_ac_checkbox_tighten]] this may be `[x]` rather than demoted **only because there is no post-merge action left** — the commit *is* the delivery. **If any part of this story's endpoint depends on an action after the commit, demote that AC to `[ ]` instead of closing it on precedent.**

---

## Tasks / Subtasks

- [ ] **Task 1 — Read what you are closing.** (AC: 0, 5, 6, 7, 8) [`architecture-spike-gpu-megashader.md`](../architecture-spike-gpu-megashader.md) → *PERF-002 re-baseline* and *Ladder rung verdict* **in full**; [architecture.md](../architecture.md)'s ladder table; [prd.md](../prd.md)'s PERF-002 / PERF-010; the Dev Agent Records of 12.4a / 12.4b / 12.4c.
- [ ] **Task 2 — Resolve AC0.** (AC: 0a–0d) **AC0a before you measure** — deciding the boundary after seeing the number is how a measurement stops being evidence.
- [ ] **Task 3 — Instrument and measure.** (AC: 1, 2, 3)
  - [ ] Extend or re-use the `[PERF-002]` per-stage marks already in `processingPipeline.ts` (`__DEV__`-gated, persisted to MMKV `processing.<sid>.perf002`) so segmentation and thumbnail export decompose.
  - [ ] ≥3 full runs on the reference device. Median. Thermal per run.
  - [ ] Archive raw JSON.
- [ ] **Task 4 — Write up the measurement.** (AC: 4, 5) Every figure `[M]`/`[D]`/`[P]` and traceable. State what is inside the number and what is not.
- [ ] **Task 5 — Close the ladder.** (AC: 6, 7, 8, 9) Rung-0 final · rung 3 retired · rung 1 step 1a marked spent · rung 2 still labelled · **FORBIDDEN row byte-verified**. Both documents, same words.
- [ ] **Task 6 — Close the follow-up table and the deferred register.** (AC: 11, 14)
- [ ] **Task 7 — Release downstream.** (AC: 12, 13, 0d) Lift the Epics 5/6/7 hold; set statuses with reasons.
- [ ] **Task 8 — Deliver.** (AC: 15–18) Fence check → gates → commit → sprint-status.

---

## Dev Notes

### The arithmetic you are re-doing, and the numbers to beat

| | value | provenance |
|---|---|---|
| source duration | **4419.633 s** = 1 h 13 min 40 s | `ac1_device_profile.mediacodec.duration_us = 4419633333` **[M]**, corroborated by 1061 × 4.1667 s GOP **[D]** |
| **PERF-002 budget @ ≤ 5%** | **220.98 s** | **[D]** |
| published re-baseline (**detection pass only**) | **44.879 s = 1.015%** | Path P `total_wall_ms` **[M]** |
| *(the rejected GPU zero-copy path, for reference only)* | *35.467 s = 0.802%* | **[M]** |
| projected bound configuration, never run end to end | **~42.0 s = 0.95%** | **[P]** |
| projected **with 12.4a's fixes** | **~18.1 s = 0.41%** | **[P]** |

The `[P]` construction, reproduced so you can check whether it held:

```
      Path P wall                    42.299 ms/kf   [M]
    − Path P disjoint GL stages       3.068 ms/kf   [M]   ← 12.4b removed these
    + AC12 CPU rule-eval arm          0.376 ms/kf   [M]   ← 12.4c wired this
    = 39.607 ms/kf  × 1061 kf  =  42.0 s  =  0.95% of source      [P]

      probe wall                      42.2 ms/kf    [M]
    − flush() per keyframe            14.5 ms/kf    [M]   ← 12.4a
    − TIMEOUT_US sleep                10.6 ms/kf    [M]   ← 12.4a
    = ~17.1 ms/kf  × 1061       ≈  18.1 s  =  0.41% of source      [P]
```

**Neither has been measured. You are the first to run either.** The second is *"~10× more headroom than the entire engine question was ever worth (2.73 s) — that comparison is the single most decision-relevant sentence Epic 12 produced."* **Report what you measure, not what the projection says**, and if the two disagree, the disagreement is the finding.

### Why the `< 10 s` framing must be handled carefully

`< 10 s` is **not an acceptance criterion** — not in `prd.md`'s PERF-002, and 12.2's AC15 says so explicitly. It is **missed**: the best measured figure is 35.5 s (on the rejected path) and the bound configuration projects to ~42 s, or ~18 s with 12.4a's fixes. **It is not written up as a failed NFR**, consistent with the 2026-05-09 ship-and-observe decision that downgraded the numeric PERF budgets to soft UX targets.

**And it is not the engine's fault** — rule evaluation is 6–7% of the wall, and ~25 ms of every 42 ms keyframe was per-keyframe pipeline teardown plus a dequeue timeout we chose ourselves. **Both halves of the framing are load-bearing: do not report a miss as a failure, and do not report the met NFR as a triumph of the engine.**

### Epic 12's yield, for the closing write-up

If AC0d flips the epic `done`, the record should say what the epic actually produced. From the verdict: *"The epic's founding premise is falsified, and that is its most valuable product."* The chain was *PERF-002 is unacceptable → the per-frame CPU `cv2.inRange` path is the ceiling → a GPU mega-shader removes it.* **Link 2 is false.**

What survived the rejection intact: the measured decode decomposition · the bit-exact integer HSV evaluator (*"which is what makes the CPU arm trustworthy — the two arms check each other"*) · `WardenRulePacker` · the working MediaCodec decode path **with the count assertion that caught a silent 2-vs-1061 failure** · and a ~2.5× decode-loop speedup target with two cheap fixes.

*"What Epic 12 refutes is a mechanism, not the decision to ask. The engine question had to be answered before ~20 stories of Epics 5/6/7 were built on it."*

### What this story must NOT claim

- **REL-006 (≥95% map ID on a held-out set)** — **9.9b's**, instrumented by Tool 9 via **9.16**. Nothing in Epic 12 measures accuracy on an unseen test set.
- **In-sample parity is not accuracy-in-the-world.** The 0 / 357,244 result is a **parity target** — the device reproducing the PC reference on the corpus the rules were tuned against. **There is no holdout.**
- **The three per-classifier accuracy figures are `[U]`** — unbacked by any delivered artifact. 12.3 carried them labelled and rested no conclusion on them. **Do not promote them to `[M]`.**
- **PERF-003 / PERF-004 / PERF-005** — unmeasured, no instrument, soft UX targets.
- **Amendment 5c does not lapse.** MediaCodec keeps decode **Android-only by construction** (iOS = VideoToolbox) even with no GLES. **Re-scoped, not reverted.** 12.4b's removal does not change this — it only removes the GPU-compute half of a future iOS port estimate.

### Delivery pattern

This is a **decision-and-documents story**, the same shape as Story 12.3 — which is the template worth following: it published its evidence, labelled every figure, named what it did not bind, and flipped its own status in the same commit as its deliverable. Its AC17/AC18 note the reasoning: working directly on `main` removes the merge boundary the Two-PR pattern existed to bridge, so the commit *is* the delivery and the flip is atomic with it ([[project_warden_main_branch_workflow]], [[feedback_two_pr_docs_execution]]).

**One caveat carried forward:** [[project_warden_shared_doc_commit_boundary]] — the post-merge pass is often not file-isolatable because foreign multi-story edits co-mingle in `sprint-status.yaml` and `deferred-work.md`. **Check `git status` before committing**; if foreign edits are present, ship this story's files alone and say what you deferred.

### Reference device

**Poco X5 Pro 5G `22101320G` / SM7325 / Adreno 642L / Android 14, API 34** ([[project_warden_reference_device]]). **Adreno 642L, never 619** — 619 is the SD695, the pre-re-anchor device. *(Note [architecture.md](../architecture.md) still carries a third and fourth stale device identity at `:847` and `:2100` — **flagged, not fixed; that is Story 9.10's scrub.** Do not fix them here, and do not cite them.)*

### References

- [Source: _bmad-output/architecture-spike-gpu-megashader.md] — *PERF-002 re-baseline* (the coverage caveat, the two `[P]` constructions), *Ladder rung verdict* (all five rows), *What this does NOT bind*, *Follow-up work required*
- [Source: _bmad-output/architecture.md] — the Innovation #1 ladder table; [Decision #13](../architecture.md) *Cascading implications* (*"Rung-0 is provisional pending Story 12.4"*); the NFR-driver bullet
- [Source: _bmad-output/prd.md] — PERF-002 (*"Story 12.4 must re-measure PERF-002 end to end"*), PERF-010 (soft-target disposition), REL-006, `mobile-AUTO-SLICE-001`'s reduced-sampling clause
- [Source: _bmad-output/epics-and-stories.md] — the Epic List addendum holding Epics 5/6/7; Epic 12's charter block and verdict banner
- [Source: _bmad-output/implementation-artifacts/12-3-engine-verdict-and-perf-rebaseline.md] — the template for a decision-and-documents story; its AC2 traceability standard and AC5 ladder audit
- [Source: _bmad-output/implementation-artifacts/deferred-work.md] — *Deferred BY Story 12.3*, the items AC14 disposes

---

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
