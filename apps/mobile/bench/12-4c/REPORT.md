# Story 12.4c — engine wiring + TS consumer rewrite: the evidence

**No device was involved in anything below.** Everything here runs on the PC, and that is stated up
front because the one thing this story cannot close on its own is MediaCodec. The device half —
`analyzeSession` on the reference Poco X5 Pro, compared against this oracle — belongs to the
**epic-end device pass** ([[feedback_batch_manual_checks_epic_end]]), like 12.4a's and 12.4b's
re-runs before it.

Fixtures: `videos/V2/2026-04-27 22-05-34.mp4` (1920×1080 h264 `yuv420p` `color_range=tv` `bt709`,
1061 keyframes, GOP 4.167 s) and `apps/tooling/output/map_configs/map_config.v2.json`
(134 rules: 10 hud_version + 3 in_match + 121 map zones over 13 maps).

---

## 1. What was missing, and what this builds

Story 12.4b proved the fire bits twice and **neither proof covers the video path independently**:

| proof | corpus | reference | why it is not enough |
|---|---|---|---|
| AC3(A) — 0 / 357,244 | 2666 PNGs | `pc_reference_fires.json` | PNGs read with `cv2.imread`. **Never touches the YUV converter.** |
| AC3(B) — 0 / 142,174 | the real capture | the device's own GPU arm | The reference was the *other device arm* — since deleted, and found defective in the same run. |

So AC10 asked for an **independent PC-side video oracle**. It exists now:

```
FFmpeg (-skip_frame nokey)  ->  numpy BT.709 limited-range + NEAREST chroma  ->  cv2 inRange
   a different H.264 decoder     the model pinned by REFERENCE_YUV_SWEEP_SHA256    Tool 9's own
                                                                            zone_fires_on_frame
                              ->  Tool 12's scoring.py / phases.py  ->  timeline + spans + matches
```

`apps/mobile/bench/12-4c/video_oracle.py`. **Nothing in that chain is our Kotlin or our
TypeScript.** The colour half is self-checking: the script builds the whole 2^24 (Y, Cb, Cr) LUT and
refuses to run unless its SHA-256 equals `REFERENCE_YUV_SWEEP_SHA256` — the same digest the device
re-derives in `colorConstantsCheck()`. An oracle whose colour model had drifted would otherwise
report disagreements that were its own.

Output: `video_oracle_fires.json` — 1061 keyframes, 76.8 s wall.

---

## 2. 🔴 The shipped Kotlin evaluator vs the oracle: **0 / 142,174**, off device

`jvm_engine_check/` compiles **`WardenRulePacker` + `WardenColorConvert` + `WardenCpuBaseline`
verbatim from `plugins/kotlin/`** (none of them import anything from Android but `org.json`) and
runs them on a desktop JVM over the same FFmpeg planes the oracle used.

| | |
|---|---|
| keyframes | **1061** (the full capture) |
| rules | 134 |
| rule-frame decisions | **142,174** |
| frames with any disagreement | **0** |
| **total disagreements** | **0** |

Artifact: `jvm_engine_check/jvm_engine_check_result.json`.

**What this closes:** the packer's band resolution (including the banker's rounding, the 9
wrap-branch rules and the 68 full-circle `h_tol = 180` rules), the BT.709 limited-range +
nearest-chroma conversion and the integer rule evaluator — against an implementation that shares no
line of code with them, on real video, not on PNGs.

**What it does NOT close, stated so nobody reads it as more than it is:** MediaCodec. These planes
are FFmpeg's, with I420 strides; the device hands back NV12 with `pixelStride = 2` and its own
`rowStride`. They are fed through the same `WardenYuvFrame` stride arithmetic, so the arithmetic is
exercised — but the decoder is not. That is the epic-end run:

```bash
# on the device, once the app can be flashed
adb pull .../analyzeSession_dump.json apps/mobile/bench/12-4c/device_analyze_session.json
cd apps/tooling && uv run python ../mobile/bench/12-4c/video_oracle.py compare \
    --device ../mobile/bench/12-4c/device_analyze_session.json
```

The comparator is written and tested against the oracle's own shape; it refuses to compare at all if
the device's `refs` order differs from the oracle's, because that is the failure 12.2 lost a full
parity run to.

---

## 3. The TS port vs Tool 12: 1061 keyframes, exact

`src/features/video-processing/__tests__/fixtures/tool12-parity.json` (448 kB, generated, committed)
holds Tool 12's own output — `scoring.py` and `phases.py` called directly by the generator, never
hand-computed — and `tool12Parity.test.ts` runs the TypeScript port against it:

