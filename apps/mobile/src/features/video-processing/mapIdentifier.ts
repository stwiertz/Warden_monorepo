// Story 12.4c (AC6) — the map identifier, rewritten onto v2 ROI/HSV scoring.
//
// 🔴 WHAT THIS REPLACED. Until 12.4c this was Story 7.5's pHash matcher: crop
// the v1 `map_name` ROI, grayscale it, DCT-hash it to 64 bits and Hamming-compare
// against `DetectionConfig.maps` (slug -> 16 hex chars) under
// `thresholds.collision_threshold`. None of those inputs exist in the v2 schema,
// and it is the reason auto-slice produced `unknown` map labels on HUD 2.0
// footage (`epics-and-stories.md:2748`) — which is the whole point of this story.
//
// What replaces it is the RAW WEIGHTED AGGREGATE over
// `minimap_identification.maps.<slug>.zones`, against `identification_threshold`
// (0.6). The per-frame half is `scoreFromFires` (engineScoring.ts); this module
// owns the per-SPAN half: a match gets ONE map label, aggregated over its
// keyframes, so a single bad keyframe cannot relabel a match.
//
// 🔴 `minimap_identification.roi` IS IGNORED — Story 9.15's D2, escalated into
// 12.1 as AC13b. Zones carry their own ABSOLUTE coordinates; the shared ROI is
// authoring metadata for the zone picker. Nothing in this file or in the packer
// reads it.
//
// 🔴 TWO DIFFERENT ARGMAXES, DELIBERATELY, because Tool 12 has two:
//   * PER FRAME — `_argmax_with_threshold`: threshold gate, tie-break by zone
//     count then `MAP_LABELS` order (`scoring.py`).
//   * PER SPAN — Python's plain `max()` over the aggregate dict, which resolves
//     a tie to the FIRST key in CONFIG order (`__main__.py:_run_video`).
// Reproducing one of them twice would silently change the other's answers, so
// both are here and both are labelled.

import type { ClassifierConfig } from "./mapConfig";
import { UNKNOWN } from "./engineScoring";

export { MAP_LABELS } from "./engineScoring";

/** One span's map verdict. `mapName === null` IS the `unknown` outcome. */
export interface MapIdentification {
  /**
   * The identified map slug, or `null` for unknown.
   *
   * 🔴 `null`, NOT the string `"unknown"`. `mobile-AUTO-SLICE-003` words it as
   * `map_name = "unknown"`, and on this surface that value is spelled `null`:
   * `map_segments.map_name` is a nullable column, `MapSegmentData.mapName` is
   * `string | null`, and Card View renders the null as "Unknown map" (Story 2.5
   * AC4). Writing the literal would put a fake map slug in the database.
   */
  mapName: string | null;
  /** The winning aggregate, or the best score below threshold. */
  confidence: number;
  /** Every scored map's aggregate over the span, for diagnosis. */
  scores: Record<string, number>;
}

/**
 * Sum the per-frame map aggregates over a span, in place of re-scoring.
 *
 * Tool 12's `_run_video` does exactly this: `map_agg` rows are summed for the
 * frames inside `[start, end]`. With today's uniform weights that makes the
 * span score a COUNT of (zone, frame) fires, so a 4-keyframe match on a 17-zone
 * map scores ~68 — which is why the 0.6 threshold is near-inert at span level
 * too, and why this is a ranking, not a probability.
 */
export function aggregateSpanScores(
  perFrameScores: readonly Record<string, number>[],
  startFrame: number,
  endFrame: number
): Record<string, number> {
  const agg: Record<string, number> = {};
  for (let i = startFrame; i <= endFrame && i < perFrameScores.length; i++) {
    for (const [slug, value] of Object.entries(perFrameScores[i])) {
      agg[slug] = (agg[slug] ?? 0) + value;
    }
  }
  return agg;
}

/**
 * A span's aggregate -> its map label.
 *
 * Tie-break is CONFIG ORDER (the first key of the aggregate object), matching
 * Python's `max(agg, key=agg.get)` in `_run_video`. `Object.entries` preserves
 * insertion order, and the aggregate is built by iterating the per-frame scores,
 * which come from `cfg.mapZoneCounts` in config order — so the two agree.
 *
 * Below `identification_threshold` -> unknown (`mobile-AUTO-SLICE-003`). A
 * zero aggregate is unknown even when the threshold is 0: nothing fired, so
 * there is nothing to identify. Tool 12's `_run_video` would return its first
 * config key with confidence 0 in that case; labelling a match `artefact`
 * because no zone fired is precisely the "forced to the nearest class" E4
 * forbids, so this is a deliberate, narrow divergence — and it is the ONLY one.
 */
export function identifySpanMap(
  agg: Record<string, number>,
  cfg: Pick<ClassifierConfig, "identificationThreshold">
): MapIdentification {
  let best: string | null = null;
  let bestScore = 0;
  for (const [slug, score] of Object.entries(agg)) {
    if (best === null || score > bestScore) {
      best = slug;
      bestScore = score;
    }
  }
  if (best === null || bestScore <= 0 || bestScore < cfg.identificationThreshold) {
    return { mapName: null, confidence: bestScore, scores: agg };
  }
  return { mapName: best, confidence: bestScore, scores: agg };
}

/** Human-readable label for logs. `UNKNOWN` is the tooling's spelling. */
export function mapLabelForLog(id: MapIdentification): string {
  return id.mapName ?? UNKNOWN;
}
