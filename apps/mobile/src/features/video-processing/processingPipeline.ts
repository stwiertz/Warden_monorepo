// Story 7.5 — Processing pipeline orchestration.
//
// Runs the full detection chain for a session:
//   1. Extract keyframes (Story 2.2 — FFmpeg).
//   2. Probe GOP interval (FFprobe). Branch on the result:
//        - shortGop: feed every keyframe through `gameDetector` (KDA/HSV).
//        - longGop : feed every keyframe through the two-pass black-screen
//                    fallback in blackScreenDetector.
//      Both paths emit the same `GameDetectorEvent[]` stream.
//   3. Pair START/END events into game segments. For each segment, sample a
//      mid-segment keyframe and run `mapIdentifier` (pHash). Persist the
//      identified maps alongside the segments.
//   4. Save `MapSegmentData[]` rows via segmentRepository.
//   5. Extract one full-resolution score-screen frame per segment at
//      `endTs + score_offset_s`, clamped to video duration. Persist its
//      path on the segment row.
//   6. Mark the session `ready` (or `error` on any failure).
//
// Crash recovery: each stage writes its outputs to MMKV under
// `processing.<sessionId>.<field>` so that a relaunched pipeline can pick up
// from the last completed checkpoint. Detection-stage outputs are stored as
// `events`, `gameSegments`, and `mapIdentifications`.
//
// Frame loading: detectors take a `FrameLoader` so the pipeline doesn't
// hard-depend on a real JPEG decoder. The default loader calls
// `loadFrameFromPath` (which throws until the native binding lands), so in
// tests the loader is overridden to return synthetic FrameBuffers. The
// shape lets the rest of the pipeline land while the OpenCV native module
// is still pending integration.

import {
  extractKeyframes,
  extractFrameAt,
  getGopInfo,
  getProcessingDir,
  getVideoDuration,
} from "../../shared/services/ffmpeg";
import {
  loadFrameFromPath,
  saturationMean,
  scaleRoi,
  type FrameBuffer,
  type Resolution,
} from "../../shared/services/opencv";
import { getSession, updateSessionStatus } from "../session/sessionRepository";
import {
  insertMapSegments,
  updateResultFramePath,
} from "./segmentRepository";
import { storage } from "../../shared/services/storage";
import {
  startForegroundService,
  stopForegroundService,
  updateForegroundServiceStage,
} from "../../shared/services/foregroundService";
import { getDetectionConfig } from "./detectionConfigService";
import {
  createGameDetector,
  pairEventsIntoSegments,
  type GameSegmentTimeline,
} from "./gameDetector";
import { createMapIdentifier } from "./mapIdentifier";
import {
  buildSaturationWindowsFromValues,
  detectBlackScreensInWindow,
  type FrameSample,
} from "./blackScreenDetector";
import { buildMapSegments } from "./segmentation";
import type { DetectionConfig } from "./detectionConfig";
import type {
  GameDetectorEvent,
  KeyframeInfo,
  MapIdentificationResult,
  MapSegmentData,
  ProcessingStage,
  ProgressCallback,
} from "./types";

export type FrameLoader = (path: string) => Promise<FrameBuffer>;

export interface RunPipelineOptions {
  onProgress?: ProgressCallback;
  // Defaults to the production loader, which throws until OpenCV is wired up.
  // Tests inject a synthetic loader.
  loadFrame?: FrameLoader;
  // Defaults to the cached DetectionConfig from Story 7.4. Tests inject one
  // directly to avoid touching Firestore + MMKV.
  detectionConfig?: DetectionConfig;
  // Resolution of the FrameBuffers returned by the loader. Defaults to the
  // detection config's reference resolution (no scaling).
  processingResolution?: Resolution;
}

function checkpointKey(sessionId: string, field: string): string {
  return `processing.${sessionId}.${field}`;
}

function saveCheckpoint(sessionId: string, stage: ProcessingStage): void {
  storage.setString(checkpointKey(sessionId, "stage"), stage);
}

export function getCheckpoint(sessionId: string): ProcessingStage | null {
  return (
    (storage.getString(checkpointKey(sessionId, "stage")) as ProcessingStage) ??
    null
  );
}

function clearCheckpoint(sessionId: string): void {
  storage.delete(checkpointKey(sessionId, "stage"));
}

