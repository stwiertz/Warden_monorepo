# Story 12.4a: Decode-Loop Optimisation

Status: done

Sprint fit: `fits-in-one-sprint`. **Kotlin + on-device measurement. No TypeScript, no pipeline wiring, no GLES removal.** Split out of Story 12.4 on 2026-09-17 (`/bmad-create-story` on 12.4) — see [epics-and-stories.md](../epics-and-stories.md) → *Story 12.4 (SPLIT 2026-09-17 → 12.4a + 12.4b + 12.4c + 12.4d)*.

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As **Stephane (solo dev / product owner)**,
I want **the three decode-loop defects Epic 12 measured — our own `TIMEOUT_US`, the per-keyframe `flush()`, and the 62 s `countSyncSamplesByScan()` — fixed and re-measured on the reference device**,
so that **the ~25.1 of 42.2 ms per keyframe that is *ours to fix* is actually reclaimed, and the bound engine ships on a decode loop that is ~2.5× faster than the one the POC benched.**

---

## ⚠️ Read This First — You Are Fixing the Thing Epic 12 Went Looking For and Did Not Expect to Find

**Epic 12 set out to prove that a GPU mega-shader would fix PERF-002. It measured the opposite, and found the real lever by accident.** Read [`architecture-spike-gpu-megashader.md`](../architecture-spike-gpu-megashader.md) → *Measured results* and *Follow-up work required* before writing a line.

Three facts frame this story, all **measured** on the Poco X5 Pro 5G:

1. **Rule evaluation was never the bottleneck.** It is **6.0–7.3% of the wall** on the GPU and **~1%** on the CPU. Choosing CPU over GPU moved a 35–45 s run by **~2.7 s**.
2. **The decode loop is worth ~26 s on the same run — roughly 10× what the entire engine question was worth.** That comparison is, verbatim, *"the single most decision-relevant sentence Epic 12 produced"* ([spike report](../architecture-spike-gpu-megashader.md) → *PERF-002*).
3. **Both halves of it are defects in our own code, not platform costs.** `flush()` costs **14.5 ms in the loop** against **1.8–3.6 ms on an idle codec** — a factor of 4 to 8, so the expense is the `END_OF_STREAM` → flush state transition, not the HFI round trip. And `TIMEOUT_US = 10_000` costs **10.6 ms/keyframe** because the probe counts **1.02 `INFO_TRY_AGAIN_LATER` per keyframe** — almost exactly one full 10 ms sleep each time, against a timeout we chose ourselves.

**The measured decomposition you are attacking** ([12.2 REPORT §5](../../apps/mobile/bench/12-2/REPORT.md), `device_probe_flush.json{,_run2,_run3}`, 100 keyframes × 3 runs, ±0.4 ms):

| stage | ms/keyframe | share | yours? |
|---|---|---|---|
| `seekTo` | 4.4 | 10 % | no |
| **`flush()`** | **14.5** | **34 %** | **YES — AC2** |
| queue IDR → first output | 22.1 | 52 % | partly |
| ⤷ *of which sleeping in `dequeueOutputBuffer`* | ***10.6*** | *25 %* | **YES — AC1** |
| accounted | 41.0 / 42.3 | 97 % | |

**Target, and it is PROJECTED not promised:** `42.2 − 25.1 = ~17.1 ms/kf → ~18.1 s` whole capture, **≈ 0.41% of source duration**, a **~2.5×** decode-loop speedup. Tagged `[P]` in the spike report: *"Neither fix has been attempted or measured."* **You are the first person to attempt either.** Report what you measure, not what the projection says.

---

## 🔴 Four Traps That Have Already Cost Build/Flash Cycles

Every one of these is a **measured** finding from Story 12.2, each of which cost a build/flash cycle ([12.2 story](12-2-android-poc-gles-port.md) → *Bugs found and fixed during the port*). They are why this story is not "two lines".

