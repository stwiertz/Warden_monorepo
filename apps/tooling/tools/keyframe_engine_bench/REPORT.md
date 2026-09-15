# Tool 12 — Keyframe Engine Bench: measured report (Story 12.1, AC11)

**Measured 2026-07-16.** Intel UHD 770 (GL 3.3.0, Build 32.0.101.5972), FFmpeg 8.0.1,
Python 3.11.15, moderngl 5.12.0 / glcontext 3.0.0.

> ### ⚠️ A PC number is NEVER a mobile number (AC14 / E6)
>
> Every figure in this report is **feasibility / relative speedup only**. It binds
> **neither PERF-002 nor PERF-010**. Only Story 12.2, running on the reference
> device — **Poco X5 Pro 5G (SM7325 / Android 14, Adreno 642L)** — can bind those;
> Story 12.3 re-baselines. The `<10 s` figure is *"the aspiration, not an AC"*.
>
> (Note for 12.2: `epics-and-stories.md:3315` says "Adreno 619". That is **wrong** —
> SM7325 = Snapdragon 778G = **Adreno 642L**; Adreno 619 is the SD695, the *old*
> device from before the reference-device re-anchoring. Correcting the epic is
> 12.2's admin. Both are GLES 3.2-capable; we target 3.0 and need nothing from 3.1+.)

This report does **not** publish the spike verdict. `architecture-spike-gpu-megashader.md`
is **12.3's** deliverable; 12.1 feeds it measured numbers, a device profile and fixtures.
The verdict slot is 12.3's.

---

## 1. Headline

| Question | Answer |
|---|---|
| Does the GPU reproduce the CPU's detections? | **Yes — bit-exact.** 0 disagreements across all 2666 labeled frames. |
| Is the pipeline decode-bound? | **Yes.** Decode is 8.86 ms/kf of a 14.41 ms/kf total (**62%**). |
| Is the GPU faster than the CPU at rule evaluation? | **No — it is ~2× SLOWER** on PC at reference resolution (0.51×). |

The pivot's **decode-bound premise is CONFIRMED**. Its implicit corollary — that a
GPU mega-shader is the way to make rule evaluation cheap — is **NOT confirmed on
PC**, and for a reason that is structural rather than incidental (§4).

---

## 2. Accuracy — exact parity with the CPU baseline (AC11, AC12, AC13)

Baseline re-run unmodified before benching, per AC12/Task 2:

```
uv run python tools/roi_detection_tester.py --config output/map_configs/map_config.v2.json --save-frame-predictions
-> output/roi_detection_tests/v2/2026-07-16T230122/
```

It **reproduced the pinned numbers exactly**, so the comparison is anchored: the
config and corpus have not moved.

| classifier | CPU baseline (pinned) | CPU re-run 2026-07-16 | **GPU (Tool 12)** |
|---|---|---|---|
| `hud_version_classifier` | 0.9805 (2614/2666) | 0.9805 (2614/2666) | **0.9805 (2614/2666)** |
| `in_match_classifier` | 1.0000 (2666/2666) | 1.0000 (2666/2666) | **1.0000 (2666/2666)** |
| `map_id_classifier` | 1.0000 (2286/2286) | 1.0000 (2286/2286) | **1.0000 (2286/2286)** |

> 🔴 **These are IN-SAMPLE numbers — a frame-for-frame PARITY TARGET, not a
> generalization claim.** The zones were tuned against this exact corpus (the
> low-saturation decision moved map-ID 0.973 → 1.000 via `h_tol=180` on 65 of 121
> zones); there is **no holdout**. Two classifiers at exactly 1.000 is a fit to
> its own training data. That is *fine here* — 12.1's question is "does the GPU
> reproduce what the CPU does on these frames", and in-sample-ness is irrelevant
> to parity. **REL-006's ≥95% floor is NOT gated by 12.1**; measuring
> generalization is 9.9b's job.

**Per-frame parity: EXACT — 0 disagreements over 2666 frames** (all three
classifiers), against Tool 9's own `frame_predictions.csv`. This is a stronger
claim than matching accuracy: two engines can post identical accuracy while
disagreeing about *which* frames they get right. They do not disagree at all.

Reproduce:

```
uv run python -m tools.keyframe_engine_bench --accuracy --cpu-compare 400 \
  --baseline-csv output/roi_detection_tests/v2/2026-07-16T230122/frame_predictions.csv
```

### How exact parity was achieved — a deviation from the Dev Notes

The story's Dev Notes prescribe **Sam Hocevar's branchless float `rgb2hsv`**. That
was **not used**, deliberately. A float conversion cannot guarantee parity: cv2's
H/S/V are *integers* produced by fixed-point arithmetic with rounding, and the CPU
reference tests `cv2.inRange` against **integer bounds inclusively** — so a hue
landing at 19.9997 instead of 20 silently flips a tight rule. 31 of the 134 rules
have bands asymmetric about their center (banker's rounding in
`int(round(h_c ± h_t))`), so they are exactly the rules a float path would fumble.

Instead, **OpenCV's integer `RGB2HSV_b` algorithm is ported verbatim into GLSL**
(`hsv_shift = 12` fixed-point, the `sdiv`/`hdiv` reciprocal tables recomputed
per-texel). Before writing a line of shader, it was brute-forced in numpy against
`cv2.cvtColor(BGR2HSV)` over **all 2^24 RGB inputs: 0 mismatches on H, S and V**.
That sweep also independently confirmed the story's `/180` decision — **max H = 179,
180 unattainable**. The exact-parity result above is the payoff.

The rejected symmetric circular-distance test stays rejected, for the reason the
story gives.

---

## 3. Timing (AC11) — full capture, `2026-04-27 22-05-34.mp4`

**1061 keyframes** over a ~2 h capture, native 1920×1080, streamed one at a time
(never accumulated — holding them would be 6.6 GB).

| stage | ms/keyframe | total | share |
|---|---|---|---|
| **decode** (FFmpeg `-skip_frame nokey`, RAM pipe) | **8.862** | 9.40 s | **62%** |
| **upload** (6.2 MB host→GPU per frame) | 1.705 ⚠️ | 1.81 s | 12% |
| **shader + readback** (1 draw, 150×1 RGBA8) | 1.177 ⚠️ | 1.25 s | 8% |
| *(scoring, phase resolution, ring, Python overhead)* | ~2.67 | ~2.83 s | 18% |
| **TOTAL (wall)** | **14.411** | **15.29 s** | 100% |

> ⚠️ **The upload / shader split above is MISATTRIBUTED — do not quote these two
> rows.** GL uploads are asynchronous, so the timer around `upload()` stops before
> the transfer completes and the blocking `draw_and_read()` absorbs the rest. Their
> **sum (2.88 ms) is correct** and every other row is correct. The true split is
> **upload ~2.44 ms / GPU work ~0.24 ms** — see §4. The rows are kept as measured,
> flagged rather than silently re-written, because they are what a naive wall-clock
> instrumentation reports and 12.2 will instrument the same way on device.

**Decode is 3.08× the entire GPU cost (upload + shader + readback).** The pipeline
is decode-bound — the pivot's central thesis, confirmed.

### GOP: the epic's assumption was wrong, in our favour

Task 1 required validating rather than inheriting the epic's **GOP-2s / 2400-keyframe**
assumption. Measured on a real V2 capture: **GOP = 4.167 s** (72 keyframes per 300 s),
yielding **1061 keyframes** for the full capture — roughly **half** what the epic
assumed. Decode is the dominant cost, so halving the keyframe count halves the
dominant cost. The `<10 s` aspiration is *closer* than the epic's arithmetic implied.

`skip_frame` codec caveats were checked, not assumed: our captures are closed-GOP
H.264, and decoded keyframe counts match ffprobe's packet-level count (30 decoded vs
29 probed over 120 s — the extra is the first frame past the cutoff). A CFR-duplication
regression would present here as ~7250 frames instead of 30.

