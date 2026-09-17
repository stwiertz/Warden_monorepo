# Story 12.4a — decode-loop optimisation: the before and the after

**Device:** Poco X5 Pro 5G — `22101320G` / `redwood` / **SM7325** / Android **14** (SDK 34) /
Adreno 642L / `c2.qti.avc.decoder` (hardware). **Thermal `NONE` (not throttled) on every run
below**, including three back-to-back full-capture runs.

**Fixture:** `videos/V2/2026-04-27 22-05-34.mp4` — 2.3 GB · 1920×1080 h264 `yuv420p` `bt709` ·
4419.633 s · GOP 4.1667 s · **1061 keyframes**.
**Config:** `apps/tooling/output/map_configs/map_config.v2.json` — 134 rules, packed LUT
sha256 `b8287e08…` (byte-identical to `lut.py`, verified in every run).

**Labels:** `[M]` measured · `[D]` derived from measurements · `[P]` projected.
Every figure below is `[M]` unless marked otherwise.

---

## 0. The headline

| | baseline `[M]` | after `[M]` | |
|---|---|---|---|
| **bound decode loop, ms/keyframe** | **41.982** | **7.706** | **5.45× faster** |
| per-keyframe `flush()` calls | 1061 | **0** | removed |
| `END_OF_STREAM` round-trips | 1061 | **1** | once per run |
| `TIMEOUT_US` | 10 000 µs | **1 000 µs** | |
| keyframes decoded / asserted | 1061 / 1061 | 1061 / 1061 | AC4 |
| PTS mismatches | n/a | **0** | AC5 |

`[D]` Over 1061 keyframes that is **44.54 s → 8.18 s, a saving of ~36.4 s** on the decode loop
alone. End to end over the same capture, the bound BIT_PARITY path went **45 253.9 ms →
10 592.2 ms (median of 3) = 4.27×**. The story projected `[P]` 17.1 ms/kf (~2.5×); the measured result is **better than the
projection by more than a factor of two**, because the projection assumed the flush and the
timeout were two independent subtractions from a fixed 42.2 ms wall, and they are not —
removing the per-keyframe EOS removes the thing the timeout was delaying as well.

