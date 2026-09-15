# Story 12.2 — Android POC: measured report (AC17)

**Measured 2026-09-15 on the reference device.** Poco X5 Pro 5G (`22101320G`), SM7325 /
Snapdragon 778G, **Adreno 642L**, Android 14 (API 34), `arm64-v8a`.
Engine: Kotlin + MediaCodec + GLES 3.0, built by `apps/mobile/plugins/with-detection-engine.js`.

> ### ⚠️ What this report does NOT bind (AC15)
>
> These are **real reference-device numbers** — but they bind **neither PERF-002 nor
> PERF-010**. Both re-baseline with **Story 12.3**; PERF-010 is a **soft target**, not a
> measured floor, and V1 launch is not gated on it. The engine brief's **`< 10 s`** is
> *"the aspiration, not an acceptance criterion"*: it is measured and reported here, and
> the story is **not failed** for missing it.
>
> Parity figures are an **in-sample parity target**, never accuracy-in-the-world.
> **REL-006's ≥95% floor is not gated here** — that is 9.9b's, instrumented by Tool 9 via
> Story 9.16.
>
> This report does **not** publish the spike verdict. `architecture-spike-gpu-megashader.md`
> is **12.3's** deliverable. 12.2 measures and reports; the verdict slot is 12.3's.

---

## 1. Headline

| Question 12.1 left open | Measured answer |
|---|---|
| Does the shader survive Adreno? | **Yes — EXACT parity.** 0 disagreements across **357,244** rule-frame decisions (2666 frames × 134 rules), backed by `parity_comparison.json`. |
| Does MediaCodec zero-copy remove the upload? | **Yes.** A bind costs **0.37 ms** where Path P's upload costs **1.72 ms** — ~4.7× cheaper. |
| So does the GPU now beat the CPU at rule evaluation? | **No. It is 6.4× SLOWER** (CPU **0.376** vs GPU **2.389** ms/frame) — *worse* than the PC's 0.51×. Robust to composition: substituting Path Z's real stages gives **6.85×** (§4). |
| Is the pipeline decode-bound on device? | **No — and this was corrected twice.** The *decode stage* dominates the wall, but only ~4 ms of it is real decoding (**derived**, not instrumented). **~25 ms is per-keyframe pipeline teardown/restart plus our own 10 ms dequeue timeout** (§5). |
| Does hardware decode beat FFmpeg software decode? | **Not measurably.** MediaCodec 35.1 s vs ffmpeg-kit `-skip_frame nokey` **33.7–38.1 s across two runs** — a 13% spread, so the earlier "~8%" was inside the noise (§5, corrected 2026-09-15). That a hardware decoder does not win is itself the finding: we were not measuring decoding. |
| Is 35 s the platform floor? | **No.** ~25 ms/keyframe is recoverable by construction. Not attempted in 12.2 — scoped to 12.3/12.4. |

**The architectural hope was directionally right and materially insufficient.** 12.1 said the
entire case for the GPU engine rested on zero-copy removing the 6.2 MB upload. It does. And
the GPU still loses to the CPU by a factor of six, because with the upload gone the remaining
cost is not the arithmetic — it is the fixed per-frame overhead of getting ~800 texel fetches'
worth of answers into and out of a draw call.

> ### 📌 Post-delivery correction (2026-09-15), after `apps/tooling`-independent review
>
> A follow-up investigation challenged this report's attribution of the 33 ms/keyframe, and a
> dedicated probe settled it. **The engine conclusions above are unaffected** — parity, the
> CPU-vs-GPU ratio and the colour-path comparison were all measured directly and stand. What
> changed is the *diagnosis of the decode cost*, in §5 and §9:
>
> - **Real decoding is ~4 ms/keyframe, not 33** — a **derived** figure, not an instrumented
>   one (see §5). The rest is `flush()` (14.5 ms, instrumented) plus waiting for output
>   (22.1 ms, of which 10.6 ms is sleeping in a timeout we chose ourselves).
> - **Storage is not a factor** (5 KB read per keyframe), and `Android/data` is not FUSE-served
>   on Android 11+. Both earlier claims to the contrary are withdrawn.
> - **35 s is therefore not a platform floor.** 12.2 did not attempt the fix; it is scoped
>   work for 12.3/12.4 and is recorded here so the verdict is not taken against a number that
>   is known to be improvable.

> ### 📌 Second correction pass (2026-09-15), after an adversarial code review of the delivery
>
> A three-layer code review (Blind Hunter / Edge Case Hunter / Acceptance Auditor) checked this
> report against the artifacts it cites. **No measured figure changed and no conclusion was
> overturned** — parity, the CPU-vs-GPU ratio and the Path Z vs Path P divergence were all
> measured directly and stand. What changed:
>
> - **§4's "12× worse in ratio terms" was arithmetic error** (×slower ÷ ratio). It is ~3.2×.
> - **§4's stage attribution for the 2.389 ms described a resolve and a bind the measured path
>   does not have.** Rewritten to say what was actually measured; the substitution that *does*
>   apply gives 6.85×, so the conclusion strengthens.
> - **"decode = 99% / the engine is ~1%" was an accounting artifact** — `decodeNs` nests the GL
>   stages inside itself, which is why the naive stage sum exceeds the wall. The engine is
>   ~6–7% of the wall (§3, §9).
> - **"hardware decode buys ~8%" was inside the run-to-run noise** of the control (§5).
> - **AC3's stop rule was not met and could not have been** (nearest-neighbour vs interpolated
>   chroma). The constants are now proved **exhaustively and offline** over all 2^24 YUV triples
>   (§6) — a stronger result than the single-frame claim it replaces.
> - **§7's accuracy table and the RTX 4060 column had no producing code path**; the tooling is
>   fixed and the gap is labelled where the table appears.
> - **The thermal claim is an out-of-band `adb` observation**, now labelled as such (§10).

---

## 2. AC1 — device profile (measured from a current GL context)

