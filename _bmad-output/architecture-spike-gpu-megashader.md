# GPU Mega-Shader Engine Spike (Epic 12 — Stories 12.1 / 12.2 / 12.3)

**Status:** **VERDICT PUBLISHED 2026-09-15.** The GPU mega-shader is **REJECTED**. CPU rule evaluation on the MediaCodec keyframe-decode path is bound. Ladder rung verdict is **provisional pending Story 12.4**.

> ### 🔴 Decision banner — 2026-09-15 (Stephane, AC0a)
>
> **The GPU mega-shader engine is rejected on measurement.** On the reference device the GPU is **6.4× slower** than the device CPU at rule evaluation (2.389 vs 0.376 ms/frame), while producing **bit-identical output** (0 disagreements across 357,244 rule-frame decisions). Zero-copy delivered exactly what Story 12.1 hoped — the upload fell from 1.72 ms to 0.37 ms — and it was nowhere near enough.
>
> **The more important result is that the engine choice barely matters.** Rule evaluation is **6.0–7.3% of the wall clock** on the GPU and ~1% on the CPU. Choosing CPU over GPU moves a 35–45 s run by about 2.7 s. The pivot was launched on the premise that a GPU mega-shader would make rule evaluation cheap enough to fix PERF-002; measurement says **rule evaluation was never the problem**.
>
> **What the problem actually is:** a per-keyframe pipeline teardown-and-restart. Of 42.2 ms/keyframe, `flush()` costs **14.5 ms** and our own `TIMEOUT_US = 10_000` costs **10.6 ms** — **~25 ms per keyframe that is ours to fix**, and that has nothing to do with the detection engine. Owner: **Story 12.4**.
>
> **And PERF-002, as literally written, is already met by a wide margin** — see [NFR re-baseline](#nfr-re-baseline-perf-002--perf-010). The missed `< 10 s` is an **aspiration, not an acceptance criterion**, and is not written up here as a failed NFR.

**Story spec:** `_bmad-output/implementation-artifacts/12-3-engine-verdict-and-perf-rebaseline.md`
**Architecture parent section:** `_bmad-output/architecture.md` → `#### Pre-PRD performance spike [SPIKE BOUND]` and `#### Decision #13 — detection-engine rule-evaluation arm [RESOLVED]`
**Pivot record:** `_bmad-output/sprint-change-proposal-2026-07-16.md`
**Source reports (measurement lives there; this document decides):**

- `apps/tooling/tools/keyframe_engine_bench/REPORT.md` — Story 12.1, PC baseline (Intel UHD 770), 2026-07-16.
- `apps/mobile/bench/12-2/REPORT.md` — Story 12.2, **reference device**, 2026-09-15.

This document is the binding deliverable named by `architecture.md` (spike scope + tree listing), `prd.md` (PERF-002, PERF-010) and the sprint change proposal. Per the `architecture-spike-<topic>.md` convention it carries **the measured numbers, the device profile, the ladder-rung verdict, and the fixtures used**. **Reviewers grep for the H2 sections below.**

**Reports live beside the code; verdicts live here.** Stories 12.1 and 12.2 each wrote a `REPORT.md` next to their implementation and explicitly withheld the verdict. This document does **not** duplicate their measurement sections — it cites them, and carries only the figures the decision rests on.

---

## Device profile

Measured from a current GL context on the reference device, 2026-09-15. Source: `apps/mobile/bench/12-2/device_report_timing.json` → `ac1_device_profile` (identical in `device_report_all.json`, `device_seektest.json`, `device_probe_flush.json{,_run2,_run3}`).

| Property | Value |
| --- | --- |
| model / manufacturer | `22101320G` (Poco X5 Pro 5G) / `Xiaomi` |
| SoC / board / hardware | `SM7325` (Snapdragon 778G) / `redwood` / `qcom` |
| Android | **14** (API **34**) |
| ABIs | `arm64-v8a`, `armeabi-v7a`, `armeabi` |
| `GL_VENDOR` | `Qualcomm` |
| `GL_RENDERER` | **`Adreno (TM) 642L`** |
| `GL_VERSION` | `OpenGL ES 3.2 V@0530.57 (GIT@4bbe300fc3, Ie69fc1c69b, 1747652194) (Date:05/19/25)` |
| `GL_SHADING_LANGUAGE_VERSION` | `OpenGL ES GLSL ES 3.20` |
| `GL_OES_EGL_image_external_essl3` | **advertised AND compiles** — Path Z was available under `#version 300 es`; no ESSL-1.00 fallback was needed |
| decoder | **`c2.qti.avc.decoder`**, `isHardwareAccelerated = true` |
| decoder output layout | semi-planar NV12 — `rowStrides = 1920,1920,1920`, `pixelStrides = 1,2,2` |
| capture as reported by the decoder | `duration_us = 4419633333`, `sync_sample_count = 1061` |

**Adreno 642L, never Adreno 619.** Adreno 619 is the Snapdragon 695 — the _pre-re-anchor_ device. The reference device was re-anchored to the Poco X5 Pro 5G (SM7325 / Android 14) during Story 1.1; see [`architecture-spike-perf-floor.md`](architecture-spike-perf-floor.md) → _Device re-anchor_. Story 12.2 corrected `epics-and-stories.md` and the `sprint-status.yaml` key. **Two stale identities remain in `architecture.md`** — the `#### Pre-PRD performance spike` scope still says _"Poco X5 (Snapdragon 695, 6 GB RAM, 6.67"; Android 13)"_ and the NFR-coverage prose carries a fourth variant. Those are **Story 9.10's prose sweep**, flagged here and deliberately not fixed (scope fence).

### Thermal context — and the honest limit on it

| | value | source |
| --- | --- | --- |
| thermal status | **0 (`NONE`)**, `throttled = false`, every cooling device at 0 | `device_seektest.json` → `ac1_device_profile.thermal` |

> ⚠️ **The two full-capture runs carry no thermal field.** `PowerManager.getCurrentThermalStatus()` collection landed _after_ `device_report_timing.json` and `device_report_all.json` were produced — neither carries a populated `thermal` key. The reading above is from a later `seektest` run on the same device and session. The indirect evidence that the full runs were not throttled is that **two independent full-capture runs agree closely**: Path Z wall **33.428** vs **33.117** ms/kf, Path P **42.299** vs **42.033**. An ~8-minute run is not long enough to provoke sustained-clock decay on this device. **Stated as corroboration, not as a per-run thermal measurement.**

