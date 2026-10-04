# Story 12.4d — PERF-002 measured end to end, over the real pipeline

**Device:** Poco X5 Pro 5G — `22101320G` / `redwood` / **SM7325** / Android **14** (SDK 34) /
Adreno 642L / `c2.qti.avc.decoder`. **Fixture:** `videos/V2/2026-04-27 22-05-34.mp4` — 2.3 GB ·
1920×1080 h264 · **4419.633 s** (1 h 13 min 40 s) · **1061 keyframes** — pushed to the device as
`/sdcard/Download/warden-12-4d-capture.mp4` and imported through the app's document picker.
**Config:** the Metro-bundled `apps/mobile/assets/detection/map_config.v2.json` (sha256
`1d9f6b01…`, byte-identical to `apps/tooling/output/map_configs/map_config.v2.json`).
**Code:** `main` @ `d96b91e` (12.4c + its review patches) plus this story's `__DEV__` marks.
**Build:** debug APK, JS from Metro (`__DEV__ = true`), 2026-10-04.

**Labels:** `[M]` measured · `[D]` derived from measurements · `[P]` projected.
Every figure below is `[M]` unless marked otherwise, and resolves to `run{1,2,3}.json` in this
directory (the `perf002` record and the `thermal` block of each run).

---

## 0. The headline

> ### **PERF-002 end to end: 19.219 s = 0.435% of source duration — median of 3 runs, against a 220.98 s budget. MET by ~11.5× `[D]`.**

| run | end-to-end `total` | % of 4419.633 s `[D]` | thermal status (worst of all samples) | battery °C before → after |
|---|---|---|---|---|
| 1 | 20 662.6 ms | 0.468% | **0** | 28 → 28 |
| 2 | 19 218.5 ms | 0.435% | **0** | 29 → 29 |
| 3 | 18 844.5 ms | 0.426% | **0** | 29 → 30 |
| **median** | **19 218.5 ms** | **0.435%** | | |

Run-to-run spread 18.8–20.7 s (9.6%), inside the 13% the ffmpeg-kit control showed in 12.2. Run 1
was the first pipeline run after an app cold start and is the slowest on every native stage.

**Thermal, per run, sampled — not just at the start.** `capture_run.mjs` snapshots
`dumpsys thermalservice` before and after each run **and every 10 s during it** (7 / 10 / 4
samples). Thermal status was **0 (NONE) on every sample of every run**, and **no cooling device
reported a non-zero state** on any sample. (This device's HAL temperature block is empty, so the
cooling devices and battery temperature are the signals actually exposed.) The three runs span
~4 minutes back to back. **Recorded as a capability point, not a floor** — see PERF-010.

---

## 1. What is inside the number (AC0a, fixed before the first run)

**Clock:** `runPipeline()` entry → `updateSessionStatus(sessionId, "ready")` returned — the existing
`[PERF-002]` clock in `processingPipeline.ts`. **Inside:** session read, status writes, foreground
service start, FFprobe duration, the whole native `analyzeSession` (probe, **keyframe index**,
decode + CPU engine), TS scoring + phase resolution, MMKV checkpoints, SQLite segment rows, **18
thumbnail exports + their DB updates**, the final status write. **Outside:** the user's tap, the
document-picker copy of the 2.3 GB file into the app cache, session-row creation, app launch.

> 🔴 **The keyframe index is INSIDE this number. Story 12.2/12.3 reported it OUTSIDE, by
> construction. So 19.219 s is NOT comparable to 44.879 s.** The comparable figure is §3.

---

## 2. The decomposition (AC2) — the three never-measured stages now have numbers

Stage deltas between consecutive marks on the one clock, median of 3 `[D]`:

