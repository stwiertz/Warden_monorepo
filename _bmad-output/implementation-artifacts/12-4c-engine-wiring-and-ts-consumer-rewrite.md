# Story 12.4c: Engine Wiring + TS Consumer Rewrite

Status: backlog

Sprint fit: **`needs-spike-or-split`** — carried forward from Story 12.4 and **retained deliberately**. Even after the 4-way split this story spans a new native API, a bundled config, three rewritten detectors, a rewritten orchestrator and a ported state machine. It is flagged so the flag is not lost; **if it must split again, the seam is AC0a's native-API shape** (a per-session native call vs a per-frame bridge), because everything else follows from it. Split out of Story 12.4 on 2026-09-17 (`/bmad-create-story` on 12.4). **Depends on Story 12.4b** — flip to `ready-for-dev` when 12.4b reaches `review`.

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As **Stephane (solo dev / product owner)**,
I want **the bound detection engine actually wired into `processingPipeline.ts`, and the mobile detection consumers rewritten off v1 pHash data onto the v2 ROI/HSV engine**,
so that **auto-slice stops producing `unknown` map labels on current-HUD footage, the engine stops being "chosen but not wired", and the ~20 stories of Epics 5/6/7 that have been held behind this can start.**

---

## ⚠️ Read This First — Three Things That Are Not What the Epic Text Implies

**This story closes [`epics-and-stories.md:2750`](../epics-and-stories.md)'s hole** — *"The TS rewrite to read v2 ROI/HSV-band data is a separate post-V1 story (TBD; **not yet enumerated in any epic**)"* — which is **trigger #2 of the whole engine-first pivot**. Without it, V1 ships [`:2748`](../epics-and-stories.md)'s *"auto-slice produces `unknown` map labels on HUD 2.0 sessions."*

Read [`architecture-spike-gpu-megashader.md`](../architecture-spike-gpu-megashader.md) → *Engine verdict* and *What this does NOT bind* first. Then these three:

### 1. 🔴 The detection SEMANTICS exist only in Python. Kotlin has fire bits and nothing else.

`WardenCpuBaseline.evaluate()` returns `BooleanArray(nRules)` — **one bit per rule, and that is all**. Everything that turns fire bits into *"this keyframe is in a match on Atlantis"* lives in **Tool 12's Python**:

| what | where | lines |
|---|---|---|
| fire bits → three classifier verdicts | [`apps/tooling/tools/keyframe_engine_bench/scoring.py`](../../apps/tooling/tools/keyframe_engine_bench/scoring.py) | 169 |
| verdicts → phase timeline, with doubt | [`apps/tooling/tools/keyframe_engine_bench/phases.py`](../../apps/tooling/tools/keyframe_engine_bench/phases.py) | 225 |

**Neither has ever run on a device.** You are porting them — to TypeScript or to Kotlin (AC0b) — and the port has a **parity obligation**, because Tool 12 is the reference Story 9.16 re-points the accuracy instrument at.

**🔴 The three classifiers use THREE DIFFERENT FORMULAS.** This is [`scoring.py`](../../apps/tooling/tools/keyframe_engine_bench/scoring.py)'s own headline warning, and it exists because the sprint-change proposal got it wrong (*"Tool 9 sums raw weighted"* — true of the **map-ID classifier only**). Implementing one formula everywhere *"silently breaks two of the three accuracy numbers"*:

| classifier | formula | threshold |
|---|---|---|
| **HUD-version** | `fires / n_hud` — **normalized, unweighted** | 0.5 |
| **in_match** | `fires / n_im` — **normalized, unweighted, then HARD-BINARY** (never `unknown`) | 0.5 |
| **map-ID** | `sum(effective_weight × fired)` — **RAW, UNNORMALIZED** | `identification_threshold` = **0.6** |

**And a degeneracy you must reproduce, not "fix":** all 134 shipped rules carry `weight = 1.0` / `weight_override = null`, so the map-ID weighted aggregate reduces to a **plain count of fired zones**. Against an *unnormalized* sum with threshold 0.6, **any map with ≥ 1 fired zone clears it** — so map-ID is effectively `argmax(fired_count)` and the threshold is **near-inert**. [`scoring.py`](../../apps/tooling/tools/keyframe_engine_bench/scoring.py) reproduces this **as-is** and says so: *"that is 9.16's call."* **It is not yours either.** Port the behaviour; log the observation; do not repair it here.

### 2. 🔴 The `unknown` path this story must honour is DOUBT, and doubt HOLDS rather than advancing.

