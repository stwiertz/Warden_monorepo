# Story 12.1: PC POC — Python + ModernGL + FFmpeg Keyframe Bench

Status: done

Sprint fit: `needs-spike-or-split` — deliberate, citable exception to Decision #ES-9 ("Story 1.1 is the only one by design"), recorded as the second ([epics-and-stories.md:3306](../epics-and-stories.md#L3306)). **The spike IS the unknowable — "took multiple focused days" is not a failure mode** (precedent: [1-1-pre-prd-performance-spike-ar-spike.md:19](1-1-pre-prd-performance-spike-ar-spike.md#L19)).

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As **Stephane (solo dev / product owner)**,
I want **a PC proof-of-concept that decodes only a video's keyframes and evaluates every `map_config` HSV rule in one GPU mega-shader, reporting measured ms/keyframe and accuracy against the CPU baseline**,
so that **the decision to bet V1 on a GPU detection engine — or to abandon it — rests on evidence rather than intuition, before any further zone-population or mobile-UI investment is made**.

---

## ⚠️ Read This First — Three Findings That Invalidate Parts of the Epic Brief

The epic was written from a conversational brief that is **not in the repo**. Analysis of the live tree contradicts it in three places. **Trust this story file over `epics-and-stories.md:3304-3310` where they disagree.**

### Finding 1 — The FFmpeg keyframe extractor you are told to build ALREADY EXISTS