function stageToOverallProgress(
  stage: ProcessingStage,
  stageProgress: number
): number {
  const stageRanges: Record<ProcessingStage, [number, number]> = {
    keyframes: [0, 30],
    detection: [30, 70],
    segmentation: [70, 90],
    results: [90, 100],
  };
  const [start, end] = stageRanges[stage];
  return Math.round(start + (end - start) * (stageProgress / 100));
}

/**
 * Run the gameDetector or the long-GOP black-screen fallback over every
 * keyframe. Both paths stream — buffers are loaded one at a time and
 * dropped immediately so a 60–90 min session doesn't hold ~600 MB+ of
 * decoded frames in RAM. The long-GOP path runs two passes; Pass 1 keeps
 * only a saturation float per keyframe, Pass 2 re-loads only the indices
 * inside high-saturation windows.
 */
export async function detectGameEvents(
  keyframes: KeyframeInfo[],
  config: DetectionConfig,
  loadFrame: FrameLoader,
  hasShortGop: boolean,
  processingResolution: Resolution | undefined
): Promise<GameDetectorEvent[]> {
  if (hasShortGop) {
    const detector = createGameDetector({ config, processingResolution });
    const events: GameDetectorEvent[] = [];
    for (const kf of keyframes) {
      const buf = await loadFrame(kf.path);
      events.push(...detector.processFrame(buf, kf.timestampMs));
    }
    events.push(...detector.flush());
    return events;
  }

  // Long-GOP fallback. Pass 1: collect saturation values without retaining
  // buffers.
  const refRes = config.reference_resolution;
  const procRes = processingResolution ?? refRes;
  const teamBarRoi = scaleRoi(config.roi_zones.team_bar, refRes, procRes);
  const satValues: number[] = [];
  for (const kf of keyframes) {
    const buf = await loadFrame(kf.path);
    satValues.push(saturationMean(buf, teamBarRoi));
  }

  const windows = buildSaturationWindowsFromValues(satValues, keyframes, config);

  // Pass 2: re-load only the buffers within each window.
  const events: GameDetectorEvent[] = [];
  for (const w of windows) {
    const samples: FrameSample[] = [];
    for (let i = w.startIndex; i <= w.endIndex; i++) {
      samples.push({
        timestampMs: keyframes[i].timestampMs,
        buffer: await loadFrame(keyframes[i].path),
      });
    }
    events.push(
      ...detectBlackScreensInWindow(samples, w, { config, processingResolution })
    );
  }
  return events;
}

/**
 * For each game segment, sample a keyframe near the middle and run the map
 * identifier. Returns one MapIdentificationResult per segment (mapName = null
 * when no fingerprint was within the collision threshold; AC 8).
 */
export async function identifyMapsForSegments(
  segments: GameSegmentTimeline[],
  keyframes: KeyframeInfo[],
  config: DetectionConfig,
  loadFrame: FrameLoader,
  processingResolution: Resolution | undefined
): Promise<MapIdentificationResult[]> {
  const identifier = createMapIdentifier({
    config,
    processingResolution,
  });
  const results: MapIdentificationResult[] = [];
  for (let i = 0; i < segments.length; i++) {
    const seg = segments[i];
    const midTs = (seg.startMs + seg.endMs) / 2;
    const kf = nearestKeyframe(keyframes, midTs);
    if (!kf) {
      results.push({
        segmentIndex: i,
        mapName: null,
        hash: "",
        hammingDistance: null,
      });
      continue;
    }
    const buffer = await loadFrame(kf.path);
    const outcome = identifier.identify(buffer);
    if (outcome.match === null) {
      console.warn(
        `[mapIdentifier] segment ${i} (${seg.startMs}-${seg.endMs}ms) — no fingerprint within collision threshold (hash=${outcome.hash})`
      );
    }
    results.push({
      segmentIndex: i,
      mapName: outcome.match?.mapName ?? null,
      hash: outcome.hash,
      hammingDistance: outcome.match?.hammingDistance ?? null,
    });
  }
  return results;
}