| stage | median | share of the run `[D]` | was |
|---|---|---|---|
| setup (session read, status, FGS start) | 223.0 ms | 1.2% | never measured |
| FFprobe duration | 280.2 ms | 1.5% | never measured |
| **native `analyzeSession`** (incl. JS↔native crossing) | **12 590.7 ms** | **65.5%** | |
| ↳ of which keyframe index (native `keyframe_index_ms`) | 3 023.8 ms | 15.7% | 2.290 s (12.2, outside the wall) |
| ↳ of which decode + engine (native `wall_ms − keyframe_index_ms`) | 9 526.8 ms | 49.6% | 44.879 s (12.3) |
| TS scoring + phase resolution (`buildSessionDetection`) | 147.2 ms | 0.8% | **never measured** |
| detection checkpoint writes (MMKV) | 5.6 ms | 0.03% | never measured |
| `buildMapSegments` | 0.9 ms | — | **never measured** |
| SQLite `deleteMapSegmentsForSession` + `insertMapSegments` | 87.1 ms | 0.5% | **never measured** |
| segmentation checkpoint writes | 0.8 ms | — | never measured |
| **thumbnail export — 18 segments** | **5 908.0 ms** | **30.7%** | **never measured** |
| ↳ of which FFmpeg `extractFrameAt` (summed) | 5 834.5 ms | | ≈ **324 ms per thumbnail** `[D]` |
| ↳ of which `updateResultFramePath` (summed) | 69.2 ms | | |
| final `ready` status write | 28.7 ms | 0.1% | never measured |

**🔴 The finding:** the stages 12.3 could only call "never measured" cost **~6.5 s together**, and
almost all of it is **one thing — thumbnail export, at ~324 ms per FFmpeg seek-and-encode**. It is
the second-largest cost in the pipeline, ~31% of the run, larger than the keyframe index and ~8×
the whole rule engine (0.650 ms/kf × 1061 = 0.690 s `[D]`). It is nowhere near threatening the
budget, so it is recorded as a finding, not a defect. Segmentation proper (TS timeline + segment
build + SQLite) is ~0.24 s.

---

## 3. The detection pass, comparable to 12.3 — and AC3 (did 12.4a's gain survive integration?)

The 12.2/12.3 boundary (detection pass, keyframe index outside) is reproduced exactly by the native
timing block: `wall_ms − keyframe_index_ms`.

| | figure | provenance |
|---|---|---|
| 12.3 published re-baseline (Path P, GPU, pre-12.4a) | 44.879 s = 1.015% | 12.2 `device_report_timing.json` `[M]` |
| 12.3's `[P]` for the bound configuration | ~42.0 s = 0.95% | `[P]`, never run |
| 12.3's `[P]` with the two decode-loop fixes | ~18.1 s = 0.41% | `[P]`, never run |
| 12.4a's bound loop, isolated (`timing` BIT_PARITY, median of 3) | 10.592 s | `bench/12-4a/REPORT.md` §0 `[M]` |
| **12.4d, in the real pipeline (median of 3)** | **9.527 s = 0.216%** | runs 1/2/3: 10 615.7 / 9 526.8 / 9 286.7 ms `[M]` |

Per keyframe, the native block reports `decode_excluding_engine` **7.767 ms/kf** and engine
**0.650 ms/kf** (medians). 12.4a's loop STRUCTURE was 7.706 ms/kf and its bound-loop decode stage
9.742 ms/kf; 12.4b's CPU engine was 0.651 ms/kf.

**AC3 verdict: the gain survived integration, intact.** The wired path decodes at the speed 12.4a
measured in isolation, and the detection pass is **4.7× faster than the published re-baseline
`[D]`** and **~1.9× better than the best projection 12.3 made `[D]`** (the projection assumed the
flush and the timeout were independent subtractions; 12.4a already showed they are not). The
remaining small gain over 12.4a's 10.592 s is consistent with 12.4b having removed the GL stages
from that path; it is not separately attributed.

**🔴 One figure moved the other way: the keyframe index.** 3.024 s median (2.918–3.086) against
12.2's 2.290 s — +32%. Same seek-built method (`syncSamplePtsListBySeek`); the file now sits behind
the document-picker copy in the app cache rather than in `getExternalFilesDir`. Not investigated;
recorded. It sits inside the end-to-end number either way.

---

## 4. The `< 10 s` aspiration — stated carefully

