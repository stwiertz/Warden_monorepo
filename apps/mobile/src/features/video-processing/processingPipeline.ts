// Story 7.5 — Processing pipeline orchestration.
// Story 12.4c — REWIRED ONTO THE BOUND DETECTION ENGINE.
//
// 🔴 STAGES 1 AND 2 COLLAPSED INTO ONE NATIVE CALL.
//
// Before: FFmpeg extracted every keyframe to `./keyframes/*.jpg` ON DISK (0-30%),
// then detection re-loaded each JPEG through `loadFrameFromPath` ->
// `react-native-fast-opencv` -> pure-TS detectors (30-70%), branching on
// `getGopInfo().hasShortGop` into either the KDA detector or a two-pass
// black-screen fallback.
//
// Now: `analyzeSession` decodes the keyframes in RAM via MediaCodec and evaluates
// the packed rules in Kotlin, returning one fire-bit row per keyframe. There is
// no JPEG, no disk round-trip, no per-frame bridge crossing, and no GOP branch
// (the engine decodes keyframes ONLY, by construction). What remains in JS is
// scoring and phase resolution, which is where the product semantics belong.
//
// The stages are now:
//   1. detection    — one native call: decode + evaluate + score + resolve phases
//   2. segmentation — spans zipped with map IDs, persisted to SQLite
//   3. results      — one score-screen thumbnail per segment (FFmpeg, unchanged)
//
// 🔴 EVERYTHING THIS FILE ALREADY GUARANTEED IS STILL GUARANTEED (AC7), and none
// of it is restated by the engine work:
//   * the foreground-service lifecycle: start INSIDE the try, stop in `finally`,
//     owner-token stop, and one `updateForegroundServiceStage` per stage
//     transition through the single `reportProgress` funnel (Story 1.2's
//     JS-push contract);
//   * MMKV checkpoint resume — with a NEW key set, and an explicit migration for
//     checkpoints written by the old shape (see CHECKPOINT_SCHEMA);
//   * error semantics: stage-boundary catch -> session `error` -> rethrow, with
//     checkpoints DELIBERATELY NOT cleared so the user can retry;
//   * progress monotonicity, and it got BETTER rather than worse: the native
//     call reports keyframe progress as device events, so the longest stage is
//     now incremental where the old `detection` stage reported only 0 then 100;
//   * the results stage's clamp to `videoDurationMs - 50` and its best-effort
//     thumbnail tolerance;
//   * `assertSafeSessionId` / path-traversal hardening — every on-disk path
//     still goes through `getProcessingDir(sessionId)`, and the engine adds no
//     new on-disk path at all (it writes nothing).

import {
  extractFrameAt,
  getProcessingDir,
  getVideoDuration,
} from "../../shared/services/ffmpeg";
import { getSession, updateSessionStatus } from "../session/sessionRepository";
import { insertMapSegments, updateResultFramePath } from "./segmentRepository";
import { storage } from "../../shared/services/storage";
import {
  startForegroundService,
  stopForegroundService,
  updateForegroundServiceStage,
} from "../../shared/services/foregroundService";
import {
  analyzeSession as analyzeSessionNative,
  cancelAnalysis,
  DetectionAnalysisCancelledError,
  type EngineSessionAnalysis,
} from "../../shared/services/detectionEngine";
import { buildSessionDetection } from "./detectionTimeline";
import { buildMapSegments } from "./segmentation";
import {
  getPrimaryMapConfig,
  summariseClassifiers,
  type MapConfigCandidate,
} from "./mapConfig";
import type { GameSegmentTimeline } from "./gameDetector";
import type {
  MapIdentificationResult,
  MapSegmentData,
  ProcessingStage,
  ProgressCallback,
} from "./types";

/**
 * The seam every test runs through, replacing Story 7.5's injectable
 * `FrameLoader`.
 *
 * That seam is why the pipeline's tests never needed a device, and losing it
 * would have taken the whole test surface with it — so the native call is
 * injectable in exactly the same shape.
 */
export type SessionAnalyzer = typeof analyzeSessionNative;

export interface RunPipelineOptions {
  onProgress?: ProgressCallback;
  /** Defaults to the native engine. Tests inject a synthetic analysis. */
  analyze?: SessionAnalyzer;
  /** Defaults to the bundled v2 config (Story 1.13 widens the source). */
  mapConfig?: MapConfigCandidate;
  /**
   * 0 = the whole capture. Development only — a limited run produces a
   * truncated timeline and must never be a shipped default.
   */
  keyframeLimit?: number;
  /** `doubt_margin`; 0 disables doubt and reproduces Story 9.13 exactly. */
  doubtMargin?: number;
}

