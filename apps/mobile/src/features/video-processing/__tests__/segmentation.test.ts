// Pure-data segmentation glue used by processingPipeline.ts. Lives in
// segmentation.ts so this test doesn't drag in expo-sqlite / firebase via
// the pipeline's import chain.

import { buildMapSegments } from "../segmentation";
import type { GameSegmentTimeline } from "../gameDetector";
import type { MapIdentificationResult } from "../types";

describe("buildMapSegments", () => {
  it("attaches map identifications to segments by index", () => {
    const segments: GameSegmentTimeline[] = [
      { startMs: 1000, endMs: 5000, scoreScreenMs: 19500 },
      { startMs: 25000, endMs: 30000, scoreScreenMs: 44500 },
    ];
    // Story 12.4c: the identification rows carry the span's RAW weighted
    // aggregate and the keyframe range it covers, not a pHash and a Hamming
    // distance. `mapName: null` is still how `unknown` is spelled.
    const ids: MapIdentificationResult[] = [
      { segmentIndex: 0, mapName: "atlantis", confidence: 44, startFrame: 1, endFrame: 4 },
      { segmentIndex: 1, mapName: null, confidence: 0, startFrame: 7, endFrame: 9 },
    ];
    expect(buildMapSegments(segments, ids)).toEqual([
      {
        mapIndex: 0,
        startTimeMs: 1000,
        endTimeMs: 5000,
        mapName: "atlantis",
        resultFramePath: null,
      },
      {
        mapIndex: 1,
        startTimeMs: 25000,
        endTimeMs: 30000,
        mapName: null,
        resultFramePath: null,
      },
    ]);
  });

  it("leaves mapName null when no identification was supplied for an index", () => {
    const segments: GameSegmentTimeline[] = [
      { startMs: 1000, endMs: 5000, scoreScreenMs: 19500 },
    ];
    expect(buildMapSegments(segments, [])).toEqual([
      {
        mapIndex: 0,
        startTimeMs: 1000,
        endTimeMs: 5000,
        mapName: null,
        resultFramePath: null,
      },
    ]);
  });
});
