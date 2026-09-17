# Story 12.4b — CPU colour port: the substitution, measured

Reference device: **Poco X5 Pro 5G (SM7325 / Android 14 / Adreno 642L)**, 2026-09-17.
Fixtures: `videos/V2/2026-04-27 22-05-34.mp4` (1920×1080 h264 `yuv420p` `color_range=tv` `bt709`,
1061 keyframes), `map_config.v2.json` (134 rules), `apps/tooling/output/labeled/v2/` (2666 PNGs).

> **STATUS: COMPLETE.** The substitution was proved first (§2, §3, §5), then the GLES/EGL surface was
> deleted (§6). AC4's ordering was followed and is recorded: every parity gate was green **before**
> the reference implementation was removed.

---

## 1. What this story had to prove before it could delete anything

`WardenCpuBaseline.evaluate()` takes `bgra: ByteArray`. `WardenKeyframeDecoder.imageToKeyframe()`
produces YUV planes. The **only** thing that ever bridged those two on the video path was
`RESOLVE_YUV_FRAG` — a GPU shader, in the file this story deletes.

And the CPU arm had **never been fed MediaCodec output at all**: Story 12.2's decisive AC12
measurement fed it BGRA decoded from labeled PNG **Bitmaps**. That gap is why
`architecture-spike-gpu-megashader.md` tags the bound configuration **`[P]`** — *"a construction over
three measured parts describing a configuration that was never run end to end."*

This report is that configuration, run end to end.

---

## 2. AC2 — the constants, re-proved exhaustively ON DEVICE ✅

| | |
|---|---|
| domain | **all 16,777,216** (Y, Cb, Cr) triples — the whole 2²⁴ space |
| device SHA-256 | `4dd2da47dc76c0b295572188703077e65b8c01c4c366b52fd73d6d6404c34e27` |
| numpy reference | `4dd2da47dc76c0b295572188703077e65b8c01c4c366b52fd73d6d6404c34e27` |
| **max error** | **0** — bit-identical, every triple, every channel |
| cost | 11.68 s, one-off |

Artifact: `report_cpucolor.json` → `ac2_color_constants`.

Three independent guards now cover these constants, and they cover **different failure modes**:

| guard | where | catches |
|---|---|---|
| `colorConvert.test.ts` | CI (jest) | Kotlin and numpy literals drifting apart |
| `ac3_numpy_reference.py verify-constants` | offline | the constants being *wrong* (2²⁴ vs exact BT.709) |
| `colorConstantsCheck()` | on device | **a wrong operator** — the one the other two cannot see |

The third matters. A `+` where the shader has a `-` contains every expected literal and passes both
offline checks. 12.2 found **two silent colour bugs** the hard way; this is the check that would have
found them in a second instead of a build/flash/run cycle.

**fp64 vs fp32, decided and measured.** `WardenColorConvert` computes in `Double`; the shader ran at
ESSL `highp float`. Measured on PC over the full domain: the two disagree on **109 of 16,777,216
triples (0.00065%), max 1 unit** — **275× rarer** than the published-rounding error the BT.709
four-decimal constants already carry, and inside the same ±1 envelope. fp64 makes the port
bit-identical to the pinned reference instead of merely close to it, and it is free because AC0b
converts ~800 texels per keyframe rather than 2,073,600.

---

## 3. AC3(B) — 🔴 THE GATE: CPU colour vs GPU colour, same decoder output ✅

Full capture, every keyframe evaluated **twice** — once through
`uploadYuvPlanes → RESOLVE_YUV_FRAG → mega-shader → glReadPixels`, once through
`WardenColorConvert → WardenCpuBaseline.evaluateYuv` — on byte-identical decoder planes.

| | |
|---|---|
| keyframes | **1061** (the full capture) |
| rules | 134 |
| rule-frame decisions | **142,174** |
| frames with any disagreement | **0** |
| **total rule disagreements** | **0** |
| decoder chroma layout | **NV12 (semi-planar, U V U V)** — observed, not assumed |
| CPU arm | **0.651 ms/keyframe** (rule regions only) |
| GPU arm | **2.855 ms/keyframe** (whole-frame convert + draw + readback + `glFinish`) |