* **the three formulas**, on a config whose three classifiers cannot be confused for one another;
* **the `weight = 1.0` degeneracy** reproduced as-is, plus non-unit weights proving the map-ID sum is
  RAW and weight-aware (`1 × 0.5 < 0.6` → unknown; `2 × 0.5 = 1.0` → fires);
* **empty detection arrays** short-circuiting to `unknown` instead of crashing;
* **doubt**: detected at the split vote, emitted as `doubt`, and **HOLDING** — with the
  counterfactual asserted too (cutting spans from the emitted states shreds one match into three);
* **the real capture**: all 1061 keyframes, every classifier verdict, the whole phase timeline, all
  18 spans and all 18 map labels.

Confidences are compared at 1e-12. They were first written to the fixture rounded to 9 decimals,
which quietly capped the assertion at ~1e-9 — looser than the thing being checked. `fires / n_im` is
the same IEEE-754 double in Python and JavaScript, so the fixture now carries full precision.

**Band coverage is asserted, not hoped for:** the capture exercises **all 9 wrap rules** and **54 of
the 68 full-circle rules** in BOTH directions (fired somewhere, cleared somewhere). Without that the
device comparison in §2 could have been vacuous.

---

## 4. 🔴 A real finding: `the_rock` fragments into 11 spans

The oracle's timeline over the capture:

```
artefact   12.5 s – 429.2 s      atlantis  520.8 – 1025.0     helios   1116.7 – 1537.5
engine   1616.7 – 2066.7         horizon  2162.5 – 2420.8     the_cliff 2520.8 – 2845.8
silva    2925.0 – 3325.0         coliseum 4141.7 – 4383.3
the_rock 3620.8 – 4054.2   ->  ELEVEN spans of ~12 s each, separated by ~20 s gaps
```

18 spans for what looks like 9 matches. In the `the_rock` stretch the in_match score alternates
between **exactly 1.0 and exactly 0.0** on a ~50 s period — all three zones agreeing each time, so
these are CONFIDENT votes and **doubt-holding cannot help**: the machine sees a clean falling edge,
runs its 15 s score window, and reopens on the next rising edge.

**This is not the port.** The port reproduces Tool 12 exactly, and Tool 12 reproduces Tool 9. It is
the shipped **zone data** on that map/mode, and it is 9.9b's (zone population) and 9.16's
(re-pointing the accuracy instrument) to act on. Recorded in `deferred-work.md` rather than tuned
here: AC13 fences zone retuning out of this story, and "fix it while wiring it" is exactly how a
parity result stops meaning anything.

It also has a **product** consequence worth naming before Epic 5 builds on these rows: one match can
land in Card View as eleven segments.

---

## 5. What the engine now produces on HUD-2.0 footage

The point of the story, in one line: **every one of the 18 detected spans gets a map label. None is
`unknown`.** The v1 pHash path produced `unknown` on this footage — `epics-and-stories.md:2748`, the
hole this story closes.

Read it as an **in-sample parity result with no holdout**. It is NOT an accuracy number, it does NOT
touch REL-006 (which has no instrument at all until Story 9.16), and the three per-classifier
figures in the spike stay `[U]`.

Per-frame, over the capture: `hud_version` predicted `v2` on 996 of 1061 keyframes (mean confidence
0.85); `pred_map` was `unknown` on 205 (almost all outside matches); 2 keyframes were doubtful.

---

## 6. Reproduce

```bash
# the oracle (needs the capture; ~77 s)
cd apps/tooling
uv run python ../mobile/bench/12-4c/video_oracle.py oracle \
    --video "../../videos/V2/2026-04-27 22-05-34.mp4"

# the committed jest fixture (no video needed once the oracle JSON exists)
uv run python ../mobile/bench/12-4c/video_oracle.py fixture

# the shipped Kotlin, off device (~5 min; writes a 3.1 GB raw dump to build/, delete it after)
cd ../mobile/bench/12-4c/jvm_engine_check
bash run.sh "../../../../../videos/V2/2026-04-27 22-05-34.mp4" 0

# the TS port against Tool 12
cd ../../.. && npx jest src/features/video-processing/__tests__/tool12Parity.test.ts
```

Note for Git Bash on Windows: `run.sh` converts every path it hands to `java` with `cygpath -w`;
without that the JVM cannot resolve an MSYS path and reports a missing main class.
