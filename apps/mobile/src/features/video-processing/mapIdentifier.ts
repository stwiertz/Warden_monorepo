// Story 7.5 — pHash-based map identifier.
//
// Per AC 7+8: extract the map_name ROI mid-segment, grayscale it, resize to
// the canvas size, compute a 64-bit perceptual hash, and Hamming-compare
// against every fingerprint in DetectionConfig.maps. The lowest-distance
// match below collision_threshold wins; if no map is close enough, return
// null (the segment becomes "Unknown map" in Card View per Story 2.5 AC 4).
//
// pHash is implemented in src/shared/services/opencv.ts as a pure-TS
// primitive — no native dep. The map identifier is itself a thin
// orchestration layer over the primitives so it stays trivial to test.

import type { DetectionConfig } from "./detectionConfig";
import {
  cropToGrayscale,
  hammingDistance,
  phash,
  scaleRoi,
  type FrameBuffer,
  type Resolution,
} from "../../shared/services/opencv";

export interface MapIdentifierOptions {
  config: DetectionConfig;
  processingResolution?: Resolution;
}

export interface MapMatch {
  mapName: string;
  hammingDistance: number;
}

export interface MapIdentificationOutcome {
  hash: string;
  match: MapMatch | null;
}

export interface MapIdentifier {
  identify(frame: FrameBuffer): MapIdentificationOutcome;
}

export function createMapIdentifier(opts: MapIdentifierOptions): MapIdentifier {
  const { config } = opts;
  const refRes = config.reference_resolution;
  const procRes = opts.processingResolution ?? refRes;
  const mapNameRoi = scaleRoi(config.roi_zones.map_name, refRes, procRes);
  const collisionThreshold = config.thresholds.collision_threshold;
  const fingerprints = Object.entries(config.maps);

  function identify(frame: FrameBuffer): MapIdentificationOutcome {
    const gray = cropToGrayscale(frame, mapNameRoi);
    const hash = phash(gray);

    let best: MapMatch | null = null;
    for (const [mapName, fingerprint] of fingerprints) {
      let dist: number;
      try {
        dist = hammingDistance(hash, fingerprint);
      } catch {
        // Mismatched lengths or non-hex — skip the entry. Logged at the
        // caller via the warning path in AC 8.
        continue;
      }
      if (dist > collisionThreshold) continue;
      if (best === null || dist < best.hammingDistance) {
        best = { mapName, hammingDistance: dist };
      }
    }

    return { hash, match: best };
  }

  return { identify };
}