`mobile-AUTO-SLICE-003` (*"marks `map_name = "unknown"` when confidence is below the recognition threshold; navigation and Cinema Mode remain available"*) is where the engine's **doubt** state lands ([prd.md](../prd.md)), and founding constraint **E4** makes doubt *"a first-class outcome, never forced to the nearest class."*

[`phases.py`](../../apps/tooling/tools/keyframe_engine_bench/phases.py)'s mechanism, which you port:
- **Detect:** with 3 in_match zones the score quantizes to {0, ⅓, ⅔, 1}. A **unanimous** vote is confident; a **split** vote is doubt. Formally `doubt iff |ratio − threshold| < doubt_margin`, default **0.2**. `doubt_margin = 0.0` disables doubt and reproduces 9.13's behaviour exactly.
- **Never force:** a doubtful frame is *emitted* as `doubt`.
- **Resolve by surrounding reliability:** a doubtful frame **does not advance the machine — the internal state HOLDS.**

**Consequently every frame has BOTH an emitted state (which may be `doubt`) and an internal state (which never is). Spans are cut from the INTERNAL state.** Get this wrong and every `in_match → doubt → in_match` blip shreds a match into two segments. States: `in_match` · `score_screen` · `not_in_match` · `doubt`.

### 3. 🔴 The stages you are replacing are not a detail — stages 1 and 2 COLLAPSE.

Today (`processingPipeline.ts`, 546 lines): **FFmpeg extracts every keyframe to `./keyframes/*.jpg` on disk (0–30%)**, then **detection re-loads each JPEG through `loadFrameFromPath` → `react-native-fast-opencv` → pure-TS detectors (30–70%)**.

The bound engine decodes keyframes **in RAM via MediaCodec** and evaluates them **in Kotlin**. There is no JPEG, no disk round-trip, and no per-frame JS bridge crossing. **Stage 1 and stage 2 become one native call.** That changes the progress ranges, the MMKV checkpoint keys, the GOP branch, and possibly whether `react-native-fast-opencv` is still a dependency at all (AC0d).

**⚠️ And a documentation trap:** both [`docs/architecture-mobile.md`](../../docs/architecture-mobile.md) and [architecture.md](../architecture.md)'s project tree describe `opencv.ts` as a **stub whose `loadFrameFromPath` throws**. **That is stale** — [`opencv.ts:412-492`](../../apps/mobile/src/shared/services/opencv.ts#L412) is a complete `react-native-fast-opencv` JSI implementation. Story 12.4b corrects the two table rows; **do not plan around the stale description.**

---

## Acceptance Criteria

### AC0 — Kickoff decisions (resolve BEFORE Task 3; record verdicts in the Dev Agent Record)