Artifact: `report_cpucolor.json` → `ac3b_cpu_color_parity`.

**This is the first end-to-end run of the bound configuration.** The `[P]` label's gap is closed on
fire bits: the CPU arm reproduces the GPU arm exactly, on real MediaCodec output, across the whole
capture — and it does so while converting **~2,600× fewer pixels** (AC0b: rule regions only, ~800
texels of 2,073,600).

The 4.4× CPU-over-GPU margin here is consistent with 12.3's verdict (6.4× on rule evaluation alone)
and is *additional* to it: this comparison includes the colour conversion, which is the work the GPU
arm was still doing for the whole frame.

---

## 4. The per-pixel colour diff — and the anomaly it found 🔴

Fire-bit agreement is an assertion about the ~800 texels the rules happen to land on. The converter
is responsible for 2,073,600. So the first keyframe's **whole** converted frame was diffed against
the GPU's resolved frame texture, per pixel, per channel:

| | |
|---|---|
| pixels | 2,073,600 |
| differing pixels | **5** |
| mean abs channel delta | 0.0000458 |
| delta histogram | `{0: 2073595, 1: 1, 68: 2, 69: 2}` |

**One pixel at delta 1** is the fp32-vs-fp64 residual predicted in §2 — expected, and inside the
envelope the constants already carry.

**Four pixels at delta 68/69 are NOT.** That is far outside any precision envelope, and it is not a
matrix or range error either — those are unbounded and affine in the pixel's own chroma, so they
would move far more than four pixels.

### 4.1 🔴 CONFIRMED: the GPU arm reads padding as Cr in the frame's last chroma texel

The coordinate dump settles it. The four pixels are:

| pixel | chroma texel | delta | GPU B,G,R | CPU B,G,R |
|---|---|---|---|---|
| (1918, 1078) | (959, 539) | 68 | `5, 73, 0` | `5, 5, 5` |
| (1919, 1078) | (959, 539) | 69 | `3, 72, 0` | `3, 3, 3` |
| (1918, 1079) | (959, 539) | 69 | `2, 71, 0` | `2, 2, 2` |
| (1919, 1079) | (959, 539) | 68 | `0, 68, 0` | `0, 0, 0` |

Chroma is 960 × 540, so **(959, 539) is the very last chroma texel**, and the four pixels are the
bottom-right 2 × 2 luma block it serves. One texel, exactly as the 4-pixel signature predicted.

**Which arm is wrong is decidable from the values, not just from the layout argument.** Invert the
conversion on the last pixel — GPU `B=0, G=68, R=0`:

- `B = 0` ⟹ `cbn ≈ 0` ⟹ **Cb ≈ 128**. Both arms agree on Cb.
- `G = 68/255 = 0.2667 = yn − 0.1873·cbn − 0.4681·crn`, with `yn ≈ 0` and `cbn ≈ 0`
  ⟹ `crn ≈ −0.5697` ⟹ **Cr ≈ 0**.
- `R = yn + 1.5748·crn ≈ −0.897` ⟹ clamped to **0**. ✓ consistent.

So the GPU read the **correct Cb** and **Cr = 0** for this texel. The CPU arm reads **Cr = 128** —
neutral — giving the grey/black `[5,5,5] … [0,0,0]` that a black bottom-right corner should be.

`Cr = 0` is not a colour. It is the **zero byte that follows the U plane's mapped extent**.

### 4.2 This is the defect 12.2's review found and then argued away

12.2's review identified this exact byte:

> *"`MediaImage`'s semi-planar U plane ends at the last **U** byte, i.e. `(ch-1)*uStride + (cw-1)*2 + 1`
> bytes, while an RG8 upload of `cw × ch` needs one byte more. `glTexSubImage2D` does not
> bounds-check a direct buffer, so one OOB heap byte became the bottom-right Cr"*

…and dismissed it:

