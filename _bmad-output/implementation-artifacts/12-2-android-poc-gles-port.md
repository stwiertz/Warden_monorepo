# Story 12.2: Android POC — Kotlin + MediaCodec + GLES 3.0 Port

Status: done

Sprint fit: `needs-spike-or-split` ([epics-and-stories.md:3312](../epics-and-stories.md#L3312)). The third deliberate exception to Decision #ES-9, after Story 1.1 and Story 12.1. **"Took multiple focused days" is not a failure mode for a spike.**

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As **Stephane (solo dev / product owner)**,
I want **the validated 12.1 engine ported to the Poco X5 Pro 5G — MediaCodec keyframe decode into a GLES 3.0 mega-shader — reporting measured ms/keyframe, a device-side CPU-vs-GPU rule-eval comparison, and colour/detection parity against 12.1's pinned outputs**,
so that **Story 12.3 can bind or reject the GPU detection engine on reference-device evidence instead of a PC extrapolation, and the ~20 stories of Epics 5/6/7 that feed off it stop waiting.**

---

## ⚠️ Read This First — What 12.1 Actually Found, and Why It Makes 12.2 the Decisive Story

**12.1 is `done` (merge `fbd4fef`). Its report is [apps/tooling/tools/keyframe_engine_bench/REPORT.md](../../apps/tooling/tools/keyframe_engine_bench/REPORT.md) (465 lines). Read §4 and §6 before writing a line of Kotlin.** Three results define your job:

1. **Accuracy: EXACT parity.** The GLSL reproduces `cv2.inRange` bit-for-bit — **0 disagreements over 2666 frames**, all three classifiers. That parity is *already banked*; your job is to prove it survives Adreno, not to re-earn it.
2. **Decode-bound: CONFIRMED.** 1061 keyframes, decode **8.862 ms/kf = 62%** of a **14.411 ms/kf** wall.
3. **🔴 On PC the GPU is ~2× SLOWER than the CPU at rule evaluation** — CPU `cv2.inRange` **1.667 ms/frame** vs GPU **3.253 ms/frame** (**0.51×**), decode excluded from both sides. Structural: the shipped rects are 1–25 px (~800 texel fetches/frame), but reaching them costs a **6.2 MB whole-frame upload** whose ~2.4 ms alone exceeds the CPU's entire rule-eval budget. The GPU's *actual* work is **~0.24 ms**.

**The entire architectural case for the GPU engine now rests on one unmeasured claim: that MediaCodec's zero-copy `samplerExternalOES` removes the upload.** If it does, the ratio inverts to roughly 7× in the GPU's favour. If it does not, the GPU engine has **no demonstrated performance argument left**.

**And there is a bind.** 12.1 quantified the colour risk: `samplerExternalOES` performs an **implicit, driver-defined YUV→RGB conversion AOSP does not specify**. Our V2 captures are `color_range=tv` + `bt709`; the range error alone shifts **S by ~19.7 units mean**, and **68 of the 134 shipped rules sit at `s_center ≤ 8`** having surrendered hue (`h_tol=180`) — immune to the matrix error, *maximally* exposed to the range error. The bit-parity mitigation (Y/U/V as three R8 textures, YUV→RGB in our own shader) **gives up the very zero-copy path that is the sole source of the advantage.**

> **That fork — zero-copy speed vs bit-parity correctness — IS this story's deliverable.** 12.3 cannot decide without both numbers. AC13 requires you to measure **both paths**, not pick one.

**Also true, and 12.3 must hear it:** even with upload *and* readback at zero, PC wall goes 14.41 → ~11.8 ms/kf, because decode is still 8.86 ms and would then be ~75% of what remains. **On Android, decode is hardware** — that may matter more than the engine choice. Measure it.

---

## Acceptance Criteria

### AC0 — Kickoff decisions (resolve BEFORE Task 1; record verdicts in Dev Agent Record)

- [x] **AC0a — Delivery vehicle.** There is genuine tension here; do not resolve it silently.
  - **Option A (RECOMMENDED) — Expo config plugin inside `apps/mobile`.** A second plugin (`apps/mobile/plugins/with-detection-engine.js`) emitting Kotlin + the `.frag` asset, modelled on the 390-line [with-foreground-service.js](../../apps/mobile/plugins/with-foreground-service.js). *For:* [architecture.md:2190](../architecture.md#L2190) amendment 5g **names this** ("Story 12.2 introduces a GLES 3.0 + MediaCodec engine module… MUST obey… sole access via `shared/services/*.ts`"); measures inside the shipped app's real minSdk/ABI/gradle reality, which is the only honest reference-device number; 12.4 inherits the plumbing; a 12.3 rejection means deleting one plugin file + one `app.json` line.
  - **Option B — standalone throwaway Kotlin/Gradle project** outside `apps/mobile`. *For:* fastest iteration, no RN/Expo/Firebase in the build loop, can host the first `androidTest`. *Against:* re-does plumbing 12.4 needs; does not exercise the real app's build; contradicts 5g's wording.
  - **Option C — local Expo module package** (`packages/` or `modules/`). *Against:* no precedent anywhere in the repo; Story 1.2 explicitly chose a legacy `ReactPackage` over Expo Modules.
  - Whichever lands: the engine Kotlin MUST be written **RN-agnostic** (a plain class plus a thin trigger), so the measurement code and the future runtime module are the same code.
- [x] **AC0b — Decode path.** `-skip_frame nokey` has **no MediaCodec equivalent flag**; this must be built.
  - **Option A (RECOMMENDED)** — ~~`MediaExtractor.seekTo(t, SEEK_TO_NEXT_SYNC)` in a loop~~ **[AMENDED 2026-09-15 ON MEASUREMENT — see below]**, feeding **only sync samples** to `MediaCodec`. A sync sample is self-contained, so decoding it alone is valid. Requires `codec.flush()` between seeks; verify the seek loop terminates (advance past the returned `sampleTime`).
    > 🔴 **The prescribed INCREMENTAL scan does not work on the reference device.** `seekTo(lastPts + 1, SEEK_TO_NEXT_SYNC)` in a loop **stops advancing after the second sync sample**, reporting **2** keyframes against a ground truth of **1061** on the shipped capture. **What shipped instead: absolute `SEEK_TO_CLOSEST_SYNC`** against a PTS list built up front (~2.9 ms per seek). Seeking is not broken; that one pattern is.
    >
    > Amended inline rather than left in the Dev Agent Record because **Story 12.4 inherits this decode path** and the original wording is an active trap for the next reader. AC0b's binding count assertion is what caught it, exactly as designed — without it the bench would have reported a self-consistent `2 == 2` over two frames.
    >
    > The decode loop now also **verifies where each seek landed** (`extractor.sampleTime == pts`, and `SAMPLE_FLAG_SYNC` set) — added 2026-09-15 in code review, because a seek landing on the *same* sample twice would have been counted as two distinct keyframes and inflated every `ms_per_keyframe` divisor.
  - **Option B** — full decode + `advance()`, keeping only buffers flagged `BUFFER_FLAG_KEY_FRAME`. Correct but decodes everything — this is the `select='eq(pict_type,I)'` mistake 12.1 measured at **5.4× slower** on PC. Use only as a control.
  - **Option C (control measurement, cheap — DO run it)** — `@wokcito/ffmpeg-kit-react-native@^6.1.2` is **already a mobile dependency** ([apps/mobile/package.json:26](../../apps/mobile/package.json#L26)) and can run 12.1's literal `-skip_frame nokey` on device. It is software decode and will lose, but it gives a directly comparable decode number and isolates "is MediaCodec hardware decode actually faster" from every other variable.
  - **Binding either way: assert the decoded keyframe count against `MediaExtractor`'s own sync-sample count.** 12.1's analogue caught a CFR-duplication regression that would have presented as ~7250 frames instead of 30.
- [x] **AC0c — Colour path. 🔴 Do not pick one. AC13 requires both measured.**
  - **Path Z (zero-copy)** — `MediaCodec` → `Surface`/`SurfaceTexture` → `samplerExternalOES`. Fast, colour-unspecified. **Gated on AC2.**
  - **Path P (bit-parity)** — `COLOR_FormatYUV420Flexible` → `Image` planes → three **R8** textures → YUV→RGB in our shader with **FFmpeg's exact constants** (bt709, limited→full range). Slower, colour-exact.
  - Record which one you would ship *if forced today*, and why — that recommendation is an input to 12.3, not a verdict.
- [x] **AC0d — Module name, package, and file locations.** Kotlin package is `team.warden.mobile` and the source root is `android/app/src/main/java/team/warden/mobile/` — note `java/`, **not** `kotlin/`, and note it is **gitignored and regenerated by `expo prebuild`** (AC18). Name the engine class, the bench entry point, and the `.frag` asset destination (`assets/` or `res/raw/` — no precedent exists; the FGS plugin writes Kotlin only).

### Gate first — run these BEFORE any rule-porting work (12.1's explicit instruction)

- [x] **AC1 — Device profile captured from the real device, and the Adreno correction landed.** Query and record `GL_VENDOR`, `GL_RENDERER`, `GL_VERSION`, `GL_SHADING_LANGUAGE_VERSION`, the full `GL_EXTENSIONS` list, `MediaCodecInfo` for the selected decoder (name, `isHardwareAccelerated`, supported colour formats), Android build/API level. **Then correct the three artifacts that disagree**, all of which say **Adreno 619** and are wrong — SM7325 = Snapdragon 778G = **Adreno 642L** (Adreno 619 is the SD695, the pre-re-anchor device per [[project_warden_reference_device]]):
  - [epics-and-stories.md:3315](../epics-and-stories.md#L3315)
  - `sprint-status.yaml`, key `12-2-android-poc-gles-port`
  - [keyframe_engine_bench/__main__.py](../../apps/tooling/tools/keyframe_engine_bench/__main__.py) — Tool 12 stamps its reference-device note into **every JSON payload it writes**, so 12.2's and 12.3's evidence artifacts currently contradict each other.
  - **Write the measured string, not the inferred one.** If the device reports something other than 642L, the device wins. Also flag (do not fix — 9.10's scrub) that [architecture.md:847](../architecture.md#L847) still says *"Poco X5 (Snapdragon 695, 6 GB RAM; Android 13)"* — a **third** identity, and [:2100](../architecture.md#L2100) a fourth site.
- [x] **AC2 — 🔴 `GL_OES_EGL_image_external_essl3` is CHECKED, never assumed.** Under `#version 300 es`, `samplerExternalOES` is **not core** — it requires `#extension GL_OES_EGL_image_external_essl3 : require`, an **optional** extension absent on a small number of GLES 3 devices. If it is missing on the Poco:
  - **Path Z is unavailable under ESSL 3.00.** Record it as a measured finding — it is a first-class result for 12.3.
  - **Do NOT silently fall back to `#version 100` + `GL_OES_EGL_image_external`.** That breaks **E2** ("same GLSL source of truth") and turns the port into a rewrite. Fall to AC0c Path P instead and say so.
  - Query via `GLES30.glGetString(GLES30.GL_EXTENSIONS)` on a **current context**, and also confirm the shader actually compiles with the `#extension` line — extension strings lie less often than drivers, but both are cheap.
- [x] **AC3 — 🔴 PC-vs-device frame diff, BEFORE any rule porting.** 12.1's literal instruction: *"Gate 12.2 on a cheap PC-vs-device frame diff before any rule-porting work."* Decode **the same keyframe of the same capture** (`videos/V2/2026-04-27 22-05-34.mp4`) on PC via FFmpeg `rgb24` and on device via **each** AC0c path; dump both to PNG; compute ΔH/ΔS/ΔV in **OpenCV HSV units**, reported as mean and as a distribution over the 68 low-saturation rule regions specifically. Diagnose using 12.1's measured signature:
  - **~16 offset / ~9% gain ⇒ range error** (limited→full): ΔS mean **19.68**, ΔV 7.64, ΔH 1.22.
  - **Saturated-hue shift with greys stable ⇒ matrix error** (709→601): ΔS 1.64, ΔV 0.43, ΔH 1.12.
  - A clean Path P must show **ΔH = ΔS = ΔV = 0** against FFmpeg. If it does not, the YUV→RGB constants are wrong and every downstream number is unanchored — **STOP and fix before proceeding.**

### Port fidelity — this is a port, not a rewrite (E2)

- [x] **AC4 — One GLSL body, two dialects, byte-identical apart from the version/extension preamble.** The shader body MUST be [keyframe_engine_bench.frag](../../apps/tooling/tools/keyframe_engine_bench/keyframe_engine_bench.frag) as it exists on `main`. Do not re-author, re-indent, or "tidy" it. If a change proves necessary on device, it lands in the **tooling file first**, both dialects are re-gated (`uv run python -m tools.keyframe_engine_bench --gate-glsl`), the tooling pytest suite re-runs, and the Android copy is regenerated from it. **Assert the equality mechanically** (checksum of the body with the preamble stripped, or the plugin copying the file verbatim at prebuild time) so drift fails loudly rather than silently.
- [x] **AC5 — LUT packing reproduced exactly from [lut.py](../../apps/tooling/tools/keyframe_engine_bench/lut.py).** `MAX_RULES = 150`, a **150×3 RGBA32F** data texture, three rows = `(x,y,w,h)` / `(h_lo,h_hi,s_lo,s_hi)` / `(v_lo,v_hi,min_ratio,mode)`. Binding details, each of which 12.1 paid for:
  - Bounds are **pre-resolved OpenCV integers on the CPU** via `resolve_band_bounds` semantics. **The band is NEVER re-derived on the GPU.** Parity comes from not re-deriving it.
  - `hsv_user_to_cv` applies `% 180` to the hue **center**; `tol_h_user_to_cv` **must NOT** — a tolerance is a *magnitude*, and modding it collapses wide bands (`h_tol=380 → 10`). **This is the #1 shader-port trap.**
  - Branch order: **full-circle tested FIRST** (`(h_hi - h_lo) >= 180`), then wrap (`h_lo < 0 || h_hi > 179`), else normal. Measured live distribution across the 134 shipped rules: **68 full-circle / 9 wrap / 57 normal — all three fire in production.**
  - `h_lo`/`h_hi` are packed **RAW** (possibly negative or >179); the shader derives `mod(h,180)` itself.
  - Rects are **clamped CPU-side** (`Rect.clamp_to`), and `area` is the **clamped** area — Tool 9 divides by the clamped `mask.size`, not `w×h`.
  - Padding texels (rules `n..149`) get `min_ratio = 2.0` so `step()` can never fire them.
  - `MAX_RECT_TEXELS = 4096` MUST stay in lockstep between the LUT packer and the `.frag`, and the packer MUST **reject** any rect above it — above the cap the loop truncates while `ratio` still divides by the full area, so a rule **silently under-fires** instead of failing.
  - `weight` / `weight_override` **never reach the GPU**. All scoring and phase resolution stay CPU-side.
- [x] **AC6 — ES-3.0 render-target rules.** Render target is **RGBA8, never RGBA32F** (not colour-renderable in ES 3.0 core; `glReadPixels` guarantees only `GL_RGBA`/`GL_UNSIGNED_BYTE`). Decode fires with **`> 127`**, never `== 255`. `GL_PACK_ALIGNMENT` pinned to **1** (150×4 = 600 B is only *accidentally* 4-aligned). Texturing a 32F LUT is fine — texturing ≠ rendering.
- [x] **AC7 — Construction-time GL self-test, before any number is trusted.** 12.1's most expensive lesson: a `GL_RGBA8UI`-vs-`GL_RGBA8` mismatch returned **uninitialized memory that looked like plausible detections** (0.35/0.31/0.05), raised nothing, and read as *"the port is broken"* rather than *"the format is wrong"*. It cost a full accuracy run. On construction: clear the FBO to a known value, read it back, assert the value **and** `glGetError() == GL_NO_ERROR`. Also validate texture geometry on every upload/bind — a same-byte-count/different-geometry frame yields silently transposed pixels. **GL failures are silent by nature. Assert the plumbing before trusting a single number.** Release the context on a failed construction (do not leak ~6 MB and an EGL context on the very path the self-test exists to catch).
- [x] **AC8 — 🔴 The integer-HSV exactness proof does NOT transfer to Adreno — verify it on device.** (Closes the 12.1 review item deferred to this story.) The shader recomputes OpenCV's `sdiv`/`hdiv` reciprocal tables at runtime with `float` divides. The exactness argument ("float error ~1/32, nearest tie ≥ 1/510 away") holds at a 24-bit mantissa, but **ESSL 3.00 `highp float` is specified as a *minimum relative precision*, not mandated IEEE-754 single.** A driver at reduced precision moves `sdiv`/`hdiv` by one, shifting S or H by ±1 — and **31 of 134 rules have bands asymmetric about their centre**, so they are exactly the rules that flip. Verify by running the device shader over a fixed frame set and comparing **per-rule fire bits** against 12.1's pinned GPU output (AC14). A mismatch here is a finding, not a bug to paper over.
- [x] **AC9 — Negative signed right-shift verified on Adreno.** `keyframe_engine_bench.frag` does `h = (h * hdiv + 2048) >> 12;` where `h` **can be negative** (the next line exists solely to correct it). The shader deliberately avoids integer `%` and `/` because ESSL 3.00 leaves them undefined for negative operands; the current code asserts `>>` sign-extends. Desktop-proven, **Adreno-unproven — and AC6's whole premise is that desktop proves nothing.** Exercise a wrap-branch rule (there are **9**) that drives `h` negative and confirm the result matches the CPU. If it diverges: bias before the shift (`h += (h<0) ? 180*4096 : 0`) **in the tooling `.frag`** per AC4, and re-gate both sides.
- [x] **AC10 — `precision highp` is honoured, and no float `rgb2hsv` is reintroduced.** The `mediump` NaN trap cannot be reproduced on PC: a float `rgb2hsv`'s `1e-10` epsilon is ~6 orders below `mediump`'s smallest normal (2⁻¹⁴) → flushes to 0 → `0/0 = NaN` on greys → **NaN fails every `step()` silently**, and our 68 low-sat rules *are* the greys. The shipped integer port sidesteps this (no epsilon; the reciprocal is gated on `diff > 0`) — **confirm it stayed integer.** `precision highp float/int/sampler2D` are mandatory; the ES fragment language has no default float precision and `sampler2D` defaults to **lowp**.

### Measurement — the actual deliverable

- [x] **AC11 — Measured on the Poco X5 Pro 5G, on the same capture 12.1 used.** `videos/V2/2026-04-27 22-05-34.mp4` (~2 h, native 1920×1080, GOP **4.167 s**, **1061 keyframes** — measured, not the epic's wrong GOP-2s/2400 assumption). Report per keyframe: **decode / upload-or-bind / shader / readback / total wall**, plus keyframe count, total wall, and thermal/throttle context (run to completion; note if sustained clocks drop).
  - Instrument **the same naive wall-clock way 12.1 did** so the numbers are directly comparable — and then **also** produce a forced-completion per-stage profile (`glFinish()`/fence per stage, median of ≥200), because 12.1 proved the naive split is **misattributed**: GL uploads are asynchronous, the timer stops before the transfer lands, and the blocking readback absorbs the tail. Report both and say which is which.
  - **Exclude EGL context creation, shader compile and the self-test from `ms_per_keyframe`** (12.1 amortized them into the headline; on device context creation is far more expensive). Report them as a separate one-off cost — it is a real number 12.3 wants.
- [x] **AC12 — 🔴 The number that decides the epic: device CPU vs device GPU at rule evaluation, decode excluded from both sides.** 12.1's headline is *"the CPU is 2× faster"*; 12.3 cannot act on that without knowing whether it holds on Adreno. Implement a **plain-Kotlin CPU baseline** — the same rects, the same integer `RGB2HSV_b`, the same inclusive integer bounds, the same `count/area >= min_ratio` — over the same frames. Do **not** route this through `react-native-fast-opencv` JSI (that re-opens Story 1.1's frozen spike and adds a variable). ~100 lines of Kotlin buys the comparison the whole epic turns on. Report `ms/frame` for each and the ratio.
- [x] **AC13 — 🔴 BOTH colour paths measured, side by side.** For **Path Z** and **Path P** independently: ms/keyframe (all stages) **and** per-rule fire-bit parity against 12.1's pinned output. This table is the single most decision-relevant artifact 12.2 produces, because 12.1 established that the GPU's entire performance case rests on the path that may cost correctness. State explicitly, from measurement:
  - Does zero-copy actually remove the upload on this device? By how much?
  - Does the OES colour conversion break parity? On how many of the 134 rules, and are they the 68 low-sat ones?
  - What does Path P cost relative to Path Z, and does the remaining margin still beat AC12's CPU number?
- [x] **AC14 — Detection parity: two corpora behind one seam** (12.1's AC8b pattern). **(a) Parity corpus** — push a fixed, enumerated subset of the labeled PNGs (`apps/tooling/output/labeled/v2/`) to the device, decode them as **RGB bitmaps** (not through the video path), and compare **per-rule fire bits** and per-frame classifications against 12.1's pinned GPU output. This isolates *shader* parity from *decode colour* — the two failure modes must not be allowed to mask each other. **(b) Timing corpus** — the full video keyframes, for AC11/AC13. State the PNG subset size and how it was chosen; a full 2666-PNG push is acceptable but not required.
  - Reproduce **all three per-classifier formulas** exactly, as 12.1 did: HUD `fires/n_hud` **normalized**; in_match `fires/n_im` **normalized then hard-binary**; map-ID `Σ effective_weight × fired` **raw, unnormalized**. `SCP:285`'s *"Tool 9 sums raw weighted"* is true of **the map-ID classifier only** — implementing that form everywhere silently breaks two of the three numbers.
  - **The shader IGNORES `minimap_identification.roi`.** It is a dead 3×5 box, byte-identical to `atlantis_z10`'s rect, that Tool 9 parses and never reads; **120 of 121 map zones fall entirely outside it**. A port that "correctly" honoured it would crop away 120/121 zones and score ≈0 — presenting as *"the port is broken"*. Evaluate zone rects as **absolute reference-resolution coordinates against the full 1920×1080 frame**. Do not fix the data defect (9.9b's, AC19-fenced).
- [x] **AC15 — 🔴 12.2 reports a real Poco number. It does NOT bind PERF-002 or PERF-010.** Those re-baseline with **12.3** ([architecture.md:842](../architecture.md#L842), [prd.md:1029](../prd.md#L1029), [:1037](../prd.md#L1037)); PERF-010 is a **soft target**, not a measured floor, and V1 launch is not gated on it. The engine brief's **`< 10 s`** is *"the aspiration, not an acceptance criterion"* — measure it, report it, do **not** fail the story for missing it. Parity figures are an **in-sample parity target**, never accuracy-in-the-world: **REL-006's ≥95% floor is not gated here** (that is 9.9b's, instrumented by Tool 9 via 9.16). 12.1 took a review finding for letting one extrapolated row read as an Android verdict — do not inherit that failure in the opposite direction.

### Deliverables, decisions and fences

- [x] **AC16 — The observed threading model, written up (amendment 5d's named deliverable).** [architecture.md:813-815](../architecture.md#L813) marks Brownfield Item 6 **"RATIONALE RE-DERIVATION REQUIRED"** and names **Story 12.2** as the owner. Its current rationale rests on *"the FFmpeg/OpenCV JSI bindings cannot be shared across the headless context boundary"* — but **EGL contexts are THREAD-bound, not JS-context-bound**. Record, from what you actually built: which thread owns `eglMakeCurrent`; which thread `MediaCodec` callbacks arrive on; `SurfaceTexture.updateTexImage()` thread affinity; whether an offscreen pbuffer context can live on a worker thread; what that implies for a Foreground Service host. **The conclusion will very likely survive — a foreground service still hosts the work — but it must be re-derived, not inherited.** Deliver the model; **12.3 rewrites the architecture prose**, not you.
- [x] **AC17 — A measured `REPORT.md`, shaped to fill 12.3's four slots.** 12.1's precedent: the report lives beside the code, not in `_bmad-output/`. It must carry **measured numbers, the device profile, ladder-rung verdict *input*, and the fixtures used** ([architecture.md:868](../architecture.md#L868)). **12.2 does NOT publish `_bmad-output/architecture-spike-gpu-megashader.md`** — that is 12.3's deliverable and the verdict slot is 12.3's.
- [x] **AC18 — Native-surface invariants honoured.** (a) **`apps/mobile/android/` is gitignored and regenerated** — every native artifact MUST be emitted by a config plugin; a hand-edit is erased by the next `expo prebuild --clean` and is invisible to git. (b) The new module obeys [architecture.md:2190](../architecture.md#L2190): **sole access via `apps/mobile/src/shared/services/*.ts`**, no feature imports it directly. (c) **SEC-007 allowlist entry** is mandatory — the tooling carve-out covers `moderngl`/12.1 only and does **not** exempt the mobile artifact. Note the honest nuance: MediaCodec and GLES are **AOSP platform APIs, not third-party SDKs**, so the entry documents the wrapper module; any npm-side package would additionally be seen by the transitive-dep scan. (d) If `MainApplication.kt` registration is needed, follow the FGS precedent: anchor-string patch that **throws loudly** on drift. (Applies as scoped by AC0a.)
- [x] **AC19 — Scope fence.** 12.2 does **NOT**: touch `gameDetector.ts` / `mapIdentifier.ts` / `blackScreenDetector.ts` / `segmentation.ts` / `processingPipeline.ts` (**12.4's**, and conditional on 12.3's verdict) · touch zone data, `apps/tooling/output/zones/v2/*`, or `contracts/map-config.schema.json` · bump `schema_version` (**E1** — rects are retained; a rect with `w=1,h=1` **is** a point) · modify Tools 9/10/11 or the emitter · publish the spike report (12.3) · re-arm the fallback ladder (12.3) · re-point Tool 9 (9.16) · re-open Story 1.1 (**FROZEN**; 12.3 supersedes, 1.1 records) · fix the `minimap_identification` data defects (9.9b). Changes to `keyframe_engine_bench.frag` are permitted **only** under AC4's procedure. Verify the fence with `git status` before delivery.
- [x] **AC20 — Gates green.** `pnpm typecheck && pnpm test && pnpm format:check` from the repo root, with **zero new** failures against a re-verified baseline (record the baseline first — do not trust a number written in a prior story). If the `.frag` was touched under AC4: re-run `--gate-glsl` (both dialects) **and** the tooling pytest suite (**305** at `main`), and state both counts. New Kotlin has no lint gate on this surface (mobile ESLint is an `echo` placeholder; no ktlint/detekt exists) — say so rather than inventing one.
- [x] **AC21 — Committed to `main` 2026-09-15.** Scope `mobile`, lowercase subject per commitlint. Per [[project_warden_main_branch_workflow]] work happens directly on `main` (no branch, no `--no-ff` merge — that clause predates the 2026-09-15 sole-dev decision); `main` is **not** auto-pushed, and has not been.
- [x] **AC22 — `sprint-status.yaml` `review → done`** + the AC1 epic/tracker corrections, per [[feedback_ac_checkbox_tighten]]. Landing in the same commit rather than a follow-up: [[feedback_two_pr_docs_execution]]'s two-PR sequencing was retired with the branch workflow, and [[project_warden_shared_doc_commit_boundary]] does not bite here because no foreign multi-story edits are co-mingled in this working tree.

---

## Tasks / Subtasks

- [x] **Task 1 — Pre-flight and AC0 (AC0a–d, AC1)**
  - [x] Re-verify baselines on `main`: root `pnpm typecheck`/`pnpm test` counts, tooling pytest count, `git status` clean.
  - [x] Confirm the device is present and `adb`-reachable; capture the full device + GL + MediaCodec profile (AC1).
  - [x] Put AC0a–AC0c to Stephane with the recommendation and the consequence of each. **Do not start Task 3 before AC0a is answered.**
  - [x] Land the Adreno 619 → measured-value correction at all three sites (AC1).
- [x] **Task 2 — The two gates that can kill the approach (AC2, AC3)**
  - [x] Probe `GL_OES_EGL_image_external_essl3` on a current context and compile-test the `#extension` line (AC2).
  - [x] PC-vs-device frame diff for every available colour path, reported in OpenCV HSV units with the 68 low-sat regions broken out (AC3).
  - [x] **Decision point:** if Path Z's colour is unusable *and* Path P's cost eats the margin, say so here — that is a legitimate 12.2 outcome and 12.3's most useful input. Do not proceed to a full port to avoid reporting it.
- [x] **Task 3 — Scaffold the native surface (AC0a, AC0d, AC18)**
  - [x] Config plugin (or chosen vehicle) emitting the engine Kotlin + the `.frag` asset, with the AC4 verbatim-copy/checksum guard.
  - [x] EGL context + offscreen FBO + program build, with the AC7 self-test on the construction path and release-on-failure.
  - [x] Prove the round-trip on a synthetic frame before any real data touches it.
- [x] **Task 4 — LUT packer in Kotlin (AC5)**
  - [x] Port `resolve_band_bounds` semantics + `pack_rules`, including the rect-area rejection and the `_PAD_MIN_RATIO` padding.
  - [x] Cross-check the packed 150×3 texture **byte-for-byte** against `lut.py`'s output for the shipped config. This is cheap and removes an entire class of divergence before any GPU work.
- [x] **Task 5 — Decode path (AC0b, AC11)**
  - [x] MediaExtractor sync-sample loop → MediaCodec; assert keyframe count against the extractor's own count.
  - [x] Run the FFmpeg-kit `-skip_frame nokey` control for a directly comparable decode number.
- [x] **Task 6 — Wire both colour paths (AC0c, AC13)** — Path Z and Path P behind one seam, switchable at runtime so the two are measured on identical everything-else.
- [x] **Task 7 — Parity run (AC8, AC9, AC10, AC14)**
  - [x] PNG parity corpus → per-rule fire bits vs 12.1's pinned output; report exact disagreements, not just an accuracy number.
  - [x] Exercise a wrap-branch rule with negative `h` (AC9) and a low-sat/grey rule (AC10) explicitly.
- [x] **Task 8 — Measurement run (AC11, AC12, AC13, AC15)** — naive + forced-completion profiles; the Kotlin CPU baseline; both colour paths; the full 1061-keyframe capture end to end.
- [x] **Task 9 — Threading model write-up (AC16)**
- [x] **Task 10 — `REPORT.md` (AC17)** — including an explicit "what this does NOT bind" section mirroring AC15.
- [x] **Task 11 — Gates + fence (AC19, AC20)**
- [ ] **Task 12 — [HELD] Commit / merge / status flip (AC21, AC22)**

---

## Dev Notes

### The native surface: what exists, what is greenfield

**Mobile GL surface is literally zero.** A strict regex over `apps/mobile` for `GLES[0-9]|OpenGL|EGL|MediaCodec|MediaExtractor|SurfaceTexture|ImageReader|\.glsl|\.frag|GLSurfaceView|expo-gl` returns **no matches**. [architecture.md:2190](../architecture.md#L2190) confirms: GPU/GLES/shader/GLSL/EGL/FBO/MediaCodec appear **nowhere else in the document** (the sole "GPU" token is a *Dear PyGui* rejected-alternative footnote about a GUI toolkit, explicitly *"must not be cited as prior art either way"*). **No prior decision authorizes the GPU path and none forbids it.**

**🔴 `apps/mobile/android/` is gitignored** — [.gitignore:73-75](../../.gitignore#L73) and [apps/mobile/.gitignore:6-7](../../apps/mobile/.gitignore#L6). `git ls-files apps/mobile/android` returns **nothing**. The directory exists on disk (built 2026-06-11) but is a **prebuild artifact**. Every durable native artifact must come from a config plugin.

**The working template is [apps/mobile/plugins/with-foreground-service.js](../../apps/mobile/plugins/with-foreground-service.js)** (390 lines, Story 1.2), registered as the 4th entry in `app.json`'s `plugins`. It composes four modifiers under `withRunOnce`:
| Piece | Mechanism |
|---|---|
| `SERVICE_KT` / `MODULE_KT` / `PACKAGE_KT` | Kotlin **string templates inside the JS plugin**, written via `withDangerousMod("android")` + `fs.writeFileSync` |
| Manifest permissions + `<service>` | `withAndroidManifest` |
| `add(WardenProcessingPackage())` | `withMainApplication` **string-patch anchored on `// add(MyReactNativePackage())`**, which **throws** if the anchor is missing |

Target dir: `android/app/src/main/java/team/warden/mobile/` — a **`java/` directory holding `.kt` files**; there is no `srcDirs` customization. Registration precedent is a **legacy bridge `ReactPackage` + `@ReactMethod` + `Promise`**, not a TurboModule (no codegen spec anywhere). The TS wrapper precedent is [foregroundService.ts](../../apps/mobile/src/shared/services/foregroundService.ts) — `NativeModules.WardenProcessing`, missing-module swallow so jest never sees the bridge, owner-token, `stop` never rejects.

⚠️ **The plugin writes Kotlin only. A `.frag`/`.glsl` asset needs a fourth emission target** (`android/app/src/main/assets/` or `res/raw/`) with **no precedent in this repo**. `withDangerousMod` runs *before* other modifiers and its ordering is documented as unreliable — check the directory exists before writing, per Expo's own guidance.

⚠️ **JSI vs TurboModule is UNDECIDED and no architectural constraint exists.** New Arch is on (`newArchEnabled: true`), Expo SDK 54 / RN 0.81.5 / React 19.1. **Record the choice as an explicit decision.** Note that amendment 5d's finding — EGL contexts are **thread**-bound — is the constraint that actually governs the binding shape, not the module system.

### Build reality — nothing is pinned locally

`app/build.gradle` defers everything to `rootProject.ext.*`, populated by the `expo-root-project` plugin from RN's version catalog. Effective values today (`node_modules/react-native/gradle/libs.versions.toml`):

| Key | Value |
|---|---|
| minSdk / targetSdk / compileSdk | **24 / 36 / 36** |
| buildTools / NDK | 36.0.0 / 27.1.12297006 |
| AGP / Kotlin / Gradle | **8.11.0 / 2.1.20 / 8.14.3** |
| ABIs | `armeabi-v7a, arm64-v8a, x86, x86_64` |

**minSdk 24 clears GLES 3.0 (API 18+) with margin**; `MediaCodec.setCallback` is 21+, `setOutputSurface` 23+. **No `externalNativeBuild`/CMake block exists** — a pure-Kotlin GLES path needs no NDK config; a C++ path would have to add one via a gradle mod. **`expo-build-properties` is absent from the repo** — if a version must change, adding it is the clean route, not editing generated `gradle.properties`. Precedent to match if any `.so` ever lands: FFmpeg-kit 6.1.4 is **16-kb page-aligned for Android 15+** ([architecture.md:211](../architecture.md#L211)).

Build/deploy commands ([architecture.md:1977](../architecture.md#L1977), [:1994](../architecture.md#L1994)):
```sh
pnpm --filter mobile exec expo prebuild     # regenerate native android/
pnpm --filter mobile android                # expo run:android (needs dev client)
pnpm --filter mobile exec expo export --platform android   # Hermes bundle ≈5.23 MB
```

### Decode: `-skip_frame nokey` has no MediaCodec equivalent

This is the largest *new* engineering surface in the story — everything else is a port. Facts:

- **MediaExtractor seeks only to sync samples.** `SEEK_TO_NEXT_SYNC` / `SEEK_TO_CLOSEST_SYNC` / `SEEK_TO_PREVIOUS_SYNC`. A sync sample is a keyframe that also carries configuration change parameters, so **feeding one alone to MediaCodec is valid** — that is the true `-skip_frame nokey` analogue.
- **You cannot skip intermediate frames and still decode later P/B frames** — but you never want them, so this constraint is free here.
- `codec.flush()` is required after each seek. Watch for a non-advancing seek loop: always seek strictly past the last returned `sampleTime`.
- Alternative: `advance()` frame by frame checking `BUFFER_FLAG_KEY_FRAME`, pre-building the keyframe PTS list. Correct, but it decodes everything — on PC the equivalent (`select='eq(pict_type,I)'`) measured **2.63 s vs 0.49 s**, a **5.4×** penalty for zero decode saving.
- **Expected shape from 12.1**: GOP **4.167 s**, **72 keyframes / 300 s**, **1061 keyframes** for the full capture. A CFR-duplication-style regression would present as a wildly inflated count — **assert it**.

### 🔴 `samplerExternalOES` under `#version 300 es` is an OPTIONAL extension

This is the finding that can quietly turn the port into a rewrite. In ESSL 3.00, `samplerExternalOES` is **not core**; it requires:

```glsl
#version 300 es
#extension GL_OES_EGL_image_external_essl3 : require
```

`GL_OES_EGL_image_external_essl3` is optional and **absent on a small number of GLES 3 devices** — a known real-world shader-compilation failure (Firefox/WebRender both carry bugs for exactly this). The ESSL 1.00 extension (`GL_OES_EGL_image_external`, `texture2D`, `gl_FragColor`) is the common fallback, and taking it would **break E2 outright**: two shader bodies, not one, and every AC6 subset guarantee re-litigated. Adreno drivers generally ship it — but *generally* is not *measured*, and AC6's whole premise is that assumptions about the target are worthless. **Probe it (AC2), and if it is missing, report that and take Path P.**

### Colour: the fork that decides the epic

| Error source | ΔS mean | ΔV mean | ΔH mean (S>40) |
|---|---|---|---|
| **range** (limited→full) | **19.68** | 7.64 | 1.22 |
| matrix (709→601) | 1.64 | 0.43 | 1.12 |

Our V2 captures are `color_range=tv` + `bt709` — **exactly the risky combination**. 68 of 134 rules sit at `s_center ≤ 8` having set `h_tol=180`; they are immune to the matrix error and **maximally exposed to the range error**. That `h_tol=180` choice is not incidental — it is the accepted [[project_warden_low_sat_hue_unconstrained]] decision that moved map-ID **0.973 → 1.000** and in_match FP → 0. **The 1.0000 / 0.9805 figures were fitted against FFmpeg's conversion and are NOT portable constants.**

Path P's constants must be FFmpeg's exact bt709 limited-range coefficients, verified by AC3's diff reading **zero**, not "close".

### Measured baseline you are comparing against (12.1, Intel UHD 770 — PC, not targets)

| Stage | ms/keyframe | Share |
|---|---|---|
| decode (`-skip_frame nokey`, RAM pipe) | **8.862** | **62%** |
| upload (6.2 MB host→GPU) | 1.705 ⚠️ misattributed | 12% |
| shader + readback | 1.177 ⚠️ misattributed | 8% |
| scoring / phases / ring / overhead | ~2.67 | 18% |
| **TOTAL wall** | **14.411** | 100% |

⚠️ **Do not quote rows 2–3 as a split** — GL uploads are async, so the naive timer misattributes. Forced-completion truth: **upload 2.34–2.46 ms (~91%) / shader 0.15–0.22 ms (~8%) / readback stall 0.004–0.073 ms (<1%, in the noise)**. Two consequences carried forward: **non-blocking readback is not worth building** (the readback direction is **600 bytes**; the 6.2 MB goes the other way), and **the GPU's real cost is ~0.24 ms** — everything else is the bus.

Engine-vs-engine, decode excluded: **CPU 1.667 ms/frame vs GPU 3.253 ms/frame = 0.51×.** (12.1's Dev Notes' 0.647 ms/frame figure was measured **@ 640×360**, a ~9× smaller upload — consistent, not contradictory.)

### Conventions that bind, and one that does not

- **E7 (argparse, `run()`/`main()`, uv, pytest at `apps/tooling/tests/`, `output/<video_stem>/`) is a TOOLING constraint and does NOT apply to 12.2.** 12.2 is on the mobile surface. Do not mis-apply it.
- **Mobile testing:** jest + jest-expo preset, config lives in [apps/mobile/package.json:34-40](../../apps/mobile/package.json#L34) (no `jest.config.*`), tests in **`__tests__/` directories** co-located with the subject. [foregroundService.test.ts](../../apps/mobile/src/shared/services/__tests__/foregroundService.test.ts) is the precedent for testing a native bridge with **no device**: `jest.mock('react-native')` + a stubbed `NativeModules` entry.
- **There is NO `androidTest`/instrumentation harness anywhere** — `android/app/src/` has only `main/`, `debug/`, `debugOptimized/`; zero `testImplementation`/`androidTestImplementation`/`testInstrumentationRunner` in `app/build.gradle`. 12.1's AC16 explicitly *forbade* a GL context in its test suite. **Decide and state** whether 12.2 is device-manual (12.1's precedent: `REPORT.md` as the deliverable) or introduces the first instrumentation setup — and if the latter, remember the config plugin must re-emit it on every prebuild.
- **Commit convention** ([INVARIANT 12], [architecture.md:1289](../architecture.md#L1289)): `<type>(<scope>): <subject>`, scope **`mobile`**, lowercase subject (commitlint).
- **Mobile ESLint does not exist** — `"lint": "echo 'eslint not configured for mobile yet'"`.
- ⚠️ **[architecture.md:2013](../architecture.md#L2013)/[:2192](../architecture.md#L2192) reference `apps/mobile/scripts/reader-app-gate.sh`. It does not exist on disk** (`apps/mobile/scripts/` is absent). Do not chase it; note the gap rather than inventing the script.

### Stale prose — do not inherit it (9.10 owns the scrub)

- [architecture.md:2047](../architecture.md#L2047) — *"the foreground service hosts the main JS context where the JSI binding lives"*. Contradicted by [:813](../architecture.md#L813): EGL contexts are **thread**-bound. This is precisely the sentence AC16 exists to make re-derivable.
- [architecture.md:2076](../architecture.md#L2076) — names `hash_validator` as the REL-006 instrument. Contradicted by [:120](../architecture.md#L120): **the instrument is Tool 9**; `hash_validator` measures Hamming distance and cannot measure a shader at all.
- [architecture.md:2179](../architecture.md#L2179) — *"iOS is glue work"*. Contradicted by amendment 5c at [:894-896](../architecture.md#L894), which this story activates.
- [architecture.md:1517](../architecture.md#L1517)/[:1703](../architecture.md#L1703) — still call `mapIdentifier.ts` a *"pHash matcher"* (true of the **current v1 code**, stale as architecture since the 2026-05-14 ROI+HSV pivot).
- **Amendment numbering:** there are exactly **seven** amendments, **5a–5g** — there is no 5h. All seven are **applied** in `architecture.md`; **5d** and **5g** carry residual work, and 12.2 owns or feeds both.
- **Line-number drift is real.** The SCP cites pre-amendment lines (~+8 in the 830–900 band, ~+12 in the 1240+ band). Re-verify any citation before pasting. Current: [INVARIANT 3] `:1251-1254`, cloud-CV FORBIDDEN `:866`, rung-3 `:865`, spike artifact `:868`, iOS assertion `:892` (amendment `:894-896`), native modules `:2190`, spike-report placement `:1052`.

### Amendment 5c activates with this story — and can lapse

[architecture.md:894-896](../architecture.md#L894), verbatim: *"The assertion above becomes **FALSE the day Story 12.2 lands**… MediaCodec + GLES 3.0 is Android-only **by construction** (iOS = VideoToolbox + Metal; GLES is deprecated on iOS). This **flips iOS Phase 2 from 'glue' to 'refactor' for the detection-engine slice**… iOS is already V3, so the cost is **deferred, not incurred**… **If Story 12.3 rejects the shader engine, this amendment lapses and the original assertion stands unmodified.**"*

Every other mobile decision (codebase, data layer, MMKV/SQLite, FGS plugin) stays cross-platform-ready — **the Android-only surface is bounded to the engine.** Keep it that way; that boundedness is what makes a 12.3 rejection cheap.

### Charter compliance — verified, not assumed

- **The only absolute prohibition is cloud CV** ([architecture.md:866](../architecture.md#L866) — *"FORBIDDEN — fall back to cloud CV | NEVER"*), and it is the **only ladder rung not re-armed on 2026-07-16**. A GPU shader is on-device ⇒ **[INVARIANT 3]** ([:1251-1254](../architecture.md#L1251)) holds and Innovation #1's privacy + marginal-cost claim is preserved.
- **E4 — doubt is a first-class outcome**, never forced to the nearest class; it maps onto `mobile-AUTO-SLICE-003`'s `unknown` and REL-006's *"graceful degradation, not blocking error"*. 12.1 **introduced** phase-axis doubt (there was no upstream `unknown` to inherit — the in_match classifier is hard-binary) via split-vote detection, one forward pass, no lookahead; it fired on **2 of 1061** keyframes. If 12.2 ports the state machine, port that design; if 12.2 only benches rule evaluation, say so and leave phases CPU-side as 12.1 built them.
- **Also inherited:** [INVARIANT 7] Reader-App banned imports, [INVARIANT 8] `EXPO_PUBLIC_AUTH_BYPASS`, [INVARIANT 9] `.npmrc node-linker=hoisted`, [INVARIANT 10] the MMKV v3 pin (*v4 needs Nitro Modules on RN 0.83+; v4 on RN 0.81 silently boot-crashes via JSI binding registration failure*) — a prebuild/native change can trip the last two.

### Data reality (verified on disk)

- Captures: `videos/V2/` — **4 real EVA captures**, incl. `2026-04-27 22-05-34.mp4` (12.1's bench video).
- Config: `apps/tooling/output/map_configs/map_config.v2.json` — **134 rules** (10 hud / 3 in_match / 121 map zones across 13 maps). **Gitignored**, but now regenerable: the 9.15 salvage landed, so all 4 fragments + `manifest.json` are **tracked** under `apps/tooling/output/zones/v2/` and `tests/test_zone_fragments_v2.py` guards the round-trip. **Leave `minimap_identification.json.bak` byte-untouched** — measured, it has **0** zones at `h_tol=180` where the live config has 65; restoring it would **regress** accuracy ([[project_warden_low_sat_hue_unconstrained]]).
- Parity corpus: `apps/tooling/output/labeled/v2/` — **2666 PNGs / 16 classes** (gitignored).
- Pinned CPU baseline: `apps/tooling/output/roi_detection_tests/v2/2026-07-16T230122/` — hud **0.9805** / in_match **1.0000** / map_id **1.0000**, plus `frame_predictions.csv` for **per-frame** comparison (a stronger claim than matching accuracy: two engines can post the same accuracy while disagreeing on *which* frames they get right).
- Schema: `contracts/map-config.schema.json` — `schema_version` enum `[1]`, explicitly *"the config-shape version (NOT the detection-method version)"*. **An engine swap does not bump it** (E1).
- ⚠️ 12.1's **Review Findings checkboxes are stale `[ ]`** in the story file, but the patches **did land** (verified in code: `pack_rules` rect-area rejection, `results.json` basename, release-on-failed-construction). Trust the code and the `done` status, not the checkboxes.

### Project Structure Notes

| Path | Status |
|---|---|
| `apps/mobile/plugins/with-detection-engine.js` | **NEW** (AC0a Option A) — second config plugin |
| `apps/mobile/app.json` | **UPDATE** — 5th `plugins` entry |
| `apps/mobile/src/shared/services/<engine>.ts` | **NEW** — sole TS entry point ([architecture.md:2190](../architecture.md#L2190)) |
| `apps/mobile/src/shared/services/__tests__/<engine>.test.ts` | **NEW** — device-free, `foregroundService.test.ts` pattern |
| `android/app/src/main/java/team/warden/mobile/*.kt` | **GENERATED** by the plugin — gitignored, never hand-edited |
| `apps/tooling/tools/keyframe_engine_bench/keyframe_engine_bench.frag` | **SOURCE OF TRUTH** — changes only via AC4 |
| `<engine>/REPORT.md` | **NEW** — AC17 deliverable |
| `_bmad-output/architecture-spike-gpu-megashader.md` | **12.3's** — do not create |
| `apps/mobile/src/features/video-processing/*` | **FENCED** — 12.4's |

### References

- [epics-and-stories.md:3279-3332](../epics-and-stories.md#L3279) — Epic 12 charter, constraints E1–E7, Story 12.2 at `:3312-3316`
- [12-1-pc-poc-gpu-megashader-bench.md](12-1-pc-poc-gpu-megashader-bench.md) — esp. §"colour-space risk" `:375-388`, HSV-on-GPU `:344-373`, reference-device `:408-410`, Completion Notes `:547-561`
- [keyframe_engine_bench/REPORT.md](../../apps/tooling/tools/keyframe_engine_bench/REPORT.md) — §4 (GPU slower / zero-copy arithmetic), §6 (recorded for 12.2), §7 (ES-3.0 gate), §9 (three formulas), §10 (doubt)
- [keyframe_engine_bench.frag](../../apps/tooling/tools/keyframe_engine_bench/keyframe_engine_bench.frag) · [lut.py](../../apps/tooling/tools/keyframe_engine_bench/lut.py) · [shader.py](../../apps/tooling/tools/keyframe_engine_bench/shader.py) · [phases.py](../../apps/tooling/tools/keyframe_engine_bench/phases.py) · [scoring.py](../../apps/tooling/tools/keyframe_engine_bench/scoring.py)
- [architecture.md](../architecture.md) — `:813-815` (5d), `:842`/`:847-853` (reference device, PERF), `:860-866` (ladder), `:868`/`:1052` (spike report), `:892-896` (5c), `:1251-1254` ([INVARIANT 3]), `:1302-1309` (mobile conventions), `:2190` (5g, native modules, SEC-007)
- [prd.md:1029](../prd.md#L1029) (PERF-002 re-baseline pending) · [:1037](../prd.md#L1037) (PERF-010 soft target) · [:1056](../prd.md#L1056) (REL-006)
- [sprint-change-proposal-2026-07-16.md](../sprint-change-proposal-2026-07-16.md) — `:43-48` (engine description), `:145-148` (risks), `:305-306` (sequencing), `:319-323` (success criteria). **Note: "Volet B" is the zone-authoring tool (~80% shipped as Tool 10), NOT the Android POC. Story 12.2 is assigned no volet.**
- [with-foreground-service.js](../../apps/mobile/plugins/with-foreground-service.js) · [foregroundService.ts](../../apps/mobile/src/shared/services/foregroundService.ts) — the native-module precedent
- [deferred-work.md](deferred-work.md) — the two items assigned to **12.2**: the ESSL-`highp`/IEEE-754 parity gap (AC8) and the Adreno 642L correction (AC1)
- External: [OES_EGL_image_external_essl3 (Khronos)](https://registry.khronos.org/OpenGL/extensions/OES/OES_EGL_image_external_essl3.txt) · [MediaExtractor seek-to-sync](https://developer.android.com/reference/android/media/MediaExtractor) · [Expo dangerous mods](https://docs.expo.dev/config-plugins/dangerous-mods/)

---

## Change Log

| Date | Change |
|---|---|
| 2026-09-15 | Story created (`/bmad-create-story` 12.2). AC0 (4 kickoff decisions) + AC1–AC22 + 12 Tasks. |
| 2026-09-15 | `/bmad-dev-story` 12.2 — **ALL 20 measurement ACs closed on the reference device; AC21/AC22 `[HELD]`.** AC0a–d resolved (A / A+C / both paths / assets+debug-manifest). Native surface: config plugin + 9 RN-agnostic Kotlin sources + TS seam + 12 device-free tests. **EXACT shader parity on Adreno 642L: 0 disagreements / 357,244 rule-frame decisions**, accuracy identical to 12.1 down to the counts. **GPU is 6.4x SLOWER than the device CPU at rule eval (0.157x)** despite zero-copy working as hoped (bind 0.37 vs upload 1.72 ms). Decode is **99% of the wall**; hardware decode beats ffmpeg software by only ~8%, so the real bound is keyframe RANDOM ACCESS, not decode or engine. Path Z diverges from bit-parity on 0.888% of decisions across 95/134 rules. `REPORT.md` delivered; gates green with zero new failures. |

---

## Dev Agent Record

### Agent Model Used

Amelia (`/bmad-dev-story` 12.2) — claude-opus-5[1m], 2026-09-15.

### AC0 — Kickoff decisions (resolved before Task 1)

Put to Stephane with recommendations and consequences; answered 2026-09-15.

| AC | Verdict | Notes |
|---|---|---|
| **AC0a** | **Option A** — Expo config plugin in `apps/mobile` | `plugins/with-detection-engine.js`, modelled on the 390-line FGS plugin. Engine Kotlin is **RN-agnostic** (no React imports in `WardenDetectionEngine` / `WardenRulePacker` / `WardenKeyframeDecoder` / `WardenCpuBaseline` / `WardenEngineBench`); the bridge is a thin trigger only. A 12.3 rejection = delete one plugin dir + one `app.json` line. |
| **AC0b** | **Option A + Option C control** | Primary: `MediaExtractor.seekTo(SEEK_TO_NEXT_SYNC)` sync-sample loop → `MediaCodec`. Control: ffmpeg-kit running 12.1's literal `-skip_frame nokey` on device. Option B (full decode + flag filter) NOT taken — it is the `select='eq(pict_type,I)'` mistake 12.1 measured at 5.4× slower. |
| **AC0c** | **BOTH paths built and measured** | AC13 mandates it; AC2 passed, so Path Z is genuinely available. The ship-if-forced recommendation is deferred to the measurement, not pre-judged. |
| **AC0d** | package `team.warden.mobile`, source root `android/app/src/main/java/team/warden/mobile/` | Engine `WardenDetectionEngine`; bench entry `WardenEngineBenchActivity` (**debug-manifest only**) + `WardenDetectionEngineModule` (RN); `.frag` → **`assets/`**, NOT `res/raw/` — `res/raw/` resource names forbid uppercase letters and dots, so the file would have to be RENAMED, undercutting AC4's "copied verbatim" guarantee. |

**JSI vs TurboModule** (Dev Notes: "UNDECIDED — record the choice"). Legacy bridge `ReactPackage` + `@ReactMethod` + `Promise`, matching the Story 1.2 precedent. No codegen spec exists anywhere in the repo, and AC16's finding is that the binding shape is governed by **EGL thread affinity**, not by the module system — so a TurboModule buys nothing this story needs.

### Debug Log References

**AC20 baseline re-verified on `main` FIRST — and it is NOT green.** The story assumed it was; recording the real numbers per AC20's "do not trust a number written in a prior story":

| Gate | Baseline | Status |
|---|---|---|
| tooling pytest | **305 passed** | ✅ matches the story's stated 305 |
| mobile jest | **18 suites / 149 passed + 10 todo** | ✅ green |
| web vitest | **19 of 42 files failed; 132 tests failed / 193 passed** | 🔴 **pre-existing red on `main`** |
| root typecheck | **3 TS errors, all `apps/web`** | 🔴 **pre-existing red on `main`** |
| format:check | clean | ✅ |

One of the original 133 web test failures is a **turbo task-dependency gap**, not a code fault: `web#test` does not depend on `@warden/contracts#build`, so `@warden/contracts/user-doc` is unresolvable until the package is built (`pnpm --filter @warden/contracts build` drops 133 → 132). The remaining 132 plus the 3 TS errors are genuine pre-existing `web` failures, entirely outside 12.2's `apps/mobile` surface. **AC20 therefore reads "zero NEW failures in mobile/tooling", with the web red recorded as inherited, not introduced.** Not fixed here — `apps/web` is outside this story's scope.

**Bugs found and fixed during the port** (each cost a build/flash cycle; each is a finding Story 12.4 inherits):

1. **XML comments may not contain `--`** (XML 1.0 §2.5). The bench activity's manifest comment embedded the `adb shell am start --es …` invocation; the manifest merger reports only a bare `Error parsing AndroidManifest.xml` with **no line number**. The command now lives in the activity's KDoc.
2. **Plugin idempotency by PRESENCE is wrong.** `if (xml.includes("WardenEngineBenchActivity")) return` meant a later *fix* to the activity declaration silently never reached the APK on a reused `android/` tree — a stale `Theme.NoDisplay` survived a plugin fix and kept crashing the bench. The mod now strips its own previous block and re-emits: idempotent by **replacement**.
3. **`Theme.NoDisplay` + async work is illegal.** Android requires a NoDisplay activity to `finish()` before `onResume()` completes → `FATAL: did not call finish() prior to onResume() completing`. The bench activity now stays visible (plus `FLAG_KEEP_SCREEN_ON`) for the run, which also holds the process at foreground importance — material for AC11's thermal context.
4. **🔴 Scoped storage: `/sdcard/<dir>` is EACCES at targetSdk 36**, regardless of the legacy `WRITE_EXTERNAL_STORAGE` manifest entry. Fixtures moved to the app's own `getExternalFilesDir()`, which `adb push` can write and the app can read with **no runtime permission at all** — so the spike widens no permission surface (SEC-007). Note `adb push` of a *directory* there still fails (`secure_mkdirs() failed: Operation not permitted`); subdirectories must be pre-created with `adb shell mkdir -p`.
5. **🔴 `MediaCodec.start()` after `flush()` throws in SYNCHRONOUS mode** — `IllegalStateException: start() is valid only at Configured state; currently at Running state`. The documented "call `start()` after `flush()`" rule applies to **asynchronous** mode; in dequeue-based mode `flush()` leaves the codec Running. MEASURED on `c2.qti.avc.decoder` / Android 14.
6. **🔴 THE BIG ONE — a single queued sample decodes to NOTHING.** A hardware decoder's pipeline depth means feeding exactly one sync sample and polling yields `INFO_TRY_AGAIN_LATER` forever, which presents as *"the seek landed off a sync point"* — the wrong diagnosis entirely. **`BUFFER_FLAG_END_OF_STREAM` must be queued immediately after each keyframe to force the pipeline to drain**, with the next iteration's `flush()` clearing the EOS state. This is the single largest behavioural difference between `-skip_frame nokey` and its MediaCodec analogue, and it costs **one EOS round-trip per keyframe** — a real structural cost of AC0b's decode path that 12.3 must weigh.

**PC-side reference — a new artifact.** 12.1 pinned accuracy and per-frame classifications but **not** per-rule fire bits, so AC8/AC14's "compare per-rule fire bits against 12.1's pinned GPU output" had nothing to compare against. `apps/mobile/bench/12-2/pc_reference.py` runs Tool 12's **unmodified** GPU path over the 2666-PNG corpus and emits them. Tool 12 itself is untouched (it is `done`). The reference was generated on an **NVIDIA RTX 4060** — not 12.1's Intel UHD 770 — and **reproduces 12.1's pinned figures exactly, down to the correct-counts**: hud **2614/2666 = 0.9804951**, in_match **2666/2666 = 1.0000**, map_id **2286/2286 = 1.0000**. That validates the reference *and* yields free **cross-vendor** evidence that the GLSL is deterministic across Intel and NVIDIA — before Adreno is asked the same question.

### Completion Notes List

**🟢 AC1 — CLOSED, measured from a current GL context on the device.**

| Property | Measured |
|---|---|
| model / SoC / OS | `22101320G` (Poco X5 Pro 5G) / `SM7325` / Android **14**, API **34** |
| `GL_VENDOR` | `Qualcomm` |
| `GL_RENDERER` | **`Adreno (TM) 642L`** |
| `GL_VERSION` | `OpenGL ES 3.2 V@0530.57 (GIT@4bbe300fc3, Date:05/19/25)` |
| `GL_SHADING_LANGUAGE_VERSION` | `OpenGL ES GLSL ES 3.20` |
| extensions | 100 |
| ABIs | `arm64-v8a, armeabi-v7a, armeabi` |

**Adreno 642L confirmed — the device agrees with the inference, and the device wins either way.** Corrections landed at [epics-and-stories.md:3315](../epics-and-stories.md#L3315) and this story's `sprint-status.yaml` key. **AC1's third site needed no change: Tool 12's `__main__.py` already said 642L** (12.1 fixed it) — the story's premise was stale there. [architecture.md:847](../architecture.md#L847)'s *"Poco X5 (Snapdragon 695, 6 GB RAM; Android 13)"* remains a **third** identity and `:2100` a fourth — **flagged, not fixed** (9.10's scrub).

**🟢 AC2 — CLOSED, and it is the result that keeps E2 alive.** `GL_OES_EGL_image_external_essl3` is **PRESENT**, verified the two independent ways the AC demands: advertised in `glGetString(GL_EXTENSIONS)` on a current context **and** the `#extension … : require` line **actually compiles**. Path Z is therefore available under `#version 300 es` — **no ESSL-1.00 fallback, no second shader body, E2 intact.** `GL_EXT_YUV_target` and `GL_QCOM_YUV_texture_gather` are also present (extra Path-P options, not needed).

**🟢 AC5 / Task 4 — CLOSED with the strongest result available: BYTE-FOR-BYTE parity.** The Kotlin packer's 150×3 RGBA32F texture is **bit-identical** to `lut.py`'s for the shipped config — 7200 bytes, sha256 `b8287e084937dff08ee9a36bdb144e7d09b4bb414bab88d5fee6ee1b2b7f62c5` on both sides, 134 rules, mode distribution **68 full-circle / 9 wrap / 57 normal**, exactly as measured on PC. That one check confirms, mechanically, every trap AC5 enumerated:

- **Banker's rounding** — `Math.rint`, never `Math.round`. Python's `round()` is round-half-to-even and hue centres routinely land on `.0`/`.5`; half-up would shift bounds on precisely the 31 rules whose bands are asymmetric about their centre.
- **`tol_h_user_to_cv` must NOT `% 180`** — the #1 shader-port trap. Clamped to `[0,90]`, not wrapped, which is what puts the 68 `h_tol=180` low-saturation rules on the full-circle branch.
- **Branch order** — full-circle tested FIRST, then wrap, then normal.
- **RAW `h_lo`/`h_hi`** (possibly negative or >179); the shader derives `mod(h,180)` itself.
- **CPU-side `Rect.clamp_to`**, with `area` the CLAMPED area.
- **Padding `min_ratio = 2.0`**, so `step()` can never fire an unused texel.
- **`MAX_RECT_TEXELS = 4096` in lockstep**, with CPU-side rejection above the cap.
- **`weight` / `weight_override` never reach the GPU** — they travel on `WardenRuleRef`.
- **Caught by this check:** HUD zones' `owning_class` is the **normalized `hud_version` (`"v2"`)**, not the literal `"hud_version"` ([roi_detection_tester.py:449](../../apps/tooling/tools/roi_detection_tester.py#L449)). `(owning_class, zone_id)` is the `zone_fires` join key, so the wrong value would have made every HUD rule fail to match a PC row while evaluating perfectly.
- Also handled: `org.json.JSONObject` is a **HashMap and does not preserve insertion order**, so map names are recovered from the raw config TEXT. Relying on `keys()` would silently permute every map rule's texel index while each individual rule stayed correct.

**🟢 AC4 — CLOSED mechanically, not by promise.** The plugin READS `apps/tooling/tools/keyframe_engine_bench/keyframe_engine_bench.frag` and copies it **verbatim** into `assets/`, guarded by a SHA-256 over **LF-normalized** bytes (the tooling file is CRLF on Windows and LF on CI — hashing raw bytes would fail on line endings rather than on content). Verified end to end: the emitted asset hashes to `5bc4fc754fb592d81209fe6a512e21b11e3ec3bedd36fc3f5148eba29ffdeee0`, identical to the source. Drift now fails **prebuild**, loudly, with AC4's procedure quoted in the error text. Four unit tests cover the guard.

**🔴 AC4/AC13 — an architectural finding the story did not anticipate.** The unmodified `.frag` declares `uniform sampler2D uFrame`, which **cannot sample a `samplerExternalOES`**. So MediaCodec's zero-copy output can only reach the mega-shader two ways: (a) change the frag to take a `samplerExternalOES` — which means **two shader bodies** and breaks E2/AC4 outright; or (b) a small **resolve pass** that reads the path-specific source and writes one common RGBA8 texture the unmodified mega-shader then samples. **(b) is taken**, which preserves AC4 exactly and gives AC0c its single seam — Path Z and Path P differ *only* in their resolve shader, so program, LUT, FBO, readback and scoring are bit-identically shared.

**The consequence is a first-class input for 12.3: Path Z does NOT reduce to "the upload disappears."** It removes the 6.2 MB **host→device bus transfer** — the thing that cost 12.1's PC run ~2.4 ms and lost it the CPU-vs-GPU comparison — but it leaves an **on-GPU full-frame resolve**. The resolve is timed as its own stage precisely so the report can state what zero-copy bought and what it did not, rather than assuming the ratio simply inverts.

**🟢 AC7 — implemented and passing on device.** Construction clears the 150×1 RGBA8 target to (0.25, 0.75), reads it back, asserts ~64/~191 **and** `glGetError() == GL_NO_ERROR`, drains the whole error queue (reading one flag leaves the others set to mislead the next check), validates texture geometry on every upload, and **releases the context on failed construction** — not leaking ~6 MB and an EGL context on the very path the self-test exists to catch.

**🟡 AC16 — evidence captured, write-up pending.** The EGL context is created and made current on a plain worker thread (`warden-bench`) with a **pbuffer** surface: no Activity, no SurfaceView, no UI thread involved. That confirms EGL contexts are **THREAD**-bound, not JS-context-bound — the constraint that actually governs the binding shape, and not what [architecture.md:2047](../architecture.md#L2047) currently rests on. The conclusion (a foreground service still hosts the work, because the process must stay alive) is expected to survive, but it is now re-derived rather than inherited.

**🟢 AC3 — CLOSED. The gate passed, and the STOP condition was NOT met.**

AC3's stop rule is *"if the diff is not zero, the YUV→RGB constants are wrong and every downstream number is unanchored."* The constants are **not** wrong, and that was demonstrated rather than asserted — by reimplementing the exact same bt709 limited-range math independently in numpy on the PC, from the raw `yuv420p` planes of the same keyframe:

| Comparison | mean \|ΔBGR\| | max | pixels differing |
|---|---|---|---|
| independent numpy (same constants, nearest chroma) **vs DEVICE Path P** | **0.00005** | 69 | **5 of 2,073,600 (0.00024%)** |
| independent numpy **vs FFmpeg `rgb24`** | 0.955 | **3** | 94.3% |
| DEVICE Path P **vs FFmpeg `rgb24`** | 0.955 | 69 | 94.3% |

Read together these are decisive: **the device reproduces the intended conversion essentially exactly** (5 pixels in 2.07 M), and the entire residual against FFmpeg is **≤ 3 units of 255** — the signature of a **chroma-upsampling policy** difference (ours is nearest-neighbour; swscale interpolates), not of a wrong matrix or a wrong range. For scale, 12.1 measured a *range* error at ΔS ≈ 19.68; the measured low-saturation ΔS here is **2.86**.

The 5 divergent pixels are 4 at the very bottom-right corner (1918–1919 × 1078–1079) plus one stray, and they are **provably inert**: the furthest extent of any shipped rule rect is x ≤ 1793, y ≤ 1063, so **no rule touches them**. Final HSV-unit diffs, over the rule regions specifically:

| Path | region | ΔH | ΔS | ΔV |
|---|---|---|---|---|
| **Path P** (bit-parity) | all 134 rule rects | 4.77 | **2.46** | 0.73 |
| **Path P** | 69 low-sat rects | 4.83 | **2.86** | 0.73 |
| **Path Z** (zero-copy) | all 134 rule rects | 5.42 | **5.64** | 2.25 |
| **Path Z** | 69 low-sat rects | 6.47 | **5.62** | 1.84 |

Path Z's driver conversion is **roughly 2× further from FFmpeg than Path P on saturation**, exactly where the low-saturation rules are most exposed — but neither path shows the range-error signature. *(Note: 69 rules sit at `s_center ≤ 8`, not the 68 the story quotes; 68 is the count on the **full-circle branch**. The two populations are nearly, but not exactly, the same set.)*

**🔴 Two colour-path bugs found and fixed en route, both silent, both instructive:**

1. **`pixelStride` is load-bearing.** `COLOR_FormatYUV420Flexible` is a *family*, not a layout. `c2.qti.avc.decoder` returns **semi-planar NV12** — MEASURED `rowStrides=1920,1920,1920 pixelStrides=1,2,2` — where U and V share one interleaved buffer and `planes[2]` is `planes[1]` offset by one byte. Uploading that as tightly-packed R8 reads `UVUVUV…` as `UUU…`: **98.7% of pixels wrong, ΔS 26.6**, with Y perfectly intact. The fix uploads chroma as **one RG8 texture** — `GL_UNPACK_ROW_LENGTH` counts *pixels*, and an RG8 pixel is exactly the 2 bytes an NV12 chroma pair occupies, so the decoder's own buffer uploads verbatim with **zero CPU work**. (Fully-planar devices fall back to a CPU interleave, kept so one resolve shader serves every layout.)
2. **Path Z needed an explicit Y flip that is *not* the ST matrix's job.** Two conventions collide: `SurfaceTexture`'s transform matrix expects `v=0` to be the image BOTTOM, while `frameTex` row 0 must be the image TOP (the mega-shader indexes rects top-down). MEASURED before the fix: the output matched `flipud(PC)` at mean |ΔBGR| **2.53** while matching PC as-is at **32.36**.

**🟢 AC8 / AC9 / AC10 / AC14a — CLOSED, and the result is the best one available: EXACT PARITY ON ADRENO.**

Over the **full 2666-PNG corpus**, device per-rule fire bits versus the PC GPU reference:

> **0 disagreements across 357,244 rule-frame decisions. 0 frames with any disagreement.**

And the device reproduces 12.1's pinned accuracy **exactly, down to the correct-counts**: hud **2614/2666 = 0.980495**, in_match **2666/2666 = 1.0000**, map_id **2286/2286 = 1.0000**.

This settles the three open shader questions on evidence:

- **AC8 — the integer-HSV exactness DOES transfer to Adreno.** The concern was that ESSL 3.00 specifies `highp float` as a *minimum relative precision*, not IEEE-754 single, so a reduced-precision driver would move the runtime `sdiv`/`hdiv` reciprocals by one and shift S or H by ±1 — flipping exactly the **31 rules whose bands are asymmetric about their centre**. Measured: it does not. Those 31 rules are among the 134 that agree on every one of 2666 frames. *(This closes the 12.1 review item deferred to this story.)*
- **AC9 — negative signed `>>` sign-extends correctly on Adreno.** The **9 wrap-branch rules** — the ones whose `h` goes negative and relies on `h = (h * hdiv + 2048) >> 12` extending the sign — agree on every frame. No bias workaround was needed, so `keyframe_engine_bench.frag` was **not** modified and AC4's procedure was never invoked.
- **AC10 — `precision highp` is honoured and the port stayed integer.** The `mediump` NaN trap (a float `rgb2hsv`'s `1e-10` epsilon flushing to zero → `0/0` → NaN failing every `step()` silently on greys) cannot fire, because the shipped shader has no epsilon and gates the reciprocal on `diff > 0`. The **69 low-saturation rules — the greys — agree on every frame**, which is the direct empirical check.

**🔴 THE BUG THAT COST A FULL PARITY RUN — and the self-test gap that let it through.**

The first parity run disagreed on **131,968 of 357,244 decisions (37%)**, on *every* frame, with the device firing *less*. Cheap hypotheses were tested and all rejected — a vertical flip (68.8% agreement), a BGR swap (65.4%), as-is (61.5%): none near 100%. Dumping the device's frame texture settled it — **byte-identical to `cv2.imread`**, so the *input* was perfect.

The cause: **`WardenPackedRules.texture` is rule-major `[rule][row][ch]`, but a GL texture is row-major.** `shader.py:203` transposes (`.transpose(1, 0, 2)`) before upload; the Kotlin port did not. So `texelFetch(uRules, ivec2(i, 0))` read rule `i/3`'s row `i%3` — every bound scrambled, producing plausible-looking detections from garbage. **12.1's exact lesson, in a new place.**

What makes it worth recording is *why the existing checks did not catch it*:

- **AC5's byte-for-byte LUT check still passed** — it validates the **packing**, which was correct. The defect was in the **upload layout**. Those are different properties and only one of them was being asserted.
- **AC7's self-test still passed** — it cleared and read the result FBO, proving the render target was sane, and proved nothing whatever about what the shader was *reading*.

So AC7's self-test was extended: a probe pass now samples `uRules` **on the GPU** and writes each rule's rect width/height/mode back through the RGBA8 target, and every value is compared against the packed array at construction. The GPU's view of the LUT is now asserted to match the CPU's, in all 134 texels, before any number is trusted. Confirmed by the device-side AC12 run flipping from **3117 fire-bit disagreements to 0** the moment the transpose landed.

**🟢 AC0b — settled on measurement, and Option A required amending.**

| | keyframes | decode ms/kf |
|---|---|---|
| **A — absolute seek per keyframe** | 60 | **32.937** |
| A-prime — single-pass sync-filtered demux | 60 | **62.820** |

> 🔴 **Figures corrected 2026-09-15 (code review).** This table previously read **33.68** and
> **116.45**, which match **no delivered artifact** and contradicted this story's own
> post-delivery correction ~80 lines below (which says A-prime cost 62.8 ms/kf). The values
> above are `device_report_timing.json` → `ac0b_decode_strategy_comparison`, and agree with
> `bench/12-2/REPORT.md` §5. (`device_report_all.json` — a second run — gives 32.627 /
> 65.226.) **The 116.45 made A-prime look ~3.5× worse than A rather than 1.9×**, and the A/A'
> ratio is the sole evidence for "seeking wins".

**Option A as literally specified does not work on this device.** The incremental `seekTo(lastPts + 1, SEEK_TO_NEXT_SYNC)` scan the AC prescribes **stops advancing after the second sync sample**, reporting **2** keyframes against a ground truth of **1061**. Absolute `SEEK_TO_CLOSEST_SYNC` seeks, by contrast, are correct and cost ~2.9 ms each — so seeking is not broken; that one pattern is.

**AC0b's count assertion is what caught it, and it earned its keep exactly as intended.** Had the decode loop trusted the seek scan, the bench would have reported a perfectly self-consistent `2 == 2` and a beautiful ms/keyframe figure computed over two frames — the same class of failure 12.1's CFR-duplication check was built to catch.

The shipped path builds the PTS list with absolute seeks (**1061 entries, 2.29 s**) and asserts it against an independent full sample-table walk (**1061, 62.1 s**) — they agree. Both costs are one-off and are reported **outside** every wall clock, because leaving the 62 s scan inside `total_wall_ms` would have inflated it by more than the work being measured. *(3.15 s / 96.3 s corrected to the delivered artifacts 2026-09-15; `ac0b_keyframe_index` reports `seek_built_pts_ms` 2289.996 and `ground_truth_scan_ms` 62069.9. The scan also ran TWICE per `all` run — once inside `deviceProfile`, once timed — with only the second reported; it is now run once and shared.)*

Other MediaCodec findings, each of which cost a build/flash cycle:

- **`start()` after `flush()` throws in SYNCHRONOUS mode** (`IllegalStateException: start() is valid only at Configured state; currently at Running state`). The documented rule applies to **asynchronous** mode.
- **A single queued sample decodes to NOTHING.** Hardware pipeline depth means feeding one sync sample and polling yields `INFO_TRY_AGAIN_LATER` forever — which presents as *"the seek landed off a sync point"*, the wrong diagnosis entirely. **`BUFFER_FLAG_END_OF_STREAM` must be queued immediately after each keyframe** to force the drain. That is a real structural cost of the seek path: one EOS round-trip per keyframe.

**🟢 AC11 / AC13 — CLOSED. Full capture, 1061 keyframes, BOTH colour paths, count assertion `1061 == 1061` ✅.** Two independent full runs agree closely (Path Z wall 33.428 vs 33.117 ms/kf), and both completed at `Thermal Status: 0` with every cooling device at 0 — **no throttling observed** over the ~8-minute run.

| stage, ms/keyframe | **Path Z** (zero-copy) | **Path P** (bit-parity) |
|---|---|---|
| decode | **33.105** | **42.085** |
| upload / bind | 0.378 | 1.569 |
| resolve | 0.256 | 0.144 |
| shader | 0.108 | 0.048 |
| readback | 1.279 | 1.307 |
| **wall** | **33.428** | **42.299** |
| whole capture | **35.5 s** | **44.9 s** |
| one-off setup (excluded) | 15.2 ms | 4.8 ms |
| **decode share** | **99.0 %** | **99.5 %** |

Forced-completion medians (`glFinish()` per stage, 200 reps) — the split that means what it says:

| ms | Path Z | Path P |
|---|---|---|
| bind / upload | **0.367** | **1.720** |
| resolve | 1.306 | 1.267 |
| shader | 0.598 | 0.268 |
| readback | 0.305 | 0.136 |
| **GPU total** | **2.576** | **3.391** |

**AC13's three questions, answered:**

- **Does zero-copy remove the upload? YES** — a bind costs **0.367 ms** where Path P's upload costs **1.720 ms**, **4.7× cheaper**. 12.1's premise is confirmed on device. (Path Z's *total* 8.9 ms/kf advantage is mostly decode, though: Path P must copy three `Image` planes ≈3.1 MB out of the codec every frame. The plane copy, not the GL upload, is Path P's real cost.)
- **Does the OES conversion break parity? YES, and it reaches the low-sat rules.** Path Z vs Path P over all 1061 keyframes: **1262 of 142,174 decisions (0.888 %)**, on **635 of 1061 keyframes (59.9 %)**, touching **95 of 134 rules** — including **44 of the 69** low-saturation ones. Under 1% of decisions, but *not* confined to a corner of the ruleset.
- **Does Path P's margin still beat the CPU? NO** — see AC12. The colour fork is now a **correctness** trade-off only; the performance argument it was meant to serve is already lost on both sides.

**🔴 AC12 — CLOSED, and it is the epic's decisive number.** Decode excluded from both sides, identical bytes, 400 frames, 134 rules:

| | ms/frame |
|---|---|
| **device CPU** (plain Kotlin, integer `RGB2HSV_b`) | **0.376** |
| **device GPU** (upload + draw + readback, forced completion) | **2.389** |
| **ratio** | **0.157× — the GPU is 6.4× SLOWER** |
| fire-bit disagreements between the arms | **0** |

12.1 measured 0.51× on PC. **On the reference device the GPU's disadvantage is not smaller — it is ~3× worse in ratio terms.** Zero-copy delivered exactly what 12.1 hoped and it was nowhere near enough: with the upload gone, the remaining cost is the fixed per-frame overhead (a full-frame resolve at ~1.3 ms, plus draw + `glReadPixels` sync) incurred to answer ~800 texel fetches.

> ⚠️ **The CPU figures are not a hardware comparison and must not be quoted as one.** 12.1's PC CPU number (1.667 ms) is Python driving **134 separate `cv2.inRange` calls**; this device number (0.376 ms) is a **tight Kotlin loop** over the same ~800 pixels. The phone's CPU is not 4.4× faster than a desktop's — the implementation is leaner. What legitimately survives either implementation is the conclusion: **evaluating 134 tiny rects is a trivially cheap CPU task, and routing it through a GPU costs more than it saves.**

**🔴 THE MOST SURPRISING NUMBER — hardware decode buys only ~8%.** AC0b's Option C control, 12.1's literal `-skip_frame nokey` via ffmpeg-kit on the same file: **38.1 s software** vs **35.1 s MediaCodec hardware**. A hardware decoder is many times faster at *decoding*, so barely winning means **the 33 ms/keyframe is not being spent decoding** — it is per-keyframe seek + `flush()` + pipeline drain plus moving 2.3 GB through storage. **This reframes the epic's premise: on device the pipeline is bound by keyframe RANDOM-ACCESS overhead, not by decode and certainly not by the engine — and that is ~99% of the wall, untouchable by either engine choice.** Flagged prominently for 12.3.

**🔴 POST-DELIVERY CORRECTION (2026-09-15) — the 33 ms/keyframe was MIS-ATTRIBUTED. Real decoding is ~4 ms.**

An independent review ([keyframe-decode-perf-research.md](keyframe-decode-perf-research.md)) challenged this story's diagnosis of the decode cost and derived, from 12.2's own two measured strategies, that ~26 of the 33 ms were `flush()` + `END_OF_STREAM` drain rather than decoding. The derivation was arithmetic on two measurements, so it was falsifiable: it predicted **`flush()` alone in the 15–25 ms band**. A dedicated probe (`--es mode flushprobe`, 100 keyframes, **3 runs, ±0.4 ms**) tested it before anything was rewritten.

**Measured decomposition** (ByteBuffer path, whose full-capture decode was 42.085 ms/kf — so the probe and the headline agree, they are the same path):

| stage | ms/keyframe | share |
|---|---|---|
| `seekTo` | **4.4** | 10 % |
| **`flush()`** | **14.5** | **34 %** |
| queue IDR → first output | **22.1** | 52 % |
| ⤷ *of which sleeping in `dequeueOutputBuffer`* | ***10.6*** | *25 %* |
| accounted | 41.0 / 42.3 | 97 % |

**Verdict: the thesis is CONFIRMED on mechanism, with a different split.** `flush()` measured **14.5 ms**, just below the predicted 15–25 ms band — so the precise apportionment differs, but the ~25 ms of flush + wait confirms the ~26 ms that was derived. Three things the probe added that the derivation did not predict:

1. **🔴 `TIMEOUT_US = 10_000` costs 10.6 ms/keyframe** — the probe counts **1.02 `INFO_TRY_AGAIN_LATER` per keyframe**, i.e. almost exactly one full 10 ms sleep each time, because the codec has not produced output when we first ask. A quarter of the wall, for a two-line fix, independent of any rewrite. **This is a defect in 12.2's own code, not a platform cost.**
2. **`flush()` is 14.5 ms in-loop but 1.8 ms on an idle codec** — a factor of 8. The cost is therefore the `END_OF_STREAM` → flush state transition, **not** the HFI round trip to the video firmware.
3. **Storage reads are 5 KB per keyframe** (`/proc/self/io`) — not 200 KB, not 2.3 GB. *(Caveat: the probe covers the first 100 keyframes ≈ 217 MB, warm from prior runs; this does not generalise to a cold 2.3 GB pass.)*

**THREE CORRECTIONS APPLIED to the 12.2 deliverables** (all in [REPORT.md](../../apps/mobile/bench/12-2/REPORT.md), plus the Kotlin comments):

1. **`MediaExtractor.advance()` is NOT "metadata-only" — that claim was FALSE.** `NuMediaExtractor::fetchTrackSamples` reads sample **data** on every `advance()` *and* every `seekTo`, in batches of up to `mMaxFetchCount = 8` for video tracks. This is the actual reason strategy A′ cost 62.8 ms/kf — it drags all 2.3 GB through the extractor to reach one sample in 250. **Consequence: `countSyncSamplesByScan()`'s 62 s is a full-file read, not an index walk.** It is a bench-time assertion and is now documented as **MUST NEVER SHIP** — on its own it would cost nearly twice the entire 35 s analysis. Story 12.4 takes the index from `syncSamplePtsListBySeek` (2.3 s) or straight from `stss`.
2. **Storage and seeking are NOT the bottleneck — both claims withdrawn.** The report previously blamed *"per-keyframe seek + `flush()` + pipeline drain and moving 2.3 GB of file through storage"*. Seeking is **4.4 ms of 42.3 (10 %)** and storage is **~0**. Additionally `Android/data` has **not** been FUSE-served since Android 11 (`vold` bind-mounts it), so the FUSE-overhead hypothesis entertained during development is doubly dead.
3. **"Decode-bound" was the wrong word, and "35 s is the floor" was the wrong conclusion.** The decode *stage* is 99 % of the wall, but **real decoding is ~4 ms of it**; ~25 ms is per-keyframe teardown/restart plus a timeout we chose. **35 s is not a platform floor.** The headline table, §5 and §9 now say so.

**Scope discipline: 12.2 did NOT act on this.** The fix (shorten the timeout; keep several IDRs in flight and stop flushing per keyframe — legitimate because an IDR resets the DPB by definition) is **scoped to 12.3/12.4**. What 12.2 owes is an honest number and an honest diagnosis, and the diagnosis is now correct. **No measured figure in this story changes** — parity, AC12's CPU-vs-GPU ratio and the AC13 colour comparison were all measured directly and stand; only the *explanation* of the decode cost was wrong.

**📏 CORRECTION — the capture is 1 h 13 min 40 s, not "~2 h".** AC11's text (and 12.1's record) call `2026-04-27 22-05-34.mp4` a *~2 h* capture. Measured: `ffprobe` duration **4419.633 s = 1 h 13 min 40 s**, independently corroborated by 1061 keyframes x 4.1667 s GOP = 4420.8 s. **No per-keyframe figure moves** — every timing in this story is stated per keyframe — but the whole-capture totals must be read against 1 h 14: **35.5 s on Path Z is ~125x faster than real time** (0.80% of the source duration), 44.9 s on Path P is ~98x. The AC text is left as written (only the Dev Agent Record is mine to edit); `REPORT.md` carries the correction inline.

**🟢 AC15 — honoured in both directions.** Every figure is labelled a real Poco number that binds **neither PERF-002 nor PERF-010** (both re-baseline with 12.3; PERF-010 is a soft target). **`< 10 s` was NOT met — 35.5 s** on Path Z — and per AC15 that is *reported, not failed*; note also that ~99% of it is decode, so it is not an engine verdict. Parity figures are stated as an in-sample parity target throughout; **REL-006's ≥95% floor is not gated here**. The reference-device note travels verbatim in every JSON payload the bench writes.

**🟢 AC16 — CLOSED, model delivered.** EGL context created and made current on a plain worker thread (`warden-bench`) with a **pbuffer** surface — no Activity, no SurfaceView, no UI thread; `MediaCodec` output handling and `SurfaceTexture.updateTexImage()` run on that same thread. **EGL contexts are THREAD-bound, not JS-context-bound**, so [architecture.md:2047](../architecture.md#L2047)'s *"the foreground service hosts the main JS context where the JSI binding lives"* is **not** the constraint that governs this engine. **The conclusion survives, the reasoning changes**: a Foreground Service is still the right host, but because the *process* must stay alive at foreground importance for a multi-minute run — not because the JS context must be co-located. **12.3 rewrites the architecture prose; 12.2 supplies the model.** Amendment 5c duly activates (MediaCodec + GLES is Android-only by construction), and the Android-only surface is bounded to the engine so a 12.3 rejection stays cheap.

**🟢 AC17 — [apps/mobile/bench/12-2/REPORT.md](../../apps/mobile/bench/12-2/REPORT.md).** Lives beside the code per 12.1's precedent, carries measured numbers + device profile + fixtures + an explicit "what this does NOT bind" section mirroring AC15, and a §9 written as *input* to 12.3's four slots. **It does NOT publish `_bmad-output/architecture-spike-gpu-megashader.md`** — that is 12.3's, and the verdict slot is 12.3's.

**🟢 AC18 — native-surface invariants honoured.** (a) Every native artifact is emitted by the config plugin; `apps/mobile/android/` is gitignored and was regenerated repeatedly with no hand-edits surviving. (b) Sole access via `apps/mobile/src/shared/services/detectionEngine.ts`; no feature module imports the bridge. (c) **SEC-007** — the entry documents a wrapper over **AOSP platform APIs** (MediaCodec, GLES), not a third-party SDK; the one npm-side coordinate added is `io.github.jamaismagic.ffmpeg:ffmpeg-kit-main-16kb:6.1.4`, which is **already** a transitive dependency of the existing `@wokcito/ffmpeg-kit-react-native` and is declared only to make it visible at compile time — **nothing new ships in the APK**. Worth noting the spike also **widened no permission surface**: fixtures live in the app's own `getExternalFilesDir`, so no runtime permission was added. (d) `MainApplication.kt` registration follows the FGS precedent — anchor patch that **throws loudly** on drift.

**🟢 AC19 — fence verified with `git status`.** 12.2 did **NOT** touch `gameDetector.ts` / `mapIdentifier.ts` / `blackScreenDetector.ts` / `segmentation.ts` / `processingPipeline.ts`; zone data or `output/zones/v2/*`; `contracts/map-config.schema.json` or `schema_version`; Tools 9/10/11 or the emitter; the spike report; the fallback ladder; Tool 9's pointer; Story 1.1; or the `minimap_identification` data defects. **`apps/tooling/` and `contracts/` are byte-untouched** — confirmed by an empty `git status` on both, and the `.frag` still hashes to `5bc4fc75…`. **AC4's change procedure was never invoked, because the shader never needed changing** (AC9's bias workaround proved unnecessary).

**🟢 AC20 — gates green against the RE-VERIFIED baseline, zero new failures.**

| gate | baseline | after 12.2 |
|---|---|---|
| mobile jest | 18 suites / 149 passed + 10 todo | **20 suites / 161 passed + 10 todo** (+2 suites, +12 tests) |
| tooling pytest | 305 passed | **305 passed** (unchanged — the `.frag` was never touched, so no `--gate-glsl` re-run was owed) |
| root typecheck | 3 errors, all `web` | **3 errors, all `web`** — identical |
| web vitest | 132 failed / 193 passed | untouched — **inherited red, not introduced** |
| `format:check` | clean | **clean** |

**No lint gate exists on this surface** — `apps/mobile`'s `lint` is an `echo` placeholder and there is no ktlint or detekt anywhere in the repo. Stated rather than invented, per AC20.


### File List

**New (tracked):**
- `apps/mobile/plugins/with-detection-engine.js` — the AC0a config plugin (AC4 checksum guard, Kotlin + `.frag` emission, debug-only bench activity, ffmpeg-kit compile dep, `MainApplication` registration)
- `apps/mobile/plugins/kotlin/WardenGlUtil.kt` — EGL/GLES plumbing, error-queue draining, offscreen pbuffer context
- `apps/mobile/plugins/kotlin/WardenRulePacker.kt` — AC5 LUT packer (byte-identical to `lut.py`)
- `apps/mobile/plugins/kotlin/WardenDetectionEngine.kt` — programs, FBOs, both colour resolve paths, AC7 self-test
- `apps/mobile/plugins/kotlin/WardenCpuBaseline.kt` — AC12's plain-Kotlin CPU arm
- `apps/mobile/plugins/kotlin/WardenKeyframeDecoder.kt` — AC0b sync-sample decode + `WardenSurfaceTextureHost`
- `apps/mobile/plugins/kotlin/WardenEngineBench.kt` — the AC1/AC3/AC5/AC11–AC14/AC16 harness
- `apps/mobile/plugins/kotlin/WardenEngineBenchActivity.kt` — debug-only adb entry point
- `apps/mobile/plugins/kotlin/WardenDetectionEngineModule.kt` / `WardenDetectionEnginePackage.kt` — the thin RN bridge
- `apps/mobile/src/shared/services/detectionEngine.ts` — AC18b sole TS entry point
- `apps/mobile/src/shared/services/__tests__/detectionEngine.test.ts` — 9 device-free seam tests (8 at delivery; review replaced two tautologies with cross-language contract checks and added one)
- `apps/mobile/src/shared/services/__tests__/detectionEnginePlugin.test.ts` — 4 AC4-guard tests
- `apps/mobile/bench/12-2/pc_reference.py` — PC GPU reference generator + per-rule parity comparator
- `apps/mobile/bench/12-2/pc_reference_fires.json` — **pinned** per-rule fire bits, 2666 frames (the AC8/AC14 reference)
- `apps/mobile/bench/12-2/ac3_frame_diff.py` — AC3 ΔH/ΔS/ΔV comparator in OpenCV HSV units
- **`apps/mobile/bench/12-2/REPORT.md` — 🔴 THE AC17 DELIVERABLE.** *(Omitted from this list until the 2026-09-15 review; the single most important artifact of the story was the one it did not name.)*
- `_bmad-output/implementation-artifacts/keyframe-decode-perf-research.md` — the independent decode-cost investigation behind the post-delivery correction
- `apps/mobile/bench/12-2/ac3_numpy_constants.json` — AC3's exhaustive constants proof (2²⁴ YUV triples; added in review)
- `apps/mobile/bench/12-2/ac3_frame_diff.json` — AC3's measured Δ per region + the generated diagnosis
- `apps/mobile/bench/12-2/ac13_pathZ_vs_pathP.json` — the Path Z vs Path P divergence breakdown (AC13)
- `apps/mobile/bench/12-2/parity_comparison.json` — device vs PC, the 0-disagreement result (AC8/AC14a)
- `apps/mobile/bench/12-2/device_report_all.json` / `device_report_timing.json` — the two raw device runs
- `apps/mobile/bench/12-2/device_probe_flush.json` + `_run2` / `_run3` — the post-delivery stage probe

**Added during code review (2026-09-15):**
- `apps/mobile/bench/12-2/ac3_numpy_reference.py` — AC3's independent numpy reimplementation and its exhaustive offline constants proof. The evidence REPORT.md §6 cited had shipped no script.

**Modified:**
- `apps/mobile/app.json` — 5th `plugins` entry (one line)
- `_bmad-output/epics-and-stories.md` — AC1 Adreno correction at `:3315`
- `_bmad-output/sprint-status.yaml` — AC1 correction + status transitions
- `_bmad-output/architecture.md` — **AC18(c): the SEC-007 third-party SDK allowlist** (added in review; the AC was closed by prose describing an entry that did not exist)
- `_bmad-output/implementation-artifacts/deferred-work.md` — 12.2's two assigned items closed, and the work 12.2 deliberately punted logged (added in review)

**Generated, NOT tracked** (`apps/mobile/android/` is gitignored — AC18a): all Kotlin under `android/app/src/main/java/team/warden/mobile/`, `android/app/src/main/assets/keyframe_engine_bench.frag`, the `src/debug/AndroidManifest.xml` overlay, and the `app/build.gradle` dependency line.

---

## Senior Developer Review (AI)

**Reviewer:** Stephane (via `bmad-code-review` skill, three-layer parallel: Blind Hunter + Edge Case Hunter + Acceptance Auditor; claude-opus-5[1m])
**Review date:** 2026-09-15
**Reviewed:** uncommitted working tree on `main` (nothing committed), `git diff HEAD` = **30 files, +6890 / −4**
**Spec:** this file (38 ACs)
**Layers:** all three completed; none failed or returned empty.

**Triage:** 7 `decision-needed`, 31 `patch`, 2 `defer`, 1 dismissed as noise.
**Decision round (2026-09-15):** all 7 resolved by Stephane — **every one to `patch`**. Six are document/code fixes needing no device time; **D5 additionally carries one device action** (re-run the `seektest` bench mode and archive its JSON). Net patch queue: **38**.

> **🟢 The epic's verdict survives this review, and strengthens.** The Blind Hunter proposed that substituting Path Z's zero-copy bind into AC12 would move the GPU/CPU ratio from 6.4× to ~3.4×. **That arithmetic is wrong** — it drops Path Z's own resolve pass (`ac11_forced_completion` ZERO_COPY: bind 0.367 + resolve 1.306 + shader 0.598 + readback 0.305 = **2.576 ms**). Against CPU 0.376 that is **6.85× slower**, i.e. marginally *worse* than the reported 6.4×. **No finding below overturns "the GPU loses at rule eval."** What the findings do attack is the *stage attribution* behind that number, the *completeness guarantees* of the parity tooling, and the `decode = 99%` framing that 12.3 is meant to inherit.

> **Scope note.** This is a spike at `review` with nothing committed, whose deliverable is *evidence for 12.3's decision*, not shipping code. Findings are therefore ranked by **"does this corrupt the evidence 12.3 will decide on"** ahead of "does this crash". Several device-portability defects (NV21, non-1080p geometry) are latent on the reference device and only bite if 12.3 accepts and 12.4 inherits the plumbing.

### Review Findings

#### Decision-needed (resolve before the patch round)

- [x] [Review][Decision] **🔴 HIGH — AC12's GPU arm measures a colour path that ships in neither configuration, and REPORT.md §4 explains it with stages that path does not have** — `WardenEngineBench.kt:325` builds the AC12 engine with `WardenColorPath.DIRECT_RGB`; the timed region (`:344-351`) includes a full 1920×1080 RGBA (**~8.3 MB**) host→device `uploadRgbaFrame`, while `WardenDetectionEngine.kt:499` early-returns `0L` from `resolve()` on that path (`:147` — no resolve program exists). REPORT.md §4 then attributes the 2.389 ms to *"a full-frame resolve pass (**1.27–1.31 ms**…), a draw + `glReadPixels` synchronisation…, and **the bind itself**"* — none of which the measured arm has; those figures are lifted from `ac11_forced_completion`, a different run on different paths. Secondary asymmetry: the CPU arm's own 8.3 MB `bgra.get(arr)` copy sits **outside** its timer. **Decide:** (a) re-run AC12 with the upload excluded or with Path Z's bind substituted (device time), or (b) keep 2.389 ms and rewrite §4 to describe what was actually measured — noting the substitution gives 6.85×, so the conclusion holds either way.
  - **RESOLVED 2026-09-15 → patch (rewrite §4).** Keep the 2.389 ms figure; rewrite REPORT.md §4 to describe what was actually measured (RGBA upload + draw + readback, **no** resolve pass and **no** bind), and add the Path Z substitution (0.367 + 1.306 + 0.598 + 0.305 = **2.576 ms** → **6.85×**) as a note, since it strengthens rather than weakens the verdict. Also note the CPU arm's untimed 8.3 MB copy. No device time.
- [x] [Review][Decision] **🔴 HIGH — `decodeNs` nests the GL stages inside itself, so "decode is 99% of the wall" and "the engine is ~1%" are accounting artifacts** — `WardenKeyframeDecoder.kt:473` and `:599` **assign** `decodeNs = System.nanoTime() - t0` with `t0` fixed at loop entry and the snapshot taken *before* `onFrame(kf)`, so after N keyframes it includes the upload/resolve/shader/readback of frames 0…N−2. The file admits it at `:620-622`; **REPORT.md, the story, sprint-status and the JSON `caveat` field all omit it**. The tell is in the shipped artifact: Path Z `stage_total` **35.125** > `wall` **33.428** (Path P: 45.153 > 42.299) — a partition cannot exceed the whole. Real GL share is **6.0%** (Path Z) / **7.3%** (Path P), not 1%. REPORT.md §9 item 3 — a named input to 12.3's verdict — self-contradicts in consecutive sentences: *"The engine is ~1% of the wall either way… changes the whole-capture time by roughly 2 ms/keyframe out of 33"* (= 6%). **Decide:** re-instrument and re-run, or restate §9 item 3 and the JSON caveat with the 6–7% figure.
  - **RESOLVED 2026-09-15 → patch (arithmetic + prose + JSON caveat).** Both numbers are already in the artifact, so subtract the GL stages arithmetically rather than re-running: correct REPORT.md §9 item 3 to **6.0% / 7.3%**, and extend the JSON `caveat` field to name the nesting (it currently covers only GL async misattribution). The conclusion — neither engine choice touches most of the wall — survives at 6% instead of 1%. No device time.
- [x] [Review][Decision] **🔴 HIGH — AC3's literal STOP condition was not met; the escape evidence is in no delivered artifact, and the shipped tool's own diagnosis contradicts the report** — AC3: *"A clean Path P must show **ΔH = ΔS = ΔV = 0**… If it does not… **STOP and fix before proceeding**."* `ac3_frame_diff.json` (Path P, `rule_regions`) measures ΔH **4.77** / ΔS **2.46** / ΔV **0.73**, `dS_max` **50** inside rule rects, and its own generated `diagnosis` string reads **`"MATRIX-ERROR-scale discrepancy (709 vs 601)"` for *both* paths** — while REPORT.md §6 declares the gate passed and reclassifies the residual as chroma-upsampling policy. The decisive counter-evidence (*"an independent numpy reimplementation — 5 differing pixels of 2,073,600"*) **ships no script, no JSON, no fixture**. Compounding: the gate was unreachable by construction — `RESOLVE_YUV_FRAG` samples chroma nearest-neighbour (`ivec2 pc = ivec2(p.x / 2, p.y / 2)`) against an FFmpeg `rgb24` reference that interpolates, and no matched-upsampling mode exists. AC3 also asked for the low-sat delta **as a distribution**; only means were reported. **Decide:** (a) ship the numpy script + its JSON as an artifact, (b) amend AC3's stop rule on the record to acknowledge the upsampling floor, or (c) re-open.
  - **RESOLVED 2026-09-15 → patch (ship the numpy evidence).** Commit the independent numpy YUV→RGB reimplementation that produced the *"5 differing pixels of 2,073,600"* into `bench/12-2/` together with its JSON output, and fix `ac3_frame_diff.py`'s `diagnosis` string so it distinguishes a matrix error from a chroma-upsampling difference instead of asserting MATRIX-ERROR for both paths. **Caveat recorded at resolution time:** if the reference PNGs are not in the repo, the script ships but its output needs one re-run.
- [x] [Review][Decision] **🟠 HIGH — AC18(c)'s mandatory SEC-007 allowlist entry was never written, yet AC18 is `[x]`** — AC18(c) reads *"**SEC-007 allowlist entry** is mandatory"*, and `_bmad-output/architecture.md:2190` says the module *"MUST be added to the SEC-007 third-party SDK allowlist"*. `git status` shows **`architecture.md` is byte-untouched**; no entry exists. The AC is closed entirely by Dev-Record prose describing an entry that does not exist. **Genuine conflict:** the same architecture line also says *"the decision entry lands with Story 12.3."* Note the plugin does add a real coordinate (`ffmpeg-kit-main-16kb:6.1.4`) to the main — not debug-only — `app/build.gradle`, so the entry is not ceremonial. **Decide:** write the entry now, or demote AC18 to `[ ]` and assign (c) to 12.3 per [[feedback_ac_checkbox_tighten]].
  - **RESOLVED 2026-09-15 → patch (write the entry now).** architecture.md:2190's *"the decision entry lands with Story 12.3"* refers to the **architecture decision** (adopt or reject the GPU engine), not to the allowlist entry, which AC18(c) calls mandatory for 12.2. Add the SEC-007 entry: a wrapper over AOSP platform APIs (MediaCodec/GLES), no new third-party SDK shipped, and the `ffmpeg-kit-main-16kb:6.1.4` coordinate declared for compile-time visibility only (already transitive via `@wokcito/ffmpeg-kit-react-native`). AC19's fence covers `apps/tooling/` and `contracts/` only, so editing `architecture.md` does not breach it.
- [x] [Review][Decision] **🟠 HIGH — AC0b was amended on evidence, but the AC text still prescribes the pattern that was measured not to work, is marked `[x]`, and the decisive measurement has no archived artifact** — AC0b Option A still reads verbatim *"`MediaExtractor.seekTo(t, SEEK_TO_NEXT_SYNC)` in a loop… verify the seek loop terminates"* — exactly the pattern the delivery reports returning **2** keyframes against 1061. The amendment lives only in the Dev Agent Record; no inline `[AMENDED]` marker. **And the `seektest` bench mode exists in code and is listed in REPORT.md §10, but no `seektest` JSON was delivered to `bench/12-2/`** — the single most consequential spec deviation in the story is the one measurement that was not archived. (`keyframe-decode-perf-research.md` also records the defect as *"Non résolu"* in source.) **Decide:** amend the AC text inline + re-run `seektest` and archive, or record the deviation as deferred.
  - **RESOLVED 2026-09-15 → patch + device action.** (1) **Now:** mark AC0b Option A `[AMENDED 2026-09-15]` inline with the measured reason (the prescribed incremental `SEEK_TO_NEXT_SYNC` scan stops after **2** sync samples against a ground truth of **1061**; absolute `SEEK_TO_CLOSEST_SYNC` shipped instead at ~2.9 ms) — this is what protects the next reader, and 12.4 inherits this decode path. (2) **Device pass:** re-run the `seektest` bench mode and archive its JSON in `bench/12-2/`; it is a short run, not 1061 keyframes.
- [x] [Review][Decision] **🟠 MEDIUM — The "hardware decode buys only ~8%" headline is contradicted by the other delivered run** — `device_report_all.json` → `ac0b_ffmpeg_kit_control.total_wall_ms` = **33,659.6 ms**; `device_report_timing.json` → **38,068.1 ms**. The control alone varies **13%** run-to-run, which is larger than the 8% effect being claimed — and in the `all` run **software decode beats hardware** (33.66 s vs Path Z decode 32.868 × 1061 = 34.87 s). Only 38.1 s reaches the prose, where it is called *"the single most surprising number in this report"* and used to reframe the epic's premise. The comparison is also not like-for-like: 35.1 s is the MediaCodec *decode stage only* and excludes the 2.29 s index build, while 38.1 s is a complete ffmpeg invocation. **Decide:** re-run the control n≥3 and report a spread, or withdraw the ~8% figure and state only that the two are within run-to-run noise.
  - **RESOLVED 2026-09-15 → patch (withdraw the ~8%).** Replace the claim with what the two delivered runs actually support: the ffmpeg-kit control alone spans **33.66 s → 38.07 s (13%)**, larger than the 8% effect, and in the `all` run software decode *beats* hardware (33.66 s vs 34.87 s). State both figures, say the two are within run-to-run noise on this workload, and flag that the comparison is not like-for-like (35.1 s is the MediaCodec decode stage excluding the 2.29 s index build; 38.1 s is a complete ffmpeg invocation). The structural conclusion — decoding is not the lever — survives intact. No device time.
- [x] [Review][Decision] **🟠 MEDIUM — Path P's plane textures are fully re-specified every keyframe, so AC13's "4.7× cheaper" is partly an implementation artifact** — `WardenDetectionEngine.kt:466,482` call `glTexImage2D` (storage re-spec) rather than `glTexStorage2D` + `glTexSubImage2D`, for a 1920×1080 R8 plus a 960×540 RG8, on every one of 1061 keyframes. Every other texture in the class uses `glTexStorage2D` (`:163,:177,:215`), and `buildTargets()`'s own comment claims the plane textures are *"allocated **lazily on the first upload**"* — which the code does not do. Path P's forced-completion upload of **1.720 ms** therefore includes a driver-side realloc a steady state would not pay; that number is one half of AC13(a)'s *"4.7× cheaper, saving ~1.35 ms/keyframe"*. **Decide:** fix to `glTexSubImage2D` and re-measure (device time), or disclose the realloc as a caveat on the 1.720 ms.
  - **RESOLVED 2026-09-15 → patch (fix the code, caveat the number).** Convert `uploadYuvPlanes` to `glTexStorage2D` once + `glTexSubImage2D` per frame, matching the rest of the class and the function's own comment. Do **not** re-measure: the fix benefits 12.4 (which inherits the plumbing) but the corrected ratio changes no decision — Path Z wins the upload either way. Annotate AC13(a)'s **1.720 ms** to record that the delivered measurement includes a driver-side storage re-spec.

#### Patch (unambiguous fix, no human input needed)

**— Evidence integrity: the bench reports success it did not verify**

- [x] [Review][Patch] **🔴 `keyframe_count_matches` is unconditionally true on every limited run** [`apps/mobile/plugins/kotlin/WardenEngineBench.kt:495`] — `.put("keyframe_count_matches", limit > 0 || nFrames == syncCount)`, commented immediately above as *"🔴 AC0b's binding assertion"*. Already visible in both shipped artifacts: `ac0b_decode_strategy_comparison` reads `n_keyframes_decoded: 60, n_sync_samples_reported: 1061, keyframe_count_matches: true`. This is the exact failure mode ("a self-consistent `2 == 2`") the AC was written to prevent. Compare against the run's own target, or emit a separate `assertion_applicable` field.
- [x] [Review][Patch] **🔴 `pc_reference.py compare()` reports "EXACT PARITY" over whatever the two sides happen to share** [`apps/mobile/bench/12-2/pc_reference.py:114`] — `common = sorted(set(ref["frames"]) & set(dev_frames))`, with no assertion that `len(common)` equals either side and no non-zero floor. The device drops frames silently in two places (`evaluateBitmap` returns `null` → `continue`; `dump()` `continue`s on shape mismatch). A fixture push landing 30 of 2666 PNGs prints **EXACT PARITY** and writes `total_rule_disagreements: 0` — the source of the headline *"0 disagreements across 357,244 decisions"*. Assert completeness and fail loudly.
- [x] [Review][Patch] **🔴 `accuracy_from_fires()` is dead code, so REPORT.md §7's accuracy table has no producing path** [`apps/mobile/bench/12-2/pc_reference.py:197`] — defined **after** `if __name__ == "__main__": raise SystemExit(main())` at `:184-185`, and called by nothing; `main()` dispatches only `dump`/`compare`, and `parity_comparison.json` carries no accuracy fields. Yet *"hud 2614/2666 = 0.980495 / in_match 2666/2666 / map_id 2286/2286"* is published as reproduced-on-Adreno in the story, REPORT §7 and sprint-status. Re-running §10's documented steps produces none of it. **AC14's fire-bit half is solidly evidenced** (2666 frames, 0 disagreements, 357,244 = 2666 × 134) — only the accuracy half is unbacked. Move the function above the `__main__` guard and wire it into `compare`. Same file: `:88` writes `"gl": {}`, so the RTX 4060 cross-vendor claim is recorded nowhere.
- [x] [Review][Patch] **🟠 AC11's EGL context-creation cost is never measured** [`apps/mobile/plugins/kotlin/WardenEngineBench.kt:751`] — AC11 requires it *"reported as a separate one-off cost — it is a real number 12.3 wants"*. `one_off_setup_ms` is `engine.setupNs` only (`WardenDetectionEngine.kt:102-119`: program build, textures, self-test); `WardenEglContext.createOffscreen()` is untimed and appears in no artifact. It is the one AC11 sub-item with zero evidence, and the story itself flagged it as the cost that "on device is far more expensive".
- [x] [Review][Patch] **🟠 The 62 s full-file scan runs twice per `all` run, and only one is reported** [`apps/mobile/plugins/kotlin/WardenEngineBench.kt:~403`] — `probe()` unconditionally calls `countSyncSamplesByScan()`; `deviceProfile()` invokes it whenever `videoPath` exists, then the timing block invokes it again. Only the second is timed (`ground_truth_scan_ms: 62069`), so `report_all.json` under-reports ~62 s of a run whose headline deliverable is 35 s. Cache `profile` (the decoder already stores it in a `var` that `probe()` overwrites).
- [x] [Review][Patch] **🟠 AC7's GPU `uRules` probe never samples row 1 — the row holding the HSV bounds** [`apps/mobile/plugins/kotlin/WardenDetectionEngine.kt`, `RULES_PROBE_FRAG` / `selfTestRulesTexture()`] — the probe fetches `ivec2(i,0)` and `ivec2(i,2)` and compares only `w`, `h`, `mode`; row 1 (`h_lo,h_hi,s_lo,s_hi`), plus `x`, `y`, `v_lo`, `v_hi`, `min_ratio`, are never read GPU-side. This is the same class of gap the file's own KDoc says cost a full parity run (*"AC5 validates PACKING, the defect was UPLOAD LAYOUT"*): a corruption confined to row 1 passes the extended self-test and produces exactly the plausible-looking-garbage the check exists to make impossible.
- [x] [Review][Patch] **🟠 AC7's probe round-trips rect w/h through 8 bits, so a rect > 255 px aborts with an actively misleading message** [`apps/mobile/plugins/kotlin/WardenDetectionEngine.kt:351-370`] — the probe shader writes `t0.z / 255.0` to an RGBA8 target; `packRules` permits rects wider than 255 px (it caps only `area <= MAX_RECT_TEXELS = 4096`, so a 1920×2 strip passes). The clamp reads back 255 ≠ 300 and throws *"AC7 rules-texture self-test FAILED… the classic cause is uploading the rule-major array without transposing it"* — pointing at a transpose bug that is not there. Latent with today's 134 rules; the KDoc's "w/h are 1..25" is an assumption, not an enforced invariant.

**— Correctness: silently wrong on a device that is not the Poco**

- [x] [Review][Patch] **🔴 The NV12 fast path is taken for NV21 too and mis-pairs Cb with the next column's Cr** [`apps/mobile/plugins/kotlin/WardenDetectionEngine.kt:460-470`] — the branch keys only on `uPixelStride == 2 && vPixelStride == 2` and uploads `planes[1]` as the RG8 base, **ignoring `planes[2]` entirely**. On NV12 (`U V U V…`) pairs are (U₀,V₀) — correct. On NV21 (`V U V U…`) `planes[1]` starts at chroma offset 1, so every Cr comes from the column to the right. Nothing anywhere compares the two planes' byte offsets (two *separate* U/V buffers with pixelStride 2 would also take this branch and read V data out of the U buffer). Silent, frame-wide, no self-test coverage — on the path REPORT.md recommends shipping *because* it is "exact, device-independent colour". Common on Exynos/MTK.
- [x] [Review][Patch] **🔴 The seek decode loop never verifies the sample the seek actually landed on** [`apps/mobile/plugins/kotlin/WardenKeyframeDecoder.kt:433`] — `seekTo(pts, SEEK_TO_CLOSEST_SYNC)` → `flush()` → queue whatever `extractor.sampleTime` now is → `decoded++`. If the seek lands on a different (or the *same*) sync sample, the frame is decoded N times and counted as N distinct keyframes, inflating the divisor of `ms_per_keyframe`. **`syncSamplePtsListBySeek` has exactly this guard (`if (t < 0 || t <= last) break`); the decode loop does not** — and this device is documented *in this very file* to have a `seekTo` that stops advancing. `keyframe_count_matches` cannot catch it (a repeated landing still increments toward `syncCount`).
- [x] [Review][Patch] **🟠 Path Z has no geometry assertion, so a non-1080p capture is silently rescaled while Path P hard-fails** [`apps/mobile/plugins/kotlin/WardenDetectionEngine.kt:495-530`] — `requireGeometry()` is called only from `uploadRgbaFrame`/`uploadYuvPlanes`, and Path Z uploads nothing. `setDefaultBufferSize(REF_W, REF_H)` is ignored once MediaCodec (the producer) sets the buffer size, so `RESOLVE_OES_FRAG` nearest-neighbour-resamples into the fixed `REF_W×REF_H` target. AC13's Path-Z-vs-Path-P comparison would then be a rescaled frame against a crash.
- [x] [Review][Patch] **🟠 `decodeKeyframes` can spin forever — `MAX_SPINS` is only checked once `inputDone`** [`apps/mobile/plugins/kotlin/WardenKeyframeDecoder.kt:611`] — two routes: (a) `dequeueInputBuffer` returns −1 while `dequeueOutputBuffer` returns `INFO_TRY_AGAIN_LATER`; (b) the sync-skip loop at `:580-590` — if `advance()` returns `false` while `sampleTime >= 0`, the `break` exits with a **non-sync** sample current, which is queued tagged `BUFFER_FLAG_KEY_FRAME`, `advance()` fails again, and the same sample is re-queued every iteration. `decodeKeyframesBySeek` checks spins unconditionally; this loop does not.
- [x] [Review][Patch] **🟠 `cpuVsGpu` divides by `counted == 0` → NaN → `JSONException` → the whole report degrades to `{"error": …}`** [`apps/mobile/plugins/kotlin/WardenEngineBench.kt:364-365`] — `require(pngs.isNotEmpty())` guards the *list*, not the count of usable frames; if every PNG fails `decodeFile` or the `REF_W` check, `JSONObject.put(String, double)` rejects NaN, `runAll`'s `catch (t: Throwable)` swallows it, and AC1/AC5/AC16 results already computed are discarded — behind a misleading JSON-serialization message.
- [x] [Review][Patch] **🟠 `packRules` hard-fails on a zone with no `min_ratio` where the Python reference defaults to 0.3** [`apps/mobile/plugins/kotlin/WardenRulePacker.kt:325` vs `lut.py:207`, `HsvBand.min_ratio: float = 0.3`] — `z.getDouble("min_ratio")` throws `JSONException`, killing the whole bench. The AC5 byte-for-byte LUT cross-check — designed to catch exactly this class of divergence — cannot run, because the Kotlin side dies before producing bytes. Use `optDouble("min_ratio", 0.3)`.
- [x] [Review][Patch] **🟠 `orderedMapNames` anchors on the first `"maps"` substring anywhere in the raw JSON text** [`apps/mobile/plugins/kotlin/WardenRulePacker.kt:224`] — `rawJson.indexOf("\"maps\"")` then `indexOf('{', anchor)`. Any earlier occurrence (a string value, another object's key, a `$comment`) walks the wrong object → silently permuted texel ordering (each rule individually correct), or `IllegalArgumentException("unterminated maps object")`. Precisely the failure the function's own KDoc exists to prevent, relocated to the anchor.
- [x] [Review][Patch] **🟡 Chroma upload reads one byte past the plane, and `uStride / 2` truncates silently on an odd stride** [`apps/mobile/plugins/kotlin/WardenDetectionEngine.kt:460-470`] — `MediaImage`'s semi-planar U plane ends at the last *U* byte (`remaining() == (ch-1)*rowStride + (cw-1)*2 + 1`), while the RG8 upload over `cw × ch` needs one byte more; `glTexImage2D` does not bounds-check. One OOB heap byte becomes the bottom-right Cr — in the path AC3 asserts bit-exactness on. Separately, `GL_UNPACK_ROW_LENGTH = uStride / 2` shears chroma progressively if `uStride` is odd; the comment asserts the stride "divides exactly" without checking.
- [x] [Review][Patch] **🟡 `setOnFrameAvailableListener` takes no Handler, and the exception text asserts the opposite** [`apps/mobile/plugins/kotlin/WardenKeyframeDecoder.kt:684`] — with no Handler the listener binds to `Looper.myLooper()`, falling back to `getMainLooper()`; the bench runs on a raw `Thread` with no Looper, so every frame notification round-trips through the **main** thread. `awaitAndBind`'s error text claims *"the listener fires on the thread that created the SurfaceTexture"* — which will send the next debugger down the wrong path — and Path Z's `upload_or_bind` (0.367 ms, the base of AC13(a)) includes a cross-thread hop whose contention differs between the Activity and the `runBench()`-from-JS entry points.
- [x] [Review][Patch] **🟡 The bound texture is never checked against the expected PTS** [`apps/mobile/plugins/kotlin/WardenKeyframeDecoder.kt:693-712`] — `frameAvailable` is a latch, not a counter; `updateTexImage()` binds whatever the BufferQueue hands back and `surfaceTexture.getTimestamp()` is never compared to `kf.presentationTimeUs`. A coalesced or dropped frame is undetectable, and on Path Z there is no other signal that the bound texture is the keyframe being timed. Compounds the seek-guard finding above.
- [x] [Review][Patch] **🟡 Concurrent `runBench` / Activity relaunch is unguarded** [`WardenDetectionEngineModule.kt:40,57`; `WardenEngineBenchActivity.kt:49`] — two JS calls before the first resolves, or a configuration change (no orientation lock declared, `onCreate` ignores `savedInstanceState`), each spawn a bare `Thread` with its own `WardenEglContext`, both writing `report_<mode>.json`, `parity_fires.json`, `rules_lut_device.f32` and `timing_fires_*.json` into the same dir — interleaved artifacts, and two runs contending for the GPU while each measures "sustained clocks".
- [x] [Review][Patch] **🟡 `parityRun` ignores PNG alpha where the PC reference does not** [`WardenEngineBench.kt:~238-260` vs `pc_reference.py`] — `BitmapFactory` premultiplies by default and `getPixels` un-premultiplies lossily, while `cv2.imread(..., IMREAD_COLOR)` drops alpha and returns stored RGB untouched. A few-unit divergence would be attributed to the shader/driver (AC8/AC9/AC10) rather than to decode. `pngDump` *reports* `has_alpha`/`is_premultiplied`; `parityRun` neither checks nor records them. Set `inPremultiplied = false` or assert opacity.
- [x] [Review][Patch] **🟡 `ac3_frame_diff.py` crashes on an empty mask** [`apps/mobile/bench/12-2/ac3_frame_diff.py`, `hsv_stats`] — a config with no zone at `s_center <= 8` makes `dh[mask]` zero-size: `.mean()` returns NaN with a RuntimeWarning and `.max()` raises `ValueError: zero-size array to reduction`. Same for an all-off-frame `allm`.

**— Config plugin: the delivery documents the lesson and then applies it to one patcher of three**

- [x] [Review][Patch] **🟠 `withPackageRegistration` and `withFfmpegKitCompileDep` use idempotency-by-presence — the exact pattern this delivery records as shipped bug #2** [`apps/mobile/plugins/with-detection-engine.js`] — both early-return on `src.includes(…)`. The bench-activity mod in the same file deliberately does *not*, with a comment explaining why: *"Skipping when the activity name is already there makes the plugin unable to CHANGE the declaration on a reused android/ tree… exactly how a stale `Theme.NoDisplay` survived a plugin fix during 12.2 development."* Change the registration or bump `FFMPEG_KIT_COORDINATE`, run `expo prebuild` without `--clean`, and both mods no-op with no error at any stage. Convert both to strip-and-rewrite.
- [x] [Review][Patch] **🟡 `withFfmpegKitCompileDep` anchors on the first `dependencies {` in `app/build.gradle`** [`with-detection-engine.js:332-345`] — a template or preceding plugin emitting `buildscript { dependencies { … } }`, or the string inside a comment, puts `implementation` in the wrong scope → a Gradle failure, or a silently non-applied dependency surfacing as `available: false` + `ClassNotFoundException` (reads as "the dep was dropped", not "the patch went to the wrong block"). `withPackageRegistration` anchors on a unique comment; do the same here.
- [x] [Review][Patch] **🟡 `withBenchActivity`'s strip regex misses a partially-written or duplicated previous block** [`with-detection-engine.js:250-254`] — the regex fails to match a crashed prior write (comment present, closing `/>` absent) and matches only the first of two, so the new block is appended alongside the stale one → duplicate `<activity>` or a malformed comment, surfacing as the manifest merger's opaque "Error parsing AndroidManifest.xml" with no line number. Idempotent-by-replacement only when the previous write completed. Related: nothing removes Kotlin files dropped from `KOTLIN_FILES`, so a rename leaves a stale `.kt` → duplicate-class compile failure on a reused tree.

**— Seam and tests**

- [x] [Review][Patch] **🟠 `BenchMode` advertises a mode the native side does not implement and omits three it does; `runAll` has no default branch** [`apps/mobile/src/shared/services/detectionEngine.ts:71-77` vs `WardenEngineBench.kt:763-809`] — the union exports **`"profile"`**, which no Kotlin branch handles; `flushprobe`, `seektest` and `pngdump` exist in Kotlin but are unreachable through the only sanctioned entry point (AC18b). `runBench("profile")` type-checks, resolves successfully, and returns a report with no measurements and **no `error` field** — indistinguishable from "this mode measured nothing". REPORT.md §10 also lists `profile`. Align the union and add a default branch that throws.
- [x] [Review][Patch] **🟡 Two of the 12 seam tests assert `JSON.parse(JSON.stringify(x)) === x` while labelled as AC coverage** [`apps/mobile/src/shared/services/__tests__/detectionEngine.test.ts`] — *"surfaces the keyframe-count assertion from a timing report"* and *"parses the device profile, including AC2's OES extension verdict"* mock the native return and then assert the mocked literals; the implementation under test is `JSON.parse(raw)`. Both would pass unchanged if `keyframe_count_matches` were computed wrongly in Kotlin, if the field were renamed natively, or if the TS interfaces were deleted. The four load-bearing tests (Android-only no-op, missing-module swallow, never-reject, malformed JSON) are real. Separately, `detectionEnginePlugin.test.ts`'s four tests exercise only `readVerbatimFrag` — **none of the plugin's manifest, gradle or `MainApplication` patching is tested**, which is where the two findings above live.

**— Documentation accuracy (the AC17 deliverable is what 12.3 quotes)**

- [x] [Review][Patch] **🟠 REPORT.md's "12× worse in ratio terms" is arithmetically ~3.2×** [`apps/mobile/bench/12-2/REPORT.md:187`] — 0.51× → 0.157× is **3.25×**; the 12× comes from dividing a "×slower" (6.4) by a ratio (0.51), two different units. The story file gets it right at `:510` (*"~3× worse in ratio terms"*), so the delivery ships both figures, with the wrong one in the report section designed to be quoted into 12.3.
- [x] [Review][Patch] **🟠 The story's AC0b table matches no delivered artifact and contradicts the story's own correction section** [`12-2-android-poc-gles-port.md:457-464` vs every artifact] — story: A **33.68** / A′ **116.45** ms/kf, PTS list **3.15 s**, ground-truth walk **96.3 s**. Artifacts: `device_report_timing.json` **32.937** / **62.820**, **2289.996 ms** / **62069.9 ms**; `device_report_all.json` **32.627** / **65.226**; REPORT.md §5 **32.937** / **62.820**, **2.29 s** / **62.1 s**. The story then contradicts itself ~80 lines later at `:538` (*"strategy A′ cost 62.8 ms/kf"*, *"`countSyncSamplesByScan()`'s 62 s"*). **116.45 makes A′ look 3.5× worse than A rather than 1.9×** — and the A/A′ ratio is the sole evidence for "seeking wins". Stale figure also in code: `WardenEngineBench.kt:403` says the scan costs *"~90 s"* while `WardenKeyframeDecoder.kt:166` says *"MEASURED COST: 62 s"*.
- [x] [Review][Patch] **🟡 "Real decoding is ~4 ms" is tagged MEASURED but is derived, and the flush "factor of 8" cherry-picks runs** [`apps/mobile/bench/12-2/REPORT.md` §9 item 4] — the source tags it **[D]** (`keyframe-decode-perf-research.md` §2: `62,8 - 58,5 = 4,3 ms/image-clé. **[D]**`) and §6 states outright *"La décomposition de la section 2 est **dérivée, pas instrumentée**."* The probe does not support it either: `queue_to_first_output_ms_mean` **22.07** less `try_again_ms_per_keyframe` **10.59** leaves ~11.5 ms unattributed; the delivered decomposition never isolates decode. Same section: the *"14.5 in-loop vs **1.8** idle — a factor of 8"* uses runs 1 and 3 and ignores `device_probe_flush_run2.json` (`idle_flush_ms_median` **3.555** → factor 4).
- [x] [Review][Patch] **🟡 AC11's thermal-status claim has no collecting code and no artifact field** [`apps/mobile/bench/12-2/REPORT.md`] — *"Both full runs completed with `Thermal Status: 0` and every `CoolingDevice` at `mValue=0`"*, offered as AC11's thermal/sustained-clock context. No Kotlin touches `PowerManager.getCurrentThermalStatus()`, `addThermalStatusListener` or `/sys/class/thermal`; `deviceProfile()` collects Build fields, GL strings and MediaCodec info only; no JSON carries a thermal field. It is an out-of-band adb observation with no artifact, in a report whose stated discipline is *"stated rather than invented"* — and the only support for the "two runs agree, therefore no throttling" inference. Label it as out-of-band, or collect it.
- [x] [Review][Patch] **🟡 The File List omits the AC17 deliverable and 7 of 8 evidence artifacts** [this file, Dev Agent Record → File List] — "New (tracked)" lists `pc_reference.py`, `pc_reference_fires.json`, `ac3_frame_diff.py` but not `apps/mobile/bench/12-2/REPORT.md` (**the AC17 deliverable itself**), nor `keyframe-decode-perf-research.md`, `ac3_frame_diff.json`, `ac13_pathZ_vs_pathP.json`, `device_report_all.json`, `device_report_timing.json`, `parity_comparison.json`, `device_probe_flush{,_run2,_run3}.json`.
- [x] [Review][Patch] **🟡 `deferred-work.md` was not updated — neither to close 12.2's two assigned items nor to log what 12.2 deliberately punted** [`_bmad-output/implementation-artifacts/deferred-work.md`] — untouched by the diff. Its two items explicitly assigned to 12.2 (this story's References) are still open: `:154` the ESSL-`highp`/IEEE-754 parity gap (closed by AC8) and `:157` the Adreno 642L-vs-619 contradiction (closed by AC1 — **so the register is now actively wrong**, since sprint-status says 642L). Conversely the punted work is unlogged: the `TIMEOUT_US = 10_000` fix (which the story itself calls *"a defect in 12.2's own code, not a platform cost"*), the `countSyncSamplesByScan()` **MUST NEVER SHIP** item, and the stop-flushing-per-keyframe rewrite. Per [[feedback_batch_manual_checks_epic_end]].

#### Defer (pre-existing, not caused by this change)

- [x] [Review][Defer] **`architecture.md:847` / `:2100` carry a third and fourth reference-device identity** [`_bmad-output/architecture.md:847,2100`] — deferred, pre-existing; explicitly flagged-not-fixed by AC1 and owned by Story 9.10's prose scrub.
- [x] [Review][Defer] **Web surface is red on `main`: vitest 132 failed / 193 passed (19 of 42 files), 3 TS errors, and a `web#test` → `@warden/contracts#build` turbo task-dep gap** [`apps/web`] — deferred, pre-existing; verified outside 12.2's surface, and AC20's "zero new failures" holds against it (jest 149 → **161** / 18 → **20** suites, pytest 305 unchanged, format clean).

#### Dismissed as noise (1)

- `flushOnlyProbe(reps <= 0)` would crash on an empty list — `reps` is hardcoded to 100 at the sole call site; unreachable.

### What the review verified as solidly closed

**AC1** (device profile measured; Adreno 642L confirmed; Tool 12's third site already correct) · **AC2** (`GL_OES_EGL_image_external_essl3` present *and* compiling, both probes in the artifact; no ESSL-1.00 fallback anywhere) · **AC4** (`.frag` copied verbatim under an LF-normalised SHA-256 guard that throws at prebuild — **the auditor recomputed it independently: `5bc4fc754fb592d8…` matches**) · **AC5** (**the auditor independently re-ran `pack_rules` and got 134 rules / 7200 bytes / sha256 `b8287e084937dff0…`, byte-identical to the device's and to `REFERENCE_LUT_SHA256`**; mode distribution 68/9/57 matches) · **AC6** · **AC9/AC10** (shader never modified, `precision highp` on every program, no float `rgb2hsv`) · **AC13's measurement half** (both paths genuinely implemented and genuinely run over 1061 keyframes twice; `ac13_pathZ_vs_pathP.json` backs every figure exactly — 1262/142,174, 635/1061, 95 rules, 44 of 69 low-sat; neither path estimated) · **AC14a's fire-bit half** (2666 frames, 0 disagreements, 357,244 decisions) · **AC18(a)/(b)** (**grep confirms `detectionEngine.ts` is the only non-test file in `apps/mobile/src` touching `NativeModules.WardenDetectionEngine`**; engine Kotlin genuinely RN-agnostic) · **AC19** (**`git status --porcelain -- apps/tooling contracts` is empty — fence holds byte-level**) · **AC20** (**re-run live: 20 suites, 161 passed + 10 todo** — exactly the claimed post-state) · **AC21/AC22** legitimately `[ ] [HELD]`.

The integer-HSV port was walked exhaustively and is **correct**: `shr` vs `ushr` sign-extension at h = −1, the `+2048` rounding term, `Math.floorMod` vs GLSL `mod()`, the full-circle-before-wrap branch order, `h_tol = 180` → `MODE_FULL_CIRCLE`, `step()`/`>=` inclusivity, zero-area rects avoiding div-by-zero on both arms, `clampRect` ↔ `Rect.clamp_to` byte-identity, `PAD_MIN_RATIO = 2.0`, `Math.rint` ↔ Python banker's rounding, `bits_to_hex` nibble order, and the LUT row-major transpose on upload. GL and EGL resource lifecycle, `checkGl`'s error-queue drain, alignment pinning, framebuffer-completeness checks, and the copy-before-`releaseOutputBuffer` ordering on the decode path all hold.

### Review outcome (2026-09-15)

**All 7 `decision-needed` resolved (every one to `patch`) and all 31 `patch` findings applied.**
2 `defer` items logged in `deferred-work.md`; 1 dismissed as unreachable.

**Gates re-run after the patch round:**

| gate | before review | after |
|---|---|---|
| mobile jest | 20 suites, 161 passed + 10 todo | **20 suites, 162 passed + 10 todo** |
| tooling pytest | 305 | **305** (unchanged — the `.frag` was never touched) |
| `pnpm typecheck` | 3 errors, all `web`, pre-existing | **3 errors, all `web`** — mobile clean |
| `pnpm format:check` | clean | **clean** |
| **AC19 fence** | holds | **`git status --porcelain -- apps/tooling contracts` empty; `.frag` still `5bc4fc75…`** |

**Zero new failures.** The net +1 test is the cross-language `BenchMode` lockstep check that
replaced two tautologies.

**No measured figure changed.** Parity (0 / 357,244), AC12's 0.157×, AC13's Path Z vs Path P
divergence and the stage timings were all measured directly and stand. What changed is how they
are *explained*, what the bench *asserts*, and four device-portability defects in code 12.4 would
inherit.

**One AC3 result is new and strictly stronger than what it replaces.**
`ac3_numpy_reference.py verify-constants` was written, run, and its output committed: over **all
16,777,216 (Y, Cb, Cr) triples**, the shader's coefficients differ from BT.709 re-derived from
the primaries by **at most 1 unit, on the green channel only, on 0.179 % of the domain** — the
published four-decimal rounding of the two green coefficients, which is what FFmpeg ships too.
**The constants can therefore move a pixel by at most one unit on one channel, which rules out
both a wrong matrix and a wrong range by measurement** — offline, with no device and no capture.
AC3's stop rule existed to protect exactly that, and it is now protected by evidence rather than
by prose.

**Still open, and deliberately:** AC21/AC22 remain `[ ] [HELD]` and **nothing is committed**.
Six items are logged in `deferred-work.md`, three of them decode-side fixes 12.2 identified and
correctly declined to act on at `review` (the `TIMEOUT_US` sleep, the never-ship 62 s scan, and
the per-keyframe flush), and three device-pass re-runs (`seektest`'s missing artifact, AC13(a)'s
upload figure after the `glTexStorage2D` fix, and `compare`'s classifier-accuracy table).
