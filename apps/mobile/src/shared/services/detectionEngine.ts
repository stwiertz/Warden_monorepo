// Story 12.2 (Epic 12) — JS wrapper for the GPU detection-engine bridge.
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
//   - Android-only: every call early-returns on non-Android. MediaCodec + GLES
//     is Android-only BY CONSTRUCTION (amendment 5c) — iOS is VideoToolbox +
//     Metal, and GLES is deprecated there.
//   - Native-module-missing swallow: in jest (and any un-prebuilt build) the
//     calls resolve to null with a __DEV__ warning, so the existing test surface
//     never sees the bridge and no test needs a device.

import { NativeModules, Platform } from "react-native";

/** One colour path's measured stage split, in ms per keyframe. */
export interface EngineStageTimings {
  /**
   * 🔴 NOT a disjoint stage. `decodeNs` is assigned from the decode loop's entry
   * and snapshotted before the GL work runs, so this NESTS the upload/resolve/
   * shader/readback of every frame but the last — which is why `stage_total`
   * can exceed `wall`. Use {@link decode_excluding_gl} and {@link gl_total}.
   */
  decode: number;
  upload_or_bind: number;
  resolve: number;
  shader: number;
  readback: number;
  /** Naive sum. Exceeds `wall` because `decode` double-counts the GL stages. */
  stage_total: number;
  wall: number;
  /** `decode` with the nested GL stages removed. The honest decode figure. */
  decode_excluding_gl?: number;
  /** upload_or_bind + resolve + shader + readback. What the ENGINE costs. */
  gl_total?: number;
  /** `gl_total / wall`. Measured ~0.06 (Path Z) / ~0.07 (Path P), not ~0.01. */
  gl_share_of_wall?: number;
}

export interface EngineTimingResult {
  color_path: "ZERO_COPY" | "BIT_PARITY" | "DIRECT_RGB";
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
   * AC11 — excluded from ms_per_keyframe and reported separately. Covers the
   * engine's own setup (program build, textures, self-test) only; EGL context
   * creation is reported at the report root as `ac11_one_off_egl_context_ms`.
   */
  one_off_setup_ms: number;
}

export interface EngineDeviceProfile {
  android_release: string;
  android_sdk_int: number;
  model: string;
  gl: Record<string, string>;
  /** AC2 — `GL_OES_EGL_image_external_essl3` is CHECKED, never assumed. */
  ac2_oes_essl3: {
    extension_advertised: boolean;
    extension_name: string;
    compiles: boolean;
  };
}

/** The bench's report. Shape mirrors WardenEngineBench.runAll. */
export interface EngineBenchReport {
  story: "12.2";
  mode: string;
  reference_device_note: string;
  ac1_device_profile: EngineDeviceProfile;
  ac5_lut_cross_check: { matches_reference: boolean; sha256: string };
  ac11_ac13_timing_naive?: EngineTimingResult[];
  /** AC11 — EGL context creation, the one-off cost 12.3 asked for by name. */
  ac11_one_off_egl_context_ms?: number;
  error?: string;
  /** Present alongside `error` when the mode itself was not recognised. */
  known_modes?: string[];
}

/**
 * Every mode the native bench dispatches on.
 *
 * 🔴 Must stay in lockstep with `WardenEngineBench.BENCH_MODES`. Before the
 * 2026-09-15 review this union exported `"profile"`, which NO Kotlin branch has
 * ever implemented — `runBench("profile")` type-checked, resolved successfully,
 * and returned a report with no measurements and no `error` field — while
 * omitting `flushprobe`, `seektest` and `pngdump`, which do exist natively and
 * were therefore unreachable through the sole sanctioned seam (AC18b).
 */
export type BenchMode =
  | "all"
  | "parity"
  | "cpugpu"
  | "timing"
  | "framediff"
  | "flushprobe"
  | "seektest"
  | "pngdump";

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
          "MediaCodec + GLES 3.0; iOS is VideoToolbox + Metal)."
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
 * AC1/AC2 — the device + GL profile, read from a CURRENT context.
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
 * it is 2.3 GB). `limit` caps the keyframe count (0 = the whole capture);
 * `cpuFrames` sizes AC12's CPU-vs-GPU comparison.
 *
 * 🔴 AC15 — the numbers this returns bind NEITHER PERF-002 NOR PERF-010. Both
 * re-baseline with Story 12.3.
 */
export async function runBench(
  mode: BenchMode = "all",
  video: string | null = null,
  limit = 0,
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