> **This is a decode-loop number, NOT a PERF-002 re-baseline.** PERF-002 end-to-end belongs to
> **Story 12.4d** (12.4a's AC9 fences it out explicitly). Section 3 reports the full-capture
> wall because AC4 and AC5 need a full-capture run, not to re-baseline anything.

---

## 1. Baseline — re-measured today, not inherited

The APK was rebuilt and reinstalled from the current tree **before** the baseline was taken, so
the "before" provably comes from the tree that was then modified. Three `flushprobe` runs,
100 keyframes each.

| metric | 12.2 banked (median of 3) | today, run 1 / 2 / 3 | today median |
|---|---|---|---|
| `wall_ms_per_keyframe` | 42.204 | 42.970 / 41.809 / 41.982 | **41.982** |
| `flush_ms_median` | 14.554 | 14.333 / 14.114 / 14.075 | **14.114** |
| `seek_ms_median` | 4.364 | 5.127 / 4.347 / 4.386 | **4.386** |
| `queue_to_first_output_ms_median` | 21.886 | 21.891 / 21.821 / 22.059 | **21.891** |
| `try_again_per_keyframe` | 1.02 | 1.03 / 1.03 / 1.02 | **1.03** |
| `try_again_ms_per_keyframe` | 10.612 | 10.697 / 10.707 / 10.603 | **10.697** |
| `idle_flush_ms_median` | 1.821–3.555 | 3.606 / 3.594 / 3.578 | **3.594** |

Every figure reproduces inside 12.2's documented spread. **The baseline is sound and the
decomposition it rests on is confirmed a second time, by a second person, three months on.**

Artifacts: `baseline_flushprobe_run{1,2,3}.json`.

---

## 2. AC1 — the timeout, and a correction to the reason it was expensive

`TIMEOUT_US` 10 000 → 1 000 µs. `decode_probe` keeps the **old structure** (seek → `flush()` →
queue → EOS → drain) so this is a clean A/B on the constant alone.

| `decode_probe` metric | before | after | Δ |
|---|---|---|---|
| `wall_ms_per_keyframe` | 41.982 | **33.442** | **−8.540** |
| `queue_to_first_output_ms_median` | 21.891 | **13.389** | **−8.502** |
| `try_again_per_keyframe` | 1.03 | 7.39 | +6.36 |
| `try_again_ms_per_keyframe` | 10.697 | **9.772** | **−0.925** |
| `flush_ms_median` | 14.114 | 14.077 | untouched, as expected |

### 🔴 AC1's stated success criterion does not hold. Its purpose is exceeded. Both are true.

AC1 asked for "`INFO_TRY_AGAIN_LATER` sleep time per keyframe drops materially from the
baseline 10.6 ms". **It did not: 10.697 → 9.772, a 0.9 ms move against a 10.6 ms claim.** Reporting a −8.5 ms/kf win against that
criterion without saying so would be reporting the wrong mechanism, and the next reader would
optimise the wrong thing.

**What the 10.6 ms actually was.** Not a decoder that is slow to answer. In the EOS-terminated
loop the sequence is: queue the IDR → poll output → `INFO_TRY_AGAIN_LATER` → **sleep a whole
timeout** → come back round and queue the `END_OF_STREAM`. Trap 2 says a single queued sample
decodes to nothing, so the decoder is *waiting for that EOS the entire time*. The sleep was not
waiting on hardware — **it was withholding the input the hardware needed.**

**Why the counter barely moved anyway.** At 1 ms we poll ~7× where we polled ~1×, so the time
accumulated *in try-again calls* is roughly the decoder's real latency either way. The −8.5 ms
comes from the **blocking** `dequeueInputBuffer` / `dequeueOutputBuffer` calls getting 10×
finer granularity, and lands in `queue_to_first_output` (−8.502), which is exactly where a
withheld-EOS effect should land.

**`[D]`** Real post-EOS decode latency is therefore ~3.5 ms, not the ~11.3 ms the baseline's
`queue_to_first_output` minus try-again suggested — the difference was timeout quantisation on
both ends.

### The wedge guard (AC0b)

Caps are now declared as durations and converted to polls, so they no longer derive silently
from the timeout:

| guard | before | after | wedge cap |
|---|---|---|---|
| `MAX_SPINS` | `500` @ 10 ms | `5000` @ 1 ms | **5 s — unchanged** |
| `MAX_SPINS_BEFORE_EOS` | `2000` @ 10 ms | `20000` @ 1 ms | **20 s — unchanged** |

---

## 3. AC0a / AC2 — the flush, and the depth sweep that chose *k*

`pipelineProbe` runs the flush-free loop at five depths over the same 100 keyframes in a single
run, so the comparison carries no run-to-run spread. Three runs, median.

| *k* | wall ms/kf (median) | per-run | decoded | PTS mismatches |
|---|---|---|---|---|
| **1** | **WEDGED — no output, all 3 runs** | — | 0 | — |
| 2 | 20.909 | 20.81 / 20.91 / 23.15 | 100/100 | 0 |
| **4** | **8.062** | 8.07 / 8.06 / 6.70 | 100/100 | 0 |
| **8** ← chosen | **7.706** | 7.71 / 7.79 / 6.94 | 100/100 | 0 |
| 16 | 7.725 | 7.80 / 7.72 / 6.50 | 100/100 | 0 |

**`k = 1` wedging is the most informative row in this report.** One IDR in flight with no EOS
produces no output at all — trap 2, reproduced directly, three times out of three. It is why
the tail still queues exactly one `END_OF_STREAM` per **run**: the flush was removable, the
drain was not.

**Why 8.** The knee is at 4 (20.9 → 8.06, then flat). 8 sits on the plateau with margin above
the knee, so a device whose reorder depth is deeper than this one's does not fall back toward
the k=2 cliff. 16 buys nothing measurable (7.725 vs 7.706) for twice the in-flight state. **4 would work
today; 8 is the same speed with headroom.**

**What the loop costs now.** At k=8, `seekTo` is **~4.5 of the 7.7 ms/kf — ~58% of the loop**.
The decode loop's remaining cost is now dominated by the one stage this story's own table
marked "not yours". **Not investigated and not claimed reducible** — logged in
`deferred-work.md` so the next reader starts from the measurement, not the old 10% framing.

---

## 4. AC4 / AC5 — proving the pixels did not move

Three back-to-back full-capture runs on the shipped binary, 1061 keyframes each, both colour
paths. **Thermal `NONE` on all three** — the speedup is not a cold-run artefact.

| | before (12.2) | run 1 | run 2 | run 3 | after median | |
|---|---|---|---|---|---|---|
| **BIT_PARITY — the BOUND path** | 45 253.9 ms | 10 022.9 | 10 627.2 | 10 592.2 | **10 592.2** | **4.27×** |
| ZERO_COPY — legacy loop, Path Z | 35 435.7 ms | 23 460.6 | 25 568.4 | 24 817.9 | **24 817.9** | 1.43× |

**ZERO_COPY improving at all is the cleanest confirmation that AC1 and AC2 are separable.**
That path still runs the per-keyframe `flush()` (§3's carve-out) and gains only the timeout
fix — 1.43×. The bound path gains both — 4.27×.

### AC4 — the count assertion

| run | `n_keyframes_decoded` | `keyframe_count_expected` | matches |
|---|---|---|---|
| 1 / 2 / 3, BIT_PARITY | **1061** | **1061** | ✅ |
| 1 / 2 / 3, ZERO_COPY | **1061** | **1061** | ✅ |

The expectation is still the **independent sample-table walk**, not the seek-built list, and
the two still agree (`counts_agree` true, 1061 = 1061). Actual numbers, not "assertion passed".

### AC5 — and why the parity run AC5 names cannot do this job

🔴 **`pc_reference.py compare` runs the LABELED PNG CORPUS through `DIRECT_RGB`.** It never
opens the video and never calls `decodeKeyframesBySeek`. It is a real check — it proves the
engine, the packed LUT and the colour conversion are untouched — **but it is structurally
incapable of detecting the defect AC5 is afraid of**, which is a decoded frame delivered under
the wrong timestamp. Running it and calling it the tripwire would have looked like evidence and
been none. That is the same mistake 12.2's `seektest` made, corrected in its own deferred-work
entry; it is not repeated here.

**So the tripwire was built.** `timing_fires_bit_parity_seek_1061.json` holds one row per
decoded keyframe — `{pts_us, fires}`, a 134-bit rule mask evaluated on that keyframe's **pixels**
and keyed by the PTS **the decoder reported**. 12.2's copy was pulled off the device before the
first new run could overwrite it, and each new run diffed against it:

| run | rows | shared PTS | changed masks | duplicate PTS | missing | extra | order identical | decisions |
|---|---|---|---|---|---|---|---|---|
| 1 | 1061 | 1061 | **0** | 0 | 0 | 0 | ✅ | 142 174 |
| 2 | 1061 | 1061 | **0** | 0 | 0 | 0 | ✅ | 142 174 |
| 3 | 1061 | 1061 | **0** | 0 | 0 | 0 | ✅ | 142 174 |

**426 522 rule-frame decisions across three runs, 0 disagreements.** The pipelined loop returns
**bit-identical pixels for identical timestamps**, delivers each keyframe exactly once, and —
though the code does not rely on it — happens to deliver them in the same order as before.

Artifacts: `fire_row_comparison_run{1,2,3}.json`, `AFTER_timing_fires_run{1,2,3}.json`,
`BEFORE_timing_fires_bit_parity_seek_1061.json`, `compare_fire_rows.py`.

**And the parity run AC5 names was run too, because "it cannot see this defect" is not a reason
to skip it.** Fresh `parity` mode run, then `pc_reference.py compare` against the pinned
`pc_reference_fires.json`:

| | value |
|---|---|
| `frames_compared` / `reference_frames` / `device_frames` | 2666 / 2666 / 2666 |
| `frame_sets_identical` | ✅ true |
| `frames_with_disagreement` | **0** |
| `total_rule_disagreements` | **0** |
| `rule_frame_decisions` | **357 244** |

The device's raw `parity_fires.json` is **byte-identical to 12.2's** (sha256
`0348662e95f444d3…` both), which is the strongest available statement that the engine, the
packed LUT and the colour conversion were not touched by this story.

⚠️ `pc_reference.py compare` **writes `parity_comparison.json` into `bench/12-2/`** and did
overwrite that banked artifact. It was restored with `git checkout`; this run's copy is kept here
as `AFTER_parity_comparison.json`. That copy also carries `ac14_classifier_accuracy`, which the
committed 12.2 artifact does not — closing a 12.2 deferred item that was waiting on "the next
device pass" (device: hud_version **0.9805**, in_match **1.000**, map_id **1.000**; an IN-SAMPLE
parity-corpus figure, **not** accuracy-in-the-world).

### AC6 — strategy A is still the one that wins

Re-measured head to head on the same 60 frames in run 1: **A (absolute seek per keyframe)
1304.3 ms vs A′ (single-pass sync-filtered demux) 4160.0 ms — A is 3.2× faster.** A′ still has
no flush and no per-keyframe EOS and still loses, for the reason §0 of the decoder now states
inline: `advance()` reads sample data, so A′ drags 2.3 GB through the extractor.

---

## 5. Reproducing this

```sh
# build + install (the plugin emits native sources at prebuild)
pnpm --filter mobile exec expo prebuild --platform android
cd apps/mobile/android && ./gradlew :app:assembleDebug
adb install -r -d app/build/outputs/apk/debug/app-debug.apk

# fixtures are staged exactly as 12.2 staged them — see bench/12-2/REPORT.md §10
DEST=/sdcard/Android/data/team.warden.mobile/files/warden12_2

# flushprobe carries decode_probe (AC1) + idle_flush_probe + ac0a_pipeline_depth_sweep
adb shell am start -n team.warden.mobile/.WardenEngineBenchActivity \
  --es mode flushprobe --es video $DEST/capture.mp4 --ei limit 0 --ei cpuFrames 400

# timing carries the full-capture count assertion (AC4) and the fire rows (AC5)
adb shell am start -n team.warden.mobile/.WardenEngineBenchActivity \
  --es mode timing --es video $DEST/capture.mp4 --ei limit 0 --ei cpuFrames 400

# AC5's decode-order tripwire
python apps/mobile/bench/12-4a/compare_fire_rows.py \
  apps/mobile/bench/12-4a/BEFORE_timing_fires_bit_parity_seek_1061.json \
  apps/mobile/bench/12-4a/AFTER_timing_fires_bit_parity_seek_1061.json
```

Each run logs `BENCH DONE` to logcat under tag `WardenBench` and writes
`report_<mode>.json` to `…/files/bench12_2/`.

---

## 6. Artifact index

| file | what it is |
|---|---|
| `baseline_flushprobe_run{1,2,3}.json` | the before, re-measured today on the current tree |
| `after_flushprobe_run{1,2,3}.json` | the after — `decode_probe` (AC1) + `ac0a_pipeline_depth_sweep` (AC0a/AC2) |
| `after_timing_run{1,2,3}.json` | the after, full capture, both colour paths (AC4, AC6) |
| `after_parity_run1.json` | the PNG-corpus parity run (AC5 as written) |
| `AFTER_timing_fires_run{1,2,3}.json` | the after's 1061 PTS-keyed rule-fire masks |
| `fire_row_comparison_run{1,2,3}.json` | **the AC5 decode-order tripwire results** |
| `AFTER_parity_fires.json` | device fire bits, byte-identical to 12.2's |
| `AFTER_parity_comparison.json` | 0 / 357 244 vs the PC reference, plus `ac14_classifier_accuracy` |
| `compare_fire_rows.py` | the comparator, and why the PNG parity run is not this |
| `REPORT.md` | this document |
| `BEFORE_report_timing.json` | 12.2's full-capture run, rescued off-device before it was overwritten |
| `BEFORE_timing_fires_bit_parity_seek_1061.json` | 12.2's 1061 fire masks — **AC5's "before"** |
| `BEFORE_parity_fires.json` / `BEFORE_report_parity.json` | 12.2's PNG-corpus parity run |

> The four `BEFORE_*` files were pulled off the device **before the first new run could overwrite
> them**. `bench/12-2/` tracks the reports but not these per-run dumps, so had they been left in
> place one `timing` run would have destroyed the only copy of AC5's baseline.