---

## 4. 🔴 The GPU is SLOWER than the CPU at rule evaluation (0.51×)

Engine-vs-engine, decode excluded from **both** sides, 134 rules, 400 frames at
1920×1080:

| path | ms/frame |
|---|---|
| **CPU** — Tool 9's `zone_fires_on_frame` (`cv2.inRange` per rect) | **1.667** |
| **GPU** — upload + mega-shader + readback | **3.253** |
| | **0.51× — the CPU is ~2× faster** |

This is not a defect in the shader, and it is not tuning-fixable on PC. It is
arithmetic:

* The shipped rects are **1–25 px** (mode 2×2; fourteen are literally 1×1). Total
  work is **~134 rules × ~6 px ≈ 800 texel fetches per frame** — the SCP's "150
  rules × 400 texels ≈ 60k fetches" is **~100× pessimistic**.
* To read those ~800 texels, the GPU path must first upload the **entire
  1920×1080×3 = 6.2 MB frame**.

### The GPU cost, decomposed — `--profile-gpu`

⚠️ **The §3 per-stage split is misattributed, and this is the honest one.** GL
uploads are **asynchronous**: wall-clocking `upload()` returns before the transfer
lands, and the blocking `draw_and_read()` silently absorbs the remainder. The
**total is correct** (2.88 ms); the split is not. Forcing completion per stage
(median of 200, `--profile-gpu`) gives the true shape:

| stage | ms | share |
|---|---|---|
| **upload** (6.2 MB, CPU→GPU) | **2.34–2.46** | **~91%** |
| shader (rule evaluation, ~800 fetches) | 0.15–0.22 | ~8% |
| readback stall (600 B) | 0.004–0.073 | **<1% — in the noise** |

So the GPU pays a **6.2 MB transfer to do ~800 pixels of work**. The mega-shader
has almost nothing to do — precisely what Finding 3 predicted ("the decode-bound
conclusion is *strengthened*") — and that same fact leaves it no headroom to win.

**Two consequences worth stating plainly:**

1. **Non-blocking readback is not worth building.** The stall is **≲0.07 ms/frame
   (~0.5% of wall)**. The story's own Dev Note — *"PBO ping-pong is premature at 600
   bytes — build synchronous, measure first"* — is **confirmed by measurement**. The
   readback direction carries 600 bytes; there is no data-transfer problem there.
   The 6.2 MB is going the *other* way.
2. **The GPU's real cost is ~0.24 ms, not 3.25 ms.** Everything else is the bus.

**Note the Dev Notes' 0.647 ms/frame figure was measured @ 640×360**, where the
upload is ~9× smaller. AC5 mandates evaluation at `reference_resolution` (1080).
The two numbers are consistent; the resolution is the difference.

### Why this does NOT settle the Android question (for 12.2 / 12.3)

The upload is the cost, and **on Android the upload need not exist**. MediaCodec can
decode straight into a `SurfaceTexture` / `samplerExternalOES` — the frame is
*already* in GPU memory and never crosses the bus.

Both rows below are **PC measurements on an Intel UHD 770**. The second is the
same PC shader time with the PC upload arithmetically removed — it is an
*extrapolation of a PC number*, **not a measurement of any Android device**, and
it does not bind PERF-002 or PERF-010 (AC14). Only 12.2, on the Poco X5 Pro 5G,
can produce a mobile number.

| | CPU (PC) | GPU (PC) | PC-relative ratio |
|---|---|---|---|
| PC, with upload — **measured** | 1.667 ms | 3.253 ms | **0.51× — GPU slower** |
| PC, upload subtracted — **arithmetic, not measured** | 1.667 ms | **~0.24 ms** | **~7× (PC extrapolation only)** |

**This is the most decision-relevant arithmetic in this report for 12.3 — and it
is a feasibility signal, not a verdict.** What it says is narrow and conditional:
*if* an Android zero-copy `samplerExternalOES` path removes the upload as
completely as subtracting it here does, *then* the PC ratio would move from 0.51×
to roughly 7×. Whether that holds on Adreno hardware — with a different memory
architecture, a different driver, and the unresolved OES colour-conversion
question of §6 — **is exactly what 12.2 exists to measure, and nothing here
anticipates its result.**

If 12.2 finds that zero-copy does not materialize, the GPU engine has **no
demonstrated performance argument left**. Worse, note the bind in §6: if the OES
colour conversion proves unusable, the bit-parity mitigation (uploading Y/U/V as
separate R8 textures) **gives up the very zero-copy path** that is the sole source
of the advantage — landing back near the PC result.

**And the ceiling is low regardless.** Even with upload *and* stall at zero, wall
goes 14.41 → ~11.8 ms/kf, because **decode is still 8.86 ms and would then be ~75%
of what remains**. Rule evaluation is not where the time goes on *either* engine.
**Decode is — and it is the only lever that moves the `<10 s` aspiration.** On
Android, MediaCodec decode is *hardware*, which is the second thing 12.2 gets to
find out and may matter more than the engine choice.

**A third option 12.3 should weigh:** since the pipeline is decode-bound on *both*
engines and the CPU rule-eval already costs only 1.67 ms/frame, the measured evidence
does not currently require a GPU engine at all. This is a finding, not a
recommendation — the verdict is 12.3's.

---

## 5. Data defects found — reported, NOT fixed (AC13b)

Both are fenced by AC18 and guarded by `tests/test_zone_fragments_v2.py`; fixing
either belongs to 9.9b. **Both have zero runtime effect today.**

1. **`minimap_identification.roi` is dead in the CPU reference and MUST be ignored.**
   It is `{"name":"minimap","x":63,"y":922,"width":3,"height":5}` — a **3×5-px** box,
   **byte-identical to `atlantis_z10`'s rect** (a stray zone pick that leaked into the
   field). **120 of 121 map zones fall entirely outside it.** Tool 9 parses it into
   `ScoringConfig.minimap_roi` and **never reads it again**.
   The shader therefore evaluates zone rects as **absolute reference-resolution
   coordinates against the full 1920×1080 frame** and does not crop. A shader that
   "correctly" honoured `roi` would crop away 120/121 zones, score ≈0, and diverge
   catastrophically — presenting as *"the GPU port is broken"* rather than *"the
   config has a dead field"*. **That dead field is why the pinned baseline reads
   map_id 1.0.** Under AC13, Tool 9 is the gate: reproduce what Tool 9 *does*, not
   what the config *appears to say*.