> *"In an NV12 layout that byte is not 'past the allocation': it is the frame's last **Cr**, and it
> belongs to the V plane, which starts at U+1 in the SAME buffer. [`isSemiPlanarNv12`] now proves
> exactly that (`u.get(1) == v.get(0)`, plus both planes spanning the frame) before this branch is
> taken — so the read lands on the right value, in mapped memory the decoder owns."*

**Measured: it does not.** `u.get(1) == v.get(0)` is a one-byte sample at the *start* of the planes;
it says nothing about what lies one byte past the U plane's *end*. On this decoder that byte is `0`,
not the final Cr. The guard converted an unchecked read into a *differently* unchecked read.

The CPU arm cannot have this bug, because it has no interleaving assumption to be wrong about: it
reads Cr from `vPlane.get((ch−1)·vRowStride + (cw−1)·vPixelStride)` — the V plane's own last byte,
through the V plane's own strides. That is correct for NV12, NV21 and I420 alike, which is exactly
why `WardenYuvFrame` has **no fast path and no layout branch** (trap 3).

### 4.3 Consequence

- **The CPU arm is the correct one.** The port is a **fix**, not merely a substitution — it repairs a
  latent frame-corner colour defect on the way out.
- **It never reached a rule**, which is why AC3(B) is 0 / 142,174: no rule rect in `map_config.v2.json`
  reaches the frame's bottom-right 2 × 2 block. The defect was real, bounded, and silent — the
  combination that survives a review.
- **It strengthens the deletion.** The argument for keeping the GPU arm as a reference is that it is
  the validated implementation; it is now the implementation with a confirmed defect the replacement
  does not have.
- It is recorded here rather than fixed: `WardenDetectionEngine.kt` is deleted by AC5 in this same
  story, and patching a file on its way to deletion buys nothing.

---

## 5. AC3(A) — the CPU evaluator against the pinned PC reference ✅

The PNG corpus, through `WardenCpuBaseline.evaluate`, compared off-device to
`bench/12-2/pc_reference_fires.json`:

| | |
|---|---|
| reference frames | 2666 |
| device frames | 2666 |
| **frame sets identical** | **true** — parity over an intersection is not parity |
| rule-frame decisions | **357,244** |
| frames with disagreement | **0** |
| **total rule disagreements** | **0** |
| CPU | 1.255 ms/frame (whole-frame BGRA, 134 rules) |

Artifact: `ac3a_cpu_parity_comparison.json`, `cpu_parity_fires.json`.

This is the GPU arm's own banked figure — 0 / 357,244 — **re-earned by the CPU evaluator rather than
inherited from it**, which AC0b required because rule-region conversion changed `evaluate`'s contract.
The same GPU figure was also re-established live on the device today before any change
(`task2_gpu_parity_comparison.json`), so the two are the same corpus on the same build of the same
device, not a comparison against a number from a fortnight ago.

Note the corpus is PNGs and carries **no YUV**, deliberately: a wrong evaluator and a wrong colour
conversion must not be able to mask each other. The colour port is proved separately (§2 and §3).

---

## 6. The removal

Done only after §2, §3 and §5 were all green — AC4's sequencing, which exists because a non-zero
result with the GPU still present is debuggable and the same result afterwards is not.

| deleted | lines | was |
|---|---|---|
| `WardenDetectionEngine.kt` | 981 | the mega-shader engine, both colour paths, FBOs, `glReadPixels`, the self-test |
| `WardenGlUtil.kt` | 219 | EGL 1.4 + GLES 3.0 plumbing, `WardenEglContext.createOffscreen` |
| `WardenSurfaceTextureHost` + the `toSurface` decode path | ~200 | Path Z, and with it **the last `flush()` outside the two bench instruments** |
| `WardenRulePacker.decodeResults` | 6 | the RGBA8 GPU-readback decoder |
| bench: `cpuVsGpu`, `pngDump`, `forcedCompletionProfile`, `threadingModel`, `availableColorPaths`, `probeOesCompiles`, `frag()` | ~350 | the GPU half of the harness |
| `detectionEnginePlugin.test.ts` | 63 | guarded `readVerbatimFrag`, the shader-copy mechanism |
| the `keyframe_engine_bench.frag` asset emission | — | **the tooling `.frag` is untouched** — Tool 12's source of truth (AC6) |