---

## Measured results

Every figure below is traceable to a delivered JSON artifact under `apps/mobile/bench/12-2/`. Measurement status is labelled on every row:

| tag | meaning |
| --- | --- |
| **[M]** | **Measured** — read directly out of a delivered artifact. |
| **[D]** | **Derived** — computed from measured figures; the computation is shown. |
| **[P]** | **Projected** — a construction over measured parts describing a configuration that was never run end to end. |
| **[U]** | **Unbacked** — reported in prose by an upstream story but **not** present in any delivered artifact. |

### The four results the verdict rests on

**1. Correctness is settled, and it is not a reason to choose either engine. [M]**

| | value | source |
| --- | --- | --- |
| rule-frame decisions compared | **357,244** (2666 frames × 134 rules) | `parity_comparison.json` |
| per-rule disagreements | **0** | `parity_comparison.json` |
| frames with any disagreement | **0** | `parity_comparison.json` |
| packed-LUT SHA-256 vs `lut.py` | `b8287e08…f62c5` — **matches**; 7200 bytes, 134 rules (57 normal / 9 wrap / 68 full-circle) | `device_report_timing.json` → `ac5_lut_cross_check` |

The GLSL is bit-exact on Adreno. **Parity is banked and it buys the GPU nothing**, because the Kotlin CPU arm produced the same bits over the same corpus (result 2 below: `fire_bit_disagreements = 0`).

> ⚠️ **[U] — the three per-classifier accuracy rows are NOT backed by a delivered artifact.** `parity_comparison.json` carries fire-bit counts only; it has no `ac14_classifier_accuracy` key. Story 12.2 found and fixed the producing code path (`accuracy_from_fires()` sat below the `__main__` guard, unreachable from any CLI path) but did not re-run `compare`, and labelled the table accordingly. The figures reported in prose — hud `0.980495 (2614/2666)`, in_match `1.0000 (2666/2666)`, map_id `1.0000 (2286/2286)` — are carried here **with that label attached** and must not be cited as measured until a `compare` re-run lands them in the JSON. **The fire-bit half of the parity claim is fully backed, and it is the half this verdict uses.**

**2. 🔴 The GPU lost, and lost harder on device than on PC. [M]**

Decode excluded from both sides, identical bytes, identical bounds, identical `count/area >= min_ratio`, 400 frames, 134 rules. Source: `device_report_all.json` → `ac12_cpu_vs_gpu`.

| | ms/frame | source |
| --- | --- | --- |
| **device CPU** — plain Kotlin, integer `RGB2HSV_b` | **0.375807** | `cpu_ms_per_frame` **[M]** |
| **device GPU** — upload + draw + `glReadPixels` + `glFinish()` | **2.389213** | `gpu_ms_per_frame` **[M]** |
| **ratio** | **0.157293 — the GPU is 6.4× slower** | `speedup_gpu_over_cpu` **[M]** |
| fire-bit disagreements between the two arms | **0** | `fire_bit_disagreements` **[M]** |
| 12.1, same comparison on PC (Intel UHD 770) | CPU 1.667 / GPU 3.253 = **0.51×** | 12.1 `REPORT.md` §4 **[M]** |

**Robust to how the GPU arm is composed. [D]** The measured 2.389 ms arm runs `DIRECT_RGB` — an 8.3 MB RGBA upload, with no resolve pass and no bind. Substituting Path Z's _real_ forced-completion stages from `device_report_timing.json` → `ac11_forced_completion` (ZERO_COPY):

```
bind 0.3667965 + resolve 1.306458 + shader 0.5982815 + readback 0.3054945
  = 2.5770305 ms   vs CPU 0.375806905 ms   =  6.86× slower
```

> **Rounding note, carried deliberately.** 12.2's `REPORT.md` quotes this sum as **2.576 ms → 6.85×**. The delivered medians sum to **2.5770305 → 6.857×**. The difference is ≤ 0.001 ms of prose rounding, **not** a data difference; this document quotes the JSON. Either way **the conclusion strengthens rather than weakens** when the GPU arm is composed out of the stages a shipping path would actually pay.

> ⚠️ **The CPU figures are not a hardware comparison.** 12.1's PC CPU number (1.667 ms) is Python driving 134 separate `cv2.inRange` calls; the device number (0.376 ms) is a tight Kotlin loop. The phone's CPU is not faster than a desktop's — the _implementation_ is leaner. What survives either implementation is the conclusion: **evaluating 134 tiny rects is a trivially cheap CPU task, and routing it through a GPU costs more than it saves.** The shipped rects are 1–25 px (mode 2×2; fourteen are literally 1×1) — ~800 texel fetches per frame against fixed per-draw costs of 2.577 ms.

**3. The engine — either engine — is ~6–7% of the wall. [M] + [D]**

Source: `device_report_timing.json` → `ac11_ac13_timing_naive`, full capture, 1061 keyframes, count-asserted `1061 == 1061`.

| stage, ms/keyframe | **Path Z** (zero-copy) | **Path P** (bit-parity) |
| --- | --- | --- |
| decode _(nested — see below)_ | 33.105 | 42.085 |
| upload / bind | 0.378 | 1.569 |
| resolve | 0.256 | 0.144 |
| shader | 0.108 | 0.048 |
| readback | 1.279 | 1.307 |
| **wall** | **33.428** | **42.299** |
| **whole capture** | **35.467 s** (`35466.802` ms) | **44.879 s** (`44879.327` ms) |
| **vs real time** | **×124.6** | **×98.5** |
| one-off engine setup (excluded above) | 15.202 ms | 4.846 ms |
| one-off EGL context (excluded above) | **47.042 ms** — `device_seektest.json` → `ac11_one_off_egl_context_ms` | — |

**GL share of the wall, disjoint [D]:**

```
Path Z:  0.377717 + 0.256002 + 0.107528 + 1.279336 = 2.021 ms / 33.428 =  6.0%
Path P:  1.568644 + 0.144035 + 0.048465 + 1.307345 = 3.068 ms / 42.299 =  7.3%
```

> 🔴 **It is 6.0% / 7.3% — NOT 1%.** The `decode` row is **not a disjoint stage**: `decodeNs` is assigned from a `t0` fixed at the decode loop's entry and snapshotted before `onFrame()` runs, so it nests the GL stages of every keyframe but the last. The tell is arithmetic — summing the Path Z stages gives **35.125** against a **wall of 33.428**, and a partition cannot exceed the whole. The earlier _"decode is 99% / the engine is ~1%"_ figure came from those nested numbers and was corrected in 12.2's code review. **Do not re-introduce it.**

