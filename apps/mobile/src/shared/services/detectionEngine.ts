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

import { DeviceEventEmitter, NativeModules, Platform } from "react-native";

// ---------------------------------------------------------------------------
// Story 12.4c — THE PRODUCTION DETECTION API (AC0a / AC1 / AC2).
//
// Everything above this block is the Story 12.2 bench seam and stays a bench
// seam. What follows is the shipped path: `analyzeSession` is what
// `processingPipeline.ts` calls, and it is the ONLY way the app reaches the
// engine — no feature module imports `NativeModules` (INVARIANT:
// native-modules-only-via-shared-services, verified by grep before delivery).
// ---------------------------------------------------------------------------

/** One rule of the packed set — the index fire bits are ordered by. */
export interface EngineRuleRef {
  texel: number;
  owning_class: string;
  zone_id: string;
  kind: "hud_version" | "in_match" | "map";
  effective_weight: number;
}

export interface EngineKeyframeFires {
  /** MediaCodec presentation timestamp, microseconds. */
  pts_us: number;
  /** Fire bits, 4 per hex char, LSB first (`WardenEngineBench.bitsToHex`). */
  fires: string;
}

/**
 * The keyframe index's own account of itself.
 *
 * 🔴 IT IS SEEK-DERIVED, SO IT IS A HYPOTHESIS. The honest ground truth is a
 * 62 s full-file read that must never ship (12.4a AC3), so the native side
 * REPORTS coverage instead of asserting it and the caller warns. A capture with
 * an irregular GOP can end the index early, which would otherwise present as
 * "the last N minutes of my session contain no matches".
 */
export interface EngineKeyframeIndex {
  source: string;
  n_pts: number;
  index_ms: number;
  first_pts_us: number;
  last_pts_us: number;
  estimated_gop_us: number;
  duration_us: number;
  uncovered_tail_us: number;
  covers_duration: boolean;
}

export interface EngineSessionAnalysis {
  story: "12.4c";
  kind: "session-analysis";
  video: string;
  hud_version: string;
  n_rules: number;
  reference_resolution: { width: number; height: number };
  refs: EngineRuleRef[];
  frames: EngineKeyframeFires[];
  n_keyframes: number;
  keyframes_expected: number;
  keyframe_count_matches: boolean;
  keyframe_index: EngineKeyframeIndex;
  decoder: Record<string, unknown>;
  decoder_chroma_layout: string;
  decoder_flush_calls: number;
  decoder_output_format_changes: number;
  timing: {
    wall_ms: number;
    keyframe_index_ms: number;
    ms_per_keyframe_wall: number;
    ms_per_keyframe_decode_excluding_engine: number;
    ms_per_keyframe_engine: number;
  };
}

export interface EngineProgressEvent {
  requestId: string;
  keyframesDone: number;
  keyframesTotal: number;
}

/** Native-module absence, surfaced as a typed failure rather than a null. */
export class DetectionEngineUnavailableError extends Error {
  constructor() {
    super(
      "the detection engine native module is not available. It is Android-only " +
        "by construction (MediaCodec; amendment 5c) and requires a prebuilt dev " +
        "client — `expo run:android` after `expo prebuild`."
    );
    this.name = "DetectionEngineUnavailableError";
  }
}

/** The user (or a screen unmount) cancelled the run. NOT a processing failure. */
export class DetectionAnalysisCancelledError extends Error {
  constructor(message?: string) {
    super(message ?? "the session analysis was cancelled");
    this.name = "DetectionAnalysisCancelledError";
  }
}

/** The capture's geometry does not match the config's reference resolution. */
export class UnsupportedCaptureError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "UnsupportedCaptureError";
  }
}

/** Must match `WardenDetectionEngineModule.EVENT_PROGRESS`. */
export const ENGINE_PROGRESS_EVENT = "WardenDetectionEngineProgress";