**Verified on a REUSED `android/` tree, not a clean one** (AC7) — a clean prebuild cannot catch a
sweeper regression, which is exactly the class of bug 12.2 hit. After `expo prebuild` the generated
tree had dropped `WardenDetectionEngine.kt`, `WardenGlUtil.kt` and `assets/keyframe_engine_bench.frag`,
and Story 1.2's `WardenProcessing*.kt` were untouched. The APK then built with **no errors and no
warnings**, and a `framediff` run on device produced a clean report — `ac0c_paths_measured:
["CPU_BT709_LIMITED"]`, no `error` field.

### 6.1 A number that changed AC0b from a preference into a requirement

The `framediff` diagnostic converts a whole frame, and it is the only place that still does:

**`whole_frame_convert_ms = 4228.9`** — 4.23 seconds for one 1920 × 1080 frame.

AC0b offered whole-frame conversion as a legitimate choice, on the reasoning that *"PERF-002 has
~176 s of unused budget"*. It is not: 1061 keyframes × 4.23 s = **~75 minutes**, about **25× the
entire PERF-002 budget**, not a spend against its slack. The rule-region path costs **0.651 ms/keyframe**
(§3) because it converts ~800 texels instead of 2,073,600.

The story's own framing of that option was therefore too generous, and only a measurement could say
so. Recorded here so 12.4c and 12.4d do not re-derive the whole-frame option from the story text.

---

## 7. Gates

| gate | before (post-12.3 / 12.4a) | after |
|---|---|---|
| mobile jest | 20 suites / 162 passed + 10 todo | **20 suites / 166 passed + 10 todo** |
| tooling pytest | 305 | **305** — unchanged |
| root typecheck | 3 errors, all `web` (pre-existing) | **3, unchanged** |
| `format:check` | clean | **clean** |

🔴 **The jest count MOVED, and legitimately** (AC14 anticipated this): −4 from deleting
`detectionEnginePlugin.test.ts`, +6 from the new `colorConvert.test.ts`, +2 from the two guards added
to `detectionEngine.test.ts`. **Story 12.4c's baseline is 20 suites / 166 passed + 10 todo**, not the
162 it would otherwise inherit.

---

## 8. Reproduce

```bash
# 🔴 §3's gate mode (`cpucolor`) NO LONGER EXISTS. It was an A/B against the GPU arm
# and was removed with it — see WardenEngineBench's banked comment block. To re-run
# it you would have to restore WardenDetectionEngine.kt and WardenGlUtil.kt from
# git history (they were deleted in this story's commit). That is the cost AC4
# priced in, and it is why the gate ran BEFORE the deletion.

# AC2 — the exhaustive constants sweep. Runs in EVERY mode.
adb shell am start -n team.warden.mobile/.WardenEngineBenchActivity --es mode framediff \
  --es video /sdcard/Android/data/team.warden.mobile/files/warden12_2/capture.mp4

# AC3(A) — CPU evaluator over the 2666-PNG corpus (~4 min), vs the pinned PC reference
adb shell am start -n team.warden.mobile/.WardenEngineBenchActivity --es mode parity --ei limit 0
adb pull .../bench12_2/parity_fires.json apps/mobile/bench/12-4b/
cd apps/mobile/bench/12-2 && python pc_reference.py compare ../12-4b/parity_fires.json
# ⚠️ `compare` WRITES bench/12-2/parity_comparison.json — 12.2's banked baseline.
#    Copy the result out and `git checkout --` that file afterwards.

# The offline constants proof (no device)
cd apps/mobile/bench/12-2 && python ac3_numpy_reference.py verify-constants
```

Staging is scoped storage — `/sdcard/<dir>` is EACCES at targetSdk 36. Input
`getExternalFilesDir(null)/warden12_2`, output `.../bench12_2`. Full sequence:
[`../12-2/REPORT.md` §10](../12-2/REPORT.md).

Note for Git Bash on Windows: `export MSYS_NO_PATHCONV=1` before any `adb` command carrying an
absolute device path, or the path is rewritten to `C:/Program Files/Git/sdcard/...`.