- [ ] **AC0a — 🔴 THE SHAPE OF THE NATIVE API.** This is the story's spine; everything else follows. Today the module exposes only `runBench(mode, video, limit, cpuFrames)` and `describeDevice()` — both bench entry points returning a JSON string.
  - **Option A (RECOMMENDED) — one per-session native call.** `analyzeSession(videoPath, configJson, options) → JSON` returning the full keyframe timeline (per-keyframe: `timestampMs`, emitted state, confidences, map scores) plus the resolved spans. **For:** one bridge crossing instead of 1061; matches how the engine already works (`runAll` owns the loop); keeps the hot loop entirely in Kotlin; and it is the only shape in which the decode-loop pipelining 12.4a built can actually pay off. **Against:** progress reporting needs a callback or an event emitter (the pipeline's `reportProgress` funnel expects granularity — see AC7), and a multi-minute call needs cancellation.
  - **Option B — per-keyframe bridge.** `nextKeyframe() → fires`. **For:** trivially incremental progress, TS keeps the state machine. **Against:** **1061 bridge crossings**, each marshalling a JSON string, on a legacy (non-Turbo, non-JSI) bridge — this is very likely to cost more than the entire rule-evaluation budget it exists to serve (which is ~1% of the wall). **Do not choose this without measuring one crossing first.**
  - **Option C — hybrid:** per-session call + a progress event stream. Realistically what Option A becomes; record it as A-with-events rather than a third path.
  - **Whatever you choose, it is reached ONLY through `apps/mobile/src/shared/services/detectionEngine.ts`** ([INVARIANT: native-modules-only-via-shared-services](../architecture.md)). No feature module touches `NativeModules.WardenDetectionEngine`. That invariant is why the seam exists.
- [ ] **AC0b — Where scoring + phase resolution live: Kotlin or TypeScript.** Porting [`scoring.py`](../../apps/tooling/tools/keyframe_engine_bench/scoring.py) + [`phases.py`](../../apps/tooling/tools/keyframe_engine_bench/phases.py). **Kotlin (RECOMMENDED under Option A)** — keeps the per-keyframe loop native, returns a finished timeline, and the ~390 lines of ported logic sit beside the evaluator they consume. **TypeScript** — easier to unit-test under jest (the project's established test surface; there are **no Kotlin tests in this repo at all**), and keeps detection *policy* in the layer that owns the product semantics. **State the testing consequence of your choice explicitly** — if it goes to Kotlin, say how it gets tested, because "on-device bench only" is a real cost.
- [ ] **AC0c — How `map_config.v2.json` reaches the device.** **DECIDED 2026-09-17 by Stephane at create-story: 12.4c bundles it minimally; Story 1.13 generalises later.** Ship `map_config.v2.json` as a **bundled Metro asset** with a narrow loader — enough to make the engine real. **Story 1.13 (`backlog`, released for create-story) later adds the hybrid stale-while-revalidate Firestore overlay, `schema_version` handling and the per-HUD manifest on top.** Your remaining decision is only the *mechanics*: asset path, how the Kotlin side receives it (a JSON string across the bridge vs a file URI it reads — note the native side currently hardcodes `File(workDir, "map_config.v2.json")` at [`WardenEngineBench.kt:53`](../../apps/mobile/plugins/kotlin/WardenEngineBench.kt#L53) and has **no** notion of Firestore or bundled assets), and what you leave as an explicit seam for 1.13. **Leave a seam, and name it in the Dev Agent Record so 1.13's create-story finds it.**
- [ ] **AC0d — The fate of `react-native-fast-opencv` and the pHash primitives.** If the engine decodes and evaluates natively, `loadFrameFromPath` — **the only runtime OpenCV call site in the whole app** — may have no callers left. Check: the results stage uses **ffmpeg's** `extractFrameAt`, not OpenCV. If OpenCV genuinely becomes unreferenced, **removing it retires a native module and a SEC-007 line**, which is a real architectural win. **But verify before deleting** — and if you keep it, say what still needs it. Same question for the pure-TS pHash primitives in [`opencv.ts`](../../apps/mobile/src/shared/services/opencv.ts) (`phash` `:314`, `hammingDistance` `:381`, `cropToGrayscale` `:194`, `resizeGrayscale` `:220`) which have no consumer once `mapIdentifier.ts` is rewritten. **Recommended: retire the pHash primitives with their consumer; decide OpenCV on evidence.** *(`@warden/contracts` is declared in `apps/mobile/package.json` but imported by nothing in `apps/mobile/src` — this story is the natural moment to make that dependency real, see AC4.)*
- [ ] **AC0e — What happens to the long-GOP fallback.** [`blackScreenDetector.ts`](../../apps/mobile/src/features/video-processing/blackScreenDetector.ts) (292 lines) is a two-pass memory-tight path selected by `getGopInfo().hasShortGop`, and it exists because holding ~600 MB of decoded frames for a 60–90 min session is not viable. **Under a keyframe-only engine the GOP branch may be meaningless** — the engine decodes *keyframes only* by construction, 1061 for a 73-minute capture, and never holds the frame set. **Decide: does the GOP branch survive at all?** If it does not, this story deletes a 292-line module and a branch in the orchestrator, and `mobile-AUTO-SLICE-001`'s *"with reduced sampling on weak hardware"* clause re-attaches to **ladder rung 1 step 1b (keyframe decimation)**, which is where Story 12.3 already moved it. **State the decision and its PRD consequence.**

### The native seam

- [ ] **AC1 — A production detection API exists on the native module and on `detectionEngine.ts`.** Per AC0a. Not `runBench`. It must: accept a video path and the config; report progress in a form the pipeline can funnel (AC7); be cancellable (a user can leave the screen mid-run — see the foreground-service contract in AC8); and never leave the bench's `benchInFlight` latch or the codec wedged on an error path.
- [ ] **AC2 — `detectionEngine.ts` remains the sole JS entry point.** [INVARIANT: native-modules-only-via-shared-services](../architecture.md). **No feature module imports `NativeModules`.** Verify by grep before delivery, as 12.2's AC18b did.
- [ ] **AC3 — The native side gets its config from the app, not from a hardcoded adb path.** [`WardenEngineBench.kt:53`](../../apps/mobile/plugins/kotlin/WardenEngineBench.kt#L53)'s `File(workDir, "map_config.v2.json")` must not be the production path. Per AC0c. **The bench may keep its own staged-file path** — it is a bench.

### The config

- [ ] **AC4 — `map_config.v2.json` is bundled, validated, and typed.** Per AC0c. Validate against the shipped contract — **`contracts/map-config.schema.json`** and its generated zod `MapConfigSchema` (`@warden/contracts`). **🔴 The generated zod is LOSSY:** `hud_version_detection` and `in_match_detection` are `z.array(z.any())`, `roi` is `z.any()`, and each map entry is `z.any()`, because the generator does not resolve `$defs` (`Rect`, `Hsv`, `Zone`, `MapEntry`). **Consuming `MapConfigSchema` as-is gives near-zero type safety on exactly the fields you care about.** Either tighten the generator (`packages/contracts/scripts/generate-zod.mjs`, then `pnpm --filter @warden/contracts build`) or add a narrow mobile-side zone type and say why. **Do not pretend the generated type validates zones when it does not.** **E1 binds: no `schema_version` bump, rules stay rectangles.**
- [ ] **AC5 — HUD-version selection happens once per session, not per frame.** The schema's own contract: *"Runtime picks the matching `map_config.<hud_version>.json` once per session via `hud_version_detection`."* With one bundled config today this is nearly trivial — **implement it as the real mechanism anyway**, because it is the seam 1.13 and future HUD versions extend. Empty detection arrays are legal and **must short-circuit to `unknown`**, not crash.

### The rewrite

- [ ] **AC6 — The three detectors are rewritten onto v2 ROI/HSV semantics.** Per AC0b, with the **three distinct formulas** of point 1 above:
  - [ ] **`gameDetector.ts`** — today a KDA white-pixel-ratio + HSV classifier with a debounced 2-state FSM (`createGameDetector`, `pairEventsIntoSegments`). Becomes the **binary `in_match`** classifier plus the ported phase machine. **Its `score_offset_s` threshold is superseded by the config's `score_screen_duration_ms` (15000).**
  - [ ] **`mapIdentifier.ts`** — today DCT pHash + Hamming against `config.maps` (hex fingerprints). Becomes **raw weighted-aggregate zone scoring** over `minimap_identification.maps.<slug>.zones` against `identification_threshold` (0.6), with **`unknown` below threshold** (`mobile-AUTO-SLICE-003`). **🔴 `minimap_identification.roi` MUST BE IGNORED by the engine** — this is Story 9.15's D2, escalated into Story 12.1 as AC13b. Zones carry their own absolute coordinates; the shared ROI is authoring metadata.
  - [ ] **`blackScreenDetector.ts`** — per AC0e.
  - [ ] **`segmentation.ts`** — `buildMapSegments` zips spans with map IDs. Spans now come from the phase machine's **internal** state (point 2), and the score screen is **timing-derived** from `score_screen_duration_ms`, not a detected class. **`mobile-AUTO-SLICE-004`** (lobby removal) still holds: lobby and transition are **merged into `not_in_match`** by design.
- [ ] **AC7 — `processingPipeline.ts` orchestrates the new chain without losing what it already guarantees.** **🔴 This file has behaviours that are load-bearing and are NOT restated in this story's ACs — they are requirements anyway.** Preserve, and prove you preserved:
  - [ ] **Foreground-service lifecycle** — `startForegroundService` inside the try, `stopForegroundService` in `finally`, **owner-token** stop, start-before-stop ordering, and `updateForegroundServiceStage` pushed **once per stage transition** through the single `reportProgress` funnel. This is Story 1.2's JS-push contract ([[project_warden_fgs_mmkv_push]]) and **the only part of this file with test coverage today** — `processingPipeline.test.ts`'s 4 tests are *entirely* FGS lifecycle.
  - [ ] **MMKV checkpoint resume** — `processing.<sid>.stage` plus the per-stage payload keys. Stages collapse (point 3), so **the key set changes**; state the new keys, and state what happens to a checkpoint written by the old shape. *(A stale checkpoint resuming into a rewritten pipeline is a real upgrade path, not a hypothetical — decide it.)*
  - [ ] **Error semantics** — stage-boundary catch → session status `error` → rethrow, **checkpoints deliberately NOT cleared** so the user can retry ([architecture.md](../architecture.md): *"checkpoint stays so user can retry"*).
  - [ ] **Progress monotonicity** — `stageToOverallProgress` maps stages onto 0–100. Re-range for the collapsed stages. *(Today only `keyframes` and `results` are incremental; `detection` and `segmentation` report only 0 then 100. A per-session native call makes this **worse** unless AC0a's progress mechanism is real — do not regress the one thing the user actually watches during a multi-minute run.)*
  - [ ] **The results stage** — `extractFrameAt` per segment at `scoreScreenMs ?? endTimeMs`, **clamped to `videoDurationMs - 50`** to avoid past-EOF reads, writing `./results/map_<i>.jpg` and `updateResultFramePath`. Best-effort: a thumbnail failure warns and continues. **Keep that tolerance.**
  - [ ] **`assertSafeSessionId` / path-traversal hardening** — `SAFE_SESSION_ID = /^[a-zA-Z0-9_-]+$/`; all on-disk paths namespaced under `getProcessingDir(sessionId)`. **Any new native path must go through the same gate.**
- [ ] **AC8 — The engine runs under the Foreground Service, and the threading model is respected.** [architecture.md](../architecture.md)'s re-derived amendment 5d: the FGS is justified by **process lifetime at foreground importance for a multi-minute run**, *not* JS-context co-location. Under Decision #13 *"with no EGL context there is no GL thread-binding constraint at all, only MediaCodec's own callback thread."* The bench already runs on a plain worker thread (`Thread("warden-bench-bridge")`). **Do not marshal decode work onto the JS thread**, and do not reintroduce a thread-affinity requirement that the GLES removal just eliminated.

### Proof

- [ ] **AC9 — 🔴 The ported scoring + phase logic is proved against Tool 12, not asserted.** The port must reproduce Tool 12's output on the same inputs. **Minimum:** a fixture-driven test over a pinned fire-bit sequence → expected timeline, generated from Tool 12 and committed, covering: all three classifier formulas; the `weight = 1.0` degeneracy; **hue wraparound** (**E3** — `h_min > h_max` MUST be read as an interval crossing 0/1; **68 of 134 shipped rules are full-circle, 9 are wrap**); the **69 low-saturation rules** where `h_tol = 180` leaves hue unconstrained ([[project_warden_low_sat_hue_unconstrained]]); doubt detection at the split vote; **and doubt HOLDING rather than advancing** (point 2 — the single most likely thing to get wrong). **A test that only covers the happy path does not close this AC.**
- [ ] **AC10 — Parity is not broken.** 12.4b established the bound configuration at **0 disagreements / 357,244 decisions** against `pc_reference_fires.json`. This story adds scoring and orchestration **above** the fire bits and must not perturb them. Re-run the parity check and report it.
- [ ] **AC11 — The pipeline is tested beyond the foreground service.** Today `processingPipeline.test.ts` covers **only** FGS lifecycle — *"No test covers the stage sequence, progress math, checkpoint resume, detection branch, or map identification."* You are rewriting all of them. **Add coverage for the stage sequence, the progress mapping, checkpoint resume, and the doubt→span behaviour**, and keep the 4 FGS tests green. Mobile: **jest + jest-expo**, co-located `__tests__/` (Decision #ES-6).
- [ ] **AC12 — `unknown` degrades gracefully, end to end.** `mobile-AUTO-SLICE-003` + REL-006: *"below-floor behaviour is graceful degradation, not blocking error."* A doubtful or below-threshold map yields `map_name = "unknown"` with navigation intact — **not** a thrown error, **not** a forced nearest-class label (**E4**).

### Fences, gates, delivery

- [ ] **AC13 — Scope fence.** 12.4c does **NOT**: re-touch the decode loop's timeout / flush / keyframe index (**12.4a's**) · remove GLES or port the colour conversion (**12.4b's**) · **re-measure PERF-002 end to end, resolve provisional rung-0, or retire ladder rung 3 (all 12.4d's)** · build the hybrid Firestore overlay / `schema_version` migration / per-HUD manifest (**1.13's** — leave the seam, per AC0c) · populate or retune zone data (**9.9b's**) · re-point Tool 9 or `video_test.py` (**9.16's**) · "fix" the map-ID threshold degeneracy (**9.16's**, point 1) · bump `schema_version` (**E1**) · run the exhaustive pHash→engine prose sweep (**9.10's** — you correct only what your own change falsifies) · touch Tool 12 (**12.1 is `done`**; you *read* it as the reference).
- [ ] **AC14 — REL-006 is NOT claimed here.** *"REL-006's ≥ 95% map-identification floor is NOT gated"* by Epic 12 — that is **9.9b's**, instrumented by Tool 9 via **9.16**, and *"without 9.16, REL-006 has no instrument at all."* The parity result is an **in-sample parity target with no holdout**, never a generalization claim. **Do not report an accuracy number as if it closed REL-006.** *(The three per-classifier accuracy figures in the spike are tagged `[U]` — unbacked by any delivered artifact. Do not promote them.)*
- [ ] **AC15 — Gates green.** `pnpm typecheck && pnpm test && pnpm format:check` from the repo root. **Re-verify the baseline first** — and note **12.4b legitimately moved the jest count** (it deleted the 4 shader-guard tests); take 12.4b's recorded number as your baseline, not 12.3's. Post-12.3 reference: tooling pytest **305**; root typecheck **3 errors, all `web` (pre-existing)**; web vitest **flaky, not merely red** (134/191 then 132/193 on the *identical* tree — its count cannot be a regression signal at ±2) (duplicate-React-under-pnpm, Story 1.10's finding — not yours). **Run `pnpm --filter @warden/contracts build` if you touch `contracts/*.schema.json`.** **🔴 Note `format:check` does NOT cover `_bmad-output/`** — `.prettierignore` excludes it, so a green run says nothing about story-file edits (it does cover your `apps/mobile` diff, which is what matters here).
- [ ] **AC16 — The Reader-App pre-commit gate passes.** `apps/mobile/scripts/reader-app-gate.sh` — mandatory before committing mobile changes ([architecture.md](../architecture.md) → *Enforcement Guidelines*). It runs a transitive-dep scan, which is exactly what AC0d's dependency decision touches.
- [ ] **AC17 — Architecture is updated to describe what now exists.** At minimum: [architecture.md](../architecture.md)'s project tree rows for `gameDetector.ts` (*"Short-GOP KDA/HSV detector"*), `mapIdentifier.ts` (*"**pHash matcher** against map_config"*), `blackScreenDetector.ts`, and the `opencv.ts` row; the FR-to-structure mapping (`mobile-AUTO-SLICE-001/002/003/004`); and [`docs/architecture-mobile.md`](../../docs/architecture-mobile.md) → *The processing pipeline* (the 4-stage table and the shortGop/longGop prose) and *Native modules*. **Correct what your change falsified. Leave the rest to 9.10.**
- [ ] **AC18 — Committed to `main`.** Direct to `main`, no branch, no PR ([[project_warden_main_branch_workflow]]); lowercase subject; scope `mobile`. Not auto-pushed. `sprint-status.yaml` rides in the same commit; check `git status` for foreign edits first ([[project_warden_shared_doc_commit_boundary]]).
- [ ] **AC19 — `sprint-status.yaml`: `12-4c-…` `in-progress → review`**, and `12-4d-…` `backlog → ready-for-dev`. Record AC0's five verdicts in the entry comment — 12.4d and Story 1.13 both read them.

---

## Tasks / Subtasks

- [ ] **Task 1 — Read the reference implementation.** (AC: 6, 9) [`scoring.py`](../../apps/tooling/tools/keyframe_engine_bench/scoring.py) and [`phases.py`](../../apps/tooling/tools/keyframe_engine_bench/phases.py) **in full, including their module docstrings** — the docstrings carry the three-formula warning, the degeneracy note, the doubt design and the falsified "latent bug" analysis. Then `_run_video` in [`__main__.py:450-540`](../../apps/tooling/tools/keyframe_engine_bench/__main__.py#L450) for how they compose.
- [ ] **Task 2 — Read what you are replacing.** (AC: 7) `processingPipeline.ts` (546 lines) end to end, and the three detectors. **Write down every behaviour AC7 lists before you change any of them.**
- [ ] **Task 3 — Resolve AC0.** (AC: 0a–0e) Five verdicts, recorded, before code. AC0a first — the rest follow from it.
- [ ] **Task 4 — Native API + config plumbing.** (AC: 1, 2, 3, 4, 5)
- [ ] **Task 5 — Port scoring + phases.** (AC: 6, 9) Three formulas, hue wraparound, doubt-holds. **Build the Tool 12 fixture first, then port against it.**
- [ ] **Task 6 — Rewrite the detectors.** (AC: 6)
- [ ] **Task 7 — Rewrite the orchestrator.** (AC: 7, 8) Work down AC7's checklist item by item; each is a regression if dropped.
- [ ] **Task 8 — Retire the pHash surface.** (AC: 0d) Only what AC0d's verdict releases.
- [ ] **Task 9 — Prove it.** (AC: 9, 10, 11, 12) Fixture parity · device parity re-run · pipeline tests · an end-to-end run on a real capture producing non-`unknown` map labels on HUD 2.0 footage — **which is the entire point of the story**.
- [ ] **Task 10 — Docs.** (AC: 17)
- [ ] **Task 11 — Deliver.** (AC: 13–19) Fence check → gates → Reader-App gate → commit → sprint-status.

---

## Dev Notes

### The config you are consuming

`apps/tooling/output/map_configs/map_config.v2.json` — **fully populated**, not the "2–3 map pilot" Story 9.15's summary describes:

```
schema_version            1              (config-SHAPE version, NOT detection-method, NOT HUD — 9.9c)
reference_resolution      1920 × 1080
hud_version               "v2"
score_screen_duration_ms  15000
hud_version_detection     10 zones
in_match_detection         3 zones       → quantizes to {0, 1/3, 2/3, 1}: split votes are the doubt band
minimap_identification
  ├ id                    "test"
  ├ identification_threshold  0.6
  ├ roi                   {minimap, 63, 922, 3, 5}   🔴 IGNORE — 9.15 D2 / 12.1 AC13b
  └ maps                  13 maps / 121 zones
      artefact · atlantis · ceres · coliseum · engine · helios · horizon
      lunar_outpost · outlaw · polaris · silva · the_cliff · the_rock
                                        ───────────────────────────────
                                        134 rules total (68 full-circle / 9 wrap / 57 normal)
```

Zone shape (`$defs/Zone`, all fields **required**): `id`, `x`, `y`, `width`, `height`, `hsv{h_center,h_tol,s_center,s_tol,v_center,v_tol}`, `min_ratio`, `weight`, `weight_override`.

**🔴 HSV units are USER-SPACE, not OpenCV-space:** H ∈ [0,360], H-tolerance ∈ [0,180] (half-circle max), S/V ∈ [0,100]. **OpenCV space is H 0–180, S/V 0–255.** The conversion is `WardenRulePacker`'s (`hueCenterUserToCv`, `svUserToCv`, `hueTolUserToCv`, `svTolUserToCv`, `resolveBandBounds`), it uses **`Math.rint` banker's rounding** (load-bearing for 31 of 134 rules), and **`hueTolUserToCv` clamps, never mods — labelled "THE #1 SHADER-PORT TRAP" in the source.** If AC0b puts scoring in TS, **you do not redo this conversion** — the packer already did it and the fire bits arrive pre-computed. If you find yourself converting HSV in TypeScript, stop: you have duplicated the packer.

**Map iteration order is config text order**, recovered by a hand-written brace-depth scanner (`orderedMapNames`) because `org.json.JSONObject` is a HashMap and loses insertion order. Zone ordering is `zone_picker`'s responsibility; **`map_config_emitter` does NOT sort.** Fire bits are returned in **canonical texel order** — `hud_version` zones, then `in_match`, then map zones in that order. **Misaligning that order is the failure 12.2 lost a full parity run to** (a rule-major vs row-major transpose that *"produced plausible-looking detections from garbage"*, and which **both** the LUT byte-check and the render-target self-test passed straight through). `WardenPackedRules.refs` carries `(texel, owningClass, zoneId, kind, effectiveWeight)` — **use `refs`, never positional arithmetic.**

### What `processingPipeline.ts` does today

```
Stage              MMKV keys (processing.<sid>.*)                      Progress
──────────────────────────────────────────────────────────────────────────────
keyframes          (FFmpeg → ./keyframes/*.jpg ON DISK)                  0– 30 %
detection          events · gameSegments · mapIdentifications ·         30– 70 %
                   duration
segmentation       segmentIds · segmentData  (+ SQLite map_segments)    70– 90 %
results            (./results/map_<i>.jpg)  → result_frame_path         90–100 %
```
Plus `perf002` (a `__DEV__`-gated wall-clock + per-stage marks) and a `[PERF-009]` line carrying event/segment counts, `gop_avg_s` and `hasShortGop`.

**Stages 1+2 collapse.** Points to watch: `getSession` miss throws **before** the try (so no FGS start/stop, no status change — preserve or deliberately change); `FrameLoader` is injectable via `RunPipelineOptions.loadFrame` and is how every existing test runs without a device — **whatever replaces it must stay injectable or the test surface dies**; detectors are constructed **inline** (`:143`, `:177`, `:195`), not injected, which is why the pipeline tests mock the modules wholesale.

### Dead code the rewrite can drop (verified unused in production `src`)

`blackScreenDetector.ts`: `BLACK_SCREEN_LUMINOSITY_THRESHOLD` (`:44`), `scanSaturationWindows` (`:118`), `detectGameEventsFallback` (`:245`), `blackScreenRangesFromSamples` (`:263`) — tests only. `types.ts`: `BlackScreenResult` (`:11`), `GameSegment` (`:51`, superseded by `GameSegmentTimeline`), `ProcessingState` (`:31`). `detectionConfig.ts`: ROIs `minimap` and `vertical` — declared and validated, **never read by any detector**.

### The v1 config path you are leaving behind

Mobile reads Firestore **`detection_config/latest`** → `DetectionConfig` (`version`, `reference_resolution`, `roi_zones{minimap,vertical,team_bar,kda,notkda,map_name}`, `thresholds{…,collision_threshold}`, **`maps: Record<string,string>`** = slug → 16-hex pHash), cached in MMKV under **`detection.config`**, validated by a hand-rolled `validateDetectionConfig`, gated at boot by `detectionConfigBootstrap` (`OfflineFirstLaunchError` / `MalformedRemoteConfigError`, three singleflights, a module-level memo). **There is no `hud_version`, no `schema_version`, no `in_match_detection`, no `minimap_identification` anywhere on the mobile TS side today.**

**🔴 Decide what happens to this whole apparatus and say so.** `detectionConfigService`/`Bootstrap` have **~20 tests** between them and the bootstrap gate blocks video processing on first-launch-offline. Options: keep it for the thresholds that survive; retire it with the pHash data; or leave it running in parallel until 1.13. **Killing `OfflineFirstLaunchError` is explicitly Story 1.13's AC7, and it is engine-agnostic** — do not do it here by accident.

### Testing standards

- **Mobile: jest + jest-expo, co-located `__tests__/<subject>.test.ts(x)`** (Decision #ES-6). Run `pnpm --filter mobile test`.
- Existing suites you are rewriting: `gameDetector`, `mapIdentifier`, `blackScreenDetector`, `segmentation`, `processingPipeline`, plus `opencv.test.ts`'s pHash block.
- **There are no Kotlin tests in this repo** — `android/app/src/` has no `test/` or `androidTest/`. Two Jest tests read Kotlin **off disk** as cross-language contract guards (the `BENCH_MODES` lockstep). **That pattern is the precedent if AC0b puts logic in Kotlin** — a fixture generated from Tool 12 and asserted from jest is in keeping with it.
- **No CI yet** (Phase 7). Gates are local: `pnpm typecheck && pnpm test` plus the Reader-App pre-commit hook.

### Project Structure Notes

- Feature-folder boundaries are enforced: **no cross-feature imports**; cross-feature comms go via a Zustand store or `src/shared/services/` ([architecture.md](../architecture.md) → *Anti-patterns*).
- Naming: modules / hooks / services are `camelCase.ts`.
- **[INVARIANT 3] — on-device only.** Telemetry must never carry frame data (the wrapper rejects `frame_url`). **Cloud-fallback CV is FORBIDDEN, verbatim and regardless of outcome.** The bound engine is on-device by construction; keep it that way.
- Native module JSON crosses the bridge as a **string**, parsed JS-side. The bridge is a **legacy `ReactPackage`, not a TurboModule** — there is no codegen spec in the repo. Relevant to AC0a's cost model.

### References

- [Source: _bmad-output/architecture.md#Decision-13] — *"`WardenCpuBaseline` and `WardenRulePacker` are already written and validated; **Story 12.4 wires them into `processingPipeline.ts` and the four detection modules**"*
- [Source: _bmad-output/architecture-spike-gpu-megashader.md] — *What this does NOT bind* ("the engine is chosen, not wired"; REL-006 not gated; in-sample parity ≠ accuracy); *Follow-up work required*
- [Source: _bmad-output/prd.md] — `mobile-AUTO-SLICE-001/002/003/004`; REL-006; the `unknown` fallback as the doubt landing site
- [Source: _bmad-output/epics-and-stories.md] — `:2748`/`:2750` (the hole this closes); Epic 12 constraints **E1** (schema unchanged), **E3** (hue wraparound mandatory), **E4** (doubt first-class); Decision #ES-6 (test ownership)
- [Source: apps/tooling/tools/keyframe_engine_bench/scoring.py] — the three formulas, the `weight = 1.0` degeneracy, *"that is 9.16's call"*
- [Source: apps/tooling/tools/keyframe_engine_bench/phases.py] — doubt detection / never-force / resolve-by-holding; emitted vs internal state; the falsified "latent bug" analysis
- [Source: contracts/map-config.schema.json] — `$defs` Rect / Hsv / Zone / MapEntry; user-space HSV units; `score_screen_duration_ms` semantics
- [Source: docs/architecture-mobile.md] — the pipeline stage table, the detection-config cache, the native-module table (**two rows stale — 12.4b corrects them**)
- [Source: _bmad-output/implementation-artifacts/deferred-work.md] — the `min_ratio` float32-vs-float64 item, **explicitly "Story 12.4's, when it wires `WardenCpuBaseline` into the pipeline"**

---

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