**Cost of the engine choice, stated plainly [D]:** `1061 keyframes × 2.577 ms = 2.73 s`. On a 35–45 s run, **choosing CPU over GPU moves the whole-capture time by under three seconds.**

**4. 🔴 The bottleneck is not decode, and it is ours to fix. [M] + [D]**

Dedicated stage probe, ByteBuffer path, 100 keyframes × 3 runs. Source: `device_probe_flush.json`, `_run2`, `_run3` → `decode_probe` / `idle_flush_probe`.

| stage | run 1 | run 2 | run 3 | carried | share |
| --- | --- | --- | --- | --- | --- |
| `seekTo` (median) | 4.364 | 4.477 | 4.298 | **~4.4 ms** | 10% |
| **`flush()`** (median) | 14.618 | 14.198 | 14.553 | **~14.5 ms** | **34%** |
| queue IDR → first output (mean) | 22.073 | 22.813 | 21.998 | **~22.1 ms** | 52% |
| ⤷ _of which sleeping in `dequeueOutputBuffer`_ | 10.593 | 10.670 | 10.612 | **_~10.6 ms_** | _25%_ |
| `INFO_TRY_AGAIN_LATER` per keyframe | 1.02 | 1.02 | 1.02 | **1.02** | — |
| `TIMEOUT_US` in force | 10 000 | 10 000 | 10 000 | **10 000 µs — our own choice** | — |
| probe wall | 42.204 | 43.226 | 41.608 | **~42.2 ms** | 100% |
| `flush()` on an **idle** codec (median) | 1.821 | 3.555 | 1.786 | **1.8–3.6 ms** | — |
| storage read per keyframe | 5.35 KB | 6.48 KB | 0.04 KB | **~0 — the page cache absorbs it** | — |

**Accounted [D]:** `4.4 + 14.5 + 22.1 = 41.0` of `42.2` = **97%**.

> 🔴 **"Real decoding is ~4 ms" is DERIVED, not instrumented.** It comes from `62.820 − 58.5` against the A′ strategy comparison, is tagged `[D]` in [`keyframe-decode-perf-research.md`](implementation-artifacts/keyframe-decode-perf-research.md) (whose §6 states outright that its section-2 decomposition is _dérivée, pas instrumentée_), and **~11.5 ms inside the 22.1 ms output wait remains unattributed** — it is _not_ all decoding. 12.2's §9 item 4 was corrected on exactly this point. **Carried here in its corrected form.**

**The cost is a per-keyframe pipeline restart, and one half of it is a plain implementation defect.** `flush()` costs 14.5 ms in the loop against 1.8–3.6 ms idle — a factor of **4 to 8** — so the expense is the `END_OF_STREAM` → flush state transition, not the HFI round trip. And the 10.6 ms is the codec not having produced output the first time we ask, against a 10 ms timeout we selected ourselves.

**Corroboration that the time is not going into decoding [M]:** a software-decode control (`ffmpeg-kit`, `-skip_frame nokey`) ran the same file in **38.068 s** (`device_report_timing.json`) and **33.660 s** (`device_report_all.json`) — a **13% run-to-run spread** — against MediaCodec's hardware decode stage at ~35.1 s. A hardware decoder is many times faster than software at _decoding_; that the two land inside each other's noise is only possible if decoding is not where the time goes. _(12.2's earlier "hardware decode buys ~8%" was smaller than the control's own spread and was withdrawn. Do not quote it.)_

### Decode-strategy comparison — carried in its corrected form

Source: `device_report_timing.json` → `ac0b_decode_strategy_comparison`, 60 keyframes each.

| strategy | decode ms/kf **[M]** |
| --- | --- |
| **A — absolute `SEEK_TO_CLOSEST_SYNC` per keyframe** (shipped) | **32.937** |
| A′ — single-pass sync-filtered demux | **62.820** |

> 🔴 **32.937 / 62.820 — NOT 33.68 / 116.45.** Those earlier figures were corrected during 12.2's delivery and must not be restated.

A′ is slow because `NuMediaExtractor::fetchTrackSamples` reads sample **data** on every `advance()`, in batches of up to 8 for video tracks — it drags 2.3 GB through the extractor to reach one sample in 250.

**Keyframe index — reported outside every wall clock above [M]:**

| | count | cost | source |
| --- | --- | --- | --- |
| ground-truth sample-table scan | 1061 | **62.070 s** | `ac0b_keyframe_index.ground_truth_scan_ms` |
| seek-built PTS list (what the decode loop consumes) | 1061 | **2.290 s** | `ac0b_keyframe_index.seek_built_pts_ms` |
| counts agree | ✅ | | `counts_agree` |

> 🔴 **The 62 s ground-truth scan is a bench-time assertion and MUST NEVER SHIP.** It is a full-file read, not an index walk. Story 12.4 takes the index from the seek-built list (2.29 s) or reads `stss` directly. **It earned its keep:** the incremental scan originally prescribed — `seekTo(lastPts + 1, SEEK_TO_NEXT_SYNC)` in a loop — **stops advancing after the second sync sample**, reporting **2** keyframes against 1061 (`device_seektest.json` → `ac0b_prescribed_incremental_scan`). Without the assertion the bench would have reported a self-consistent `2 == 2` and a beautiful ms/keyframe figure computed over two frames.

### Colour — recorded for the record; **not load-bearing under the bound engine**

Path Z vs Path P divergence, full capture. Source: `ac13_pathZ_vs_pathP.json`.

| | value | check |
| --- | --- | --- |
| decisions compared | **142,174** | = 1061 × 134 ✅ |
| per-rule disagreements | **1262** | **0.888%** [D] |
| keyframes with ≥1 disagreement | **635 of 1061** | **59.9%** [D] |
| rules affected | **95 of 134** | **70.9%** [D] |
| …low-saturation | **44 of 69** | |
| …full-circle branch | **43 of 68** | |
| worst offenders | `engine/engine_z00` 209 · `atlantis/atlantis_z02` 136 (low-sat) · `v2/hud_z00` 103 · `helios/helios_z03` 88 (low-sat) | |

Colour accuracy vs FFmpeg `rgb24`, in OpenCV HSV units, over rule regions. Source: `ac3_frame_diff.json`.