2. **`minimap_identification.id` is the literal string `"test"`.** Also inert.

---

## 6. Recorded for 12.2 — not solvable on PC

* **🔴 Colour is the largest Android risk, not the graphics API.**
  `samplerExternalOES` performs an **implicit, driver-defined YUV→RGB conversion that
  AOSP does not specify**; FFmpeg's rgb24 agrees only by coincidence. Our V2 captures
  are tagged `color_range=tv` + `bt709` — exactly the risky combination. Measured
  divergence vs a correct decode: **range (limited→full) shifts S by ~19.7 units
  mean**, matrix (709→601) only ~1.6. **68 of our 134 rules sit at `s_center ≤ 8`
  having surrendered hue (`h_tol=180`)** — immune to the matrix error, *maximally*
  exposed to the range error. **The 1.0000 / 0.9805 figures are NOT portable
  constants** — they were fitted against FFmpeg's conversion.
  *Mitigation to weigh:* decode to `COLOR_FormatYUV420Flexible`, upload Y/U/V as
  separate R8 textures, do YUV→RGB in *our* shader with FFmpeg's exact constants.
  **But note that trade is no longer obviously affordable**: it buys bit-parity by
  *giving up the zero-copy OES path* — which §4 shows is the only thing that could
  make the GPU competitive at all. **Gate 12.2 on a cheap PC-vs-device frame diff
  before any rule-porting work** (~16 offset / ~9% gain ⇒ range error; saturated-hue
  shift with greys stable ⇒ matrix error).