[apps/tooling/utils/video.py:208](../../apps/tooling/utils/video.py#L208) `extract_iframes_scaled()` already implements **exactly** Volet A's decode spec: `-skip_frame nokey`, RAM pipe, no disk write, BGR24, PTS via a `showinfo` stderr reader thread, `check_ffmpeg()` PATH guard, `proc.terminate()` in `finally`.

```python
cmd = [
    "ffmpeg",
    "-skip_frame", "nokey",          # decoder-level: skips reconstruction, not just filtering
    "-v", "info", "-nostats",
    "-i", str(video_path),
    "-vf", f"showinfo,scale={scaled_w}:{scaled_h}",
    "-vsync", "0",                   # == -fps_mode passthrough (deprecated spelling — see AC0a)
    "-f", "rawvideo", "-pix_fmt", "bgr24",
    "pipe:1",
]
```

The module is **live, not orphaned** — Tool 6 imports `check_ffmpeg` / `extract_frame_at_timestamp` / `extract_frame_at_timestamp_scaled` at [video_timeline_labeler.py:27-30](../../apps/tooling/tools/video_timeline_labeler.py#L27-L30). `extract_iframes_scaled()` itself has no current caller but is documented as the architecture's decode path ([apps/tooling/docs/architecture.md:56](../../apps/tooling/docs/architecture.md#L56), [:69](../../apps/tooling/docs/architecture.md#L69)).

**Consequence:** the epic's "Reuses:" list ([:3308](../epics-and-stories.md#L3308)) omits the single largest reuse in the task. **Do not write a new FFmpeg pipe.** Also: `extract_frame_at_timestamp_scaled()` ([video.py:341](../../apps/tooling/utils/video.py#L341)) is the retroactive-thumbnail mechanism, and `get_gop_interval()` ([:164](../../apps/tooling/utils/video.py#L164)) validates the epic's GOP-2s / 2400-keyframe assumption in one call.

**E5 is therefore half-wrong.** FFmpeg is already a documented **system-PATH** dependency of this package ([apps/tooling/docs/architecture.md:30](../../apps/tooling/docs/architecture.md#L30): *"Video decoding | FFmpeg subprocess (not OpenCV VideoCapture) | OpenCV cannot selectively decode I-frames only"*; [development-guide.md:10](../../apps/tooling/docs/development-guide.md#L10): *"FFmpeg | Any recent | Must be available on system PATH"*). FFmpeg-as-decoder **restores** this package's own documented architecture; it breaks only Story 9.13's *local* AC. Of E5's "two manifests to update", **only `moderngl` actually lands in them.**

### Finding 2 — 🔴 The untracked `.bak` is NOT newer/better data. Do NOT restore it.

`apps/tooling/output/zones/v2/minimap_identification.json.bak` is untracked (`??`), mtime **Jun 11** — *newer* than `map_config.v2.json` (May 30). The naive read is "the `.bak` is the latest tuning, preserve it." **That read is backwards and would regress accuracy.**

Measured over the **121 map zones** (both files: identical ids, identical rects — only `h_tol`/`s_tol` differ, on 69 zones):

| | zones at `h_tol=180` | `s_center` of those zones |
|---|---|---|
| `map_config.v2.json` (May 30) | **65** | 0–8 (mean **3.6**) — *all 65 have `s_center ≤ 20`* |
| `minimap_identification.json.bak` (Jun 11) | **0** | — |
| `map_config.v2.json`, map zones at `h_tol≠180` | 56 | 57–85 (mean **73.0**) |

Among map zones the split is cleanly bimodal: **every** map zone at `h_tol=180` is white/grey (`s_center ≤ 8`); every hue-constrained map zone is saturated (`s_center ≥ 57`). All 3 `in_match` zones are `h_tol=180`, `s_center` 6–7.

*(Scope precisely: that bimodality is a **map-zone** property, not a property of all 134 rules. Counterexample: `hud_z09` is `h_tol=139, s_center=5` — low-sat **and** hue-constrained. Don't over-generalize it into "all greys are hue-unconstrained".)*

That pattern is precisely the **accepted, recorded tuning decision**: low-saturation (white/grey) zones set `h_tol=180` (hue unconstrained), which moved map-ID **0.973 → 1.000**. The `.bak` carries the **pre-decision** state — hue still constrained on low-sat zones — despite its later mtime.

**Hard corroboration:** the Tool 9 report generated the same day as the config, [`output/roi_detection_tests/v2/2026-05-30T135106/report.json`](../../apps/tooling/output/roi_detection_tests/v2/2026-05-30T135106/report.json), scores **map_id accuracy = 1.0** — the exact post-tuning number the decision records. The tuned state is on disk and measured; the `.bak` is not.

**Binding:** `map_config.v2.json` is the tuned artifact. The `.bak` is a historical backup of a superseded fragment lineage. **Do not restore it, do not merge it, do not treat mtime as recency of content.** Preserve it untouched for the audit trail (AC0b).

### Finding 3 — The scoring math is currently degenerate, and the bench must reproduce that

Measured across all 134 shipped rules:

- `min_ratio` = **0.3 on every single rule** (134/134)
- `weight` = **1.0 on every single rule**; `weight_override` = **null on every single rule**
- Rect areas: **1–25 px**, mode **2×2**. Fourteen rules are literally `w=1,h=1`.

Two consequences the brief's arithmetic misses:

1. **Tool 9's "weighted aggregate" reduces to a plain count of fired zones** (`Σ effective_weight × fired` with all weights 1.0). Against `identification_threshold = 0.6` on an **unnormalized sum**, *any map with ≥1 fired zone clears the threshold* — so map-ID is effectively `argmax(fired_count)` and the threshold is near-inert. Reproduce this exactly; do not "fix" it here (that is 9.16's call).
2. **`min_ratio` is dominated by quantization, not by ratio.** On a 2×2 rect (4 px), `ratio >= 0.3` means **≥2 of 4 pixels**. On a 1×1 rect, it means **any single in-band pixel**. The SCP's "150 rules × 400 texels ≈ 60k fetches" ([SCP:62](../sprint-change-proposal-2026-07-16.md#L62)) is **~100× pessimistic** — real total is ~134 rules × ~6 px ≈ **800 fetches**. The decode-bound conclusion is *strengthened*, not weakened.

---

## Acceptance Criteria

### AC0 — Kickoff decisions (resolve BEFORE Task 1; record verdict in Dev Agent Record)

- [x] **AC0a — Decoder binding.** Recommended default: **Option A**.
  - **Option A (RECOMMENDED) — reuse `utils/video.py` subprocess.** Zero new pip deps beyond `moderngl`; matches the epic's literal `-skip_frame nokey`; already proven and already a live module. Requires two small in-story fixes: (i) `-vsync 0` → **`-fps_mode passthrough`** (`-vsync` is deprecated since FFmpeg 5.1 and **already removed in 9.x master**; both spellings mean passthrough, so this is a rename, not a behavior change); (ii) add a **no-scale / native-resolution** variant — the bench must read at `reference_resolution` height 1080 (see AC5).
  - **Option B — PyAV 18.0.0** (`av`, released 2026-07-02, bundles FFmpeg 8.1.2, `requires-python >=3.11`, declares **no** dependencies, `stream.codec_context.skip_frame = 'NONKEY'`). Cleaner: PTS and pixels arrive as one object, eliminating the stderr-thread PTS pairing. Costs a second new pip dep and supersedes an existing live module.
  - **⚠️ Whichever option: `-fps_mode passthrough` (or PyAV) is MANDATORY, not cosmetic.** Verified on a real V2 capture: the rawvideo muxer sets `AVFMT_NOTIMESTAMPS` but **not** `AVFMT_VARIABLE_FPS`, so `auto` resolves to CFR and **silently duplicates each keyframe ~250×** — a 30 s segment yielded **1999 frames instead of 8**. `utils/video.py`'s existing `-vsync 0` already avoids this; do not drop it while renaming.
- [x] **AC0b — Bench input + `.bak` disposition.** Recommended default: **Option A**.
  - **Option A (RECOMMENDED)** — bench against the existing `apps/tooling/output/map_configs/map_config.v2.json` (13 maps / 121 map zones / 10 hud / 3 in_match = **134 rules**, fully populated, carrying the accepted `h_tol=180` low-sat tuning per Finding 2). Leave `minimap_identification.json.bak` **byte-untouched**. Story 12.1 is **read-only** with respect to zone data.
  - **Option B** — block on Story 9.15 authoring + landing first.
  - **Note for Stephane (does not block 12.1):** the zone-fragment source-of-truth contract is **broken on disk** — see "Dependency Reality Check" below. That is 9.15's problem, not 12.1's.
- [x] **AC0c — LUT packing.** Recommended default: **Option A** (pre-resolved OpenCV integer bounds). Full spec in Dev Notes → "The 150×3 LUT". The brief's "position + HSV + V" does not fit 3 texels and does not reproduce `band_inrange_ratio`'s three branches; Option A does both exactly.
- [x] **AC0d — Tool name + number.** Recommended default: **Tool 12 — `apps/tooling/tools/keyframe_engine_bench/`** (package form, per the epic's `tools/<name>/`). The epic literally says `<name>`; the sprint slug is `12-1-pc-poc-gpu-megashader-bench`.

### Engine + decode

- [x] **AC1 — Package layout.** Tool lives at `apps/tooling/tools/<name>/` as a **package** with `__init__.py` + `__main__.py` (thin CLI) + GL-free pure-logic modules + a GL-isolating module. Follows the `zone_picker/` precedent. Invoked `python -m tools.<name>`. `run()` (core logic, returns results) + `main()` (argparse entry) per [architecture.md:1002](../architecture.md#L1002). **argparse, not Typer/click** ([:281](../architecture.md#L281)).
- [x] **AC2 — Keyframe-only decode, RAM pipe, no disk write of decoded frames.** Reuses `utils/video.py` (AC0a). Frames stream **one at a time** — never accumulate (1061 keyframes × 6.2 MB = **6.6 GB** if you hold them). Each keyframe carries its PTS. **"No disk write" scopes to decoded frames**, not to deliverables: the phase timeline and thumbnails are the story's outputs and land in `output/<video_stem>/` per [architecture.md:1046](../architecture.md#L1046).
- [x] **AC3 — GL context isolated behind a `run()`-shaped seam.** [architecture.md:1148](../architecture.md#L1148) prescribes *"stateless pure functions (np in → np out)"*; a GL context is stateful. LUT packing, result decoding, phase resolution, and the circular buffer MUST be pure functions testable **without a GL context** (this is E7's named friction and the AC11 test gate depends on it).
- [x] **AC4 — Mega-shader.** One draw per keyframe. Rules texture **150×3 RGBA32F** (`texelFetch`, `ivec` coords, explicit lod); render target **150×1 RGBA8** (see AC6); one 0/1 per rule. **CPU-side scoring and phase resolution — NO combination logic in GLSL** ([SCP:46](../sprint-change-proposal-2026-07-16.md#L46)). `weight` / `weight_override` never enter the shader. Rule count is **134 today with 16 slots of headroom**; `bastion` is in `MAP_LABELS` but has no corpus and no config entry — a 14th map pushes to ~140+. **Do not hardcode 150** — size from the config and assert `n_rules <= 150` with a clear error.
- [x] **AC5 — Reference-resolution parity.** Frames are read at `reference_resolution.height` (**1080**) before rule evaluation, matching every other tool ([SCP:60](../sprint-change-proposal-2026-07-16.md#L60): *"A fixed denominator IS normalization"*). **⚠️ Do not scale twice.** `utils/video.py` scales inside FFmpeg (`scale=w:h`, swscale bicubic, **even-width rounding** `round(src_w*th/sh/2)*2`); Tool 9's `_resize_to_ref` ([roi_detection_tester.py:498](../../apps/tooling/tools/roi_detection_tester.py#L498)) uses `max(1, round(w*ref_h/h))` with `INTER_AREA`. At 1920×1080 → 1080 **both are no-ops and agree**; at any other height they produce **different widths and different pixels**, confounding the accuracy comparison. Decode at native 1080 and do not resize, or resize on exactly one path and document it.
- [x] **AC6 — GLSL in the ES-3.0-compatible subset from line one (E2).** This is what makes 12.2 a port, not a rewrite. Binding rules, each of which silently passes on desktop and fails on Adreno:
  - **Render target MUST be RGBA8, NOT RGBA32F.** RGBA32F is texture-only and **not color-renderable in ES 3.0 core** (needs `EXT_color_buffer_float`); `glReadPixels` guarantees only `GL_RGBA`/`GL_UNSIGNED_BYTE`. Write 1.0/0.0, threshold **`>127`** on CPU (never `==255`). A 150×3 RGBA32F input *texture* is fine — texturing ≠ rendering.
  - **No implicit int→float.** `float x = 1;` compiles on desktop `330 core`, **errors** on ES 3.00. Write `1.0`; construct explicitly. This is the #1 silent killer.
  - `precision highp float; precision highp int;` mandatory (ES fragment shaders have no default float precision; desktop ignores these, so **the PC POC cannot reproduce `mediump` bugs**).
  - `out vec4`, never `gl_FragColor`. `texture()`, never `texture2D()`. `layout(location=) uniform` is banned in both.
  - Set `glPixelStorei(GL_PACK_ALIGNMENT, 1)` — 150×4 = 600 B is *accidentally* 4-aligned; that luck dies if the rule count or format changes.
  - **Enforcement:** author one shader body, swap only the `#version` line, and gate on **`glslangValidator -G -S frag`**. Desktop drivers run a permissive front-end — `#version 300 es` compiling locally proves *nothing* about Adreno, and ModernGL **cannot create a real GLES context** ([moderngl#507](https://github.com/moderngl/moderngl/issues/507), closed unimplemented).
- [x] **AC7 — Hue wraparound (E3).** `H_min > H_max` MUST be read as an interval crossing 0.0/1.0. Must reproduce **all three** branches of `band_inrange_ratio` ([zones.py:131](../../apps/tooling/tools/common/zones.py#L131)). Measured branch distribution across the 134 shipped rules — **all three are live in production, none is hypothetical**:

  | branch | condition | count |
  |---|---|---|
  | full-circle | `h_hi - h_lo >= 180` | **68** |
  | wrap | `h_lo < 0 \|\| h_hi > 179` | **9** |
  | normal | otherwise | **57** |

  The exact `/180` (not `/179`) mapping is in Dev Notes → "HSV on the GPU".
- [x] **AC8 — CPU-side phase resolution with "doubt" as a first-class outcome (E4).** Stream processing — **no sliding window, no two-pass** ([SCP:46](../sprint-change-proposal-2026-07-16.md#L46)). Doubt is never forced to the nearest class.
  - 🔴 **There is no upstream `unknown` to inherit on the path that matters.** `_argmax_with_threshold`'s `unknown` ([roi_detection_tester.py:605](../../apps/tooling/tools/roi_detection_tester.py#L605)) is used by the **HUD-version and map-ID** classifiers only. The **in_match** classifier — the one that drives the phase state machine and therefore AC10's timeline — is **hard-binary and never returns unknown** ([roi_detection_tester.py:725-729](../../apps/tooling/tools/roi_detection_tester.py#L725-L729), comment verbatim: *"Binary: clears threshold → in_match, else not_in_match (**NOT unknown**)"*). So doubt on the phase axis must be **introduced by this story**, not inherited. Say so in the report; do not let AC10's enum question mask this as an export-format detail — the cause is upstream of the enum.
  - **Doubt-resolution mechanism** ([SCP:46](../sprint-change-proposal-2026-07-16.md#L46), verbatim): doubt is *"resolved by the reliability of surrounding transition screens"*. That is the whole specification that exists — one clause, constrained only by "stream processing, no sliding window, no two-pass". Design it, state the design in the report, and keep it CPU-side.
  - State machine otherwise inherited unchanged from 9.13 ([epics-and-stories.md:2820](../epics-and-stories.md#L2820)): `in_match` rising → span; falling → `score_screen` for `score_screen_duration_ms` (**15000**); then `not_in_match`.
- [x] **AC8b — Two frame sources behind one seam.** The two deliverables consume **different corpora** and the tool needs both:
  - **Accuracy (AC11/AC12/Task 8)** runs on the **2666 labeled PNGs** at `output/labeled/v2/` — that is the only corpus with ground truth and the only one Tool 9's baseline covers. Read via `np.fromfile` + `cv2.imdecode` (never `cv2.imread`); mirror `iter_labeled_frames`' ordering ([roi_detection_tester.py:517](../../apps/tooling/tools/roi_detection_tester.py#L517)) without importing Tool 9's iterator wholesale if it drags dependencies.
  - **ms/keyframe (AC11/Task 7)** runs on **video keyframes** from `videos/V2/` via the FFmpeg pipe.
  - Both feed the same `(frame_bgr_at_ref) -> [bool; n_rules]` shader path. **Put a frame-source seam in front of it** (`frames.py`) so neither deliverable forks the engine. Rule ordering (texel index `i` → `(owning_class, zone_id)`) MUST be preserved and returned alongside the LUT — CPU aggregation depends on it.
- [x] **AC9 — 3-keyframe circular buffer + retroactive thumbnails.** On a phase change at keyframe N, emit **frame N-2**. Buffer holds N, N-1, N-2. Thumbnails are a permitted disk write (AC2), to `output/<video_stem>/`.
- [x] **AC10 — Phase timeline export.** Inherit 9.13's `results.json` shape verbatim ([epics-and-stories.md:2820-2821](../epics-and-stories.md#L2820-L2821)) — top-level `hud_version` + ordered `{frame_idx, timestamp_ms, state}` + `matches: [{start_frame, end_frame, map_id, confidence}]`. Determinism per REL-005: `sort_keys=False`, `ensure_ascii=False`, `round(x, 6)`, trailing newline ([video_test.py:721](../../apps/tooling/tools/video_test.py#L721)). **⚠️ 9.13's `state` enum is `{in_match, score_screen, not_in_match}` — it has no `doubt` member, but AC8 mandates doubt is first-class.** Resolve explicitly and record the verdict: extend the enum, or map doubt → `not_in_match` + a sibling confidence field. Do not leave it implicit.

### Measurement — the actual deliverable

- [x] **AC11 — Report `ms/keyframe` AND accuracy vs the CPU baseline.** Both numbers, or the story has not delivered. Breakdown: decode / upload / shader+readback, separately — the pivot's whole thesis is that this is **decode-bound**.
- [x] **AC12 — Re-establish + confirm the CPU baseline before benching.** A baseline **already exists** — **39** Tool 9 reports are on disk under `output/roi_detection_tests/v2/`. The latest, [`2026-05-30T135106/report.json`](../../apps/tooling/output/roi_detection_tests/v2/2026-05-30T135106/report.json), run against `map_config.v2.json` over the 2666-PNG corpus:

  | classifier | accuracy **(in-sample)** | n_evaluated | n_correct |
  |---|---|---|---|
  | `hud_version_classifier` | **0.9805** | 2666 | 2614 |
  | `in_match_classifier` | **1.0** | 2666 | 2666 |
  | `map_id_classifier` | **1.0** | 2286 | 2286 |

  🔴 **These are IN-SAMPLE numbers — a frame-for-frame PARITY TARGET, not a generalization claim.** *(Label added 2026-07-16 by the Story 9.15 code review, decision D3.)* The zones were tuned against this exact corpus (the low-saturation decision moved map-ID **0.973 → 1.000** via `h_tol=180` on 65 of 121 zones); there is **no holdout**. Two classifiers at exactly **1.000** is a fit to its own training data, not proof detection generalizes.

  **For this story that is fine, and you must not "improve" it.** 12.1's question is *"does the GPU reproduce what the CPU does on these frames"* — in-sample-ness is irrelevant to parity, and these are exactly the right numbers to match. **But phrase them as parity in the AC11 report**, never as accuracy-in-the-world: **AC14 already forbids** claiming to bind PERF-002/PERF-010, and this is the accuracy-side analogue. **REL-006's ≥95% floor is NOT gated by 12.1** — measuring generalization is 9.9b's job (its AC2 certitude + zero-train/test-overlap gate). **Story 9.15 pins these same three numbers**, with the same label, as the only durable record ([9-15 AC6](9-15-pilot-zone-set-for-engine-poc.md)) — and its `tests/test_zone_fragments_v2.py` guard now fails if the config drifts out from under them.

  Do **not** treat these as given: the directory is gitignored and its provenance is a same-day artifact. **Re-run Tool 9 unmodified and confirm the numbers reproduce**, then pin that run as *the* baseline:
  `uv run python tools/roi_detection_tester.py --config output/map_configs/map_config.v2.json --save-frame-predictions`
  If the re-run diverges from the table above, **stop and report** — that means the config or corpus moved under us, and the whole accuracy comparison is unanchored. Tool 9 itself is untouched by this story ([roi_detection_tester.py](../../apps/tooling/tools/roi_detection_tester.py) is 9.16's to re-point, not 12.1's).
- [x] **AC13 — Match Tool 9's scoring semantics **per classifier**.** 🔴 [SCP:285](../sprint-change-proposal-2026-07-16.md#L285) says *"Tool 9 sums raw weighted"* — **that is true of the map-ID classifier only.** Verified in code, Tool 9 uses **three different formulas**, and implementing one of them everywhere silently breaks two of the three accuracy numbers:

  | classifier | formula | source |
  |---|---|---|
  | HUD-version | `fires / n_hud` — **normalized**, unweighted | [roi_detection_tester.py:675](../../apps/tooling/tools/roi_detection_tester.py#L675) |
  | in_match | `fires / n_im` — **normalized**, unweighted, then hard-binary | [roi_detection_tester.py:723](../../apps/tooling/tools/roi_detection_tester.py#L723) |
  | map-ID | `Σ effective_weight × fired` — **raw, unnormalized** | [roi_detection_tester.py:742-748](../../apps/tooling/tools/roi_detection_tester.py#L742-L748) |

  Tool 10's live preview normalizes weight-aware (`Σeff_fired/Σeff_total`, [zone_picker/app.py:316-324](../../apps/tooling/tools/zone_picker/app.py#L316-L324)); Tool 11 uses a **fourth** formula (`Σ(ratio×w if fired)/Σw`). **Tool 9 is the gate → reproduce Tool 9's per-classifier forms exactly.** Document the divergence; do not silently reconcile it.
- [x] **AC13b — 🔴 The shader MUST IGNORE `minimap_identification.roi`. It is dead in the CPU reference, and honouring it invalidates the whole bench.** Zone rects are **absolute reference-resolution coordinates** — evaluate them against the full 1920×1080 frame. Do **not** crop to `roi`, do **not** treat zone coords as roi-relative.

  This is not a style note. `roi` **looks** authoritative and is not:

  | fact | evidence |
  |---|---|
  | `roi` = `{"name":"minimap","x":63,"y":922,"width":3,"height":5}` — a **3×5-px** box | `output/zones/v2/minimap_identification.json` |
  | It is **byte-identical to `atlantis_z10`'s rect** — a stray zone pick that leaked into the field | verified, Story 9.15 code review |
  | **120 of 121 map zones fall entirely outside it** (zones span x 8–606, y 741–1061; roi spans x 63–66, y 922–927). The only zone inside is the one it was copied from | verified, Story 9.15 code review |
  | Tool 9 parses it into `ScoringConfig.minimap_roi` and **never reads it again** — `extract_roi`/`scale_roi` are called from nowhere in the tool path | [roi_detection_tester.py:440](../../apps/tooling/tools/roi_detection_tester.py#L440), `minimap_roi` has exactly 3 references: field decl, construction, kwarg |

  **That dead field is why the pinned baseline reads `map_id 1.0`.** A shader that "correctly" honours `roi` would crop away 120/121 zones, score ≈0, and diverge catastrophically from a CPU reference that silently ignores it — and the failure presents as *"the GPU port is broken"*, not *"the config is odd"*. Under AC13 **Tool 9 is the gate**: reproduce what Tool 9 *does*, not what the config *appears to say*. Same bucket: `minimap_identification.id` is the literal string `"test"` — also inert, also not a defect to fix here.

  🔴 **Do not "fix" the data to make this cleaner.** Zone fragments are fenced by AC18, and any zone-value edit breaks Story 9.15's byte-identity guard (`tests/test_zone_fragments_v2.py`) and un-pins the baseline AC12 depends on. Report both anomalies in the AC11 report as **known data defects with zero runtime effect today**, and leave the fix to 9.9b.
- [x] **AC14 — 🔴 A PC number is NEVER a mobile number (E6).** Rated **High** risk ([SCP:146](../sprint-change-proposal-2026-07-16.md#L146)); *"written into 12.1's scope"*. The report MUST phrase every number as **feasibility / relative speedup**, and MUST NOT claim to bind **PERF-002** or **PERF-010**. Only 12.2 on the Poco X5 Pro 5G binds those; 12.3 re-baselines ([architecture.md:842](../architecture.md#L842)). The `<10 s` target is *"the aspiration, not an AC"* ([SCP:246](../sprint-change-proposal-2026-07-16.md#L246)). Include the reference-device note verbatim in the report.
- [x] **AC15 — Record the new-dep decision explicitly (E5).** `moderngl>=5.12,<6` into **both** `apps/tooling/pyproject.toml` and `apps/tooling/requirements.txt`. Recorded decision in the story's Dev Agent Record, **not a silent drift**. Two notes: (i) the manifests are **already out of sync** — `requirements.txt` is missing `jsonschema`, which `map_config_emitter.py:25` hard-imports; fixing it is in scope for this story. (ii) `moderngl` needs only `glcontext` and declares no numpy pin — the `numpy>=1.24,<2` pin is **not** a conflict. (iii) **`moderngl` in `apps/tooling` does NOT trip SEC-007** — that allowlist is scoped to the mobile artifact ([architecture.md:2190](../architecture.md#L2190), verbatim carve-out). FFmpeg is a system-PATH dep, already documented — it lands in no manifest (Finding 1).

### Gates

- [x] **AC16 — pytest.** New `apps/tooling/tests/test_<name>.py`. Pure-logic only: **no GL context, no real video decode, no Tk, no PIL** in tests — the GL context is the analogue of Tk here. Mock the decoder (synthetic BGR frames, 9.13 precedent). Cover: LUT packing, result decoding, all three hue branches (incl. `h_tol=180` full-circle and a 0/1-crossing case), `min_ratio` quantization at 1×1 and 2×2 rects, phase state machine, circular buffer N-2 emission, doubt outcome. Baseline **208 tests collected** — 0 regressions. ⚠️ **Was 204**; the Story 9.15 code review added `tests/test_zone_fragments_v2.py` (+4) — the fragments→config regression guard AC12's pinned baseline now rests on.
- [x] **AC17 — `wardentooling.py` registration.** Tool 12 registered: `flow_*` fn + `_TOOL_MAP` entry + `choices_main` label + `menu_main` branch + `_reprompt_source` branch. **⚠️ `-m` package + positional video is a first** — video sits at `last_args` index **2** (`["-m", "tools.X", <video>, ...]`), not index 1 as in the `video_test` pattern. `run_tool` needs **no** change (it already does `[sys.executable] + args`).
- [x] **AC18 — Scope fence.** Touch **nothing** outside `apps/tooling/tools/<name>/`, `apps/tooling/tests/test_<name>.py`, the two manifests, `wardentooling.py`, and (AC0a) `utils/video.py`. **Do NOT touch:** `contracts/map-config.schema.json` (E1 — no `schema_version` bump; [INVARIANT 1] makes `contracts/` master), Tool 9, Tool 10, Tool 11, the emitter, zone fragments, or any zone data. No mobile/web files.
- [x] **AC19 — ~~[HELD]~~ DONE 2026-09-15.** `review → done` flip + post-merge sprint-status update. Two-PR pattern collapsed to a single pass: AC20's merge landed on `main` in the same session, so the chicken-and-egg the pattern exists to avoid does not arise. Both this file's `Status:` and the `12-1-pc-poc-gpu-megashader-bench` key in `sprint-status.yaml` now read `done`.
- [x] **AC20 — ~~[HELD]~~ DONE 2026-09-15.** Local `git merge --no-ff` per Epic 9 precedent (`gh` is unauthenticatable non-interactively). Conventional Commits, scope **`tooling`** ([INVARIANT 12]). **Delivered:** feature `6254833` *"feat(tooling): add tool 12 keyframe engine bench — GPU mega-shader POC (Story 12.1)"* + record `f0b91a7`, both on `correct-course-engine-first-pivot`, then the whole engine-first package merged `--no-ff` into **`main`** as `fbd4fef` *"chore: merge engine-first pivot — Epic 12 + Story 9.15 + Story 12.1"*. Merged locally rather than via PR — sole developer, working directly on `main` from here (Stephane, 2026-09-15). Gates re-verified on the merge result: `uv run pytest` → **305 passed**.

---

## Tasks / Subtasks

- [x] **Task 1 — Kickoff + pre-flight** (AC0)
  - [x] Resolve AC0a/AC0b/AC0c/AC0d; record verdicts in Dev Agent Record.
  - [x] Confirm `ffmpeg`/`ffprobe` on PATH (`check_ffmpeg()`); confirm `python --version` ≥3.11 (local: **3.11.15**, ffmpeg **8.0.1**).
  - [x] Pin the pytest baseline: `cd apps/tooling && uv run pytest --collect-only -q` → expect **204**.
  - [x] Sanity-check the corpus: `map_config.v2.json` = 134 rules; `output/labeled/v2/` = 2666 PNGs / 16 classes; `videos/V2/` = 4 captures.
  - [x] Run `get_gop_interval()` on a `videos/V2` capture — **validate the epic's GOP-2s / 2400-keyframe assumption rather than inheriting it** ([SCP:62](../sprint-change-proposal-2026-07-16.md#L62)). Record the real number.
- [x] **Task 2 — CPU baseline FIRST** (AC12)
  - [x] Read the existing latest report: `output/roi_detection_tests/v2/2026-05-30T135106/report.json` (hud **0.9805** / in_match **1.0** / map_id **1.0**).
  - [x] Re-run Tool 9 unmodified: `uv run python tools/roi_detection_tester.py --config output/map_configs/map_config.v2.json --save-frame-predictions`.
  - [x] **Confirm the re-run reproduces those three numbers.** If it diverges → STOP and report (the config or corpus moved; the comparison is unanchored). Archive the confirmed run as **the** baseline. Without this, AC11 is unanchored.
- [x] **Task 3 — Dependency decision + manifests** (AC15)
  - [x] Add `moderngl>=5.12,<6` to `pyproject.toml` + `requirements.txt`; add the missing `jsonschema` to `requirements.txt`.
  - [x] `uv sync`; verify `create_context(standalone=True, require=330)` works headless. Record GL vendor/version.
- [x] **Task 4 — Decode path** (AC2, AC5, AC0a)
  - [x] Apply the `-vsync 0` → `-fps_mode passthrough` rename in `utils/video.py`; add the native-resolution variant.
  - [x] Verify keyframe count against `get_keyframe_timestamps()` — **assert counts match**; a CFR-duplication regression shows up here (1999 vs 8).
  - [x] Stream one frame at a time. Never accumulate.
- [x] **Task 5 — Pure-logic core** (AC1, AC3, AC0c, AC8b) — *all GL-free, all unit-testable*
  - [x] `pack_rules(config) -> (np.ndarray[150,3,4], rule_index)` per the AC0c layout; pre-resolve OpenCV int bounds + `mode` via `zones.py`'s conversions; `Rect.clamp_to` applied here; assert `n_rules <= 150`; **return the texel-index → `(owning_class, zone_id)` map**.
  - [x] `decode_results(rgba8_150x1) -> list[bool]` (threshold `>127`).
  - [x] `frames.py` — the AC8b seam: labeled-PNG source + video-keyframe source behind one interface.
  - [x] Phase state machine (port from `video_test._run_state_machine` — **read the bug note in Dev Notes first**) + doubt resolution (AC8).
  - [x] 3-keyframe circular buffer emitting N-2.
  - [x] CPU scorer reproducing Tool 9's **three per-classifier formulas** + `_argmax_with_threshold` semantics (AC13).
- [x] **Task 6 — Shader + GL seam** (AC4, AC6, AC7)
  - [x] GLSL body, ES-3.0 subset; `#version` line swappable; RGBA8 target.
  - [x] Gate on `glslangValidator -G -S frag`.
  - [x] GL module isolated behind `run()`.
- [x] **Task 7 — Wire the bench + outputs** (AC9, AC10, AC11)
  - [x] `results.json` + thumbnails → `output/<video_stem>/`.
  - [x] Instrument decode / upload / shader+readback separately.
- [x] **Task 8 — Accuracy comparison** (AC11, AC13, AC14)
  - [x] Shader vs Task-2 baseline on the same labeled corpus.
  - [x] Report phrased as feasibility/relative-speedup only. Reference-device caveat verbatim.
- [x] **Task 9 — Tests + registration** (AC16, AC17)
  - [x] `test_<name>.py`; `uv run pytest` → 204 + new, 0 regressions.
  - [x] `pnpm --filter tooling test` parity.
  - [x] Register Tool 12 in `wardentooling.py`; smoke `python -m tools.<name> --help`.
- [ ] **Task 10 — [HELD] Delivery** (AC19, AC20) — commit + local `--no-ff` merge; hold the post-merge pass.

---

### Review Findings

*Code review 2026-07-19 (`/bmad-code-review`, 3 adversarial layers: Blind Hunter / Edge Case Hunter / Acceptance Auditor). 43 raw findings → 3 decision-needed, 28 patch, 5 deferred, 7 merged-or-dismissed. Suite independently re-verified: **262 passed, 0 failures**.*

#### Decision needed

- [ ] **[Review][Decision] Span `matches` aggregation silently replaces 9.13's algorithm** — `__main__.py::_run_video` sums per-frame `map_scores` across a span and takes `max()`, with `confidence` = the **unbounded raw sum**. 9.13's `_aggregate_span_map` ([video_test.py:644-677](../../apps/tooling/tools/video_test.py#L644-L677)) uses **mode of per-frame argmax**, ties broken by mean score then canonical `ordered_slugs` position, `confidence` = **bounded mean**. Three consequences: (a) `scores.pred_map` — the thresholded, tie-broken prediction from the carefully-reused `_argmax_with_threshold` — is computed then **discarded**; (b) `identification_threshold` is never applied at span level; (c) `if agg:` is **always true** (every frame carries all 13 slugs incl. `0.0`), so the `"unknown"` branch is **dead code** and a span where no map zone fired returns an arbitrary insertion-ordered slug with `confidence: 0.0`. Also drops 9.13's deterministic tie-break → REL-005 regression against a shape AC10 calls "inherited verbatim". **Options: (1) restore 9.13's mode-of-argmax + mean confidence; (2) keep the sum and amend AC10 + REPORT.md to declare the divergence explicitly.** Blocks P12.
- [ ] **[Review][Decision] Negative signed right-shift in the ES-3.0 fragment path** — `keyframe_engine_bench.frag:~2673` does `h = (h * hdiv + 2048) >> 12;` where `h` can be negative (line +1 exists solely to correct it: `h = h + ((h < 0) ? 180 : 0);`). The shader deliberately avoids integer `%` and `/` because ESSL 3.00 leaves them undefined for negative operands — right-shift of a negative signed int sits in the same implementation-defined bucket. Desktop-proven, Adreno-unproven, and AC6's whole premise is that desktop proves nothing. **Options: (1) bias before the shift (`h += (h<0) ? 180*4096 : 0`); (2) do the divide in float; (3) record for 12.2 and leave.**
- [ ] **[Review][Decision] AC18 fence text does not cover `uv.lock`** — the diff modifies `uv.lock` (adds `glcontext` + `moderngl`), which is mechanically unavoidable given AC15 mandates the manifest change, but `uv.lock` is not on AC18's permitted list. Substantive intent is satisfied — **verified: no zone data, no `contracts/`, no Tool 9/10/11, no emitter, no mobile/web files touched**. **Options: (1) amend AC18 to name `uv.lock`; (2) accept as ratified in the Dev Agent Record.**

#### Patch

- [ ] **[Review][Patch] 🔴 Rect area > `MAX_RECT_TEXELS` silently under-counts instead of failing** — loop caps at `min(area, 4096)` but `ratio = count / area` divides by the **full** area, so a rule can never exceed `4096/area` and silently under-fires vs `band_inrange_ratio`. `pack_rules` validates `n_rules > MAX_RULES` but **never** rect area. Latent (shipped rects 1–25 px), fails as a wrong number not an error, in the one module whose entire job is parity. *Found independently by two blind layers; confirmed in review.* [keyframe_engine_bench.frag:43,127,166 + lut.py:154]
- [ ] **[Review][Patch] `scoring.py` — the module implementing AC13's three formulas — has zero test coverage** — tests import `lut`, `phases`, `frames`, `shader`, `zones`, `roi_detection_tester` and **never** `scoring` / `score_from_fires` (verified: 0 references). Swap the map-ID formula for the HUD one and the suite still passes green. [tests/test_keyframe_engine_bench.py]
- [ ] **[Review][Patch] `TestCpuParityContract` tests only OpenCV, never any Tool 12 code** — the 1×1/2×2/zero-area tests call `band_inrange_ratio` exclusively; no `resolve_band_bounds`, no `pack_rules`, no comparison of the two. They pass verbatim against an empty package. `test_modes_match_band_inrange_ratio_branch_selection` ends `assert 0.0 <= ratio <= 1.0` — definitionally cannot fail. [tests/test_keyframe_engine_bench.py:937-991]
- [ ] **[Review][Patch] `doubt` is treated as a phase change and emits spurious thumbnails** — trigger is `state != prev_state` on the **emitted** state, which can be `doubt`; `phases.py` deliberately holds internal state on doubt so it does not split a span. Every `in_match→doubt→in_match` blip writes two PNGs named outside 9.13's phase vocabulary. Should test `resolver.state`. Doubt fired 2/1061 → up to 4 of 55 shipped thumbnails are non-transitions. *Confirmed in review.* [__main__.py:424-435]
- [ ] **[Review][Patch] Resolution mismatch skips every frame and still exits 0 with a plausible `results.json`** — `if (w,h) != (exp_w,exp_h): continue`; accuracy is `c/float(n)` over survivors only, with **no field recording how many frames were dropped**. A non-16:9 source (or a config missing `reference_resolution.width`, where `_config_extras` *fabricates* a 16:9 width behind a stderr WARN) drops everything and writes `n_keyframes: 0` / `accuracy: 0.0` as a well-formed result. Nothing in the output proves 2666 frames were evaluated. Also desyncs AC9's N-2 guarantee (ring.push is after the `continue`, so "two back" means two *accepted* back). [__main__.py:195-216,389-396]
- [ ] **[Review][Patch] `main()` catches only `(ValueError, OSError)` — four live failure classes traceback** — `check_ffmpeg()`/`get_video_info()` raise `RuntimeError`; `get_video_info` raises `CalledProcessError` on corrupt input; `import moderngl` raises `ImportError`; `create_context` raises `moderngl.Error`; `_selftest` raises `RuntimeError`. All bypass the `error: ...` + exit-1 contract, surfacing as raw tracebacks through `run_tool` in the menu. [__main__.py:618]
- [ ] **[Review][Patch] `--profile-gpu` returns before the `try`, bypassing the error handler entirely** [__main__.py:584-589]
- [ ] **[Review][Patch] `MegaShader.__init__` leaks the GL context and ~6 MB of textures when `_selftest()` fails** — ctx/textures/fbo/vao are created, then `_selftest()` (designed to raise) runs on the last line. `__init__` raising means `with` never enters, so `release()` never runs. Ironic given the self-test exists precisely for this failure class. Needs try/except → `release()` → re-raise. [shader.py:132-137,200-210]
- [ ] **[Review][Patch] `decode_s` reads an unvalidated dict key — the decode-bound headline degrades silently to zero** — `float(prof.get("ffmpeg_read", 0.0))`. A rename or an unrecorded stat on the native path prints `decode 0.000 ms/kf` and suppresses `gpu_speedup_vs_decode` via a falsy check. The story's central thesis reports as unmeasured with no error. [__main__.py:2229]
- [ ] **[Review][Patch] `results.json` hardcodes `"config": "map_config.v2.json"` regardless of `--config`** — 9.13 writes `os.path.basename(config)`. Bench a v3 config and the artifact 12.3 inherits misidentifies its own provenance. *Found by two layers.* [__main__.py:2250]
- [ ] **[Review][Patch] `results.json` omits 9.13's top-level `video` and `stride` keys** while REPORT.md §11 claims "9.13's shape verbatim". [__main__.py::_build_results]
- [ ] **[Review][Patch] REPORT.md misattributes "span confidences in the hundreds" to Finding 3** — the per-frame `17.0` is genuinely Finding 3's degeneracy; the **hundreds are not** — they are produced by this story's own cross-frame summation (see Decision #1). An artifact introduced by 12.1 is presented as evidence about the shipped config, in the deliverable that feeds 12.3. [REPORT.md §8 + Completion Note 5]
- [ ] **[Review][Patch] REPORT.md's `~7×` zero-copy row reads as an Android verdict (AC14 red-line)** — a PC shader time with the PC upload arithmetically removed, placed in a **verdict** column about Android hardware ("the GPU engine is not marginal on Android — it is excellent"). Caveated in surrounding prose, but the row quoted alone states a conclusion AC14 forbids 12.1 from binding. [REPORT.md §4]
- [ ] **[Review][Patch] Wall-clock timing includes GL context creation, GLSL compile and the self-test** — `t_wall0` is set *before* `with MegaShader(...)`, so `ms_per_keyframe_total` amortizes them. Small at 1061 frames, but this is the headline deliverable and 12.2 re-measures it the same way on a device where context creation is far more expensive. [__main__.py:2151-2154]
- [ ] **[Review][Patch] `--baseline-csv` failures discard the entire completed GPU run** — `_compare_to_baseline` runs *after* the full 2666-frame loop; a missing file raises `OSError` (exit 1, no `accuracy.json`), a missing column raises `KeyError` (uncaught). Validate the CSV header *before* the expensive loop. [__main__.py:253,315-325]
- [ ] **[Review][Patch] Padding texels evaluate as *fired*** — zeroed rules give `area=0` → `ratio=0.0`, `min_ratio=0.0`, and `step(0.0, 0.0) == 1.0`. Harmless only because `decode_results` slices `[:n_rules]`; a landmine for any future full-readback consumer. `test_unused_texels_are_zeroed` checks the *input* texture, not the output. [lut.py + .frag]
- [ ] **[Review][Patch] `upload()` has no shape validation** — `frame_tex.write(...)` with no check against construction geometry. Callers guard it today; a same-byte-count/different-geometry frame (1440×1080 vs 1080×1440) yields silently transposed pixels. Same reasoning that produced `_selftest`. [shader.py:3592-3594]
- [ ] **[Review][Patch] `--doubt-margin >= 0.5` freezes the state machine, accepted without warning** — validated `>= 0` only; every ratio in `(0,1)` then satisfies `|ratio-0.5| < margin` → `CALL_DOUBT` (a hold). Timeline goes near-uniformly `doubt`, `matches` empty. [__main__.py:598-600, phases.py:91-93]
- [ ] **[Review][Patch] A config with zero `in_match` zones yields a whole-video `not_in_match` timeline, silently** — `pred_in_match="unknown"` / conf `0.0` is ignored; the classifier driving the entire timeline is unconfigured and nothing warns. [scoring.py:113-116 → __main__.py:409-412]
- [ ] **[Review][Patch] Failed thumbnail encode is dropped without a warning** — `if _write_png(...)` skips the append when `cv2.imencode` returns `ok=False`; the transition vanishes from `thumbnails` as though none was warranted. (Write failures *do* raise and are caught — only the encode path is silent.) [__main__.py:430]
- [ ] **[Review][Patch] `--accuracy` silently ignores a positional video argument** [__main__.py:513-524,553]
- [ ] **[Review][Patch] `in_match_call`'s `ratio > 0.0` guard diverges from Tool 9 at `threshold = 0`** — docstring claims `doubt_margin=0` "collapses to Tool 9's hard-binary call"; that holds only for `threshold > 0`. Undocumented and untested (the zero-margin test only exercises the default 0.5). [phases.py:3067, scoring.py:3331-3334]
- [ ] **[Review][Patch] `iter_labeled_frames` HUD filter is `startswith("v")`** — any future sibling dir beginning with "v" (`videos/`, `validation/`, `v2_backup/`) is ingested as a HUD version and pollutes the HUD denominator. The guard test uses `notes`, which cannot catch this. [frames.py:2519]
- [ ] **[Review][Patch] `validate_glsl` conflates "glslangValidator not installed" with "shader failed the gate"** — both render as `[FAIL]` + exit 1 with the same message; CI cannot tell "gate not run" from "gate failed". [shader.py:3467-3472, __main__.py:1953-1960]
- [ ] **[Review][Patch] `--profile-gpu` benchmarks on an unseeded random frame** — not reproducible run-to-run and not representative of HUD content, yet the Dev Agent Record calls its output "the most decision-relevant number for 12.3". Seed it or use a real frame. [__main__.py:1891]
- [ ] **[Review][Patch] Dead code in the GL seam** — `self._n_bytes = MAX_RULES * 4` assigned, never read; `map_zone_counts` carries zero-zone map entries that are then skipped. Both sit in modules whose stated job is being the auditable parity contract. [shader.py:3560, scoring.py:3338-3350]
- [ ] **[Review][Patch] `_time_cpu_rule_eval` docstring is inaccurate** — claims "the same frames the GPU just ran"; it re-walks `iter_labeled_frames` from scratch, and the `break` check fires after the generator has already decoded the next frame. Correctness-neutral (decode is outside the timer), but the docstring asserts a property the code does not have. [__main__.py:2070-2077]
- [ ] **[Review][Patch] Dev Agent Record pytest counts are off by one** — records "208 → 261" and "+53"; actual is **208 → 262** and **+54** (independently re-run: 262 passed, 54 in `test_keyframe_engine_bench.py`). Arithmetic is otherwise self-consistent, so the suite is genuinely clean — but this number gets cited as a downstream baseline. [story Dev Agent Record + sprint-status.yaml]

#### Deferred

- [x] **[Review][Defer] ESSL `highp` is not guaranteed IEEE-754, so the integer-HSV exactness proof does not transfer to the target** [keyframe_engine_bench.frag:2656-2666] — deferred, cannot be resolved on PC (12.2)
- [x] **[Review][Defer] `min_ratio` compared at float32 on GPU vs float64 on CPU — a genuine unguarded parity seam** [lut.py:161,171] — deferred, unreachable with shipped values
- [x] **[Review][Defer] Stale thumbnails from a previous run persist in `--out`** [__main__.py:530-531] — deferred, cosmetic
- [x] **[Review][Defer] Reference-device GPU contradiction: code says Adreno 642L, sprint-status says 619** [__main__.py:1810-1816] — deferred, 12.2's admin per the story's own note
- [x] **[Review][Defer] A test pins buffer *identity* (`out[0].frame_bgr is src`), locking in aliasing the ring buffer depends on not happening** [tests:1168-1179] — deferred, green today

---

## Dev Notes

### Dependency Reality Check — read before believing the epic's dependency line

The epic says **"Dependencies: Story 9.15 (pilot zone set — the POC needs zones to test against)"** ([:3310](../epics-and-stories.md#L3310)). The pivot's premise was a chicken-and-egg: *12.1 needs zones → 9.9b makes zones → 9.9b is blocked*.

**What is actually on disk contradicts that premise.** 9.15 was scoped as *"minimal population (2–3 maps + HUD + in_match)"* ([SCP:184](../sprint-change-proposal-2026-07-16.md#L184)). Reality:

| Asset | Path | State |
|---|---|---|
| Emitted config | `apps/tooling/output/map_configs/map_config.v2.json` | **13 maps / 121 map zones / 10 hud / 3 in_match = 134 rules, fully populated, tuned** |
| Labeled corpus | `apps/tooling/output/labeled/v2/` | **2666 PNGs / 16 classes** (13 maps + lobby 296 / score 41 / transition 43) |
| Real captures | `videos/V2/` | **4 EVA captures, 12.7 GB, 6h13m total** |

The human campaign 9.15 was invented to pilot **already ran past 9.15's finish line**. 12.1 can run **today** (AC0b Option A).

**But two real problems exist — flag them, do not fix them here:**

1. 🔴 **The zone-fragment source-of-truth contract is broken.** 9.9b AC9 Option A's design is "fragments committed, `map_config` regenerable from them." The inverse is true: `map_config.v2.json` is **gitignored** (`output/*`), and **none of the four required fragments exist** — `zones/v2/` holds only `_SCAFFOLD_README.md`, `manifest.template.json` (≠ `manifest.json`), and the untracked `minimap_identification.json.bak` (≠ `.json`). `map_config_emitter.py` hard-requires all four (`_FRAGMENT_FILES`) and raises `FileNotFoundError` on the *first* one. **The emitter cannot regenerate the config 12.1 consumes. Git has zero copies of any of it.** `manifest.template.json` still carries the deliberate string sentinel `"TODO_HUMAN_CALIBRATION__see_AC3__..."`, which cannot silently pass the AC3 dry-run.
2. ⚠️ **The measured baseline is real but unversioned.** 39 Tool 9 reports exist under `output/roi_detection_tests/v2/` (AC12) — but that whole tree is **gitignored**, so the only evidence of the engine's current accuracy is untracked local state. One `git clean -xfd` erases the config, the corpus, the baseline, and the `.bak` together.

Both belong to 9.15 — which likely needs re-scoping from "greenfield picker campaign" to **"salvage, reconstruct fragments, commit, and baseline"**. Raised for Stephane at the end of this file. **12.1 is read-only w.r.t. zone data and is not blocked by either.**

Two data-quality caveats to note in the report (not to fix): `minimap_identification.roi` is a **3×5-pixel** box with `id: "test"` — placeholder-looking; and `bastion` is in `MAP_LABELS` but has neither corpus nor config entry (13 maps in practice, not 14).

> ⚠️ **Updated 2026-07-16 (Story 9.15 code review) — the `roi` caveat was underrated and is now binding as [AC13b](#acceptance-criteria).** It is not merely "placeholder-looking": `roi` is **byte-identical to `atlantis_z10`'s rect**, **120 of 121 zones fall outside it**, and Tool 9 **parses it and never reads it**. A shader that honours it scores ≈0 and the bench reads as a broken GPU port rather than a dead config field. `id: "test"` stays a report-only note. **Neither is fixable here** — zone data is fenced by AC18 and guarded by `tests/test_zone_fragments_v2.py`.

### The 150×3 LUT — AC0c Option A (RECOMMENDED)

The brief's *"150×3 — position + HSV + V"* ([SCP:44](../sprint-change-proposal-2026-07-16.md#L44)) does not survive contact: a rule needs rect(4) + 6 HSV fields + `min_ratio` = **11 values**, and center/tol packing forces the shader to re-derive bounds and re-implement the wrap branching in float — which will **not** reproduce `cv2.inRange`'s inclusive **integer** bounds.

**Pre-resolve the bounds on the CPU instead — exactly as `zones.py` already does — and pass the resolved integers.** Twelve slots, twelve values, perfect fit, and it collapses the shader to one branchless compare:

| texel | RGBA channels |
|---|---|
| `(i, 0)` | `x`, `y`, `width`, `height` — ref-res pixels, as floats |
| `(i, 1)` | `h_lo`, `h_hi`, `s_lo`, `s_hi` — **OpenCV integer space**, as floats |
| `(i, 2)` | `v_lo`, `v_hi`, `min_ratio`, `mode` |

`mode` ∈ {**0** = normal, **1** = wrap (`h_lo<0 || h_hi>179`), **2** = full-circle (`h_hi-h_lo >= 180`)} — mirroring `band_inrange_ratio`'s three branches 1:1.

**This packing is sufficient — no extra fields are needed for the wrap branch.** The shader derives `h_lo % 180` / `h_hi % 180` itself: GLSL's `mod()` is **floored**, matching Python's `%` for negative operands (`mod(-6.0,180.0) == 174.0`), so the wrap branch's two sub-intervals `[h_lo%180, 179]` ∪ `[0, h_hi%180]` reconstruct exactly. The `max(0,·)` / `min(255,·)` clamps on S/V are provable no-ops on the shipped data and are applied CPU-side anyway.

CPU-side, reuse `zones.py`'s conversions **verbatim** — do not re-derive them:

```python
h_c, s_c, v_c = hsv_user_to_cv(band.h_center, band.s_center, band.v_center)
h_t = tol_h_user_to_cv(band.h_tol)      # magnitude — NO % 180; clamped to 90
s_t = tol_sv_user_to_cv(band.s_tol)
v_t = tol_sv_user_to_cv(band.v_tol)
h_lo, h_hi = int(round(h_c - h_t)), int(round(h_c + h_t))
s_lo, s_hi = max(0, int(round(s_c - s_t))), min(255, int(round(s_c + s_t)))
v_lo, v_hi = max(0, int(round(v_c - v_t))), min(255, int(round(v_c + v_t)))
```

🔴 **The center/tolerance asymmetry is the #1 shader-port trap** and `zones.py` documents it explicitly ([zones.py:107-128](../../apps/tooling/tools/common/zones.py#L107-L128)):
- `hsv_user_to_cv` applies `% 180` — correct for a hue **center** (a position on the circle).
- `tol_h_user_to_cv` **does NOT** mod by 180 — *"a tolerance is a magnitude, not a position; modding it would silently collapse wide bands (e.g. h_tol=380 → 10)"*. Values ≥90 CV units saturate the circle and are **clamped, not wrapped**.

Shader: fragment for output texel `i` fetches rule `i`'s 3 texels, loops the rect's pixels in the frame texture, converts each to OpenCV-quantized HSV, counts in-band, computes `ratio = count/area`, outputs `step(min_ratio, ratio)`. **`cv2.inRange` is inclusive on both bounds** — use `>=` / `<=`, and note the fire test is `ratio >= band.min_ratio` (`>=`, not `>`, [roi_detection_tester.py:584](../../apps/tooling/tools/roi_detection_tester.py#L584)).

Dynamic loop bounds are legal in ES 3.00 fragment shaders (the ES 2.0 restriction was lifted). Rects are 1–25 px so the loop is trivial — still, cap it defensively.

⚠️ **`clamp_to` is part of the contract, and the naive `ratio = count/area` breaks it.** Tool 9 clamps each rect to the frame before evaluating ([roi_detection_tester.py:582](../../apps/tooling/tools/roi_detection_tester.py#L582)) and `band_inrange_ratio` divides by the **clamped** `mask.size`, not the declared `width×height`. `Rect.clamp_to` returns **0-area** when fully off-frame — a documented bug-fix; the pre-fix version returned a 1×1 sliver that could false-fire ([zones.py:36-74](../../apps/tooling/tools/common/zones.py#L36-L74)), and `band_inrange_ratio` returns `0.0` on `region.size == 0`. Today this is **latent**: 0 of 134 rects exceed 1920×1080 (max `x+w`=1793, `y+h`=1063). It becomes a silent parity break the moment a zone is drawn off-edge. Clamp in the packer (CPU-side, where `Rect.clamp_to` can be reused verbatim) so the shader's denominator is already correct.

### HSV on the GPU

**The `/180` vs `/179` question is settled: 180.** Brute-forced across all 2²⁴ RGB inputs — OpenCV's H **max is 179 and 180 is unattainable**; it is an excluded wrapping endpoint (like clock minutes ÷60, not ÷59). Using 179 imposes a **1.005× hue stretch (~1.3°)** — enough to flip tight rules.

```
h_glsl = h_cv/180.0     s_glsl = s_cv/255.0     v_glsl = v_cv/255.0     # S/V: 255 IS attainable
```

Use Sam Hocevar's branchless `rgb2hsv`. **Do not swizzle to `.bgr`** — `COLOR_BGR2HSV` expects BGR and yields true hue; a GPU RGB texel yields the same. **Hoist `rgb2hsv` out of the rule loop.**

🔴 **REJECTED ALTERNATIVE — do not use the symmetric circular-distance test.** The obvious-looking branchless form is *not equivalent* to `band_inrange_ratio` and must not be substituted for AC0c Option A:

```glsl
// ⚠️ NON-NORMATIVE — REJECTED. Reads hCenter/hTol, which the AC0c LUT does not carry,
// and disagrees with cv2.inRange on 31 of the 134 shipped rules.
float hDist = abs(fract(hsv.x - hCenter + 0.5) - 0.5);
float ok = step(hDist, hTol) * step(s0,hsv.y)*step(hsv.y,s1) * step(v0,hsv.z)*step(hsv.z,v1);
```

**Why it fails.** `h_c` always lands on `.0`/`.5` (user H ÷ 2), so `int(round(h_c ± h_t))` under Python's **banker's rounding** produces bands that are **asymmetric about `h_c`** — which a symmetric distance test cannot reproduce. Brute-forced across H∈[0,179] for all 134 rules: **31 disagree.** Examples:

```
hud_z02      normal  h_c=14.5  h_t=5.0   cv=[10,20]    → symmetric form misses H=20
atlantis_z00 normal  h_c=11.5  h_t=5.0   cv=[6,16]     → symmetric form misses H=6
hud_z09      wrap    h_c=174.0 h_t=69.5  cv=[104,244]  → symmetric form misses H=64,104
```

**Normative rule: the CPU pre-resolves the integer bounds exactly as `zones.py` does, and the shader compares against those bounds inclusively.** Parity with `cv2.inRange` comes from *not re-deriving the band on the GPU*. The 68 `h_tol=180` rules still cost no special case — they resolve to `mode=2` (full-circle) on the CPU, where hue is simply not tested.

⚠️ **Mobile-only NaN trap (record for 12.2, cannot reproduce on PC):** `rgb2hsv`'s `1.0e-10` epsilon is ~6 orders below `mediump`'s smallest normal (2⁻¹⁴) → flushes to 0 → `0/0 = NaN` on greys → **NaN fails every `step()` silently**. Our 68 low-sat rules are exactly the greys. Use `highp`, or raise epsilon to ~1e-4.

### 🔴 The colour-space risk that threatens the whole port (for 12.2 — record, don't solve)

The largest Android risk is **colour, not the graphics API**. `samplerExternalOES` performs an **implicit, driver-defined YUV→RGB conversion** that AOSP does not specify; FFmpeg's rgb24 agrees only by coincidence.

Quantified on a real V2 capture — which is tagged `color_range=tv` (limited) + `bt709`, exactly the risky combination. Divergence vs correct decode, in OpenCV HSV units:

| Error source | ΔS mean | ΔV mean | ΔH mean (S>40) |
|---|---|---|---|
| **range (limited→full)** | **19.68** | 7.64 | 1.22 |
| matrix (709→601) | 1.64 | 0.43 | 1.12 |

**The range error shifts S by ~20 units — and 68 of our rules are tuned at `s_center ≤ 8` with `s_tol` in the tens.** Those zones surrendered H (`h_tol=180`), making them **immune to the matrix error but maximally exposed to the range error**. **The 1.000 map-ID / 0.979 in_match figures are not portable constants** — they were fitted against FFmpeg's conversion.

Mitigation to recommend to 12.2: decode to `COLOR_FormatYUV420Flexible`, upload Y/U/V as separate R8 textures, do YUV→RGB in *our* shader with FFmpeg's exact constants — trading the zero-copy OES path for bit-parity. There is ~21× headroom to pay for it. **Gate 12.2 on a cheap PC-vs-device frame diff before any rule-porting work** (~16 offset / ~9% gain ⇒ range error; saturated-hue shift with greys stable ⇒ matrix error).

### Measured expectations (Intel UHD 770, FFmpeg 8.0.1 — orientation only, not targets)

| Path | Measured |
|---|---|
| `-skip_frame nokey` (**before `-i`**) | **0.49 s** / 120 s segment |
| `-vf select='eq(pict_type,I)'` | 2.63 s — post-decode filter, **zero decode saving** |
| ffprobe packet-level PTS (no decode) | 0.15 s |
| Full 150-rule shader @ 640×360, upload+render+readback | **0.647 ms/frame** |
| Full video: decode+pipe vs GPU (1061 keyframes) | **14.7 s vs 0.69 s → decode-bound ~21×** |

**This confirms the pivot's decode-bound premise. Optimise decode, not GL.** PBO ping-pong is premature at 600 bytes — build synchronous, measure first.

⚠️ **Flag placement:** `-skip_frame` **after** `-i` is misrouted to the *encoder* — it warns, exits 0, and does a **full decode**. Placement is silent-failure territory.

⚠️ **`skip_frame` codec caveats:** a **no-op on VP9 and libaom-AV1** (silently returns all frames) and loses non-IDR keyframes on **open-GOP H.264**. Our V2 captures are safe — verified over 300 s: packets-K = 72, `skip_frame` = 72, all `pict_type=I`, closed GOP. Assert the counts anyway (Task 4).

⚠️ **Subprocess gotchas** (already handled in `utils/video.py` — don't regress them): `stderr` must be drained or the 64 K pipe buffer **deadlocks**; never `communicate()` on video; loop `readinto` for exact `w*h*3` reads; get W/H from ffprobe (hardcoding **shears silently**).

### Reference-device contradiction — do not propagate

[epics-and-stories.md:3315](../epics-and-stories.md#L3315) says *"Poco X5 Pro 5G (SM7325/A14, **Adreno 619**, GLES 3.2-capable)"*. **The GPU is wrong.** SM7325 = Snapdragon 778G = **Adreno 642L**. Adreno 619 is the SD695 — the *old* device, from before the re-anchoring recorded in [[project_warden_reference_device]]. (The research pass also flagged a "Snapdragon 7s Gen 2" framing = SM7435/Adreno 710 — also not this device.) All support GLES 3.2; we target **3.0** and need nothing from 3.1+. **Correcting the epic is 12.2's admin, not 12.1's** — just don't inherit the error into the report.

### Toolchain — verified live 2026-07-16

| Package | Latest | Notes |
|---|---|---|
| **moderngl** | **5.12.0** (2024-10-17) | No release in 21 mo but **last commit 2026-07-11** — maintained, not abandoned. Needs only `glcontext`. |
| glcontext | 3.0.0 | ⚠️ its `__version__` **misreports "2.3.7"** — trust `pip show`. |
| **av (PyAV)** | **18.0.0** (2026-07-02) | Bundles FFmpeg 8.1.2; `requires-python >=3.11`; **no** declared deps. (AC0a Option B.) |
| ffmpeg-python | 0.2.0 (**2019**) | 🔴 **Abandoned 7 years. Do not use.** |
| FFmpeg | 8.1.2 (local: **8.0.1**) | System PATH dep. |

**API currency:** `create_standalone_context()` is **deprecated** → use `create_context(standalone=True)`. `simple_framebuffer()` deprecated → `framebuffer()`. Verified headless on this box: `require=330` → GL 3.3.0 Intel UHD 770; `require=460` → 4.6 available; `GL_ARB_ES3_compatibility` present. Windows uses the WGL backend — **no window, no display needed**. `backend='egl'` is **Linux-only**. RDP sessions fall back to software GL. ⚠️ `require=300` would mean *desktop GL 3.0*, **not ES**.

Note: pip now resolves `opencv-python` to **5.0.0**, which the `<5` pin excludes — pin is doing real work, leave it.

### Existing conventions — bind, don't rediscover

- **Windows non-ASCII path safety is a hard convention.** Read via `np.fromfile` + `cv2.imdecode` (`_read_frame_bgr`, [roi_detection_tester.py:485](../../apps/tooling/tools/roi_detection_tester.py#L485)) — **never `cv2.imread`**. Write via `cv2.imencode` + `open().write()` ([video_timeline_labeler.py:746-753](../../apps/tooling/tools/video_timeline_labeler.py#L746-L753)) — **never `cv2.imwrite`**. Applies to AC9 thumbnails.
- **Config reads use `encoding="utf-8-sig"`** (BOM-tolerant) — [video_test.py:268](../../apps/tooling/tools/video_test.py#L268).
- **Never rely on `HsvBand`'s `min_ratio=0.3` class default** — set it explicitly per zone from the config. Both Tool 9 and Tool 11 call this out; [video_test.py:230](../../apps/tooling/tools/video_test.py#L230) calls it *"the #3 disaster in the story Dev Notes"*. (It happens to be 0.3 everywhere today — that is luck, not license.)
- **Sanctioned sibling reuse pattern** ([video_test.py:88-99](../../apps/tooling/tools/video_test.py#L88-L99)) — Tool 9's module import is side-effect-free (`main()` is `__main__`-guarded). Copy this comment shape when importing from `tools.roi_detection_tester`.
- **`tools/common/labels.py` forbids tkinter/PIL imports** ([labels.py:6-8](../../apps/tooling/tools/common/labels.py#L6-L8)).
- Tools never import each other's `app.py`; they share state only via files ([architecture.md:1940-1944](../architecture.md#L1940-L1944)).
- Launcher runs tools via `subprocess.run([sys.executable] + args, cwd=PROJECT_ROOT)` — **all paths relative to `apps/tooling/`**, not repo root.
- `conftest.py` is the **sys.path shim only — add no fixtures** (9.13 AC10).

### Latent bug in the code you are about to port

[video_test.py:606-614](../../apps/tooling/tools/video_test.py#L606-L614) `_run_state_machine`: `falling_ts = ts` is assigned **immediately before** `(ts - falling_ts) >= dur` is evaluated, so the falling-edge expression is always `0 >= dur` — the branch depends only on `dur`, never on elapsed time. The comment describes the intent ("inclusive on the falling-edge frame"); the code does not implement it. **If you port the state machine, this rides along.** Port the *intent*, note the divergence from 9.13's behavior in the report, and do not silently "fix" Tool 11 (AC18 fences it).

### Charter compliance — verified, not assumed

- The **only** absolute prohibition is cloud CV ([architecture.md:866](../architecture.md#L866) — *"FORBIDDEN — fall back to cloud CV | NEVER"*). A GPU shader is on-device ⇒ **[INVARIANT 3]** ([:1251-1254](../architecture.md#L1251-L1254)) holds; Innovation #1's privacy + marginal-cost claim is preserved. It is the only rung that was **not** re-armed on 2026-07-16.
- `apps/tooling` is chartered as *"a lab, not a runtime dependency"* ([:432](../architecture.md#L432), [:1028](../architecture.md#L1028)) — a Python POC is squarely in-charter. **No mobile→tooling or web→tooling code path**; the only artifact that crosses is `map_config.json`.
- **Greenfield confirmed:** GPU/GLES/OpenGL/shader/GLSL/ModernGL/EGL/FBO/MediaCodec appear **nowhere** in `architecture.md` outside the 2026-07-16 amendments. The sole pre-existing "GPU" token is [:294](../architecture.md#L294) — a *Dear PyGui* rejected-alternative footnote about a **GUI toolkit**, explicitly *"must not be cited as prior art either way"*. **No prior decision authorizes the GPU path and none forbids it** — the decision entry lands with **12.3**, not here.
- **12.1 does not re-open Story 1.1.** 1.1's rung-0 JSI verdict is FROZEN and remains the record for the JSI path ([architecture.md:842](../architecture.md#L842), [SCP:210-214](../sprint-change-proposal-2026-07-16.md#L210-L214)) — *"editing a completed spike destroys the audit trail. 12.3 supersedes; 1.1 records."*
- **12.1 does not publish the spike report.** `_bmad-output/architecture-spike-gpu-megashader.md` is **12.3's** deliverable ([:3322](../epics-and-stories.md#L3322)). 12.1 feeds it: measured numbers + device profile + fixtures. The **verdict slot is 12.3's** ([architecture.md:868](../architecture.md#L868) defines the four-part shape).
- **12.1 does not re-arm the fallback ladder** (12.3) and **does not re-point Tool 9** (9.16).

### Stale prose in architecture.md — do not inherit

The 2026-07-16 amendments govern where these conflict:
- [:1517](../architecture.md#L1517) / [:1703](../architecture.md#L1703) still call `mapIdentifier.ts` a *"pHash matcher"* — contradicted by [:120](../architecture.md#L120) / [:383](../architecture.md#L383) (ROI+HSV since the 2026-05-14 pivot).
- [:2076](../architecture.md#L2076) / [:1608](../architecture.md#L1608) / [:1781](../architecture.md#L1781) still name `hash_validator.py` as the REL-006 instrument — contradicted by [:120](../architecture.md#L120) (**Tool 9**; `hash_validator` measures Hamming distance and **cannot measure a shader**).
- [:2047](../architecture.md#L2047) still says the FGS *"hosts the main JS context where the JSI binding lives"* — contradicted by [:813](../architecture.md#L813) (EGL contexts are **thread**-bound, not JS-context-bound).
- **Tools 6 and 9 are absent from architecture.md's tree entirely** ([:1596-1620](../architecture.md#L1596-L1620) predates Epic 9). Source their signatures from the code, not the doc.
- Line-number drift: the SCP cites `:684` for Decision #ES-9; the live line is [epics-and-stories.md:696](../epics-and-stories.md#L696). Re-verify citations before pasting.

### Project Structure Notes

```
apps/tooling/
├── tools/
│   ├── <name>/                    # NEW — Tool 12 (AC0d)
│   │   ├── __init__.py
│   │   ├── __main__.py            # thin CLI: argparse, run()/main()
│   │   ├── lut.py                 # PURE: pack_rules / decode_results
│   │   ├── frames.py              # PURE: the AC8b seam — labeled-PNG source | video-keyframe source
│   │   ├── phases.py              # PURE: state machine, doubt, circular buffer
│   │   ├── shader.py              # GL-ISOLATED: context, program, FBO  ← the seam
│   │   └── <name>.frag            # GLSL, ES-3.0 subset
│   ├── common/zones.py            # REUSE verbatim — do not fork the math
│   ├── roi_detection_tester.py    # Tool 9 — READ-ONLY (accuracy gate; 9.16 owns changes)
│   └── video_test.py              # Tool 11 — READ-ONLY (state-machine reference)
├── utils/video.py                 # REUSE — the FFmpeg keyframe pipe (AC0a touches it)
├── tests/test_<name>.py           # NEW — pure logic, no GL
├── pyproject.toml                 # + moderngl
└── requirements.txt               # + moderngl, + jsonschema (already-missing fix)
```

Untracked `__pycache__` shells at `tools/auto_roi_discoverer/` and `tools/minimap_zone_selector/` are 9.11 retirement leftovers — **not** live code, not in git. Ignore them.

### References

- [epics-and-stories.md:3279-3333](../epics-and-stories.md#L3279-L3333) — Epic 12 (the binding record; strictly richer than the SCP)
- [epics-and-stories.md:3293-3300](../epics-and-stories.md#L3293-L3300) — **E1–E7 founding constraints** (exist nowhere else)
- [epics-and-stories.md:3304-3310](../epics-and-stories.md#L3304-L3310) — Story 12.1
- [epics-and-stories.md:696](../epics-and-stories.md#L696), [:3103-3105](../epics-and-stories.md#L3103-L3105) — Decision #ES-9
- [epics-and-stories.md:2820-2821](../epics-and-stories.md#L2820-L2821) — 9.13's surviving state machine + `results.json` shape
- [epics-and-stories.md:2825-2826](../epics-and-stories.md#L2825-L2826) — Tool 9: CPU baseline + sole REL-006 enforcement
- [epics-and-stories.md:2830-2845](../epics-and-stories.md#L2830-L2845) — Story 9.15 (prose only; **no numbered ACs exist**)
- [sprint-change-proposal-2026-07-16.md:41-48](../sprint-change-proposal-2026-07-16.md#L41-L48) — Volet A condensed brief (**the source brief is NOT in the repo — this is the only surviving record**)
- [sprint-change-proposal-2026-07-16.md:62](../sprint-change-proposal-2026-07-16.md#L62) — rects-retained decision + the ~0.2% budget arithmetic
- [sprint-change-proposal-2026-07-16.md:168](../sprint-change-proposal-2026-07-16.md#L168) — Story 12.1's mandated ACs
- [sprint-change-proposal-2026-07-16.md:285](../sprint-change-proposal-2026-07-16.md#L285) — *"one divergence to carry into 12.1"* (AC13)
- [architecture.md:2190](../architecture.md#L2190) — 5th native module + **the SEC-007 carve-out for `moderngl`**
- [architecture.md:842](../architecture.md#L842) — reference-device clamp (**AC14's source**)
- [architecture.md:120](../architecture.md#L120) — REL-006 instrument → Tool 9
- [architecture.md:277-283](../architecture.md#L277-L283), [:1002](../architecture.md#L1002), [:1027](../architecture.md#L1027), [:1033](../architecture.md#L1033), [:1046](../architecture.md#L1046), [:1148](../architecture.md#L1148) — E7 tooling conventions
- [architecture.md:866](../architecture.md#L866), [:1251-1254](../architecture.md#L1251-L1254) — cloud-CV prohibition, [INVARIANT 3]
- [contracts/map-config.schema.json:96-108](../../contracts/map-config.schema.json#L96-L108) — `Hsv`: **user-space, NOT OpenCV-space**
- [contracts/map-config.schema.json:110-139](../../contracts/map-config.schema.json#L110-L139) — `Zone`: the LUT row tuple
- [apps/tooling/tools/common/zones.py:107-161](../../apps/tooling/tools/common/zones.py#L107-L161) — conversions + `band_inrange_ratio` (**the math to replicate**)
- [apps/tooling/utils/video.py:208-299](../../apps/tooling/utils/video.py#L208-L299) — `extract_iframes_scaled` (**Finding 1**)
- [apps/tooling/docs/architecture.md:30](../../apps/tooling/docs/architecture.md#L30), [:72](../../apps/tooling/docs/architecture.md#L72) — FFmpeg-subprocess decode is this package's documented architecture
- Memory: [[project_warden_low_sat_hue_unconstrained]] (**Finding 2**), [[project_warden_engine_first_pivot]], [[project_warden_reference_device]], [[feedback_two_pr_docs_execution]], [[feedback_ac_checkbox_tighten]], [[feedback_batch_manual_checks_epic_end]]

---

## Change Log

| Date | Change |
|---|---|
| 2026-07-16 | **Story implemented via `/bmad-dev-story` (Amelia; claude-opus-4-8[1m]). `ready-for-dev → in-progress → review`.** AC0a–AC0d + AC1–AC18 `[x]`; Tasks 1–9 `[x]`. AC19/AC20 + Task 10 `[ ] [HELD]` (post-merge admin). Delivered Tool 12 `apps/tooling/tools/keyframe_engine_bench/` (8 modules + `.frag` + `REPORT.md`) + `tests/test_keyframe_engine_bench.py` (+53; pytest **208 → 261**, 0 regressions, `pnpm --filter tooling test` parity) + `wardentooling.py` Tool 12 registration + `utils/video.py` (`-fps_mode passthrough` rename + `extract_iframes_native`) + both manifests (`moderngl`, and the pre-existing `jsonschema` gap). **RESULTS: (1) accuracy = EXACT parity — 0 disagreements over 2666 frames, all three classifiers matching the pinned baseline (0.9805 / 1.0000 / 1.0000), which was re-run first and reproduced exactly. (2) decode-bound CONFIRMED — decode 8.862 ms/kf = 62% of a 14.411 ms/kf wall over 1061 keyframes, 3.08× the whole GPU cost. (3) 🔴 the GPU is ~2× SLOWER than the CPU at rule evaluation (3.253 vs 1.667 ms/frame = 0.51×)** — structural: ~800 texel fetches need a 6.2 MB upload, and upload alone exceeds the CPU's entire budget. Does not settle Android (MediaCodec zero-copy removes the upload → ~1.4×); flagged for 12.3 along with the option the evidence permits — that no GPU engine is required at all. **KEY DEVIATIONS (all recorded, all evidence-backed): (a)** rejected the Dev Notes' float `rgb2hsv` and ported OpenCV's **integer** `RGB2HSV_b` into GLSL after brute-forcing it against `cv2.cvtColor` over all 2^24 RGB (0 mismatches; also confirms max H = 179 ⇒ `/180`) — a float path cannot hit integer `inRange` bounds and 31/134 rules have asymmetric bands; this is what bought exact parity. **(b)** AC6's literal `glslangValidator -G -S frag` **cannot validate ES 3.00** (`-G` requires ES ≥ 3.10) — gate runs without `-G`, verified to reject `float x = 1;` on `300 es` and accept it on `330 core`. **(c)** the flagged `video_test.py:613` "latent bug" is **not a bug** — elapsed IS 0 on the falling-edge frame, so `0 >= dur` is the correct, documented intent; no 9.13 divergence to report. **(d)** AC10 verdict: enum **EXTENDED** with `doubt` + `confidence` (remapping = the forcing E4 forbids); doubt fired on 2/1061. **DEBUG:** a silent moderngl `u1`(=RGBA8**UI**) vs `f1`(=RGBA8) format mismatch made the first full run return uninitialized memory as plausible detections (0.35/0.31/0.05) — now guarded by a construction-time `MegaShader._selftest()`. **GOP measured at 4.167 s (1061 keyframes), ~half the epic's GOP-2s/2400 assumption.** Dev-Notes staleness noted: the 9.15 salvage landed, so the fragment source-of-truth contract is **no longer broken**. AC13b honoured (shader ignores the dead 3×5 `roi`); both data defects reported, neither fixed. Nothing committed. epic-12 stays `in-progress`. |
| 2026-07-16 | Story created via `/bmad-create-story` (Stephane; claude-opus-4-8[1m]). `backlog → ready-for-dev`; epic-12 `backlog → in-progress` (first story). AC0 (4 kickoff decisions) + AC1–AC20 + 10 Tasks + Dev Notes. Three live-tree findings recorded that invalidate parts of the epic brief (existing FFmpeg extractor; the `.bak` is not newer data; degenerate scoring math). Dependency on 9.15 reassessed against disk state — 12.1 is unblocked. |

## Dev Agent Record

### Agent Model Used

`claude-opus-4-8[1m]` (Amelia, `/bmad-dev-story`), 2026-07-16.

### AC0 — Kickoff decisions (resolved before Task 1)

| AC | Verdict | Rationale |
|---|---|---|
| **AC0a — Decoder binding** | **Option A — reuse `utils/video.py`** (Stephane, confirmed) | Zero new pip deps beyond `moderngl`; the module already implements Volet A's decode spec verbatim (Finding 1). Both in-story fixes applied: `-vsync 0` → `-fps_mode passthrough`, and a new native-resolution variant `extract_iframes_native()`. |
| **AC0b — Bench input + `.bak`** | **Option A — bench `map_config.v2.json`; leave the `.bak` byte-untouched** | Story 12.1 is read-only w.r.t. zone data. The `.bak` was not read, moved, or restored. **Dev-Notes correction:** the fragment source-of-truth contract is **no longer broken** — the 9.15 salvage landed (`e4b9c29`, `be0292b`, `1ba0f96`), so all four fragments + `manifest.json` now exist on disk and `tests/test_zone_fragments_v2.py` (+4) guards them. That Dev Note is stale in 12.1's favour. |
| **AC0c — LUT packing** | **Option A — pre-resolved OpenCV integer bounds** | 12 slots for 12 values; reproduces `band_inrange_ratio`'s three branches 1:1. Parity comes from *not* re-deriving the band on the GPU. The symmetric circular-distance form stays rejected. |
| **AC0d — Tool name + number** | **Tool 12 — `apps/tooling/tools/keyframe_engine_bench/`** | Package form per the epic's `tools/<name>/`; `zone_picker/` precedent. |
| **AC6 gate tooling** (not an AC0 item; needed a call) | **Download the Khronos prebuilt glslang** (Stephane, confirmed) | Not on PATH, not pip-installable. Used out-of-tree via `$GLSLANG_VALIDATOR`; **not vendored** (AC18). |

### Debug Log References

**Pre-flight (Task 1).** pytest baseline **208** (matches AC16's amended figure, not the stale 204 in Task 1's text). Python 3.11.15, FFmpeg 8.0.1, config = **134 rules** (10 hud + 3 in_match + 121 map), corpus 2666 PNGs / 16 classes, 4 V2 captures. GL: Intel UHD 770, GL 3.3.0, `GL_ARB_ES3_compatibility` present.

**GOP — the epic's assumption was wrong (Task 1).** Measured, not inherited: **GOP = 4.167 s**, 72 keyframes / 300 s, **1061 keyframes** for the full capture — roughly **half** the epic's GOP-2s / 2400-keyframe assumption. Since decode dominates, this halves the dominant cost.

**🔴 The bug that cost a full accuracy run — moderngl `u1` vs `f1`.** First full accuracy run returned 0.35 / 0.31 / 0.05 with 101 disagreements over 48 frames. Root cause: **moderngl's `dtype='u1'` spells `GL_RGBA8UI` (an *integer* texture), not normalized `GL_RGBA8` (which is `dtype='f1'`)**. The frame texture was an integer texture read through a `sampler2D`, and the render target was an integer attachment receiving a `vec4`. **Neither raised** — the readback returned uninitialized memory that looked like plausible detections. Localized by noticing the readback held values of 100 and 1 when `step()` can only emit 0 or 255, then bisecting to a constant-red shader (still garbage) and finally to `fbo.read()` raising `GL_INVALID_OPERATION` while `tex.read()` returned correct pixels. Fixed to `f1` on both. `MegaShader._selftest()` now asserts the clear/read round-trip at construction so this class of silent GL failure can never pass unnoticed again.

**🔴 AC6's prescribed gate command is unusable.** `glslangValidator -G -S frag` **rejects `#version 300 es` outright** ("ES shaders for SPIR-V require version 310 or higher") — `-G` requests SPIR-V-for-OpenGL codegen, so the literal command *structurally cannot* validate the ES 3.00 dialect E2 mandates. Gate runs **without `-G`** (glslang's GLSL/ESSL front-end — the part that enforces the subset). Verified the gate is real: it **rejects `float x = 1;` under `300 es` and accepts it under `330 core`**, i.e. it catches the #1 silent killer that the `-G` form could not even reach.

**Integer HSV — a deliberate deviation from the Dev Notes, brute-forced first.** Dev Notes prescribe Sam Hocevar's float `rgb2hsv`. Rejected: cv2's HSV are *integers* from fixed-point math, and `cv2.inRange` tests **integer bounds inclusively**, so a float hue at 19.9997 instead of 20 flips a rule — and 31 of 134 rules have bands asymmetric about their center. Ported OpenCV's integer `RGB2HSV_b` into GLSL instead, after brute-forcing a numpy model against `cv2.cvtColor(BGR2HSV)` over **all 2^24 RGB inputs: 0 mismatches on H/S/V**. That sweep also independently confirmed `/180` (**max H = 179; 180 unattainable**). Payoff: exact per-frame parity (below).

**The "latent bug" at `video_test.py:606-614` is NOT a bug.** The observation (`falling_ts = ts` before `(ts - falling_ts) >= dur`, so the expression is always `0 >= dur`) is accurate; the conclusion is not. On the falling-edge frame, elapsed time **is zero by definition**, so `0 >= dur` correctly evaluates "is the score window already over?" — zero score frames when `dur == 0`, falling-edge frame first in `score_screen` when `dur > 0`. Exactly the documented intent. Ported as intent with the zero explicit; Tool 11 untouched. **No divergence from 9.13 exists to report.**

### Completion Notes List

**Both AC11 deliverables landed. The pivot's premise is confirmed; its implicit corollary is not.**

1. **Accuracy — EXACT parity (AC11/AC12/AC13).** AC12's baseline was re-run unmodified first and **reproduced the pinned numbers exactly** (hud 0.9805 / in_match 1.0000 / map_id 1.0000) → `output/roi_detection_tests/v2/2026-07-16T230122/`, pinned as *the* baseline. The GPU then matched **all three numbers identically**, and per-frame against Tool 9's own `frame_predictions.csv`: **0 disagreements over 2666 frames**. Phrased throughout as an in-sample **parity target**, never as accuracy-in-the-world (REL-006's floor is 9.9b's job, not 12.1's).
2b. **🔴 CORRECTION (post-review question from Stephane: "isn't there a better way to avoid transferring too much data and use non-blocking calls?"). The run output's upload/shader split was MISATTRIBUTED, and the Android upside was UNDER-reported.** GL uploads are **asynchronous** — the timer around `upload()` stops before the transfer lands, and the blocking `draw_and_read()` absorbs the tail. The **total (2.88 ms) was always correct**; the split was not. Added **`--profile-gpu`** (forces completion per stage, median of 200) to make the true shape reproducible: **upload 2.34–2.46 ms (~91%) / shader 0.15–0.22 ms (~8%) / readback stall 0.004–0.073 ms (<1%, in the noise)**. Two consequences: **(i) non-blocking readback is NOT worth building** — the stall is ≲0.07 ms/frame (~0.5% of wall), and the readback direction carries only **600 bytes**; the 6.2 MB goes the *other* way. The story's Dev Note (*"PBO ping-pong is premature at 600 bytes — build synchronous, measure first"*) is **confirmed by measurement**. **(ii) The zero-copy upside is ~7×, not the ~1.4× first reported** — the GPU's real cost is **~0.24 ms**, not 3.25 ms, so removing the upload gives **0.24 vs the CPU's 1.667 ms**. **This is the most decision-relevant number in the story for 12.3:** the GPU engine is not marginal on Android, it is excellent — but the *entire* case rests on zero-copy, and §6's colour bind is that the bit-parity mitigation (Y/U/V as R8 textures) **gives up that very path**. Ceiling unchanged though: even with upload and stall at zero, wall goes 14.41 → ~11.8 ms/kf because decode (8.86 ms) would then be ~75% of what remains. `REPORT.md` §3's two affected rows are **flagged in place, not silently rewritten** — they are what naive wall-clock instrumentation reports, and 12.2 will instrument the same way on device. pytest 261 → **262**.

2. **🔴 Timing — decode-bound CONFIRMED, but the GPU LOSES at rule evaluation.** Full capture, 1061 keyframes: decode **8.862 ms/kf (62%)**, upload 1.705, shader+readback 1.177, wall **14.411 ms/kf** (15.29 s). **Decode is 3.08× the entire GPU cost** — the pivot's thesis holds. But engine-vs-engine with decode excluded from both: **CPU 1.667 ms/frame vs GPU 3.253 ms/frame = 0.51× — the CPU is ~2× faster.** Structural, not tuning-fixable on PC: the rects are 1–25 px (~800 texel fetches/frame — the SCP's 60k is ~100× pessimistic), yet the GPU must upload the whole **6.2 MB** frame to reach them; upload alone (1.705 ms) already exceeds the CPU's entire rule-eval budget. The Dev Notes' 0.647 ms/frame was measured **@ 640×360**, where upload is ~9× smaller; AC5 mandates 1080. **This does not settle Android** — MediaCodec's zero-copy `samplerExternalOES` removes the upload (leaving ~1.4×), so the whole architectural case for the GPU rests on a path only 12.2 can measure. Flagged for 12.3, including the third option the evidence permits: since both engines are decode-bound and CPU rule-eval is already 1.67 ms/frame, the measured evidence **does not currently require a GPU engine at all**. Verdict is 12.3's; 12.1 reports.
3. **AC8/AC10 — doubt designed, implemented, and stated.** Confirmed in code that there is **no upstream `unknown` to inherit** on the phase axis (the in_match classifier is hard-binary). Mechanism: split-vote detection (unanimous = confident, split = doubt; `--doubt-margin 0` reproduces 9.13), never forced to the nearest class, resolved by holding the machine so surrounding reliable context (the confidently-armed score-screen timer, which keeps running underneath) gives the doubtful stretch its meaning. One forward pass, no window, no lookahead. **AC10 verdict: the enum is EXTENDED** with `doubt` + a sibling `confidence` field — remapping to `not_in_match` is exactly the forcing E4 forbids. Measured: doubt fired on **2 of 1061** keyframes.
4. **AC13b honoured — the shader ignores `minimap_identification.roi`.** Zone rects evaluated as absolute reference-res coords against the full 1920×1080 frame. Both data defects (`roi` = 3×5 box byte-identical to `atlantis_z10`; `id` = `"test"`) reported as known defects with zero runtime effect today. **Neither fixed** (AC18-fenced, 9.9b's).
5. **AC13 — all three per-classifier formulas reproduced** exactly (HUD normalized / in_match normalized-then-binary / map-ID raw unnormalized). Divergence from Tools 10/11 documented, not reconciled. Live confirmation of Finding 3's degenerate scoring: observed `map_id_confidence` of **17.0** against a 0.6 threshold.
6. **AC15 — deps recorded.** `moderngl>=5.12,<6` added to **both** manifests; the pre-existing `jsonschema` gap in `requirements.txt` fixed as the AC directs. FFmpeg lands in no manifest (system-PATH dep, Finding 1). `uv.lock` updated as a consequence.
7. **Gates.** pytest **208 → 262** (+54; the `+53`/`261` figures elsewhere in this record predate item 2b's added test — see the correction at the end of 2b), **0 regressions**; `uv run pytest` and `pnpm --filter tooling test` parity confirmed. GLSL gate green on all four variants. Tool 12 registered at all five `wardentooling.py` points — including AC17's first-of-its-kind `-m` package + positional-video layout (video at `last_args` index **2**, not 1); `run_tool` needed no change. **↻ Post-review (2026-07-19): 262 → 305 (+43 review-hardening tests).**

**AC19/AC20 + Task 10 HELD** — commit / `--no-ff` merge / `review → done` flip are post-merge admin per [[feedback_two_pr_docs_execution]] + [[feedback_ac_checkbox_tighten]]. Nothing was committed.

**Not done, by design:** did not re-open Story 1.1, publish the spike report (12.3), re-arm the ladder (12.3), re-point Tool 9 (9.16), or touch zone data / schema / Tools 9-11 / the emitter.

### File List

**New**

- `apps/tooling/tools/keyframe_engine_bench/__init__.py`
- `apps/tooling/tools/keyframe_engine_bench/__main__.py`
- `apps/tooling/tools/keyframe_engine_bench/lut.py`
- `apps/tooling/tools/keyframe_engine_bench/frames.py`
- `apps/tooling/tools/keyframe_engine_bench/phases.py`
- `apps/tooling/tools/keyframe_engine_bench/scoring.py`
- `apps/tooling/tools/keyframe_engine_bench/shader.py`
- `apps/tooling/tools/keyframe_engine_bench/keyframe_engine_bench.frag`
- `apps/tooling/tools/keyframe_engine_bench/REPORT.md` — the AC11 measured report (feeds 12.3)
- `apps/tooling/tests/test_keyframe_engine_bench.py` (+54 tests; **+97 after the 2026-07-19 review pass**)

**Modified**

- `apps/tooling/utils/video.py` — AC0a: `-vsync 0` → `-fps_mode passthrough`; `extract_iframes_scaled` refactored onto a shared `_extract_iframes` + new `extract_iframes_native` (AC5). Public signature/behaviour of `extract_iframes_scaled` unchanged.
- `apps/tooling/pyproject.toml` — + `moderngl>=5.12,<6`
- `apps/tooling/requirements.txt` — + `moderngl>=5.12,<6`, + `jsonschema>=4.23.0` (pre-existing gap)
- `apps/tooling/wardentooling.py` — Tool 12 registration (flow / `_TOOL_MAP` / `choices_main` / `menu_main` / `_reprompt_source`)
- `uv.lock` — lockfile consequence of the `moderngl` manifest change

**Generated (gitignored, not deliverable source)**

- `apps/tooling/output/roi_detection_tests/v2/2026-07-16T230122/` — the pinned AC12 baseline
- `apps/tooling/output/keyframe_engine_bench/accuracy.json`
- `apps/tooling/output/2026-04-27 22-05-34/{results.json, bench.json, 55 thumbnails}`

### Review Findings
