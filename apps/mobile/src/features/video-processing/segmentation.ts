// Pure-data segmentation helpers used by processingPipeline.ts.
//
// Lives in a standalone module (rather than inside processingPipeline.ts) so
// tests can exercise the logic without dragging in expo-sqlite, expo-file-
// system, or firebase via the pipeline's import chain. Story 2.5 is expected
// to grow this module — for now it owns just the pieces 7.5 needs.

import type { GameSegmentTimeline } from "./gameDetector";
import type { MapIdentificationResult, MapSegmentData } from "./types";

/**
 * Combine paired game segments with their per-segment map identifications
 * into the row shape segmentRepository persists. `mapName` is null when the
 * identifier returned no fingerprint within the collision threshold.
 */
export function buildMapSegments(
  segments: GameSegmentTimeline[],
  identifications: MapIdentificationResult[]
): MapSegmentData[] {
  const idByIndex = new Map<number, MapIdentificationResult>();
  for (const id of identifications) idByIndex.set(id.segmentIndex, id);

  return segments.map((seg, i) => ({
    mapIndex: i,
    startTimeMs: seg.startMs,
    endTimeMs: seg.endMs,
    mapName: idByIndex.get(i)?.mapName ?? null,
    resultFramePath: null,
  }));
}
