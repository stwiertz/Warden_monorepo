// Pure-data segmentation helpers used by processingPipeline.ts.
//
// Lives in a standalone module (rather than inside processingPipeline.ts) so
// tests can exercise the logic without dragging in expo-sqlite, expo-file-
// system, or firebase via the pipeline's import chain. Story 2.5 is expected
// to grow this module — for now it owns just the pieces 7.5 needs.

import type { GameSegmentTimeline } from "./gameDetector";
import type { MapIdentificationResult, MapSegmentData } from "./types";

/**
 * Combine game segments with their per-segment map identifications into the row
 * shape segmentRepository persists.
 *
 * Story 12.4c changed where both inputs come from, not what this does:
 *   * the segments are cut from the phase machine's INTERNAL states, so a
 *     doubtful keyframe mid-match does not split one match into two rows;
 *   * the score screen is TIMING-derived from `score_screen_duration_ms` rather
 *     than detected as a class, and it lives on the segment, not here;
 *   * `mapName` is null when the span's aggregate did not clear
 *     `identification_threshold` — that null IS `mobile-AUTO-SLICE-003`'s
 *     `map_name = "unknown"` on this surface, and Card View renders it as
 *     "Unknown map" with navigation intact (REL-006: graceful degradation, not a
 *     blocking error).
 *
 * `mobile-AUTO-SLICE-004` still holds: lobby and transition are merged into
 * `not_in_match` by design, so neither ever becomes a row.
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