* **`mediump` NaN trap (cannot reproduce on PC).** A float `rgb2hsv`'s `1e-10`
  epsilon is ~6 orders below `mediump`'s smallest normal (2⁻¹⁴) → flushes to 0 →
  `0/0 = NaN` on greys → NaN fails every `step()` silently, and our 68 low-sat rules
  are exactly the greys. **Our integer HSV port sidesteps this entirely** (no epsilon,
  no division by `diff` in float where `diff == 0` — the reciprocal is gated on
  `diff > 0`). The trap is recorded in case 12.2 reintroduces a float path.
  `precision highp` is mandatory regardless; desktop ignores it, so **the PC POC
  cannot reproduce `mediump` bugs at all**.
* **ES 3.0 conformance is gated, not assumed** — see §7.

---

## 7. ES-3.0 subset gate (AC6 / E2)

One shader body; only the `#version` line is swapped. Both dialects are compiled on
every gate run:

```
uv run python -m tools.keyframe_engine_bench --gate-glsl
```

```
[OK ] frag  #version 300 es      [OK ] frag  #version 330 core
[OK ] vert  #version 300 es      [OK ] vert  #version 330 core
```

**Deviation from AC6's literal command.** AC6 prescribes `glslangValidator -G -S frag`.
`-G` requests SPIR-V-for-OpenGL codegen and **rejects `#version 300 es` outright**
("ES shaders for SPIR-V require version 310 or higher") — so the prescribed flag
*structurally cannot* validate the ES 3.00 dialect E2 mandates. The gate drops `-G`
and runs glslang's GLSL/ESSL front-end, which is the part that enforces the subset.
Verified live that the gate is real: it **rejects `float x = 1;` under `#version 300 es`
and accepts it under `#version 330 core`** — i.e. it catches the #1 silent killer,
which the `-G` form could not even reach.

`glslangValidator` is not pip-installable and was not on this box; the Khronos
prebuilt (`glslang-master-windows-Release.zip`, Glslang 16.4.0 / ESSL 3.20) is used
out-of-tree via `$GLSLANG_VALIDATOR`. It is **not vendored into the repo** (AC18).