/**
 * 🔴 THE CHECKPOINT SHAPE CHANGED, SO IT IS VERSIONED.
 *
 * The old pipeline wrote `stage` values of `keyframes | detection | segmentation
 * | results`, plus `events` (GameDetectorEvent[], a type that no longer exists)
 * and `mapIdentifications` rows carrying pHash `hash`/`hammingDistance` fields.
 * Resuming a v1 checkpoint into this pipeline would either skip the only stage
 * that now does any detection, or feed pHash-era rows into segmentation.
 *
 * So: a checkpoint without `CHECKPOINT_SCHEMA` is DISCARDED and its payload keys
 * are deleted, and the session re-runs from the start. That is a real upgrade
 * path (an app update mid-processing is not hypothetical), it costs one analysis
 * of a session the user had not finished anyway, and it is the only option that
 * cannot produce a silently wrong timeline.
 */
export const CHECKPOINT_SCHEMA = 2;

/** Payload keys the pipeline owns under `processing.<sessionId>.*`. */
const CHECKPOINT_KEYS = [
  "stage",
  "schema",
  "gameSegments",
  "mapIdentifications",
  "duration",
  "segmentIds",
  "segmentData",
  "analysis",
  "perf002",
  // v1 keys, listed so the migration can delete them. `events` was the old
  // detector's START/END/SCORE_SCREEN stream; nothing writes it any more.
  "events",
] as const;

function checkpointKey(sessionId: string, field: string): string {
  return `processing.${sessionId}.${field}`;
}

function saveCheckpoint(sessionId: string, stage: ProcessingStage): void {
  storage.setString(checkpointKey(sessionId, "stage"), stage);
  storage.setNumber(checkpointKey(sessionId, "schema"), CHECKPOINT_SCHEMA);
}

/**
 * The last fully-completed stage, or null.
 *
 * Returns null — after clearing the stale payload — for any checkpoint written
 * by a pipeline older than {@link CHECKPOINT_SCHEMA}, including the `keyframes`
 * stage that no longer exists.
 */
export function getCheckpoint(sessionId: string): ProcessingStage | null {
  const stage = storage.getString(checkpointKey(sessionId, "stage")) as
    | ProcessingStage
    | undefined;
  if (!stage) return null;
  const schema = storage.getNumber(checkpointKey(sessionId, "schema")) ?? 0;
  if (schema !== CHECKPOINT_SCHEMA || !isKnownStage(stage)) {
    if (__DEV__) {
      console.warn(
        `[processingPipeline] discarding checkpoint for ${sessionId}: stage=` +
          `${stage} schema=${schema} (this build writes schema ` +
          `${CHECKPOINT_SCHEMA}). The session re-runs from the start.`
      );
    }
    clearCheckpoint(sessionId);
    return null;
  }
  return stage;
}

function isKnownStage(value: string): value is ProcessingStage {
  return value === "detection" || value === "segmentation" || value === "results";
}

function clearCheckpoint(sessionId: string): void {
  for (const field of CHECKPOINT_KEYS) {
    storage.delete(checkpointKey(sessionId, field));
  }
}

/**
 * Stage -> overall 0-100.
 *
 * Re-ranged for the collapsed stages. Detection owns 0-70 because it IS the
 * multi-minute stage (decode + evaluate over every keyframe) and it is now
 * genuinely incremental: the native call reports keyframe progress, so the bar
 * moves throughout instead of jumping 0 -> 100 the way the old detection stage
 * did.
 */
function stageToOverallProgress(
  stage: ProcessingStage,
  stageProgress: number
): number {
  const stageRanges: Record<ProcessingStage, [number, number]> = {
    detection: [0, 70],
    segmentation: [70, 90],
    results: [90, 100],
  };
  const [start, end] = stageRanges[stage];
  return Math.round(start + (end - start) * (stageProgress / 100));
}

/**
 * Cancel the analysis in flight for `sessionId`, if any.
 *
 * 🔴 DELIBERATELY NOT WIRED TO SCREEN UNMOUNT. Cancelling when the user leaves
 * the screen would contradict Story 1.2's whole reason for existing: the
 * foreground service is there so a multi-minute run SURVIVES backgrounding (J2).
 * This is the seam for an explicit "stop processing" action, and for a caller
 * that knows the run is no longer wanted — not for navigation.
 *
 * The pipeline then throws {@link DetectionAnalysisCancelledError}, which is NOT
 * treated as a processing failure: the session keeps its checkpoint and its
 * previous status, and a later run resumes.
 */