| | ΔS, all 134 rects | ΔS, 69 low-sat |
| --- | --- | --- |
| Path P (bit-parity) | **2.46** | **2.86** |
| Path Z (zero-copy OES) | **5.64** | **5.62** |

> ⚠️ **Do not quote `ac3_frame_diff.json`'s `diagnosis` string.** It reads _"MATRIX-ERROR-scale discrepancy (709 vs 601)"_ — a heuristic label emitted by the analysis script, **superseded** by 12.2 §6, which proved the shader's coefficients exhaustively and offline over all 2²⁴ (Y, Cb, Cr) triples (`ac3_numpy_reference.py verify-constants`; error bounded at 1 unit on green over 0.179% of the domain). Neither path shows the range-error signature 12.1 measured at ΔS ≈ 19.68. The residual is a **chroma-upsampling policy difference** (nearest vs swscale interpolation), ≤ 3 units of 255.

**Under the bound engine this fork does not exist.** See [Engine verdict](#engine-verdict) → AC0b.

---

## NFR re-baseline (PERF-002 / PERF-010)

### PERF-002 — re-baselined, and what is inside the number

**The budget, re-verified here and not inherited from prose:**

| | value | provenance |
| --- | --- | --- |
| source duration | **4419.633 s** = **1 h 13 min 40 s** | `ac1_device_profile.mediacodec.duration_us = 4419633333` **[M]**, corroborated by 1061 × 4.1667 s GOP = 4420.87 s **[D]** |
| **PERF-002 budget @ ≤ 5%** | **220.98 s** (3 min 41 s) | 4419.633 × 0.05 **[D]** |
| measured, **Path Z** (zero-copy, GPU) | **35.467 s = 0.802%** — ×124.6 real time | `total_wall_ms = 35466.802` **[M]** |
| measured, **Path P** (bit-parity, GPU) | **44.879 s = 1.015%** — ×98.5 real time | `total_wall_ms = 44879.327` **[M]** |

> **The capture is 1 h 13 min 40 s, not the "~2 h" the 12.1 / 12.2 AC text says.** Corrected in 12.2's Dev Agent Record. Every per-keyframe figure is unaffected; the whole-capture totals must be read against 1 h 14.

**🔴 The number this re-baseline binds is Path P's, not Path Z's — and the reason matters.**

Path Z is a zero-copy decode **into a GL texture**. It exists to feed the shader and nothing else. **The bound engine has no shader**: a CPU rule evaluator needs the pixels on the CPU, which is the ByteBuffer path — Path P. Re-baselining PERF-002 off 35.5 s would mean quoting a number produced by the configuration this spike just rejected. The conservative, defensible figure is:

> ### **PERF-002 re-baselines at ≤ 1.02% of source duration — 44.879 s measured against a 220.98 s budget. MET by ~4.9×.**

This is an **upper bound** on the bound configuration, because Option A _removes_ work from the path that produced it (the GL stages) and adds back only the CPU arm:

```
[P] projected, bound configuration:
      Path P wall                    42.299 ms/kf   [M]
    − Path P disjoint GL stages       3.068 ms/kf   [M]
    + AC12 CPU rule-eval arm          0.376 ms/kf   [M]
    = 39.607 ms/kf  × 1061 kf  =  42.0 s  =  0.95% of source
```

**Labelled [P], and used nowhere as the binding number.** It is a construction over three measured parts describing a configuration that **was never run end to end**. Story 12.4 measures it for real.

**🔴 The honesty requirement — what this number covers and what it does not.**

The 44.9 s is a **detection-pass bench**, not an auto-slice run. PERF-002 scopes _auto-slice processing time_. Excluded from every wall clock above, and each of them would add to a real run:

| excluded | measured cost, if known | status |
| --- | --- | --- |
| keyframe index build | **2.290 s** by seek (`seek_built_pts_ms`); the 62.070 s ground-truth scan **must never ship** | **[M]**, reported outside the wall by construction |
| engine / EGL one-off setup | 4.846–15.202 ms engine, 47.042 ms EGL context | **[M]**, excluded by construction |
| **segmentation** (round-boundary detection → round list) | — | **never measured** |
| **thumbnail export** | — | **never measured** |
| the rest of the auto-slice pipeline (`processingPipeline.ts` stages, MMKV checkpointing, clip metadata) | — | **never measured** |

**Therefore:** the re-baselined figure says _the detection pass costs ~1% of source duration on the reference device_. It does **not** say the full auto-slice pass does. The margin is large enough — ~4.9×, with ~176 s of the budget unused — that the excluded stages would have to cost roughly **four times the entire detection pass** to breach the NFR, which is why this re-baseline is defensible rather than optimistic. But it is bounded, and **Story 12.4 must re-measure PERF-002 end to end over the real pipeline** before the NFR is treated as closed.

**The `< 10 s` aspiration.**

`< 10 s` is **not an acceptance criterion** — not in `prd.md`'s PERF-002, and 12.2's AC15 says so explicitly. It is **missed**: the best measured figure is 35.5 s (Path Z) and the bound configuration projects to ~42 s. **It is not written up here as a failed NFR, and the met NFR is not written up as a triumph of the shader** — the shader contributes 6% of the wall, and the CPU arm replaces it with ~1%.

**Where the aspiration could actually come from [P]:**

```
  probe wall                       42.2 ms/kf   [M]
− flush() per keyframe             14.5 ms/kf   [M]  (Story 12.4)
− TIMEOUT_US sleep                 10.6 ms/kf   [M]  (Story 12.4, two lines)
= ~17.1 ms/kf  × 1061  ≈  18.1 s   →  0.41% of source
```

**[P] — PROJECTED. Neither fix has been attempted or measured.** It would not reach `< 10 s`, but it lands within ~2× of it, and it is **~10× more headroom than the entire engine question was ever worth** (2.73 s). That comparison is the single most decision-relevant sentence Epic 12 produced.

### PERF-010 — disposition

> ### **PERF-010 stays a SOFT TARGET. Story 12.2's reference-device run does NOT bind a number here.**

**Reasoning, stated rather than left ambiguous:**

- PERF-010 was softened from _"measured floor TBD"_ to _"soft reference target — Poco X5 Pro 5G class; no committed minimum supported device"_ on **2026-05-09**, when Story 1.1.1's measurement was cancelled in favour of ship-and-observe. **That is a product decision, not a measurement outcome**, and nothing Epic 12 measured reverses it.
- The 2026-07-16 pivot **re-pointed which spike would report a number** (Story 1.1 → Story 12.3). It did not re-arm a measured floor, and this document does not create one.
- What 12.2 measured is a **detection-pass throughput on one device**, not a minimum-supported-device floor. A floor is a statement about the _population_ of devices V1 will accept; a single-device run cannot produce one. Binding PERF-010 would require a device matrix, which no story owns and none is proposed here.
- V1 launch is **not gated** on a measurement. It ships against whatever the Play Store filter accepts, and is revisited only if real-user feedback surfaces unacceptable performance.

**What the reference-device run _does_ contribute:** a documented capability point — _SM7325 / Adreno 642L / Android 14 completes the detection pass at ~1% of source duration, with no thermal throttling observed over an ~8-minute run._ That is recorded as **evidence**, not as a floor.

**Cascade:** `architecture.md`'s NFR-coverage line previously read _"PERF-010 (mobile reference-device floor): TBD pending spike — architecture's load-bearing first deliverable."_ It is updated by this story to state the soft-target disposition and point here.

---

## Engine verdict

> ### 🔴 **VERDICT — Option A. The GPU mega-shader is REJECTED. CPU rule evaluation on the MediaCodec keyframe-decode path is BOUND.**
>
> Decided by Stephane, 2026-09-15, per the handoff in `sprint-change-proposal-2026-07-16.md`. Recorded architecturally as `architecture.md` → **Decision #13**.

### What is bound

| | |
| --- | --- |
| **decode** | MediaCodec keyframe decode — absolute `SEEK_TO_CLOSEST_SYNC` per keyframe (strategy A, 32.937 ms/kf, against A′'s 62.820), ByteBuffer output, bit-parity YUV→RGB conversion |
| **rule evaluation** | **Kotlin CPU** — the integer `RGB2HSV_b` arm, already written as `WardenCpuBaseline.kt` and already validated at **0 fire-bit disagreements** against the GPU arm |
| **rule packing** | `WardenRulePacker` — byte-identical semantics to `lut.py`, SHA-256 verified against the reference |
| **keyframe index** | the seek-built PTS list (2.290 s). The 62 s ground-truth scan is bench-only and **must never ship** |

### What is dropped

EGL context and pbuffer surface · the GLES mega-shader · the LUT texture upload · the full-frame resolve pass · `glReadPixels` synchronisation · driver-defined OES colour conversion · **the entire Path Z / Path P colour fork**.

### Why — the reasoning, stated as a decision and not as a summary

**1. The performance argument that launched the pivot is falsified.** The founding chain was _PERF-002 is unacceptable → the per-frame CPU `cv2.inRange` path is the ceiling → a GPU mega-shader removes the ceiling._ **Link 2 is false on the reference device.** Rule evaluation is 0.376 ms/frame on the CPU against a 33–42 ms wall — it was never the ceiling, on either engine. The GPU does the same work in 2.389–2.577 ms and is therefore **6.4–6.9× slower**, which is _worse_ than PC's 0.51×, not better. Zero-copy worked (bind 1.720 → 0.367 ms) and did not come close to closing the gap.

**2. Correctness is explicitly NOT the reason.** The shader is bit-exact on Adreno over 357,244 decisions, including the 31 rules with bands asymmetric about their centre, the 9 wrap-branch rules that depend on negative signed `>>` sign-extending, and the 69 low-saturation rules. **If the decision were about correctness, the GPU would survive it.** It is about cost, and the two arms are indistinguishable in output.

**3. The GPU's cost is structural, not tuning-fixable.** The shipped rects are 1–25 px (fourteen are 1×1) — ~800 texel fetches per frame. Against that, the fixed per-draw costs are a full-frame resolve (1.306 ms), the shader (0.598 ms), a readback sync (0.305 ms) and the bind (0.367 ms). **The arithmetic was never the bottleneck, so making it parallel buys nothing.** No shader tuning changes that ratio; only a very much larger ruleset would, and none is proposed.

**4. Option A removes an entire architectural surface at no measured cost.** No EGL context to own and make current, no thread-affinity constraint imposed by GL, no LUT texture upload, no readback synchronisation, and no **driver-defined, AOSP-unspecified** colour conversion. Every one of those is a class of failure that cannot occur in code that does not exist. Story 12.2 spent a full parity run on exactly one of them — a rule-major vs row-major transpose that produced _plausible-looking detections from garbage_, and that both the LUT byte-check and the render-target self-test passed straight through.

**5. Option B was not chosen because the justification it requires does not exist.** Option B is defensible only on a **non-performance** argument — headroom against a much larger future ruleset, or offloading the CPU for concurrent work. Neither is on the roadmap: the ruleset is 134 rules across 13 maps, growth is one rule set per new map, and nothing in the pipeline competes for the CPU during a detection pass. **No such justification was offered, so Option B was not taken.**

**6. Option C was not chosen because it re-creates the defect this story exists to fix.** Deferring the rule-eval arm would leave Story 9.16 unable to re-point Tool 9 at an engine that is not chosen, leaving **REL-006's ≥95% accuracy floor with no instrument at all**. And there is almost nothing left to defer: both arms are written, and the bound one is already validated at 0 disagreements.

### What this rejection does NOT say, and Epic 12's actual yield

**The pivot's judgment was sound even though its mechanism was wrong.** The engine question had to be answered before ~20 stories of Epics 5 / 6 / 7 were built on top of it. What Epic 12 refutes is **a mechanism, not the decision to ask.**

Epic 12 produced, and all of it survives the rejection:

- A **measured decode decomposition** nobody had — and with it the discovery that ~25 ms of every keyframe is ours to reclaim.
- A **bit-exact integer HSV rule evaluator** validated on Adreno across 357,244 decisions — which is what makes the CPU arm trustworthy, because the two arms check each other.
- **`WardenRulePacker`**, with byte-identical semantics to `lut.py`, SHA-256 verified.
- A **working MediaCodec keyframe-decode path** with a count assertion that caught a silent 2-vs-1061 failure.
- The falsification of three separate wrong diagnoses that were live before it ran: _"the pipeline is decode-bound"_, _"storage / FUSE is a contributor"_, _"seeking is the main cost"_.
- **A ~2.5× decode-loop speedup target with two concrete, cheap fixes** — 25.1 of 42.2 ms/keyframe, worth ~26 s on a 35–45 s run, against the 2.7 s the entire engine question was worth.

### AC0b — colour path: **N/A**

**The fork dissolves under Option A.** Path Z exists only to hand a `samplerExternalOES` texture to a shader; with no shader there is no OES conversion and no divergence to weigh. The bound engine reads the **ByteBuffer path's bit-parity conversion** (ΔS 2.46 over all 134 rects, 2.86 over the 69 low-saturation rules, with no range-error signature).

**Recorded as N/A with its reason, not left blank.** For the record, 12.2's input-not-verdict recommendation had been **Path P**, on the grounds that Path Z's 0.888% divergence is _driver-defined and unspecified by AOSP_ — therefore unpredictable across devices, and landing on 44 of the 69 low-saturation rules, exactly where the accepted `h_tol = 180` tuning is most fragile. **Option A reaches the same colour behaviour by removing the choice instead of making it.**

### AC0d — decode-loop fix owner: **Story 12.4**

The two fixes — shorten `TIMEOUT_US` (two lines, ~10.6 ms/kf) and stop flushing per keyframe by keeping several IDRs in flight (~14.5 ms/kf; an IDR resets the DPB by definition, so no flush is required for correctness) — are **re-homed to Story 12.4**. Story 12.3 is `fits-in-one-sprint` and writes no production code; taking a Kotlin change here would break that fence and re-open a device-measurement loop. **The headroom they represent is quantified above**, so the deferral is informed rather than an omission.

---

## Ladder rung verdict

The Innovation #1 fallback ladder lives in `architecture.md` → `#### Pre-PRD performance spike` → _Spike outcomes & ladder_. All five rows were audited on 2026-09-15 against the question **"is the trigger reachable, and does the remedy engage the measured cost?"** Two rows failed it and are amended; one is answered; one is carried verbatim.

### Rung-0 (Pass row) — **PROVISIONAL pending Story 12.4**

> **`rung-0 provisional — engine bound on measurement (CPU rule evaluation on MediaCodec keyframe decode); PERF-002 MET and re-baselined at ≤ 1.02%; PERF-003 / PERF-004 UN-INSTRUMENTED; PERF-005 unmeasured; the pipeline binding is Story 12.4's. Cloud-fallback remains FORBIDDEN regardless.`**

The Pass row's condition is _"all 4 PERF NFRs met on reference device **with a real engine binding**"_. Three things are true and must be said together:

1. **Only PERF-002 is measured.** It is met by ~4.9× on the bound configuration's conservative bound (44.879 s against a 220.98 s budget), with the coverage caveat above.
2. **PERF-003 and PERF-004 have never been measured** and have no instrument — see rung 2. **PERF-005** (clip export ≤ 2× clip duration) is likewise unmeasured; the export surface does not exist yet.
3. **"With a real engine binding" is not yet true.** Story 12.2 shipped a **bench**, not a pipeline binding. The engine is _chosen_; it is not _wired_. That is Story 12.4's.

**Precedent followed:** Story 1.1's provisional rung-0 ([`architecture-spike-perf-floor.md`](architecture-spike-perf-floor.md) → _Ladder rung verdict — accepted as final_). The difference is that 1.1's provisional verdict was later **accepted as final without a measurement run** (2026-05-09 ship-and-observe). This one is provisional pending **an integration**, not a measurement — and Story 12.4 is scheduled, so it resolves rather than lapses.

### Rung 1 — 🔴 **RE-ARMED. The old remedy was INERT and nobody had recorded it.**

**Old remedy:** _"lower auto-slice frame-sampling rate."_

**Why it was inert.** Under a keyframe-only engine **the sampling rate IS the GOP** — 4.1667 s, 1061 keyframes for this capture. There is no continuous frame-rate knob to turn down: you either decode a keyframe or you skip it. And the thing the old remedy was reaching for — cheaper per-frame rule evaluation — is **6.0–7.3% of the wall**, so turning that knob, if it existed, would recover almost nothing. **This is the same class of defect as rung 3's unreachable _"JSI binding does not ship"_ trigger**, which the 2026-07-16 pass fixed while leaving rung 1 alone: a rung that reads armed and is not.

**New remedy — two steps, cheapest first, and both engage the measured cost:**

| step | remedy | measured basis | cost to the product |
| --- | --- | --- | --- |
| **1a** | **Reduce per-keyframe decode-loop overhead** — shorten `TIMEOUT_US` (~10.6 ms/kf); stop flushing per keyframe by pipelining IDRs (~14.5 ms/kf) | `device_probe_flush*.json`: 25.1 of 42.2 ms/kf | **none** — no accuracy or granularity change. Try this first. |
| **1b** | **Decimate keyframes** — process every _N_th keyframe | decode is ~94% of the wall and scales linearly with keyframe count | **real** — detection granularity falls from 4.17 s to _N_ × 4.17 s |

**Step 1b is what _"lower the sampling rate"_ can honestly mean under this engine**, which is why the rung is re-armed rather than retired.

**PRD cascade.** `mobile-AUTO-SLICE-001`'s _"with reduced sampling on weak hardware"_ clause attaches to **step 1b** and survives intact — the clause is still true, it now simply names a keyframe-decimation mechanism rather than an imaginary frame-rate knob. **Step 1a carries no PRD clause**, because it has no user-visible effect.

### Rung 2 (PERF-003 / PERF-004) — **trigger marked UN-INSTRUMENTED; rung retained**

**The remedy is sound** — dropping Minimap+HUD overlay rendering on weak hardware, device-profile-gated, degrading view modes to Full + Minimap. **The trigger cannot fire.**

- PERF-003 (view-mode toggle ≤ 100 ms) and PERF-004 (Cinema Mode cold-start ≤ 1.5 s) have **never been measured**. Story 1.1's substrate-gap audit found the surfaces do not exist: no `expo-av` / `expo-video` dependency, no `<Video>` component, `CinemaModeScreen.tsx` a visual stub, no Cinema / Card routes.
- Both became **soft UX targets on 2026-05-09**, when Story 1.1.1 was cancelled — measurement gates downgraded to design targets by an explicit ship-and-observe decision.
- There is therefore **no instrument that could produce the "over budget" reading this rung's trigger requires.**

**Disposition (AC0c): retained, and explicitly labelled `TRIGGER UN-INSTRUMENTED (2026-09-15)`.** Not retired — the remedy is the right one, and the rung should exist the day a number does. Not re-armed — arming it means building a view-mode / cold-start timing instrument, which is real work that no story currently owns.

**What arming it would take, named rather than assumed:** the instrument belongs with the surfaces, i.e. **Stories 5.4 / 5.5 / 6.6**, when Card View, Cinema Mode and the clip surfaces are built. Until then this rung fires only on **observed** behaviour (a user report, a hands-on session), not on a measurement. **A rung that fires on observation is honest; a rung that claims a measurement it cannot take is the defect this story exists to remove.**

### Rung 3 (Hard fail) — **verdict: DOES NOT FIRE. Not yet retired.**

The trigger was re-armed in wording on 2026-07-16 to _"the on-device detection engine does not ship as a real binding within V1 timeline"_ (engine-agnostic; it previously fired only on _"JSI binding does not ship"_, unreachable under a shader engine). **Evidence now exists, so the verdict against it can be stated:**

- **An engine is bound** — CPU rule evaluation on MediaCodec keyframe decode (Decision #13).
- **Both arms are written**, and the bound one is validated at **0 fire-bit disagreements** over 357,244 decisions.
- **A working decode path exists** on the reference device, count-asserted at 1061 == 1061.

**Rung 3 does not fire. It is not yet retired**, because the _binding_ — wiring the engine into `processingPipeline.ts` — is **Story 12.4's**, and the trigger is about shipping a real binding _within the V1 timeline_. **Rung 3 retires when Story 12.4 lands.** If 12.4 does not land in the V1 timeline, this rung fires on its own terms and auto-slice defers to V2.

### FORBIDDEN row — **carried VERBATIM, unchanged**

> **FORBIDDEN — fall back to cloud CV. NEVER.** Breaks Innovation #1 (privacy + lower marginal cost). Architecture asserts this is forbidden regardless of spike outcome.

**[INVARIANT 3] holds under the verdict**: both candidate engines are on-device, and the bound one — Kotlin CPU rule evaluation over locally decoded keyframes — is _more_ obviously on-device than the one it replaced. **Not re-worded, not modernized, not folded into another row.** It remains the only absolute prohibition in the ladder; every other rung has now been re-armed, re-labelled or answered, and this one has not moved since it was written.

---

## Fixtures

Exactly as Story 12.2 recorded them. All are gitignored build outputs, staged via `adb push` to the app's own `getExternalFilesDir` (`/sdcard/…` is `EACCES` under scoped storage at `targetSdk 36`).

| fixture | path | properties |
| --- | --- | --- |
| **capture** | `videos/V2/2026-04-27 22-05-34.mp4` | 2.3 GB · 1920×1080 h264 `yuv420p` `color_range=tv` `bt709` · **4419.633 s** · GOP **4.1667 s** · **1061 keyframes** |
| **config** | `apps/tooling/output/map_configs/map_config.v2.json` | **134 rules** — 10 hud / 3 in_match / 121 map across 13 maps · modes 68 full-circle / 9 wrap / 57 normal |
| **parity corpus** | `apps/tooling/output/labeled/v2/` | **2666 PNGs** / 16 classes |
| **PC GPU reference** | `apps/mobile/bench/12-2/pc_reference_fires.json` (tracked) | per-rule fire bits for 2666 frames, generated from Tool 12 **unmodified** |
| **PC baseline report** | `apps/tooling/tools/keyframe_engine_bench/REPORT.md` | Intel UHD 770 · GL 3.3.0 · FFmpeg 8.0.1 · Python 3.11.15 · moderngl 5.12.0 |

**Delivered evidence artifacts** — every figure in this document resolves to one of these (all under `apps/mobile/bench/12-2/`):

| artifact | what it backs here |
| --- | --- |
| `device_report_timing.json` | device profile · full-capture naive split (both paths) · forced-completion medians · decode-strategy A vs A′ · keyframe index · LUT cross-check · ffmpeg-kit control (38.068 s) |
| `device_report_all.json` | **`ac12_cpu_vs_gpu`** — the decisive CPU-vs-GPU number · second independent full-capture run · ffmpeg-kit control (33.660 s) |
| `parity_comparison.json` | 0 disagreements / 357,244 decisions / 0 frames |
| `ac13_pathZ_vs_pathP.json` | Path Z vs Path P divergence, per-rule breakdown |
| `ac3_frame_diff.json` | colour ΔH / ΔS / ΔV — whole-frame, rule-regions, low-sat |
| `ac3_numpy_constants.json` (+ `ac3_numpy_reference.py`) | the exhaustive offline constants proof over all 2²⁴ YUV triples |
| `device_probe_flush.json` · `_run2` · `_run3` | the stage decomposition — `seekTo` / `flush()` / queue-to-output / `INFO_TRY_AGAIN_LATER` / `/proc/self/io` |
| `device_seektest.json` | thermal status · one-off EGL context cost · the prescribed-incremental-scan failure (2 vs 1061) |
| `pc_reference.py` · `pc_reference_fires.json` | the PC reference, and the device-vs-PC diff |

**Reproduction:** `apps/mobile/bench/12-2/REPORT.md` §10 carries the full build / stage / run / analyse sequence and the mode list (`all`, `parity`, `cpugpu`, `timing`, `framediff`, `seektest`, `pngdump`, `flushprobe`).

**Supporting analysis:** [`keyframe-decode-perf-research.md`](implementation-artifacts/keyframe-decode-perf-research.md) — the independent decode-cost investigation that prompted the `flushprobe`; its §6 marks its own section-2 decomposition as **derived, not instrumented**.

---

## What this does NOT bind

Mirrors Story 12.2's AC15 block, and extends it with what the verdict itself does not settle.

- **PERF-010 is not bound.** It remains a **soft target**, not a measured floor, per the 2026-05-09 ship-and-observe decision. V1 launch is not gated on a measurement. See [NFR re-baseline](#nfr-re-baseline-perf-002--perf-010).
- **PERF-002's re-baseline covers the detection pass only.** Segmentation, thumbnail export and the rest of the auto-slice pipeline are **outside every number here** and were never measured. Story 12.4 must re-measure end to end.
- **PERF-003 / PERF-004 / PERF-005 are not measured and have no instrument.** They are soft UX targets. Rung 2's trigger is explicitly un-instrumented.
- **In-sample parity is not accuracy-in-the-world.** The 0 / 357,244 result is a **parity target** — the device reproducing the PC reference on the corpus the rules were tuned against. **There is no holdout.** It is not, and never was, a generalization claim.
- **🔴 REL-006's ≥ 95% map-identification floor is NOT gated here.** That is **Story 9.9b's**, instrumented by **Tool 9** via **Story 9.16**. Nothing in this spike measures accuracy on an unseen test set.
- **The three per-classifier accuracy figures are `[U]` — unbacked by any delivered artifact.** See [Measured results](#measured-results).
- **The engine is chosen, not wired.** Story 12.2 delivered a **bench**. No production code path calls the bound engine today; `gameDetector.ts`, `mapIdentifier.ts`, `blackScreenDetector.ts`, `segmentation.ts` and `processingPipeline.ts` are untouched. **That is Story 12.4's**, and rung-0 is provisional until it lands.
- **This spike removes no code.** The GLES / EGL surface, the mega-shader and the Path Z / Path P fork are **rejected architecturally**; their physical removal from `apps/mobile/plugins/**` and the `Warden*.kt` sources is **Story 12.4's**. SEC-007 entries 5 / 5a are corrected in place, not deleted — see `architecture.md`.
- **Amendment 5c does not lapse.** MediaCodec keeps decode **Android-only by construction** (iOS = VideoToolbox) even with no GLES. The amendment is **re-scoped**, not reverted — see `architecture.md` → `#### iOS Phase 2 deferral`.
- **No device re-measurement was performed by Story 12.3.** Every number here was measured by Stories 12.1 and 12.2, and is re-verified against their delivered JSON rather than re-collected.

---

## Follow-up work required

### Re-homed to Story 12.4 (with the headroom quantified, per AC0d)

| item | measured headroom | note |
| --- | --- | --- |
| **Shorten `TIMEOUT_US` on `dequeueOutputBuffer`** | **~10.6 ms/kf** → ~11.2 s over 1061 kf | Two lines. The probe counts **1.02** `INFO_TRY_AGAIN_LATER` per keyframe against a 10 ms timeout — almost exactly one full sleep each time. |
| **Stop flushing per keyframe** | **up to ~14.5 ms/kf** → ~15.4 s over 1061 kf | Keep several IDRs in flight. An IDR resets the DPB by definition, so no flush is required for correctness. `flush()` costs 14.5 ms in-loop against 1.8–3.6 ms idle — the expense is the `END_OF_STREAM` → flush transition. |
| **Replace `countSyncSamplesByScan()`** | avoids a **62.070 s** full-file read | Bench-time assertion that **must never ship**. Take the index from the seek-built list (2.290 s), or read `stss` directly. |
| **Physically remove the GLES / EGL surface** | — | Plugin + `Warden*.kt` GLES / EGL sources. SEC-007 entry 5 then narrows to MediaCodec-only, and entry 5a's compile-time coordinate is re-evaluated. |
| **Re-measure PERF-002 end to end** | — | Over the real auto-slice pipeline, including segmentation and thumbnail export. Closes the coverage caveat above and resolves provisional rung-0. |
| **Wire the bound engine into the pipeline** | — | `processingPipeline.ts` and the four detection modules. Retires rung 3. |

**Combined projection [P]:** `42.2 − 25.1 = ~17.1 ms/kf → ~18.1 s` whole capture, **≈ 0.41% of source duration**. Neither fix attempted, neither measured.

### Downstream stories this verdict unblocks

| story | effect of the verdict |
| --- | --- |
| **9.16** — re-point detection testers at the bound engine | **Conditional on this verdict, and the rejection changes what it means.** Tool 9 and `video_test.py` re-point at **CPU rule evaluation on MediaCodec keyframe decode**, not at a GLES shader. **Without 9.16, REL-006 has no instrument at all.** |
| **9.9b** — iterative zone population for shipping configs | Released. The engine it populates zones for is settled, and the zone data is engine-independent under either arm — the rule semantics are identical (0 disagreements). |
| **9.10** — PRD / architecture editorial pass | Released. It keeps the **exhaustive** pHash→ROI/HSV prose sweep; this story amended only the ~10 sites its own ACs named. Stale reference-device identities in `architecture.md` are flagged above for it. |
| **1.13** — hybrid `map_config` delivery / `schema_version` | Released for create-story. |
| **12.4** — mobile detection consumer rewrite | **Conditional on this verdict, and the rejection changes its content**: it is now a CPU-arm wiring + decode-loop optimisation + GLES-removal story, not a shader-integration story. |

Behind those, **Epics 5 / 6 / 7** (~20 stories) were _"held behind 12.3 + 12.4"_. **12.3 has landed; only 12.4 remains between them and start.**

### Deferred-work items disposed

| item | disposition |
| --- | --- |
| Stale thumbnails in Tool 12's output directory | **Re-homed.** The output directory is an evidence artifact this story _reads_; it is not corrupted by the stale entries, and no figure here depends on them. Cleanup belongs with whoever next writes to that directory. |
| `TIMEOUT_US` | **Re-homed to Story 12.4.** Headroom quantified above. |
| Per-keyframe `flush()` | **Re-homed to Story 12.4.** Headroom quantified above. |

---

## Amendments this spike lands in `architecture.md` and `prd.md`

Recorded here so a reader can verify the cascade rather than trust it.

| # | target | action |
| --- | --- | --- |
| **5b** | Innovation #1 fallback ladder | **Ladder re-armed.** Rung 1's remedy replaced (inert → two-step decode-loop + decimation); rung 2's trigger labelled `UN-INSTRUMENTED`; rung 3's verdict stated; Pass row marked provisional; **FORBIDDEN row carried verbatim.** |
| **5c** | iOS Phase 2 deferral | **Resolved: RE-SCOPED, not lapsed.** MediaCodec keeps decode Android-only even without GLES. |
| **5d** | Foreground Service rationale | **Re-derived** from 12.2's measured threading model; the **`RATIONALE RE-DERIVATION REQUIRED` banner is removed.** |
| **5f** | REL-006 instrument | **Finished** — the two remaining `hash_validator` sites re-pointed to Tool 9 via Story 9.16. |
| **5g** | Fifth native module | **`Decision #13` written.** |
| **SEC-007** | allowlist entries 5 / 5a | **Corrected in place** — the engine survives in reduced form (MediaCodec, no GLES / EGL). |
| **PERF-002** | `prd.md` | **Re-baselined** — `RE-BASELINE PENDING` replaced with the measured figure plus the coverage caveat. |
| **PERF-010** | `prd.md` + `architecture.md` | **Disposition recorded** — stays a soft target. |

**Left FROZEN, deliberately:** Story 1.1's preserved JSI record and its rung-0 verdict, in both `architecture.md` and `architecture-spike-perf-floor.md`. **12.3 supersedes; 1.1 records.** A forward pointer is added; the record is not edited.
