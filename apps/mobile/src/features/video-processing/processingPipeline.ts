import {
  extractKeyframes,
  extractFrameAt,
  getVideoDuration,
  getProcessingDir,
} from "../../shared/services/ffmpeg";
import { getSession, updateSessionStatus } from "../session/sessionRepository";
import { detectBlackScreens } from "./blackScreenDetector";
import { matchMapEndScreens } from "./templateMatcher";
import { insertMapSegments } from "./segmentRepository";
import { storage } from "../../shared/services/storage";
import type {
  KeyframeInfo,
  TimestampRange,
  TemplateMatchResult,
  MapSegmentData,
  ProcessingStage,
  ProgressCallback,
} from "./types";

const TEMPLATE_DIR = "assets/images/map-templates";

// Checkpoint keys
function checkpointKey(sessionId: string, field: string): string {
  return `processing.${sessionId}.${field}`;
}

/**
 * Segment video into map episodes by combining detection results.
 *
 * Algorithm:
 * - Black screen ranges mark transitions between maps
 * - Template matches (when available) confirm map end screens
 * - First gameplay starts after the first black screen (lobby excluded)
 * - Maps are the gameplay between consecutive black screens
 */
export function segmentVideo(
  blackScreenRanges: TimestampRange[],
  templateMatches: TemplateMatchResult[],
  videoDurationMs: number
): MapSegmentData[] {
  if (blackScreenRanges.length === 0) {
    // No black screens detected — treat entire video as one segment
    return [
      {
        mapIndex: 0,
        startTimeMs: 0,
        endTimeMs: videoDurationMs,
        mapName: null,
        resultFramePath: null,
      },
    ];
  }

  const segments: MapSegmentData[] = [];
  let mapIndex = 0;

  // Skip lobby: first gameplay starts after the first black screen ends
  for (let i = 0; i < blackScreenRanges.length; i++) {
    const currentBlackEnd = blackScreenRanges[i].endMs;
    const nextBlackStart =
      i + 1 < blackScreenRanges.length
        ? blackScreenRanges[i + 1].startMs
        : videoDurationMs;

    // Skip tiny segments (< 30s) — likely transitions, not maps
    const segmentDuration = nextBlackStart - currentBlackEnd;
    if (segmentDuration < 30_000) continue;

    // Check if a template match falls within this segment
    const matchInSegment = templateMatches.find(
      (m) => m.timestampMs >= currentBlackEnd && m.timestampMs <= nextBlackStart
    );

    segments.push({
      mapIndex,
      startTimeMs: currentBlackEnd,
      endTimeMs: nextBlackStart,
      mapName: matchInSegment?.templateName ?? null,
      resultFramePath: null,
    });

    mapIndex++;
  }

  return segments;
}

/**
 * Save processing checkpoint to MMKV for crash recovery.
 */
function saveCheckpoint(sessionId: string, stage: ProcessingStage): void {
  storage.setString(checkpointKey(sessionId, "stage"), stage);
}

/**
 * Get last completed processing stage from checkpoint.
 */
export function getCheckpoint(sessionId: string): ProcessingStage | null {
  return (
    (storage.getString(checkpointKey(sessionId, "stage")) as ProcessingStage) ??
    null
  );
}

/**
 * Clear processing checkpoint after completion.
 */
function clearCheckpoint(sessionId: string): void {
  storage.delete(checkpointKey(sessionId, "stage"));
}

/**
 * Map processing stages to overall progress percentages.
 */
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
 * Run the full processing pipeline for a session.
 *
 * Pipeline: extract keyframes → detect black screens → match templates
 *           → segment video → extract result frames → mark ready
 */
