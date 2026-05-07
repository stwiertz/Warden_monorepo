// Story 7.5 — Game state detector.
//
// Reads the kda + notkda ROIs of each frame and runs a 2-state machine that
// emits START / END / SCORE_SCREEN events:
//   - kda ROI must contain ≥ min_ratio fraction of "near-white" pixels
//     (sat ≤ sat_max AND val ≥ val_min in HSV-8U) — that is, the KDA digits
//     of the gameplay HUD are visible.
//   - notkda ROI mean grayscale must be < hud_brightness_max — i.e. the dark
//     HUD strip is on screen, not a bright menu/lobby.
// Both conditions must hold to count the frame as "in game".
//
// The state machine debounces noisy frames via start_confirm_frames /
// end_confirm_frames: a transition only fires after that many consecutive
// frames agree. START is timestamped at the FIRST confirming frame; END is
// timestamped at the LAST in-game frame seen before the run of off frames.
// On END the detector also emits a SCORE_SCREEN event at endTs + score_offset_s.
//
// The detector is stateful and per-session; create one with createGameDetector
// and feed frames in chronological order via processFrame.

import type { DetectionConfig } from "./detectionConfig";
import type { GameDetectorEvent } from "./types";
import {
  grayscaleMean,
  hsvWhitePixelRatio,
  scaleRoi,
  type FrameBuffer,
  type Resolution,
} from "../../shared/services/opencv";

export type GameState = "not_in_game" | "in_game";

export interface GameDetectorOptions {
  config: DetectionConfig;
  // Resolution of the FrameBuffers fed to processFrame. Defaults to the
  // config's reference resolution, in which case ROIs are used as-is.
  processingResolution?: Resolution;
}

export interface GameDetector {
  processFrame(frame: FrameBuffer, timestampMs: number): GameDetectorEvent[];
  // Called when no more frames will be supplied. If the detector is still in
  // "in_game" at that moment, emit a synthetic END (+ SCORE_SCREEN) at the
  // last-seen in-game timestamp so we don't drop a trailing segment.
  flush(): GameDetectorEvent[];
  getState(): GameState;
}

export function createGameDetector(opts: GameDetectorOptions): GameDetector {
  const { config } = opts;
  const refRes = config.reference_resolution;
  const procRes = opts.processingResolution ?? refRes;
  const kdaRoi = scaleRoi(config.roi_zones.kda, refRes, procRes);
  const notkdaRoi = scaleRoi(config.roi_zones.notkda, refRes, procRes);

  const startConfirm = Math.max(1, Math.floor(config.thresholds.start_confirm_frames));
  const endConfirm = Math.max(1, Math.floor(config.thresholds.end_confirm_frames));
  const satMax = config.thresholds.sat_max;
  const valMin = config.thresholds.val_min;
  const minRatio = config.thresholds.min_ratio;
  const hudBrightnessMax = config.thresholds.hud_brightness_max;
  const scoreOffsetMs = Math.round(config.thresholds.score_offset_s * 1000);

  let state: GameState = "not_in_game";
  let pending: GameState | null = null;
  let pendingCount = 0;
  let pendingFirstTs = 0; // timestamp of the first frame in the pending run
  let lastInGameTs = 0; // timestamp of the last frame the detector classified in-game

  function classify(frame: FrameBuffer): GameState {
    const ratio = hsvWhitePixelRatio(frame, kdaRoi, satMax, valMin);
    const hudGray = grayscaleMean(frame, notkdaRoi);
    return ratio >= minRatio && hudGray < hudBrightnessMax
      ? "in_game"
      : "not_in_game";
  }

  function processFrame(
    frame: FrameBuffer,
    timestampMs: number
  ): GameDetectorEvent[] {
    const observed = classify(frame);

    if (observed === state) {
      // Reset any in-flight transition: we got a frame that confirms the
      // current state, so the previous candidate run is no longer credible.
      pending = null;
      pendingCount = 0;
      if (state === "in_game") lastInGameTs = timestampMs;
      return [];
    }

    if (pending !== observed) {
      pending = observed;
      pendingCount = 1;
      pendingFirstTs = timestampMs;
    } else {
      pendingCount++;
    }

    const required = observed === "in_game" ? startConfirm : endConfirm;
    if (pendingCount < required) {
      return [];
    }

    if (observed === "in_game") {
      // Transition into in_game: fire START at the first confirming frame.
      state = "in_game";
      lastInGameTs = timestampMs;
      pending = null;
      pendingCount = 0;
      return [{ type: "START", timestamp_ms: pendingFirstTs }];
    }

    // Transition out: END is the last in-game frame's timestamp.
    state = "not_in_game";
    pending = null;
    pendingCount = 0;
    const endTs = lastInGameTs;
    return [
      { type: "END", timestamp_ms: endTs },
      { type: "SCORE_SCREEN", timestamp_ms: endTs + scoreOffsetMs },
    ];
  }

  function flush(): GameDetectorEvent[] {
    if (state !== "in_game") return [];
    const endTs = lastInGameTs;
    state = "not_in_game";
    pending = null;
    pendingCount = 0;
    return [
      { type: "END", timestamp_ms: endTs },
      { type: "SCORE_SCREEN", timestamp_ms: endTs + scoreOffsetMs },
    ];
  }

  return {
    processFrame,
    flush,
    getState: () => state,
  };
}

/**
 * Pair START and END events into game segments. Robust to extra START or
 * END events (drops unmatched ones) and to flushed end-of-stream END.
 * SCORE_SCREEN events are recorded alongside their parent segment so the
 * orchestrator knows where to extract the result frame.
 */
export interface GameSegmentTimeline {
  startMs: number;
  endMs: number;
  scoreScreenMs: number;
}

export function pairEventsIntoSegments(
  events: GameDetectorEvent[]
): GameSegmentTimeline[] {
  const segments: GameSegmentTimeline[] = [];
  let openStart: number | null = null;
  let pendingEnd: number | null = null;

  for (const ev of events) {
    if (ev.type === "START") {
      // A second START with no END in between: keep the earliest one (that
      // matches the "first confirming frame" semantics from the detector).
      if (openStart === null) openStart = ev.timestamp_ms;
    } else if (ev.type === "END") {
      pendingEnd = ev.timestamp_ms;
    } else if (ev.type === "SCORE_SCREEN") {
      if (openStart !== null && pendingEnd !== null) {
        segments.push({
          startMs: openStart,
          endMs: pendingEnd,
          scoreScreenMs: ev.timestamp_ms,
        });
        openStart = null;
        pendingEnd = null;
      }
    }
  }

  // If an END was emitted without a trailing SCORE_SCREEN (shouldn't happen
  // with the detector above, but defend against malformed event streams),
  // close the segment with no score-screen offset.
  if (openStart !== null && pendingEnd !== null) {
    segments.push({
      startMs: openStart,
      endMs: pendingEnd,
      scoreScreenMs: pendingEnd,
    });
  }

  return segments;
}