`< 10 s` is **not an acceptance criterion** (not in `prd.md`'s PERF-002; 12.2's AC15 says so).
On 12.2's own boundary — detection pass, index outside — the bound pipeline now lands at
**9.527 s**, under it. **End to end it does not: 19.219 s.** Both halves are stated; neither is
promoted. **And it is not a triumph of the engine:** rule evaluation is 0.69 s of a 19.2 s run
(3.6% `[D]`). What moved the number was the decode loop (12.4a: a per-keyframe flush and a dequeue
timeout we chose ourselves), and what dominates what is left is decode, the keyframe index and
thumbnail export.

---

## 5. Correctness on the device — the AC10 halves 12.4c left open

12.4c proved the shipped Kotlin against an independent PC oracle **on FFmpeg planes, off device**,
and said plainly that MediaCodec was not covered. Every run above also wrote the raw
`analyzeSession` result (`__DEV__`, after the clock stopped) and it was compared with
`bench/12-4c/video_oracle.py compare`:

| run | keyframes matched | rule-frame decisions | disagreements | artifact |
|---|---|---|---|---|
| 1 | 1061 / 1061 | 142 174 | **0** | `ac10_video_parity_run1.json` |
| 2 | 1061 / 1061 | 142 174 | **0** | `ac10_video_parity_run2.json` |
| 3 | 1061 / 1061 | 142 174 | **0** | `ac10_video_parity_run3.json` |