function nearestKeyframe(
  keyframes: KeyframeInfo[],
  targetMs: number
): KeyframeInfo | null {
  if (keyframes.length === 0) return null;
  let best = keyframes[0];
  let bestDelta = Math.abs(best.timestampMs - targetMs);
  for (let i = 1; i < keyframes.length; i++) {
    const d = Math.abs(keyframes[i].timestampMs - targetMs);
    if (d < bestDelta) {
      best = keyframes[i];
      bestDelta = d;
    }
  }
  return best;
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

  const session = await getSession(sessionId);
  if (!session) throw new Error(`Session ${sessionId} not found`);

  const { onProgress, loadFrame = loadFrameFromPath } = options;
  const config = options.detectionConfig ?? (await getDetectionConfig());
  const processingResolution = options.processingResolution;

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
    let keyframes: KeyframeInfo[] = [];
    let videoDurationMs = 0;

    // Checkpoint semantics: lastStage is the LAST FULLY-COMPLETED stage. A
    // crash before any stage's saveCheckpoint leaves lastStage pointing at
    // the prior stage (or null), so on resume the corresponding block re-
    // runs from scratch — but completed stages are skipped.
    const keyframesDone =
      lastStage === "keyframes" ||
      lastStage === "detection" ||
      lastStage === "segmentation" ||
      lastStage === "results";
    const detectionDone =
      lastStage === "detection" ||
      lastStage === "segmentation" ||
      lastStage === "results";
    const segmentationDone =
      lastStage === "segmentation" || lastStage === "results";
    const resultsDone = lastStage === "results";

    if (!keyframesDone) {
      reportProgress("keyframes", 0);
      videoDurationMs = await getVideoDuration(session.video_file_path);
      keyframes = await extractKeyframes(session.video_file_path, sessionId, {
        totalDurationMs: videoDurationMs,
        onProgress: (pct) => reportProgress("keyframes", pct),
      });
      saveCheckpoint(sessionId, "keyframes");
      reportProgress("keyframes", 100);
      __perfMark(`keyframes_done_count=${keyframes.length}`);
    }

    if (!detectionDone) {
      reportProgress("detection", 0);

      if (keyframes.length === 0) {
        videoDurationMs = await getVideoDuration(session.video_file_path);
        keyframes = await extractKeyframes(session.video_file_path, sessionId, {
          totalDurationMs: videoDurationMs,
          onProgress: (pct) => reportProgress("keyframes", pct),
        });
      }

      const gop = await getGopInfo(session.video_file_path);
      const events = await detectGameEvents(
        keyframes,
        config,
        loadFrame,
        gop.hasShortGop,
        processingResolution
      );
      const gameSegments = pairEventsIntoSegments(events);
      const mapIdentifications = await identifyMapsForSegments(
        gameSegments,
        keyframes,
        config,
        loadFrame,
        processingResolution
      );

      storage.setObject(checkpointKey(sessionId, "events"), events);
      storage.setObject(
        checkpointKey(sessionId, "gameSegments"),
        gameSegments
      );
      storage.setObject(
        checkpointKey(sessionId, "mapIdentifications"),
        mapIdentifications
      );
      storage.setNumber(checkpointKey(sessionId, "duration"), videoDurationMs);

      saveCheckpoint(sessionId, "detection");
      reportProgress("detection", 100);
      if (__DEV__) {
        const startCount = events.filter((e) => e.type === "START").length;
        const endCount = events.filter((e) => e.type === "END").length;
        const scoreCount = events.filter(
          (e) => e.type === "SCORE_SCREEN"
        ).length;
        console.log(
          `[PERF-009] sessionId=${sessionId} events START=${startCount} END=${endCount} SCORE=${scoreCount} segments=${gameSegments.length} mapIDs=${mapIdentifications.length} gop_avg_s=${gop.averageGopSeconds.toFixed(2)} hasShortGop=${gop.hasShortGop}`
        );
      }
      __perfMark(
        `detection_done_segments=${gameSegments.length}_events=${events.length}`
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
        const scoreScreenMs = gameSegments[i]?.scoreScreenMs ?? seg.endTimeMs;
        // Clamp the offset to the last available frame. If the clamp swallows
        // the entire offset, log a warning but still try to capture *some*
        // frame near the end so Card View has a thumbnail (Dev Notes AC 5).
        let frameTimestamp = scoreScreenMs;
        if (videoDurationMs > 0 && frameTimestamp > videoDurationMs - 50) {
          const clamped = Math.max(seg.endTimeMs, videoDurationMs - 50);
          if (clamped - seg.endTimeMs < 1000) {
            console.warn(
              `[results] segment ${i}: score_offset_s clamped from ${frameTimestamp}ms to ${clamped}ms (video ends at ${videoDurationMs}ms)`
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
    await updateSessionStatus(sessionId, "error");
    throw error;
  } finally {
    // Owner-token stop: if a newer pipeline has since taken the singleton
    // service, this stale stop is a no-op (never strips its J2 protection).
    await stopForegroundService(sessionId);
  }
}