1. **🔴 THE FILE'S OWN HEADER IS STALE AND WILL MISLEAD YOU.** [`WardenKeyframeDecoder.kt:22-33`](../../apps/mobile/plugins/kotlin/WardenKeyframeDecoder.kt#L22-L33) says **A′ (single forward pass, sync-filtered demux) is "what shipped"**. **It is not what is bound.** [Decision #13](../architecture.md) binds *"absolute `SEEK_TO_CLOSEST_SYNC` per keyframe (**strategy A, 32.937 ms/kf**, against A′'s **62.820**)"*. A′ is the **slower** path — it drags 2.3 GB through the extractor because `NuMediaExtractor::fetchTrackSamples` reads sample **data** on every `advance()`, in batches of up to 8. **Your target is `decodeKeyframesBySeek()` ([:474](../../apps/mobile/plugins/kotlin/WardenKeyframeDecoder.kt#L474)), not `decodeKeyframes()` ([:617](../../apps/mobile/plugins/kotlin/WardenKeyframeDecoder.kt#L617)).** AC8 makes you fix the comment.
2. **🔴 A SINGLE QUEUED SAMPLE DECODES TO NOTHING.** A hardware decoder's pipeline depth means feeding exactly one sync sample and polling yields `INFO_TRY_AGAIN_LATER` **forever** — which *presents* as "the seek landed off a sync point", the wrong diagnosis entirely. That is **why** `BUFFER_FLAG_END_OF_STREAM` is queued after each keyframe ([:548](../../apps/mobile/plugins/kotlin/WardenKeyframeDecoder.kt#L548)): to force the drain. **And that is why `flush()` is there** ([:524](../../apps/mobile/plugins/kotlin/WardenKeyframeDecoder.kt#L524)) — to clear the EOS state for the next iteration. **The flush and the EOS are one mechanism. You cannot remove one without replacing the other.** This is the whole engineering content of AC2 and is what AC0a exists to decide.
3. **🔴 `MediaCodec.start()` after `flush()` THROWS in synchronous mode** — `IllegalStateException: start() is valid only at Configured state; currently at Running state`. The documented "call `start()` after `flush()`" rule applies to **asynchronous** mode only; in dequeue-based mode `flush()` leaves the codec Running. MEASURED on `c2.qti.avc.decoder` / Android 14. The code already knows this ([:525](../../apps/mobile/plugins/kotlin/WardenKeyframeDecoder.kt#L525) *"NB: no start() after flush()"*) — do not "restore" it.
4. **🔴 THE COUNT ASSERTION EARNED ITS KEEP — DO NOT WEAKEN IT.** The incremental scan originally prescribed (`seekTo(lastPts + 1, SEEK_TO_NEXT_SYNC)` in a loop) **stops advancing after the second sync sample**, reporting **2** keyframes against a ground truth of **1061** (`device_seektest.json` → `ac0b_prescribed_incremental_scan`). Without the assertion the bench would have reported a self-consistent `2 == 2` and *"a beautiful ms/keyframe figure computed over two frames"*. **Any speedup you measure is worthless unless the count still comes out 1061.** AC4.

---

## Acceptance Criteria

### AC0 — Kickoff decisions (resolve BEFORE Task 2; record verdicts in the Dev Agent Record)

- [x] **AC0a — 🔴 How the per-keyframe `flush()` is eliminated.** **VERDICT: OPTION A**, with an explicit Path-Z carve-out and one `END_OF_STREAM` per RUN. ***k* = 8, MEASURED by a 5-point sweep** (k=1 **WEDGES**, k=2 20.909, k=4 8.062, **k=8 7.706**, k=16 7.725 ms/kf; 0 PTS mismatches at every working depth). See the Dev Agent Record and [REPORT §3](../../apps/mobile/bench/12-4a/REPORT.md). This is the story's real design decision, not a parameter. Today the loop is: `seekTo` → `flush()` → queue sample → queue `EOS` → drain → repeat. The spike's licence is *"an IDR resets the DPB **by definition**, so no flush is required for correctness"*.
  - **Option A (RECOMMENDED) — pipeline several IDRs, drop the EOS round-trip entirely.** Queue *k* keyframes' samples back-to-back (each obtained by an absolute `SEEK_TO_CLOSEST_SYNC`, so each is an IDR and self-contained), never signalling EOS, and drain outputs as they arrive, **matching output buffers to requested keyframes by PTS** rather than by arrival order. Removes `flush()` (14.5 ms) *and* the EOS round-trip in one change. *Costs:* you must choose *k*, hold *k* frames' worth of output in flight, and handle the tail drain at end-of-list. **Decide and record *k* and how you picked it.**
  - **Option B — keep EOS, remove only the flush.** Not viable as stated: after an EOS the codec must be reset before it accepts more input, and `start()` after `flush()` throws in synchronous mode (trap 3). **If you believe there is a variant that works, state the mechanism and prove it on device — do not assume it.**
  - **Option C — bank AC1 only, defer AC2.** Reclaims ~10.6 of the ~25.1 ms/kf. Legitimate fallback **only** if Option A is measured not to work; if taken, AC2 is demoted to `[ ]` and re-homed with the measured reason, per [[feedback_ac_checkbox_tighten]].
- [x] **AC0b — The new `TIMEOUT_US` value, and what it does to the wedge guard.** **VERDICT: `1_000L`.** The caps are now declared as DURATIONS and converted to polls, so they no longer derive silently from the timeout: `MAX_SPINS` 500→5000 and `MAX_SPINS_BEFORE_EOS` 2000→20000, leaving the wedge budget at **5 s and 20 s, unchanged**. Today `TIMEOUT_US = 10_000L` ([:794](../../apps/mobile/plugins/kotlin/WardenKeyframeDecoder.kt#L794)). Options: a short fixed timeout (e.g. `1_000L`), `0L` with a bounded spin, or a blocking `-1L`. **🔴 The spin guard at [:804](../../apps/mobile/plugins/kotlin/WardenKeyframeDecoder.kt#L804) derives its wedge cap FROM `TIMEOUT_US`** (*"at TIMEOUT_US = 10 ms a poll, this caps the wedge at ~20 s"*). Changing the timeout silently changes that cap by the same factor. **Re-derive the spin limit so the wedge cap stays in the same order of magnitude, and say so in the comment.** A hang that used to bail in 20 s must not become one that bails in 2 s (false failure) or 200 s (a wedged run).
- [x] **AC0c — Keyframe-index source.** **VERDICT: the seek-built PTS list** (`syncSamplePtsListBySeek`) — already what the loop consumes. `countSyncSamplesByScan()` is RETAINED as the bench-only independent ground truth AC4 asserts against; an `stss` reader was not written because a second seek-derived index would not be independent. `countSyncSamplesByScan()` ([:189](../../apps/mobile/plugins/kotlin/WardenKeyframeDecoder.kt#L189)) costs **62.070 s** and **MUST NEVER SHIP**. Two replacements: the **seek-built PTS list** (`syncSamplePtsListBySeek()` [:433](../../apps/mobile/plugins/kotlin/WardenKeyframeDecoder.kt#L433), **2.290 s**, already implemented, already the list the decode loop consumes — **RECOMMENDED**) or a direct `stss` box read. Record the choice and why. *(Both count 1061 and `counts_agree` is ✅ in `ac0b_keyframe_index`.)*
- [x] **AC0d — Which bench modes are the before/after instrument.** **VERDICT: `flushprobe` (3 runs, median) + `timing` (3 runs) on the same fixture and device.** 🔴 **The baseline was RE-MEASURED today on the current tree, not inherited** — the APK was rebuilt and reinstalled first, and every baseline figure reproduced inside 12.2's documented spread. Diffed against `device_probe_flush.json{,_run2,_run3}` and `device_report_timing.json`. `flushprobe` produced the decomposition this story attacks and `timing` produced the wall clock. **You need a comparable run on the same fixture, same modes, same device.** Record the exact invocation and which JSON you will diff against (`device_probe_flush.json{,_run2,_run3}` and `device_report_timing.json`). Note run-to-run spread is real: the ffmpeg-kit control alone varied **13%** between runs (38.068 s vs 33.660 s), and `flush()` idle cost varied 1.786–3.555 ms across three runs. **Take ≥3 runs and report the median, as 12.2 did.**

### The fixes

- [x] **AC1 — `TIMEOUT_US` no longer costs ~10.6 ms/keyframe.** Per AC0b. `10_000L → 1_000L`. `timeout_us_used` **1000**; try-again count **1.03 → 7.39** per keyframe; `decode_probe` wall **41.982 → 33.442 ms/kf (−8.540)**; `queue_to_first_output_ms_median` **21.891 → 13.389 (−8.502)**. Median of 3 runs each, same structure, same fixture, thermal `NONE`.

  > 🔴 **AMENDED ON EVIDENCE 2026-09-17 — THE STATED SUCCESS CRITERION DOES NOT HOLD, AND THE FIX IS GOOD ANYWAY. BOTH FACTS MATTER.** The AC asked for "`INFO_TRY_AGAIN_LATER` sleep time per keyframe drops materially from the baseline 10.6 ms". **MEASURED: 10.697 → 9.772 ms/kf — a 0.9 ms move against a 10.6 ms claim. It did not materially drop.** The AC was written on a projection about *where* the 10.6 ms went, and the projection is wrong.
  >
  > **What the 10.6 ms actually was.** Not a decoder slow to answer. The loop queues the IDR, polls output, gets `TRY_AGAIN`, and **sleeps a full timeout before coming back round to queue the `END_OF_STREAM` the decoder is waiting for** — trap 2 says one queued sample decodes to nothing. The sleep was not waiting on hardware; **it was withholding the input hardware needed.**
  >
  > **Why the named counter did not move.** At 1 ms we poll ~7× where we polled ~1×, so time accumulated *inside try-again calls* is ~the decoder's real latency either way. The −8.5 ms/kf comes from the **blocking** `dequeue*` calls getting 10× finer granularity, and it lands in `queue_to_first_output` — exactly where a withheld-EOS effect belongs.
  >
  > Amended **inline** rather than left in the Dev Agent Record, per 12.2's AC0b precedent: Story 12.4b/c/d inherit this decode path, and "reduce the poll timeout to cut try-again sleep" is an active trap for the next reader. Evidence: [`bench/12-4a/REPORT.md` §2](../../apps/mobile/bench/12-4a/REPORT.md).
- [x] **AC2 — The per-keyframe `flush()` is gone from the bound decode path.** Per AC0a. `decodeKeyframesBySeek()` no longer calls `flush()` once per keyframe. Measured headroom to reclaim: **up to ~14.5 ms/kf → ~15.4 s over 1061 keyframes.** *(If AC0a resolves to Option C, demote this to `[ ]`, record the measured reason, and re-home it in [deferred-work.md](deferred-work.md).)*
- [x] **AC3 — `countSyncSamplesByScan()` is not reachable from any shipping path.** **KEPT as a bench-only assertion** (it earned that right — trap 4) and made unreachable BY CONSTRUCTION, not by coincidence. Two changes: `probe()`'s `scanSyncSamples` now defaults to **`false`**, and `deviceProfile()` — which the RN bridge's `describeDevice` reaches — **never scans at all** (it used to read `scanSyncSamples = knownSyncCount < 0`, i.e. "if you do not already know, go and spend 62 s"; it was saved today only by `describeDevice` happening to pass a null video path, which **Story 12.4c would have broken**). **No caller anywhere now passes `scanSyncSamples = true`**; the walk is reachable from exactly two explicit bench blocks (`all`/`timing`, `seektest`). Unmissable KDoc banner added. Per AC0c. It may **remain in the file as a bench-only assertion** — it earned that right (trap 4) — but it MUST be unreachable from the path Story 12.4c wires into the pipeline, and its KDoc must say so in one unmissable line. **Deleting it outright is also acceptable** if the count assertion is preserved by other means (AC4). Record which you did.
- [x] **AC4 — 🔴 The keyframe count assertion still fires and still reads 1061 == 1061.** **ACTUAL COUNTS, full capture, both colour paths: `n_keyframes_decoded` = 1061, `keyframe_count_expected` = 1061, `keyframe_count_matches` = true.** The ground truth is still the independent sample-table walk (1061), and the seek-built index still agrees (`counts_agree` true). Not "assertion passed" — the numbers are in `after_timing_run{1,2,3}.json`. Non-negotiable. Whatever restructuring AC0a produces, the decoded-keyframe count is still asserted against `WardenDecoderProfile.syncSampleCount` and still agrees. **A run that decodes fewer keyframes faster is not a speedup, and this assertion is the only thing standing between you and reporting one.** Report the actual counts, not "assertion passed".
- [x] **AC5 — 🔴 Bit-parity is preserved: 0 per-rule disagreements.** **BOTH the check AC5 names and the check AC5 actually needs.**

  **(a) As written.** Fresh `parity` run + `pc_reference.py compare` against the pinned `pc_reference_fires.json`: **0 frames with disagreement, 0 total rule disagreements, 357 244 rule-frame decisions, `frame_sets_identical` true** — reproduces the banked baseline. The device's raw `parity_fires.json` is **byte-identical to 12.2's** (sha256 `0348662e95f444d3…`).

  > 🔴 **AMENDED ON EVIDENCE — THE NAMED INSTRUMENT CANNOT DETECT THE NAMED FAILURE MODE.** AC5 calls this run "the tripwire for a pipelining bug that returns frames out of order". It is not one. `parityRun` pushes the **labeled PNG corpus** through `DIRECT_RGB`; it never opens the video and never calls `decodeKeyframesBySeek`, so a decode-order defect is invisible to it. It is still worth running — it proves the engine, LUT and colour conversion are untouched — but presenting it as the order check would have looked like evidence and been none, which is exactly the mistake 12.2's `seektest` made and logged.

  **(b) The tripwire that does work.** `timing_fires_bit_parity_seek_1061.json` carries one row per decoded keyframe — a 134-bit rule mask over that keyframe's **pixels**, keyed by **the PTS the decoder reported**. 12.2's copy was pulled off the device before the first new run could overwrite it, and all three full-capture runs were diffed against it: **1061 rows, 1061 shared PTS, 0 changed masks, 0 duplicate PTS, 0 missing, 0 extra, delivery order identical — 142 174 rule-frame decisions per run, 426 522 across three, 0 disagreements.** Comparator and results: `compare_fire_rows.py`, `fire_row_comparison_run{1,2,3}.json`. The decode change must not move a single pixel. Re-run the parity comparison against the pinned PC reference (`apps/mobile/bench/12-2/pc_reference_fires.json`, 2666 frames) and reproduce **0 disagreements**. The banked baseline is **0 / 357,244 decisions** (`parity_comparison.json`). **If parity moves, the decode changed the pixels and the fix is wrong** — this AC is the tripwire for a pipelining bug that returns frames out of order (Option A's specific failure mode: matching outputs by arrival rather than by PTS).
- [x] **AC6 — Strategy A is retained.** `decodeKeyframesBySeek` still does an absolute `SEEK_TO_CLOSEST_SYNC` per keyframe over the seek-built PTS list, and the landing is still verified against the requested PTS and `SAMPLE_FLAG_SYNC` (that check was preserved through the restructure as `seekToVerifiedSyncSample`). A′ (`decodeKeyframes`) is untouched and still runs in the head-to-head. Figures carried as **32.937 / 62.820**. Absolute `SEEK_TO_CLOSEST_SYNC` per keyframe (**32.937 ms/kf**), not A′'s single-pass sync-filtered demux (**62.820 ms/kf**). Bound by [Decision #13](../architecture.md). **Do not "simplify" toward A′ because its comment claims it shipped** (trap 1). Also carry the corrected figures: **32.937 / 62.820 — NOT 33.68 / 116.45**, which were corrected during 12.2's delivery and must not be restated.
- [x] **AC7 — The before/after is archived as an artifact, not asserted in prose.** New directory **`apps/mobile/bench/12-4a/`** (not an extension of `bench/12-2/`, so 12.2's banked evidence stays untouched — which mattered: `pc_reference.py` writes into `bench/12-2/` by default and did overwrite `parity_comparison.json`, restored with `git checkout`). Contains the re-measured baseline (3 runs), the after (3 runs), three full-capture runs, the parity run, 12.2's rescued `BEFORE_*` artifacts, the fire-row comparator and its three results, and [`REPORT.md`](../../apps/mobile/bench/12-4a/REPORT.md) carrying fixture identity, device profile, thermal state per run, run counts, medians, and `[M]`/`[D]`/`[P]` labels. **Every figure in this record resolves to that directory.** New JSON under `apps/mobile/bench/12-4a/` (or extend `bench/12-2/` with clearly-suffixed filenames — record which and why). Must contain: the baseline figures cited here, the new figures, the fixture identity, the device profile, run count, and the median. **Every figure in the Dev Agent Record must resolve to this artifact** — the standard Story 12.3 set for Epic 12 evidence (its AC2).
- [x] **AC8 — The stale strategy comment is corrected.** Amended **inline** at the top of the file. It now states that **A shipped and is bound (32.937 ms/kf)** and **A′ is the slower alternative (62.820), retained for comparison only**, with the reason A′ loses despite having no flush and no EOS (`advance()` reads sample DATA, so A′ drags 2.3 GB through the extractor). The one claim from the old text that survives — the *incremental* `SEEK_TO_NEXT_SYNC(lastPts+1)` pattern really is broken on this device, 2 vs 1061 — is kept and clearly separated from the strategy question. [`WardenKeyframeDecoder.kt:22-33`](../../apps/mobile/plugins/kotlin/WardenKeyframeDecoder.kt#L22-L33) must state what is actually bound: **A shipped (32.937 ms/kf); A′ is the slower alternative (62.820 ms/kf) and is retained for comparison only.** Amend **inline**, not in a commit message — 12.2 set this precedent explicitly for AC0b (*"Amended inline rather than left in the Dev Agent Record because Story 12.4 inherits this decode path and the original wording is an active trap for the next reader"*). You are that next reader; do it for the one after you.

### Fences, gates, delivery

- [x] **AC9 — Scope fence.** Verified with `git status --porcelain`. Touched: **two Kotlin files only** (`WardenKeyframeDecoder.kt`, `WardenEngineBench.kt`), the new `apps/mobile/bench/12-4a/`, this story file, `deferred-work.md`, `sprint-status.yaml`. **No `.ts` file**, no `processingPipeline`/`gameDetector`/`mapIdentifier`/`blackScreenDetector`/`segmentation`, no GLES/EGL removal, no `WardenCpuBaseline.kt` or `WardenRulePacker.kt` (the packed LUT sha256 `b8287e08…` is unchanged in every run), no `map_config*`/zone data/`contracts/`, no `schema_version` bump, no `prd.md`, no Tool 9 / `video_test.py`. PERF-002 end-to-end **not** re-measured — the full-capture wall is reported because AC4/AC5 require a full-capture run, and is explicitly not offered as a re-baseline. *(One incidental 12.2 file was overwritten by `pc_reference.py` and restored — see AC7.)* 12.4a does **NOT**: touch any `.ts` file · touch `processingPipeline.ts` / `gameDetector.ts` / `mapIdentifier.ts` / `blackScreenDetector.ts` / `segmentation.ts` (**12.4c's**) · remove the GLES/EGL surface (**12.4b's**) · change `WardenCpuBaseline.kt` or `WardenRulePacker.kt` (both validated; changing them invalidates AC5's baseline) · touch `map_config*`, zone data, or `contracts/` · bump `schema_version` (**E1**) · re-measure PERF-002 end to end (**12.4d's**) · edit `prd.md` NFRs · re-point Tool 9 or `video_test.py` (**9.16's**). Verify with `git status --porcelain` before delivery.
- [x] **AC10 — Gates green.** Re-verified from scratch, not trusted. **root `typecheck`: 3 errors, all `web`** (`LoginForm.tsx`, `RegistrationForm.tsx` Zod-v4/resolver overloads + a missing `@warden/contracts/user-doc`) — **identical to the documented pre-existing baseline**; mobile/tooling/contracts all pass. **mobile jest: 20 suites, 162 passed + 10 todo.** **tooling pytest: 305 passed.** **`format:check`: clean.** `web` vitest inherited red (20 files / 134 tests, duplicate-React-under-pnpm, Story 1.10's finding — not this story's). *(🔴 Turbo **cached** 3 of 5 `test` tasks, so the first `pnpm test` printed nothing for mobile/tooling; both were re-run uncached to get these numbers. A cached green is not a verified green.)*

  > **Finding, per AC10's own instruction to treat a moved number as one:** this AC states mobile jest at **161** passed; it is **162**. This story's diff contains **no TypeScript**, so the figure was stale before 12.4a began rather than moved by it. `pnpm typecheck && pnpm test && pnpm format:check` from the repo root. **Re-verify the baseline first — do not trust these numbers, they are a starting point, not a gate.** Post-12.3 state: mobile jest **20 suites / 161 passed + 10 todo**; tooling pytest **305**; root typecheck **3 errors, all `web` (pre-existing)**; web vitest **inherited red** (duplicate-React-under-pnpm, Story 1.10's finding — not yours); `format:check` clean. **🔴 Note `format:check` does NOT cover `_bmad-output/`** — `.prettierignore` excludes it, so a green run says nothing about story-file edits. A Kotlin-only diff should move none of them; if one moves, that is a finding. *(`plugins/kotlin/*.kt` is not compiled by `pnpm typecheck` — the real gate for this story is the device run.)*
- [x] **AC11 — The three deferred-work items this story owns are disposed.** All three closed in [deferred-work.md](deferred-work.md) with **measured** outcomes, not status words — including the correction that the `TIMEOUT_US` item's own stated diagnosis ("the codec has not produced output yet") is **wrong**, and that it was not the "two-line fix" it claimed. **A fourth, unowned item was also closed incidentally**: "re-run `pc_reference.py compare` so §7's classifier-accuracy table has a producing artifact — correct home: the next device pass". This was that pass. **And one new item was logged**: `seekTo` is now ~58% of the decode loop, recorded as a measurement, explicitly **not** as a claim that it is reducible. [deferred-work.md](deferred-work.md) *Deferred BY Story 12.2* → `TIMEOUT_US` ([:184](deferred-work.md)), `countSyncSamplesByScan()` ([:185](deferred-work.md)), per-keyframe `flush()` ([:186](deferred-work.md)). All three were **re-homed here by Story 12.3 (AC0d/AC15) with the headroom quantified**. Mark each closed with the **measured** outcome, or re-homed with a reason. Do not leave them reading as open.
- [x] **AC12 — Committed to `main`.** Commit **`e73b650`**, direct to `main`, no branch, no PR, lowercase subject, scope `mobile`. 33 files. `sprint-status.yaml` rides in the same commit. 🔴 **It also bundles the uncommitted 12.4-split artifacts** (`epics-and-stories.md`, the 12-4b/c/d story files) that were already in the working tree at kickoff: `sprint-status.yaml` co-mingles their edits with this story's status flip, so the commit boundary is not file-isolatable ([[project_warden_shared_doc_commit_boundary]]). **`main` is NOT pushed** — that stays Stephane's call. Direct to `main`, no branch, no PR ([[project_warden_main_branch_workflow]]). Commitlint requires a **lowercase subject**; scope `mobile` per the `367f09e feat(mobile): android gles/mediacodec detection engine poc (story 12.2)` precedent. `main` is **not** auto-pushed. `sprint-status.yaml` rides in the same commit — the Two-PR sequencing retired with the branch workflow ([[feedback_two_pr_docs_execution]]); check `git status` for foreign edits first ([[project_warden_shared_doc_commit_boundary]]).
- [x] **AC13 — `sprint-status.yaml`: `12-4a-…` `in-progress → review`**, and `12-4b-…` `backlog → ready-for-dev` (its dependency is now satisfied). Record the measured before/after in the entry comment — the next story reads it.

---

## Tasks / Subtasks

- [x] **Task 1 — Read the evidence and re-establish the baseline.** (AC: 0d, 7)
  - [x] Read [12.2 REPORT §5](../../apps/mobile/bench/12-2/REPORT.md) (*AC0b — decode* and *Where the time actually goes*) and the [spike report](../architecture-spike-gpu-megashader.md) → *Follow-up work required*.
  - [x] Read `decodeKeyframesBySeek()` ([:474-600](../../apps/mobile/plugins/kotlin/WardenKeyframeDecoder.kt#L474)) and `decodeProbe()` ([:272-385](../../apps/mobile/plugins/kotlin/WardenKeyframeDecoder.kt#L272)) in full. `decodeProbe` is the instrument; `decodeKeyframesBySeek` is the patient.
  - [x] Stage the fixture and re-run the baseline **on the device** (≥3 runs, median). Do not diff against a number you did not reproduce.
- [x] **Task 2 — Resolve AC0.** (AC: 0a–0d) Record all four verdicts in the Dev Agent Record before writing code.
- [x] **Task 3 — AC1: the timeout.** (AC: 1, 0b)
  - [x] Change `TIMEOUT_US`; **re-derive the spin/wedge cap at [:804](../../apps/mobile/plugins/kotlin/WardenKeyframeDecoder.kt#L804)** and update its comment.
  - [x] Re-run `flushprobe`; report the new try-again count per keyframe against the 1.02 baseline.
- [x] **Task 4 — AC2: the flush.** (AC: 2, 0a) The hard one. Restructure per AC0a; **match outputs to keyframes by PTS**; handle the tail drain.
- [x] **Task 5 — AC3/AC4: the index and the assertion.** (AC: 3, 4, 0c)
- [x] **Task 6 — 🔴 Prove you did not break it.** (AC: 4, 5, 6)
  - [x] Full-capture run: count assertion **1061 == 1061**.
  - [x] Parity run against `pc_reference_fires.json`: **0 disagreements**. If non-zero, **stop** — the pipelining is returning frames out of order.
- [x] **Task 7 — Measure and archive.** (AC: 7) ≥3 runs, median, new JSON, every figure traceable.
- [x] **Task 8 — AC8: fix the stale header.** (AC: 8)
- [x] **Task 9 — Deliver.** (AC: 9–13) Fence check → gates → deferred-work → commit → sprint-status.

---

## Dev Notes

### The file you are changing

`apps/mobile/plugins/kotlin/WardenKeyframeDecoder.kt` — **918 lines**. It is the **tracked source of truth**; `apps/mobile/android/**` is **gitignored** and regenerated at prebuild by [`apps/mobile/plugins/with-detection-engine.js`](../../apps/mobile/plugins/with-detection-engine.js) (which copies 9 Kotlin files from `plugins/kotlin/`). **Edit `plugins/kotlin/`, never `android/`** — an edit under `android/` is silently discarded on the next prebuild.

Two decode paths, and the naming is a trap (see trap 1):

| function | line | strategy | ms/kf | bound? |
|---|---|---|---|---|
| `decodeKeyframesBySeek()` | [:474](../../apps/mobile/plugins/kotlin/WardenKeyframeDecoder.kt#L474) | **A** — absolute `SEEK_TO_CLOSEST_SYNC` per keyframe, flush, queue, EOS, drain | **32.937** | **✅ YES** |
| `decodeKeyframes()` | [:617](../../apps/mobile/plugins/kotlin/WardenKeyframeDecoder.kt#L617) | A′ — single forward pass, sync-filtered demux, no flush, no EOS | 62.820 | ❌ no |
| `decodeProbe()` | [:272](../../apps/mobile/plugins/kotlin/WardenKeyframeDecoder.kt#L272) | the `flushprobe` instrument — stage-by-stage | — | instrument |
| `countSyncSamplesByScan()` | [:189](../../apps/mobile/plugins/kotlin/WardenKeyframeDecoder.kt#L189) | ground-truth scan | 62.070 s | ❌ **must never ship** |
| `syncSamplePtsListBySeek()` | [:433](../../apps/mobile/plugins/kotlin/WardenKeyframeDecoder.kt#L433) | the index the loop consumes | 2.290 s | ✅ |

**Why A′ is slower despite having no flush and no EOS:** `NuMediaExtractor::fetchTrackSamples` reads sample **data** on every `advance()`, in batches of up to `mMaxFetchCount = 8` for video tracks — so A′ drags **2.3 GB** through the extractor to reach one sample in 250. An earlier version of both this report and the decoder called `advance()` *"metadata-only: nothing here is decoded"*. **That is false**, and it is the same misconception that made `countSyncSamplesByScan()` cost 62 s.

### `decodeNs` is nested — do not build a new number on it

[:563](../../apps/mobile/plugins/kotlin/WardenKeyframeDecoder.kt#L563) and [:700](../../apps/mobile/plugins/kotlin/WardenKeyframeDecoder.kt#L700) **assign** `decodeNs = System.nanoTime() - t0` with `t0` fixed at loop entry, so after N keyframes it includes the downstream work of frames 0…N−2. The file admits it ([:734-737](../../apps/mobile/plugins/kotlin/WardenKeyframeDecoder.kt#L734)). **The tell:** Path Z `stage_total` **35.125** > `wall` **33.428** — a partition cannot exceed the whole. This is what produced the retracted *"decode is 99% of the wall"* framing; the real GL share was **6.0% / 7.3%**. **Report wall-clock and the `flushprobe` stage decomposition. Do not quote `decodeNs` as a disjoint stage.**

### What you must NOT disturb

- **`WardenCpuBaseline.kt` and `WardenRulePacker.kt`** — the bound evaluator and packer. `WardenRulePacker` is **byte-identical** to `lut.py` (sha256 `b8287e08…`, 7200 bytes, 134 rules, 68 full-circle / 9 wrap / 57 normal). AC5's parity baseline assumes both are untouched.
- **The colour conversion.** The bound configuration is the **ByteBuffer path's bit-parity YUV→RGB** (Path P), not zero-copy Path Z. Path Z decodes into a GL texture to feed a shader, and the shader is rejected. Do not "optimise" toward Path Z; 12.4b deletes it.
- **Scoped storage.** `/sdcard/<dir>` is **EACCES at targetSdk 36** regardless of the legacy manifest entry. Fixtures live in the app's own `getExternalFilesDir()`, writable by `adb push` with **no runtime permission**. `adb push` of a *directory* still fails (`secure_mkdirs() failed`) — pre-create with `adb shell mkdir -p`.

### Measurement hygiene (this is an evidence story)

- **≥3 runs, report the median.** 12.2's spread is documented and real: ffmpeg-kit control **38.068 s vs 33.660 s = 13%**; idle `flush()` **1.786 / 1.821 / 3.555 ms**.
- **Label every figure `[M]` measured, `[D]` derived, `[P]` projected** — Story 12.3's AC2 standard. Specifically: *"real decoding is ~4 ms"* is **`[D]`, not instrumented** (`62.8 − 58.5`), with **~11.5 ms of the 22.1 ms output wait unattributed**. 12.2's §9 item 4 was corrected on exactly this point — do not re-introduce it.
- **Thermal context:** no throttling was observed over an ~8-minute run, recorded as a capability point, not a floor (`device_seektest.json`). Collect it again; a speedup that only appears cold is not a speedup.

### Fixtures

| fixture | path |
|---|---|
| capture | `videos/V2/2026-04-27 22-05-34.mp4` — 2.3 GB · 1920×1080 h264 `yuv420p` `bt709` · **4419.633 s** · GOP **4.1667 s** · **1061 keyframes** |
| config | `apps/tooling/output/map_configs/map_config.v2.json` — **134 rules** (10 hud / 3 in_match / 121 map across 13 maps) |
| parity corpus | `apps/tooling/output/labeled/v2/` — 2666 PNGs / 16 classes |
| PC reference (**tracked**) | `apps/mobile/bench/12-2/pc_reference_fires.json` |

Reproduction sequence: [`apps/mobile/bench/12-2/REPORT.md` §10](../../apps/mobile/bench/12-2/REPORT.md) — build / stage / run / analyse, plus the mode list (`all`, `parity`, `cpugpu`, `timing`, `framediff`, `seektest`, `pngdump`, `flushprobe`).

### Project Structure Notes

- Kotlin sources: `apps/mobile/plugins/kotlin/*.kt`, package `team.warden.mobile`. Emitted to `android/app/src/main/java/team/warden/mobile/` at prebuild — **gitignored**.
- Plugin: `apps/mobile/plugins/with-detection-engine.js`, registered as the 5th entry in [`apps/mobile/app.json`](../../apps/mobile/app.json) `expo.plugins`.
- **Plugin idempotency is by REPLACEMENT, not presence** — 12.2 learned this the hard way: `if (xml.includes("WardenEngineBenchActivity")) return` meant a later *fix* silently never reached the APK on a reused `android/` tree. If you touch the plugin, preserve that discipline.
- JS-side access is **only** via `apps/mobile/src/shared/services/detectionEngine.ts` ([INVARIANT: native-modules-only-via-shared-services](../architecture.md)). You should not need to touch it; if you change a native method **signature**, you do — and `detectionEngine.test.ts` pins `BenchMode` in lockstep with Kotlin's `BENCH_MODES`.

### References

- [Source: _bmad-output/architecture-spike-gpu-megashader.md] — *Measured results* (decode decomposition, strategy comparison, keyframe index), *PERF-002 re-baseline* (the `[P]` projection), *Follow-up work required* (this story's three items with headroom), *AC0d — decode-loop fix owner: Story 12.4*
- [Source: _bmad-output/architecture.md#Decision-13] — what is bound: strategy A, ByteBuffer bit-parity, seek-built index; *"`countSyncSamplesByScan()` must never ship"*
- [Source: apps/mobile/bench/12-2/REPORT.md] — §5 *Where the time actually goes* (the stage table), §9 item 4, §10 *reproduce*
- [Source: _bmad-output/implementation-artifacts/12-2-android-poc-gles-port.md] — *Bugs found and fixed during the port* (traps 2–4), AC0b's inline amendment
- [Source: _bmad-output/implementation-artifacts/deferred-work.md] — *Deferred BY Story 12.2*, the three items AC11 disposes
- [Source: _bmad-output/epics-and-stories.md#Epic-12] — founding constraints E1–E7; E6 *"a PC number is NEVER a mobile number"*

---

## Dev Agent Record

### Agent Model Used

`claude-opus-5[1m]` (Amelia, `/bmad-dev-story 12.4a`), 2026-09-17. Reference device
**Poco X5 Pro 5G** — `22101320G` / `redwood` / **SM7325** / Android **14** (SDK 34) /
Adreno 642L, `c2.qti.avc.decoder`, thermal `NONE` (not throttled) on every run below.

### AC0 — kickoff verdicts (recorded BEFORE any code was written)

#### AC0a — how the per-keyframe `flush()` is eliminated → **OPTION A**, with an explicit Path-Z carve-out

**Option A (pipeline several IDRs, no per-keyframe EOS).** Each sample is fetched by an
absolute `SEEK_TO_CLOSEST_SYNC`, so each is a self-contained IDR; *k* of them are queued
back-to-back and outputs are drained as they arrive, **matched to requests by
`info.presentationTimeUs`, never by arrival order** (AC5's named failure mode). `flush()`
disappears from the loop entirely.

**The tail still needs exactly one `END_OF_STREAM` — per RUN, not per keyframe.** Trap 2 is
real and it is not a flush problem: a hardware AVC decoder holds frames for reorder, so the
last *d* keyframes will not come out on their own. One EOS after the final sample drains
them. That is **1 × 14.5 ms instead of 1061 ×**, and it keeps trap 2's mechanism intact
rather than deleting half of it.

**🔴 Carve-out — the Surface path (Path Z) keeps the legacy flush+EOS loop.** Pipelining is
unsafe there and this is structural, not cautious: `WardenSurfaceTextureHost` consumes one
posted frame at a time and already treats `pendingFrames > 1` as an anomaly, so *k* frames
in flight would coalesce in the `SurfaceTexture` and silently mis-bind. Decision #13 binds
**Path P (ByteBuffer, bit-parity)**, Path Z exists only to feed the rejected shader, and
**Story 12.4b deletes it**. So AC2 is satisfied on the bound path, and the branch that keeps
`flush()` is the one already scheduled for removal. Recorded rather than quietly done.

**Option B rejected** as the story states it: after an EOS the codec will not accept more
input without a reset, and `start()` after `flush()` throws in synchronous mode (trap 3). No
variant was attempted, so none is claimed.

**Choice of *k*: measured, not picked.** A `pipelineProbe` sweeps *k* ∈ {1, 2, 4, 8, 16} over
the same 100 keyframes in a single run, so the depth is bound by evidence in the same
artifact as everything else. Value and reasoning recorded under *Measured results*.

#### AC0b — new `TIMEOUT_US`, and the wedge guard → **`1_000L`, with the caps re-expressed in TIME**

`10_000L → 1_000L`. The mechanism the baseline actually shows is not "polling is slow": the
probe queues the IDR, polls once, gets `INFO_TRY_AGAIN_LATER`, and **sleeps a full timeout
before the loop comes back round and queues the `END_OF_STREAM` the decoder is waiting for**.
The sleep is dead time that *delays the input the codec needs* — which is why 1.02 try-agains
cost 10.6 ms/kf. At 1 ms the EOS lands ~9 ms earlier.

**The spin caps no longer derive silently from the timeout.** They are now declared as
durations and converted to polls, so the wedge budget is invariant under a timeout change:

| guard | before | after | wedge cap |
|---|---|---|---|
| `MAX_SPINS` | `500` @ 10 ms | `5000` @ 1 ms | **5 s, unchanged** |
| `MAX_SPINS_BEFORE_EOS` | `2000` @ 10 ms | `20000` @ 1 ms | **20 s, unchanged** |

#### AC0c — keyframe-index source → **the seek-built PTS list** (`syncSamplePtsListBySeek`, 2.290 s)

The recommended option, and already what the decode loop consumes — no change of source, only
a change of *reachability* for the thing it replaces. `countSyncSamplesByScan()` (62.070 s) is
**retained as the bench-only independent ground truth** that AC4's assertion compares against;
an `stss` reader was not written, because the assertion's value is being independent of the
seek list, and a second seek-derived index would not be.

#### AC0d — before/after instrument → **`flushprobe`, ≥3 runs, median**, plus `timing` for the wall

`adb shell am start -n team.warden.mobile/.WardenEngineBenchActivity --es mode <mode> --es
video <files>/warden12_2/capture.mp4 --ei limit 0 --ei cpuFrames 400`, fixture
`videos/V2/2026-04-27 22-05-34.mp4` (2.3 GB, 1061 keyframes).

**The baseline was re-measured today on the current source tree, not inherited.** The APK was
rebuilt/reinstalled first so the "before" provably comes from the tree being modified.
Diffed against `apps/mobile/bench/12-2/device_probe_flush.json{,_run2,_run3}` and
`device_report_timing.json`; new runs archived under `apps/mobile/bench/12-4a/` (AC7).

### Measured results

All figures `[M]` measured unless marked `[D]` derived or `[P]` projected. Median of 3 runs.
Thermal `NONE` / not throttled on **every** run, including three back-to-back full-capture
passes. Full artifact set and reproduction steps:
[`apps/mobile/bench/12-4a/REPORT.md`](../../apps/mobile/bench/12-4a/REPORT.md).

#### The headline

| | baseline `[M]` | after `[M]` | |
|---|---|---|---|
| **BOUND LOOP, ms/keyframe** (`ac11_ac13_timing_naive` BIT_PARITY `decode`) | **42.431** | **9.742** | **4.36×** |
| loop STRUCTURE, ms/keyframe (`decodeProbe` → `pipelineProbe`) | 41.982 | 7.706 | 5.45× |
| per-keyframe `flush()` calls | 1061 | **0** | |
| `END_OF_STREAM` round-trips | 1061 | **1** | once per run |
| **full capture, bound BIT_PARITY path** | **45 253.9 ms** | **10 592.2 ms** | **4.27×**, −34.7 s |
| keyframes decoded / asserted | 1061 / 1061 | **1061 / 1061** | AC4 |
| rule-frame decisions vs 12.2 | — | **426 522 over 3 runs, 0 disagreements** | AC5 |

> 🔴 **CORRECTED 2026-09-17 BY CODE REVIEW.** This table originally carried only the second
> row, labelled "bound decode loop". **It is not the bound loop** — `41.982` is `decodeProbe`'s
> wall and `7.706` is `pipelineProbe`'s, two INSTRUMENTS, neither of which is the shipped
> `decodeKeyframesBySeekPipelined`. Both measure the loop STRUCTURE fairly and the k-sweep rests
> on them legitimately, but **quote 4.27× / 4.36× for what shipped, not 5.45×.**
>
> ⚠️ **The full-capture baseline is INHERITED, n = 1.** `BEFORE_report_timing.json` is dated
> 2026-09-15T15:30; only `flushprobe` was re-measured on 09-17. "Median of 3" applies to the
> after side. The banked Decision-#13 basis is **44 879.3**, not 45 253.9 (4.24× against it).

`[D]` On the loop STRUCTURE alone that is **44.54 s → 8.18 s over 1061 keyframes**; on the bound
loop's own decode stage, **45.02 s → 10.34 s**. The story projected
`[P]` 17.1 ms/kf (~2.5×); the measured result **beats the projection by more than 2×**, because
the projection treated the flush and the timeout as two independent subtractions from a fixed
42.2 ms wall. They are not — removing the per-keyframe EOS also removes the thing the timeout
was delaying.

> **🔴 This is a decode-loop number, NOT a PERF-002 re-baseline.** AC9 fences end-to-end
> PERF-002 out of this story; it is **12.4d's**. The full-capture figure is reported because
> AC4 and AC5 require a full-capture run, not to re-baseline anything. The 44.9 s / 1.02%
> PERF-002 figure from 12.3 also covers a **detection pass only** — segmentation, thumbnail
> export and the rest of the auto-slice pipeline remain unmeasured.

#### AC1 — the timeout, and a correction to *why* it was expensive

| `decode_probe` (structure unchanged, constant only) | before | after | Δ |
|---|---|---|---|
| `wall_ms_per_keyframe` | 41.982 | **33.442** | **−8.540** |
| `queue_to_first_output_ms_median` | 21.891 | **13.389** | **−8.502** |
| `try_again_per_keyframe` | 1.03 | 7.39 | +6.36 |
| `try_again_ms_per_keyframe` | 10.697 | **9.772** | −0.925 |
| `flush_ms_median` | 14.114 | 14.077 | untouched, as expected |

**AC1's stated criterion did not hold; its purpose was exceeded.** The AC is amended inline
above with the measured mechanism: the 10.6 ms was the loop **withholding the `END_OF_STREAM`
the decoder was waiting for**, not the decoder being slow. `[D]` real post-EOS decode latency
is therefore ~3.5 ms, not the ~11.3 ms the baseline's arithmetic implied — the rest was timeout
quantisation at both ends.

#### AC0a — the depth sweep that chose *k*

| *k* | wall ms/kf (median of 3) | decoded | PTS mismatches |
|---|---|---|---|
| **1** | **WEDGED — no output at all, 3 runs of 3** | 0 | — |
| 2 | 20.909 | 100/100 | 0 |
| 4 | 8.062 | 100/100 | 0 |
| **8 ← chosen** | **7.706** | 100/100 | 0 |
| 16 | 7.725 | 100/100 | 0 |

**`k = 1` wedging is the most informative row.** One IDR in flight with no EOS produces no
output — **trap 2 reproduced directly**. It is why the tail keeps exactly one `END_OF_STREAM`
per run: the flush was removable, **the drain was not**. **Why 8:** the knee is at 4 and then
flat; 8 sits on the plateau with margin, so a device with deeper reorder does not fall back
toward the k=2 cliff, while 16 buys ~0.02 ms for twice the in-flight state.

#### Full capture, three back-to-back runs, thermal `NONE` throughout

| path | before (12.2) | run 1 | run 2 | run 3 | median | |
|---|---|---|---|---|---|---|
| **BIT_PARITY — BOUND** | 45 253.9 | 10 022.9 | 10 627.2 | 10 592.2 | **10 592.2** | **4.27×** |
| ZERO_COPY — legacy loop | 35 435.7 | 23 460.6 | 25 568.4 | 24 817.9 | **24 817.9** | 1.43× |

**ZERO_COPY improving at all is the cleanest confirmation that AC1 and AC2 are separable.** It
keeps the per-keyframe `flush()` (the Path-Z carve-out) and gains only the timeout fix — 1.43×.
The bound path gains both — 4.27×. Count assertion **1061 / 1061 on every run, both paths**.

**AC6 re-measured head to head** on the same 60 frames: **A 1304.3 ms vs A′ 4160.0 ms — A is
3.2× faster.** A′ still has no flush and no per-keyframe EOS and still loses.

#### What the loop costs now

`seekTo` is **~4.5 of the 7.7 ms/kf — ~58% of the loop**. The stage this story's own table
marked "not yours" at 10% is now the dominant term. **Not investigated and not claimed
reducible**; logged in [deferred-work.md](deferred-work.md) so the next reader starts from the
measurement rather than the old framing.

### Debug Log References

- `adb devices` was empty at kickoff; the story was HELD until the reference device was attached
  rather than writing unverifiable Kotlin. Every AC here is a measured one.
- Git Bash mangles `/sdcard/...` into a Windows path — `MSYS_NO_PATHCONV=1` is required for
  every `adb shell` / `adb pull` in this repo's environment.
- Baseline re-measured on a rebuilt+reinstalled APK **before** any edit, so the "before"
  provably comes from the tree that was then modified.
- Two build/flash cycles: one for the decode restructure, one for the AC3 `deviceProfile`
  hardening. The second is a **measurement no-op** (`timing` already passed a ground truth in,
  so the flipped branch was never taken there) — confirmed by re-running the whole `flushprobe`
  set on the final binary and reproducing every figure. It also cut `flushprobe` from **110 s
  to 40 s** by removing a 62 s scan no mode in that run used.

### Completion Notes List

- **AC0a Option A taken and measured.** `decodeKeyframesBySeek` now pipelines k=8 IDRs with no
  `flush()` and one `END_OF_STREAM` per run, matching outputs to requests **by PTS**.
- **AC1 amended on evidence.** The named metric did not move; the wall moved −8.5 ms/kf. The
  mechanism in the AC was wrong and is corrected inline, because 12.4b/c/d inherit this path.
- **AC2 verified structurally:** `flush()` survives at exactly three sites — `decodeProbe` and
  `flushOnlyProbe` (both instruments) and `decodeKeyframesBySeekSurfaceLegacy` (Path Z, which
  **12.4b deletes**). **Zero in the bound path.**
- **AC3 went further than "don't call it".** `deviceProfile()` — reachable from the RN bridge —
  used to opt *into* the 62 s walk whenever the caller had no ground truth, saved only by
  `describeDevice` passing a null video path. **Story 12.4c would have shipped it.** Now no
  caller anywhere passes `scanSyncSamples = true`.
- **AC5's stated instrument cannot see what AC5 is afraid of.** `pc_reference.py compare` runs
  the **labeled PNG corpus** through `DIRECT_RGB`; it never opens the video and never touches
  `decodeKeyframesBySeek`, so it cannot detect a decode-order defect. It was run anyway (it
  proves the engine and LUT are untouched) **and** a real tripwire was built: 12.2's banked
  per-keyframe fire rows were pulled off the device before they could be overwritten, and the
  full-capture rows diffed against them — **1061 keyframes × 134 rules = 142 174 rule-frame
  decisions, 0 disagreements, 0 duplicate PTS, 0 missing, delivery order identical.**
- **AC10 finding:** the story states mobile jest at **161** passed; it is **162** on the current
  tree. This diff touches no TypeScript, so that figure was stale before this story started.

### File List

- `apps/mobile/plugins/kotlin/WardenKeyframeDecoder.kt` — modified (AC1, AC2, AC3, AC6, AC8)
- `apps/mobile/plugins/kotlin/WardenEngineBench.kt` — modified (AC0a sweep, AC3 hardening)
- `apps/mobile/bench/12-4a/REPORT.md` — new (AC7)
- `apps/mobile/bench/12-4a/compare_fire_rows.py` — new (AC5 tripwire)
- `apps/mobile/bench/12-4a/baseline_flushprobe_run{1,2,3}.json` — new
- `apps/mobile/bench/12-4a/after_flushprobe_run{1,2,3}.json` — new
- `apps/mobile/bench/12-4a/after_timing_run{1,2,3}.json` — new
- `apps/mobile/bench/12-4a/after_parity_run1.json` — new
- `apps/mobile/bench/12-4a/BEFORE_report_timing.json` — new (12.2's run, rescued off-device)
- `apps/mobile/bench/12-4a/BEFORE_timing_fires_bit_parity_seek_1061.json` — new
- `apps/mobile/bench/12-4a/BEFORE_parity_fires.json`, `BEFORE_report_parity.json` — new
- `apps/mobile/bench/12-4a/AFTER_timing_fires_run{1,2,3}.json` — new *(corrected 2026-09-17 by review: this list named a single `AFTER_timing_fires_bit_parity_seek_1061.json`, which was never committed)*
- `apps/mobile/bench/12-4a/fire_row_comparison_run{1,2,3}.json` — new (AC5 result) *(corrected: was listed as `fire_row_comparison.json`)*
- `apps/mobile/bench/12-4a/AFTER_parity_comparison.json`, `AFTER_parity_fires.json` — new (AC5a)
- `apps/mobile/bench/12-4a/after_parity_run1.json`, `after_timing_run{1,2,3}.json`, `after_flushprobe_run{1,2,3}.json` — new
- `_bmad-output/implementation-artifacts/12-4a-decode-loop-optimisation.md` — this file
- `_bmad-output/implementation-artifacts/deferred-work.md` — AC11 disposal + one new item
- `_bmad-output/sprint-status.yaml` — AC13

---

### Review Findings

> 🔴 **THE 26 PATCHES BELOW WERE APPLIED ON 2026-09-17, AFTER EVERY BENCH ARTIFACT WAS
> CAPTURED.** `apps/mobile/bench/12-4a/` therefore describes the PRE-patch code.
> `:app:compileDebugKotlin` **BUILD SUCCESSFUL** and the repo gates are unmoved (tooling 305,
> mobile jest 20 suites / 162 + 10 todo, typecheck 3 pre-existing `web`, `format:check` clean,
> web vitest inherited red) — **but nothing has been run on the device.** The patches are
> defensive and are expected to be behaviour-neutral on `c2.qti.avc.decoder`; expected is not
> measured. A re-run is logged in [deferred-work.md](deferred-work.md), homed to **12.4b's first
> device pass**, per [[feedback_batch_manual_checks_epic_end]].

`/bmad-code-review 12.4a` (Stephane, `claude-opus-5[1m]`), 2026-09-17, against commit `e73b650`.
Three layers: Blind Hunter (diff only), Edge Case Hunter (diff + project), Acceptance Auditor
(diff + spec + context docs). **2 decision-needed, 24 patch, 8 deferred, 4 dismissed as noise.**
Both decisions were resolved by Stephane on 2026-09-17, documentation-only in each case, so the
actionable list below is **26 patch items and 8 deferred**.

**The verdict is not in doubt** — `flush()` is gone from the bound path, the count assertion
reads 1061/1061 on all three runs, and the fire rows are bit-identical. The findings below are
about *portability of the new loop* and *accuracy of the record*, not about whether the fix works.

#### Decision needed — RESOLVED BY STEPHANE 2026-09-17, then APPLIED (both → patch, documentation only)

- [x] [Review][Patch] **Wedge-cap polarity in the pipelined loop — VERDICT: OPTION (a), COMMENT ONLY.** The `if (eosQueued) MAX_SPINS else MAX_SPINS_BEFORE_EOS` expression stays exactly as committed; the KDoc is corrected to state that the pipelined path runs under the 20 s cap for steady state and the 5 s cap only for the tail drain, and that this is deliberate — a stalled fill IS the k-too-small failure and deserves the generous budget. Rationale for not swapping: the banked k-sweep and the three full-capture runs were all measured under the committed polarity. — `decodeKeyframesBySeekPipelined:661` and `pipelineProbe:824` read `val cap = if (eosQueued) MAX_SPINS else MAX_SPINS_BEFORE_EOS`, and `eosQueued` only turns true once `nextToQueue >= target`. So for ~1053 of 1061 keyframes the bound path is guarded by the **20 s** cap, not the 5 s one AC0b's table advertises for steady state. The constant's KDoc justifies the generous cap solely by `decodeKeyframes` (A-prime) skipping non-sync samples — a rationale that does not apply here, where every queue is a verified sync sample. **Options: (a) correct the comment only, leaving the measured-good behaviour untouched; (b) swap the caps so the fill phase gets 5 s and the tail drain 20 s.** (b) changes wedge behaviour on a path that currently measures clean.
- [x] [Review][Patch] **`PIPELINE_DEPTH = 8` single-codec binding — VERDICT: OPTION (a), ACCEPT AND RECORD.** No fallback branch is added: an untested escalation path on the loop 12.4b/c/d build on is a worse trade than a documented constraint, and this is the same ship-and-observe posture Epic 12 took on the perf ladder. Record in the KDoc and in deferred-work: k=8 is MEASURED ON ONE CODEC (`c2.qti.avc.decoder` / SM7325 / Android 14), and the failure signature on a codec needing k > 8 is `no output after N polls (decoded=0/..., queued=8, inFlight=8, eosQueued=false)` — if that is ever seen, raise `PIPELINE_DEPTH` and re-sweep. 12.4d's end-to-end pass is where it would surface. **Original finding:** — EOS is queued only when `nextToQueue >= target`, and the fill loop is capped by `inFlight.size < PIPELINE_DEPTH`. On a codec whose output latency is >= 8 IDRs, or one that holds all its input buffers without emitting, fill blocks, EOS is never queued, and the run dies at the wedge cap. The commit proves the mechanism is real — `k=1 WEDGES`, 3 runs of 3. `k=8` was measured on `c2.qti.avc.decoder` only, and 12.4b/c/d inherit this loop as the shipping path. **Options: (a) accept the single-device binding and record it as a known constraint, consistent with the reference-device re-anchoring and the ship-and-observe posture Epic 12 adopted; (b) add a depth-escalation or EOS-nudge fallback before the wedge throw.**

#### Patch — decode-loop correctness and robustness

- [x] [Review][Patch] EOS input is stamped `0L`, which is exactly keyframe 0's PTS — `zero_count=1` in both fire-row artifacts. `eos` is computed at `:631` but read only inside the `info.size == 0` branch, so a codec that attaches EOS to the last *data-bearing* buffer (permitted by MediaCodec) makes `inFlight.remove(0L)` fail after keyframe 0 was already delivered, failing a bit-perfect run at the finish line and blaming the decoder for a timestamp this code chose [WardenKeyframeDecoder.kt:622,631]
- [x] [Review][Patch] The `when` on `dequeueOutputBuffer` has no `else`, so `INFO_OUTPUT_FORMAT_CHANGED` (-2, returned by every decoder at least once) and `INFO_OUTPUT_BUFFERS_CHANGED` (-3) bypass the spin counter entirely — the one hang the wedge budget exists to prevent is the one it cannot catch [WardenKeyframeDecoder.kt:628-670]
- [x] [Review][Patch] `readSampleData` is guarded only for `< 0`; a zero-length sample is queued with no EOS flag, its PTS can never leave `inFlight`, and the run dies misattributed to "the decoder dropped queued IDRs" [WardenKeyframeDecoder.kt:604]
- [x] [Review][Patch] `inFlight.add(pts)` return value is ignored — a duplicate PTS in `ptsList` queues two samples but records one, silently exceeding `PIPELINE_DEPTH` and later throwing a message that blames the decoder for a duplicate the caller supplied [WardenKeyframeDecoder.kt:613]
- [x] [Review][Patch] `MAX_SPINS = (WEDGE_CAP_MS * 1_000L / TIMEOUT_US).toInt()` has no `coerceAtLeast(1)`: `TIMEOUT_US = 0L` throws `ExceptionInInitializerError` in `<clinit>`, and `TIMEOUT_US > 5_000_000` yields a cap of 0 that fires on the first `TRY_AGAIN` — the exact false-failure AC0b's re-derivation claims to have eliminated [WardenKeyframeDecoder.kt:1085]
- [x] [Review][Patch] The wedge-throw message reports `"$cap polls at ${TIMEOUT_US}us"` — the one place a human meets this budget is the one place AC0b's ms-denominated framing was not carried through [WardenKeyframeDecoder.kt:664]
- [x] [Review][Patch] The PTS-mismatch diagnostic asserts only "already delivered, or never queued" and dumps no in-flight context — it excludes the third cause (the codec altered the timestamp), which is the likely one on a non-reference device [WardenKeyframeDecoder.kt:635]

#### Patch — instrument integrity (this is what selected `k = 8`)

- [x] [Review][Patch] `pipelineProbe` increments `decoded` even when `inFlight.remove` fails, so unrequested frames inflate the divisor of every headline figure — a depth that mis-delivers reports a *better* ms/kf than one that does not [WardenKeyframeDecoder.kt:812-814]
- [x] [Review][Patch] `pipelineProbe` exits a short decode via a silent `break` with no `error` key, so the bench's `catch (Throwable)` never fires and a depth that decoded 3 of 100 lands in the sweep table looking like a measurement; `all_decoded` is tautologically true on every non-`break` exit [WardenKeyframeDecoder.kt:818,835]
- [x] [Review][Patch] `pipelineProbe` records no `max_observed_in_flight`, so the flat k=8 / k=16 result cannot be distinguished from the codec's input-buffer count clamping both to the same effective depth — one `maxOf` would settle whether 8 is the knee or the ceiling [WardenKeyframeDecoder.kt:831]
- [x] [Review][Patch] `"flush_calls" to 0` is a hardcoded assertion, not an observation — if a `flush()` is ever reintroduced the artifact that exists to prove it is gone will keep reporting zero [WardenKeyframeDecoder.kt:844]
- [x] [Review][Patch] `pipelineProbe` does not validate `depth >= 1`; `depth = 0` wedges for 20 s and throws a message blaming the codec for a caller's argument [WardenKeyframeDecoder.kt:765]
- [x] [Review][Patch] `dec.syncSamplePtsListBySeek(200)` sits outside the sweep's `try`, so one extractor error discards every depth already measured and `ac0a_pipeline_depth_sweep` is never written; conversely an all-five-failed sweep still reports success with no aggregate check [WardenEngineBench.kt:1009]
- [x] [Review][Patch] `compare_fire_rows.py` — AC5(b)'s only real tripwire — has `identical` true on two empty `frames` arrays (prints `OK — 0 keyframes … 0 disagreements`, exits 0); `rows_before` is reported but never asserted against `len(b_by_pts)`, so duplicate PTS in the BEFORE file silently collapse; there is no `dup_before` to match `dup_after`. The committed results are substantive in fact (1061 rows, 485 distinct masks) — the instrument just cannot tell the difference [compare_fire_rows.py:118-167]

#### Patch — evidence and record accuracy

- [x] [Review][Patch] **`deferred-work.md:190` records a full-capture result that exists in no artifact**: "45 253.9 ms -> **19 013.6 ms (2.38x, -26.2 s)**". `19013` appears nowhere under `apps/mobile/bench/`. Committed BIT_PARITY walls are 10 022.9 / 10 627.2 / 10 592.2, median **10 592.2 = 4.27x, -34.7 s** — which is what REPORT.md, the story headline, the commit message and `sprint-status.yaml` all say. This is the permanent disposal record 12.4b/c/d will read [deferred-work.md:190]
- [x] [Review][Patch] **The 5.45x headline is a probe-to-probe comparison, labelled as the bound loop.** 41.982 is `decodeProbe`'s wall; 7.706 is `pipelineProbe`'s — a separate reimplementation of the pipelined structure, not `decodeKeyframesBySeekPipelined`. The bound loop's own measured figure is in the same artifacts: `ac11_ac13_timing_naive` BIT_PARITY `decode` **42.431 -> 9.742 ms/kf ~= 4.36x**, wall 4.27x. Nothing in the story or REPORT labels 5.45x as a probe figure [REPORT.md §0/§3, story Dev Agent Record, deferred-work.md:190]
- [x] [Review][Patch] **"The baseline was RE-MEASURED today, not inherited" holds for `flushprobe` only.** `baseline_flushprobe_run{1,2,3}` are 2026-09-17T10:14-10:18; `BEFORE_report_timing.json` carries `generated_at` = **2026-09-15T15:30**, ~1.8 days earlier. So the 45 253.9 ms behind the 4.27x is a single inherited run, n=1, and "median of 3" applies to the after side only. It is also not the banked tracked figure — `bench/12-2/device_report_timing.json` reads 44 879.3, which is what Decision #13 and the PERF-002 re-baseline use [AC0d, REPORT.md, commit message]
- [x] [Review][Patch] The File List and REPORT.md §5's copy-paste repro name two artifacts that were never committed: `AFTER_timing_fires_bit_parity_seek_1061.json` and `fire_row_comparison.json`. Committed are `AFTER_timing_fires_run{1,2,3}.json` and `fire_row_comparison_run{1,2,3}.json`, so §5's last command fails as written [story File List, REPORT.md §5]
- [x] [Review][Patch] The `TIMEOUT_US` KDoc still opens in bold with the framing AC1's amendment exists to retire — "**WAS `10_000L`, AND THAT COST 10.6 ms PER KEYFRAME**" — and never states the after value (9.772), never says the named counter did not move, never says the try-again *count* rose 1.03 -> 7.39. AC1 amended the story inline precisely so the next reader would not be trapped; the file they actually open still leads with the refuted number [WardenKeyframeDecoder.kt:1052-1056]
- [x] [Review][Patch] The sweep's comment claims `depth = 1` "is the control … which separates 'the flush was the cost' from 'the pipelining was the win'". Depth 1 threw on all three runs, so the sweep produced no flush-free/pipeline-free datapoint and separates nothing; the lowest working depth (k=2) is already pipelined. REPORT §3's "most informative row" framing is defensible — the code comment states the goal as achieved [WardenEngineBench.kt:1003-1005]
- [x] [Review][Patch] `k=1 "decoded 0"` is an inference, not a recorded measurement — the sweep's `catch` block stores only `{pipeline_depth, error}`, and since `spins` resets on every delivery, the 20 s throw is equally consistent with a run that decoded 90 frames then stalled. The "decoded | 0" column in the story's and REPORT's k-sweep tables is not backed by the artifact [WardenEngineBench.kt:1013-1018]
- [x] [Review][Patch] Record the AC6 caveat: `ac0b_decode_strategy_comparison` carries `"color_path": "ZERO_COPY"` on **both** arms, which `decodeKeyframesBySeek:534` routes to `decodeKeyframesBySeekSurfaceLegacy`. The A-vs-A-prime head-to-head therefore re-confirms A on the *legacy* loop; shipped pipelined A was never benched against A-prime [REPORT.md §4]
- [x] [Review][Patch] Record the AC0d caveat: before and after `flushprobe` do not execute the same work. AC3's hardening means `baseline_flushprobe_run1` has `sync_sample_count: 1061, "scanned here"` and `after_flushprobe_run1` has `-1, "NOT MEASURED"` — so the baseline pulled 2.3 GB through the extractor immediately before `decodeProbe` and the after runs did not. Warm page cache favours the baseline, so the direction is conservative, but the Debug Log's "a measurement no-op" is wrong for `flushprobe` specifically — the mode AC1's entire A/B rests on [Debug Log, REPORT.md §2]
- [x] [Review][Patch] Minor numeric inconsistencies: `seekTo` share quoted as "~58%" (story, REPORT §3) vs "~59%" (deferred-work.md:179) against a measured 4.430/7.706 = 57.5%; "0 disagreements across 142 174 rule-frame decisions" (deferred-work.md:190) vs 426 522 across three runs (story AC5); full-capture before quoted as 45 253.9 against the banked Decision-#13 basis of 44 879.3

#### Deferred — real, not caused by this change or not actionable now

- [x] [Review][Defer] No `try`/`finally` around a dequeued input buffer or `imageToKeyframe`'s `Image` — both leak on any throw between acquisition and hand-back. Bounded today by every caller's `use {}`; pre-existing pattern throughout the file [WardenKeyframeDecoder.kt:599-612,1023-1042] — deferred, pre-existing
- [x] [Review][Defer] `configureCodec()` has no `if (codec != null)` guard and overwrites the field; additionally the pipelined path leaves the codec in end-of-stream state with no `flush()`/`stop()`, so a second decode on one instance would wedge rather than leak. No caller does this today — the bench constructs a fresh decoder per depth — but nothing enforces or documents that [WardenKeyframeDecoder.kt:849-863] — deferred, pre-existing
- [x] [Review][Defer] A zero-size non-EOS output orphans its PTS in `inFlight` permanently, shrinking effective depth for the rest of the run. Fails loud via the EOS throw, but misattributed and without listing which PTS were stranded [WardenKeyframeDecoder.kt:646-657] — deferred, pre-existing
- [x] [Review][Defer] `TIMEOUT_US` is a class-wide constant lowered 10x on one path's measurement; `decodeKeyframes` (A-prime), `decodeProbe` and the retained Surface-legacy loop all now poll at 1000 Hz, including during A-prime's documented long sample-skip stretches [WardenKeyframeDecoder.kt:1067] — deferred, pre-existing
- [x] [Review][Defer] `MAX_SPINS_BEFORE_EOS`'s duration framing assumes every spin costs a full `TIMEOUT_US`; in `decodeKeyframes`, whose sample-skip body the KDoc explicitly cites, a spin also runs `advance()` at milliseconds per call, so the real bail-out budget grew ~10x rather than staying at 20 s [WardenKeyframeDecoder.kt:1079-1086] — deferred, pre-existing
- [x] [Review][Defer] "Thermal `NONE` on every run" rests on a single sample written under `ac1_device_profile` before any decode work begins — a statement about three run *starts*, not about the ~8 minutes they cover. Dev Notes require "a speedup that only appears cold is not a speedup" [WardenEngineBench.kt:975] — deferred, needs a device pass
- [x] [Review][Defer] AC5(b)'s BEFORE tripwire exists in exactly one rescued copy with no documented regeneration path, and 12.4b deletes the legacy loop that produced it — one accidental overwrite from being unreproducible [bench/12-4a/BEFORE_timing_fires_bit_parity_seek_1061.json] — deferred, owned by 12.4b
- [x] [Review][Defer] The k-sweep rebuilds the PTS list per depth (5 x ~2.3 s) rather than hoisting it, so the five rows are not guaranteed to be over an identical list if seek behaviour drifts [WardenEngineBench.kt:1009] — deferred, pre-existing

#### Dismissed as noise

- `probe()`'s `scanSyncSamples` default flip leaving a silent `-1` — verified nil blast radius: `probe()` has exactly one caller (`WardenEngineBench.kt:111`) which passes `false` explicitly, and AC4's `keyframe_count_expected` comes from `timingRun`'s own `groundTruth` argument, not from `probe`.
- "`configureCodec` leaks a hardware decoder per call" — no caller invokes a decode twice on one instance; the sweep builds a fresh decoder inside `use {}` per depth. (The missing *guard* is retained above as a defer.)
- "Commit message says no caller passes `scanSyncSamples = true` while the KDoc says the scan is reachable from `all`/`timing`/`seektest`" — both are true; those modes call `countSyncSamplesByScan()` directly, not through `probe`.
- Process objection that AC1 and AC5 were amended inline by the same commit they govern, and that bundling the 12.4-split artifacts makes the commit non-revertable — both are explicit, pre-authorised constraints (12.2's AC0b precedent for inline amendment; AC12 and the shared-doc commit-boundary constraint for the bundling).
