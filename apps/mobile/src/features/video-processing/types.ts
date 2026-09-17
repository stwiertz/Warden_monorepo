// Story 12.4c removed three shapes that the engine rewrite left with no
// producer and no consumer:
//   * `KeyframeInfo` — the pipeline no longer extracts keyframes to disk, so
//     there is no `{ path, timestampMs }` pair to pass around. Keyframes exist
//     only inside the native call now.
//   * `BlackScreenResult` / `TimestampRange` — the long-GOP black-screen
//     fallback is gone with `blackScreenDetector.ts` (AC0e).
//   * `ProcessingState` and `GameSegment` — already dead before this story
//     (verified unused in production `src`; `GameSegment` was superseded by
//     `GameSegmentTimeline`).

export interface MapSegmentData {
  mapIndex: number;
  startTimeMs: number;
  endTimeMs: number;
  mapName: string | null;
  resultFramePath: string | null;
}

/**
 * 🔴 `"keyframes"` IS GONE (Story 12.4c). Extraction and detection collapsed
 * into one native call, so there is no stage in which keyframes are produced but
 * not yet evaluated. The remaining three are the real boundaries, and they are
 * also the keys the foreground-service notification maps to French copy — the
 * TS<->Kotlin stage contract in `plugins/with-foreground-service.js` moves with
 * this type.
 */
export type ProcessingStage = "detection" | "segmentation" | "results";

export interface ProgressCallback {
  (stage: ProcessingStage, stageProgress: number): void;
}

// Story 12.4c — the v2 engine's outputs.
//
// `GameDetectorEvent` (START / END / SCORE_SCREEN) is gone with the debounced
// two-state FSM that emitted it. The phase machine resolves a STATE per keyframe
// and spans are cut from the internal states, so there is no event stream to
// pair — which also removes `pairEventsIntoSegments` and the malformed-stream
// defences it needed.

export interface MapIdentificationResult {
  /** Index into the GameSegmentTimeline[] array. */
  segmentIndex: number;
  /** The map slug, or `null` for unknown (mobile-AUTO-SLICE-003). */
  mapName: string | null;
  /**
   * The winning RAW weighted aggregate over the span, or the best below-threshold
   * score when `mapName` is null.
   *
   * 🔴 NOT a probability and NOT an accuracy. With all 134 shipped rules at
   * weight 1.0 this is a COUNT of (zone, keyframe) fires, so it grows with match
   * length. It ranks maps within one span; it does not compare across spans, and
   * it says nothing about REL-006.
   */
  confidence: number;
  /** The span this verdict covers, in keyframe indices. Diagnosis only. */
  startFrame: number;
  endFrame: number;
}
