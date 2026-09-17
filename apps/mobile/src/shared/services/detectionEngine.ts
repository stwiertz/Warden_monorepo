// Story 12.2 (Epic 12) — JS wrapper for the detection-engine bridge.
// Story 12.4b — narrowed to the CPU engine; every GL-shaped field is gone.
//
// AC18b — architecture.md:2190 amendment 5g: the native detection-engine module
// is reachable ONLY through `shared/services/*.ts`. This file is that seam. No
// feature module may import `NativeModules.WardenDetectionEngine` directly.
//
// Story 12.2 is a SPIKE: nothing here is wired into the shipped pipeline, and
// AC19 fences `gameDetector.ts` / `mapIdentifier.ts` / `blackScreenDetector.ts` /
// `segmentation.ts` / `processingPipeline.ts` as Story 12.4's, conditional on the
// 12.3 verdict. This module exists so the measurement path and the future
// runtime path are the same path, and so the bench is reachable from JS as well
// as from adb.
//
// Guarantees, matching the foregroundService.ts precedent:
//   - Android-only: every call early-returns on non-Android. MediaCodec is
//     Android-only BY CONSTRUCTION (amendment 5c). 🔴 Story 12.4b RE-SCOPED that
//     amendment, it did NOT revert it: removing GLES does not make decode
//     portable, because MediaCodec is the Android-only half. iOS is
//     VideoToolbox + Metal and is Phase 2.
//   - Native-module-missing swallow: in jest (and any un-prebuilt build) the
//     calls resolve to null with a __DEV__ warning, so the existing test surface
//     never sees the bridge and no test needs a device.

import { NativeModules, Platform } from "react-native";

/**
 * The bound pipeline's measured stage split, in ms per keyframe.
 *
 * 🔴 STORY 12.4b REPLACED THE GL STAGES. This carried
 * `upload_or_bind` / `resolve` / `shader` / `readback` / `gl_total` /
 * `gl_share_of_wall`, naming four GPU stages that no longer happen. They were not
 * renamed to CPU equivalents on purpose: a reader comparing `resolve` across
 * stories would be comparing a whole-frame GPU pass against an ~800-texel CPU
 * loop. The bound pipeline is decode, then engine.
 */
export interface EngineStageTimings {
  /**
   * 🔴 NOT a disjoint stage. `decodeNs` is assigned from the decode loop's entry
   * and snapshotted before the engine work runs, so this NESTS the conversion and
   * evaluation of every frame but the last — which is why `stage_total` can
   * exceed `wall`. Use {@link decode_excluding_engine} and {@link engine_total}.
   */
  decode: number;
  /**
   * Colour conversion + rule evaluation, in ONE pass: a texel is converted only
   * when a rule asks for it, so the whole-frame conversion the GPU arm needed
   * (2,073,600 pixels to read ~800) simply does not happen.
   */
  engine: number;
  /** Naive sum. Exceeds `wall` because `decode` double-counts the engine. */
  stage_total: number;
  wall: number;
  /** `decode` with the nested engine work removed. The honest decode figure. */
  decode_excluding_engine?: number;
  /** What the ENGINE costs. */
  engine_total?: number;
  /** `engine_total / wall`. */
  engine_share_of_wall?: number;
}

export interface EngineTimingResult {
  /**
   * 🔴 The three GPU colour paths are gone. `ZERO_COPY` decoded straight into a
   * SurfaceTexture for the shader and its conversion was DRIVER-DEFINED — it
   * diverged from bit-parity on 0.888% of decisions, including 44 of the 69
   * low-saturation rules. `BIT_PARITY` uploaded YUV planes for a GPU resolve.
   * `DIRECT_RGB` was the PNG corpus path. One CPU converter replaces all three,
   * which is how the colour behaviour became predictable across devices — by
   * removing the choice rather than by making it.
   */
  color_path: "CPU_BT709_LIMITED";
  /** Which 4:2:0 layout the decoder handed back. Observed, never assumed. */
  decoder_chroma_layout?: string;
  n_keyframes_decoded: number;
  n_sync_samples_reported: number;
  /**
   * AC0b's binding assertion — decoded count vs the expected count.
   *
   * On a LIMITED run this compares against `min(limit, sync samples)`, not
   * against the file's full sync-sample count; {@link keyframe_count_assertion}
   * says which. (Before 2026-09-15 a limited run reported `true`
   * unconditionally, so the field asserted nothing while looking like it had.)
   */
  keyframe_count_matches: boolean;
  keyframe_count_assertion?: "limited-run" | "full-capture";
  keyframe_count_expected?: number;
  ms_per_keyframe: EngineStageTimings;
  total_wall_ms: number;
  /**
   * 🔴 Structurally ZERO since Story 12.4b, and reported rather than dropped so a
   * missing field is not read as a measurement that failed. It covered the GPU
   * engine's program build, texture allocation and rules self-test; the CPU
   * engine allocates nothing per run.
   */
  one_off_setup_ms: number;
  one_off_setup_note?: string;
}

export interface EngineDeviceProfile {
  android_release: string;
  android_sdk_int: number;
  model: string;
  /**
   * 🔴 `gl` and `ac2_oes_essl3` were removed by Story 12.4b. They carried
   * GL_RENDERER / GL_VERSION and a live compile probe for
   * `GL_OES_EGL_image_external_essl3`, because Path Z's availability turned on
   * them. There is no GL context to describe and no extension whose absence
   * changes anything any more.
   */
  engine: {
    kind: string;
    color_conversion: string;
    gpu_used: false;
  };
  /** Present only when the profile was given a video path. */
  mediacodec?: Record<string, unknown>;
}