/** Reject codes the native side uses. Matched, so they are an API. */
const CODE_CANCELLED = "WARDEN_ANALYSIS_CANCELLED";
const CODE_UNSUPPORTED_GEOMETRY = "WARDEN_UNSUPPORTED_GEOMETRY";

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
  runBench(mode: string, video: string | null, limit: number): Promise<string>;
  describeDevice(): Promise<string>;
  analyzeSession(
    requestId: string,
    videoPath: string,
    configJson: string,
    limit: number
  ): Promise<string>;
  cancelAnalysis(requestId: string): Promise<boolean>;
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
  limit = 0
): Promise<EngineBenchReport | null> {
  if (unavailable("runBench")) return null;
  try {
    const raw = await native!.runBench(mode, video, limit);
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

export interface AnalyzeSessionOptions {
  /**
   * Identifies this run so progress events and cancellation reach the right
   * one. The pipeline passes the sessionId.
   */
  requestId: string;
  videoPath: string;
  /**
   * The config, as JSON TEXT. Map iteration order lives in the string — the
   * native packer recovers it by scanning the raw text, because
   * `org.json.JSONObject` is a HashMap. See mapConfig.ts.
   */
  configJson: string;
  /** 0 = the whole capture. Non-zero is for development only. */
  limit?: number;
  onProgress?: (event: EngineProgressEvent) => void;
}

/**
 * 🔴 THE PRODUCTION DETECTION CALL — ONE NATIVE CALL PER SESSION (AC0a/AC1).
 *
 * Decodes every keyframe with MediaCodec and evaluates the packed rules over it
 * in Kotlin, resolving with the whole fire-bit timeline. It does NOT score: the
 * three classifier formulas and the phase machine are TypeScript's
 * (`detectionTimeline.ts`), so the detection semantics live where the tests are.
 *
 * Unlike the bench entry points above, this THROWS rather than resolving null.
 * A bench that cannot run is a reportable fact; a session the user asked to
 * process that cannot be analysed is an outcome the pipeline must handle — and
 * `null` at this seam would reach the checkpoint logic as "no matches found".
 *
 * Errors worth distinguishing, and distinguished:
 *   * {@link DetectionAnalysisCancelledError} — the user left; not a failure.
 *   * {@link UnsupportedCaptureError} — wrong capture geometry for this config.
 *   * {@link DetectionEngineUnavailableError} — no native module (jest, iOS, a
 *     build that was never prebuilt).
 */
export async function analyzeSession(
  options: AnalyzeSessionOptions
): Promise<EngineSessionAnalysis> {
  if (Platform.OS !== "android" || !native) {
    throw new DetectionEngineUnavailableError();
  }
  const { requestId, videoPath, configJson, limit = 0, onProgress } = options;

  // Subscribed BEFORE the call so no early progress event is missed, and
  // filtered by requestId so a stale subscription from a previous session
  // cannot move this one's progress bar.
  const subscription = onProgress
    ? DeviceEventEmitter.addListener(
        ENGINE_PROGRESS_EVENT,
        (event: EngineProgressEvent) => {
          if (event?.requestId === requestId) onProgress(event);
        }
      )
    : null;

  try {
    const raw = await native.analyzeSession(
      requestId,
      videoPath,
      configJson,
      limit
    );
    return JSON.parse(raw) as EngineSessionAnalysis;
  } catch (error) {
    const code = (error as { code?: string })?.code;
    const message = (error as { message?: string })?.message ?? String(error);
    if (code === CODE_CANCELLED) {
      throw new DetectionAnalysisCancelledError(message);
    }
    if (code === CODE_UNSUPPORTED_GEOMETRY) {
      throw new UnsupportedCaptureError(message);
    }
    throw error;
  } finally {
    subscription?.remove();
  }
}

/**
 * Ask the in-flight analysis to stop. Resolves true when the request matched.
 *
 * Cooperative and idempotent: the native side polls the flag once per keyframe,
 * so the worst case is one keyframe (~8 ms) of extra work, and a cancel for a
 * run that already finished (or for somebody else's run) is a no-op rather than
 * an error. Never throws — callers reach it from unmount paths.
 */
export async function cancelAnalysis(requestId: string): Promise<boolean> {
  if (Platform.OS !== "android" || !native) return false;
  try {
    return await native.cancelAnalysis(requestId);
  } catch (error) {
    if (__DEV__) {
      console.warn("[detectionEngine] cancelAnalysis failed", error);
    }
    return false;
  }
}
