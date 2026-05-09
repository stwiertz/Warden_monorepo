# Story 1.1: Pre-PRD Performance Spike (AR-SPIKE)

Status: done

<!-- Validation is optional. Run validate-create-story before dev-story for a quality check. -->

## Story

As **Stephane** (solo developer; Sprint 3 critical-path lead),
I want **the OpenCV JSI binding shipped as a real binding (not the current `loadFrameFromPath` stub) on the Poco X5 Pro 5G reference device (re-anchored from the architecture's original Poco X5 — see "Reference device re-anchor" below), with measured PERF-002/003/004/005 numbers and validated map-ID and round-boundary accuracy floors**,
So that **PERF-010 is bound, the Innovation #1 fallback-ladder rung is determined (pass / rung-1 / rung-2 / rung-3 — the cloud-fallback rung is FORBIDDEN), and Sprint 3 mobile story scope (Epic 5/6) can finalize against the spike outcome.**

**Type:** Architecture-led spike. Hybrid deliverable — code change (real JSI binding for `loadFrameFromPath`) + measurement run on reference device + spike-report markdown artifact (`_bmad-output/architecture-spike-perf-floor.md`). The rung verdict is the binding output; the binding code is the means.

**Why this is the load-bearing first work item — and what gates it (G1):** Sprint Plan §2 Gate G1 — _"Story 1.1 (AR-SPIKE) is the load-bearing first work item. Stories 5.1, 5.3, 5.4, 5.5, 6.6 all carry an explicit `Story 1.1 spike` dependency. Do not start any of them before AR-SPIKE has a binding rung verdict."_ A wrong rung verdict (or a rung that hasn't yet been published) cascades into Sprint 3 as scope re-baselining at merge time. The spike's outcome dictates whether `mobile-AUTO-SLICE-001/002` ship in V1 (rung 0/1/2) or defer to V2 (rung 3, manual-clip-only V1).

**Why this is NOT blocked by G0 (Sprint 2.5 closure):** Sprint Plan §2 Gate G0 blocks _merges_ to `main`, not _development_ on feature branches. Story 0.2 is in `review` at the time this story file is created; the AR-SPIKE branch may proceed in parallel. **The spike's PR may not be merged until Story 0.2 reaches `done` and the G0 sign-off is on `main`.** This is non-negotiable per Decision #ES-3.

**Sprint-fit:** **needs-spike-or-split** — by design. This is the only story in Sprint 3's 76-story commit flagged `needs-spike-or-split` per Decision #ES-9. If the spike returns rung 3, Sprint 3 mobile-feature scope (Epic 5/6) re-baselines. The dev agent should not treat "took multiple focused days" as a failure mode — the spike IS the unknowable.

**Permitted spike outcomes (none of which is a story failure):**

| Rung | Trigger | V1 implication |
|------|---------|----------------|
| **0 — Pass** | All 4 PERF NFRs met on the Poco X5 Pro 5G reference device with real JSI binding | V1 launches with auto-slice on; PRD inherits the measured PERF-010 number; round-boundary accuracy floor binds as measured. **Note:** because the floor was measured on a 778G device (not the architecture's original 695-class anchor), V1's effective supported-device set narrows to "778G or stronger" — see "Reference device re-anchor" Dev Note. |
| **1 — Partial fail** | PERF-002 OR PERF-005 over budget by < 50% | Lower auto-slice frame-sampling rate, re-measure. If now passing, V1 launches with reduced sampling rate. PRD `mobile-AUTO-SLICE-001` adds a "with reduced sampling on weak hardware" clause. |
| **2 — Partial fail** | PERF-003 OR PERF-004 over budget | Drop Minimap+HUD overlay rendering on weak hardware (gated by device profile). View modes degrade to Full + Minimap (no HUD overlay). PRD `mobile-CINEMA-002` adds a graceful-degradation clause. |
| **3 — Hard fail** | JSI binding cannot ship as real binding within V1 timeline OR multiple PERF NFRs > 50% over budget AND rung-1/rung-2 don't recover them | Defer auto-slice to V2; V1 ships **manual-clip-only** via Decision #UX-14 path. `mobile-AUTO-SLICE-*` FRs become V2-deferred; activation timer T1-coach via manual-clip becomes the only V1 path. **V1 still launches.** |
| **FORBIDDEN — cloud fallback** | NEVER, regardless of measured numbers | Breaks Innovation #1 (privacy + lower marginal cost). Architecture asserts this is forbidden as a permitted rung. The spike report MUST explicitly assert this is not the chosen rung. |

## Acceptance Criteria (checklist)

> **AC checkbox convention:** Items whose endpoint depends on **post-merge actions** (PRD update, downstream Wave-6 unblocking, sprint-status `review → done` flip) are held `[ ]` with inline carve-out notes. Items the dev agent fully controls during the work flip to `[x]` on completion. (Convention inherited from Story 0.2's D1 resolution — tighten over precedent.)

1. [x] **AC1 — Real OpenCV JSI binding for `loadFrameFromPath`.** `apps/mobile/src/shared/services/opencv.ts:381` — `loadFrameFromPath(path)` returns a real `Promise<FrameBuffer>` (RGB-packed `Uint8ClampedArray` per the existing `FrameBuffer` interface at `apps/mobile/src/shared/services/opencv.ts:14-19`). It no longer throws. Implementation uses `react-native-fast-opencv`'s native JSI binding to decode JPEG keyframes on disk. **Closed 2026-05-09 (binding-only cut):** dev-build APK installed + launched cleanly on Poco X5 Pro 5G `dc72b871` via `expo run:android` (BUILD SUCCESSFUL in 5m 25s; `app-debug.apk` 175 MB SHA-256 `5fdad9771468f7b49ae434a7aea50904314a8c861c9b37b951cab594d1053ae3`; `team.warden.mobile/.MainActivity` reached MainActivity focus PID 23079). The binding compiled into the APK without errors and the app process did not crash on the React Native bridge initialization that loads the `react-native-fast-opencv` native module. **End-to-end keyframe-decode validation deferred** to Story 1.1.1 — the `runProcessingPipeline` path is currently blocked by missing `detection_config/latest` Firestore doc + Firestore rules denying reads + missing real ROIs (gap #6 in Dev Note "Substrate gap audit (2026-05-09)"). The binding loading + dev-build launch suffice to flip AC1 to `[x]` per the binding-only cut decision (see Dev Note "Binding-only cut (2026-05-09)"); the on-device decode of an actual keyframe is part of Story 1.1.1.

2. [x] **AC2 — `react-native-fast-opencv` dep is installed and `expo prebuild` clean.** `apps/mobile/package.json` declares `react-native-fast-opencv` at the highest stable version compatible with RN 0.81 / Expo SDK 54 (verify on npm at spike start; the architecture text claims "already a dep" — **VERIFY** rather than trust; per Story 0.2 lesson, trust live files over plan claims). `pnpm install` succeeds with `.npmrc` `node-linker=hoisted` ([INVARIANT 9]) preserved. `pnpm --filter mobile exec expo prebuild` succeeds; `pnpm --filter mobile exec expo export --platform android` produces a Hermes bundle without errors. _If a stable RN-0.81-compatible version does not exist, this AC's failure path is **not** "skip the binding" — it is "spike returns rung 3" (binding cannot ship in V1 timeline). Document the constraint in the spike report._ **Verified 2026-05-09:** `react-native-fast-opencv@0.4.8` installed; the lib was developed against `react-native@0.79.1` but its peer-deps are wildcard and the JSI surface holds across the RN 0.79→0.81 minor gap. `pnpm install` succeeded (one unrelated peer warning: `react-dom@19.2.4` wants `react@^19.2.4`, we have 19.1.0 — does not affect mobile bundling). `expo prebuild --platform android --clean` succeeded; `apps/mobile/android/` regenerated. `expo export --platform android` produced a 5.27 MB Hermes bundle (`_expo/static/js/android/index-9491fc77a198e675a775b8da260972f8.hbc`) with no warnings about the new native module. `apps/mobile/android/` and `apps/mobile/ios/` added to root `.gitignore` so prebuild artifacts are not committed.

3. [x] **AC3 — Reference device profile measured.** **Poco X5 Pro 5G** (model `22101320G` / codename `redwood_eea`; SoC `SM7325` Snapdragon 778G — 1× Cortex-A78 @ 2.4 GHz + 3× Cortex-A78 @ 2.2 GHz + 4× Cortex-A55 @ 1.9 GHz, 4 nm; ~7.0 GiB raw RAM (8 GB SKU); 6.67" 1080×2400 @ 440 dpi screen; Android 14 / HyperOS V816 build `OS2.0.14.0.UMSEUXM`; security patch 2025-11-01). _Re-anchored from the architecture's original "Poco X5 (SD695, A13)" reference — see "Reference device re-anchor" Dev Note for rationale and cascade scope._ Device profile recorded in the spike report's `## Device profile` section: model, SoC, RAM, screen resolution, OS version, Android security-patch level (`adb shell getprop ro.build.version.security_patch`), the dev-build APK SHA-256, and the Hermes engine version reported by `adb logcat | grep -i hermes` at first launch. **Closed 2026-05-09:** all required fields recorded at `_bmad-output/architecture-spike-perf-floor.md:14` (`## Device profile` section); Hermes engine version sub-bullet noted as bundled with React Native 0.81.5 with capture deferred to Story 1.1.1 measurement run per binding-only-cut Dev Note line 257.

4. [ ] **AC4 — PERF-002 measured on the 1h20 EVA After-h reference video.** _**DEFERRED 2026-05-09 to Story 1.1.1** per binding-only-cut decision (see Dev Note "Binding-only cut (2026-05-09)"). The `__DEV__`-gated PERF-002 + per-stage timing instrumentation has been added to `apps/mobile/src/features/video-processing/processingPipeline.ts:245+` for use by Story 1.1.1; it logs `[PERF-002] sessionId=<id> mark=<label> t+<ms>` and persists per-stage timings to MMKV at `processing.<sessionId>.perf002`. Cannot run end-to-end measurement in this branch because gap #6 (`detection_config/latest` not seeded + Firestore rules deny reads + real ROIs not assembled) blocks `runProcessingPipeline` execution._ Original AC text retained: _"Auto-slice run end-to-end against a 1h20 EVA After-h source (architecture-supplied; not committed to repo — Stephane stages locally on the device). Wall-clock auto-slice duration ≤ 5% of source duration (1h20 = 80 min → ≤ 4 min). The measurement excludes app cold-start time (timer starts at `runProcessingPipeline()` entry, stops at `updateSessionStatus(sessionId, 'ready')`). The measurement is the **median of 3 runs** (cold-launch each run; clear MMKV processing checkpoints between runs). All 3 raw numbers + median + variance are recorded in the spike report."_ **For Story 1.1.1**, the budget scales to the actual source duration: at the 1h49m39s reference video, 5% = **329 s ≈ 5m29s**; the absolute pass criterion shifts but the ratio binds.

5. [ ] **AC5 — PERF-003 measured on Cinema Mode view-mode toggle.** _**DEFERRED 2026-05-09 to Story 5.5** (`5-5-view-mode-toggle-full-minimap-minimap-hud-no-player-swap`) per AR-SPIKE scope-split decision (see Dev Note "Spike scope split — PERF-003/004/005 deferred to Epic 5/6")._ The original AC text remains the binding measurement spec; it just runs as part of Story 5.5's ACs instead of this spike. **Carve-out reason:** the Cinema Mode `<Video>` component, `expo-av` (or `expo-video`) dependency, and 3-state view-mode segmented control don't exist in the codebase as of this spike's branch (`ar-spike-perf-floor`). `apps/mobile/src/features/video-playback/CinemaModeScreen.tsx` is a labeled visual stub (top-of-file comment: *"VISUAL STUB — wire the controls + scrub head + minimap toggle to the real player when video-playback feature lands"*). Building those surfaces inside this spike would pollute the measurement-only scope. Stays `[ ]` here; flips on Story 5.5's close. Original AC text retained below for reference: _"From a paid-user dev session with at least one auto-sliced segment opened in Cinema Mode, toggle the view-mode segmented control through Full → Minimap → Minimap+HUD → Full. Frame-time delta for each transition ≤ 100 ms. **No `expo-av` player swap permitted** — the same source must be used; only crop/style change. Measured via Hermes performance API (`performance.now()`) bracketing the toggle handler. Median of 3 sessions × 3 toggles each (9 total samples). All 9 raw numbers + median + p95 in the spike report."_

6. [ ] **AC6 — PERF-004 measured on Cinema Mode cold-start.** _**DEFERRED 2026-05-09 to Story 5.4** (`5-4-cinema-mode-immersive-review-with-reveal-on-tap-controls`) per AR-SPIKE scope-split decision._ **Carve-out reason:** no Card View screen exists (`HomeScreen.handleResume` is a no-op with comment *"Card View lands in Sprint 3; until then we stay on Home"*); no `CinemaMode` route registered in `RootNavigator` (only `Login`/`Home`/`Processing` are routed); no `<Video>` component to attach `onLoadedData` to. Stays `[ ]` here; flips on Story 5.4's close. Original AC text retained for reference: _"Card View → tap Card → first frame visible. Timer starts at the navigation-action dispatch, stops at the first `expo-av` `onLoadedData` event for the Cinema Mode `<Video>`. Median ≤ 1.5 s. Median of 5 cold launches (full app cold-start between each). All 5 raw numbers + median + p95 in the spike report."_

7. [ ] **AC7 — PERF-005 measured on clip export (Mobile-tier).** _**DEFERRED 2026-05-09 to Story 6.6** (`6-6-mobile-hd-encode-tier-selection`) per AR-SPIKE scope-split decision._ **Carve-out reason:** clip-creation surfaces (bracket handles per `mobile-CLIP-001`, clip-from-Cinema-Mode flow per Story 5.3, Mobile-tier export action per Story 6.6) are all Sprint 3 Epic 5/6 work that hasn't shipped. Cannot define + export a 30 s clip from a Cinema Mode that doesn't exist. Stays `[ ]` here; flips on Story 6.6's close. Original AC text retained for reference: _"From a paid-user dev session in Cinema Mode, define a 30 s clip via the bracket handles (per `mobile-CLIP-001`), trigger Mobile-tier export. Timer starts at the export-dispatch action, stops at the FFmpeg-kit completion callback for the encoded MP4. Median encode duration ≤ 60 s (≤ 2× clip duration). Median of 3 clip exports. All 3 raw numbers + median in the spike report."_

8. [ ] **AC8 — Map ID accuracy ≥ 95% on unseen test set.** _**DEFERRED 2026-05-09 to Story 1.1.1** per binding-only-cut decision. **Three substrate issues** (gaps #4, #5, #6) compound for this AC: (a) EVA HUD substrate shift invalidates legacy fingerprints in `map_config.json` for new-HUD content; (b) on-device opencv.ts uses `phash` while legacy `map_config.json` declares `"hash_method": "ahash"` — the methods are not bit-equivalent, so the existing on-device `mapIdentifier` returns null for every segment regardless of input; (c) `detection_config/latest` is not seeded in Firestore so the on-device pipeline can't even start. Story 1.1.1 needs Stories 1-13 / 1-14 / 1-16 to land first PLUS pHash/ahash method reconciliation PLUS new-HUD re-fingerprinting before this AC's measurement is meaningful. Original AC text retained for Story 1.1.1's use._

9. [ ] **AC9 — Round-boundary detection floor validated.** _**DEFERRED 2026-05-09 to Story 1.1.1** per binding-only-cut decision. **Two substrate issues** (gaps #4, #6) compound: (a) EVA HUD substrate shift means the on-device `gameDetector`'s KDA/HSV ROIs (kda, notkda, team_bar) target an old HUD layout that has changed — false-negative rates on new-HUD content will be high until the detector is reworked; the long-GOP `blackScreenDetector` fallback is more substrate-stable (black screens stay black) but still depends on real ROI values; (b) detection_config not seeded blocks the pipeline. The `__DEV__`-gated `[PERF-009]` event-count log added to `processingPipeline.ts` will surface raw event counts (START / END / SCORE_SCREEN + segment count + map-ID count) when Story 1.1.1's measurement runs, but ground-truth comparison (recall/precision/false-positive-rate) is per-substrate. Original AC text retained for Story 1.1.1's use._

10. [~] **AC10 — Ladder rung verdict determined and recorded — PROVISIONAL.** _**FURTHER SCOPE-LIMITED 2026-05-09 (binding-only cut):** with all measurement ACs (AC4, AC5/6/7, AC8, AC9) deferred to Story 1.1.1 (see Dev Note "Binding-only cut (2026-05-09)" + the per-AC carve-outs), no measurement-driven rung verdict is possible from this spike. Story 1.1 publishes a **provisional rung-0 verdict** based on binding-viability evidence only:_ binding compiles, prebuild + export clean, dev-build APK installs + launches cleanly on the X5 Pro. **Provisional verdict: `rung-0 plausible — binding viable; final rung TBD post-Story-1.1.1 measurement; cloud-fallback rung remains FORBIDDEN per AC11 regardless of any future measurement outcome.`** Recorded in the spike report's `## Ladder rung verdict` section with the carve-out + the explicit Story-1.1.1-handoff. The marker `[~]` is used (instead of `[x]` or `[ ]`) to flag the AC as "provisionally closed pending measurement-side closure"; flips to `[x]` when Story 1.1.1's measurement confirms (or revises to rung-1/rung-2/rung-3).

11. [x] **AC11 — `cloud fallback` rung explicitly asserted as forbidden.** Spike report's `## Forbidden rungs` section asserts verbatim: _"Cloud-fallback CV is FORBIDDEN regardless of measured numbers. Breaks Innovation #1 (privacy + lower marginal cost). Not a permitted rung in this spike."_ This is a defense against future dev-agents (or even future-self) interpreting a hard-fail as license to cloud-process frames. **Closed 2026-05-09:** verbatim assertion is in place at `_bmad-output/architecture-spike-perf-floor.md:171`.

12. [x] **AC12 — Spike deliverable published.** `_bmad-output/architecture-spike-perf-floor.md` exists and contains, at minimum, these H2 sections in this order (binding-only-cut scope; see Dev Note "Binding-only cut (2026-05-09)"): `## Device profile` (AC3 — Poco X5 Pro 5G real values), `## Device re-anchor` (2026-05-09 re-anchor rationale), `## JSI binding viability` (AC1 + AC2 closure evidence: build success, APK SHA-256, prebuild + export clean, dev-build launch on device), `## Source video provenance` (the 1h49 720p EVA After-h source — name, duration, resolution, encoder, SHA-256, NOT committed; flag the 1h20/1080p spec divergences), `## Substrate gap audit (six gaps)` (the 6 gaps blocking measurement, with handoff-to-followup-stories), `## Ladder rung verdict — provisional` (AC10 — `rung-0 plausible`, with explicit Story-1.1.1-revision clause), `## Forbidden rungs` (AC11 verbatim), `## Deferred measurements (Story 1.1.1 inheritance)` (which ACs Story 1.1.1 inherits + the substrate-completion preconditions for each), `## V1 implication summary` (binding viable; full-measurement floor TBD post-Story-1.1.1; flag the 778G device-set narrowing), `## Follow-up work required` (concrete handoff to Stories 1-13 / 1-14 / 1-15 / 1-16, new-HUD work, pHash/ahash reconciliation, Story 1.1.1 itself), `## G1 sign-off — partial` (AC16 amended — closes for binding viability + Sprint-3 stories without `Story 1.1 spike` dep; full close pending Story 1.1.1). The file is the binding artifact reviewers grep for. **Closed 2026-05-09:** all 11 H2 sections present in the spec-mandated order at `_bmad-output/architecture-spike-perf-floor.md` (lines 14, 39, 52, 107, 134, 149, 169, 177, 197, 211, 224).

13. [ ] **AC13 — PRD updated post-spike with PERF-010 + conditional FR clauses.** _Held `[ ]` per AC checkbox tighten — this is post-merge admin._ After the spike PR merges, `_bmad-output/prd.md` PERF-010 line gets the measured number substituted in (replacing "TBD per architecture pre-PRD spike"). For rung-1/rung-2, the PRD adds the conditional FR clause exactly as architecture-line 855/856 specifies. For rung-3, the PRD V2-defers `mobile-AUTO-SLICE-001` and `mobile-AUTO-SLICE-002` and the `mobile-CARD-*` entries get the manual-clip-only graceful-degradation clause. This AC ships as a **separate follow-up commit** on the same branch (or a separate PR if the spike PR has already merged); flips to `[x]` once that commit lands on `main`.

14. [x] **AC14 — Sprint-status flip on G1 close.** _Originally held `[ ]` per AC checkbox tighten — the `review → done` portion is post-merge admin._ `_bmad-output/sprint-status.yaml` `development_status[1-1-pre-prd-performance-spike-ar-spike]` flips `backlog → ready-for-dev → in-progress → review → done` across the work; `last_updated` bumps to current ISO date at each flip. `epic-1` flips `backlog → in-progress` when the story file is created (this happens at create-story time — already done by the time the dev agent reads this file; verify it). Flips to `[x]` once `done` lands. **Closed 2026-05-09 (post-merge):** flipped `review → done` in this post-merge follow-up commit; `last_updated` comment records G1 partial close + Story 1.1.1 queued as `backlog`; `epic-1: in-progress` retained (Sprint 3 Epic 1 has 17 more backlog stories).

15. [x] **AC15 — Single-PR delivery (gated by G0).** All file modifications ship in **one PR** titled exactly `feat: AR-SPIKE — pre-PRD performance floor (Story 1.1)`. PR body links to: this story file; `_bmad-output/architecture-spike-perf-floor.md`; Sprint Plan §2 Gate G1 (`_bmad-output/sprint-plan.md` line 31); architecture line 832 (`#### Pre-PRD performance spike [SPIKE BOUND]`). Branch name: `ar-spike-perf-floor`. _Originally held `[ ]` until the PR is filed with the AC15-mandated title verbatim; flips to `[x]` once the PR is open. **The PR may not be merged to `main` until Sprint 0.2 reaches `done` and clears Gate G0** — per Decision #ES-3 / Sprint Plan §2 Gate G0._ **Closed 2026-05-09 (post-merge):** PR #5 (<https://github.com/stwiertz/Warden_monorepo/pull/5>) filed with the AC15-mandated title verbatim, body per spec template (refreshed for binding-only-cut); merged at commit `a633c2e` on 2026-05-09. G0 gate was already cleared (Story 0.2 closed at `e6ad6e0`) before this PR opened; merge unblocked from the start.

16. [x] **AC16 — G1 sign-off statement appended to spike report (partial — provisional rung).** _Originally held `[ ]` until rung verdict is published in the spike report._ A final section `## G1 sign-off` is appended to `_bmad-output/architecture-spike-perf-floor.md` containing exactly: _"Story 1.1 published the AR-SPIKE rung verdict on \<YYYY-MM-DD\>. Sprint Plan §2 Gate G1 is now CLEARED. Sprint 3 stories with explicit `Story 1.1 spike` dependency (5.1, 5.3, 5.4, 5.5, 6.6) may begin development per the rung's V1 implication. PRD update follows in a separate commit per AC13."_ Flips to `[x]` once the section is in place. **Closed (partial) 2026-05-09:** `## G1 sign-off — partial` section is in place at `_bmad-output/architecture-spike-perf-floor.md:224` with the binding-only-cut amendment (closes for binding viability + Sprint-3 stories without `Story 1.1 spike` dep; full close pending Story 1.1.1 final rung).

## Tasks / Subtasks

> **Workflow shape:** This is an **architecture-led spike**, not a feature story. The dev agent's primary obligation is to MEASURE accurately and CHOOSE the rung honestly. A rung-3 verdict is a successful spike outcome, not a story failure. The dev agent MUST NOT silently change PRD numbers, MUST NOT fall back to cloud CV regardless of measurement pressure, and MUST NOT skip ACs by claiming "the binding wouldn't install" — that's exactly the rung-3 trigger that the spike report should articulate.

- [x] **Task 1: Audit current state — opencv.ts, package.json, prebuild config (AC: 1, 2)**
  - [x] Read `apps/mobile/src/shared/services/opencv.ts` end-to-end. Confirm the only entry point that requires the native binding is `loadFrameFromPath` (line 381). Every other primitive (`hsvWhitePixelRatio`, `grayscaleMean`, `saturationMean`, `cropToGrayscale`, `resizeGrayscale`, `phash`, `dct1D`, `dct2D`, `hammingDistance`) is pure TS and has no native dependency. The boundary is intentionally narrow. **Confirmed 2026-05-09:** boundary holds; lines 14-19 define the `FrameBuffer` contract, lines 73-371 are pure-TS detector primitives, lines 381-385 are the throw-stub that this story replaces.
  - [x] Read `apps/mobile/package.json` `dependencies` block. **Verify `react-native-fast-opencv` is or is NOT present.** As of Story 0.2 closure (commit `1c12ff8`), it is **NOT** listed — the architecture text's "already a dep" claim is plan-side, not code-side. The dev agent must install it (`pnpm --filter mobile add react-native-fast-opencv@<latest-stable>`). **Confirmed 2026-05-09:** absent at `1c12ff8`; installed in this story (see Task 2).
  - [x] Confirm `apps/mobile/android/` does not exist (Expo prebuild artifact; `expo prebuild` regenerates it). The dev build flow is `pnpm install → expo prebuild → expo run:android`. **Confirmed 2026-05-09:** absent at branch creation; root `.gitignore` updated to exclude `apps/mobile/android/` and `apps/mobile/ios/` so the regenerated dirs are not committed (prebuild-on-demand convention, matching the unified monorepo's existing state).
  - [x] Confirm `react-native-mmkv` stays pinned at v3 ([INVARIANT 9 + apps/mobile/package.json line 35]). Do not let a transitive dep bump push it to v4 (boot-crash on RN 0.81). **Confirmed 2026-05-09:** `react-native-mmkv@3.3.3` retained after the fast-opencv install; no transitive bump.

- [x] **Task 2: Install and wire `react-native-fast-opencv` (AC: 1, 2)**
  - [x] `pnpm --filter mobile add react-native-fast-opencv@<latest-stable-RN-0.81-compatible>` — verify the resolved version against the lib's CHANGELOG / peerDependencies for RN 0.81 / Expo SDK 54 / Hermes compatibility. Document the version pin choice in the spike report. **Done 2026-05-09:** installed `react-native-fast-opencv@0.4.8` (latest stable on npm). Peer deps are `{ react: '*', react-native: '*' }`. The lib's own `devDependencies` show it was developed against `react-native@0.79.1`/`react@19.0.0` — the JSI surface (`base64ToMat`, `matToBuffer`, `cvtColor`, `clearBuffers`) does not depend on the wider RN bridge surface that changed across 0.79→0.81, and prebuild + export validate this empirically. Version-pin rationale to be repeated in the spike report's `## Library versions` subsection.
  - [x] Replace the `loadFrameFromPath` stub (line 381) with a real implementation. Suggested skeleton (verify against the lib's API surface at install time):
    ```ts
    import { OpenCV, ColorConversionCodes } from 'react-native-fast-opencv';
    export async function loadFrameFromPath(path: string): Promise<FrameBuffer> {
      const mat = OpenCV.createObject('Mat'); // verify exact constructor
      OpenCV.invoke('imread', mat, path);
      const rgbMat = OpenCV.createObject('Mat');
      OpenCV.invoke('cvtColor', mat, rgbMat, ColorConversionCodes.COLOR_BGR2RGB);
      const { width, height } = OpenCV.toJSValue(rgbMat).size;
      const data = OpenCV.toJSValue(rgbMat).data; // packed RGB Uint8Array
      mat.release(); rgbMat.release();
      return { data: new Uint8ClampedArray(data), width, height };
    }
    ```
    The exact JSI surface depends on the installed version; treat the skeleton as illustrative. Critical invariants: (a) the returned `data` MUST be RGB-packed (not BGR) so existing detectors (`hsvWhitePixelRatio`, `cropToGrayscale`) read the right channels; (b) `data.length === width * height * 3`; (c) Mat objects are released to avoid native-heap leaks across thousands of keyframes. **Done 2026-05-09 — actual implementation diverges from the skeleton because `react-native-fast-opencv@0.4.8` does not expose `imread` (no direct file-path entry) and `toJSValue(mat)` returns base64-encoded JPEG/PNG, not raw bytes.** Real flow:
    1. `expo-file-system/legacy.readAsStringAsync(path, { encoding: Base64 })` — read the JPEG keyframe from disk as base64 (mirrors `ffmpeg.ts`'s lazy-require pattern for the legacy module).
    2. `OpenCV.base64ToMat(base64)` — decodes JPEG/PNG → BGR `Mat`.
    3. `OpenCV.createObject(ObjectType.Mat, 0, 0, DataTypes.CV_8UC3)` — empty placeholder for the converted output; `cvtColor` resizes it.
    4. `OpenCV.invoke('cvtColor', bgrMat, rgbMat, ColorConversionCodes.COLOR_BGR2RGB)` — BGR → RGB.
    5. `OpenCV.matToBuffer(rgbMat, 'uint8')` — extracts `{ buffer: Uint8Array, rows, cols, channels }`.
    6. Validates `channels === 3` and `buffer.length === rows*cols*3` defensively (the binding-correctness check; if the binding ever returns 4-channel output, callers would silently misread channels).
    7. `OpenCV.clearBuffers([])` in a `finally` block — releases the native Mats so PSS doesn't grow unboundedly during a long auto-slice run (mitigates the rung-1 trigger flagged in Dev Notes).
    8. The native imports are lazy-required inside the function (matching `ffmpeg.ts`'s `getFFmpeg()` pattern) so jest still loads `opencv.ts` without the native module — detector tests inject synthetic `FrameLoader`s and never hit this code path.
  - [x] `pnpm --filter mobile exec expo prebuild` — should succeed, regenerating `apps/mobile/android/` with the fast-opencv autolinking entries. **Done 2026-05-09:** `expo prebuild --platform android --clean` succeeded; `apps/mobile/android/` regenerated. Only warning: `expo-system-ui not installed` (unrelated, comes from `userInterfaceStyle: dark` in `app.json`).
  - [x] `pnpm --filter mobile exec expo export --platform android` — Hermes bundle smoke check; should succeed without warnings about the new native module. **Done 2026-05-09:** export produced a 5.27 MB Hermes bundle (`_expo/static/js/android/index-9491fc77a198e675a775b8da260972f8.hbc`); no warnings about `react-native-fast-opencv`. The smoke output (`dist-spike/`) was deleted after verification.
  - [x] If the build fails: do NOT silently downgrade or skip — document the failure in the spike report and consider whether this drives a rung-3 verdict (binding cannot ship in V1 timeline). **Not triggered:** prebuild + export both succeeded.
  - [x] **Additional dev-agent action — remove obsolete stub-throw test.** `apps/mobile/src/shared/services/__tests__/opencv.test.ts:237-243` previously asserted that `loadFrameFromPath` throws a `/react-native-fast-opencv/` error — it was a placeholder for the throw-stub. Now that the stub is replaced with the real binding, that assertion is no longer meaningful; deleted and replaced with a comment explaining the intentional test-coverage gap (per Dev Notes "Testing standards summary" — the binding's correctness is validated by on-device measurement against the Python pHash reference, not by jest unit tests). Also removed the now-unused `loadFrameFromPath` import from the test file. Regression: full mobile jest suite passes (105/105 tests).

- [ ] **Task 3: Stage reference device + reference video (AC: 3, 4)**
  - [x] Confirm reference device is reachable via `adb devices`. Capture device profile (model, SoC, RAM, screen resolution, OS, security-patch level) for spike report `## Device profile`. **Done 2026-05-09:** `adb devices` returned `dc72b871` / model `22101320G` / device `redwood`. **Discovery:** the connected device is a Poco X5 **Pro** 5G (SM7325 / Snapdragon 778G / Android 14 / 8 GB RAM), NOT a Poco X5 (SD695 / Android 13 / 6 GB RAM) as the architecture originally bound. Re-anchored per Stephane's call (see "Reference device re-anchor" Dev Note); story file + AC3 patched accordingly. Full profile captured: brand `POCO`, model `22101320G`, codename `redwood_eea`, SoC `SM7325` (`SM7325` per `ro.soc.model`; manufacturer `QTI` per `ro.soc.manufacturer`), MIUI/HyperOS `V816` build `OS2.0.14.0.UMSEUXM`, Android `14` (SDK `34`), security patch `2025-11-01`, screen `1080x2400` @ density `440`, MemTotal `7363096 kB`. Hermes version + dev-build APK SHA-256 captured at Task 3 sub-bullet 3 (post-`expo run:android`).
  - [x] Stage the EVA After-h reference video on the device. **Do NOT commit the video to the repo.** Record name, duration, resolution, encoder (mediainfo / ffprobe output) in the spike report `## Source video provenance`. **Done 2026-05-09:** the file is already staged at `/sdcard/Download/2026-01-18 12-10-30.mp4` (2,158,588,458 bytes; SHA-256 `7f958d532863ddf3bec2482c967e151f97f6a50554d374e57e2f2badbf35f38b`). Probed via `adb pull` + local `ffprobe` (the moov atom is not in the head-64-MB nor tail-64-MB region — fragmented or mid-file location; full pull was needed).
    - **Provenance fields** (for spike report `## Source video provenance`):
      - **Path on device:** `/sdcard/Download/2026-01-18 12-10-30.mp4`
      - **Recording origin:** Windows-recorded (top-level `uuid` atom embeds Windows build string `10.0.26100.0` = Windows 11 24H2)
      - **Container:** MP4 (`major_brand: mp42`, `compatible_brands: mp41 isom`)
      - **Video stream:** H.264 Main profile (avc1), yuv420p progressive, 1280×720 (SAR 1:1, DAR 16:9), 30 fps, 2,461 kb/s, 197,388 frames, level 3.1
      - **Audio stream:** AAC LC (mp4a), 44.1 kHz stereo, 160 kb/s
      - **Overall bitrate:** 2,624 kb/s
      - **Duration:** 01:49:39.61 (6,579.6 seconds)
      - **Creation time:** 2026-01-18T13:21:02 UTC
    - **Divergences from spec (must be flagged in spike report):**
      1. **Duration:** 1h49m39s actual, vs 1h20m architecture-spec'd. AC4's pass criterion is **ratio-based** ("≤ 5% of source duration"), so it scales: budget = 5% × 6580 s = **329 s ≈ 5m29s** (vs the 4m AC4 example for 1h20). The ratio binds; the absolute number scales with source.
      2. **Resolution:** 1280×720 actual, vs the architecture-implied 1080p reference. **720p source under-represents 1080p workload** — less I/O during keyframe extraction, smaller decode cost, smaller crop+resize input. PERF-002 measured on 720p is a **lower bound** for the 1080p case. Spike report `## PERF-002 — auto-slice` will flag this; a 1080p re-measurement (post-spike) would tighten the floor.
      3. **Recording origin:** Windows desktop capture, not Android device capture. Codec/profile (H.264 Main 30 fps yuv420p) is representative of typical mobile-friendly H.264 sources, but exact GOP structure may differ from a phone-camera or in-app capture (probe via `getGopInfo` at Task 9 round-boundary detection step).
    - **Stephane confirmed (2026-05-09)** these divergences are acceptable for the spike measurement; the goal is to produce a binding rung verdict on the actual hardware + workload available, not to wait for a perfect-spec source. Re-measurement on a true 1h20 1080p source can be a follow-up if the rung-0 verdict is borderline.
  - [ ] Install the dev build APK on the Poco X5 Pro 5G (`pnpm --filter mobile exec expo run:android` against a connected device). Capture Hermes engine version (`adb logcat | grep -i hermes` at first launch) + dev-build APK SHA-256 (`sha256sum apps/mobile/android/app/build/outputs/apk/debug/app-debug.apk` or equivalent) for the `## Device profile` section.

- [ ] **Task 4: Measure PERF-002 (auto-slice end-to-end on 1h20 source) (AC: 4)**
  - [ ] Cold-launch the app, sign in (use `EXPO_PUBLIC_AUTH_BYPASS=false` per [INVARIANT 8]; do not bypass auth — the entitlement gate must pass for `runProcessingPipeline` to fire).
  - [ ] Import the 1h20 reference video via the document picker.
  - [ ] Wrap `runProcessingPipeline` (or its outer caller in `useVideoProcessing.ts`) with a wall-clock timer: start at `runProcessingPipeline` entry, stop at `updateSessionStatus(sessionId, 'ready')`. Implementation suggestion: a temporary `console.time('perf-002')` / `console.timeEnd('perf-002')` log captured via `adb logcat`, then resolved via `--filter Reactnative` or a runtime `__DEV__`-gated MMKV write of the elapsed ms.
  - [ ] Run 3 times; cold-launch the app each time; clear MMKV processing checkpoints (`storage.deleteAll()` is too broad — selectively clear `processing.*` keys) between runs.
  - [ ] Record the 3 raw numbers + median + variance in the spike report `## PERF-002 — auto-slice`. Pass criterion: median ≤ 240 000 ms (4 min for 1h20).

- [ ] **Task 5: Measure PERF-003 (view-mode toggle ≤ 100 ms) (AC: 5)** — _**DEFERRED 2026-05-09 to Story 5.5** per scope-split (see Dev Note)._ The original sub-bullets remain the binding measurement spec for whoever picks up Story 5.5; they don't run as part of this spike.
  - [ ] _DEFERRED:_ Open Cinema Mode for one auto-sliced segment.
  - [ ] _DEFERRED:_ Wrap the view-mode-toggle handler with `performance.now()` bracketing. Toggle Full → Minimap → Minimap+HUD → Full. Record per-transition ms.
  - [ ] _DEFERRED:_ Confirm **no `expo-av` source swap** — verify by inspecting React DevTools (or instrumenting the `<Video>` component) that the same `source` prop instance is reused across toggles; only crop/style props change.
  - [ ] _DEFERRED:_ Run 3 sessions × 3 toggles = 9 samples. Record raw + median + p95 in `## PERF-003` (of Story 5.5's spike-report addendum or its own implementation-record).

- [ ] **Task 6: Measure PERF-004 (Cinema Mode cold-start ≤ 1.5 s) (AC: 6)** — _**DEFERRED 2026-05-09 to Story 5.4** per scope-split._
  - [ ] _DEFERRED:_ From Card View, tap a Card. Timer starts at the navigation dispatch (`navigation.navigate('CinemaMode', ...)`), stops at the first `<Video onLoadedData>` event.
  - [ ] _DEFERRED:_ Run 5 cold launches (full app cold-start, then immediate Card-tap). Record raw + median + p95 in `## PERF-004`.

- [ ] **Task 7: Measure PERF-005 (clip export ≤ 60 s for 30 s Mobile-tier clip) (AC: 7)** — _**DEFERRED 2026-05-09 to Story 6.6** per scope-split._
  - [ ] _DEFERRED:_ In Cinema Mode, define a 30 s clip via the bracket handles. Trigger Mobile-tier export.
  - [ ] _DEFERRED:_ Timer from export-action dispatch to FFmpeg-kit completion callback (the same FFmpeg path used in `apps/mobile/src/shared/services/ffmpeg.ts`).
  - [ ] _DEFERRED:_ Run 3 clip exports. Record raw + median in `## PERF-005`.

- [ ] **Task 8: Validate map ID accuracy ≥ 95% on unseen test set (AC: 8)**
  - [ ] Source an unseen test set: frames sampled from EVA After-h matches that are NOT in the `map_config.json` reference fingerprint set. Aim for ≥ 30 frames per canonical map (× 14 maps = ≥ 420 frames) for statistically meaningful per-map accuracy.
  - [ ] Run `apps/tooling/tools/hash_validator.py` against the test set; capture overall + per-map accuracy. _The Python tool is the authoritative reference per architecture line 558._
  - [ ] **Cross-check the on-device output**: Run the same frames through the on-device `mapIdentifier` (via a dev-only test harness; do NOT add it to production code) and confirm the Hamming distances match the Python reference for the same input. Discrepancy = binding-correctness bug; halt the spike, root-cause, fix, re-test.
  - [ ] Record the confusion matrix + accuracy numbers in `## Map ID accuracy`. Pass: overall ≥ 95% AND per-map ≥ 90%.

- [ ] **Task 9: Validate round-boundary detection floor (AC: 9)**
  - [ ] Run the full processing pipeline against the 1h20 reference video. Capture all START/END events emitted by `gameDetector` (or the long-GOP `blackScreenDetector` fallback if the source has GOP > 2 s — verify with `getGopInfo`).
  - [ ] Compare against ground truth (Stephane manually annotates the round boundaries in the reference video, or relies on a pre-existing labeled reference set).
  - [ ] Compute: (a) recall (detected STARTs ÷ ground-truth STARTs); (b) precision (correctly-detected STARTs ÷ all detected STARTs — i.e., 1 - false-positive-rate); (c) END-event accuracy. Record in `## Round-boundary detection floor`.
  - [ ] **The spike SETS the floor.** The legacy tooling target ("100% black-screen-transition detection with 0 false positives") is a ceiling; the on-device port may degrade. The dev agent records the measured number and writes a justified verdict — does the floor support a rung-0 / rung-1 / rung-2 / rung-3 outcome?

- [ ] **Task 10: Determine ladder rung verdict (AC: 10, 11)**
  - [ ] Aggregate AC4–AC9 measurements. Apply the ladder logic from architecture line 854–858:
    - All 4 PERF NFRs met + accuracy floors met → **rung-0**.
    - PERF-002 OR PERF-005 over by < 50% → attempt rung-1 (lower sampling); re-measure; if recovers → rung-1 verdict; if not → rung-3.
    - PERF-003 OR PERF-004 over budget → attempt rung-2 (drop Minimap+HUD on weak hardware); re-measure; if recovers → rung-2 verdict; if not → rung-3.
    - JSI binding wouldn't install OR multiple PERFs > 50% over and rungs 1/2 don't recover → **rung-3** (defer auto-slice to V2).
  - [ ] Write `## Ladder rung verdict` in the spike report with the choice + driving measurements + tuning attempts (rung-1/rung-2) + V2-deferred FR list (rung-3).
  - [ ] Write `## Forbidden rungs` in the spike report with the verbatim cloud-fallback assertion per AC11.

- [ ] **Task 11: Publish spike deliverable (AC: 12, 16)**
  - [ ] Write `_bmad-output/architecture-spike-perf-floor.md` with all required H2 sections (per AC12). Each section is data-first (raw numbers + median/p95 first) and prose-second (interpretation last).
  - [ ] Append `## G1 sign-off` per AC16 (verbatim text).
  - [ ] Cross-link the spike report from the story file's References section (already done in this template — verify on close).

- [ ] **Task 12: Update sprint-status, branch + commit + PR (AC: 14, 15)** — _partially done by dev agent at HALT-point; commit/push/PR remain for post-measurement work._
  - [x] `_bmad-output/sprint-status.yaml` flip `1-1-pre-prd-performance-spike-ar-spike: ready-for-dev → in-progress` (when work begins) → `review` (when code-review starts) → `done` (post-PR-merge admin). `last_updated` bumps each flip. _Already flipped `backlog → ready-for-dev` by `bmad-create-story`._ **Done 2026-05-09:** flipped working-tree `ready-for-dev → in-progress` and bumped `last_updated` comment to describe the branch state (cut from main; in-progress; Tasks 1-2 complete; Tasks 3-9 paused for hardware). Per Story 0.2 Lesson #7, the eventual commit will collapse to `backlog → review` in a single diff once review begins.
  - [x] Verify `epic-1: in-progress` (already done by `bmad-create-story` since this is the first story in epic-1). **Confirmed 2026-05-09** in working tree.
  - [x] `git checkout -b ar-spike-perf-floor`. **Done 2026-05-09:** branch cut from `main@76fec7c`. Story 1.1 planning state (sprint-status flip + new story file) was stashed off Story 0.2's branch (`sprint-2-5-disposition-execution`) and restored onto the new branch — one trivial conflict on `sprint-status.yaml`'s `last_updated` comment was resolved by keeping the Story-1.1 narrative.
  - [ ] **Commit shape recommendation (not AC-bound):** Two commits — `feat: wire react-native-fast-opencv JSI binding for loadFrameFromPath` (covers AC1/AC2 code) + `docs: publish AR-SPIKE performance-floor report (Story 1.1)` (covers AC12/AC16 + this story file + sprint-status). Single-commit `feat: ...` is also acceptable; AC15 binds the PR title, not the commit subject. Both subjects use lower-case verb-first per `@commitlint/config-conventional` (verified at `commitlint.config.ts`). _Pending Stephane's call — see Dev Agent Record → Completion Notes for the HALT-point handoff options._
  - [ ] Push branch. Capture the PR-create URL returned by `git push -u origin ar-spike-perf-floor` (no `gh` CLI on Stephane's host — manual PR open via the URL, per Story 0.2 lesson at line 213).
  - [ ] Open the PR with **exact** title `feat: AR-SPIKE — pre-PRD performance floor (Story 1.1)` per AC15 (paste verbatim from Dev Notes "PR title and body to file").
  - [ ] **Do NOT merge** until Story 0.2 reaches `done` and `_bmad-output/sprint-2.5-conflict-audit.md` shows the G0 sign-off section on `main`. G0 blocks all Sprint 3 merges per Decision #ES-3.

- [ ] **Task 13: Post-merge admin (AC: 13, 14)** — _all sub-bullets here flip after the spike PR merges, on a follow-up admin commit._
  - [ ] `_bmad-output/prd.md` PERF-010 line gets the measured number substituted in (replacing "TBD per architecture pre-PRD spike (Risk #2 escalation)").
  - [ ] For rung-1/rung-2 verdicts: PRD adds the conditional FR clauses verbatim per architecture line 855/856.
  - [ ] For rung-3 verdict: PRD V2-defers `mobile-AUTO-SLICE-001`/`002`; updates `mobile-CARD-*` graceful-degradation entries.
  - [ ] Commit: `docs: update PRD with AR-SPIKE rung verdict (Story 1.1 follow-up)`.
  - [ ] Sprint-status.yaml: `1-1-pre-prd-performance-spike-ar-spike: review → done`. `last_updated` bumps. Comment header line updated.
  - [ ] Flip AC13 + AC14 + AC15 + AC16 to `[x]` once the admin commit lands. Update Dev Agent Record's Completion Notes.

### Review Findings (2026-05-09)

> Code review run on branch `ar-spike-perf-floor` (vs `main`) using parallel adversarial layers (Blind Hunter, Edge Case Hunter, Acceptance Auditor). Triage: 8 patches, 4 defers; ~22 raised findings dismissed as noise/handled/intentional (e.g., gitignore is per AC2; `react-native-fast-opencv@0.4.8` exact-pin is per spec; `expo-file-system@^19.0.21` IS declared; `__DEV__` is the standard RN ambient global; `storage.setObject` is sync; jest test removal is documented in the replacement comment). 1 decision-needed item resolved → patch (AC10 wording normalized to `rung`).

**Patch (all resolved 2026-05-09)**

- [x] [Review][Patch] **AC10 wording — normalized `final verdict TBD` → `final rung TBD`** — AC10 body at story line 53 now reads `final rung TBD`, matching Dev Note line 254 and spike report `architecture-spike-perf-floor.md:151`. (Resolved from a decision-needed finding.)
- [~] [Review][Patch] **`OpenCV.clearBuffers([])` semantics — verified correct after lib-source check** — original Blind Hunter concern was based on misreading the API. Verified at `node_modules/react-native-fast-opencv/src/utils/UtilsFunctions.ts:20`: signature is `clearBuffers(idsToKeep?: string[])` — the parameter is IDs to **keep**, so `[]` = "keep nothing" → clear all. Code unchanged on this front; function-comment documentation tightened to make the semantics explicit.
- [x] [Review][Patch] **Mat-handle leak in narrow window between allocations + release-side throw masking original error** — both `OpenCV.base64ToMat` and `OpenCV.createObject` now allocate inside the `try`, so a throw between them no longer orphans `bgrMat`. The `finally`'s `clearBuffers([])` is wrapped in an inner try/catch so a release-side throw doesn't replace the underlying decode error. [`apps/mobile/src/shared/services/opencv.ts:417-498`]
- [x] [Review][Patch] **Silent zero-FrameBuffer on null `base64ToMat` / 0×0 `matToBuffer`** — added `if (!bgrMat) throw …` after base64ToMat and `if (rows === 0 || cols === 0) throw …` after matToBuffer.
- [x] [Review][Patch] **Bare `catch {}` collapsed two require failures into one error — split** — separate try/catches per module, each preserves the underlying error via `cause`, error message identifies which module is missing.
- [x] [Review][Patch] **AC11 / AC12 / AC16-partial checkboxes flipped to `[x]`** — per the AC checkbox tighten convention. Each item now carries a `**Closed 2026-05-09:**` provenance note pointing at the spike report line where its deliverable lives. AC15 stays `[ ]` (PR-open trigger); AC13/AC14 stay `[ ]` (post-merge admin).
- [x] [Review][Patch] **PERF-009 log-line field order normalized to spec** — `[PERF-009] sessionId=<id> events START=… END=… SCORE=… segments=… mapIDs=… gop_avg_s=… hasShortGop=…` now matches the spec-quoted prefix at `architecture-spike-perf-floor.md:195`. [`processingPipeline.ts:362`]
- [x] [Review][Patch] **Catch path now persists `__perfStages` to MMKV** — error branch records `__perfStages.total` + `__perfStages.errored = 1`, then writes to `processing.<sessionId>.perf002` with the same best-effort semantics as the success branch. Failed-run timing trails are now diagnostic for Story 1.1.1.

**Defer**

- [x] [Review][Defer] **`clearCheckpoint` doesn't delete `events`/`gameSegments`/`mapIdentifications`/`perf002` MMKV keys** — deferred, pre-existing tech debt extended (not introduced) by this diff. Stale keys leak across runs. [`processingPipeline.ts:104-106`]
- [x] [Review][Defer] **Stage labels embed unbounded counts (`keyframes_done_count=1342`)** — deferred to Story 1.1.1. Design choice that makes cross-run aggregation harder; revisit if Story 1.1.1 wants stable keys + sidecar count fields. [`processingPipeline.ts:311, 365, 395, 480`]
- [x] [Review][Defer] **PERF-009 only emitted when detection runs this invocation** — deferred. Guarded by `if (!detectionDone)`; resumed sessions skip it. Story 1.1.1's measurement is cold-launch with cleared MMKV per spec, so won't bite the measurement. [`processingPipeline.ts:352-365`]
- [x] [Review][Defer] **Base64 round-trip + `Uint8ClampedArray(buffer)` copy = ~2-3× memory per frame** — deferred to Story 1.1.1. Only API the lib exposes; flag for Story 1.1.1's measurement to consider whether the perf cost is acceptable for V1. [`opencv.ts:429-462`]

## Dev Notes

### What this story is — and is NOT

- ✅ **IS:** A measurement spike that produces a binding rung verdict for V1 launch criteria. Output = real OpenCV JSI binding code (apps/mobile/) + spike report markdown (`_bmad-output/architecture-spike-perf-floor.md`) + PRD update follow-up (post-merge).
- ✅ **IS:** A V1-launch-blocking deliverable. The spike's outcome conditions Sprint 3 mobile scope. Without it, Wave 6 (Epic 5/6 mobile features) cannot start with a defined scope.
- ❌ **IS NOT:** A feature story. The binding code is in service of the measurement; this story does NOT ship `mobile-AUTO-SLICE-001` or any other FR. Those ship in subsequent Sprint 3 stories that depend on this spike's verdict.
- ❌ **IS NOT:** A guarantee that the spike "passes". Rung-3 (V2-defer auto-slice) is a permitted, fully-acknowledged outcome that still ships V1. The spike report MUST be honest about which rung was reached.
- ❌ **IS NOT:** A license to fall back to cloud CV. AC11 makes this explicit. Even if every PERF NFR misses by 100×, the verdict is rung-3 (manual-clip-only V1), not "send frames to a server".
- ❌ **IS NOT:** Blocked by Story 0.2's review state — development may proceed on a feature branch. **Merge** is blocked by G0 (Story 0.2 reaching `done`).

### Preconditions the dev agent must verify before starting Task 4

These are external dependencies. If any is missing, the spike either (a) waits, or (b) records a partial outcome with an honest "could not measure due to missing precondition" note in the spike report.

| Precondition | Verification | If missing |
|---|---|---|
| Reference device reachable (Poco X5 Pro 5G per re-anchor; see Dev Note) | `adb devices` returns it | Spike halts; cannot measure on reference device. Record device unavailability in report; flag for Stephane. **Confirmed 2026-05-09:** device `dc72b871` reachable; mismatch with original-spec Poco X5 surfaced and re-anchored to X5 Pro 5G per Stephane. |
| Android 13 OS version | `adb shell getprop ro.build.version.release` returns "13" | Note OS version actually present; spike still proceeds — measurements anchored to the actually-tested device. |
| 1h20 EVA After-h reference video staged on device | File exists at `/sdcard/Movies/<name>.mp4` (or document-picker-reachable path); `mediainfo` confirms duration ≈ 80 min | Stephane sources from his archive; spike report records the specific source file (name, duration, resolution, encoder). |
| Unseen map-ID test set available | ≥ 420 frames (≥ 30 per canonical map × 14 maps) labeled with ground-truth map name | Stephane sources from his frame_labeler exports OR generates from the reference video segments; record provenance. |
| `apps/tooling/tools/hash_validator.py` runnable | `cd apps/tooling && python tools/hash_validator.py --help` returns help text | Repair the tooling environment first (the legacy regression tool is the authoritative reference for AC8). |
| `react-native-fast-opencv` has a stable RN-0.81-compatible release | Check `npm view react-native-fast-opencv versions --json` and the lib's GitHub releases at install time | If no compatible release: this is exactly the rung-3 trigger (AC2 fail path); document and verdict accordingly. |

### Reference device profile (Poco X5 Pro 5G — re-anchored)

**Live, measured profile as of 2026-05-09 (binding):**

- Brand `POCO`, model `22101320G`, codename `redwood_eea` → Poco **X5 Pro 5G** (EEA / European variant)
- SoC `SM7325` = Qualcomm Snapdragon 778G (1× Cortex-A78 @ 2.4 GHz + 3× Cortex-A78 @ 2.2 GHz + 4× Cortex-A55 @ 1.9 GHz, Adreno 642L GPU, 4 nm process)
- RAM: 7,363,096 kB raw via `/proc/meminfo` → 8 GB SKU
- Screen: 1080×2400 @ 440 dpi physical density, 6.67" panel
- OS: Android 14 (SDK 34), HyperOS V816, build `OS2.0.14.0.UMSEUXM`, security patch 2025-11-01
- Hermes engine version: TBD (capture from `adb logcat | grep -i hermes` at first dev-build launch)
- Dev-build APK SHA-256: TBD (capture from `apps/mobile/android/app/build/outputs/apk/debug/app-debug.apk` after `expo run:android`)

### Binding-only cut (2026-05-09) — Story 1.1.1 inherits measurement

After two further substrate gaps surfaced in Session 2 (gaps #5 and #6 below), Stephane chose to **cut Story 1.1 to binding-only scope** and defer all measurement ACs to a new follow-up Story 1.1.1. The spike-as-spec'd assumed a substrate stack that doesn't exist in the codebase yet; rather than bundle 1-3 hours of infrastructure work into a "measurement spike" that fundamentally can't measure today, ship the binding-viability evidence + a clean handoff.

**What the spike closes (AC1, AC2, AC3, AC11, AC12, AC15, AC16 partial):**

- **AC1 — JSI binding viable.** `react-native-fast-opencv@0.4.8` compiles into the dev-build APK without errors; APK launches cleanly on the Poco X5 Pro 5G `dc72b871` (BUILD SUCCESSFUL in 5m 25s; `app-debug.apk` 175 MB SHA-256 `5fdad9771468f7b49ae434a7aea50904314a8c861c9b37b951cab594d1053ae3`; `team.warden.mobile/.MainActivity` reached MainActivity focus PID 23079, Metro bundler connected). The native module loads without React Native bridge errors. **End-to-end keyframe-decode validation deferred** to Story 1.1.1 (gap #6 blocks the auto-slice path).
- **AC2 — Dep installed + prebuild + export clean.** Done Session 1.
- **AC3 — Device profile captured.** Real X5 Pro 5G profile (SM7325 / Android 14 / 8 GB / HyperOS V816 / security patch 2025-11-01); APK SHA-256 captured. Hermes version: bundled with React Native 0.81.5 (exact commit pinned in RN source tree; not surfaced in user-readable logcat tags during this session — Story 1.1.1 measurement run can capture it via `adb logcat -s ReactNativeJS` during a real auto-slice).
- **AC11 — Cloud-fallback rung asserted FORBIDDEN.** Verbatim assertion in spike report; no cloud-fallback code added regardless of substrate findings.
- **AC12 — Spike report published.** With binding-only-cut layout (see updated AC12).
- **AC15 — Single-PR delivery.** PR title binds verbatim per the original AC15.
- **AC16 — G1 sign-off (partial).** Sprint Plan §2 G1 closes for binding viability + Sprint-3 stories without `Story 1.1 spike` dep; full close (Stories 5.x / 6.x dependencies) waits on Story 1.1.1's measurement.

**What Story 1.1.1 inherits (AC4, AC5, AC6, AC7, AC8, AC9, AC10 final, AC13):**

| AC | Story 1.1.1 dependency |
|---|---|
| AC4 — PERF-002 wall-clock | Gap #6 (detection_config + rules) |
| AC5 — PERF-003 view-mode toggle | Story 5.5 (Cinema Mode + view-mode toggle UI) |
| AC6 — PERF-004 Cinema cold-start | Story 5.4 (Cinema Mode + Card View) |
| AC7 — PERF-005 clip export | Story 6.6 (Mobile-tier export action) |
| AC8 — Map ID accuracy | Gaps #4 (new HUD), #5 (pHash/ahash), #6 (config seed) — three-substrate stack |
| AC9 — Round-boundary detection floor | Gaps #4 (new HUD), #6 (config seed) |
| AC10 — Final rung verdict | All measurement ACs closed → final rung pickable from rung-0 / rung-1 / rung-2 / rung-3 ladder |
| AC13 — PRD update post-measurement | Final rung verdict published |

**Provisional rung verdict for Story 1.1:** **`rung-0 plausible — binding viable; final rung TBD post-Story-1.1.1 measurement; cloud-fallback rung remains FORBIDDEN per AC11 regardless of any future measurement outcome.`** This provisional verdict allows Sprint 3 stories with explicit `Story 1.1 spike` dependency (5.1, 5.3, 5.4, 5.5, 6.6) to **plan against rung-0** but be ready to revise scope if Story 1.1.1's measurement comes back hostile.

### Substrate gap audit (2026-05-09) — six gaps blocking measurement

For the spike report's `## Substrate gap audit` section. Each gap has a Sprint-3 follow-up handoff.

| # | Gap | Discovered | Handoff |
|---|---|---|---|
| 1 | Wrong reference device — connected device is Poco X5 Pro 5G (SM7325 / SD778G / Android 14 / 8 GB), not Poco X5 (SD695 / Android 13 / 6 GB) the architecture/PRD/UX bound. | Session 2 — `adb devices` returned model `22101320G` codename `redwood_eea` | **Re-anchored** to X5 Pro 5G in this story; cross-cutting cascade through `architecture.md:839`, `prd.md:669`, `epics-and-stories.md:749`, `ux-design.md` (multiple), `sprint-status.yaml` comment is **AC13-extended post-merge admin** scope. |
| 2 | Wrong source video — `/sdcard/Download/2026-01-18 12-10-30.mp4` is 1h49m39s @ 1280×720 (Windows-recorded screen capture per `uuid` atom embedding Windows build `10.0.26100`), not 1h20 @ 1080p as architecture line 839 implies. | Session 2 — local `ffprobe` after `adb pull` (the moov atom is mid-file; head + tail probes failed) | **Accepted with caveats**: AC4's pass criterion is ratio-based so budget scales (5% × 6580 s = 5m29s); 720p source under-represents 1080p workload (PERF-002 measurement on this source is a lower bound for V1). Story 1.1.1 should rerun on 1080p source if available. |
| 3 | Cinema Mode / Card View / clip-creation surfaces missing — `apps/mobile/package.json` has no `expo-av`/`expo-video` dep; no `<Video>` component anywhere; `CinemaModeScreen.tsx` is a labeled visual stub (line 15-19); `RootNavigator` only routes Login → Home → Processing (no Cinema/Card routes); `HomeScreen.handleResume` is a no-op. | Session 2 — code-side audit before instrumenting AC5/6/7 | **AC5/6/7 deferred** to Stories 5.5 / 5.4 / 6.6 respectively (see Dev Note "Spike scope split — PERF-003/004/005 deferred to Epic 5/6 (2026-05-09)"). Those stories carry inherited "PERF measurement" obligations as part of their ACs. |
| 4 | EVA HUD substrate shift — Stephane confirms EVA has launched a new HUD; map-ID surfaces (HUD layout, minimap placement) and round START/END recognition (KDA layout) all changed. The 1h49 reference video + `apps/tooling/output/map_config.json` fingerprints + `gameDetector` ROIs are all pre-shift content. | Session 2 — Stephane's domain knowledge | **Sentinel-only measurement** acceptable on old-HUD content (per Stephane's call to "do the full set up with the older video for dev purpose and then update it"). New-HUD revalidation is **mandatory pre-V1**: re-fingerprint the 14 canonical maps under new HUD; rework KDA/HSV ROIs in `detection_config`; rerun AC8 + AC9 measurement. Likely a dedicated Sprint 3 story (not yet in `sprint-status.yaml`). |
| 5 | pHash (on-device `apps/mobile/src/shared/services/opencv.ts:phash`) vs ahash (`map_config.json` declares `"hash_method": "ahash"`) divergence — the on-device `mapIdentifier` calls `phash(...)` and Hamming-compares against `map_config.json`'s ahash fingerprints. Methods are not bit-equivalent → every map ID returns null today, regardless of input. Even if `detection_config/latest` is seeded from `map_config.json` verbatim, the on-device `mapIdentifier` cannot match any fingerprint. | Session 2 — code audit + map_config.json inspection | Method reconciliation required: either (a) swap on-device `phash` → `ahash` (then re-test all `mapIdentifier` jest fixtures), or (b) regenerate `map_config.json` with phash via `apps/tooling/tools/map_config_generator.py` (would need a `--method=phash` flag). **Either way ties into the new-HUD re-fingerprinting work** (gap #4) — do both at the same time. Story TBD. |
| 6 | `detection_config/latest` not seeded in Firestore + Firestore rules deny reads of `detection_config/{cfg}` (`apps/web/firestore.rules:8-10` catch-all denies everything except `/users/{userId}` for owner) + real ROI values not assembled into the on-device `DetectionConfig` schema (legacy `map_config.json` has only `roi.map_name`; on-device needs 6 ROIs: `minimap`, `vertical`, `team_bar`, `kda`, `notkda`, `map_name`). | Session 2 — first dev-build launch logged `[detectionConfig] initial fetch failed FirebaseError: Missing or insufficient permissions` + `[subscription] checkSubscription failed FirebaseError: Missing or insufficient permissions` | **Sprint 3 Stories 1-13** (`hybrid-map-config-delivery-schema-version-1`) + **1-14** (`firestore-rules-coverage-extended`) + **1-15** (`firestore-rules-production-deploy`) + **1-16** (`detection-config-latest-operator-documentation`) cover this. Story 1.1.1's measurement waits on these. |

### Spike scope split — PERF-003/004/005 deferred to Epic 5/6 (2026-05-09)

When the dev agent (Session 2) prepared to instrument PERF-003/004/005 measurement hooks, code-side audit of `apps/mobile/` revealed that the surfaces those ACs target **do not exist in the codebase yet**:

- **`expo-av` / `expo-video` not in deps.** `apps/mobile/package.json` declares no video player. There is no `<Video>` component anywhere in the source tree.
- **`CinemaModeScreen.tsx` is a labeled visual stub.** Top-of-file comment (line 15-19): *"VISUAL STUB — wire the controls + scrub head + minimap toggle to the real player when video-playback feature lands. The controls overlay is currently always visible; the design calls for tap-to-reveal + auto-hide after 4s."* The component renders a stylized `MapArt` placeholder, not real video. The view-mode toggle is 2-state (minimap on/off), not the 3-state (Full → Minimap → Minimap+HUD) AC5 requires.
- **No `CinemaMode` route registered.** `RootNavigator.tsx` only routes `Login`, `Home`, `Processing`. Cinema Mode is unreachable from in-app navigation.
- **No Card View screen.** `HomeScreen.handleResume` is a no-op with comment *"Card View lands in Sprint 3; until then we stay on Home"*.
- **No clip-creation surfaces.** No bracket-handle UI, no clip-from-Cinema-Mode flow, no Mobile-tier export action wired through `apps/mobile/src/shared/services/ffmpeg.ts`'s `executeWithArguments` for an export use case.

These surfaces are the substance of Epic 5 (5.1 Card View, 5.2 Card→Cinema nav, 5.3 timeline manual clip, 5.4 Cinema Mode immersive review, 5.5 view-mode toggle, 5.6 default-Full-for-unknown-map, 5.7 view-mode persistence, 5.8 next/previous explicit buttons) and Epic 6 (6.1 30-s clip region, 6.2 manual-clip-from-timeline, 6.3 voice annotation, 6.4 voice re-record, 6.5 clip preview, 6.6 Mobile/HD encode tier, 6.7 share sheet, 6.8 Discord H264/AAC, 6.9 clip deletion). **Per Sprint Plan §2 G1, those Epic 5/6 stories carry an explicit `Story 1.1 spike` dependency and cannot start until this spike closes G1.** Chicken-and-egg: the spike needs the surfaces to measure; the surfaces can't be built until the spike clears them.

**Decision (Stephane, 2026-05-09):** Scope-split the spike. Measure what's measurable today; transfer PERF-003/004/005 measurement obligation to the matching Epic 5/6 stories as inherited ACs. Path A (scope-split) was chosen over Path B (build a `__DEV__`-only perf harness inside this spike — would have added 2-5 days of harness work and polluted the spike's measurement-only scope) and Path C (defer the whole spike — would have broken the Sprint Plan §2 dependency chain).

**What this spike now measures (Tasks/ACs that remain in scope):**

| AC | Subject | Path |
|---|---|---|
| AC1 | Real OpenCV JSI binding for `loadFrameFromPath` | Verified by AC4's auto-slice running to completion (binding fires on every keyframe; no crash = AC1 holds) |
| AC2 | `react-native-fast-opencv` dep + prebuild clean | Done Session 1 |
| AC3 | Reference device profile (Poco X5 Pro 5G — re-anchored) | Done Session 2 (Hermes version + APK SHA-256 captured at dev-build install) |
| AC4 | PERF-002 auto-slice ≤ 5% source duration | Measured Session 2 via Home → Import → Processing flow (3 cold-launch runs on the 1h49 source; budget = 329 s) |
| AC8 | Map ID accuracy ≥ 95% on unseen test set | Measured Session 2 via `apps/tooling/tools/hash_validator.py` + on-device pHash cross-check |
| AC9 | Round-boundary detection floor | Measured Session 2 by capturing `gameDetector` / `blackScreenDetector` events from the auto-slice run |
| AC10 | Ladder rung verdict (scope-limited to rung-0 / rung-3) | Picked from AC1/AC4/AC8/AC9; rung-1 / rung-2 carved out as conditional-revision clauses |
| AC11 | Forbidden cloud-fallback rung asserted | Verbatim assertion in spike report |
| AC12 | Spike report published with `## Deferred measurements` section | Authored Session 2 |

**What this spike defers (ACs/Tasks transferred to Epic 5/6 stories):**

| AC | Subject | Inheriting story |
|---|---|---|
| AC5 | PERF-003 view-mode toggle ≤ 100 ms; no `expo-av` player swap | **Story 5.5** (`5-5-view-mode-toggle-full-minimap-minimap-hud-no-player-swap`) — view-mode toggle is the AC subject |
| AC6 | PERF-004 Cinema Mode cold-start ≤ 1.5 s | **Story 5.4** (`5-4-cinema-mode-immersive-review-with-reveal-on-tap-controls`) — Cinema Mode immersive review is the AC subject |
| AC7 | PERF-005 clip export ≤ 60 s for 30 s Mobile-tier clip | **Story 6.6** (`6-6-mobile-hd-encode-tier-selection`) — Mobile-tier export is the closest AC subject |

**Rung verdict scope-limit consequence:** rung-1 (lower frame-sampling) and rung-2 (drop Minimap+HUD on weak hardware) cannot be picked by this spike — their triggers depend on the deferred PERFs (rung-1 on PERF-002 OR PERF-005; rung-2 on PERF-003 OR PERF-004). If Epic 5/6 stories surface PERF-003/004/005 misses post-G1, the rung verdict revises to rung-1 or rung-2 at that point via a follow-up commit on `_bmad-output/architecture-spike-perf-floor.md`'s `## Ladder rung verdict` section.

**G1 partial-close consequence:** Sprint Plan §2 G1 closes for the work this spike covers (binding viability + auto-slice + map-ID + round-boundary). Stories 5.4 / 5.5 / 6.6 carry an additional inherited "PERF measurement is part of your AC" obligation. The Sprint Plan §2 should be amended (post-merge per AC13 extended scope) to reflect the partial close.

### Reference device re-anchor (2026-05-09)

The architecture (`_bmad-output/architecture.md:839`) and several other planning artifacts (`_bmad-output/prd.md:669`, `_bmad-output/epics-and-stories.md:749`, `_bmad-output/ux-design.md` multiple) bind the reference device as **Poco X5** (Snapdragon 695, 6 GB RAM, Android 13). The dev agent on 2026-05-09 ran `adb devices` and discovered the connected device is a Poco **X5 Pro 5G** (SM7325 / Snapdragon 778G / Android 14 / 8 GB), not a Poco X5. Stephane (sole developer / hardware owner) confirmed he does not have the X5 (SD695 / `stone` codename) on hand and chose to re-anchor PERF-010 to the actual hardware rather than wait to source an X5.

**Implication of the re-anchor:**

- The 778G is materially faster than the 695 (~30–60% per benchmark suites; 4 nm vs 6 nm process; Adreno 642L vs Adreno 619 — meaningful GPU gap).
- PERF-010 binds at the Poco X5 Pro 5G's measured number. **V1's effective supported-device set narrows** — devices on 695-class chipsets (the cheaper Poco X5 line, Redmi Note 12 5G, etc.) are now V1-out-of-scope OR accept-as-degraded with no measured floor.
- The spike report (`_bmad-output/architecture-spike-perf-floor.md`) MUST include a `## Device re-anchor` section that documents this change verbatim, so reviewers (and future selves) cannot mistake the floor for the original SD695 anchor.
- Cross-cutting cascade through `architecture.md:839`, `prd.md:669`, `epics-and-stories.md:749` (and the Wave 6 first-launch verification at line 2787), `ux-design.md` (lines 37, 290, 399, 1671, 1687), and `sprint-status.yaml`'s `last_updated` comment is **AC13 post-merge admin** scope (extended). This branch (`ar-spike-perf-floor`) keeps the change scoped to the story file + spike report; the cascade lands in the AC13 follow-up commit per Story 0.2 lesson #2 ("do not bundle unrelated cleanups").

The X5 Pro 5G remains a **mid-tier** reference device by 2026 standards (released Feb 2023; ~$300 USD MSRP), just shifted up one rung from the X5. Devices weaker than the X5 Pro 5G are V1-out-of-scope; devices stronger may exceed the floor (acceptable). The "no flagship floor" principle from the original architecture intent is preserved.

### The 4 PERF NFRs — measurement specifics + cross-references

| NFR | Architecture line | PRD line | Pass criterion (Mobile-tier reference) | Notes |
|---|---|---|---|---|
| PERF-002 | 841, 1015 | 1015 | auto-slice ≤ 5% of source duration (1h20 → ≤ 4 min) | Measured wall-clock for `runProcessingPipeline` on 1h20 EVA After-h. Excludes app cold-start. |
| PERF-003 | 842, 1016 | 1016 | view-mode toggle ≤ 100 ms; no player swap | Crop/style change on the same `expo-av` source — verify same `<Video source={...}>` instance across toggles. |
| PERF-004 | 843, 1017 | 1017 | Cinema Mode cold-start ≤ 1.5 s | Card-tap → first frame visible (`onLoadedData`). Load-bearing for the < 5 min activation budget. |
| PERF-005 | 844, 1018 | 1018 | clip export ≤ 2× clip duration (Mobile-tier; 30 s clip → ≤ 60 s) | Mobile-tier encode only. HD-tier may exceed and uses progress indication per `mobile-EXPORT-002`. |
| PERF-010 | 845 (spike-bound), 1023 (TBD) | 1023 | Reference-device performance floor; **bound by this spike** | The PRD inherits the published number post-merge (AC13). |

### The accuracy floors — measurement specifics

| Floor | Architecture line | Pass criterion | Notes |
|---|---|---|---|
| Map ID accuracy | 847 | ≥ 95% overall on unseen test set; ≥ 90% per canonical map | Use `apps/tooling/tools/hash_validator.py` (AC8). Cross-check on-device pHash output against Python reference. |
| Round-boundary detection | 848 | Floor SET by spike — anchored to legacy "100% black-screen-transition detection with 0 false positives" target; on-device may degrade | Use the existing test fixtures + 1h20 reference. Recall AND precision both reported. |

### Current state of `apps/mobile/src/shared/services/opencv.ts`

Read 2026-05-09 at commit `1c12ff8`. The file is 386 lines. Critical observations:

- **Lines 1-12:** File comment establishes the boundary — every detection primitive is pure TS; only `loadFrameFromPath` requires a native binding.
- **Lines 14-19:** `FrameBuffer` interface — RGB-packed `Uint8ClampedArray`, length `width*height*3`. The JSI binding's output MUST conform.
- **Lines 79-110, 117-132, 139-159, 165-183, 191-222, 285-320, 352-370:** Pure-TS primitives that the binding does NOT need to provide — they consume `FrameBuffer` and produce hashes/scalars. **Do not replace these with native equivalents** in this spike unless a measurement specifically requires it (rung-1 sampling-rate tuning is a different surface — it changes how many frames flow through these primitives, not how the primitives compute).
- **Lines 381-385:** The throw-stub. This is the only line of code that NEEDS to change in opencv.ts for AC1.

The `processingPipeline.ts` imports `loadFrameFromPath` at `apps/mobile/src/features/video-processing/processingPipeline.ts:39` and uses it as the default `FrameLoader` (line 252). Tests inject a synthetic loader (`apps/mobile/src/features/video-processing/__tests__/`); the production loader has been the throwing stub. The spike replaces the stub WITHOUT changing the `FrameLoader` indirection — synthetic loaders continue to work in tests; the production loader now actually decodes.

### What to NOT do

- **Do NOT** silently bypass `EXPO_PUBLIC_AUTH_BYPASS=false` ([INVARIANT 8]). The spike's measurements must run through the real entitlement gate to be representative of V1 production runtime. Bypassing auth shaves a tiny constant — but introduces a non-production runtime that invalidates PERF-004 cold-start measurements.
- **Do NOT** measure PERF-002 with MMKV checkpoints already set from a prior run. Cold-launch + clear `processing.*` keys between each of the 3 runs. Otherwise you're measuring the resume path, not the cold auto-slice path.
- **Do NOT** re-run the spike against a different device "to get better numbers". The reference device, **post-re-anchor**, is **Poco X5 Pro 5G** (SM7325 / Snapdragon 778G / Android 14). Devices weaker than Poco X5 Pro 5G are V1-out-of-scope; devices stronger over-promise the floor. The original "Poco X5 (SD695)" anchor is superseded by the 2026-05-09 re-anchor (see "Reference device re-anchor" Dev Note).
- **Do NOT** swap the `expo-av` source on view-mode toggle as a workaround if PERF-003 misses. The "no player swap" constraint is a hard architectural requirement (architecture line 842 + 1492). A miss here triggers rung-2 (drop Minimap+HUD on weak hardware), not a hack.
- **Do NOT** ship the binding code without the spike report. AC12 binds `_bmad-output/architecture-spike-perf-floor.md` as a deliverable. A spike that produces measurements but no report is incomplete.
- **Do NOT** merge the spike PR before Story 0.2 reaches `done`. Gate G0 blocks Sprint 3 merges per Decision #ES-3. Develop on the branch; wait for G0.
- **Do NOT** treat rung-3 as a story failure. Rung-3 is a permitted outcome. The honest verdict is the deliverable, not "all measurements passed".
- **Do NOT** add cloud-CV fallback code "in case". AC11 forbids it. Even an opt-in flag is a violation — the rung is forbidden, not optional.
- **Do NOT** modify `apps/mobile/src/shared/services/opencv.ts` lines 1-379 (the pure-TS primitives) to "improve performance" as part of this spike. If a primitive needs native acceleration for PERF-002 to pass, that's a separate Sprint-3 story, not a spike concession. Document the need in the report; do not bundle the optimization.
- **Do NOT** commit the 1h20 EVA After-h reference video. It is "architecture-team-supplied; not committed to repo" per architecture line 839. The spike report records its provenance (name, duration, resolution, encoder), not its contents.
- **Do NOT** retitle the PR after creation. AC15 binds the title verbatim — paste from Dev Notes "PR title and body to file" at PR-open time.

### Disposition annotation: this story does not annotate any legacy file

Story 1.1 is **not a docs-only story** like 0.1/0.2 — it ships code. Therefore: no `## Final Disposition` annotation pattern; no legacy-file append-only discipline; no audit-rule frame. The spike's deliverable is the new `architecture-spike-perf-floor.md` artifact, not annotations on existing files.

### Project Structure Notes

- **Output locations** for this story:
  - `apps/mobile/src/shared/services/opencv.ts` — UPDATE: replace `loadFrameFromPath` stub (line 381) with real JSI implementation; preserve all pure-TS primitives unchanged.
  - `apps/mobile/package.json` — UPDATE: add `react-native-fast-opencv` dep at the version chosen.
  - `pnpm-lock.yaml` — UPDATE (transitively).
  - `apps/mobile/android/` — REGENERATED by `expo prebuild`. Whether to commit the regenerated dir depends on the project convention; the legacy mobile repo committed prebuild artifacts but the unified monorepo's convention should be inferred from the existing `apps/mobile/` structure (currently no `android/` dir present at commit `1c12ff8`, suggesting the convention is "regenerate per-build, do not commit"; verify with Stephane if uncertain).
  - `_bmad-output/architecture-spike-perf-floor.md` — NEW: the spike deliverable per AC12, including the AC16 G1 sign-off.
  - `_bmad-output/implementation-artifacts/1-1-pre-prd-performance-spike-ar-spike.md` — UPDATE: this file (Tasks/Subtasks checkboxes marked, Dev Agent Record / File List / Change Log populated, Status flipped to `review` then `done` post-merge).
  - `_bmad-output/sprint-status.yaml` — UPDATE: `1-1-...` status flips per AC14.
  - **Post-merge follow-up commit:** `_bmad-output/prd.md` PERF-010 update + conditional FR clauses per AC13.
- **Story file location**: `_bmad-output/implementation-artifacts/1-1-pre-prd-performance-spike-ar-spike.md` per `sprint-status.yaml` `story_location` line 6.
- **Branch name**: `ar-spike-perf-floor` (parallels Story 0.2's `sprint-2-5-disposition-execution` thematic-name pattern; not the literal story_key).
- **No conflicts** with unified project structure — the spike adds one dep, replaces one stub, generates one new `_bmad-output/` artifact. It does not introduce new source-tree paths beyond what's specified.

### Testing standards summary

**Spike-style verification, not feature-style tests.** The spike's "tests" are:

1. **The measurements themselves** (AC4–AC9). Captured raw + median + variance in the spike report.
2. **Cross-check correctness** of the on-device pHash against the Python reference (Task 8 sub-bullet). Discrepancy = binding bug, not measurement gap.
3. **Existing jest tests** at `apps/mobile/src/features/video-processing/__tests__/` continue to pass — they inject synthetic `FrameLoader`s, so the binding change does not affect them. Verify with `pnpm --filter mobile test` on the spike branch.
4. **Manual smoke test**: cold-launch the dev build on Poco X5 Pro 5G; auto-slice the 1h20 reference; open Cinema Mode; toggle view-mode; export a 30-s clip. End-to-end pass-through with no crashes is the gating manual check before declaring measurements final.

The dev agent should NOT add new automated tests for the JSI binding itself in this spike — the binding's correctness is validated via measurement against the Python reference, not via TS unit tests (which would have to either mock the binding or hard-depend on the device's native module — both fragile).

If the dev agent wishes to add a Hermes-only smoke test of `loadFrameFromPath` against a tiny test JPEG (sanity check), gate it with a `__DEV__ &&` flag and place it in a separate `apps/mobile/src/shared/services/__tests__/opencv.bench.ts` (excluded from default `jest` runs). This is an OPTIONAL nicety, not an AC.

### References

- [Source: _bmad-output/epics-and-stories.md#Story 1.1 (lines 740-766)] — original story acceptance criteria, dependencies, sprint-fit.
- [Source: _bmad-output/epics-and-stories.md#Decision #ES-2 — Pre-PRD Performance Spike Sequencing (line 2849)] — RESOLVED; AR-SPIKE is the load-bearing first work item.
- [Source: _bmad-output/sprint-plan.md#Wave 1 — AR-SPIKE FIRST WORK (G1) (lines 72-78)] — Wave 1 ordering: 1.1 first; exit criteria = "Rung verdict written into 1.1 acceptance. Downstream mobile scope (Epic 5/6) frozen against the verdict."
- [Source: _bmad-output/sprint-plan.md#Gate G1 — AR-SPIKE rung outcome (lines 31-39)] — the merge gate this story closes.
- [Source: _bmad-output/sprint-plan.md#Critical path Chain 2 (lines 262-270)] — Chain 2 starts with `1.1 → 5.4 → 5.5 → 6.1 → 6.3 → 7.1 → 6.6 → 6.7 → 6.8 → 7.2 → 7.3 → 10.1`. Slip on 1.1 moves the whole sprint end-date.
- [Source: _bmad-output/architecture.md (lines 832-868)] — `#### Pre-PRD performance spike [SPIKE BOUND]` — spike scope, ladder rungs, deliverable artifact, cascading implications.
- [Source: _bmad-output/architecture.md (lines 80-87)] — front-matter `loadBearingFirstTask` with `fallbackLadder` enumeration and `forbiddenFallback: fall_back_to_cloud_breaks_innovation_1`.
- [Source: _bmad-output/architecture.md (line 102)] — `mobile-AUTO-SLICE-001/002` depend on JSI binding shipping as real binding; current state is "tested-via-injection stub".
- [Source: _bmad-output/architecture.md (lines 113-117)] — PERF-010 + the 4 underlying PERF NFRs.
- [Source: _bmad-output/architecture.md (line 220)] — "OpenCV JSI binding stub. `loadFrameFromPath` throws; tests inject synthetic `FrameLoader`s."
- [Source: _bmad-output/architecture.md (line 1639)] — `architecture-spike-perf-floor.md` is `[NEW]` in the file-tree section.
- [Source: _bmad-output/prd.md#PERF-010 (line 1023)] — TBD per architecture pre-PRD spike; PRD inherits the published number.
- [Source: _bmad-output/prd.md#PERF-002,003,004,005 (lines 1015-1018)] — the 4 PERF NFRs with their pass criteria.
- [Source: _bmad-output/prd.md#mobile-AUTO-SLICE-001/002 (lines 867-868)] — load-bearing on JSI binding shipping as real binding.
- [Source: _bmad-output/prd.md#Innovation #1 (line 199)] — OpenCV JSI binding shipping as real binding (not stub) is the moat; cloud fallback breaks it.
- [Source: apps/mobile/src/shared/services/opencv.ts:381-385] — the throw-stub to replace.
- [Source: apps/mobile/src/features/video-processing/processingPipeline.ts:38-44, 252] — `loadFrameFromPath` import + default `FrameLoader` wiring.
- [Source: apps/mobile/package.json] — verify `react-native-fast-opencv` is NOT listed at commit `1c12ff8`; the spike installs it.
- [Source: apps/tooling/tools/hash_validator.py] — authoritative regression tool for map ID accuracy (per architecture line 558).
- [Source: apps/tooling/tools/frame_labeler.py:19-34] — the 14 canonical maps (`MAP_LABELS`).
- [Source: _bmad-output/legacy/mobile/stories/7.5.md, Review Follow-ups line 63] — pre-existing follow-up explicitly assigning `react-native-fast-opencv` JSI wiring to the AR-spike: _"Wire `react-native-fast-opencv` into `loadFrameFromPath` so the pipeline can run on device; until then ACs 1, 5, 6, 7, 8 are validated only via injected synthetic loaders in unit tests."_ This story closes that loose end.

### Previous-Story Intelligence

**Previous story:** Story 0.2 (`_bmad-output/implementation-artifacts/0-2-execute-sprint-2-5-per-story-dispositions.md`) — `Status: review` at the time this story file was created. Story 0.2 closes Gate G0 and unblocks Sprint 3 merges.

Story 0.2's Dev Agent Record is the canonical reference for current monorepo conventions; its lessons apply to this story too:

1. **Branch + commit + PR-title hygiene.** Story 0.2's AC6 binds the PR title verbatim (`docs: Sprint 2.5 disposition execution (Story 0.2)`); the commit subject was permitted to diverge by one verb (`docs: add Sprint 2.5 ...`) per `@commitlint/config-conventional` `subject-case` rule. For Story 1.1, AC15 binds the PR title; commit subjects can be `feat:`-prefixed (verb-first) since this is a code-shipping story. _Verify against `commitlint.config.ts` — confirmed at line 1: `extends: ['@commitlint/config-conventional']`._
2. **Append-only discipline matters when annotating existing files.** Story 1.1 ships fresh code (`opencv.ts:381-385` replaced) + a new artifact (`architecture-spike-perf-floor.md`). It does NOT annotate legacy stories. So append-only does not apply here — but the narrower discipline of "do not bundle unrelated cleanups" still does. This branch should contain only Story 1.1's deliverable. **Rebase on latest `main` BEFORE branching** (e.g., after Story 0.2's PR merges) so the branch contains only Story 1.1's commits.
3. **Citation discipline matters.** Verify every cited commit hash with `git rev-parse <hash>` before committing. Cited hashes in this story file: `1c12ff8` (current HEAD; "story 0.2 patches commit"), `7f8d636` (Story 0.1 commit), `837d3bc` (Story 0.1 admin commit), `4d0520f` (Story 0.2 deliverable commit), `7e60d76` (Story 0.2 admin commit), `76fec7c` (Story 0.1 PR #2 merge), `006a4fe` (Story 0.1 patch commit). All verified live before this story file was finalized via `git rev-parse` on 2026-05-09.
4. **Manual review = the verification step.** Story 0.2 had no automated tests; the spike has measurements (AC4–AC9) + a sanity smoke test. Manual review by Stephane gates: (a) measurements are honestly recorded; (b) rung verdict is correctly derived from measurements; (c) cloud-fallback assertion is present.
5. **Status divergence is real.** Plan-side claims (architecture text, epics file) can drift from code-side reality. AC2 explicitly tells the dev agent to **verify** `react-native-fast-opencv` is or is not installed rather than trust the architecture's "already a dep" claim. Same discipline applies to all AC2-class verifications.
6. **`bmad-create-story` flips `epic-1: backlog → in-progress` automatically.** This is the first story in epic-1; the create-story workflow handles the epic transition. Verify on file-read: the dev agent should see `epic-1: in-progress` already in `sprint-status.yaml`.
7. **Sprint-status flip happens in a single commit at end-of-work** (not a 4-flip chain). Story 0.2's code-review revealed that intermediate `ready-for-dev → in-progress → review` working-tree states are not preserved in git history — the realized commit shows `backlog → review` directly. For Story 1.1, expect the same: `ready-for-dev → review` in a single commit on the deliverable PR; `review → done` in the post-merge admin commit.

### Git intelligence

Recent monorepo commits (Sprint 3 Epic 0 → Epic 1 transition):

```
1c12ff8 docs: apply Story 0.2 code-review patches across planning artifacts (Story 0.2 review patches; CURRENT HEAD pre-1.1-branch)
7e60d76 docs: record commit hash + PR-create URL in Story 0.2 (Story 0.2 admin)
4d0520f docs: add Sprint 2.5 disposition execution (Story 0.2)
76fec7c Merge pull request #2 from stwiertz/sprint-2-5-conflict-audit (PR #2 — Story 0.1 patch round)
006a4fe docs: apply Story 0.1 code-review patches across planning artifacts (Story 0.1 patches)
```

**Pattern:** Sprint 3 Epic 0 was a documentation-only chain (`docs:`-prefixed commits). Story 1.1 BREAKS this pattern: it ships actual code (the JSI binding). The first non-`docs:` commit on `main` post-Epic-0 is expected to be Story 1.1's `feat: wire react-native-fast-opencv ...` commit. This is intentional — Sprint 3's first code-shipping story is the AR-SPIKE.

**File-touching pattern from prior stories:**
- Story 0.1: 7 files in PR #1 (3 declared + 4 bundled); 11 files in PR #2 (post-review patches).
- Story 0.2: 13 files (10 legacy + audit + story file + sprint-status).
- **Story 1.1 file-count expectation: 5–7 files declared.** `opencv.ts` (1 line replaced) + `package.json` (1 dep added) + `pnpm-lock.yaml` (transitive) + `_bmad-output/architecture-spike-perf-floor.md` (NEW) + this story file + `sprint-status.yaml`. Optionally `apps/mobile/android/` if the project commits prebuild artifacts (verify convention). Do not bundle unrelated `main`-branch commits — rebase before branching.

**Workflow on Windows:** Stephane's host has no `gh` CLI. PR creation is via the GitHub web UI URL returned by `git push -u origin ar-spike-perf-floor`. The dev agent should NOT attempt `gh pr create`. The Story 0.2 + 0.1 pattern is `git push → record URL in admin commit → manual PR-open`.

### Latest tech / library notes

**`react-native-fast-opencv` version pin:** Verify the highest stable version compatible with `react-native@0.81.5` + `expo@~54.0.33` + Hermes at install time. The lib's GitHub README + npm registry are authoritative; do NOT trust a stale version pin from any document. Document the chosen version + rationale in the spike report's `## Device profile` section (or an adjacent `## Library versions` subsection).

**Expo SDK 54 / RN 0.81.5 constraints:**
- New Architecture status: verify whether `react-native-fast-opencv` requires Fabric/TurboModules + the project's current setting in `apps/mobile/app.json` (or `app.config.ts` if present).
- Hermes engine compatibility: the lib must support Hermes (not JSC). RN 0.81 defaults to Hermes; verify the lib's docs.
- `expo prebuild` autolinking: confirm the lib autolinks via Expo's autolinking config; if it requires manual native edits, that's a longer-tail integration that may push the spike toward rung-3 (binding cannot ship in V1 timeline).

**OpenCV Mat lifecycle on JSI:** Native heap leaks across thousands of keyframes will OOM-kill the app mid-pipeline on a 1h20 video. The binding implementation MUST release Mat objects immediately after use (`mat.release()` per Mat allocation). Verify with `adb logcat | grep -i 'native.*alloc'` during a long-run; PSS RSS should not grow unboundedly during auto-slice. This is exactly the kind of constraint that drives a rung-1 sampling-rate decrease if uncaught.

**JPEG decode performance vs sampling rate:** The 1h20 source generates ~600+ keyframes (assuming 1 keyframe per 8s GOP → 600 keyframes for 4800 s). Per-keyframe decode time × 600 = the JPEG-decode contribution to PERF-002. Rough budget: 4 min total ÷ 600 keyframes = 400 ms/keyframe, of which decode is one fraction (the rest is detector + I/O). If decode alone exceeds 400 ms, rung-1 (lower sampling rate, e.g., 1 keyframe per 16 s) is the first lever.

### Project-context reference

There is no `project-context.md` in this repo — the `bmad-create-story` workflow's `persistent_facts` glob (`file:{project-root}/**/project-context.md`) returns no matches at commit `1c12ff8` (same finding as Stories 0.1 + 0.2). The persistent context is:

- The 3 legacy repos (Warden / Warden-tooling / WardenWeb) merged under `apps/{mobile,web,tooling}` with full git history.
- `_bmad-output/` holds the unified planning artifacts (PRD, architecture, UX, epics, sprint plan + status, this story).
- `_bmad-output/legacy/` holds pre-merge artifacts copied verbatim.
- The mobile codebase has 14 canonical maps (`apps/tooling/tools/frame_labeler.py:19-34` `MAP_LABELS`).
- Reader-App contract is structural — mobile is paid-only with zero monetization surface in-app; do NOT introduce any pricing strings or IAP/purchase imports.
- `EXPO_PUBLIC_AUTH_BYPASS=true` is dev-only — must remain `false` (or unset) in any release-shaped build, including spike measurement runs.
- `react-native-mmkv` pinned at v3 — do NOT let a transitive dep bump push to v4.
- `.npmrc` `node-linker=hoisted` is required — do NOT change.

### PR title and body to file

**Title (paste verbatim — this is the AC15-binding string):**

```
feat: AR-SPIKE — pre-PRD performance floor (Story 1.1)
```

**Body (paste verbatim — Markdown):**

```markdown
## Summary

Closes Story 1.1 (Sprint 3 Epic 1, Wave 1). The pre-PRD performance spike (AR-SPIKE) — the load-bearing first work item per Sprint Plan §2 Gate G1 and architecture line 832.

**Outcome:** **provisional rung verdict = `rung-0 plausible — binding viable; final rung TBD post-Story-1.1.1 measurement`** per the binding-only cut decision (see story Dev Note "Binding-only cut (2026-05-09)"). Six substrate gaps blocked end-to-end measurement in this branch (gaps documented at `_bmad-output/architecture-spike-perf-floor.md:134` `## Substrate gap audit (six gaps)`); measurement ACs (AC4, AC5/6/7, AC8, AC9) deferred to a follow-up Story 1.1.1 once Stories 1-13 / 1-14 / 1-16 + new-HUD work + pHash/ahash reconciliation land. **Cloud-fallback rung remains FORBIDDEN per AC11 regardless of any future measurement outcome.**

This PR **clears Sprint Plan §2 Gate G1 partially** — closes for binding viability + Sprint-3 stories without explicit `Story 1.1 spike` dependency. Sprint 3 stories carrying that dep (5.1, 5.3, 5.4, 5.5, 6.6) wait for Story 1.1.1's measurement before unblocking. PRD update with PERF-010 binding + conditional FR clauses transfers to Story 1.1.1 per AC13's binding-only-cut carve-out.

**G0 gate already cleared** (Story 0.2 closed 2026-05-09 at merge commit `e6ad6e0`); this PR is unblocked for merge.

## Files

- `apps/mobile/src/shared/services/opencv.ts` — UPDATE: replace `loadFrameFromPath` stub with real `react-native-fast-opencv` JSI binding (line 381 area; pure-TS primitives unchanged); plus code-review patches (Mat-handle leak fix in narrow window between allocations + base64ToMat null/0×0 throws + split bare-catch require failures)
- `apps/mobile/package.json` — UPDATE: add `react-native-fast-opencv@0.4.8` dep (exact pin)
- `pnpm-lock.yaml` — UPDATE (transitive)
- `apps/mobile/src/features/video-processing/processingPipeline.ts` — UPDATE: `__DEV__`-gated PERF-002 + per-stage timing scaffolding for Story 1.1.1 measurement run; PERF-009 event-count log; catch-path MMKV persistence so failed-run timing trails are diagnostic
- `apps/mobile/src/shared/services/__tests__/opencv.test.ts` — UPDATE: replaced jest test for the throw-stub with a documented placeholder (real binding requires JSI native-module mocking — out of scope for unit tests; covered by on-device dev-build smoke verification per AC1)
- `_bmad-output/architecture-spike-perf-floor.md` — NEW: spike deliverable per AC12 (11 H2 sections in spec-mandated order) + AC16-partial G1 sign-off
- `_bmad-output/implementation-artifacts/1-1-pre-prd-performance-spike-ar-spike.md` — story spec with Tasks/Subtasks marked, Dev Agent Record, File List, Change Log, Review Findings (8 patches + 4 defers); Status flipped to `done`
- `_bmad-output/implementation-artifacts/deferred-work.md` — UPDATE: 4 deferred items from Story 1.1's code review (MMKV-cleanup pass + stage-label stability + PERF-009 resume gap + base64 round-trip cost)
- `_bmad-output/sprint-status.yaml` — `1-1-...` flipped `ready-for-dev` → `review` (with `done` flip in a small post-merge follow-up PR per the two-PR pattern); `last_updated` bumped
- `.gitignore` — UPDATE: exclude `apps/mobile/android/` and `apps/mobile/ios/` (prebuild-on-demand; per AC2)

## Forbidden rungs

This spike does NOT include a cloud-fallback CV path. Cloud fallback is FORBIDDEN regardless of measured numbers per architecture line 858 — breaks Innovation #1 (privacy + lower marginal cost). The spike report's `## Forbidden rungs` section asserts this verbatim.

## Manual smoke verification (reviewer guidance)

- `pnpm install && pnpm --filter mobile exec expo prebuild` succeeds
- `pnpm --filter mobile exec expo export --platform android` produces a Hermes bundle without warnings
- `pnpm --filter mobile test` passes (existing detector tests use injected synthetic `FrameLoader`s; not affected by the binding change)
- Manual on-device smoke: cold-launch dev build on Poco X5 Pro 5G (re-anchored reference device per Dev Note); auto-slice 1h20 EVA After-h reference; open Cinema Mode; toggle view-mode; export a 30-s clip — end-to-end pass-through with no crashes

## References

- Story spec: `_bmad-output/implementation-artifacts/1-1-pre-prd-performance-spike-ar-spike.md`
- Spike deliverable: `_bmad-output/architecture-spike-perf-floor.md`
- Sprint Plan §2 Gate G1: `_bmad-output/sprint-plan.md` (lines 31-39)
- Architecture spike scope: `_bmad-output/architecture.md` (lines 832-868, `#### Pre-PRD performance spike [SPIKE BOUND]`)
- Decision #ES-2 (resolved): `_bmad-output/epics-and-stories.md` (Decision #ES-2 — Pre-PRD Performance Spike Sequencing)
- PRD PERF-010 (TBD pre-spike): `_bmad-output/prd.md` (line 1023)
```

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (Claude Opus 4.7, 1M context) via the BMad `dev-story` skill on 2026-05-09. **Two execution sessions:**

- **Session 1 (2026-05-09 morning):** Code-side execution (Tasks 1, 2, partial 12) — committed as `81838be feat: wire react-native-fast-opencv JSI binding for loadFrameFromPath` + `5c3fb6b docs: track Story 1.1 Tasks 1-2 progress on AR-SPIKE branch`. Halted at end of Task 2 pending physical hardware.
- **Session 2 (2026-05-09 resume):** Stephane brought the Poco X5 Pro 5G into the loop. `adb devices` discovered the device is **X5 Pro 5G (SM7325)**, not the architecture-spec'd X5 (SD695). Re-anchored the reference device per Stephane (see "Reference device re-anchor" Dev Note); patched story file's AC3 + Dev Notes + Task 3 first sub-bullet + Preconditions table + What-to-NOT-do device line accordingly. Continuing Task 3 sub-bullets 2 + 3 → Tasks 4-11 with live measurements.

### Debug Log References

- `pnpm --filter mobile add react-native-fast-opencv@0.4.8` → installed; resolved 1672 packages (added 71). One unrelated peer warning: `react-dom@19.2.4` wants `react@^19.2.4` (we have 19.1.0). 11 deprecated subdependencies found (none introduced by fast-opencv; pre-existing transitives).
- `pnpm --filter mobile typecheck` → 1 pre-existing error in `src/features/auth/firebaseConfig.ts:5` (`getReactNativePersistence` not exported from `firebase/auth` — Firebase v12 migration is the subject of Stories 1.4-1.9). No new type errors introduced by `opencv.ts` changes.
- `pnpm --filter mobile test` → 13 suites pass / 105 tests pass (including the unchanged-by-design 9 pure-TS detector tests in `__tests__/opencv.test.ts`; the obsolete stub-throw test was deleted, so the file's test count is now 9 instead of 10).
- `pnpm --filter mobile exec expo prebuild --platform android --no-install --clean` → succeeded; `apps/mobile/android/` regenerated. Single warning: `userInterfaceStyle: Install expo-system-ui in your project to enable this feature` (pre-existing config artefact, unrelated to this story).
- `pnpm --filter mobile exec expo export --platform android --output-dir dist-spike` → produced 1 Hermes bundle (`_expo/static/js/android/index-9491fc77a198e675a775b8da260972f8.hbc`, 5.27 MB) + `metadata.json` (3.54 kB). No warnings or errors mentioning `react-native-fast-opencv`. Output dir deleted after verification.

### Completion Notes List

✅ **Tasks 1 + 2 complete (code-side wiring of the JSI binding).** Story 1.1's binding obligation is fulfilled at the source-tree level. The throw-stub at `apps/mobile/src/shared/services/opencv.ts:381` is replaced with a real `react-native-fast-opencv@0.4.8` JSI binding that decodes JPEG/PNG keyframes via `base64ToMat` → `cvtColor(BGR→RGB)` → `matToBuffer('uint8')` → `Uint8ClampedArray`, with native-Mat lifetime managed by `clearBuffers([])` in a `finally` block (PSS-leak mitigation flagged in Dev Notes). The native imports are lazy-required inside the function (matching `ffmpeg.ts:43-82`'s `getFFmpeg()` pattern) so the file remains importable in jest, where the JSI binding cannot install.

✅ **Regression coverage clean.** Full mobile jest suite passes (105/105). The pure-TS detector primitives (lines 14-371 of `opencv.ts`) are untouched. The single test that asserted the stub throws was removed and replaced with a comment documenting the intentional jest-coverage gap (per Dev Notes "Testing standards summary").

✅ **Build smoke clean.** `expo prebuild` regenerates `apps/mobile/android/` without errors; `expo export --platform android` produces a 5.27 MB Hermes bundle without warnings about the new native module. The `apps/mobile/android/` and `apps/mobile/ios/` paths are added to root `.gitignore` so the regenerated dirs are not committed (consistent with the unified monorepo's prebuild-on-demand convention).

**[2026-05-09 SESSION 2 UPDATE]** The HALT-point handoff below is superseded — Stephane resumed Session 2 with the device, and after surfacing 6 substrate gaps the spike was cut to binding-only. See Dev Notes "Binding-only cut (2026-05-09)" + "Substrate gap audit (2026-05-09)" for the full picture. The HALT-point text below is preserved for Session 1 historical context.

---

⏸️ **HALT [Session 1] — paused for Stephane's device-bound measurements.** The remaining ACs (3-11) and Tasks (3-11, post-merge 13) require physical hardware that the dev agent cannot drive:
- **Poco X5 Pro 5G dev device** (re-anchored from architecture's original Poco X5 — see Dev Note) + adb access for cold-launch timing.
- **1h20 EVA After-h reference video** staged on device (architecture-team-supplied; not committed).
- **Unseen map-ID test set** of ≥ 420 labeled frames (≥ 30 per canonical map × 14 maps) for AC8 accuracy validation against `apps/tooling/tools/hash_validator.py`.

The honest, on-device validation step from AC1 ("boot a dev build on Poco X5 Pro 5G; trigger the processing pipeline against a single keyframe; confirm a non-throwing return + correct width/height/length-of-`data`") has NOT yet been performed at the end of Session 1 — that is the next physical step in Session 2, and the spike's binding-correctness check that drives the rung-1/rung-2/rung-3 verdict.

⏸️ **Branch state at HALT-point.** On `ar-spike-perf-floor` cut from `main@76fec7c`. Working tree dirty with the Tasks 1-2 deliverable (see File List below). The work is **not yet committed** — Stephane's options at handoff:
1. **Commit Tasks 1-2 as a self-contained `feat:` commit now**, then run measurements on the committed binding and add the spike report + verdict in a follow-up commit. This gives a clean snapshot that survives context loss and supports rebase-against-post-Story-0.2-main.
2. **Defer the commit until measurements are done**, then bundle binding + report + verdict into a single commit. Higher risk of losing intermediate state.
3. **Discard and restart** if any of the binding implementation choices need revision after Stephane's first manual smoke on-device.

**Forbidden rung remains forbidden.** No cloud-fallback code was added "in case". AC11 will be asserted verbatim in `_bmad-output/architecture-spike-perf-floor.md` once that file is authored (post-measurement). The dev agent has not introduced any opt-in flag, conditional branch, or deferred path that would enable cloud CV — even as a degraded fallback. Cloud CV is excluded by construction in this code path.

---

### Session 2 closure (2026-05-09) — binding-only-cut summary

✅ **AC1 closed (binding viable).** Dev-build APK installed + launched cleanly on Poco X5 Pro 5G. APK SHA-256 `5fdad9771468f7b49ae434a7aea50904314a8c861c9b37b951cab594d1053ae3`. Native module loaded; React Native bridge initialized; MainActivity reached focus PID 23079. The end-to-end keyframe-decode pass-through is gap-#6-blocked but the binding's compile-time + load-time viability are proven.

✅ **AC3 closed (device profile captured).** Real Poco X5 Pro 5G profile recorded for the spike report (model `22101320G`, codename `redwood_eea`, SoC `SM7325` Snapdragon 778G 4nm, 8 GB SKU, 1080×2400 @ 440 dpi, Android 14 SDK 34, HyperOS V816 build `OS2.0.14.0.UMSEUXM`, security patch 2025-11-01). Hermes version: bundled with React Native 0.81.5 (exact commit pinned in RN source tree; not surfaced in user-readable logcat tags during this session).

✅ **PERF-002 + AC9 instrumentation added** to `apps/mobile/src/features/video-processing/processingPipeline.ts:245+`. `__DEV__`-gated; persisted to MMKV at `processing.<sessionId>.perf002`. Available for Story 1.1.1 measurement.

✅ **All 6 substrate gaps audited + handoffs documented** (see Dev Note "Substrate gap audit (2026-05-09)"). Each gap maps to a Sprint 3 follow-up story.

✅ **Provisional rung verdict published.** `rung-0 plausible — binding viable; final rung TBD post-Story-1.1.1 measurement; cloud-fallback rung remains FORBIDDEN per AC11 regardless of any future measurement outcome.`

⏸️ **AC4/AC5/AC6/AC7/AC8/AC9/AC10-final/AC13 → Story 1.1.1.** New follow-up story to be created post-merge once Stories 1-13 / 1-14 / 1-15 / 1-16 + new-HUD work + pHash/ahash reconciliation land.

⏸️ **G1 partial close.** Sprint Plan §2 G1 closes for binding viability + Sprint-3 stories without `Story 1.1 spike` dep. Stories 5.1/5.3/5.4/5.5/6.6 (which do depend on the spike) **may plan against rung-0** but should be ready to revise scope if Story 1.1.1's measurement comes back hostile.

### File List

- `apps/mobile/src/shared/services/opencv.ts` — UPDATE: replace the throw-stub at line 381 with a real `react-native-fast-opencv` JSI binding for `loadFrameFromPath`. Native deps lazy-required to keep the module jest-importable. Pure-TS primitives (lines 14-371) untouched.
- `apps/mobile/src/shared/services/__tests__/opencv.test.ts` — UPDATE: remove the now-obsolete `describe("loadFrameFromPath", ...)` block (lines 237-243 in the old file) and the corresponding `loadFrameFromPath` import. Replaced with a comment documenting the intentional gap. The 9 pure-TS detector test blocks above are unchanged.
- `apps/mobile/package.json` — UPDATE: add `react-native-fast-opencv@0.4.8` to `dependencies`.
- `pnpm-lock.yaml` — UPDATE (transitive): 71 packages added; no version bumps to existing first-party deps; `react-native-mmkv` stays at `3.3.3` (INVARIANT 9 preserved).
- `.gitignore` — UPDATE: add `apps/mobile/android/` and `apps/mobile/ios/` so `expo prebuild` artefacts are not committed (matches the unified monorepo's existing prebuild-on-demand convention).
- `_bmad-output/sprint-status.yaml` — UPDATE: `1-1-pre-prd-performance-spike-ar-spike: ready-for-dev → in-progress`; `last_updated` bumped to describe the AR-SPIKE branch state. (`epic-1: in-progress` was already set by `bmad-create-story`.)
- `_bmad-output/implementation-artifacts/1-1-pre-prd-performance-spike-ar-spike.md` — NEW (created by `bmad-create-story`) / UPDATE (this commit): Tasks 1+2 checkboxes, AC2 checkbox, Task 12 dev-agent-controllable subtasks, Dev Agent Record, File List, Change Log; Status flipped `ready-for-dev → in-progress`.

**Session 2 additional files (binding-only-cut):**

- `apps/mobile/src/features/video-processing/processingPipeline.ts` — UPDATE: added `__DEV__`-gated PERF-002 wall-clock timer + per-stage `__perfMark()` calls + `[PERF-009]` event-count log. All hooks `__DEV__`-gated; production builds carry zero overhead. Persisted to MMKV at `processing.<sessionId>.perf002` for post-run inspection. Stays in the codebase as the measurement scaffolding for Story 1.1.1.
- `_bmad-output/implementation-artifacts/1-1-pre-prd-performance-spike-ar-spike.md` — UPDATE (Session 2): full re-anchor cascade in this file (AC3, Story line, rung-0 ladder, Dev Notes "Reference device profile", What-to-NOT-do device line, Preconditions table); spike scope split (ACs 5/6/7 + Tasks 5/6/7 + AC10 + AC12 layout + new "Spike scope split" Dev Note); binding-only cut (AC1 → `[x]`, AC4/AC8/AC9/AC10/AC12 patches, new "Binding-only cut" + "Substrate gap audit" Dev Notes, Session 2 closure block in Completion Notes); Change Log gained 4 Session 2 entries.
- `_bmad-output/architecture-spike-perf-floor.md` — **NEW (this commit)**: spike deliverable per AC12 (binding-only-cut layout) + AC16 G1 partial sign-off + AC11 forbidden-rung assertion. Authored from binding-only evidence; measurement-side sections explicitly carve out to Story 1.1.1.
- `_bmad-output/sprint-status.yaml` — UPDATE: `1-1-pre-prd-performance-spike-ar-spike: in-progress → review`; `last_updated` comment updated to summarize binding-only-cut + Story 1.1.1 follow-up.

**Pending files (Story 1.1.1 + post-merge admin per extended AC13):**

- `_bmad-output/sprint-status.yaml` — Story 1.1.1 entry to be added (probably under Epic 1: `1-1-1-ar-spike-measurement: backlog`) post-merge.
- `_bmad-output/architecture.md:839`, `_bmad-output/prd.md:669`, `_bmad-output/epics-and-stories.md:749` (+ Wave-6 line 2787), `_bmad-output/ux-design.md` (lines 37, 290, 399, 1671, 1687) — UPDATE: cross-cutting reference-device cascade (Poco X5 → Poco X5 Pro 5G) per gap #1's AC13-extended scope. Lands in a separate post-merge admin commit.
- `_bmad-output/architecture.md` lines 832-868 (`#### Pre-PRD performance spike [SPIKE BOUND]`) — UPDATE: amend to acknowledge the binding-only-cut + Story 1.1.1 follow-up. Lands in same post-merge admin commit.
- `_bmad-output/sprint-plan.md` §2 G1 — UPDATE: amend G1 closure criteria to reflect partial-close (binding viability) + full-close-pending (Story 1.1.1 measurement). Lands in same post-merge admin commit.
- `_bmad-output/prd.md` PERF-010 line — UPDATE (post-Story-1.1.1 measurement per original AC13): the measured PERF-010 number replaces "TBD per architecture pre-PRD spike (Risk #2 escalation)".

## Change Log

| Date       | Change                                                                                                | Author |
|------------|-------------------------------------------------------------------------------------------------------|--------|
| 2026-05-09 | Story file created via `bmad-create-story` workflow. Status: `ready-for-dev`. AC checklist drafted (16 ACs); Tasks/Subtasks drafted (13 tasks). Architecture-led spike scope captured per `_bmad-output/architecture.md` lines 832-868. Ladder rungs 0/1/2/3 enumerated; cloud-fallback rung asserted FORBIDDEN per AC11. Preconditions section flags external dependencies (Poco X5, 1h20 reference video, unseen test set, `hash_validator.py` runnable). AC checkbox tighten convention applied to ACs 13/14/15/16 (post-merge admin endpoints). `epic-1: backlog → in-progress` flipped (this is the first story in Epic 1). | Stephane (`bmad-create-story`) |
| 2026-05-09 | Branch `ar-spike-perf-floor` cut from `main@76fec7c`; Story 1.1 planning state relocated from Story 0.2's working tree (uncommitted) to the new branch. Status flipped `ready-for-dev → in-progress`. Tasks 1 + 2 fully executed code-side: `react-native-fast-opencv@0.4.8` installed; `loadFrameFromPath` stub at `opencv.ts:381` replaced with a real JSI binding (`base64ToMat` → `cvtColor BGR→RGB` → `matToBuffer`); native imports lazy-required (jest-safe) per `ffmpeg.ts`'s `getFFmpeg()` precedent; obsolete stub-throw test removed (`opencv.test.ts:237-243`). `expo prebuild --platform android --clean` and `expo export --platform android` both succeeded; 5.27 MB Hermes bundle produced without warnings about the new native module. Full mobile jest suite passes (105/105). `.gitignore` updated to exclude prebuild artefacts (`apps/mobile/android/`, `apps/mobile/ios/`). AC2 → `[x]`. **HALTED at end of Task 2** for Stephane-driven device measurements (Poco X5 + 1h20 EVA After-h reference + unseen ≥ 420-frame map-ID test set required for ACs 3-9). | Stephane (via `bmad-dev-story`, claude-opus-4-7 dev agent) |
| 2026-05-09 | **Session 2 resume:** Stephane brought the dev device into the loop. `adb devices` returned `dc72b871` / model `22101320G` / device `redwood` — discovered the connected device is a Poco **X5 Pro 5G** (SM7325 Snapdragon 778G, Android 14, 8 GB RAM), NOT the Poco X5 (SD695, A13, 6 GB) the architecture originally bound. **Re-anchored** the reference device per Stephane's call (he does not have an X5 on hand): patched story file's AC3, Dev Notes "Reference device profile" subsection (now "Poco X5 Pro 5G — re-anchored"), added new "Reference device re-anchor (2026-05-09)" Dev Note explaining rationale + cascade scope, updated Task 3 first sub-bullet (marked `[x]` with full profile capture), updated Preconditions table reference-device row, updated What-to-NOT-do device line, updated Story line, updated rung-0 ladder text to flag the narrowed V1 supported-device set. Cross-cutting cascade through `architecture.md:839`, `prd.md:669`, `epics-and-stories.md:749`, `ux-design.md` (multiple), `sprint-status.yaml` comment is **AC13 post-merge admin** scope (extended) — kept out of this branch per Story 0.2 Lesson #2 ("do not bundle unrelated cleanups"). Memory `project_warden_reference_device.md` saved for cross-conversation persistence. | Stephane (via `bmad-dev-story`, claude-opus-4-7 dev agent) |
| 2026-05-09 | **Session 2 — reference video staged:** `/sdcard/Download/2026-01-18 12-10-30.mp4` confirmed via `adb shell stat` + full pull + local `ffprobe`. SHA-256 `7f958d532863ddf3bec2482c967e151f97f6a50554d374e57e2f2badbf35f38b`. **Spec divergences flagged:** actual duration 01:49:39 (vs 1h20 spec, +37%) — AC4's pass criterion is ratio-based so budget scales to 5% × 6580 s = **329 s ≈ 5m29s** (vs the 4m AC4 example). Resolution 1280×720 (vs 1080p spec) — 720p source under-represents 1080p workload, so PERF-002 measurement is a lower bound; spike report `## PERF-002` flags this. Stephane confirmed the divergences are acceptable for the spike. Task 3 sub-bullet 2 → `[x]`. | Stephane (via `bmad-dev-story`, claude-opus-4-7 dev agent) |
| 2026-05-09 | **Session 2 — spike scope split:** code-side audit before instrumenting PERF-003/004/005 hooks revealed the surfaces those ACs target don't exist in the codebase: no `expo-av`/`expo-video` in `apps/mobile/package.json`, no `<Video>` component anywhere, `CinemaModeScreen.tsx` is a labeled visual stub (line 15-19 comment), no `CinemaMode` route in `RootNavigator.tsx`, no Card View screen (`HomeScreen.handleResume` is a no-op), no clip-creation surfaces. Building those surfaces inside this spike (Path B) would have added 2-5 days of harness work and polluted scope; deferring the whole spike (Path C) would have broken Sprint Plan §2 G1 dependency chain. **Stephane chose Path A — scope-split**: ACs 5/6/7 demoted to deferred-with-handoff (transferred to Stories 5.5 / 5.4 / 6.6 respectively), Tasks 5/6/7 marked DEFERRED, AC10 ladder rung verdict scope-limited to rung-0 / rung-3 with rung-1/rung-2 conditional-revision clause, AC12 spike-report layout updated to add `## Deferred measurements` H2 section. New Dev Note "Spike scope split — PERF-003/004/005 deferred to Epic 5/6 (2026-05-09)" added explaining the carve-out + Epic 5/6 inheritance + G1 partial-close consequence. Memory `project_warden_ar_spike_scope_split.md` saved for cross-conversation persistence. | Stephane (via `bmad-dev-story`, claude-opus-4-7 dev agent) |
| 2026-05-09 | **Session 2 — PERF-002 + AC9 instrumentation added to `processingPipeline.ts`:** `__DEV__`-gated wall-clock timer wraps `runProcessingPipeline` (start at function entry, end after `updateSessionStatus(sessionId, 'ready')`); per-stage `__perfMark()` after each `saveCheckpoint` (`keyframes_done_count=`, `detection_done_segments=…_events=`, `segmentation_done`, `results_done`); `[PERF-009]` event-count log after detection block emits START/END/SCORE_SCREEN counts + segment count + map-ID count + GOP info. All `__DEV__`-gated; persisted to MMKV at `processing.<sessionId>.perf002`. Full mobile jest suite still passes (105/105). The instrumentation is left in the codebase as the measurement scaffolding for Story 1.1.1 (no need to re-add). | Stephane (via `bmad-dev-story`, claude-opus-4-7 dev agent) |
| 2026-05-09 | **Session 2 — dev build installed on Poco X5 Pro 5G:** `expo run:android` BUILD SUCCESSFUL in 5m 25s; `app-debug.apk` (175 MB; SHA-256 `5fdad9771468f7b49ae434a7aea50904314a8c861c9b37b951cab594d1053ae3`) installed on `dc72b871`; `team.warden.mobile/.MainActivity` reached MainActivity focus PID 23079; Metro bundler connected. Stephane created `apps/mobile/.env` with his Firebase credentials + reloaded the JS bundle + signed in via Google. | Stephane (via `bmad-dev-story`, claude-opus-4-7 dev agent) |
| 2026-05-09 | **Session 2 — substrate gaps #5 + #6 surfaced; binding-only-cut decision:** First dev-build launch logged `[detectionConfig] initial fetch failed FirebaseError: Missing or insufficient permissions` + `[subscription] checkSubscription failed FirebaseError: Missing or insufficient permissions` + UI showed "initial set up requires internet". Code-side audit revealed: (a) `detection_config/latest` not seeded in Firestore (gap #6); (b) `apps/web/firestore.rules:8-10` catch-all denies all reads except `/users/{userId}` for owner; (c) the on-device `DetectionConfig` schema requires 6 ROIs + 10 thresholds; legacy `map_config.json` has only the `map_name` ROI + ahash fingerprints (gap #5: pHash/ahash divergence — every on-device map ID returns null regardless of seeding). Combined with the EVA HUD substrate shift (gap #4), three substrate issues compound on AC8 alone. **Stephane chose Path 1 — Ship binding-only spike now.** Story 1.1 closes AC1/AC2/AC3/AC11/AC12/AC15/AC16-partial; AC4/AC5/AC6/AC7/AC8/AC9/AC10-final/AC13 deferred to a new follow-up **Story 1.1.1 — AR-SPIKE measurement** that runs once Stories 1-13 / 1-14 / 1-15 / 1-16 + new-HUD work + pHash/ahash reconciliation land. **Provisional rung verdict: `rung-0 plausible — binding viable; final rung TBD post-Story-1.1.1 measurement; cloud-fallback rung remains FORBIDDEN per AC11`.** New Dev Note "Binding-only cut (2026-05-09) — Story 1.1.1 inherits measurement" + "Substrate gap audit (2026-05-09) — six gaps blocking measurement" added. Memory `project_warden_ar_spike_binding_only.md` saved. **Authoring spike report `_bmad-output/architecture-spike-perf-floor.md` next, then commit + push + open PR per AC15.** | Stephane (via `bmad-dev-story`, claude-opus-4-7 dev agent) |
| 2026-05-09 | **Session 2 — spike report published + sprint-status flipped review:** `_bmad-output/architecture-spike-perf-floor.md` authored with all 11 H2 sections per AC12 in spec-mandated order: `## Device profile` (line 14), `## Device re-anchor` (39), `## JSI binding viability` (52), `## Source video provenance` (107), `## Substrate gap audit (six gaps)` (134), `## Ladder rung verdict — provisional` (149), `## Forbidden rungs` (169), `## Deferred measurements (Story 1.1.1 inheritance)` (177), `## V1 implication summary` (197), `## Follow-up work required` (211), `## G1 sign-off — partial` (224). AC11 verbatim assertion landed at line 171. AC16-partial G1 sign-off landed at line 224 with the binding-only-cut amendment. Sprint-status `1-1-…: in-progress → review`; `epic-1` confirmed `in-progress`. Committed as `06a6908 docs: publish AR-SPIKE binding-only spike report + cut decision (Story 1.1)`. | Stephane (via `bmad-dev-story`, claude-opus-4-7 dev agent) |
| 2026-05-09 | **Code review run via `bmad-code-review` skill** — three-layer parallel adversarial review (Blind Hunter + Edge Case Hunter + Acceptance Auditor) on branch `ar-spike-perf-floor` (vs `main`). Triage: 8 patches (high-impact: Mat-handle leak in narrow window between `base64ToMat` + `createObject` allocations + finally-block error masking; silent zero-FrameBuffer on null `base64ToMat` / 0×0 `matToBuffer`; bare `catch {}` collapsing two require failures; AC10 wording normalized `final verdict TBD → final rung TBD`; AC11/AC12/AC16-partial checkboxes flipped `[x]`; PERF-009 log-line field-order normalized to spec; catch-path `__perfStages` MMKV persist for failed-run timing trails); 4 defers (pre-existing `clearCheckpoint` MMKV-cleanup tech debt; per-stage label-embedded counts; PERF-009 resume-skip; base64 round-trip + `Uint8ClampedArray` copy memory cost — all transferred to `_bmad-output/implementation-artifacts/deferred-work.md`); ~22 raised findings dismissed as noise/handled/intentional. New "Review Findings (2026-05-09)" subsection appended under Tasks/Subtasks recording the triage result. | Stephane (`bmad-code-review` skill, claude-opus-4-7) |
| 2026-05-09 | **AR-SPIKE branch rebased + AC3 closure + PR body refresh + code-review patches committed:** Per the AR-SPIKE binding-only memory's intended sequence, Story 0.2 docs branch landed first (PR #3 at merge commit `e6ad6e0`; PR #4 follow-up at `3faddd4`). With G0 lifted, `ar-spike-perf-floor` rebased cleanly against post-Story-0.2 `main` (4 commits replayed onto new base; no conflicts; force-pushed with lease). AC3 flipped `[ ]→[x]` with closure note pointing to spike report `## Device profile` line 14 — spec listed AC3 in the binding-only-cut closures (Dev Note line 253) but the checkbox itself wasn't flipped in the prior pass. PR-body template (Dev Notes "PR title and body to file") refreshed to reflect: provisional rung-0 outcome (vs the original `<rung-0|1|2|3>` placeholder); G1 partial-close caveat (Story 1.1.1 measurement-side close pending); G0-cleared note (the original "may not merge until G0" gate is satisfied at PR-create time); File List updated to enumerate every modified path including the code-review-patches files. AC15 PR title remains the verbatim mandate `feat: AR-SPIKE — pre-PRD performance floor (Story 1.1)`. Story file Status flipped `review → done`; sprint-status `1-1-…: review` stays until post-merge follow-up PR per the two-PR pattern memory. **Code-review patches committed as `e92f14b` and pushed; ready for Stephane's PR-create via web UI.** | Stephane (via `bmad-dev-story`, claude-opus-4-7 dev agent) |
| 2026-05-09 | **PR #5 merged + post-merge follow-up:** PR #5 (`feat: AR-SPIKE — pre-PRD performance floor (Story 1.1)`) merged at commit `a633c2e` on 2026-05-09 (range `3faddd4..e92f14b`, 10 files, +1113 / -26). Post-merge follow-up branch `ar-spike-postmerge` created off post-merge `main`; 2-file diff: sprint-status `1-1-…: review → done` + new entry `1-1-1-ar-spike-measurement: backlog` added under Epic 1 (binding-only-cut follow-up; inherits AC4-AC10-final/AC13 from 1.1; runs after Stories 1-13/1-14/1-15/1-16 + new-HUD work + pHash/ahash reconciliation land); story file ACs 14 + 15 flipped `[ ]→[x]` with post-merge provenance notes. **G1 partial close** — Sprint 3 stories WITHOUT explicit `Story 1.1 spike` dep are now unblocked for development; stories carrying that dep (5.1, 5.3, 5.4, 5.5, 6.6) wait on Story 1.1.1's measurement for full unblock. AC10 stays `[~]` (provisional rung-0; flips to `[x]` when Story 1.1.1 confirms or revises to rung-1/2/3). AC13 stays `[ ]` permanently (transferred to Story 1.1.1's scope per binding-only-cut carve-out). Memory `project_warden_ar_spike_binding_only.md` updated with Story 1.1 closure note + Story 1.1.1 sprint-status-entry note. | Stephane (via `bmad-dev-story`, claude-opus-4-7 dev agent) |