Subset rules observed, each of which silently passes on desktop and fails on Adreno:
RGBA8 render target (**not** RGBA32F — not color-renderable in ES 3.0 core) decoded
with `> 127` (never `== 255`); **no implicit int→float anywhere**;
`precision highp float/int/sampler2D` (the ES fragment language has *no* default float
precision, and `sampler2D` defaults to **lowp** — which would shred both the RGBA32F
rule bounds and the 8-bit frame); `out vec4` not `gl_FragColor`; `texelFetch` not
`texture2D`; no `layout(location=)` on uniforms; `GL_PACK_ALIGNMENT` pinned to 1
(150×4 = 600 B is only *accidentally* 4-aligned). Integer `%` and `/` are **undefined
for negative operands in ES 3.00**, so hue wrap uses float `mod()` (floored, like
Python's `%`) — `h_lo` is negative on exactly the 9 wrap-branch rules, so an integer
`%` would be UB that happens to work on desktop.

ModernGL **cannot create a real GLES context** ([moderngl#507], closed unimplemented),
and desktop drivers run a permissive front-end. **`#version 300 es` compiling locally
proves nothing about Adreno.** The validator is the gate; the driver is not.

---

## 8. Engineering notes worth carrying forward

* **A GL format mismatch cost a full accuracy run and failed silently.** moderngl's
  `dtype='u1'` spells `GL_RGBA8**UI**` — an *integer* texture — not normalized
  `GL_RGBA8` (which is `dtype='f1'`). A `sampler2D` cannot legally read an integer
  texture and a `vec4` cannot legally be written to an integer attachment. Neither
  raised: the readback returned **uninitialized memory** that looked like plausible
  detections (accuracy 0.35 / 0.31 / 0.05), reading as *"the GPU port is broken"*.
  `MegaShader` now runs a **construction-time self-test** (clear to a known value,
  read it back, assert `GL_NO_ERROR`) so this class of failure is loud.
  **For 12.2: GL failures are silent by nature. Assert the plumbing before trusting
  a single number.**
* **The state-machine "latent bug" is not a bug.** The Dev Notes flag
  `video_test.py:606-614` — `falling_ts = ts` assigned immediately before
  `(ts - falling_ts) >= dur` is evaluated, "so the falling-edge expression is always
  `0 >= dur`". The observation is accurate; the conclusion does not follow. On the
  falling-edge frame, elapsed time since the falling edge **is zero by definition**,
  so `0 >= dur` is the *correct* evaluation of "is the score window already over?" —
  yielding zero score frames when `dur == 0` and making the falling-edge frame the
  first `score_screen` frame when `dur > 0`, exactly as the comment describes.
  Elapsed time starts mattering on the *following* frames, which take the
  `score_screen` branch where the same expression is live. **Ported as intent, with
  the zero made explicit.** Tool 11 is untouched (AC18). **No divergence from 9.13's
  behaviour exists to report.**
* **`min_ratio` is dominated by quantization, not ratio.** On a 2×2 rect, `>= 0.3`
  means ≥2 of 4 pixels — so 0.3 and 0.49 are the *same rule*. On a 1×1 rect it means
  *any* in-band pixel. Unit-tested at both sizes.
* **Scoring is degenerate today and is reproduced AS-IS, not "fixed"** (that is
  9.16's call). All 134 rules carry `weight = 1.0` / `weight_override = null`, so the
  map-ID "weighted aggregate" reduces to a plain fired-count; against
  `identification_threshold = 0.6` on an **unnormalized** sum, any map with ≥1 fired
  zone clears it — map-ID is effectively `argmax(fired_count)` and the threshold is
  near-inert. Live confirmation: observed **per-frame** `map_id_confidence` values
  of **17.0** against a 0.6 threshold.

  ⚠️ **Scope this to the per-frame number only.** Span-level confidences in the
  *hundreds* also appear in `results.json`, but those are **not** evidence about
  the shipped config — they are an artifact of *this tool's own* span
  aggregation, which sums per-frame map scores across every keyframe in a span.
  A 100-keyframe span multiplies a per-frame count of ~2 into ~200 by
  construction. Attributing them to Finding 3 would present a 12.1 implementation
  choice as a property of the zone data. (Whether that summation should instead
  inherit 9.13's mode-of-argmax + mean confidence is an open question raised by
  the 2026-07-19 code review; see the story's Review Findings, decision #1.)

---

## 9. AC13 — Tool 9 uses THREE formulas, not one

`SCP:285` says *"Tool 9 sums raw weighted"*. **That is true of the map-ID classifier
only.** Implementing that one form everywhere would silently break two of the three
accuracy numbers. Reproduced per-classifier, exactly:

| classifier | formula | source |
|---|---|---|
| HUD-version | `fires / n_hud` — **normalized**, unweighted | `roi_detection_tester.py:675` |
| in_match | `fires / n_im` — **normalized**, unweighted, then **hard-binary** | `:723` |
| map-ID | `Σ effective_weight × fired` — **raw, unnormalized** | `:742-748` |

Divergence documented, **not silently reconciled**: Tool 10's live preview normalizes
weight-aware (`Σeff_fired/Σeff_total`); Tool 11 uses a **fourth** formula
(`Σ(ratio×w if fired)/Σw`). **Tool 9 is the gate**, so Tool 9's forms are what the
bench reproduces. `weight` / `weight_override` never enter the shader.

---

## 10. Doubt — introduced here, not inherited (AC8, AC10)

🔴 **There was no upstream `unknown` to inherit on the path that matters.**
`_argmax_with_threshold`'s `unknown` serves the **HUD-version and map-ID** classifiers
only. The **in_match** classifier — the one that drives the phase state machine and
therefore the timeline — is **hard-binary and never returns unknown**
(`:725-729`, verbatim: *"Binary: clears threshold → in_match, else not_in_match
(NOT unknown)"*). So phase-axis doubt is **introduced by 12.1**. AC10's "9.13's enum
has no `doubt` member" is a *symptom* of that, not the cause.

The only specification that exists is one clause (`SCP:46`): doubt is *"resolved by
the reliability of surrounding transition screens"*, constrained to stream processing.
**Design chosen, stated here as AC8 requires:**

1. **Detect.** in_match score is `fires / n_im`; with 3 shipped zones it quantizes to
   {0, ⅓, ⅔, 1}. A **unanimous** vote is confident; a **split** vote is doubt
   (`|ratio − threshold| < doubt_margin`, default 0.2). `--doubt-margin 0` disables
   doubt and reproduces 9.13 exactly.
2. **Never force.** A doubtful frame is emitted as `doubt` — never rounded to the
   nearest class (E4).
3. **Resolve by surrounding reliability.** A doubtful frame does **not advance** the
   machine; the internal state **holds**. The reliable context around it — the
   confident frames that opened the span, and the score-screen timer armed by a
   *confident* falling edge — determines the meaning of the doubtful stretch, and a
   span is not shredded by one unreliable frame. The score clock keeps running
   underneath, so doubt cannot freeze the timeline. One forward pass; holding uses
   only what is already known. **No sliding window, no lookahead, no two-pass.**

Each frame therefore carries an **emitted** state (which may be `doubt`) and an
**internal** state (which never is). Spans are cut from the internal state.

**AC10 verdict — the enum is EXTENDED**, not remapped: `{in_match, score_screen,
not_in_match, doubt}`, plus a sibling `confidence` field per frame. Mapping
`doubt → not_in_match` is precisely the "forced to the nearest class" E4 forbids, and
would make an unreliable frame indistinguishable from a confidently-negative one.

Measured on the full capture: **doubt fired on 2 of 1061 keyframes** (in_match 772,
not_in_match 215, score_screen 72). Rare, and first-class.

---

## 11. Deliverables produced

Full capture `2026-04-27 22-05-34.mp4` → `apps/tooling/output/2026-04-27 22-05-34/`:

* `results.json` — 9.13's shape verbatim (top-level `hud_version`, ordered
  `{frame_idx, timestamp_ms, state}` + `confidence`, and `matches:
  [{start_frame, end_frame, map_id, confidence}]`). Deterministic per REL-005:
  `sort_keys=False`, `ensure_ascii=False`, `round(x, 6)`, trailing newline.
  **18 match spans** detected across the ~2 h capture.
* `bench.json` — timings + GL profile + thumbnail manifest.
* **55 retroactive thumbnails**, each the **N-2** keyframe at a phase change (AC9),
  written via `cv2.imencode` + `open().write()` (never `cv2.imwrite`).
  Spot-checked: the `in_match → score_screen` thumbnail at kf 000102 is a genuine
  in-match ARTEFACT frame with the HUD live — i.e. gameplay from *before* the score
  screen, which is the point. The span was independently identified as `artefact`.

`--accuracy` → `apps/tooling/output/keyframe_engine_bench/accuracy.json`.

**No decoded frames are written to disk** (AC2). Frames stream one at a time.

---

## 12. What 12.1 did NOT do

Re-open Story 1.1 (FROZEN; 12.3 supersedes, 1.1 records) · publish the spike report
(12.3) · re-arm the fallback ladder (12.3) · re-point Tool 9 (9.16) · touch zone data,
`contracts/map-config.schema.json`, Tool 9/10/11, or the emitter (AC18) · bump
`schema_version` (E1 — rects retained; a rect with `w=1,h=1` **is** a point).
