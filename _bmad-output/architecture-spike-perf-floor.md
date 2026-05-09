# AR-SPIKE — Pre-PRD Performance Floor (Story 1.1)

**Status:** Binding-only cut (Session 2, 2026-05-09). Provisional rung verdict published. Final rung TBD post-Story-1.1.1 measurement.

**Branch:** `ar-spike-perf-floor`
**Story spec:** `_bmad-output/implementation-artifacts/1-1-pre-prd-performance-spike-ar-spike.md`
**Architecture parent section:** `_bmad-output/architecture.md` lines 832-868 (`#### Pre-PRD performance spike [SPIKE BOUND]`)
**Sprint Plan parent gate:** `_bmad-output/sprint-plan.md` §2 Gate G1 (lines 31-39)

This document is the binding deliverable per AC12 + AC16 G1 sign-off. Reviewers grep for the H2 sections below.

---

## Device profile

Connected device confirmed via `adb devices -l` on 2026-05-09:

| Field | Value | Source |
|---|---|---|
| Brand | `POCO` | `getprop ro.product.brand` |
| Model | `22101320G` | `getprop ro.product.model` |
| Codename | `redwood_eea` | `getprop ro.product.name` |
| Device | `redwood` | `getprop ro.product.device` |
| SoC manufacturer | `QTI` (Qualcomm Technologies) | `getprop ro.soc.manufacturer` |
| SoC model | `SM7325` (Snapdragon 778G — 1× Cortex-A78 @ 2.4 GHz + 3× Cortex-A78 @ 2.2 GHz + 4× Cortex-A55 @ 1.9 GHz, Adreno 642L GPU, 4 nm process) | `getprop ro.soc.model` |
| Android | `14` (SDK `34`) | `getprop ro.build.version.release` / `sdk` |
| Build | `OS2.0.14.0.UMSEUXM` | `getprop ro.build.fingerprint` |
| HyperOS | `V816` | `getprop ro.miui.ui.version.name` |
| Security patch | `2025-11-01` | `getprop ro.build.version.security_patch` |
| Screen | `1080×2400` @ density `440` (6.67" panel) | `wm size` / `wm density` |
| RAM (raw) | `7,363,096 kB` (~7.0 GiB → 8 GB SKU) | `/proc/meminfo` MemTotal |
| Hermes engine | Bundled with React Native 0.81.5 (exact commit pinned in RN source tree; not surfaced in user-readable logcat tags this session — Story 1.1.1 measurement run will capture it via `adb logcat -s ReactNativeJS` at first cold launch) | TBD Story 1.1.1 |
| Dev-build APK | `apps/mobile/android/app/build/outputs/apk/debug/app-debug.apk` (175 MB) | local build |
| Dev-build APK SHA-256 | `5fdad9771468f7b49ae434a7aea50904314a8c861c9b37b951cab594d1053ae3` | `sha256sum app-debug.apk` |
| adb serial | `dc72b871` | `adb devices` |
| App package | `team.warden.mobile` (versionName `1.0.0`, versionCode `1`, minSdk `24`, targetSdk `36`) | `dumpsys package` |
| Launched MainActivity | PID `23079` (post-`expo run:android`) | `pidof team.warden.mobile` |

## Device re-anchor

The architecture (`_bmad-output/architecture.md:839`) and several other planning artifacts (`_bmad-output/prd.md:669`, `_bmad-output/epics-and-stories.md:749`, `_bmad-output/ux-design.md` multiple lines) bind the reference device as **Poco X5** (Snapdragon 695 — SD695, 6 GB RAM, Android 13). The dev agent in Session 2 ran `adb devices` and discovered the connected device is a Poco **X5 Pro 5G** (codename `redwood_eea` = X5 Pro 5G EEA variant; SoC `SM7325` = Snapdragon 778G / 4 nm; ~7.0 GiB raw RAM = 8 GB SKU; Android 14), **not** a Poco X5 (codename `stone` = SM6375 / SD695 / 6 GB / A13).

Stephane (sole developer, hardware owner) confirmed he does not have an X5 (SD695) on hand and chose to **re-anchor PERF-010 to the X5 Pro 5G** rather than wait to source an X5.

**Implication of the re-anchor:**

- The Snapdragon 778G is materially faster than the SD695: ~30–60% per benchmark suites; 4 nm vs 6 nm process; Adreno 642L vs Adreno 619 — meaningful GPU gap.
- PERF-010 binds at the Poco X5 Pro 5G's measured number (when Story 1.1.1 measures it). **V1's effective supported-device set narrows** — devices on 695-class chipsets (the cheaper Poco X5 line, Redmi Note 12 5G, etc.) are now V1-out-of-scope OR accept-as-degraded with no measured floor.
- The X5 Pro 5G remains a **mid-tier** reference device by 2026 standards (released Feb 2023; ~$300 USD MSRP) — the architecture's "no flagship floor" principle is preserved, just shifted up one rung.
- **Cross-cutting cascade** through `architecture.md:839`, `prd.md:669`, `epics-and-stories.md:749` (+ Wave-6 line 2787), `ux-design.md` (lines 37, 290, 399, 1671, 1687), and `sprint-status.yaml` last_updated comment is **AC13-extended post-merge admin** scope (kept out of this branch per Story 0.2 Lesson #2 — "do not bundle unrelated cleanups"). The cascade lands in a separate post-merge admin commit.

## JSI binding viability

This section closes AC1 and AC2.

### AC1 — Real OpenCV JSI binding for `loadFrameFromPath`

**Pre-spike state (commit `1c12ff8`):** `apps/mobile/src/shared/services/opencv.ts:381` was a throw-stub:

```ts
export async function loadFrameFromPath(_path: string): Promise<FrameBuffer> {
  throw new Error("loadFrameFromPath: react-native-fast-opencv binding not yet wired");
}
```

**Post-spike state (commit `81838be`):** The stub is replaced with a real `react-native-fast-opencv@0.4.8` JSI binding. Implementation flow:

1. `expo-file-system/legacy.readAsStringAsync(path, { encoding: Base64 })` — reads the JPEG keyframe from disk as base64 (mirrors `ffmpeg.ts`'s lazy-require pattern for the legacy module).
2. `OpenCV.base64ToMat(base64)` — decodes JPEG/PNG → BGR `Mat`.
3. `OpenCV.createObject(ObjectType.Mat, 0, 0, DataTypes.CV_8UC3)` — empty placeholder for the converted output.
4. `OpenCV.invoke('cvtColor', bgrMat, rgbMat, ColorConversionCodes.COLOR_BGR2RGB)` — BGR → RGB.
5. `OpenCV.matToBuffer(rgbMat, 'uint8')` — extracts `{ buffer: Uint8Array, rows, cols, channels }`.
6. Defensive validation: `channels === 3` and `buffer.length === rows * cols * 3` (catches binding-correctness regressions where a future fast-opencv version returns 4-channel output).
7. `OpenCV.clearBuffers([])` in a `finally` block — releases the native Mats so PSS doesn't grow unboundedly across thousands of keyframes.
8. The native imports are **lazy-required** inside the function (matching `ffmpeg.ts`'s `getFFmpeg()` pattern) so jest still loads `opencv.ts` without the native module — detector tests inject synthetic `FrameLoader`s and never hit this code path.

**Closure evidence (Session 2, 2026-05-09):**

| Check | Result |
|---|---|
| `pnpm install` succeeds | ✅ (Session 1) |
| `pnpm --filter mobile exec expo prebuild --platform android --clean` succeeds | ✅ (Session 1) |
| `pnpm --filter mobile exec expo export --platform android` produces a Hermes bundle without warnings about the new native module | ✅ 5.27 MB Hermes bundle (Session 1) |
| Full mobile jest suite passes (no regressions; pure-TS detector primitives untouched) | ✅ 105/105 tests (Session 1 + Session 2) |
| `pnpm exec expo run:android` builds the dev APK | ✅ BUILD SUCCESSFUL in 5m 25s (Session 2) |
| APK installs on Poco X5 Pro 5G | ✅ `dc72b871`, 175 MB APK SHA-256 `5fdad9…` |
| App launches without React Native bridge initialization errors | ✅ MainActivity reached focus PID 23079 |
| Native module `react-native-fast-opencv` loads on app boot | ✅ no "native module not available" in logcat |

**End-to-end keyframe-decode validation deferred to Story 1.1.1.** The `runProcessingPipeline` execution path is currently blocked by gap #6 (`detection_config/latest` not seeded + Firestore rules deny reads). Once gap #6 resolves, Story 1.1.1's first auto-slice run will exercise `loadFrameFromPath` for every keyframe and confirm the binding produces correct width × height × 3 RGB-packed `Uint8ClampedArray` output. The binding's compile-time + module-load-time viability proven here is sufficient to flip AC1 to `[x]` per the binding-only-cut decision; the on-device decode-correctness check is part of Story 1.1.1's AC4/AC8 measurement.

### AC2 — `react-native-fast-opencv` dep installed + prebuild + export clean

Closed Session 1 (commit `81838be`). Verified:

- `react-native-fast-opencv@0.4.8` added to `apps/mobile/package.json` `dependencies`.
- `pnpm install` succeeds with `.npmrc` `node-linker=hoisted` ([INVARIANT 9]) preserved.
- `react-native-mmkv@3.3.3` retained at v3 ([INVARIANT 9]; no transitive bump to v4).
- `pnpm --filter mobile exec expo prebuild --platform android --clean` succeeds; `apps/mobile/android/` regenerated.
- `pnpm --filter mobile exec expo export --platform android` produces a 5.27 MB Hermes bundle (`_expo/static/js/android/index-9491fc77a198e675a775b8da260972f8.hbc`) with no warnings about the new native module.
- `apps/mobile/android/` and `apps/mobile/ios/` added to root `.gitignore` so prebuild artifacts are not committed.

### Library versions

- `react-native-fast-opencv`: **0.4.8** (latest stable on npm at install time). The lib's own devDependencies show it was developed against `react-native@0.79.1`/`react@19.0.0`; its peer dependencies are wildcard (`{ react: '*', react-native: '*' }`). Empirical validation: prebuild + export + dev-build install all succeed against `react-native@0.81.5` + `react@19.1.0` + Expo SDK 54. The JSI surface (`base64ToMat`, `matToBuffer`, `cvtColor`, `clearBuffers`) does not depend on the wider RN bridge surface that changed across 0.79→0.81.

## Source video provenance

Per Stephane's pick (Session 2, 2026-05-09):

| Field | Value |
|---|---|
| Path on device | `/sdcard/Download/2026-01-18 12-10-30.mp4` |
| File size | 2,158,588,458 bytes (~2.01 GiB) |
| SHA-256 | `7f958d532863ddf3bec2482c967e151f97f6a50554d374e57e2f2badbf35f38b` |
| Container | MP4 (`major_brand: mp42`, `compatible_brands: mp41 isom`) |
| Recording origin | Windows desktop capture (top-level `uuid` atom embeds Windows build string `10.0.26100.0` = Windows 11 24H2) |
| Video stream | H.264 Main profile (avc1), yuv420p progressive, 1280×720 (SAR 1:1, DAR 16:9), 30 fps, 2,461 kb/s, 197,388 frames, level 3.1 |
| Audio stream | AAC LC (mp4a), 44.1 kHz stereo, 160 kb/s |
| Overall bitrate | 2,624 kb/s |
| Duration | 01:49:39.61 (6,579.6 seconds) |
| Creation time | 2026-01-18T13:21:02 UTC |

**NOT committed to repo** per Dev Note "Do NOT commit the 1h20 EVA After-h reference video" + architecture line 839.

### Spec divergences (must be carried into Story 1.1.1's measurement)

1. **Duration: 1h49m39s actual vs 1h20m architecture-spec'd.** AC4's pass criterion is **ratio-based** ("≤ 5% of source duration"), so the budget scales: budget = 5% × 6580 s = **329 s ≈ 5m29s** (vs the 4m AC4 example for 1h20). The ratio binds; the absolute number scales with source.
2. **Resolution: 1280×720 actual vs the architecture-implied 1080p reference.** **720p source under-represents 1080p workload** — less I/O during keyframe extraction, smaller decode cost, smaller crop+resize input. PERF-002 measured on 720p will be a **lower bound** for the 1080p case. Story 1.1.1's spike report should rerun on 1080p source if available; until then the 720p number is the floor and 1080p re-measurement would tighten it.
3. **Recording origin: Windows desktop capture, not Android device capture.** Codec/profile (H.264 Main 30 fps yuv420p) is representative of typical mobile-friendly H.264 sources, but exact GOP structure may differ from a phone-camera or in-app capture (probe via `getGopInfo` at Story 1.1.1 measurement time).

Stephane confirmed (2026-05-09) these divergences are acceptable for the spike measurement; the goal is to produce a binding rung verdict on the actual hardware + workload available, not to wait for a perfect-spec source.

## Substrate gap audit (six gaps)

Six substrate gaps were discovered during Session 2's measurement attempts. Each gap blocks one or more measurement ACs and has a Sprint-3 follow-up handoff. **Together, these gaps are why the spike is cut to binding-only and AC4–AC10-final defer to Story 1.1.1.**

| # | Gap | Blocks ACs | Follow-up handoff |
|---|---|---|---|
| 1 | Wrong reference device — Poco X5 Pro 5G (SM7325 / SD778G / Android 14 / 8 GB) connected, not Poco X5 (SD695 / Android 13 / 6 GB) per spec | AC3 verbatim text (now patched) | **Resolved this branch** (re-anchor); cross-cutting cascade through architecture.md / prd.md / epics-and-stories.md / ux-design.md is **AC13-extended post-merge admin** |
| 2 | Wrong source video — 1h49 720p vs spec's 1h20 1080p | AC4 budget + measurement bias | Accepted with caveats this branch; Story 1.1.1 may rerun on 1080p source |
| 3 | Cinema Mode / Card View / clip surfaces missing — no `expo-av`/`expo-video` dep, no `<Video>` component, `CinemaModeScreen.tsx` is visual stub, no Cinema/Card routes, no clip bracket UI | AC5, AC6, AC7 | **Stories 5.5, 5.4, 6.6** inherit PERF-003/004/005 measurement obligations as part of their ACs |
| 4 | EVA HUD substrate shift — new HUD invalidates fingerprints + KDA detection ROIs | AC8 (fingerprints), AC9 (KDA detector) | Dedicated Sprint 3 story (TBD; not yet in `sprint-status.yaml`): re-fingerprint 14 canonical maps under new HUD; rework KDA/HSV ROIs in `detection_config` |
| 5 | pHash (on-device `opencv.ts:phash`) vs ahash (`map_config.json` declares `hash_method: ahash`) divergence — `mapIdentifier` returns null for every segment regardless of input | AC8 | Method reconciliation work: either swap on-device `phash` → `ahash` (re-test mapIdentifier fixtures) or regenerate `map_config.json` with phash via `apps/tooling/tools/map_config_generator.py`. Tied into gap #4 (do at the same time as new-HUD re-fingerprinting). Story TBD. |
| 6 | `detection_config/latest` not seeded in Firestore + Firestore rules deny reads of `detection_config/{cfg}` (only `/users/{userId}` for owner is permitted) + real ROI values not assembled into the on-device `DetectionConfig` schema (legacy `map_config.json` has only `roi.map_name`; on-device needs 6 ROIs) | AC4, AC8, AC9 (auto-slice path can't fire) | **Sprint 3 Stories 1-13** (`hybrid-map-config-delivery-schema-version-1`) + **1-14** (`firestore-rules-coverage-extended`) + **1-15** (`firestore-rules-production-deploy`) + **1-16** (`detection-config-latest-operator-documentation`) |

The story file's Dev Note "Substrate gap audit (2026-05-09) — six gaps blocking measurement" carries the same audit with discovery-evidence detail.

## Ladder rung verdict — provisional

**Verdict (provisional, Story 1.1):** **`rung-0 plausible — binding viable; final rung TBD post-Story-1.1.1 measurement; cloud-fallback rung remains FORBIDDEN per AC11 regardless of any future measurement outcome.`**

**Rationale:**

The binding-viability evidence (AC1, AC2, AC3 closure) demonstrates that the JSI binding ships as a real binding (not a stub) on the X5 Pro 5G dev build. This eliminates the rung-3 "binding cannot ship in V1 timeline" trigger. The remaining ladder triggers (rung-0 vs rung-1 vs rung-2 vs rung-3) all depend on PERF-002/003/004/005 measurements that are deferred to Story 1.1.1.

**Pickable rungs from this spike's evidence alone:**

- **`rung-0 plausible`** — binding viable (AC1, AC2 closed). No PERF measurement available yet, so this is the plausible-default rung pending Story 1.1.1's measurement.
- **`rung-3 ruled out for binding-shipping reason`** — the binding compiled, prebuild + export clean, dev-build APK launches cleanly. Rung-3's "binding cannot ship in V1 timeline" trigger does not apply. Rung-3 may still be reached via the OTHER trigger ("multiple PERF NFRs > 50% over budget AND rung-1/rung-2 don't recover them") IF Story 1.1.1's measurement comes back hostile.

**NOT pickable from this spike's evidence:**

- **`rung-1` / `rung-2`** — both require PERF measurement misses (rung-1 on PERF-002 OR PERF-005; rung-2 on PERF-003 OR PERF-004). Story 1.1.1 will determine.
- **`rung-3 via measurement-failure path`** — also requires PERF measurement. Story 1.1.1 will determine.

**Conditional revision clause:** If Story 1.1.1's measurement comes back with PERF-002 over budget by ≥ 50% AND lower-sampling-rate tuning doesn't recover, the rung revises to rung-3 (defer auto-slice to V2; manual-clip-only V1 per Decision #UX-14). If Stories 5.4/5.5/6.6 surface PERF-003/004/005 misses post-G1, the rung revises to rung-2 (drop Minimap+HUD overlay rendering on weak hardware, gated by device profile). Sprint Plan §2 G1 should be amended (post-merge admin) to reflect this two-stage close.

## Forbidden rungs

> **Cloud-fallback CV is FORBIDDEN regardless of measured numbers. Breaks Innovation #1 (privacy + lower marginal cost). Not a permitted rung in this spike.**

This assertion is verbatim per Story 1.1 AC11 + architecture line 858. **No cloud-fallback code was added to this branch — even as an opt-in flag, conditional branch, or deferred path.** The `runProcessingPipeline` flow operates entirely on-device via the JSI binding for keyframe decode + pure-TS detector primitives + FFmpeg-kit for keyframe extract and clip export. There is no network call to a CV service in the pipeline; the only network calls are Firestore reads (detection config + user doc) and Firebase Auth, which are unrelated to the CV path.

This holds for Story 1.1.1 and all future ladder revisions: even if Story 1.1.1's measurement comes back with multiple PERF NFRs > 100× over budget, the verdict is rung-3 (defer auto-slice to V2; manual-clip-only V1), not "send frames to a server."

## Deferred measurements (Story 1.1.1 inheritance)

A new follow-up story **Story 1.1.1 — AR-SPIKE measurement** is required. It runs after Sprint 3 Stories 1-13 + 1-14 + 1-15 + 1-16 land (gap #6 resolution) AND after the new-HUD re-fingerprinting + pHash/ahash reconciliation work lands (gaps #4 + #5). Until then, the following ACs from Story 1.1 cannot be measured and Story 1.1.1 inherits their measurement obligation:

| AC | Subject | Story 1.1.1 precondition |
|---|---|---|
| **AC4** | PERF-002 auto-slice ≤ 5% source duration | Gap #6 (detection_config + rules + ROIs) |
| **AC5** | PERF-003 view-mode toggle ≤ 100 ms | **Story 5.5** (Cinema Mode + 3-state view-mode toggle) |
| **AC6** | PERF-004 Cinema Mode cold-start ≤ 1.5 s | **Story 5.4** (Cinema Mode + Card View + `<Video onLoadedData>`) |
| **AC7** | PERF-005 clip export ≤ 60 s for 30 s Mobile-tier | **Story 6.6** (Mobile-tier export action + bracket-handle UI) |
| **AC8** | Map ID accuracy ≥ 95% on unseen test set | Gaps #4 (new HUD), #5 (pHash/ahash), #6 (config seed) — three-substrate stack |
| **AC9** | Round-boundary detection floor | Gaps #4 (new HUD KDA detector rework), #6 (config seed) |
| **AC10 (final)** | Final ladder rung verdict | All measurement ACs above closed |
| **AC13** | PRD update with measured PERF-010 + conditional FR clauses | Final rung verdict published |

**Measurement scaffolding already in place for Story 1.1.1 (no rework needed):**

- `apps/mobile/src/features/video-processing/processingPipeline.ts:245+` — `__DEV__`-gated PERF-002 wall-clock timer + per-stage `__perfMark()` calls (after each `saveCheckpoint`). Logs `[PERF-002] sessionId=<id> mark=<label> t+<ms>` to logcat; persists to MMKV at `processing.<sessionId>.perf002` for post-run inspection.
- Same file, after the detection block: `[PERF-009] sessionId=<id> events START=<n> END=<n> SCORE=<n> segments=<n> mapIDs=<n> gop_avg_s=<s> hasShortGop=<bool>` — surfaces raw event counts for AC9 ground-truth comparison.

## V1 implication summary

**Per the provisional rung verdict (rung-0 plausible):**

- V1 launches with auto-slice on. PRD inherits the **measured** PERF-010 number when Story 1.1.1 publishes it (post-merge admin per AC13).
- **V1 supported-device set narrows** to "778G or stronger" (consequence of the X5 Pro 5G re-anchor — gap #1). Devices on 695-class chipsets (cheaper Poco X5, Redmi Note 12 5G) are V1-out-of-scope OR accept-as-degraded with no measured floor. The PRD's "screen sizes 5.5"–6.7"+" line at `prd.md:669` should be amended to add a CPU-tier floor (post-merge admin).
- Stories 5.1/5.3/5.4/5.5/6.6 (which carry an explicit `Story 1.1 spike` dependency per Sprint Plan §2 G1) **may plan against rung-0** but should be ready to revise scope if Story 1.1.1's measurement comes back hostile.

**Per the conditional-revision clauses:**

- **If revised to rung-1** (Story 1.1.1 measures PERF-002 OR PERF-005 over budget by < 50% and lower-sampling-rate tuning recovers): V1 ships with reduced sampling rate; PRD `mobile-AUTO-SLICE-001` adds a "with reduced sampling on weak hardware" clause.
- **If revised to rung-2** (Story 5.4/5.5 measures PERF-003 OR PERF-004 over budget): drop Minimap+HUD overlay rendering on weak hardware (gated by device profile). View modes degrade to Full + Minimap (no HUD overlay). PRD `mobile-CINEMA-002` adds a graceful-degradation clause.
- **If revised to rung-3** (multiple PERF NFRs > 50% over budget AND rung-1/rung-2 don't recover): defer auto-slice to V2; V1 ships **manual-clip-only** via Decision #UX-14 path. `mobile-AUTO-SLICE-001/002` FRs become V2-deferred; activation timer T1-coach via manual-clip becomes the only V1 path. **V1 still launches.**

## Follow-up work required

Concrete handoffs from this spike to Sprint 3:

1. **Cross-cutting reference-device cascade (gap #1)** — UPDATE `architecture.md:839`, `prd.md:669`, `epics-and-stories.md:749` (+ Wave-6 line 2787), `ux-design.md` (lines 37, 290, 399, 1671, 1687) to reference Poco X5 Pro 5G (SM7325) instead of Poco X5 (SD695). Lands in a separate post-merge admin commit per **AC13-extended scope**. Bundle with the `architecture.md` + `prd.md` + `sprint-plan.md` amendments below.
2. **Architecture amendment (binding-only-cut)** — UPDATE `_bmad-output/architecture.md` lines 832-868 (`#### Pre-PRD performance spike [SPIKE BOUND]`) to acknowledge the binding-only-cut + Story 1.1.1 follow-up. Same post-merge admin commit.
3. **Sprint Plan amendment (G1 partial close)** — UPDATE `_bmad-output/sprint-plan.md` §2 G1 closure criteria to reflect partial close (binding viability) + full-close-pending (Story 1.1.1 measurement). Same post-merge admin commit.
4. **Sprint-status amendment** — ADD Story 1.1.1 entry to `_bmad-output/sprint-status.yaml` (probably under Epic 1: `1-1-1-ar-spike-measurement: backlog`). Same post-merge admin commit.
5. **Stories 1-13 / 1-14 / 1-15 / 1-16 (gap #6)** — already in `sprint-status.yaml` Epic 1 backlog. These are the prerequisite for Story 1.1.1's measurement to fire.
6. **New-HUD re-fingerprinting + KDA-detector rework story (gap #4)** — TBD. Add to Sprint 3 backlog. Likely a multi-week effort; lives in Epic 1 or a new sub-epic under it.
7. **pHash/ahash method reconciliation (gap #5)** — bundle with #6 (do at the same time as new-HUD re-fingerprinting). Either swap on-device `phash` → `ahash` (re-test `mapIdentifier` jest fixtures) OR regenerate `map_config.json` with phash via `apps/tooling/tools/map_config_generator.py` (would need a `--method=phash` flag in the script).
8. **Story 1.1.1 — AR-SPIKE measurement** — runs after #5, #6, #7 land. Inherits AC4, AC5, AC6, AC7, AC8, AC9, AC10-final, AC13 from Story 1.1.

## G1 sign-off — partial

> **Story 1.1 published the AR-SPIKE binding-viability evidence on 2026-05-09.** Sprint Plan §2 Gate G1 is **PARTIALLY CLEARED**: closes for binding viability + Sprint-3 stories without `Story 1.1 spike` dependency. **Full close (Stories 5.1, 5.3, 5.4, 5.5, 6.6 unblock) waits on Story 1.1.1's measurement.** Those stories may begin development with the **provisional rung-0 assumption** but should be ready to revise scope if Story 1.1.1's measurement comes back hostile. PRD update with PERF-010 binding follows in a separate commit per AC13 once Story 1.1.1 publishes the measured floor.

This sign-off statement closes AC16 (partial). When Story 1.1.1 publishes its measurement, AC16 is amended in this same `_bmad-output/architecture-spike-perf-floor.md` file with a "G1 sign-off — full" subsection.