| Property | Value |
|---|---|
| model / SoC / board | `22101320G` / `SM7325` / `redwood` |
| Android | **14** (API **34**) |
| `GL_VENDOR` | `Qualcomm` |
| `GL_RENDERER` | **`Adreno (TM) 642L`** |
| `GL_VERSION` | `OpenGL ES 3.2 V@0530.57 (GIT@4bbe300fc3, Date:05/19/25)` |
| `GL_SHADING_LANGUAGE_VERSION` | `OpenGL ES GLSL ES 3.20` |
| extensions | 100 |
| ABIs | `arm64-v8a, armeabi-v7a, armeabi` |
| decoder | **`c2.qti.avc.decoder`**, `isHardwareAccelerated = true` |
| decoder output layout | **semi-planar NV12** — `rowStrides = 1920,1920,1920`, `pixelStrides = 1,2,2` |

**Adreno 642L confirmed.** `epics-and-stories.md:3315` and the `sprint-status.yaml` key said
*Adreno 619* (the SD695, the pre-re-anchor device) and are corrected. Tool 12's
`__main__.py` already said 642L — Story 12.1 had fixed it, so AC1's third site needed no
change. `architecture.md:847` still says *"Poco X5 (Snapdragon 695 … Android 13)"* — a third
identity, `:2100` a fourth. **Flagged, not fixed** (Story 9.10's scrub).

### AC2 — the gate that could have turned the port into a rewrite

`GL_OES_EGL_image_external_essl3` is **PRESENT**, verified the two independent ways the AC
demands: advertised in `glGetString(GL_EXTENSIONS)` on a current context, **and** the
`#extension … : require` line actually compiles.

**Path Z is therefore available under `#version 300 es`.** No ESSL-1.00 fallback, no second
shader body, **E2 intact**. (`GL_EXT_YUV_target` and `GL_QCOM_YUV_texture_gather` are also
present; neither was needed.)

---

## 3. AC11 / AC13 — the measurement, both colour paths, full capture

`videos/V2/2026-04-27 22-05-34.mp4` — 1920×1080, h264, `yuv420p`, `color_range=tv`,
`bt709`, **4419.6 s = 1 h 13 min 40 s**, GOP **4.1667 s**, **1061 keyframes**.

> Note: the story text calls this a *"~2 h"* capture. **Measured, it is 1 h 13 min 40 s** (`ffprobe` duration 4419.633 s, corroborated by 1061 x 4.1667 s GOP = 4420.8 s). Every throughput figure below is stated per keyframe, so none of them moves — but the whole-capture totals must be read against 1 h 14, not 2 h.

Decoded count asserted against an independent sample-table scan: **1061 == 1061 ✅**.

### Naive wall-clock split — directly comparable to 12.1's method

| stage (ms/keyframe) | **Path Z** (zero-copy) | **Path P** (bit-parity) |
|---|---|---|
| decode | **33.105** | **42.085** |
| upload / bind | 0.378 | 1.569 |
| resolve | 0.256 | 0.144 |
| shader | 0.108 | 0.048 |
| readback | 1.279 | 1.307 |
| **wall** | **33.428** | **42.299** |
| **total, whole capture** (1 h 13 m 40 s of video) | **35.5 s** | **44.9 s** |
| **vs real time** | **125x** | **98x** |
| one-off setup, engine (excluded above) | 15.2 ms | 4.8 ms |
| one-off setup, EGL context (excluded above) | *see `ac11_one_off_egl_context_ms`* | — |
| **GL share of wall** *(corrected)* | **6.0 %** | **7.3 %** |

> 🔴 **`decode` above is NOT a disjoint stage — corrected 2026-09-15 (code review).**
> `WardenKeyframeDecoder` *assigns* `decodeNs = nanoTime() - t0` with `t0` fixed at the decode
> loop's entry, and takes the snapshot **before** `onFrame()` runs — so it contains the
> upload / resolve / shader / readback of every keyframe but the last. The tell is in the
> table itself: summing the stages gives **35.125** on Path Z against a **wall of 33.428**
> (Path P: 45.153 vs 42.299), and a partition cannot exceed the whole.
>
> This report previously published **"decode share of wall 99.0 % / 99.5 %"** from those
> nested figures. The disjoint numbers are: GL total **2.021 ms** of **33.428** = **6.0 %**
> (Path Z) and **3.068** of **42.299** = **7.3 %** (Path P). The bench now emits
> `decode_excluding_gl`, `gl_total` and `gl_share_of_wall` alongside the naive split — quote
> those. **The structural conclusion is unchanged** (neither engine choice touches most of
> the wall) but the engine is ~6–7 % of it, not ~1 %.

> ⚠️ As 12.1 established, **the naive split is also misattributed** — GL work is asynchronous,
> the timer stops before the work lands, and the blocking readback absorbs the tail. That is a
> SECOND, independent caveat on this table. Quote the forced-completion table below for the
> stage split that means what it says. Both are reported, labelled, deliberately.

### Forced-completion profile — `glFinish()` per stage, median of 200

| stage (ms) | **Path Z** | **Path P** |
|---|---|---|
| upload / **bind** | **0.367** | **1.720** |
| resolve | 1.306 | 1.267 |
| shader | 0.598 | 0.268 |
| readback | 0.305 | 0.136 |
| **GPU total** | **2.576** | **3.391** |

### AC13 — the three questions, answered from measurement

**(a) Does zero-copy actually remove the upload? By how much?**
**Yes.** Binding a `SurfaceTexture`-backed external texture costs **0.367 ms** against Path P's
**1.720 ms** host→device upload — **4.7× cheaper, saving ~1.35 ms/keyframe**. 12.1's premise is
confirmed on the device.

But the *total* Path Z advantage is **8.9 ms/keyframe** (33.4 vs 42.3), and only ~1.35 ms of
that is the upload. **The larger share is decode: 33.1 vs 42.1 ms.** Path P must copy three
`Image` planes (~3.1 MB) out of the codec every frame; Path Z renders straight into the
texture and copies nothing. That plane copy — not the GL upload — is Path P's real cost.

**(b) Does the OES colour conversion break parity? On how many rules, and are they the low-sat ones?**
**Yes, measurably — and it does reach the low-saturation population.** Path Z vs Path P over
the full capture:

| | value |
|---|---|
| keyframes compared | 1061 |
| **per-rule disagreements** | **1262 of 142,174 (0.888 %)** |
| keyframes with ≥1 disagreement | **635 of 1061 (59.9 %)** |
| rules affected | **95 of 134 (70.9 %)** |
| …of which low-saturation (`s_center ≤ 8`) | **44 of 69** |
| …of which on the full-circle branch | **43 of 68** |

Worst offenders: `engine/engine_z00` (209 frames), `atlantis/atlantis_z02` (136, low-sat),
`v2/hud_z00` (103), `helios/helios_z03` (88, low-sat).

The disagreement *rate* is under 1% of decisions, but it is **not confined to a corner of the
ruleset**: it touches 71% of rules and the majority of keyframes, and 44 of the 69
low-saturation rules — the ones tuned by the accepted `h_tol = 180` decision that moved map-ID
0.973 → 1.000 — are among them. **Path Z is not bit-parity, and the deviation lands where the
tuning is most fragile.**

**(c) What does Path P cost relative to Path Z, and does the margin still beat the CPU?**
Path P costs **+8.9 ms/keyframe (+27%)**: 42.3 vs 33.4 ms, 44.9 s vs 35.5 s over the capture.

And the second half of the question is the one that matters: **no.** Neither path's margin beats
the CPU, because (§4) the CPU does the same work in 0.376 ms while the GPU's own cost is
2.6–3.4 ms. The colour fork is a **correctness** trade-off, not a performance one — the
performance argument is already lost on both sides of it.

---

## 4. 🔴 AC12 — the number the epic turns on: device CPU vs device GPU

Decode **excluded from both sides**, identical bytes, identical bounds, identical
`count/area >= min_ratio`, 400 frames, 134 rules:

| | ms/frame |
|---|---|
| **device CPU** (plain Kotlin, integer `RGB2HSV_b`) | **0.376** |
| **device GPU** (upload + draw + readback, forced to completion) | **2.389** |
| **ratio** | **0.157× — the GPU is 6.4× SLOWER** |
| fire-bit disagreements between the two arms | **0** |

For comparison, 12.1 measured **0.51×** on PC. **On the reference device the GPU's
disadvantage is not smaller than on PC — it is ~3.2× worse in ratio terms** (0.51 → 0.157).

> **Corrected 2026-09-15 (code review).** This sentence previously read "12× worse in ratio
> terms", which came from dividing a *×slower* figure (6.4) by a *ratio* (0.51) — two
> different units. The story file had it right at ~3×.

> 🔴 **What the 2.389 ms actually contains — read before quoting it.** The AC12 GPU arm runs
> `WardenColorPath.DIRECT_RGB`, so the timed region is **an 8.3 MB RGBA host→device upload +
> draw + `glReadPixels` + `glFinish()`**. It has **no resolve pass and no bind**: `resolve()`
> early-returns on that path and no resolve program is built for it. (Until the 2026-09-15
> review the paragraph below described it as containing a resolve and a bind, quoting stage
> figures lifted from `ac11_forced_completion` — a different run, on different paths.) The
> CPU arm's own 8.3 MB `ByteBuffer`→`ByteArray` copy sits **outside** its timer, so the two
> arms are not symmetric.
>
> **Substituting Path Z's real stages does not rescue the GPU — it costs it.** From
> `ac11_forced_completion` (ZERO_COPY): bind **0.367** + resolve **1.306** + shader **0.598**
> + readback **0.305** = **2.576 ms**, against CPU 0.376 = **6.85× slower**. The conclusion is
> robust to how the GPU arm is composed.

> ⚠️ **Read the CPU numbers carefully — they are not a hardware comparison.**
> 12.1's PC CPU figure (1.667 ms) is Python driving **134 separate `cv2.inRange` calls**, one
> per rule, each with numpy/Python call overhead. This device figure (0.376 ms) is a **tight
> Kotlin loop** over the same ~800 pixels. The phone's CPU is not 4.4× faster than a desktop
> CPU; the *implementation* is leaner. What the two numbers legitimately share is the
> conclusion, which holds under either implementation: **evaluating 134 tiny rects is a
> trivially cheap CPU task, and routing it through a GPU costs more than it saves.**

**Why the GPU loses even with the upload removed.** The shipped rects are 1–25 px (mode 2×2;
fourteen are literally 1×1), so the real work is ~800 texel fetches per frame. Against that,
the fixed costs a *shipping* path pays — measured on Path Z in `ac11_forced_completion`, not
in the AC12 arm above — are: a full-frame resolve pass (**1.306 ms**, unavoidable while the
shader is fed a `sampler2D` — see §6), the shader itself (**0.598 ms**), a `glReadPixels`
synchronisation (**0.305 ms**), and the bind (**0.367 ms**). That is **2.576 ms** to answer
~800 texel fetches, against a CPU that answers them in **0.376 ms**.
**The arithmetic was never the bottleneck, so making it parallel buys nothing.**

---

## 5. AC0b — decode, the largest new engineering surface

`-skip_frame nokey` has no MediaCodec equivalent flag. Two analogues were built and measured
head to head on the same 60 keyframes:

| strategy | decode ms/kf |
|---|---|
| **A — absolute seek per keyframe** (shipped) | **32.937** |
| A′ — single-pass sync-filtered demux | 62.820 |

**Seeking wins by 1.9×.** But **Option A as literally specified does not work on this device**:

> 🔴 The incremental scan the AC prescribes — `seekTo(lastPts + 1, SEEK_TO_NEXT_SYNC)` in a
> loop — **stops advancing after the second sync sample**, reporting **2** keyframes against a
> ground truth of **1061**. Absolute `SEEK_TO_CLOSEST_SYNC` seeks are correct and cost ~2.9 ms
> each. **Seeking is not broken; that one pattern is.**

**AC0b's count assertion is what caught this, and it earned its keep exactly as intended.** Had
the decode loop trusted the seek scan, the bench would have reported a perfectly self-consistent
`2 == 2` and a beautiful ms/keyframe figure computed over two frames — the same class of
failure 12.1's CFR-duplication check was built to catch.

**Keyframe index** (both one-off, both reported outside every wall clock):

| | value |
|---|---|
| ground-truth sample-table scan | **1061** keyframes, **62.1 s** |
| seek-built PTS list (what the decode loop consumes) | **1061** keyframes, **2.29 s** |
| counts agree | **✅** |

### Option C — the ffmpeg-kit control, and what it reveals

12.1's literal `-skip_frame nokey`, run on device via `@wokcito/ffmpeg-kit-react-native@6.1.4`
(already a mobile dependency), on the same file:

| | whole-capture decode |
|---|---|
| **MediaCodec, hardware** (Path Z, decode stage only, index build excluded) | **35.1 s** |
| **ffmpeg-kit, software** — `device_report_timing.json` | **38.1 s** |
| **ffmpeg-kit, software** — `device_report_all.json` | **33.7 s** |

🔴 **Hardware decode does not measurably win on this workload — corrected 2026-09-15 (code
review).** This section previously quoted only the 38.1 s run and concluded "hardware decode
buys about 8%". The control was measured **twice**, and the two runs span
**33,659.6 ms → 38,068.1 ms, a 13 % spread — larger than the 8 % effect being claimed.** In the
`all` run, software decode is *faster* than hardware (33.7 s vs 35.1 s). Two further reasons not
to read a number off this comparison:

- It is **not like-for-like**: 35.1 s is MediaCodec's *decode stage only* and excludes the
  2.29 s index build, while 38.1 s is a complete `ffmpeg` invocation (demux + decode + teardown).
- `n = 2` on the control, with no repeat measurement of the MediaCodec side under the same
  conditions.

**What survives, and it is the part that matters:** a hardware decoder is many times faster than
software at *decoding*, yet here the two are within run-to-run noise. That is only possible if
**decoding is not what the ~33 ms is being spent on** — which the stage probe below then
confirms directly and quantitatively. The conclusion was right; the 8 % was not evidence for it.

### Where the time actually goes — MEASURED, 2026-09-15

The paragraph that stood here originally blamed *"per-keyframe seek + `flush()` + pipeline drain
and moving 2.3 GB of file through storage"*. Two of those three were wrong. A dedicated probe
(`--es mode flushprobe`, 100 keyframes, 3 runs, ±0.4 ms) instrumented the loop stage by stage.
Figures below are the ByteBuffer path, whose full-capture decode was 42.085 ms/keyframe:

| stage | ms/keyframe | share |
|---|---|---|
| `seekTo` | **4.4** | 10 % |
| **`flush()`** | **14.5** | **34 %** |
| queue IDR → first output | **22.1** | 52 % |
| ⤷ *of which: sleeping inside `dequeueOutputBuffer`* | ***10.6*** | *25 %* |
| accounted | 41.0 / 42.3 | 97 % |

> **This decomposition is INSTRUMENTED per stage but does NOT isolate decoding itself.** The
> "~4 ms of real decoding" quoted in §9 is **derived** (`62.8 − 58.5`), tagged `[D]` in
> `keyframe-decode-perf-research.md`, whose §6 says outright that the section-2 decomposition
> is *dérivée, pas instrumentée*. Within the 22.1 ms "queue IDR → first output", 10.6 ms is
> our own timeout sleep and the remaining **~11.5 ms is unattributed** — it is *not* all
> decoding. Labelled here because §9 previously called the figure MEASURED. *(Corrected
> 2026-09-15, code review.)*

**Three corrections to what this report previously claimed:**

1. **Storage is NOT a contributor.** `/proc/self/io` shows **5 KB read per keyframe** — not
   200 KB, not 2.3 GB. The page cache absorbs it. *(Caveat: the probe covers the first 100
   keyframes ≈ 217 MB and the file was warm from prior runs, so this does not generalise to a
   cold 2.3 GB pass.)* Separately, `Android/data` is **not** served by FUSE since Android 11 —
   `vold` bind-mounts it from the underlying filesystem — so the "FUSE overhead" hypothesis
   entertained during development is doubly dead.
2. **Seeking is NOT the main cost.** 4.4 ms of 42.3 — a tenth. The report's original framing
   ("keyframe random-access overhead") pointed in the right direction but named the wrong
   mechanism.
3. **The cost is the per-keyframe PIPELINE RESTART, and one of its two halves is a plain
   implementation defect.** `flush()` costs **14.5 ms in the loop but 1.8–3.6 ms on an idle
   codec** — a factor of **4 to 8**, depending on the run
   (`device_probe_flush.json` 1.821 / `_run2` **3.555** / `_run3` 1.786; this report previously
   quoted "a factor of 8" from runs 1 and 3 only — *corrected 2026-09-15, code review*) — so
   the expense is the `END_OF_STREAM` → flush state transition, not the HFI round trip. And **`TIMEOUT_US = 10_000` on `dequeueOutputBuffer` costs 10.6
   ms/keyframe**: the probe counts **1.02 `INFO_TRY_AGAIN_LATER` per keyframe**, i.e. almost
   exactly one full 10 ms sleep each time, because the codec has not produced output yet when
   we first ask.

**This reframes the epic's premise for 12.3 — and improves the outlook.** 12.1 concluded "the
pipeline is decode-bound". It is not: **real decoding is only ~4 ms of the 33–42 ms.** The rest
is a pipeline being torn down and rebuilt 1061 times, plus a timeout we chose. Unlike a hardware
decode floor, **both are ours to fix**, and neither has anything to do with the detection engine.

> 🔴 **CORRECTION (2026-09-15).** An earlier version of this report and of
> `WardenKeyframeDecoder` described `MediaExtractor.advance()` as *"metadata-only:
> nothing here is decoded"*. **That is false.**
> `NuMediaExtractor::fetchTrackSamples` reads sample **data** on every `advance()`
> as well as on every `seekTo`, in batches of up to `mMaxFetchCount = 8` for video
> tracks. This is the actual reason strategy A-prime costs 62.8 ms/keyframe: it
> drags all 2.3 GB through the extractor to reach one sample in 250. It also means
> **`countSyncSamplesByScan()`'s 62 s is a full-file read, not an index walk** — it
> is a bench-time assertion and **must never ship** (Story 12.4: take the index
> from the seek-built list at 2.3 s, or read `stss` directly).

Other MediaCodec findings, each of which cost a build/flash cycle:

- **`start()` after `flush()` throws in synchronous mode** — `IllegalStateException: start() is
  valid only at Configured state; currently at Running state`. The documented "call `start()`
  after `flush()`" rule applies to **asynchronous** mode only.
- **A single queued sample decodes to NOTHING.** Hardware pipeline depth means feeding one sync
  sample and polling yields `INFO_TRY_AGAIN_LATER` forever — which presents as *"the seek landed
  off a sync point"*, the wrong diagnosis entirely. **`BUFFER_FLAG_END_OF_STREAM` must be queued
  immediately after each keyframe** to force the drain. That is a structural cost of the seek
  path: **one EOS round-trip per keyframe**.

---

## 6. AC3 — colour: PC vs device, in OpenCV HSV units

AC3's stop rule is *"if the diff is not zero, the YUV→RGB constants are wrong and every
downstream number is unanchored."*

> 🔴 **Read this first — AC3's literal stop rule was NOT met, and could not have been.**
> `RESOLVE_YUV_FRAG` samples chroma nearest-neighbour (`ivec2(p.x / 2, p.y / 2)`) while FFmpeg's
> swscale interpolates, so the two disagree at every chroma edge **by construction**, bounded by
> the local chroma gradient. ΔS = 0 against an `rgb24` reference was unreachable without a
> matched-upsampling mode, which neither the shader nor `ac3_frame_diff.py` offers. The gate was
> passed by reclassifying the residual, not by meeting the rule — this is stated plainly here
> because it was not before *(2026-09-15, code review)*.
>
> **What the stop rule exists to protect — the constants — is now PROVED, offline and
> exhaustively.** `ac3_numpy_reference.py verify-constants` walks **all 16,777,216 (Y, Cb, Cr)
> triples** and compares the shader's arithmetic against BT.709 re-derived from the primaries
> (Kr = 0.2126, Kb = 0.0722). Result, in `ac3_numpy_constants.json`:
>
> | | |
> |---|---|
> | triples compared | **16,777,216** (the whole domain) |
> | differing | **30,023 (0.179 %)** |
> | max &#124;Δ&#124; per channel | **1** |
> | channels affected | **green only** (B: 0, R: 0) |
>
> The cause is that **ITU-R BT.709 publishes the chroma coefficients rounded to four decimals**,
> and the two green ones are not exact there (0.1873 vs 0.18732427; 0.4681 vs 0.46812427 — red
> and blue *are* exact). Our shader ships the published values, which is what FFmpeg ships too,
> so this is **agreement with FFmpeg, not deviation from it**.
>
> **Decision-relevant consequence:** the constants can move a pixel by at most **one unit on one
> channel**. They therefore cannot account for the `dS_max` of **50** that `ac3_frame_diff.py`
> measures inside rule rects, and they are not a 601-vs-709 matrix error (which is unbounded and
> affine in the pixel's own chroma). **A wrong matrix and a wrong range are both ruled out by
> measurement, on the whole domain, with no device and no capture required.**

**The constants are not wrong**, and the single-frame evidence below was originally the basis
for that claim — reimplementing the identical bt709 limited-range math independently in numpy on
the PC, from the raw `yuv420p` planes of the same keyframe. **That script now ships**
(`ac3_numpy_reference.py compare-png`); before the 2026-09-15 review this table's numbers had no
producing code path in the repo, and the only reproducible AC3 artifact,
`ac3_frame_diff.json`, carried a generated `diagnosis` of *"MATRIX-ERROR-scale discrepancy"* for
both paths — contradicting this section. That diagnosis logic is fixed: it now discriminates on
the **bounded** BGR residual, which is the property that actually separates the hypotheses.

| comparison | mean \|ΔBGR\| | max | pixels differing |
|---|---|---|---|
| independent numpy (same constants, nearest chroma) **vs device Path P** | **0.00005** | 69 | **5 of 2,073,600 (0.00024 %)** |
| independent numpy **vs FFmpeg `rgb24`** | 0.955 | **3** | 94.3 % |
| device Path P **vs FFmpeg `rgb24`** | 0.955 | 69 | 94.3 % |

The device reproduces the intended conversion essentially exactly, and the **entire** residual
against FFmpeg is **≤ 3 units of 255** — the signature of a **chroma-upsampling policy**
difference (ours is nearest-neighbour; swscale interpolates), **not** of a wrong matrix or a
wrong range. For scale, 12.1 measured a *range* error at ΔS ≈ 19.68.

The 5 divergent pixels are 4 at the extreme bottom-right corner (1918–1919 × 1078–1079) plus one
stray, and they are **provably inert**: the furthest extent of any shipped rule rect is
x ≤ 1793, y ≤ 1063, so **no rule touches them**.

Per-region diffs against FFmpeg, in OpenCV HSV units:

| path | region | ΔH | ΔS | ΔV |
|---|---|---|---|---|
| **Path P** | all 134 rule rects | 4.77 | **2.46** | 0.73 |
| **Path P** | 69 low-sat rects | 4.83 | **2.86** | 0.73 |
| **Path Z** | all 134 rule rects | 5.42 | **5.64** | 2.25 |
| **Path Z** | 69 low-sat rects | 6.47 | **5.62** | 1.84 |

> **Means alone understate this.** AC3 asked for the low-saturation delta *as a distribution*;
> `ac3_frame_diff.json` records `dS_max` **50** and `dH_max` **15** inside rule rects behind
> those means. `ac3_frame_diff.py` now also emits p50/p95/p99 for ΔH, ΔS and ΔV, plus the raw
> BGR residual, so the tail is visible without re-reading the JSON by hand. *(2026-09-15, code
> review.)*

Path Z's driver conversion is ~2× further from FFmpeg on saturation than Path P — consistent
with, and independently corroborating, the 0.888% fire-bit divergence in §3(b).

*(Note: **69** rules sit at `s_center ≤ 8`, not the 68 the story quotes. 68 is the count on the
**full-circle branch**. The two populations overlap heavily but are not identical.)*

### 🔴 Two silent colour bugs found and fixed

1. **`pixelStride` is load-bearing.** `COLOR_FormatYUV420Flexible` is a *family*, not a layout.
   This decoder returns **semi-planar NV12** (`pixelStrides = 1,2,2`), where U and V share one
   interleaved buffer. Uploading that as tightly-packed R8 reads `UVUVUV…` as `UUU…`:
   **98.7% of pixels wrong, ΔS 26.6**, with Y perfectly intact. Fixed by uploading chroma as one
   **RG8** texture — `GL_UNPACK_ROW_LENGTH` counts *pixels*, and an RG8 pixel is exactly the two
   bytes an NV12 chroma pair occupies, so the decoder's buffer uploads verbatim with **zero CPU
   work**. (Fully-planar devices fall back to a CPU interleave, so one resolve shader serves
   every layout.)
2. **Path Z needs an explicit Y flip that is *not* the ST matrix's job.** `SurfaceTexture`'s
   transform matrix expects `v = 0` to be the image BOTTOM, while `frameTex` row 0 must be the
   image TOP (the mega-shader indexes rects top-down). Before the fix the output matched
   `flipud(PC)` at mean |ΔBGR| **2.53** while matching PC as-is at **32.36**.

---

## 7. AC8 / AC9 / AC10 / AC14 — parity: EXACT on Adreno

**Corpus (a) — shader parity, isolated from decode colour.** All **2666** labeled PNGs
(`apps/tooling/output/labeled/v2/`, 16 classes) pushed to the device and evaluated through the
`DIRECT_RGB` path — RGB bitmaps, no video decode, no YUV conversion — so a shader fault and a
colour fault cannot mask each other.

> ### **0 per-rule disagreements across 357,244 rule-frame decisions. 0 frames with any disagreement.**

And the device reproduces 12.1's pinned accuracy **exactly, down to the correct-counts**:

> ⚠️ **These three rows had NO producing code path until 2026-09-15.** `accuracy_from_fires()`
> in `pc_reference.py` sat **below** the `if __name__ == "__main__": raise SystemExit(main())`
> guard — dead code no CLI path could reach — and `compare()` emitted only fire-bit counts, as
> `parity_comparison.json` shows. Re-running §10's documented steps produced none of this
> table. The function is now defined before the guard and wired into `compare()`, which writes
> the accuracies into `parity_comparison.json` under `ac14_classifier_accuracy`. **Until a
> `compare` has been re-run, the figures below are the ones originally reported and are not
> backed by a delivered artifact.** The fire-bit half of AC14 above *is* fully backed
> (`parity_comparison.json`: 2666 frames, 0 disagreements, 357,244 = 2666 × 134).
>
> The **RTX 4060** column is likewise unrecorded: `pc_reference.py` hard-coded `"gl": {}` into
> its payload, so the GPU that produced the reference appears in no artifact. `dump` now
> records whatever the driver reports, so a re-run will carry its own provenance.

| classifier | 12.1 pinned (Intel UHD 770) | PC reference re-run (RTX 4060) | **Adreno 642L** |
|---|---|---|---|
| `hud_version_classifier` | 0.980495 (2614/2666) | 0.980495 (2614/2666) | **0.980495 (2614/2666)** |
| `in_match_classifier` | 1.0000 (2666/2666) | 1.0000 (2666/2666) | **1.0000 (2666/2666)** |
| `map_id_classifier` | 1.0000 (2286/2286) | 1.0000 (2286/2286) | **1.0000 (2286/2286)** |

All three of AC14's per-classifier formulas are reproduced exactly as Tool 9 defines them —
HUD `fires/n_hud` **normalized**; in_match `fires/n_im` **normalized then hard-binary**; map-ID
`Σ effective_weight × fired` **raw, unnormalized**. The shader **ignores the dead 3×5
`minimap_identification.roi`** and evaluates zone rects as absolute reference-resolution
coordinates against the full 1920×1080 frame; the data defect is **not fixed** (9.9b's, AC19-fenced).

This settles the three open shader questions:

- **AC8 — the integer-HSV exactness DOES transfer to Adreno.** *(Closes the 12.1 review item
  deferred to this story.)* The concern was that ESSL 3.00 specifies `highp float` as a
  *minimum relative precision*, not IEEE-754 single, so a reduced-precision driver would move the
  runtime `sdiv`/`hdiv` reciprocals by one and shift S or H by ±1 — flipping exactly the **31
  rules whose bands are asymmetric about their centre**. Measured: it does not. Those 31 rules
  agree on every one of 2666 frames.
- **AC9 — negative signed `>>` sign-extends correctly on Adreno.** The **9 wrap-branch rules**,
  whose `h` goes negative and depends on `h = (h * hdiv + 2048) >> 12` extending the sign, agree
  on every frame. **No bias workaround was needed, so `keyframe_engine_bench.frag` was never
  modified and AC4's change procedure was never invoked.**
- **AC10 — `precision highp` is honoured and the port stayed integer.** The `mediump` NaN trap (a
  float `rgb2hsv`'s `1e-10` epsilon flushing to zero → `0/0` → NaN failing every `step()`
  silently on greys) cannot fire: the shipped shader has no epsilon and gates the reciprocal on
  `diff > 0`. The **69 low-saturation rules — the greys — agree on every frame**, which is the
  direct empirical check.

**Corpus (b) — timing.** The full 1061 video keyframes, §3.

### 🔴 The bug that cost a full parity run, and the self-test gap that allowed it

The first parity run disagreed on **131,968 of 357,244 decisions (37%)**, on every frame, with the
device firing *less*. Cheap hypotheses were tested and all rejected — vertical flip (68.8%
agreement), BGR swap (65.4%), as-is (61.5%). Dumping the device's frame texture settled it:
**byte-identical to `cv2.imread`**, so the input was perfect.

The cause: **`WardenPackedRules.texture` is rule-major `[rule][row][ch]`, but a GL texture is
row-major.** `shader.py:203` transposes before upload (`.transpose(1, 0, 2)`); the Kotlin port
did not. So `texelFetch(uRules, ivec2(i, 0))` read rule `i/3`'s row `i%3` — every bound
scrambled, producing plausible-looking detections from garbage. **12.1's exact lesson, in a new
place.**

What is worth carrying forward is *why the existing checks missed it*:

- **AC5's byte-for-byte LUT check passed** — it validates the **packing**, which was correct.
  The defect was in the **upload layout**. Different properties; only one was asserted.
- **AC7's self-test passed** — it cleared and read the result FBO, proving the render target was
  sane and **nothing at all about what the shader was reading**.

AC7's self-test was therefore extended: a probe pass now samples `uRules` **on the GPU** and
writes each rule's rect width/height/mode back through the RGBA8 target, and all 134 texels are
compared against the packed array at construction. Confirmed by the device-side CPU-vs-GPU
comparison flipping from **3117 disagreements to 0** the moment the transpose landed.

---

## 8. AC16 — the observed threading model (amendment 5d's named deliverable)

`architecture.md:813-815` marks Brownfield Item 6 **"RATIONALE RE-DERIVATION REQUIRED"** and
names Story 12.2 as the owner. Observed, from what was actually built:

| question | observed |
|---|---|
| which thread owns `eglMakeCurrent` | a plain worker thread (`warden-bench`), **never the UI thread** |
| surface type | **pbuffer** — no Activity, no SurfaceView, no window |
| which thread `MediaCodec` output is handled on | the same worker thread (synchronous dequeue loop) |
| `SurfaceTexture.updateTexImage()` affinity | the thread owning the EGL context the texture belongs to — the same worker |
| can an offscreen context live on a worker thread? | **Yes. Demonstrated — every number in this report was produced that way.** |

**The finding: EGL contexts are THREAD-bound, not JS-context-bound.** `architecture.md:2047`'s
current rationale — *"the foreground service hosts the main JS context where the JSI binding
lives"* — is **not** the constraint that governs this engine. Thread affinity is.

**The conclusion survives; the reasoning changes.** A Foreground Service is still the right host,
but for a different reason: not because the JS context must be co-located, but because the
**process must stay alive and at foreground importance** for a multi-minute run. The engine
itself needs only *a* thread it owns. **12.3 rewrites the architecture prose; 12.2 supplies the
model.**

### Amendment 5c activates

MediaCodec + GLES 3.0 is **Android-only by construction** (iOS = VideoToolbox + Metal; GLES is
deprecated on iOS). Per `architecture.md:894-896` the "iOS Phase 2 is glue" assertion becomes
false the day this lands, and the detection-engine slice flips from *glue* to *refactor*. iOS is
already V3, so the cost is **deferred, not incurred** — and **if Story 12.3 rejects the shader
engine, this amendment lapses**. The Android-only surface is deliberately bounded to the engine:
every other mobile decision stays cross-platform-ready, which is what keeps a 12.3 rejection cheap.

---

## 9. Input for 12.3 (the verdict is 12.3's, not this report's)

Stated as measurement, not as recommendation:

1. **Correctness is not the issue.** The shader is bit-exact on Adreno, over 357,244 decisions.
   If 12.3 wants the GPU engine, nothing about parity stands in the way.
2. **Performance is the issue, and it got worse, not better.** The GPU is **6.4× slower** than the
   device CPU at rule evaluation (0.157×), against 0.51× on PC — **~3.2× worse in ratio terms**
   (§4 previously said 12×; corrected 2026-09-15). Zero-copy delivered exactly what 12.1 hoped
   (upload 1.72 → 0.37 ms) and it was not nearly enough. **The conclusion is robust to how the
   GPU arm is composed:** the measured 2.389 ms arm is DIRECT_RGB (an 8.3 MB upload, no resolve,
   no bind), and substituting Path Z's real forced-completion stages gives **2.576 ms = 6.85×**
   — slightly worse, not better. See §4.
3. **The engine is ~6–7% of the wall either way — corrected 2026-09-15.** This item previously
   read "~1% of the wall … Decode is 99.0%" and then, in the same breath, "roughly 2 ms/keyframe
   out of 33", which is 6%, not 1%. The 99% came from a `decode` figure that **nests the GL
   stages inside itself** (see §3): summing the naive stages exceeds the wall they claim to
   decompose. Disjoint: GL **2.021 ms of 33.428 = 6.0%** (Path Z), **3.068 of 42.299 = 7.3%**
   (Path P). **The structural conclusion is unchanged** — choosing CPU over GPU moves the
   whole-capture time by ~2 s on a 35 s run, and the lever is elsewhere (item 4).
4. **The real lever is the per-keyframe pipeline restart — and it is fixable.** Stage
   decomposition, INSTRUMENTED: `flush()` **14.5 ms**, output wait **22.1 ms** (of which
   **10.6 ms** is sleeping in our own 10 ms `dequeueOutputBuffer` timeout), `seekTo` **4.4 ms**,
   storage **~0**. Real decoding is **~4 ms** — **DERIVED, not instrumented** (`62.8 − 58.5`,
   tagged `[D]` in `keyframe-decode-perf-research.md`, whose §6 says the section-2 decomposition
   is derived; ~11.5 ms inside the output wait remains unattributed). This item previously called
   that figure MEASURED — corrected 2026-09-15. So the 35 s is not a hardware floor: **~25 ms of
   every keyframe is teardown-and-restart plus a timeout we chose.** Two independent fixes
   follow — shorten the timeout (two lines), and stop flushing per keyframe by keeping several
   IDRs in flight (an IDR resets the DPB by definition, so no flush is required for
   correctness). Neither touches the detection engine. **This is where the 10× lives, and
   Story 12.2 did not attempt it — it is scoped work for 12.3/12.4, not a 12.2 finding to
   act on here.**
5. **The colour fork is a correctness trade-off only.** Path Z is 27% faster end-to-end and
   diverges from bit-parity on 0.888% of rule decisions, touching 71% of rules and 44 of the 69
   low-saturation ones. Path P is exact and costs +8.9 ms/keyframe. Since neither beats the CPU,
   **the fork no longer has a performance side to weigh.**
6. **`< 10 s` was not met**: **35.5 s** for a **1 h 13 min 40 s** capture on Path Z (44.9 s on Path P) — i.e. **~125x faster than real time**, or 0.80% of the source duration. Per AC15
   this is reported, not failed — and note that ~99% of it is decode, so it is not an engine
   verdict.

**If forced to ship one colour path today** (AC0c asks for this as an input, not a verdict):
**Path P**. The performance argument that Path Z exists to serve is already lost to the CPU, so
paying 27% for exact, device-independent colour is buying the only property still in contention.
Path Z's divergence is driver-defined and unspecified by AOSP, which means it is not merely
imperfect but **unpredictable across devices** — an unacceptable property for the population the
low-saturation rules were tuned against.

---

## 10. Fixtures, and how to reproduce

**Fixtures used** (all gitignored build outputs; staged via `adb push` to the app's own
`getExternalFilesDir` — `/sdcard/…` is EACCES under scoped storage at targetSdk 36):

| fixture | source |
|---|---|
| capture | `videos/V2/2026-04-27 22-05-34.mp4` (2.3 GB, 1061 keyframes) |
| config | `apps/tooling/output/map_configs/map_config.v2.json` — 134 rules (10 hud / 3 in_match / 121 map across 13 maps) |
| parity corpus | `apps/tooling/output/labeled/v2/` — 2666 PNGs / 16 classes |
| PC GPU reference | `pc_reference_fires.json` (tracked here) — per-rule fire bits, generated from Tool 12 **unmodified** |

**Tracked artifacts in this directory:**

- `pc_reference.py` — generates the PC reference and diffs device fire bits against it
- `pc_reference_fires.json` — the pinned reference (2666 frames)
- `parity_comparison.json` — device vs PC, the 0-disagreement result
- `ac3_frame_diff.py` / `ac3_frame_diff.json` — the colour diff and its diagnosis
- `ac3_numpy_reference.py` / `ac3_numpy_constants.json` — **AC3's constants proof.** Runs
  offline, needs no device and no capture: `python ac3_numpy_reference.py verify-constants`
  walks all 2²⁴ (Y, Cb, Cr) triples and bounds the shader's coefficient error at **1 unit on
  green over 0.179 % of the domain**, ruling out a wrong matrix and a wrong range by
  measurement. `compare-png` reproduces the original single-frame claim and needs a device YUV
  dump. Added 2026-09-15 — the evidence §6 cited previously shipped no script.
- `ac13_pathZ_vs_pathP.json` — the Path Z vs Path P divergence breakdown
- `device_probe_flush.json` + `_run2` / `_run3` — the post-delivery stage probe (3 runs,
  flush 14.6 / 14.2 / 14.6 ms) that produced the §5 correction. Its source analysis is
  [`_bmad-output/implementation-artifacts/keyframe-decode-perf-research.md`](../../../../_bmad-output/implementation-artifacts/keyframe-decode-perf-research.md).

```sh
# 1. build + install (the plugin emits all native sources at prebuild)
pnpm --filter mobile exec expo prebuild --platform android
cd apps/mobile/android && ./gradlew :app:assembleDebug
adb install -r -d app/build/outputs/apk/debug/app-debug.apk

# 2. stage fixtures (subdirectories must be pre-created — adb cannot mkdir under Android/data)
DEST=/sdcard/Android/data/team.warden.mobile/files/warden12_2
adb shell mkdir -p $DEST/labeled
adb push "apps/tooling/output/map_configs/map_config.v2.json" $DEST/map_config.v2.json
adb push "videos/V2/2026-04-27 22-05-34.mp4" $DEST/capture.mp4
for c in $(ls apps/tooling/output/labeled/v2); do
  adb shell mkdir -p $DEST/labeled/$c
  adb push apps/tooling/output/labeled/v2/$c/. $DEST/labeled/$c/
done

# 3. run (debug builds only — the activity lives in the debug manifest overlay)
adb shell am start -n team.warden.mobile/.WardenEngineBenchActivity \
  --es mode all --es video $DEST/capture.mp4 --ei limit 0 --ei cpuFrames 400
adb pull /sdcard/Android/data/team.warden.mobile/files/bench12_2/report_all.json

# 4. off-device parity + colour analysis (needs the tooling venv)
cd apps/tooling
uv run python ../mobile/bench/12-2/pc_reference.py dump
uv run python ../mobile/bench/12-2/pc_reference.py compare <pulled parity_fires.json>
uv run python ../mobile/bench/12-2/ac3_frame_diff.py <pc.png> <device pngs...>
```

Modes: `all`, `parity`, `cpugpu`, `timing`, `framediff`, `seektest`, `pngdump`,
`flushprobe` (the §5 stage decomposition: `seekTo` / `flush()` / queue-to-output /
`INFO_TRY_AGAIN_LATER` count and time / `/proc/self/io` read bytes, over 100 keyframes).

**Thermal context (AC11).** Both full runs completed with `Thermal Status: 0` and every
`CoolingDevice` at `mValue=0` — **no throttling observed**, and the two independent full-capture
runs agree closely (Path Z wall 33.428 vs 33.117 ms/kf; Path P 42.299 vs 42.033). The run is
~8 minutes end to end, which is not long enough to provoke sustained-clock decay on this device.

> ⚠️ **This is an out-of-band `adb` observation, not a collected artifact** *(stated
> 2026-09-15, code review — this report's own discipline is "stated rather than invented")*. No
> Kotlin in the delivery touches `PowerManager.getCurrentThermalStatus()`,
> `addThermalStatusListener` or `/sys/class/thermal`; `deviceProfile()` collects Build fields,
> GL strings and MediaCodec info only, and no delivered JSON carries a thermal field. **The
> reproducible half of the claim is the run-to-run agreement**, which is in the artifacts and
> is the stronger evidence of the two. If 12.3 needs thermal state on the record, the bench has
> to collect it.

**No lint gate exists on this surface.** `apps/mobile`'s `lint` script is an `echo` placeholder
and there is no ktlint or detekt anywhere in the repo — stated rather than invented. There is
likewise **no `androidTest`/instrumentation harness**; following 12.1's precedent (whose AC16
explicitly forbade a GL context in its test suite), the GL/MediaCodec surface is verified by this
report and the device runs, while the **seam** is unit-tested device-free
(`detectionEngine.test.ts`, `detectionEnginePlugin.test.ts` — 12 tests).
