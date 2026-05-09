# Story 1.1: Pre-PRD Performance Spike (AR-SPIKE)

Status: in-progress

<!-- Validation is optional. Run validate-create-story before dev-story for a quality check. -->

## Story

As **Stephane** (solo developer; Sprint 3 critical-path lead),
I want **the OpenCV JSI binding shipped as a real binding (not the current `loadFrameFromPath` stub) on the Poco X5 reference device, with measured PERF-002/003/004/005 numbers and validated map-ID and round-boundary accuracy floors**,
So that **PERF-010 is bound, the Innovation #1 fallback-ladder rung is determined (pass / rung-1 / rung-2 / rung-3 — the cloud-fallback rung is FORBIDDEN), and Sprint 3 mobile story scope (Epic 5/6) can finalize against the spike outcome.**

**Type:** Architecture-led spike. Hybrid deliverable — code change (real JSI binding for `loadFrameFromPath`) + measurement run on reference device + spike-report markdown artifact (`_bmad-output/architecture-spike-perf-floor.md`). The rung verdict is the binding output; the binding code is the means.

**Why this is the load-bearing first work item — and what gates it (G1):** Sprint Plan §2 Gate G1 — _"Story 1.1 (AR-SPIKE) is the load-bearing first work item. Stories 5.1, 5.3, 5.4, 5.5, 6.6 all carry an explicit `Story 1.1 spike` dependency. Do not start any of them before AR-SPIKE has a binding rung verdict."_ A wrong rung verdict (or a rung that hasn't yet been published) cascades into Sprint 3 as scope re-baselining at merge time. The spike's outcome dictates whether `mobile-AUTO-SLICE-001/002` ship in V1 (rung 0/1/2) or defer to V2 (rung 3, manual-clip-only V1).

**Why this is NOT blocked by G0 (Sprint 2.5 closure):** Sprint Plan §2 Gate G0 blocks _merges_ to `main`, not _development_ on feature branches. Story 0.2 is in `review` at the time this story file is created; the AR-SPIKE branch may proceed in parallel. **The spike's PR may not be merged until Story 0.2 reaches `done` and the G0 sign-off is on `main`.** This is non-negotiable per Decision #ES-3.

**Sprint-fit:** **needs-spike-or-split** — by design. This is the only story in Sprint 3's 76-story commit flagged `needs-spike-or-split` per Decision #ES-9. If the spike returns rung 3, Sprint 3 mobile-feature scope (Epic 5/6) re-baselines. The dev agent should not treat "took multiple focused days" as a failure mode — the spike IS the unknowable.

**Permitted spike outcomes (none of which is a story failure):**

| Rung | Trigger | V1 implication |
|------|---------|----------------|
| **0 — Pass** | All 4 PERF NFRs met on Poco X5 with real JSI binding | V1 launches with auto-slice on; PRD inherits the measured PERF-010 number; round-boundary accuracy floor binds as measured. |
| **1 — Partial fail** | PERF-002 OR PERF-005 over budget by < 50% | Lower auto-slice frame-sampling rate, re-measure. If now passing, V1 launches with reduced sampling rate. PRD `mobile-AUTO-SLICE-001` adds a "with reduced sampling on weak hardware" clause. |
| **2 — Partial fail** | PERF-003 OR PERF-004 over budget | Drop Minimap+HUD overlay rendering on weak hardware (gated by device profile). View modes degrade to Full + Minimap (no HUD overlay). PRD `mobile-CINEMA-002` adds a graceful-degradation clause. |
| **3 — Hard fail** | JSI binding cannot ship as real binding within V1 timeline OR multiple PERF NFRs > 50% over budget AND rung-1/rung-2 don't recover them | Defer auto-slice to V2; V1 ships **manual-clip-only** via Decision #UX-14 path. `mobile-AUTO-SLICE-*` FRs become V2-deferred; activation timer T1-coach via manual-clip becomes the only V1 path. **V1 still launches.** |
| **FORBIDDEN — cloud fallback** | NEVER, regardless of measured numbers | Breaks Innovation #1 (privacy + lower marginal cost). Architecture asserts this is forbidden as a permitted rung. The spike report MUST explicitly assert this is not the chosen rung. |

## Acceptance Criteria (checklist)

> **AC checkbox convention:** Items whose endpoint depends on **post-merge actions** (PRD update, downstream Wave-6 unblocking, sprint-status `review → done` flip) are held `[ ]` with inline carve-out notes. Items the dev agent fully controls during the work flip to `[x]` on completion. (Convention inherited from Story 0.2's D1 resolution — tighten over precedent.)

1. [ ] **AC1 — Real OpenCV JSI binding for `loadFrameFromPath`.** `apps/mobile/src/shared/services/opencv.ts:381` — `loadFrameFromPath(path)` returns a real `Promise<FrameBuffer>` (RGB-packed `Uint8ClampedArray` per the existing `FrameBuffer` interface at `apps/mobile/src/shared/services/opencv.ts:14-19`). It no longer throws. Implementation uses `react-native-fast-opencv`'s native JSI binding to decode JPEG keyframes on disk. **Verification:** boot a dev build on Poco X5; trigger the processing pipeline against a single keyframe; confirm a non-throwing return + correct width/height/length-of-`data` (`width * height * 3`).

2. [x] **AC2 — `react-native-fast-opencv` dep is installed and `expo prebuild` clean.** `apps/mobile/package.json` declares `react-native-fast-opencv` at the highest stable version compatible with RN 0.81 / Expo SDK 54 (verify on npm at spike start; the architecture text claims "already a dep" — **VERIFY** rather than trust; per Story 0.2 lesson, trust live files over plan claims). `pnpm install` succeeds with `.npmrc` `node-linker=hoisted` ([INVARIANT 9]) preserved. `pnpm --filter mobile exec expo prebuild` succeeds; `pnpm --filter mobile exec expo export --platform android` produces a Hermes bundle without errors. _If a stable RN-0.81-compatible version does not exist, this AC's failure path is **not** "skip the binding" — it is "spike returns rung 3" (binding cannot ship in V1 timeline). Document the constraint in the spike report._ **Verified 2026-05-09:** `react-native-fast-opencv@0.4.8` installed; the lib was developed against `react-native@0.79.1` but its peer-deps are wildcard and the JSI surface holds across the RN 0.79→0.81 minor gap. `pnpm install` succeeded (one unrelated peer warning: `react-dom@19.2.4` wants `react@^19.2.4`, we have 19.1.0 — does not affect mobile bundling). `expo prebuild --platform android --clean` succeeded; `apps/mobile/android/` regenerated. `expo export --platform android` produced a 5.27 MB Hermes bundle (`_expo/static/js/android/index-9491fc77a198e675a775b8da260972f8.hbc`) with no warnings about the new native module. `apps/mobile/android/` and `apps/mobile/ios/` added to root `.gitignore` so prebuild artifacts are not committed.

3. [ ] **AC3 — Reference device profile measured.** Poco X5 (Snapdragon 695 — 4× Cortex-A78 + 4× Cortex-A55, 6 GB RAM, 6.67" 1080p screen, Android 13). Device profile recorded in the spike report's `## Device profile` section: model, SoC, RAM, screen resolution, OS version, Android security-patch level (`adb shell getprop ro.build.version.security_patch`), the dev-build APK SHA-256, and the Hermes engine version reported by `adb logcat | grep -i hermes` at first launch.

4. [ ] **AC4 — PERF-002 measured on the 1h20 EVA After-h reference video.** Auto-slice run end-to-end against a 1h20 EVA After-h source (architecture-supplied; not committed to repo — Stephane stages locally on the device). Wall-clock auto-slice duration ≤ 5% of source duration (1h20 = 80 min → ≤ 4 min). The measurement excludes app cold-start time (timer starts at `runProcessingPipeline()` entry, stops at `updateSessionStatus(sessionId, 'ready')`). The measurement is the **median of 3 runs** (cold-launch each run; clear MMKV processing checkpoints between runs). All 3 raw numbers + median + variance are recorded in the spike report.

5. [ ] **AC5 — PERF-003 measured on Cinema Mode view-mode toggle.** From a paid-user dev session with at least one auto-sliced segment opened in Cinema Mode, toggle the view-mode segmented control through Full → Minimap → Minimap+HUD → Full. Frame-time delta for each transition ≤ 100 ms. **No `expo-av` player swap permitted** — the same source must be used; only crop/style change. Measured via Hermes performance API (`performance.now()`) bracketing the toggle handler. Median of 3 sessions × 3 toggles each (9 total samples). All 9 raw numbers + median + p95 in the spike report.

6. [ ] **AC6 — PERF-004 measured on Cinema Mode cold-start.** Card View → tap Card → first frame visible. Timer starts at the navigation-action dispatch, stops at the first `expo-av` `onLoadedData` event for the Cinema Mode `<Video>`. Median ≤ 1.5 s. Median of 5 cold launches (full app cold-start between each). All 5 raw numbers + median + p95 in the spike report.

7. [ ] **AC7 — PERF-005 measured on clip export (Mobile-tier).** From a paid-user dev session in Cinema Mode, define a 30 s clip via the bracket handles (per `mobile-CLIP-001`), trigger Mobile-tier export. Timer starts at the export-dispatch action, stops at the FFmpeg-kit completion callback for the encoded MP4. Median encode duration ≤ 60 s (≤ 2× clip duration). Median of 3 clip exports. All 3 raw numbers + median in the spike report.

8. [ ] **AC8 — Map ID accuracy ≥ 95% on unseen test set.** Run the legacy regression suite at `apps/tooling/tools/hash_validator.py` (Python; the authoritative regression tool for `tooling-VALIDATE-001` per architecture line 558) over an **unseen** test set (frames NOT in the `map_config.json` reference fingerprint set). Measure per-map accuracy and overall accuracy. Pass criterion: overall ≥ 95% AND per-map ≥ 90% on every canonical map (the 14 maps from `apps/tooling/tools/frame_labeler.py:19-34`). Spike report includes the confusion matrix and the test-set provenance (where the unseen frames were sourced; how many per map; ROI scaling assumptions). _If the on-device pHash output differs from the Python reference for the same frame, that's a binding-correctness bug, not a measurement gap — block the spike on resolving the divergence and document the root cause in the report._

9. [ ] **AC9 — Round-boundary detection floor validated.** Run the on-device `gameDetector` (KDA/HSV) + long-GOP `blackScreenDetector` fallback against the 1h20 reference + the existing test fixtures (`apps/mobile/src/features/video-processing/__tests__/`). Measure: (a) detected-START events vs ground truth; (b) detected-END events vs ground truth; (c) false-positive rate. The legacy tooling target is "100% black-screen-transition detection with 0 false positives" — the on-device port may degrade. **The spike SETS the floor**; the dev agent records the measured number AND a justified pass/fail-with-degradation verdict. Floor below 95% recall OR false-positive rate above 0 puts pressure on a rung-1/rung-2/rung-3 verdict.

10. [ ] **AC10 — Ladder rung verdict determined and recorded.** Pick exactly one of: `rung-0 (pass)` | `rung-1 (lower frame-sampling)` | `rung-2 (drop Minimap+HUD on weak hardware)` | `rung-3 (defer auto-slice to V2; manual-clip-only V1)`. Record the choice in the spike report's `## Ladder rung verdict` section with: (a) the chosen rung; (b) which AC4–AC9 measurements drove the choice; (c) for rung-1/rung-2, the parameter-tuning attempted and the re-measured numbers; (d) for rung-3, the V2-deferred FR list (`mobile-AUTO-SLICE-001`, `mobile-AUTO-SLICE-002`, plus any `mobile-CARD-*` graceful-degradation entries). _Iterative tuning is permitted: the dev agent may try lower sampling rates (rung-1 attempt) before falling to rung-2; rung-2 attempt before falling to rung-3._

11. [ ] **AC11 — `cloud fallback` rung explicitly asserted as forbidden.** Spike report's `## Forbidden rungs` section asserts verbatim: _"Cloud-fallback CV is FORBIDDEN regardless of measured numbers. Breaks Innovation #1 (privacy + lower marginal cost). Not a permitted rung in this spike."_ This is a defense against future dev-agents (or even future-self) interpreting a hard-fail as license to cloud-process frames.

12. [ ] **AC12 — Spike deliverable published.** `_bmad-output/architecture-spike-perf-floor.md` exists and contains, at minimum, these H2 sections in this order: `## Device profile` (AC3), `## Source video provenance` (1h20 EVA After-h — name, duration, resolution, encoder, NOT committed), `## PERF-002 — auto-slice` (AC4), `## PERF-003 — view-mode toggle` (AC5), `## PERF-004 — Cinema Mode cold-start` (AC6), `## PERF-005 — clip export` (AC7), `## Map ID accuracy` (AC8), `## Round-boundary detection floor` (AC9), `## Ladder rung verdict` (AC10), `## Forbidden rungs` (AC11), `## V1 implication summary` (per-rung; what the PRD inherits), `## Regression-test fixtures` (which fixtures from `apps/mobile/src/features/video-processing/__tests__/` and `apps/tooling/tools/hash_validator.py` were used). The file is the binding artifact reviewers grep for.

13. [ ] **AC13 — PRD updated post-spike with PERF-010 + conditional FR clauses.** _Held `[ ]` per AC checkbox tighten — this is post-merge admin._ After the spike PR merges, `_bmad-output/prd.md` PERF-010 line gets the measured number substituted in (replacing "TBD per architecture pre-PRD spike"). For rung-1/rung-2, the PRD adds the conditional FR clause exactly as architecture-line 855/856 specifies. For rung-3, the PRD V2-defers `mobile-AUTO-SLICE-001` and `mobile-AUTO-SLICE-002` and the `mobile-CARD-*` entries get the manual-clip-only graceful-degradation clause. This AC ships as a **separate follow-up commit** on the same branch (or a separate PR if the spike PR has already merged); flips to `[x]` once that commit lands on `main`.

14. [ ] **AC14 — Sprint-status flip on G1 close.** _Held `[ ]` per AC checkbox tighten — the `review → done` portion is post-merge admin._ `_bmad-output/sprint-status.yaml` `development_status[1-1-pre-prd-performance-spike-ar-spike]` flips `backlog → ready-for-dev → in-progress → review → done` across the work; `last_updated` bumps to current ISO date at each flip. `epic-1` flips `backlog → in-progress` when the story file is created (this happens at create-story time — already done by the time the dev agent reads this file; verify it). Flips to `[x]` once `done` lands.

15. [ ] **AC15 — Single-PR delivery (gated by G0).** All file modifications ship in **one PR** titled exactly `feat: AR-SPIKE — pre-PRD performance floor (Story 1.1)`. PR body links to: this story file; `_bmad-output/architecture-spike-perf-floor.md`; Sprint Plan §2 Gate G1 (`_bmad-output/sprint-plan.md` line 31); architecture line 832 (`#### Pre-PRD performance spike [SPIKE BOUND]`). Branch name: `ar-spike-perf-floor`. _Held `[ ]` until the PR is filed with the AC15-mandated title verbatim; flips to `[x]` once the PR is open. **The PR may not be merged to `main` until Sprint 0.2 reaches `done` and clears Gate G0** — per Decision #ES-3 / Sprint Plan §2 Gate G0._

16. [ ] **AC16 — G1 sign-off statement appended to spike report.** _Held `[ ]` until rung verdict is published in the spike report._ A final section `## G1 sign-off` is appended to `_bmad-output/architecture-spike-perf-floor.md` containing exactly: _"Story 1.1 published the AR-SPIKE rung verdict on \<YYYY-MM-DD\>. Sprint Plan §2 Gate G1 is now CLEARED. Sprint 3 stories with explicit `Story 1.1 spike` dependency (5.1, 5.3, 5.4, 5.5, 6.6) may begin development per the rung's V1 implication. PRD update follows in a separate commit per AC13."_ Flips to `[x]` once the section is in place.

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
  - [ ] Confirm Poco X5 dev device is reachable via `adb devices`. Capture device profile (model, SoC, RAM, screen resolution, OS, security-patch level) for spike report `## Device profile`.
  - [ ] Stage the 1h20 EVA After-h reference video on the device's `/sdcard/Movies/` (or a path the dev build's document picker can reach). **Do NOT commit the video to the repo.** Record name, duration, resolution, encoder (mediainfo / ffprobe output) in the spike report `## Source video provenance`.
  - [ ] Install the dev build APK on the Poco X5 (`pnpm --filter mobile exec expo run:android` against a connected device).

- [ ] **Task 4: Measure PERF-002 (auto-slice end-to-end on 1h20 source) (AC: 4)**
  - [ ] Cold-launch the app, sign in (use `EXPO_PUBLIC_AUTH_BYPASS=false` per [INVARIANT 8]; do not bypass auth — the entitlement gate must pass for `runProcessingPipeline` to fire).
  - [ ] Import the 1h20 reference video via the document picker.
  - [ ] Wrap `runProcessingPipeline` (or its outer caller in `useVideoProcessing.ts`) with a wall-clock timer: start at `runProcessingPipeline` entry, stop at `updateSessionStatus(sessionId, 'ready')`. Implementation suggestion: a temporary `console.time('perf-002')` / `console.timeEnd('perf-002')` log captured via `adb logcat`, then resolved via `--filter Reactnative` or a runtime `__DEV__`-gated MMKV write of the elapsed ms.
  - [ ] Run 3 times; cold-launch the app each time; clear MMKV processing checkpoints (`storage.deleteAll()` is too broad — selectively clear `processing.*` keys) between runs.
  - [ ] Record the 3 raw numbers + median + variance in the spike report `## PERF-002 — auto-slice`. Pass criterion: median ≤ 240 000 ms (4 min for 1h20).

- [ ] **Task 5: Measure PERF-003 (view-mode toggle ≤ 100 ms) (AC: 5)**
  - [ ] Open Cinema Mode for one auto-sliced segment.
  - [ ] Wrap the view-mode-toggle handler with `performance.now()` bracketing. Toggle Full → Minimap → Minimap+HUD → Full. Record per-transition ms.
  - [ ] Confirm **no `expo-av` source swap** — verify by inspecting React DevTools (or instrumenting the `<Video>` component) that the same `source` prop instance is reused across toggles; only crop/style props change.
  - [ ] Run 3 sessions × 3 toggles = 9 samples. Record raw + median + p95 in `## PERF-003`.

- [ ] **Task 6: Measure PERF-004 (Cinema Mode cold-start ≤ 1.5 s) (AC: 6)**
  - [ ] From Card View, tap a Card. Timer starts at the navigation dispatch (`navigation.navigate('CinemaMode', ...)`), stops at the first `<Video onLoadedData>` event.
  - [ ] Run 5 cold launches (full app cold-start, then immediate Card-tap). Record raw + median + p95 in `## PERF-004`.

- [ ] **Task 7: Measure PERF-005 (clip export ≤ 60 s for 30 s Mobile-tier clip) (AC: 7)**
  - [ ] In Cinema Mode, define a 30 s clip via the bracket handles. Trigger Mobile-tier export.
  - [ ] Timer from export-action dispatch to FFmpeg-kit completion callback (the same FFmpeg path used in `apps/mobile/src/shared/services/ffmpeg.ts`).
  - [ ] Run 3 clip exports. Record raw + median in `## PERF-005`.

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
| Poco X5 dev device reachable | `adb devices` returns it | Spike halts; cannot measure on reference device. Record device unavailability in report; flag for Stephane. |
| Android 13 OS version | `adb shell getprop ro.build.version.release` returns "13" | Note OS version actually present; spike still proceeds — measurements anchored to the actually-tested device. |
| 1h20 EVA After-h reference video staged on device | File exists at `/sdcard/Movies/<name>.mp4` (or document-picker-reachable path); `mediainfo` confirms duration ≈ 80 min | Stephane sources from his archive; spike report records the specific source file (name, duration, resolution, encoder). |
| Unseen map-ID test set available | ≥ 420 frames (≥ 30 per canonical map × 14 maps) labeled with ground-truth map name | Stephane sources from his frame_labeler exports OR generates from the reference video segments; record provenance. |
| `apps/tooling/tools/hash_validator.py` runnable | `cd apps/tooling && python tools/hash_validator.py --help` returns help text | Repair the tooling environment first (the legacy regression tool is the authoritative reference for AC8). |
| `react-native-fast-opencv` has a stable RN-0.81-compatible release | Check `npm view react-native-fast-opencv versions --json` and the lib's GitHub releases at install time | If no compatible release: this is exactly the rung-3 trigger (AC2 fail path); document and verdict accordingly. |

### Reference device profile (Poco X5)

From architecture line 839: Snapdragon 695 (4× Cortex-A78 + 4× Cortex-A55), 6 GB RAM, 6.67" 1080p screen, Android 13. _Verify each at spike start; the spike report's `## Device profile` section is the binding device snapshot._

The Poco X5 is intentionally a **mid-tier** reference device — slow enough that auto-slice is a real workload, fast enough that V1 doesn't ship requiring a flagship. Devices weaker than Poco X5 are out of scope for V1 (PERF-010 binds at this device's measured floor).

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
- **Do NOT** re-run the spike against a different device "to get better numbers". The reference device is **Poco X5**, period. Devices weaker than Poco X5 are V1-out-of-scope; devices stronger than Poco X5 over-promise the floor.
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
4. **Manual smoke test**: cold-launch the dev build on Poco X5; auto-slice the 1h20 reference; open Cinema Mode; toggle view-mode; export a 30-s clip. End-to-end pass-through with no crashes is the gating manual check before declaring measurements final.

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

**Outcome:** rung verdict = `<rung-0 | rung-1 | rung-2 | rung-3>` — see `_bmad-output/architecture-spike-perf-floor.md` for measured PERF-002/003/004/005 numbers, map ID accuracy, round-boundary detection floor, ladder-tuning attempts, and V1 implication summary.

This PR **clears Sprint Plan §2 Gate G1**: Sprint 3 stories with explicit `Story 1.1 spike` dependency (5.1, 5.3, 5.4, 5.5, 6.6) may begin development per the rung's V1 implication. PRD update with PERF-010 binding + conditional FR clauses follows in a separate commit per AC13.

**This PR may not merge until Story 0.2 reaches `done` and clears Gate G0** — per Decision #ES-3 / Sprint Plan §2 Gate G0.

## Files

- `apps/mobile/src/shared/services/opencv.ts` — UPDATE: replace `loadFrameFromPath` stub with real `react-native-fast-opencv` JSI binding (line 381 only; pure-TS primitives unchanged)
- `apps/mobile/package.json` — UPDATE: add `react-native-fast-opencv` dep
- `pnpm-lock.yaml` — UPDATE (transitive)
- `_bmad-output/architecture-spike-perf-floor.md` — NEW: spike deliverable per AC12 + AC16 G1 sign-off
- `_bmad-output/implementation-artifacts/1-1-pre-prd-performance-spike-ar-spike.md` — story spec with Tasks/Subtasks marked, Dev Agent Record, File List, Change Log; Status flipped to `review`
- `_bmad-output/sprint-status.yaml` — `1-1-...` flipped `ready-for-dev` → `review`; `last_updated` bumped

## Forbidden rungs

This spike does NOT include a cloud-fallback CV path. Cloud fallback is FORBIDDEN regardless of measured numbers per architecture line 858 — breaks Innovation #1 (privacy + lower marginal cost). The spike report's `## Forbidden rungs` section asserts this verbatim.

## Manual smoke verification (reviewer guidance)

- `pnpm install && pnpm --filter mobile exec expo prebuild` succeeds
- `pnpm --filter mobile exec expo export --platform android` produces a Hermes bundle without warnings
- `pnpm --filter mobile test` passes (existing detector tests use injected synthetic `FrameLoader`s; not affected by the binding change)
- Manual on-device smoke: cold-launch dev build on Poco X5; auto-slice 1h20 EVA After-h reference; open Cinema Mode; toggle view-mode; export a 30-s clip — end-to-end pass-through with no crashes

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

claude-opus-4-7 (Claude Opus 4.7, 1M context) via the BMad `dev-story` skill on 2026-05-09. Code-side execution only (Tasks 1, 2, partial 12); device-bound work (Tasks 3-9, Task 10 verdict, Tasks 11/13 reports) paused for Stephane's Poco X5 measurement runs.

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

⏸️ **HALT — paused for Stephane's device-bound measurements.** The remaining ACs (3-11) and Tasks (3-11, post-merge 13) require physical hardware that the dev agent cannot drive:
- **Poco X5 dev device** + adb access for cold-launch timing.
- **1h20 EVA After-h reference video** staged on device (architecture-team-supplied; not committed).
- **Unseen map-ID test set** of ≥ 420 labeled frames (≥ 30 per canonical map × 14 maps) for AC8 accuracy validation against `apps/tooling/tools/hash_validator.py`.

The honest, on-device validation step from AC1 ("boot a dev build on Poco X5; trigger the processing pipeline against a single keyframe; confirm a non-throwing return + correct width/height/length-of-`data`") has NOT yet been performed — that is the next physical step, and the spike's binding-correctness check that drives the rung-1/rung-2/rung-3 verdict.

⏸️ **Branch state at HALT-point.** On `ar-spike-perf-floor` cut from `main@76fec7c`. Working tree dirty with the Tasks 1-2 deliverable (see File List below). The work is **not yet committed** — Stephane's options at handoff:
1. **Commit Tasks 1-2 as a self-contained `feat:` commit now**, then run measurements on the committed binding and add the spike report + verdict in a follow-up commit. This gives a clean snapshot that survives context loss and supports rebase-against-post-Story-0.2-main.
2. **Defer the commit until measurements are done**, then bundle binding + report + verdict into a single commit. Higher risk of losing intermediate state.
3. **Discard and restart** if any of the binding implementation choices need revision after Stephane's first manual smoke on-device.

**Forbidden rung remains forbidden.** No cloud-fallback code was added "in case". AC11 will be asserted verbatim in `_bmad-output/architecture-spike-perf-floor.md` once that file is authored (post-measurement). The dev agent has not introduced any opt-in flag, conditional branch, or deferred path that would enable cloud CV — even as a degraded fallback. Cloud CV is excluded by construction in this code path.

### File List

- `apps/mobile/src/shared/services/opencv.ts` — UPDATE: replace the throw-stub at line 381 with a real `react-native-fast-opencv` JSI binding for `loadFrameFromPath`. Native deps lazy-required to keep the module jest-importable. Pure-TS primitives (lines 14-371) untouched.
- `apps/mobile/src/shared/services/__tests__/opencv.test.ts` — UPDATE: remove the now-obsolete `describe("loadFrameFromPath", ...)` block (lines 237-243 in the old file) and the corresponding `loadFrameFromPath` import. Replaced with a comment documenting the intentional gap. The 9 pure-TS detector test blocks above are unchanged.
- `apps/mobile/package.json` — UPDATE: add `react-native-fast-opencv@0.4.8` to `dependencies`.
- `pnpm-lock.yaml` — UPDATE (transitive): 71 packages added; no version bumps to existing first-party deps; `react-native-mmkv` stays at `3.3.3` (INVARIANT 9 preserved).
- `.gitignore` — UPDATE: add `apps/mobile/android/` and `apps/mobile/ios/` so `expo prebuild` artefacts are not committed (matches the unified monorepo's existing prebuild-on-demand convention).
- `_bmad-output/sprint-status.yaml` — UPDATE: `1-1-pre-prd-performance-spike-ar-spike: ready-for-dev → in-progress`; `last_updated` bumped to describe the AR-SPIKE branch state. (`epic-1: in-progress` was already set by `bmad-create-story`.)
- `_bmad-output/implementation-artifacts/1-1-pre-prd-performance-spike-ar-spike.md` — NEW (created by `bmad-create-story`) / UPDATE (this commit): Tasks 1+2 checkboxes, AC2 checkbox, Task 12 dev-agent-controllable subtasks, Dev Agent Record, File List, Change Log; Status flipped `ready-for-dev → in-progress`.

**Pending files (Stephane's measurement work):**

- `_bmad-output/architecture-spike-perf-floor.md` — NEW: spike deliverable per AC12 + AC16 G1 sign-off (data-first sections for AC4-AC9 measurements + AC10 verdict + AC11 forbidden-rung assertion). Authored after Stephane's device-bound runs.
- `_bmad-output/prd.md` — UPDATE (post-merge admin per AC13): PERF-010 line gets the measured number; conditional FR clauses for rung-1/2; V2-deferral for rung-3.

## Change Log

| Date       | Change                                                                                                | Author |
|------------|-------------------------------------------------------------------------------------------------------|--------|
| 2026-05-09 | Story file created via `bmad-create-story` workflow. Status: `ready-for-dev`. AC checklist drafted (16 ACs); Tasks/Subtasks drafted (13 tasks). Architecture-led spike scope captured per `_bmad-output/architecture.md` lines 832-868. Ladder rungs 0/1/2/3 enumerated; cloud-fallback rung asserted FORBIDDEN per AC11. Preconditions section flags external dependencies (Poco X5, 1h20 reference video, unseen test set, `hash_validator.py` runnable). AC checkbox tighten convention applied to ACs 13/14/15/16 (post-merge admin endpoints). `epic-1: backlog → in-progress` flipped (this is the first story in Epic 1). | Stephane (`bmad-create-story`) |
| 2026-05-09 | Branch `ar-spike-perf-floor` cut from `main@76fec7c`; Story 1.1 planning state relocated from Story 0.2's working tree (uncommitted) to the new branch. Status flipped `ready-for-dev → in-progress`. Tasks 1 + 2 fully executed code-side: `react-native-fast-opencv@0.4.8` installed; `loadFrameFromPath` stub at `opencv.ts:381` replaced with a real JSI binding (`base64ToMat` → `cvtColor BGR→RGB` → `matToBuffer`); native imports lazy-required (jest-safe) per `ffmpeg.ts`'s `getFFmpeg()` precedent; obsolete stub-throw test removed (`opencv.test.ts:237-243`). `expo prebuild --platform android --clean` and `expo export --platform android` both succeeded; 5.27 MB Hermes bundle produced without warnings about the new native module. Full mobile jest suite passes (105/105). `.gitignore` updated to exclude prebuild artefacts (`apps/mobile/android/`, `apps/mobile/ios/`). AC2 → `[x]`. **HALTED at end of Task 2** for Stephane-driven device measurements (Poco X5 + 1h20 EVA After-h reference + unseen ≥ 420-frame map-ID test set required for ACs 3-9). | Stephane (via `bmad-dev-story`, claude-opus-4-7 dev agent) |