**MediaCodec → `WardenColorConvert` → `WardenCpuBaseline` on the reference device reproduces the
independent oracle exactly, on all three runs.** Every run resolved **18 spans, all 18 labelled,
none `unknown`** (`[PERF-009]` line in each run's `logcat`), `keyframe_count_matches: true`,
`covers_duration: true`, chroma layout `NV12`.

**PNG-corpus parity re-run (12.4b's carried item):** see §6.

**What this is not:** in-sample parity, not accuracy. **There is no holdout. REL-006 is not touched**
— it is 9.9b's, instrumented via 9.16. `the_rock` resolves into 11 of the 18 spans — **its R&D rounds, not a fragmentation defect** (§8).

---

## 6. PNG-corpus parity (12.4b's carried device re-run)

12.4b proved its CPU colour port on the PNG corpus **before** its own code review, and carried the
re-run against the post-review code to "the next device pass". This is it — `WardenEngineBenchActivity
--es mode parity --ei limit 0`, on the APK built from `d96b91e`, 2026-10-04:

| | result | artifact |
|---|---|---|
| frames compared | **2666 / 2666**, frame sets identical | `png_parity_comparison.json` |
| rule-frame decisions | **357 244** | 〃 |
| **disagreements vs the pinned PC reference** | **0** (0 frames) | 〃 |
| exhaustive 2²⁴ (Y, Cb, Cr) colour sweep | `matches_reference: true` (3.9 s) | `png_report_parity.json` → `ac2_color_constants` |
| packed LUT | sha256 `b8287e08…`, = `lut.py` | `png_report_parity.json` → `ac5_lut_cross_check` |
| CPU evaluator | 0.271 ms/frame | `png_report_parity.json` → `ac14a_parity` |
| thermal | `NONE` | `png_report_parity.json` → `ac1_device_profile` |

`pc_reference.py compare` writes into `bench/12-2/parity_comparison.json` by default (12.2's banked
baseline); the result was copied here and that file restored with `git checkout --`, as 12.4b did.

**12.4a's carried re-run (`flushprobe` + `timing` against its post-review code) was NOT re-run as a
probe.** The post-review bound loop is the one the three end-to-end runs above executed — 1061/1061
keyframes each, fire rows exactly equal to the independent oracle, decode-excluding-engine 7.767
ms/keyframe against 12.4a's 7.706 probe structure. That re-evidences the shipped loop directly,
which is what the item asked for; the probes measure instruments, not the shipped path.

---

## 7. How the runs were made — and the one thing that had to be bypassed

1. `expo prebuild --platform android` → `:app:assembleDebug` → `adb install -r -d`.
2. Metro: `EXPO_OFFLINE=1 npx expo start --offline` (the online dependency check failed), `adb reverse tcp:8081 tcp:8081`.
3. `adb push` the capture to `/sdcard/Download/`; import it through the app.
4. Per run: `node apps/mobile/bench/12-4d/capture_run.mjs <N>` (clears logcat, samples thermal
   every 10 s, archives the `[PERF-002] record=` line), then start the analysis in the app.
5. `adb exec-out run-as team.warden.mobile cat files/analyzeSession_dump.json > device_analyze_session_runN.json`,
   then `cd apps/tooling && uv run python ../mobile/bench/12-4c/video_oracle.py compare --device … --out …`.

**🔴 Processing could not be started on the device without a local, uncommitted bypass, and the
reason is a V1 finding, not a measurement artefact.** `useVideoProcessing` refuses to start while
`detection.offlineFirstLaunchBlocked` is set, and the bootstrap sets it whenever the **Story 7.4
`detection_config/latest` Firestore read fails with no cache**. That read failed with
`PERMISSION_DENIED`, and the user-facing copy said *"Initial setup requires internet"* on a
connected phone. Two facts make this more than a test-account problem:

- **`apps/web/firestore.rules` denies every path except `users/{uid}`** — so, if those are the
  deployed rules, `detection_config/latest` is unreadable for **every** user, subscribed or not.
- **The 12.4c pipeline does not consume that document at all** — detection runs on the bundled
  `map_config.v2.json`. The gate blocks processing on a config nothing reads.

For the runs, the gate was skipped locally under `__DEV__ && EXPO_PUBLIC_AUTH_BYPASS` (approved
by Stephane, 2026-10-04) and **reverted before commit**. The gate sits in the hook, **before**
`runProcessingPipeline` — outside the clock — so it cannot have changed any figure here. Logged in
`deferred-work.md` as a V1 blocker for the detection-config owners (1.13 / 1.14–1.16).

---

## 8. Against the human labels — in-sample, and stated as such

Parity (§5) proves the device computes what the PC reference computes. It does not prove that is
what happened in the video. `label_check.py` answers that for this capture: Tool 6's 2666 labeled
PNGs carry no source-video field, so each is matched **by pixels** (192×108 grey, mean abs diff ≤ 4)
to this capture's keyframe at its timestamp; **1027** belong to it. Each human label is then
compared with the oracle's per-keyframe output, which the device reproduces exactly.

| check | result | |
|---|---|---|
| map-labeled frame lands inside a detected match | **859 / 859** | 100% |
| …and that match carries the human's map | **859 / 859** | 100% |
| `lobby` frame not read as in-match | **99 / 99** | 100% |
| `transition` frame not read as in-match | **35 / 35** | 100% |
| `score` frame read as `score_screen` | **30 / 34** | 88.2% |

The 4 score misses: 2 on a `doubt` keyframe at the end of the `the_cliff` match, 2 read
`not_in_match`. None changes a match or a map label; they only move which frame the timing-derived
thumbnail lands on. Every one of the 18 detected matches contains human labels of its own map and no
other map (`label_check.json` → `match_label_votes`).

**🔴 IN-SAMPLE, NOT REL-006.** The rules were tuned on these same PNGs. This shows the shipped
detection reproduces the labels it was tuned against on this capture; it says nothing about unseen
footage. REL-006 (≥ 95% on a held-out set) stays 9.9b's, instrumented via 9.16.

**`the_rock` — 11 spans, and they are rounds.** Between 3620.8 s and 4054.2 s the detected states
alternate in-match → score-screen roughly every 50 s. Stephane confirmed (2026-10-04) that the_rock
is played in **R&D** — no respawn, several short rounds, a score screen after each — so the 11 spans
are its rounds, not one match cut into pieces. All 38 `the_rock` labels fall inside spans. This
**re-classifies** 12.4c's "fragments into 11 spans (zone data)" finding: not a zone defect, but a
product question for Epic 5 — group rounds into one match in Card View, or show them as rounds.