export async function runProcessingPipeline(
  sessionId: string,
  onProgress?: ProgressCallback
): Promise<void> {
  const session = await getSession(sessionId);
  if (!session) throw new Error(`Session ${sessionId} not found`);

  await updateSessionStatus(sessionId, "processing");

  const reportProgress = (stage: ProcessingStage, stageProgress: number) => {
    onProgress?.(stage, stageToOverallProgress(stage, stageProgress));
  };

  try {
    const lastStage = getCheckpoint(sessionId);
    let keyframes: KeyframeInfo[] = [];
    let videoDurationMs = 0;

    // Stage 1: Extract keyframes
    if (!lastStage || lastStage === "keyframes") {
      reportProgress("keyframes", 0);
      videoDurationMs = await getVideoDuration(session.video_file_path);
      keyframes = await extractKeyframes(
        session.video_file_path,
        sessionId
      );
      saveCheckpoint(sessionId, "keyframes");
      reportProgress("keyframes", 100);
    }

    // Stage 2: Detection (black screens + template matching)
    if (!lastStage || lastStage === "keyframes" || lastStage === "detection") {
      reportProgress("detection", 0);

      // Re-load keyframes if resuming
      if (keyframes.length === 0) {
        keyframes = await extractKeyframes(
          session.video_file_path,
          sessionId
        );
        videoDurationMs = await getVideoDuration(session.video_file_path);
      }

      const blackScreenResult = await detectBlackScreens(keyframes);
      const templateMatches = await matchMapEndScreens(
        keyframes,
        TEMPLATE_DIR
      );

      // Store detection results in MMKV for segmentation stage
      storage.setObject(checkpointKey(sessionId, "blackScreens"), blackScreenResult.ranges);
      storage.setObject(checkpointKey(sessionId, "templateMatches"), templateMatches);
      storage.setNumber(checkpointKey(sessionId, "duration"), videoDurationMs);

      saveCheckpoint(sessionId, "detection");
      reportProgress("detection", 100);
    }

    // Stage 3: Segmentation
    if (
      !lastStage ||
      ["keyframes", "detection", "segmentation"].includes(lastStage)
    ) {
      reportProgress("segmentation", 0);

      const blackScreenRanges =
        storage.getObject<TimestampRange[]>(
          checkpointKey(sessionId, "blackScreens")
        ) ?? [];
      const templateMatches =
        storage.getObject<TemplateMatchResult[]>(
          checkpointKey(sessionId, "templateMatches")
        ) ?? [];
      videoDurationMs =
        storage.getNumber(checkpointKey(sessionId, "duration")) ?? 0;

      const segments = segmentVideo(
        blackScreenRanges,
        templateMatches,
        videoDurationMs
      );

      const savedSegments = await insertMapSegments(sessionId, segments);

      // Store segment IDs for result frame extraction
      storage.setObject(
        checkpointKey(sessionId, "segmentIds"),
        savedSegments.map((s) => s.id)
      );
      storage.setObject(
        checkpointKey(sessionId, "segmentData"),
        segments
      );

      saveCheckpoint(sessionId, "segmentation");
      reportProgress("segmentation", 100);
    }

    // Stage 4: Extract result frames
    reportProgress("results", 0);

    const segmentData =
      storage.getObject<MapSegmentData[]>(
        checkpointKey(sessionId, "segmentData")
      ) ?? [];
    const segmentIds =
      storage.getObject<string[]>(
        checkpointKey(sessionId, "segmentIds")
      ) ?? [];
    const processingDir = getProcessingDir(sessionId);

    for (let i = 0; i < segmentData.length; i++) {
      const seg = segmentData[i];
      // Extract result frame ~3 seconds before segment end (scoreboard)
      const frameTimestamp = Math.max(seg.startTimeMs, seg.endTimeMs - 3000);
      const outputPath = `${processingDir}/results/map_${seg.mapIndex}.jpg`;

      try {
        await extractFrameAt(
          session.video_file_path,
          frameTimestamp,
          outputPath
        );

        // Update DB with result frame path
        if (segmentIds[i]) {
          const { updateResultFramePath } = await import("./segmentRepository");
          await updateResultFramePath(segmentIds[i], outputPath);
        }
      } catch {
        // Non-fatal: result frame is optional for Card View
      }

      reportProgress(
        "results",
        Math.round(((i + 1) / segmentData.length) * 100)
      );
    }

    saveCheckpoint(sessionId, "results");

    // Done — mark session ready
    await updateSessionStatus(sessionId, "ready");
    clearCheckpoint(sessionId);
  } catch (error) {
    await updateSessionStatus(sessionId, "error");
    throw error;
  }
}