export async function cancelProcessing(sessionId: string): Promise<boolean> {
  return cancelAnalysis(sessionId);
}

/**
 * Run the full processing pipeline for a session.
 */
export async function runProcessingPipeline(
  sessionId: string,
  options: RunPipelineOptions = {}
): Promise<void> {
  // Story 1.1 AR-SPIKE — PERF-002 wall-clock + per-stage timing.
  // __DEV__-gated; no production overhead. Read live via:
  //   adb logcat -s ReactNativeJS:V *:S | grep PERF-002
  // Persisted to MMKV at processing.<sessionId>.perf002 for post-run inspection.
  const __perfStart = __DEV__ ? performance.now() : 0;
  const __perfStages: Record<string, number> = {};
  const __perfMark = (label: string): void => {
    if (!__DEV__) return;
    const t = performance.now() - __perfStart;
    __perfStages[label] = t;
    console.log(
      `[PERF-002] sessionId=${sessionId} mark=${label} t+${t.toFixed(0)}ms`
    );
  };
  if (__DEV__) {
    console.log(`[PERF-002] sessionId=${sessionId} start`);
  }

  // Unchanged and deliberate: a missing session throws BEFORE the try, so no
  // foreground service is started, none is stopped, and no status is written for
  // a session that does not exist.
  const session = await getSession(sessionId);
  if (!session) throw new Error(`Session ${sessionId} not found`);

  const { onProgress, analyze = analyzeSessionNative } = options;
  const mapConfig = options.mapConfig ?? getPrimaryMapConfig();
  const classifiers = summariseClassifiers(mapConfig);

  await updateSessionStatus(sessionId, "processing");

  // Story 1.2 (BF-5) — push the stage to the FGS notification on each
  // transition. Fire-and-forget: the wrapper never rejects, so this must not
  // block or fail the pipeline.
  let lastNotifiedStage: ProcessingStage | null = null;
  const reportProgress = (stage: ProcessingStage, stageProgress: number) => {
    if (stage !== lastNotifiedStage) {
      lastNotifiedStage = stage;
      void updateForegroundServiceStage(stage);
    }
    onProgress?.(stage, stageToOverallProgress(stage, stageProgress));
  };

  try {
    // Story 1.2 (BF-5) — keep the JS context alive while the pipeline runs in
    // the background (J2). Inside the try so a native start failure propagates
    // to the catch below (session → "error"); the finally guarantees the
    // service is always stopped — on success, on a re-thrown error, and even
    // when this start call itself throws. Never leak the service (architecture.md:821).
    await startForegroundService(sessionId);

    const lastStage = getCheckpoint(sessionId);
    let videoDurationMs = 0;

    // Checkpoint semantics are unchanged: lastStage is the LAST FULLY-COMPLETED
    // stage, so a crash before a stage's saveCheckpoint re-runs that stage from
    // scratch while completed stages are skipped.
    const detectionDone =
      lastStage === "detection" ||
      lastStage === "segmentation" ||
      lastStage === "results";
    const segmentationDone =
      lastStage === "segmentation" || lastStage === "results";
    const resultsDone = lastStage === "results";

    if (!detectionDone) {
      reportProgress("detection", 0);

      // The duration is probed here rather than during keyframe extraction —
      // the stage that used to own it no longer exists — and it is still needed
      // by the results stage's past-EOF clamp.
      videoDurationMs = await getVideoDuration(session.video_file_path);

      const analysis: EngineSessionAnalysis = await analyze({
        requestId: sessionId,
        videoPath: session.video_file_path,
        configJson: mapConfig.rawJson,
        limit: options.keyframeLimit ?? 0,
        onProgress: (event) => {
          if (event.keyframesTotal > 0) {
            reportProgress(
              "detection",
              Math.min(
                100,
                Math.round((event.keyframesDone / event.keyframesTotal) * 100)
              )
            );
          }
        },
      });

      const detection = buildSessionDetection(analysis, mapConfig, classifiers, {
        doubtMargin: options.doubtMargin,
      });
      const gameSegments = detection.segments;
      const mapIdentifications = detection.identifications;

      if (!analysis.keyframe_index.covers_duration && __DEV__) {
        console.warn(
          `[processingPipeline] the keyframe index stops ` +
            `${(analysis.keyframe_index.uncovered_tail_us / 1e6).toFixed(1)}s ` +
            `before the end of the capture (GOP estimate ` +
            `${(analysis.keyframe_index.estimated_gop_us / 1e6).toFixed(2)}s). ` +
            "The index is seek-derived and stops at the first step that fails to " +
            "advance, so an irregular GOP truncates it — matches after that point " +
            "are not detected."
        );
      }
      if (!detection.hud.matched && __DEV__) {
        console.warn(
          `[processingPipeline] HUD-version selection did not match ` +
            `${mapConfig.hudVersion} (mean confidence ` +
            `${detection.hud.meanConfidence.toFixed(2)} over ` +
            `${detection.hud.sampledKeyframes} keyframes). Analysing with it ` +
            "anyway — below-floor behaviour is graceful degradation, not a " +
            "blocking error (REL-006)."
        );
      }

      storage.setObject(checkpointKey(sessionId, "gameSegments"), gameSegments);
      storage.setObject(
        checkpointKey(sessionId, "mapIdentifications"),
        mapIdentifications
      );
      storage.setNumber(checkpointKey(sessionId, "duration"), videoDurationMs);
      // A compact record of WHAT ran, not the timeline: 1061 rows of per-frame
      // state would be the largest thing this app ever puts in MMKV, and nothing
      // resumes from them.
      storage.setObject(checkpointKey(sessionId, "analysis"), {
        hudVersion: detection.hud.hudVersion,
        hudConfidence: detection.hud.meanConfidence,
        keyframes: analysis.n_keyframes,
        keyframeCountMatches: analysis.keyframe_count_matches,
        coversDuration: analysis.keyframe_index.covers_duration,
        engineMsPerKeyframe: analysis.timing.ms_per_keyframe_engine,
        wallMs: analysis.timing.wall_ms,
      });

      saveCheckpoint(sessionId, "detection");
      reportProgress("detection", 100);
      if (__DEV__) {
        console.log(
          `[PERF-009] sessionId=${sessionId} keyframes=${detection.stats.keyframes} ` +
            `in_match=${detection.stats.inMatchFrames} ` +
            `score_screen=${detection.stats.scoreScreenFrames} ` +
            `not_in_match=${detection.stats.notInMatchFrames} ` +
            `doubt=${detection.stats.doubtFrames} ` +
            `segments=${gameSegments.length} ` +
            `unknownMaps=${detection.stats.unknownMapSegments} ` +
            `hud=${detection.hud.hudVersion} ` +
            `engine_ms_per_kf=${analysis.timing.ms_per_keyframe_engine.toFixed(3)} ` +
            `layout=${analysis.decoder_chroma_layout}`
        );
      }
      __perfMark(
        `detection_done_segments=${gameSegments.length}_keyframes=${detection.stats.keyframes}`
      );
    }

    if (!segmentationDone) {
      reportProgress("segmentation", 0);

      const gameSegments =
        storage.getObject<GameSegmentTimeline[]>(
          checkpointKey(sessionId, "gameSegments")
        ) ?? [];
      const mapIdentifications =
        storage.getObject<MapIdentificationResult[]>(
          checkpointKey(sessionId, "mapIdentifications")
        ) ?? [];
      videoDurationMs =
        storage.getNumber(checkpointKey(sessionId, "duration")) ?? 0;

      const segments = buildMapSegments(gameSegments, mapIdentifications);
      const savedSegments = await insertMapSegments(sessionId, segments);

      storage.setObject(
        checkpointKey(sessionId, "segmentIds"),
        savedSegments.map((s) => s.id)
      );
      storage.setObject(checkpointKey(sessionId, "segmentData"), segments);

      saveCheckpoint(sessionId, "segmentation");
      reportProgress("segmentation", 100);
      __perfMark("segmentation_done");
    }

    if (!resultsDone) {
      reportProgress("results", 0);

      const segmentData =
        storage.getObject<MapSegmentData[]>(
          checkpointKey(sessionId, "segmentData")
        ) ?? [];
      const segmentIds =
        storage.getObject<string[]>(checkpointKey(sessionId, "segmentIds")) ??
        [];
      const gameSegments =
        storage.getObject<GameSegmentTimeline[]>(
          checkpointKey(sessionId, "gameSegments")
        ) ?? [];
      if (videoDurationMs === 0) {
        videoDurationMs =
          storage.getNumber(checkpointKey(sessionId, "duration")) ?? 0;
      }
      if (videoDurationMs === 0) {
        // Storage cache evicted between stages; re-probe so the score-screen
        // clamp has a basis. Without this we'd silently send a possibly-past-
        // EOF timestamp into FFmpeg.
        videoDurationMs = await getVideoDuration(session.video_file_path);
        storage.setNumber(checkpointKey(sessionId, "duration"), videoDurationMs);
      }
      const processingDir = getProcessingDir(sessionId);

      for (let i = 0; i < segmentData.length; i++) {
        const seg = segmentData[i];
        // The score-screen timestamp is now TIMING-DERIVED (the first keyframe
        // the phase machine resolved to `score_screen`), not `endTs +
        // score_offset_s`. The clamp below is unchanged and still load-bearing.
        const scoreScreenMs = gameSegments[i]?.scoreScreenMs ?? seg.endTimeMs;
        // Clamp the offset to the last available frame. If the clamp swallows
        // the entire offset, log a warning but still try to capture *some*
        // frame near the end so Card View has a thumbnail (Dev Notes AC 5).
        let frameTimestamp = scoreScreenMs;
        if (videoDurationMs > 0 && frameTimestamp > videoDurationMs - 50) {
          const clamped = Math.max(seg.endTimeMs, videoDurationMs - 50);
          if (clamped - seg.endTimeMs < 1000) {
            console.warn(
              `[results] segment ${i}: score-screen timestamp clamped from ${frameTimestamp}ms to ${clamped}ms (video ends at ${videoDurationMs}ms)`
            );
          }
          frameTimestamp = clamped;
        }
        const outputPath = `${processingDir}/results/map_${seg.mapIndex}.jpg`;

        let extracted = false;
        try {
          await extractFrameAt(
            session.video_file_path,
            frameTimestamp,
            outputPath
          );
          extracted = true;
        } catch (err) {
          // Result frame is best-effort: a missing thumbnail still leaves the
          // segment navigable. Log so prod failures are diagnosable instead
          // of presenting as silently-empty Card View tiles.
          console.warn(
            `[results] segment ${i}: thumbnail extraction failed at ${frameTimestamp}ms`,
            err
          );
        }
        if (extracted && segmentIds[i]) {
          try {
            await updateResultFramePath(segmentIds[i], outputPath);
          } catch (err) {
            // FFmpeg succeeded but the DB update failed: file exists on disk
            // without a row pointing at it. Surface so it can be reconciled.
            console.warn(
              `[results] segment ${i}: thumbnail saved at ${outputPath} but DB update failed`,
              err
            );
          }
        }

        reportProgress(
          "results",
          Math.round(((i + 1) / segmentData.length) * 100)
        );
      }

      saveCheckpoint(sessionId, "results");
      __perfMark("results_done");
    }

    await updateSessionStatus(sessionId, "ready");
    if (__DEV__) {
      const totalMs = performance.now() - __perfStart;
      __perfStages.total = totalMs;
      console.log(
        `[PERF-002] sessionId=${sessionId} end totalMs=${totalMs.toFixed(0)}`
      );
      try {
        storage.setObject(
          checkpointKey(sessionId, "perf002"),
          __perfStages
        );
      } catch (err) {
        // Best-effort; perf data is also in logcat.
        console.warn(`[PERF-002] mmkv persist failed:`, err);
      }
    }
    clearCheckpoint(sessionId);
  } catch (error) {
    if (__DEV__) {
      const totalMs = performance.now() - __perfStart;
      __perfStages.total = totalMs;
      __perfStages.errored = 1;
      console.log(
        `[PERF-002] sessionId=${sessionId} ERROR totalMs=${totalMs.toFixed(0)} err=${error instanceof Error ? error.message : String(error)}`
      );
      try {
        storage.setObject(
          checkpointKey(sessionId, "perf002"),
          __perfStages
        );
      } catch (persistErr) {
        console.warn(`[PERF-002] mmkv persist (error path) failed:`, persistErr);
      }
    }
    // 🔴 CANCELLATION IS NOT A FAILURE. The user left the screen; the session
    // keeps whatever status it had before this run and its checkpoint, so the
    // next run resumes instead of restarting. Marking it `error` would make a
    // deliberate act look like a broken app — and `error` is a terminal state in
    // the session list.
    if (error instanceof DetectionAnalysisCancelledError) {
      await updateSessionStatus(sessionId, session.status);
      throw error;
    }
    await updateSessionStatus(sessionId, "error");
    throw error;
  } finally {
    // Owner-token stop: if a newer pipeline has since taken the singleton
    // service, this stale stop is a no-op (never strips its J2 protection).
    await stopForegroundService(sessionId);
  }
}