/** The bench's report. Shape mirrors WardenEngineBench.runAll. */
export interface EngineBenchReport {
  story: "12.2";
  mode: string;
  reference_device_note: string;
  ac1_device_profile: EngineDeviceProfile;
  ac5_lut_cross_check: { matches_reference: boolean; sha256: string };
  /**
   * Story 12.4b AC2 — the bt709 limited-range conversion re-derived over ALL 2^24
   * (Y, Cb, Cr) triples ON DEVICE and hashed against the pinned numpy reference.
   * Present in EVERY mode: it is the only check that can catch a wrong OPERATOR
   * rather than a wrong constant, and 12.2 found two silent colour bugs the hard
   * way.
   */
  ac2_color_constants?: {
    triples: number;
    sha256: string;
    reference_sha256_from_numpy: string;
    matches_reference: boolean;
  };
  /**
   * 🔴 A ONE-ELEMENT array since Story 12.4b, and its element is a different
   * thing: pre-12.4b the first entry was ZERO_COPY. Stated here rather than left
   * for Story 12.4d to infer from an array that silently got shorter.
   */
  ac11_ac13_timing_naive?: EngineTimingResult[];
  ac0c_paths_measured?: string[];
  ac0c_paths_removed?: string[];
  error?: string;
  /** Present alongside `error` when the mode itself was not recognised. */
  known_modes?: string[];
}

/**
 * Every mode the native bench dispatches on.
 *
 * 🔴 Must stay in lockstep with `WardenEngineBench.BENCH_MODES` — asserted
 * MECHANICALLY by `detectionEngine.test.ts`, which reads the Kotlin off disk.
 * Before the 2026-09-15 review this union exported `"profile"`, which NO Kotlin
 * branch has ever implemented — `runBench("profile")` type-checked, resolved
 * successfully, and returned a report with no measurements and no `error` field.
 *
 * Story 12.4b retired two committed modes: `cpugpu` (its GPU arm is gone; its
 * CPU half moved into `parity`, which now times the whole 2666-PNG corpus instead
 * of a 400-PNG prefix) and `pngdump` (it dumped the resolved GPU frame texture).
 * The temporary `cpucolor` gate — an A/B against the GPU arm — only ever existed
 * on the working tree and was never committed; it is still named in the guard so
 * it cannot come back. Its result is banked in `apps/mobile/bench/12-4b/REPORT.md`.
 */
export type BenchMode =
  | "all"
  | "parity"
  | "timing"
  | "framediff"
  | "flushprobe"
  | "seektest";

interface WardenDetectionEngineNative {
  runBench(
    mode: string,
    video: string | null,
    limit: number,
    cpuFrames: number
  ): Promise<string>;
  describeDevice(): Promise<string>;
}

const native = NativeModules.WardenDetectionEngine as
  | WardenDetectionEngineNative
  | undefined;

function warnMissing(action: string): void {
  if (__DEV__) {
    console.warn(
      `[detectionEngine] native module WardenDetectionEngine not found; ${action} is a no-op ` +
        "(expected in jest / non-Android / un-prebuilt builds)."
    );
  }
}

function unavailable(action: string): boolean {
  if (Platform.OS !== "android") {
    if (__DEV__) {
      console.warn(
        `[detectionEngine] ${action} is Android-only by construction (amendment 5c: ` +
          "MediaCodec; iOS is VideoToolbox + Metal)."
      );
    }
    return true;
  }
  if (!native) {
    warnMissing(action);
    return true;
  }
  return false;
}

/**
 * The device profile — SoC, API level, thermal state and the MediaCodec decoder.
 *
 * Returns null when the bridge is unavailable rather than throwing: a probe that
 * cannot run is not an error condition for any caller, and every caller in this
 * story treats "no device" as a reportable fact.
 */
export async function describeDevice(): Promise<EngineDeviceProfile | null> {
  if (unavailable("describeDevice")) return null;
  try {
    return JSON.parse(await native!.describeDevice()) as EngineDeviceProfile;
  } catch (error) {
    console.warn("[detectionEngine] describeDevice failed", error);
    return null;
  }
}

/**
 * Runs the Story 12.2 measurement harness and returns its report.
 *
 * `video` is an on-device path (the capture is pushed with adb, never bundled —
 * it is 2.3 GB). `limit` caps the keyframe count (0 = the whole capture).
 *
 * 🔴 AC15 — the numbers this returns bind NEITHER PERF-002 NOR PERF-010.
 * PERF-002 was re-baselined by Story 12.3 and is re-measured end to end by Story
 * 12.4d; PERF-010 stays a SOFT target, not a device-population floor.
 */
export async function runBench(
  mode: BenchMode = "all",
  video: string | null = null,
  limit = 0,
  /**
   * Retained as the bridge's fourth positional argument. It sized the retired
   * `cpugpu` comparison and the native side now ignores it; left in place so the
   * bridge signature does not shift under Story 12.4c, which owns this seam next.
   */
  cpuFrames = 400
): Promise<EngineBenchReport | null> {
  if (unavailable("runBench")) return null;
  try {
    const raw = await native!.runBench(mode, video, limit, cpuFrames);
    return JSON.parse(raw) as EngineBenchReport;
  } catch (error) {
    console.warn("[detectionEngine] runBench failed", error);
    return null;
  }
}

/** True when the native engine bridge is linked into this build. */
export function isEngineAvailable(): boolean {
  return Platform.OS === "android" && native !== undefined;
}
