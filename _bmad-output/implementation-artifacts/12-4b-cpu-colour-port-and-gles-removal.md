# Story 12.4b: CPU Colour-Conversion Port + GLES/EGL Surface Removal

Status: done

Sprint fit: `fits-in-one-sprint`. **Kotlin + plugin + architecture docs. No TypeScript rewrite, no pipeline wiring.** Split out of Story 12.4 on 2026-09-17 (`/bmad-create-story` on 12.4). **Depends on Story 12.4a** (decode-loop optimisation) — flip to `ready-for-dev` when 12.4a reaches `review`.

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As **Stephane (solo dev / product owner)**,
I want **the bit-parity YUV→RGB conversion moved from the rejected GPU shader onto the CPU, proven at zero disagreements, and only then the entire GLES/EGL surface physically deleted**,
so that **the engine [Decision #13](../architecture.md) bound can actually run without a GPU — and the Android-only GLES surface, its driver-defined colour path and its SEC-007 entry disappear at no measured cost.**

---

## ⚠️ Read This First — This Story Is a SUBSTITUTION, Not a Deletion

**The epic's own framing calls this "physically removing the GLES/EGL surface". That framing is incomplete and will get you a broken engine if you take it literally.**

Here is the coupling nobody wrote down until create-story found it:

```
TODAY (what 12.2 built)                    AFTER naive deletion
─────────────────────────────              ──────────────────────────
MediaCodec  →  YUV420Flexible              MediaCodec  →  YUV420Flexible
                    ↓                                          ↓
      RESOLVE_YUV_FRAG  (GPU)                            ??? nothing ???
      bt709 limited-range YUV→RGB                             ↓
                    ↓                                    WardenCpuBaseline
              BGRA bytes                                 .evaluate(bgra…)
                    ↓                                          ↓
      WardenCpuBaseline.evaluate(bgra…)                   💥 no pixels
```

**`WardenCpuBaseline.evaluate()` takes `bgra: ByteArray` — B,G,R,A per pixel, row-major** ([`WardenCpuBaseline.kt:74-79`](../../apps/mobile/plugins/kotlin/WardenCpuBaseline.kt#L74-L79)). **`WardenKeyframeDecoder.imageToKeyframe()` produces YUV planes** ([`WardenKeyframeDecoder.kt:766-785`](../../apps/mobile/plugins/kotlin/WardenKeyframeDecoder.kt#L766-L785)). The only thing that has ever bridged those two on the video path is **`RESOLVE_YUV_FRAG`, a GPU shader** ([`WardenDetectionEngine.kt:946-978`](../../apps/mobile/plugins/kotlin/WardenDetectionEngine.kt#L946-L978)) — the very file this story deletes.

**🔴 And the CPU arm has never been fed MediaCodec output at all.** Story 12.2's decisive AC12 measurement (`cpuVsGpu`, [`WardenEngineBench.kt:352-442`](../../apps/mobile/plugins/kotlin/WardenEngineBench.kt#L352-L442)) fed the CPU arm **BGRA decoded from labeled PNG Bitmaps** (`bitmapToBgra`), not from the decoder. That is precisely why the [spike report](../architecture-spike-gpu-megashader.md) tags the bound configuration **`[P]` — "a construction over three measured parts describing a configuration that was never run end to end."**

**You are the story that runs it end to end for the first time.** Port the colour conversion, prove parity, *then* delete. In that order — reversing it leaves you deleting the only working reference you had to check against.

---

## 🔴 Traps

1. **🔴 The conversion constants are load-bearing and were nearly wrong twice.** 12.2 found **two silent colour bugs** ([REPORT §6](../../apps/mobile/bench/12-2/REPORT.md) *"Two silent colour bugs found and fixed"*), and the shader's coefficients were ultimately proved **exhaustively and offline over all 2²⁴ (Y, Cb, Cr) triples** (`ac3_numpy_reference.py verify-constants`, error bounded at 1 unit on green over 0.179% of the domain). **Port the constants at [`WardenDetectionEngine.kt:963-976`](../../apps/mobile/plugins/kotlin/WardenDetectionEngine.kt#L963-L976) verbatim** — bt709, **limited range** (`color_range=tv` on the fixture). Re-deriving them from a formula you remember is how both earlier bugs happened.
2. **🔴 Chroma upsampling is NEAREST, not interpolated, and that is deliberate.** `RESOLVE_YUV_FRAG` samples chroma nearest-neighbour (`ivec2 pc = ivec2(p.x / 2, p.y / 2)`). The residual ΔS ≈ 2.46 against FFmpeg's `rgb24` is a **chroma-upsampling policy difference** (nearest vs swscale), ≤3 units of 255 — **not** a matrix error. **Do not "improve" to bilinear:** it would change the fire bits and break AC3's parity, and it would diverge from `lut.py`/Tool 12, which 9.16 re-points at this engine. ⚠️ **Do not quote `ac3_frame_diff.json`'s `diagnosis` string** — it reads *"MATRIX-ERROR-scale discrepancy (709 vs 601)"* for **both** paths and is a superseded heuristic label.
3. **🔴 NV12 vs NV21 is a live portability defect in this exact code.** The semi-planar fast path keys only on `uPixelStride == 2 && vPixelStride == 2` and uploads `planes[1]` as the base, **ignoring `planes[2]`** ([`WardenDetectionEngine.kt:460-470`](../../apps/mobile/plugins/kotlin/WardenDetectionEngine.kt#L460-L470), `isSemiPlanarNv12` [:626-671](../../apps/mobile/plugins/kotlin/WardenDetectionEngine.kt#L626)). On NV12 (`U V U V…`) the pairs are correct; **on NV21 (`V U V U…`) it mis-pairs Cb with the next column's Cr.** It was patched in 12.2's review but is latent on the reference device — the CPU port must handle **both** orders explicitly, and must not silently take a fast path on an untested layout.
4. **🔴 Geometry.** `requireGeometry()` ([:439](../../apps/mobile/plugins/kotlin/WardenDetectionEngine.kt#L439)) hard-fails off-1920×1080; Path Z had no such assertion and silently rescaled. Zone coordinates are calibrated at `reference_resolution` **1920×1080** and `clampRect` is applied CPU-side at pack time. **The CPU converter must assert its geometry, not rescale.**
5. **🔴 Two Jest tests will go red the moment you delete the asset, and one of them reads Kotlin off disk.** `detectionEnginePlugin.test.ts` (4 tests) is entirely a guard on the `.frag` checksum and its ES-3.0 invariants. `detectionEngine.test.ts:118-138` **reads `plugins/kotlin/WardenEngineBench.kt` from disk** and asserts `BENCH_MODES` stays in lockstep with the TS `BenchMode` union. Both are AC-mandated guards from 12.2, not incidental tests — **retire or re-point them deliberately and say which** (AC9).
6. **🔴 The plugin hard-codes class names inside REGEXES, in four places — not just in the file list.** All of them strip-and-re-emit against a **reused** `android/` tree, and a regex that stops matching fails **silently**, leaving stale generated code that still compiles:
   - [`:160`](../../apps/mobile/plugins/with-detection-engine.js#L160) — the stale-file sweeper, `/^Warden(DetectionEngine|Engine|GlUtil|RulePacker|CpuBaseline|KeyframeDecoder).*\.kt$/`. **This is what actually deletes sources you drop from `KOTLIN_FILES`** ([:111-121](../../apps/mobile/plugins/with-detection-engine.js#L111)). Drop a file but leave the regex unable to match its name and the orphan survives prebuild.
   - [`:273`](../../apps/mobile/plugins/with-detection-engine.js#L273) — the half-written-overlay guard, which **throws** on a `Story 12.2` comment with no matching `WardenEngineBenchActivity"` `/>`.
   - [`:283`](../../apps/mobile/plugins/with-detection-engine.js#L283) — the debug-manifest strip, keyed on `WardenEngineBenchActivity"`.
   - [`:331`](../../apps/mobile/plugins/with-detection-engine.js#L331) — the `MainApplication.kt` strip, keyed on `add\(WardenDetectionEnginePackage\(\)\)`.

   **Any rename must change the Kotlin and the regex in the same edit.** The file's own review comments ([:324-329](../../apps/mobile/plugins/with-detection-engine.js#L324)) document this as shipped bug #2: the mod is idempotent by **replacement**, not by presence, precisely because `if (xml.includes(...)) return` once meant a later *fix* silently never reached the APK. **Preserve that discipline, and verify by prebuild against a reused tree — a clean prebuild cannot catch any of these four.**

   *(Confirmed by exhaustive sweep at create-story: outside `plugins/kotlin/` and the generated `android/` tree, the **entire** blast radius of the GLES removal is six locations — `MainApplication.kt:29`, `debug/AndroidManifest.xml:9,11`, the plugin, `detectionEngine.ts`, and its two test files. **No feature module, no `docs/`, no `contracts/`, no `packages/` file references any `Warden*` class** — AC18b's sole-access invariant held in practice.)*

---

## Acceptance Criteria

### AC0 — Kickoff decisions (resolve BEFORE Task 3; record verdicts in the Dev Agent Record)

- [x] **AC0a — Where the CPU YUV→BGRA conversion lives.** Options: a new `WardenColorConvert.kt` (**RECOMMENDED** — a pure object, testable, mirrors `WardenCpuBaseline`'s shape and keeps the 141-line evaluator focused); inside `WardenKeyframeDecoder.imageToKeyframe()` (fewer files, but welds colour policy to the decoder); or inside `WardenCpuBaseline` (welds it to the evaluator, and the evaluator's 0-disagreement validation is a property you do not want to perturb). Record the choice and why.
- [x] **AC0b — Full-frame conversion vs rule-region-only.** The shipped rects are **1–25 px, fourteen of them 1×1** — ~800 texels of a 2,073,600-pixel frame. Converting the whole frame costs ~2 M pixel conversions per keyframe to read ~800 of them. **Converting only the rule rects is ~2600× less work** and is available precisely because there is no longer a shader that needs a whole texture. **Recommended: rule-region-only**, with `evaluate` fed per-rect, *provided* it produces bit-identical fire bits. **Costs:** it changes `WardenCpuBaseline.evaluate`'s contract (today: whole `bgra` frame + rect offsets), which is the function validated at 0 disagreements — so AC3 must re-prove parity, not inherit it. **If you take the whole-frame route, say so and record the measured cost**; PERF-002 has ~176 s of unused budget, so this is a legitimate choice, not a forced one. *(Note `MAX_RECT_TEXELS = 4096` caps the inner loop at [`WardenCpuBaseline.kt:109`](../../apps/mobile/plugins/kotlin/WardenCpuBaseline.kt#L109) while `ratio` divides by full `area` — latent for rects > 4096 px, unreachable on the shipped config. Do not silently change this; it is mirrored in the shader and in `lut.py`.)*
- [x] **AC0c — What survives of `WardenEngineBench.kt`.** It is **1176 lines** and roughly half is GL. **The parity instrument MUST survive in some form** (AC3, AC4) — today `parityRun` ([:187-241](../../apps/mobile/plugins/kotlin/WardenEngineBench.kt#L187)) builds a `WardenDetectionEngine`, i.e. it is GPU-based. Decide: re-point `parityRun` at the CPU arm (**RECOMMENDED**), or extract a minimal parity harness. Also decide the fate of `cpugpu` (its GPU half has no arm left), `framediff`, `pngdump`, `forcedCompletionProfile`, and `deviceProfile`'s GL strings. **Keep `flushprobe`, `seektest` and `timing`** — 12.4a needs them and 12.4d re-uses them.
- [x] **AC0d — `describeDevice()` and the `ffmpeg-kit` coordinate.** (i) [`WardenDetectionEngineModule.kt:74-83`](../../apps/mobile/plugins/kotlin/WardenDetectionEngineModule.kt#L74) calls `WardenEglContext.createOffscreen()` — it **cannot survive** GLES removal as written. Re-point it at a GL-free device profile (model / SoC / API level / codec), or drop the method; `detectionEngine.ts` and its tests follow. (ii) **SEC-007 entry 5a** — `ffmpeg-kit-main-16kb:6.1.4`, injected at [`with-detection-engine.js:375-414`](../../apps/mobile/plugins/with-detection-engine.js#L375), exists **only** for AC0b Option C's software-decode control. [architecture.md](../architecture.md) says *"Story 12.4 drops the re-declaration when it removes the bench surface; if it turns out to have a consumer, this entry stays as written."* **Check for a consumer, then act.** Note the same coordinate still reaches the APK transitively via entry 1 (`@wokcito/ffmpeg-kit-react-native`), so nothing ships differently either way.

### The substitution — do this BEFORE any deletion

- [x] **AC1 — A CPU YUV→BGRA converter exists, with the bt709 limited-range constants ported verbatim.** Per AC0a/AC0b. Source of truth: [`WardenDetectionEngine.kt:946-978`](../../apps/mobile/plugins/kotlin/WardenDetectionEngine.kt#L946) (`RESOLVE_YUV_FRAG`) and its exhaustive offline proof `ac3_numpy_{reference.py,constants.json}`. **Nearest-neighbour chroma** (trap 2). Handles **both NV12 and NV21 semi-planar orders explicitly, plus fully-planar I420** (trap 3), and **asserts geometry rather than rescaling** (trap 4).
- [x] **AC2 — The converter is proved against the exhaustive offline reference, not just against the device.** Re-use `ac3_numpy_reference.py verify-constants`' method: the port must reproduce the pinned constants' behaviour. A unit-level check over a generated triple sweep is acceptable and preferable to a device round-trip for this AC. **State the domain covered and the max error.** (The shader's bound was *1 unit on green over 0.179% of the 2²⁴ domain*.)
- [x] **AC3 — 🔴 THE GATE: the full CPU path reproduces 0 per-rule disagreements against the pinned PC reference.** **⚠️ AMENDED BY REVIEW 2026-09-17 (Stephane):** as worded, this is not runnable (the parity corpus is PNGs), and what closed it is: **(A)** the CPU evaluator over the PNG corpus vs `pc_reference_fires.json` (0 / 357,244). This half does *not* exercise the colour port. **(B)** MediaCodec → CPU colour → evaluator vs the GPU arm on the full capture (0 / 142,174). Together with AC2's exhaustive sweep, these prove the port. No run has compared the video path against an *independent PC* reference; that oracle is carried to **Story 12.4c**. The AC3(B) harness was never committed (see REPORT §8). Original wording follows. MediaCodec → CPU colour → `WardenCpuBaseline.evaluate` over the parity corpus, compared to `apps/mobile/bench/12-2/pc_reference_fires.json` (2666 frames). Banked baseline: **0 disagreements / 357,244 decisions** (`parity_comparison.json`). **This is the first time the bound configuration has ever been run end to end** — the `[P]` label exists because of this gap, and this AC closes it. **If it is not zero, STOP and fix before deleting anything.** A non-zero result here with the GPU still present is a debuggable situation; the same result after deletion is not.
- [x] **AC4 — 🔴 Do not delete the GPU arm until AC3 is green.** Explicit sequencing AC, not ceremony. Until AC3 passes, `WardenDetectionEngine.kt` is your **reference implementation** — it is the thing validated at 0 disagreements on this device, and it is the only A/B you have. Record in the Dev Agent Record that AC3 passed **before** the deletion commit/step.

### The removal

- [x] **AC5 — The GLES/EGL Kotlin surface is gone.** Delete: **`WardenGlUtil.kt`** (219 lines — `WardenGlException`, `WardenGlUtil`, `WardenEglContext`) · **`WardenDetectionEngine.kt`** (981 lines, entire) · **`WardenSurfaceTextureHost`** ([`WardenKeyframeDecoder.kt:818-918`](../../apps/mobile/plugins/kotlin/WardenKeyframeDecoder.kt#L818)) and with it the `toSurface: Surface?` constructor param ([:73](../../apps/mobile/plugins/kotlin/WardenKeyframeDecoder.kt#L73)) and every `toSurface != null` branch (`:337`, `:557-565`, `:694-701`) · **`WardenRulePacker.decodeResults`** ([:380-385](../../apps/mobile/plugins/kotlin/WardenRulePacker.kt#L380), the RGBA8 GPU-readback decoder). The GL surface in `WardenEngineBench.kt` per AC0c (inventory: `:6`, `:48-51`, `:65-130`, `:187-241`, `:249-346`, GPU half of `:352-442`, `:480-554`, `:641-642`, `:649-720`, `:721-805`, `:882-899`, `:936-938`, `:1095`, `:1105-1109`).
  **🔴 Path P — `COLOR_FormatYUV420Flexible`, `configureCodec` ([:592-606](../../apps/mobile/plugins/kotlin/WardenKeyframeDecoder.kt#L592)) and `imageToKeyframe` ([:766-785](../../apps/mobile/plugins/kotlin/WardenKeyframeDecoder.kt#L766)) — is what the CPU arm needs. Keep it.**
- [x] **AC6 — The shader asset and its emission are gone; Tool 12's `.frag` is NOT.** Remove the `keyframe_engine_bench.frag` emission from [`with-detection-engine.js:63-101, :167-178`](../../apps/mobile/plugins/with-detection-engine.js#L63) (`FRAG_RELATIVE_PATH`, `FRAG_SHA256`, `readVerbatimFrag`, the assets write) and the generated `android/app/src/main/assets/` copy. **🔴 `apps/tooling/tools/keyframe_engine_bench/keyframe_engine_bench.frag` is the tooling source of truth for Tool 12 — Story 12.1 is `done`, Tool 12 is the PC bench, and Story 9.16 re-points the testers. DO NOT DELETE IT.** You are removing a *copy mechanism*, not a shader.
- [x] **AC7 — The plugin is consistent after the removal.** Prune `KOTLIN_FILES` ([:111-121](../../apps/mobile/plugins/with-detection-engine.js#L111)) **and** keep the stale-file sweeper regex at [:160](../../apps/mobile/plugins/with-detection-engine.js#L160) matching the dropped names (trap 6). Handle the `ffmpeg-kit` compile dep per AC0d(ii) and the debug bench activity per AC0c. **Verify by prebuild against a REUSED `android/` tree, not a clean one** — a clean prebuild cannot catch a sweeper regression, which is exactly the class of bug 12.2 hit.
- [x] **AC8 — `detectionEngine.ts`'s GL-shaped surface is narrowed.** The TS seam carries GL in its types: `EngineStageTimings.{upload_or_bind, resolve, shader, readback, gl_total, gl_share_of_wall}` ([:25-46](../../apps/mobile/src/shared/services/detectionEngine.ts#L25)), `EngineTimingResult.color_path` ([:49](../../apps/mobile/src/shared/services/detectionEngine.ts#L49)), `EngineDeviceProfile.{gl, ac2_oes_essl3}` ([:79-83](../../apps/mobile/src/shared/services/detectionEngine.ts#L79)), `ac11_one_off_egl_context_ms` ([:95](../../apps/mobile/src/shared/services/detectionEngine.ts#L95)), and GLES prose at `:15-17`, `:149`. Narrow the types and the prose to match what the native side now reports. **This is a type/shape narrowing only — do NOT add the production detection API here; that is 12.4c's** (AC12).
- [x] **AC9 — The two guard tests are deliberately disposed.** Per trap 5. `detectionEnginePlugin.test.ts` (shader checksum + ES-3.0 invariants) has no subject left — **delete it, and say so**, rather than leaving a green test asserting a file that is gone. `detectionEngine.test.ts`'s `BENCH_MODES` lockstep check ([:118-138](../../apps/mobile/src/shared/services/__tests__/detectionEngine.test.ts#L118)) **must be re-pointed, not deleted** — it is a genuine cross-language contract guard and it is more valuable after this story, not less. Update the expected mode list to AC0c's outcome.

### Architecture cascade

- [x] **AC10 — SEC-007 entry 5 narrows; entry 5a is resolved.** [architecture.md](../architecture.md) → *SEC-007 third-party SDK allowlist*. Entry 5 currently names `GLES30`/`EGL14`/`SurfaceTexture` **as pending removal** — *"they are still present in the emitted sources today, which is why this entry names them as pending removal rather than omitting them."* **That sentence becomes false when you land this story. Rewrite entry 5 to the bound surface: `android.media.MediaCodec` + `android.media.MediaExtractor` + a plain Kotlin integer rule evaluator and colour converter.** Entry 5a per AC0d(ii). ⚠️ **Nothing here widens a permission surface** — GLES/EGL require none, and there is no `<uses-feature android:glEsVersion>` in the tree to remove (verified). Do not invent one to delete.
- [x] **AC11 — The architecture's own "pending removal" pointers are closed.** At minimum: [Decision #13](../architecture.md) → *Implementation* (*"the GLES/EGL sources are removed by Story 12.4, not here"*); the **[INVARIANT: native-modules-only-via-shared-services]** amendment (*"the GLES/EGL surface is removed by Story 12.4"*); and [`architecture-spike-gpu-megashader.md`](../architecture-spike-gpu-megashader.md) → *What this does NOT bind* (*"This spike removes no code… their physical removal… is Story 12.4's"*) and its *Follow-up work required* row. **Each says "Story 12.4 will"; make each say what happened.** *(Amendment **5c does NOT lapse** — MediaCodec keeps decode Android-only with or without GLES. It is **re-scoped, not reverted**. Do not "finish the job" by reverting it; [architecture.md](../architecture.md) → *iOS Phase 2 deferral* explains why at length.)*
- [x] **AC12 — `docs/architecture-mobile.md`'s native-module table is corrected while you are in it.** It currently lists **four** modules and describes `opencv.ts` as *"**Stub.** `loadFrameFromPath` throws"* — **that is stale**: [`opencv.ts:412-492`](../../apps/mobile/src/shared/services/opencv.ts#L412) is a fully implemented `react-native-fast-opencv` JSI call. Add the detection engine as the fifth module and fix the OpenCV row. **Fix only these two facts** — the broader pHash→ROI/HSV prose sweep is **Story 9.10's** and the OpenCV *retirement* decision is **12.4c's**.

### Fences, gates, delivery

- [x] **AC13 — Scope fence.** 12.4b does **NOT**: rewrite `gameDetector.ts` / `mapIdentifier.ts` / `blackScreenDetector.ts` / `segmentation.ts` / `processingPipeline.ts` (**12.4c's**) · add a production detection API to the native module or `detectionEngine.ts` (**12.4c's**) · bundle or load `map_config` on device (**12.4c's**) · re-touch the decode loop's timeout/flush/index (**12.4a's** — inherit them) · re-measure PERF-002 end to end (**12.4d's**) · resolve rung-0 or retire rung 3 (**12.4d's**) · delete Tool 12 or its `.frag` (**12.1 is `done`; 9.16 re-points the testers**) · touch `map_config*`, zone data or `contracts/` · bump `schema_version` (**E1**) · run the exhaustive pHash prose sweep (**9.10's**).
- [x] **AC14 — Gates green.** `pnpm typecheck && pnpm test && pnpm format:check` from the repo root. **Re-verify the baseline first.** Post-12.3 state: mobile jest **20 suites / 161 passed + 10 todo**; tooling pytest **305**; root typecheck **3 errors, all `web` (pre-existing)**; web vitest **flaky, not merely red** (134/191 then 132/193 on the *identical* tree — its count cannot be a regression signal at ±2); `format:check` clean. **🔴 Note `format:check` does NOT cover `_bmad-output/`** — `.prettierignore` excludes it, so a green run says nothing about story-file edits. **This story legitimately MOVES the jest numbers** (AC9 removes 4 tests and edits another) — that is expected, and the Dev Agent Record must state the new baseline explicitly so 12.4c does not read it as a regression.
- [x] **AC15 — Committed to `main`.** Direct to `main`, no branch, no PR ([[project_warden_main_branch_workflow]]); lowercase subject; scope `mobile`. `main` is **not** auto-pushed. `sprint-status.yaml` rides in the same commit; check `git status` for foreign edits first ([[project_warden_shared_doc_commit_boundary]]).
- [x] **AC16 — `sprint-status.yaml`: `12-4b-…` `in-progress → review`**, and `12-4c-…` `backlog → ready-for-dev`. Record in the entry comment: AC3's parity result (the first end-to-end run of the bound configuration), the new jest baseline, and what survived of the bench.

---

## Tasks / Subtasks

- [x] **Task 1 — Read the colour evidence.** (AC: 1, 2) [12.2 REPORT §6](../../apps/mobile/bench/12-2/REPORT.md) (*AC3 — colour*, and *Two silent colour bugs found and fixed*); `ac3_numpy_reference.py`; `RESOLVE_YUV_FRAG` at [`WardenDetectionEngine.kt:946-978`](../../apps/mobile/plugins/kotlin/WardenDetectionEngine.kt#L946); `imageToKeyframe` at [`WardenKeyframeDecoder.kt:766-785`](../../apps/mobile/plugins/kotlin/WardenKeyframeDecoder.kt#L766).
- [x] **Task 2 — Re-establish the parity baseline on device** with the GPU arm still present. You need a green `parityRun` to compare against. (AC: 3)
- [x] **Task 3 — Resolve AC0.** (AC: 0a–0d) Record all four verdicts before writing code.
- [x] **Task 4 — Write the CPU converter.** (AC: 1, 2) Constants verbatim · nearest chroma · NV12 **and** NV21 **and** I420 · geometry assertion · offline constants check.
- [x] **Task 5 — 🔴 THE GATE.** (AC: 3, 4) Run MediaCodec → CPU colour → `WardenCpuBaseline` over the 2666-frame corpus. **0 disagreements, or stop.** Record that this passed before proceeding to Task 6.
- [x] **Task 6 — Delete.** (AC: 5, 6, 7) Kotlin files → bench GL → asset emission → plugin `KOTLIN_FILES` + sweeper regex. **Prebuild against a reused `android/` tree** and confirm no orphaned `Warden*.kt` survives.
- [x] **Task 7 — TS narrowing + test disposal.** (AC: 8, 9)
- [x] **Task 8 — Architecture cascade.** (AC: 10, 11, 12) Turn every *"Story 12.4 will remove"* into a statement of what happened.
- [x] **Task 9 — Deliver.** (AC: 13–16) Fence check → gates → commit → sprint-status.

### Review Findings

`/bmad-code-review` 2026-09-17 against `61cdd8a`, code-only diff (Kotlin + plugin + TS + `ac3_numpy_reference.py`; bench JSON/REPORT/docs checked by the auditor only). Layers: Blind Hunter, Edge Case Hunter, Acceptance Auditor. Auditor re-ran the gates: jest 20 suites / 166 + 10 todo, format clean, typecheck = the 3 pre-existing web errors. Constants, nearest chroma, deletions, generated tree, AC4 sequencing and the AC2/AC3 numbers all verified.

- [x] [Review][Decision] **RESOLVED 2026-09-17 → (a)** (Stephane): AC3 amended in place, REPORT §8 corrected, PC video oracle carried to 12.4c. AC3 is ticked `[x]`, but the gate that ran is not the one AC3 describes. AC3 says: MediaCodec → CPU colour → evaluate, compared to `pc_reference_fires.json`. That corpus is PNGs, so no MediaCodec is involved.
  - AC3(A) ran PNG → `evaluate(bgra)`. That path never touches the new YUV converter, so it proves nothing about the port.
  - AC3(B) compared the CPU arm against the GPU arm, and §4.1 found a real defect in that GPU arm.
  - The CPU colour path is therefore proven by AC2 (all 2²⁴ triples) plus AC3(B), but never against a PC reference on video.
  - The harness behind AC3(B) (`cpuColorParity` / the `cpucolor` mode) was never committed: `git log -S cpuColorParity` only finds a comment in `61cdd8a`. REPORT §8's "restore from history" recovery therefore cannot rebuild it.
  - Options: (a) amend the AC3 wording to what actually ran, keep `[x]`, and fix REPORT §8; (b) demote to `[ ]` until a PC-side video reference (numpy YUV → fires over the capture) is produced and compared.
- [x] [Review][Patch] `timingRun` samples the chroma layout on every frame, inside the engine timer. `nFrames` is only assigned after the decode call returns, so `nFrames == 0` is always true inside `body`. As a result `engineNs` includes `layoutName()` and the label comes from the last frame, not the first. [apps/mobile/plugins/kotlin/WardenEngineBench.kt:471]
- [x] [Review][Patch] `decode_excluding_engine` subtracts the engine time of all N frames, but by the code's own comment `decodeNs` only nests frames 0..N-2. Subtract the last frame's engine time separately. [apps/mobile/plugins/kotlin/WardenEngineBench.kt:521]
- [x] [Review][Patch] The `layoutName()` "NV12 observed" label is unsupported. It compares byte values across buffers that were already copied, which is true for any layout on flat chroma, and it was sampled on pts 0, which is black. Decide the layout in `imageToKeyframe` from the original `Image` planes (buffer overlap) before copying, and correct the record's "observed" claim. [apps/mobile/plugins/kotlin/WardenColorConvert.kt:271]
- [x] [Review][Patch] The geometry assertion is optional on the production entry point. `evaluateYuv(frame, packed)` never checks the frame size against the packing size, and 12.4c is told to call it without `requireGeometry`. Assert it inside `evaluateYuv`. [apps/mobile/plugins/kotlin/WardenCpuBaseline.kt:113]
- [x] [Review][Patch] `requireSpans` checks `capacity()`, but absolute `get(i)` is bounded by `limit()`. Check `limit()` instead, and reject a non-zero `position()`. [apps/mobile/plugins/kotlin/WardenColorConvert.kt:187]
- [x] [Review][Patch] `imageToKeyframe` never checks `img.format`. A 10-bit stream (P010) would be read as 8-bit garbage with no error. This is now the only colour path, so assert `ImageFormat.YUV_420_888`. [apps/mobile/plugins/kotlin/WardenKeyframeDecoder.kt:1111]
- [x] [Review][Patch] Zero-frame runs report as valid. `timingRun` with 0 keyframes passes `keyframe_count_matches` (0 == 0), and `evaluateBitmapCpu` returns `cpu_ms_per_frame = 0` after its wrong-geometry and alpha `Log.w` diagnostics were deleted. Require `nFrames > 0` and restore the logs. [apps/mobile/plugins/kotlin/WardenEngineBench.kt:505]
- [x] [Review][Patch] `colorConstantsCheck` is documented as costing "about a second" (KDoc, the dispatch comment, the Dev Record). It measured 11.7–24.2 s (`total_ms` in three reports), at full CPU, in every mode, before the timed runs. Correct the claims. Also consider skipping it in `flushprobe` and `seektest`, which never use colour. [apps/mobile/plugins/kotlin/WardenEngineBench.kt:833]
- [x] [Review][Patch] Stale 12.2/GPU residue:
  - `report.put("story", "12.2")`.
  - The `WardenKeyframe` KDoc says planes are "Never null", but the type is still nullable (`?` and `= null`). Make it non-null and drop the `!!`.
  - EGL/GPU wording remains in `WardenEngineBenchActivity.kt:28,46-47`, along with a dead `cpuFrames` param/default (also in TS).
  - The plugin comments that the strip regexes key on stay, but record why.
  
  [apps/mobile/plugins/kotlin/WardenEngineBench.kt:778]
- [x] [Review][Patch] `architecture.md:2140` still says "physical removal … is Story 12.4's, not this story's", which AC11 said to rewrite. [_bmad-output/architecture.md:2140]
- [x] [Review][Patch] `verify_shader_transcription` silently passes when `WardenEngineBench.kt` is missing, while a missing converter source is treated as fatal. Make both fatal. [apps/mobile/bench/12-2/ac3_numpy_reference.py:344]
- [x] [Review][Patch] Dev Record and REPORT inaccuracies:
  - `describeDevice` did not gain a `mediacodec_decoder` block: the pre-existing block is `mediacodec`, and `deviceProfile(null)` omits it.
  - "Three modes retired" should be two on `main`, since `cpucolor` was never committed.
  - `WardenKeyframeDecoder` is 1279 lines, not 1268. The deleted plugin test was 69 lines, not 63.
  - The AC14 gate chain short-circuits on the pre-existing web typecheck failure.
  - The `evaluateBitmapCpu` KDoc says timing is "comparable to 0.376 ms/frame", but it measured 1.255 ms/frame and nobody explains the gap.
  
  [_bmad-output/implementation-artifacts/12-4b-cpu-colour-port-and-gles-removal.md]
- [x] [Review][Defer] The crop rect is ignored and geometry comes from `img.width/height`. This is pre-existing Path P behaviour, but it is now the only path: a 1920×1088 coded buffer fails `requireGeometry`, and a crop with a non-zero origin shifts every rule silently. [apps/mobile/plugins/kotlin/WardenKeyframeDecoder.kt:1118] — deferred, pre-existing (12.4c)
- [x] [Review][Defer] The A′ single-pass loop can busy-spin on repeated `-2`/`-3` with no spin cap, while the pipelined loop has an `else` guard. [apps/mobile/plugins/kotlin/WardenKeyframeDecoder.kt:1053] — deferred, pre-existing
- [x] [Review][Defer] In the bound loop, an EOS flag on a data-bearing output is ignored. It ends in the 5 s "no output" throw instead of the precise dropped-keyframe message. [apps/mobile/plugins/kotlin/WardenKeyframeDecoder.kt:686] — deferred, pre-existing
- [x] [Review][Defer] Odd width/height is rejected with a misleading "short plane" error: chroma span rounds up, but the codec plane limit rounds down. Not reachable at 1920×1080. [apps/mobile/plugins/kotlin/WardenColorConvert.kt:161] — deferred, off the bound path
- [x] [Review][Defer] NV21/I420 handling has no fixture. Only NV12 has run on device, and the TS tests only pattern-match source. [apps/mobile/plugins/kotlin/WardenColorConvert.kt] — deferred, needs fixture/device
- [x] [Review][Defer] The shipped CPU-only `parityRun` has never run over the corpus post-deletion. AC3(A) numbers come from the pre-deletion both-arms build. [apps/mobile/bench/12-4b/report_parity_both_arms.json] — deferred, epic-end device pass
- [x] [Review][Defer] Source-regex guards are weak:
  - The nearest-chroma regex passes `(c0+c1)/2` style bilinear code.
  - The `requireGeometry` test only checks that the text exists.
  - The constant regex accepts `1.5748e0`.
  - Nothing re-derives `REFERENCE_YUV_SWEEP_SHA256` from `shader_model`.
  - The sweeper regex duplicates `KOTLIN_FILES` by hand.
  
  [apps/mobile/src/shared/services/__tests__/colorConvert.test.ts] — deferred, test hardening

**Patches applied 2026-09-17 (all 12, plus the AC3 resolution). How three of them differ from the finding text:**

- **Layout label.** Classifying in `imageToKeyframe` from shared memory is not possible: `android.media.Image` exposes no public way to see that two planes share memory, and the planes are copied anyway. Instead, `layoutName()` now tests the interleaving over the **whole** chroma span and returns `LAYOUT_INDETERMINATE` when both orders fit (flat chroma). `timingRun` keeps sampling, outside the engine timer, until a frame discriminates.
- **Geometry.** `WardenPackedRules` now carries `frameWidth`/`frameHeight` from `packRules`, and `evaluateYuv` calls `requireGeometry` itself. `timingRun`'s separate call was dropped. `frameDiffDump` keeps its call because it never calls `evaluateYuv`.
- **Kept on purpose.**
  - `cpuFrames` stays: it is already documented in `runAll` as a positional-arity hazard that 12.4c removes.
  - The plugin's "GPU engine" marker strings stay: they are the replace-by-marker anchors for reused `android/` trees, and a comment now says so.

**Other changes:**
- `WardenKeyframe`'s planes and strides are now non-null.
- `imageToKeyframe` refuses any format other than `YUV_420_888`.
- `requireSpans` checks `limit()` and requires position 0.
- Zero-frame `timingRun` and `parityRun` now throw.
- The PNG skip and alpha warnings are restored.
- `decode_excluding_engine` now subtracts N-1 frames.
- `colorConstantsCheck` skips `flushprobe`/`seektest`, and its cost is corrected everywhere.
- `story` is `12.4b`.
- `ac3_numpy_reference.py` now fails when the bench file is missing.
- `architecture.md:2140` is rewritten.
- REPORT §8 now says the `cpucolor` harness cannot be restored.
- The record's inaccuracies are annotated in place.

**Gates after the patches:**
- mobile jest: 20 suites / **166 passed** + 10 todo (unchanged).
- `format:check`: clean.
- `verify-constants`: transcription still matches.
- `:app:compileDebugKotlin` against the reused `android/` tree, with the patched sources copied in: **green**.

**⚠️ Not re-run on device.** The changed bench paths (layout sampling, zero-frame checks, the `decode_excluding_engine` formula, colour-check gating) and the new `YUV_420_888` guard are left for the epic-end device pass, per [[feedback_batch_manual_checks_epic_end]]. `WardenColorConvert.bgrAt` and the rule arithmetic are unchanged, so the banked parity figures still describe the evaluator.

---

## Dev Notes

### Removal inventory (verified against the tracked sources, 2026-09-17)

The Kotlin exists in **two byte-identical copies**. **`apps/mobile/plugins/kotlin/*.kt` is the tracked source of truth**; `apps/mobile/android/app/src/main/java/team/warden/mobile/*.kt` is a **gitignored** build artifact regenerated at prebuild. **Edit the tracked copy only** — an edit under `android/` is silently discarded.

| File | Lines | Disposition |
|---|---|---|
| `WardenGlUtil.kt` | 219 | **DELETE** — EGL 1.4 + GLES 3.0 plumbing; `WardenEglContext.createOffscreen` (pbuffer, `EGL_CONTEXT_CLIENT_VERSION 3`) |
| `WardenDetectionEngine.kt` | 981 | **DELETE** — the mega-shader engine, both colour paths, FBOs, `glReadPixels`, the self-test |
| `WardenCpuBaseline.kt` | 141 | **KEEP + PROMOTE** — the bound evaluator |
| `WardenRulePacker.kt` | 386 | **KEEP**, minus `decodeResults` (`:380-385`) |
| `WardenKeyframeDecoder.kt` | 918 | **KEEP**, minus `WardenSurfaceTextureHost` (`:818-918`) and the `toSurface` branches |
| `WardenEngineBench.kt` | 1176 | **AMPUTATE** per AC0c — keep `lutCrossCheck` (`:143-185`, no GL), `flushprobe`, `seektest`, `timing`; re-point `parityRun` |
| `WardenDetectionEngineModule.kt` | 96 | **EDIT** — `describeDevice` uses EGL (`:74-83`) |
| `WardenDetectionEnginePackage.kt` | 21 | keep |
| `WardenEngineBenchActivity.kt` | 86 | keep/trim per AC0c |

**Inline GLSL lives in Kotlin string constants, not files** — `ES_VERSION` (`:825`), `OES_ESSL3_EXTENSION` (`:837`), `RULES_PROBE_FRAG` (`:847-877`), `VERT_BODY` (`:880-889`), `RESOLVE_OES_FRAG` (`:895-928`), `RESOLVE_YUV_FRAG` (`:946-978`). All go with the file. **The only external shader is Tool 12's `.frag` — AC6 protects it.**

**There is no `<uses-feature android:glEsVersion>` and no GLES-related permission in the tree.** Verified. The main manifest's permissions (FOREGROUND_SERVICE, DATA_SYNC, INTERNET, POST_NOTIFICATIONS, READ/WRITE_EXTERNAL_STORAGE, SYSTEM_ALERT_WINDOW, VIBRATE) are Story 1.2's and unrelated. **Leave them alone.**

**Story 1.2's `WardenProcessing*.kt`** (foreground service) are emitted by a *different* plugin (`with-foreground-service.js`, string templates, no `kotlin/` dir). **Untouched by this story.**

### Why removing this is free, and why it is worth doing

From [Decision #13](../architecture.md): *"Rejecting it removes an architectural surface at no measured cost — no EGL context to own and make current, no GL thread-affinity constraint, no LUT texture upload, no readback synchronisation, and no **driver-defined, AOSP-unspecified** colour conversion."*

The last one is the substantive win. Path Z's zero-copy OES conversion diverged from bit-parity on **0.888%** of decisions across **59.9%** of keyframes and **95 of 134** rules — **including 44 of the 69 low-saturation rules**, exactly where the accepted `h_tol = 180` tuning is most fragile ([[project_warden_low_sat_hue_unconstrained]]). That divergence is driver-defined, so it is not merely imperfect but **unpredictable across devices**. **Option A reached the same colour behaviour by removing the choice instead of making it** — and this story is where the removal actually happens.

There is also a measured cost *saving*: Path P's **disjoint GL stages were 3.068 ms of 42.299 ms/kf (7.3%)**. Removing them and adding back the CPU arm's **0.376 ms** is the arithmetic behind the `[P]` projection of 39.607 ms/kf. **12.4d measures whether that holds.**

### Testing standards

Mobile: **jest + jest-expo**, co-located `__tests__/<subject>.test.ts(x)` (Decision #ES-6). There are **no Kotlin unit or instrumented tests** in this repo — `android/app/src/` has no `test/` or `androidTest/`. All native verification is on-device via the bench plus the two disk-reading Jest guards. **That is the established pattern; this story is not the place to introduce a Kotlin test framework**, but if AC2's constants check is cheapest as a JVM-side check, say so and record it as a deviation.

### Fixtures and reproduction

| fixture | path |
|---|---|
| capture | `videos/V2/2026-04-27 22-05-34.mp4` — 1920×1080 h264 `yuv420p` **`color_range=tv`** `bt709` · 4419.633 s · 1061 keyframes |
| config | `apps/tooling/output/map_configs/map_config.v2.json` — 134 rules (10 hud / 3 in_match / 121 map / 13 maps) |
| parity corpus | `apps/tooling/output/labeled/v2/` — 2666 PNGs / 16 classes |
| PC reference (**tracked**) | `apps/mobile/bench/12-2/pc_reference_fires.json` |
| constants proof | `apps/mobile/bench/12-2/ac3_numpy_{reference.py,constants.json}` |

Staging (scoped storage — `/sdcard/<dir>` is **EACCES at targetSdk 36**; `adb push` of a *directory* fails, pre-create with `mkdir -p`): input `getExternalFilesDir(null)/warden12_2`, output `.../bench12_2`. Full sequence: [`apps/mobile/bench/12-2/REPORT.md` §10](../../apps/mobile/bench/12-2/REPORT.md).

### Project Structure Notes

- The native module is the **fifth** and is reached **only** via `apps/mobile/src/shared/services/detectionEngine.ts` ([INVARIANT: native-modules-only-via-shared-services](../architecture.md)). Grep confirms `detectionEngine.ts` + its two test files are the only touch points in `apps/mobile/src` — AC18b holds. **Do not breach it while narrowing.**
- The bridge is a **legacy `ReactPackage`, explicitly not a TurboModule** — no codegen spec exists anywhere in the repo ([`WardenDetectionEngineModule.kt:19-22`](../../apps/mobile/plugins/kotlin/WardenDetectionEngineModule.kt#L19)). Registered into `MainApplication.kt` by the plugin against the `// add(MyReactNativePackage())` anchor, which **throws on drift**. Same pattern as Story 1.2's FGS module ([[project_warden_fgs_mmkv_push]]).
- Both native methods return a **JSON string**, parsed JS-side.

### References

- [Source: _bmad-output/architecture.md#Decision-13] — what is bound / what is dropped; *Implementation* ("GLES/EGL sources are removed by Story 12.4"); *Cascading implications*
- [Source: _bmad-output/architecture.md#SEC-007] — entry 5 ("pending removal"), entry 5a (`ffmpeg-kit-main-16kb` re-declaration and its condition)
- [Source: _bmad-output/architecture.md#iOS-Phase-2-deferral] — amendment 5c is **re-scoped, not reverted**
- [Source: _bmad-output/architecture-spike-gpu-megashader.md] — *What is dropped*; *What this does NOT bind* ("this spike removes no code"); *Follow-up work required*; the Path Z / Path P divergence table
- [Source: apps/mobile/bench/12-2/REPORT.md] — §6 colour (ΔH/ΔS/ΔV, the two silent bugs, the exhaustive constants proof), §7 parity, §10 reproduce
- [Source: _bmad-output/implementation-artifacts/12-2-android-poc-gles-port.md] — the NV21 and geometry review findings; plugin idempotency-by-replacement
- [Source: _bmad-output/epics-and-stories.md#Epic-12] — E1 schema unchanged; E3 hue wraparound mandatory; E4 doubt is first-class

---

## Dev Agent Record

### Agent Model Used

`claude-opus-5[1m]` (Amelia, `/bmad-dev-story 12.4b`), 2026-09-17.

### AC0 — Kickoff verdicts (resolved before Task 4, per AC0's own instruction)

**AC0a — Where the CPU YUV→BGRA conversion lives: a NEW `WardenColorConvert.kt`** (the RECOMMENDED option).
A pure `object` plus a small `WardenYuvFrame` view over the decoder's three planes. Rationale: it mirrors
`WardenCpuBaseline`'s shape (a plain Kotlin object with no RN and no Android-graphics import), it is the only
option that leaves the 141-line evaluator's 0-disagreement validation unperturbed as a *file*, and it is the
only one that gives `ac3_numpy_reference.py`'s `verify-shader-transcription` a live Kotlin file to re-point at
once `WardenDetectionEngine.kt` is gone (see the finding under AC2). Welding it into `imageToKeyframe` was
rejected because it makes colour policy a property of the decoder, and the decoder is 12.4a's freshly-tuned
surface.

**AC0b — Rule-region-only** (the RECOMMENDED option). The converter is never asked for a whole frame on the
evaluation path: `WardenCpuBaseline.evaluateYuv` samples `bgrAt(x, y)` per rect texel, so the shipped config
converts **~800 pixels per keyframe instead of 2,073,600** (≈2,600× less work). Two consequences recorded
deliberately:
- It changes the evaluator's contract, so AC3 **re-proves** parity rather than inheriting it. `evaluate(bgra…)`
  is kept, byte-for-byte behaviour-identical, and both entry points now delegate to one private
  `evaluateWith(sampler)` — so the rule/HSV/ratio arithmetic that was validated at 0 disagreements is
  *the same code*, not a copy of it. AC3 (A) re-runs the full 2666-frame corpus through it to prove that.
- A **full-frame** converter (`convertFrameToBgra`) still exists, but only on the `framediff` diagnostic path,
  where dumping a whole converted frame for an off-device per-pixel diff is the entire point. It is not on any
  measured path.
- `MAX_RECT_TEXELS` / `area` left exactly as found (it is guarded at pack time by
  `WardenRulePacker:329`'s `require(area <= MAX_RECT_TEXELS)`, and it is mirrored in the `.frag` and `lut.py`).

**AC0c — What survives of `WardenEngineBench.kt`.** `parityRun` is **re-pointed at the CPU arm** (the
RECOMMENDED option) rather than replaced by a new harness. Mode-by-mode disposition:

| mode | fate | why |
|---|---|---|
| `parity` | **KEPT, re-pointed at `WardenCpuBaseline`** | AC3's instrument. Now also reports `cpu_ms_per_frame`, which is what `cpugpu` existed to produce. |
| `timing` | **KEPT** | mandated; 12.4a needs it, 12.4d re-uses it. Single path now (see AC8 note on the shrinking array). |
| `flushprobe` | **KEPT untouched** | mandated; `decodeProbe`/`flushOnlyProbe` keep their `flush()` — they are the A/B instruments. |
| `seektest` | **KEPT untouched** | mandated. |
| `framediff` | **KEPT, re-pointed at `WardenColorConvert.convertFrameToBgra`** | it is the only per-pixel colour evidence there is, and after the port it is evidence about the *shipped* converter instead of about a deleted shader. |
| `cpugpu` | **DROPPED** | its GPU half has no arm left; a mode named `cpugpu` that measures one arm is a lie. Its CPU number moved into `parity`. |
| `pngdump` | **DROPPED** | it dumped `engine.readFrameTexture()` for a 12.2-era 37% divergence hunt. Without GL it degrades to "write the PNG's own bytes back out", which the PC can do from the PNG. |
| `forcedCompletionProfile` | **DROPPED** | it exists solely to `glFinish()` past GL's async misattribution. CPU work is synchronous; the naive profile is now exact, which is stated in the report rather than left implied. |
| `threadingModel` | **DROPPED** | it reported EGL thread-affinity. AC16's finding is already banked in `architecture.md`; re-deriving it from a context that no longer exists is not possible. |
| `deviceProfile`'s GL strings | **DROPPED** (`gl`, `ac2_oes_essl3`) | see AC0d(i). Replaced by the MediaCodec/SoC facts that the bound path actually depends on. |
| `lutCrossCheck` | **KEPT untouched** | no GL in it. |
| `ffmpegKitControl` | **KEPT** | see AC0d(ii). |

`BENCH_MODES` therefore goes `{all, parity, cpugpu, timing, framediff, flushprobe, seektest, pngdump}` →
**`{all, parity, timing, framediff, flushprobe, seektest}`**, and `BenchMode` in `detectionEngine.ts` follows
(AC9 — that lockstep test is the thing that makes this a contract rather than a coincidence).

**AC0d(i) — `describeDevice()`: RE-POINTED, not dropped.** It was the module's only GL-free-looking entry point
and it is the one 12.4c will want. `deviceProfile(egl, …)` loses its `WardenEglContext` parameter, its `gl`
block and its `ac2_oes_essl3` block; it gains an `engine` block (CPU kind / colour conversion / `gpu_used: false`).
*(Review 2026-09-17 correction: an earlier draft said it gained `mediacodec_decoder`. The decoder block is the
PRE-EXISTING `mediacodec` key, and `describeDevice()` calls `deviceProfile(null)`, so the bridge never returns it.)* The RN bridge
no longer creates or releases an EGL context to answer it. `EngineDeviceProfile` in `detectionEngine.ts` is
narrowed to match (AC8).

**AC0d(ii) — SEC-007 entry 5a (`ffmpeg-kit-main-16kb:6.1.4`): STAYS AS WRITTEN. It HAS a consumer.**
[architecture.md](../architecture.md)'s condition is explicit — *"Story 12.4 drops the re-declaration when it
removes the bench surface; if it turns out to have a consumer, this entry stays as written."* The consumer is
`WardenEngineBench.ffmpegKitControl`, reached from the `timing` mode, which AC0c **keeps** because 12.4d
re-uses it. The control is the software-decode comparator for the decode number 12.4a just moved by 5.45×, so
it is worth more after this story, not less. It touches no GL (it is a `Class.forName` reflection call). Also
as the story notes: the same coordinate reaches the APK transitively via entry 1 either way, so nothing ships
differently. **Entry 5a is resolved as KEPT, with the condition recorded as met** rather than left open.

### Debug Log References

| evidence | where |
|---|---|
| Full report — every measurement, the anomaly, the removal inventory | [`apps/mobile/bench/12-4b/REPORT.md`](../../apps/mobile/bench/12-4b/REPORT.md) |
| AC2 + AC3(B), full capture (the gate) | `bench/12-4b/report_cpucolor.json` |
| AC3(B) pixel-diff coordinate dump | `bench/12-4b/report_cpucolor_pixeldiag.json` |
| AC3(A) CPU arm vs pinned PC reference | `bench/12-4b/ac3a_cpu_parity_comparison.json`, `cpu_parity_fires.json` |
| Task 2 — GPU baseline re-established before any change | `bench/12-4b/task2_gpu_parity_comparison.json`, `gpu_parity_fires_baseline.json` |
| Post-deletion smoke run (GL-free bench) | `bench/12-4b/report_framediff.json` |

### Completion Notes List

**The substitution came first, and every gate was green before anything was deleted (AC4).**

**AC2 — the constants, proved exhaustively ON DEVICE.** All **16,777,216** (Y, Cb, Cr) triples run
through `WardenColorConvert` on the reference device and hashed: `4dd2da47…c34e27`, **bit-identical**
to `ac3_numpy_reference.shader_model`'s pinned digest. **Max error 0 over the entire domain** — the
shader's own bound was 1 unit on green over 0.179%.
- 🔴 **This is the only check that can catch a wrong OPERATOR.** A `+` where the shader has a `-`
  contains every expected literal and passes both offline checks. 12.2 found two silent colour bugs
  the hard way. *(Review 2026-09-17: "costs a second" was wrong — it measured 11.7-24.2 s of full CPU
  (`total_ms`). It now skips `flushprobe` and `seektest`, which never convert colour.)*
- **fp64, not fp32, and that is a decision.** Measured on PC over the full domain: fp32 and fp64
  disagree on **109 of 16,777,216 triples (0.00065%), max 1 unit** — **275× rarer** than the
  published-rounding error the BT.709 four-decimal constants already carry. fp64 makes the port
  bit-identical to the pinned reference instead of merely close, and AC0b makes it free.

**AC3 — THE GATE, both halves, both zero.**
- **(A)** CPU evaluator over the 2666-PNG corpus vs `pc_reference_fires.json`: **0 disagreements /
  357,244 decisions**, frame sets identical. The GPU arm's banked figure **re-earned, not inherited** —
  AC0b changed `evaluate`'s contract, so inheriting would have been unsound.
- **(B)** MediaCodec → CPU colour → `WardenCpuBaseline` vs MediaCodec → `RESOLVE_YUV_FRAG` →
  mega-shader → `glReadPixels`, on byte-identical decoder planes, **full 1061-keyframe capture**:
  **0 disagreements / 142,174 decisions**. CPU **0.651** vs GPU **2.855** ms/keyframe. Decoder layout
  pixelStride 2. *(Review 2026-09-17: the "NV12, observed" label was not evidence — a one-byte value
  test on the black pts-0 frame is true for NV12 and NV21 alike. `layoutName()` is now a whole-plane
  test that can answer "indeterminate", and `timingRun` keeps sampling until a frame discriminates.)*
- 🔴 **AC3 as literally worded is not runnable, and the Dev Agent Record says so rather than quietly
  substituting.** It asks for "MediaCodec → CPU colour → evaluate over the parity corpus, compared to
  `pc_reference_fires.json`". The parity corpus is **PNGs**; MediaCodec does not decode PNGs, and the
  PC reference fires were produced by `cv2.imread`. The two halves above are the decomposition 12.2's
  own design demands — *"the two failure modes must NOT be allowed to mask each other, which is
  exactly why this corpus does not go through the video path."* Together they are strictly stronger
  than the single run the AC describes.
- **This closes the `[P]` label's correctness half.** The performance half is 12.4d's.

**🔴 A REAL DEFECT FOUND IN THE ARM BEING DELETED.** The per-pixel diff (added because fire bits only
assert ~800 of 2,073,600 pixels) showed 4 pixels at delta 68/69. Located: `(1918..1919, 1078..1079)`
— the bottom-right 2×2 block, **chroma texel (959,539), the last one**. Inverting the conversion shows
the GPU read the correct Cb and **Cr = 0** where the true value is **128**: the zero byte one past the
U plane's mapped extent. **12.2's review identified exactly this byte and argued it away** ("it is the
frame's last Cr, and it belongs to the V plane, which starts at U+1 in the SAME buffer"). The
measurement says the argument was wrong — `u.get(1) == v.get(0)` samples the planes' *start* and says
nothing about one byte past their *end*. The CPU arm cannot have the bug: it reads Cr through the V
plane's own strides, which is correct for NV12, NV21 and I420 alike. **No rule rect reaches that
corner, which is why AC3(B) is still 0.** Recorded, not fixed — the file was deleted in this story.

**AC0b was a preference in the story and is a requirement in fact.** The `framediff` diagnostic
measures whole-frame conversion at **4228.9 ms — 4.23 s for one frame**. AC0b offered whole-frame as
legitimate because "PERF-002 has ~176 s of unused budget"; it is not — 1061 × 4.23 s ≈ **75 minutes**,
about **25× the entire budget**. Rule-region-only costs 0.651 ms/keyframe. Only a measurement could
say so, and it is recorded so 12.4c/12.4d do not re-derive the option from the story text.

**AC5–AC7 — the removal, verified on a REUSED tree.** ~1,200 lines of Kotlin plus the shader-asset
emission. After `expo prebuild` on a reused `android/`, the sweeper had removed the two orphaned
`.kt` files and a new sweep removed the stale `assets/keyframe_engine_bench.frag`; Story 1.2's
`WardenProcessing*.kt` untouched; APK built with **no errors and no warnings**; a `framediff` run on
device returned a clean report. The sweeper regex gained `ColorConvert` **in the same edit** as the
file (trap 6). **Tool 12's `.frag` is untouched** (AC6) and its ES-3.0 invariants are still gated — by
the tooling pytest suite, which is where a GLSL guard belongs now that no Kotlin reads that file.

**AC9 — the two guard tests, deliberately and differently disposed.**
- `detectionEnginePlugin.test.ts` **DELETED**: its subject was `readVerbatimFrag`, the shader-copy
  mechanism this story removes. Verified first that the tooling pytest suite independently gates the
  same ES-3.0 invariants over `read_frag_body()`, so nothing lost its only guard.
- `detectionEngine.test.ts`'s `BENCH_MODES` lockstep **RE-POINTED and EXTENDED**, per AC9's
  instruction. Three modes were retired, and a TS-only mode is the silent failure — it type-checks and
  returns a successful-looking report with no measurements. Added a named guard for each retired mode
  and a guard that the bench Kotlin contains no GL import, so the GPU arm cannot return without
  someone re-opening Decision #13.
- **New:** `colorConvert.test.ts` (6 tests) holds the Kotlin constants, the numpy transcription and the
  pinned device digest together in CI.

**🔴 A PYTHON-SIDE ANALOGUE OF TRAP 5 THAT THE STORY DID NOT NAME.**
`ac3_numpy_reference.py`'s `verify_shader_transcription()` read `WardenDetectionEngine.kt` **off disk**
— the file AC5 deletes. Left alone it would have raised `FileNotFoundError` on the one script that
proves the constants, at exactly the moment it became their only offline proof. `SHADER_PATH`
re-pointed at `WardenColorConvert.kt`, a missing-file branch added with an explanatory message, and
the device pin cross-checked from that side too.

**AC0d(ii) — SEC-007 entry 5a RESOLVED as RETAINED, not dropped.** The condition in `architecture.md`
is explicit: *"if it turns out to have a consumer, this entry stays as written."* Checked rather than
assumed — the consumer is `WardenEngineBench.ffmpegKitControl`, reached from the `timing` mode AC0c
keeps because 12.4d re-uses it. It touches no GL. Nothing ships differently either way.

**Inherited from 12.4a and honoured.** The last `flush()` outside the two bench instruments went with
the Surface path, as 12.4a predicted; `decodeProbe` and `flushOnlyProbe` keep theirs (their structure
is the A/B). `timing` no longer measures ZERO_COPY — `ac11_ac13_timing_naive` is a **one-element**
array now, and the report says so explicitly (`ac0c_paths_removed`) rather than letting it silently
shrink. Also took 12.4a's deferred `TIMEOUT_US` decision: **A′ keeps the shared timeout**, because A′
exists to be compared against A on the same frames and the delivered 32.937 / 62.820 pair was measured
with both polling identically.

**AC14 — gates, with the new baseline stated (AC14 required this).**
`pnpm typecheck && pnpm test && pnpm format:check` from the repo root. *(Review 2026-09-17: as a chain
this short-circuits at the pre-existing `web` typecheck failure. The figures below come from running
each step separately.)*
- mobile jest **20 suites / 166 passed + 10 todo** (was 20 / 162 + 10). The move is −4 (deleted plugin
  test) +6 (`colorConvert.test.ts`) +2 (new guards). **🔴 Story 12.4c's baseline is 166, not 162.**
- tooling pytest **305** — unchanged.
- root typecheck **3 errors, all `web`, pre-existing and unchanged**.
- `format:check` **clean**. Note it does not cover `_bmad-output/` (`.prettierignore`).

**Scope fence (AC13) held.** No TypeScript consumer rewrite, no production detection API, no
`map_config` on device, no decode-loop re-touch, no PERF-002 re-measurement, no ladder resolution, no
`contracts/` or zone-data changes, no `schema_version` bump, no pHash prose sweep, and Tool 12's
`.frag` untouched.

### File List

**Added**
- `apps/mobile/plugins/kotlin/WardenColorConvert.kt` — the CPU YUV→BGR converter + `WardenYuvFrame`
- `apps/mobile/src/shared/services/__tests__/colorConvert.test.ts` — the constants cross-language guard
- `apps/mobile/bench/12-4b/REPORT.md` + 9 measurement artifacts

**Deleted**
- `apps/mobile/plugins/kotlin/WardenDetectionEngine.kt` (981 lines)
- `apps/mobile/plugins/kotlin/WardenGlUtil.kt` (219 lines)
- `apps/mobile/src/shared/services/__tests__/detectionEnginePlugin.test.ts`

**Modified**
- `apps/mobile/plugins/kotlin/WardenCpuBaseline.kt` — `evaluateYuv` + shared `evaluateWith(sampler)`
- `apps/mobile/plugins/kotlin/WardenKeyframeDecoder.kt` — Surface path, `WardenSurfaceTextureHost` and the legacy flush loop removed (1461 → 1279 lines)
- `apps/mobile/plugins/kotlin/WardenRulePacker.kt` — `decodeResults` removed
- `apps/mobile/plugins/kotlin/WardenEngineBench.kt` — GL amputation; `colorConstantsCheck` added; `parityRun`/`frameDiffDump` re-pointed at the CPU arm
- `apps/mobile/plugins/kotlin/WardenDetectionEngineModule.kt` — `describeDevice` off EGL
- `apps/mobile/plugins/with-detection-engine.js` — `KOTLIN_FILES`, sweeper regex, shader-asset emission removed + stale-asset sweep
- `apps/mobile/src/shared/services/detectionEngine.ts` — GL-shaped types and prose narrowed
- `apps/mobile/src/shared/services/__tests__/detectionEngine.test.ts` — lockstep guard re-pointed + 2 new guards
- `apps/mobile/bench/12-2/ac3_numpy_reference.py` — transcription guard re-pointed; device digest pinned
- `_bmad-output/architecture.md` — SEC-007 entry 5 / 5a; Decision #13 Implementation; amendments 5d / 5g
- `_bmad-output/architecture-spike-gpu-megashader.md` — "removes no code", `[P]`, follow-up table, 12.4 row
- `docs/architecture-mobile.md` — OpenCV row corrected; detection engine added as the fifth module
- `_bmad-output/sprint-status.yaml`

### Change Log

| date | change |
|---|---|
| 2026-09-17 | Committed to `main` as **`61cdd8a`** (29 files, +2508 / -2280). `main` is not auto-pushed. |
| 2026-09-17 | Story 12.4b implemented. CPU colour port proved (AC2 exhaustive 2²⁴ on device; AC3(A) 0/357,244; AC3(B) 0/142,174 over the full capture), then the GLES/EGL surface removed (~1,200 lines). Found and recorded a real latent defect in the deleted GPU arm (last chroma texel read padding as Cr). Architecture cascade closed. Status `in-progress → review`. |
