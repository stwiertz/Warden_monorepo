// Story 7.5 — Long-GOP black-screen fallback detector.
//
// When ffprobe reports a keyframe interval > 2s on the source video, the
// KDA-based gameDetector loses temporal precision (it only sees frames every
// 2+ seconds). In that case the pipeline switches to this two-pass black-
// screen detector, which is more tolerant of sparse keyframes:
//
//   Pass 1 (`scanSaturationWindows`)
//     Walk every I-frame and read the mean saturation of the `team_bar`
//     ROI. Windows where saturation stays above `min_ratio * 255` are
//     candidate gameplay regions; the contiguous "high-sat" runs become
//     [start, end] windows on which Pass 2 runs.
//
//   Pass 2 (`detectBlackScreensInWindow`)
//     A 3-state debouncer applied only to frames inside a Pass-1 window:
//       - `undetermined`: initial state until we know whether the run
//         starts inside or outside a game.
//       - `waiting_for_start`: outside a game, waiting for the first bright
//         non-black frame (game START at that timestamp).
//       - `waiting_for_end`: inside a game, waiting for the next sustained
//         black screen (game END at the timestamp before black began).
//     Sustained = `start_confirm_frames` consecutive non-black or black
//     frames respectively, mirroring the gameDetector debouncing.
//
// Frame brightness is read from `notkda` ROI grayscale mean — the same
// signal the gameDetector uses, so config tuning carries over.

import type { DetectionConfig } from "./detectionConfig";
import type {
  GameDetectorEvent,
  KeyframeInfo,
  TimestampRange,
} from "./types";
import {
  grayscaleMean,
  saturationMean,
  scaleRoi,
  type FrameBuffer,
  type Resolution,
} from "../../shared/services/opencv";

// Re-exported only because legacy callers in pre-7.5 code paths imported it
// as the constant name. Story 7.5 sources every threshold from DetectionConfig.
export const BLACK_SCREEN_LUMINOSITY_THRESHOLD = 15;

export interface BlackScreenDetectorOptions {
  config: DetectionConfig;
  processingResolution?: Resolution;
}

export interface SaturationWindow {
  startIndex: number; // inclusive, into the keyframes array
  endIndex: number; // inclusive
  startMs: number;
  endMs: number;
}

export interface FrameSample {
  timestampMs: number;
  buffer: FrameBuffer;
}

/**
 * Pass 1 (pure-data variant) — given a per-keyframe saturation array and
 * the matching keyframe timeline, return contiguous high-saturation runs.
 * Pulled out so the streaming pipeline can compute `satValues` on the fly
 * (one float per keyframe, no buffer retention) instead of materialising
 * a FrameSample[] for the whole video.
 *
 * `satValues.length` MUST equal `keyframes.length`. Both arrays MUST be
 * sorted by timestamp.
 */
export function buildSaturationWindowsFromValues(
  satValues: number[],
  keyframes: KeyframeInfo[],
  config: DetectionConfig
): SaturationWindow[] {
  // Clamp to a sensible floor so a too-loose config can't open a single
  // window covering the entire video.
  const satThreshold = Math.max(8, config.thresholds.team_bar_min_sat);
  const windows: SaturationWindow[] = [];
  let runStart: number | null = null;

  for (let i = 0; i < satValues.length; i++) {
    const isHigh = satValues[i] >= satThreshold;
    if (isHigh && runStart === null) {
      runStart = i;
    } else if (!isHigh && runStart !== null) {
      windows.push({
        startIndex: runStart,
        endIndex: i - 1,
        startMs: keyframes[runStart].timestampMs,
        endMs: keyframes[i - 1].timestampMs,
      });
      runStart = null;
    }
  }
  if (runStart !== null) {
    windows.push({
      startIndex: runStart,
      endIndex: satValues.length - 1,
      startMs: keyframes[runStart].timestampMs,
      endMs: keyframes[satValues.length - 1].timestampMs,
    });
  }

  return windows;
}

/**
 * Pass 1 — find contiguous runs of high-saturation keyframes via the
 * `team_bar` ROI. Used to narrow Pass-2 to the regions of the video where
 * gameplay HUD is plausibly on screen.
 *
 * `samples` MUST be sorted by timestampMs. The output windows are also
 * sorted and non-overlapping.
 */
export function scanSaturationWindows(
  samples: FrameSample[],
  opts: BlackScreenDetectorOptions
): SaturationWindow[] {
  const { config } = opts;
  const refRes = config.reference_resolution;
  const procRes = opts.processingResolution ?? refRes;
  const teamBarRoi = scaleRoi(config.roi_zones.team_bar, refRes, procRes);

  const satValues = samples.map((s) => saturationMean(s.buffer, teamBarRoi));
  const keyframes: KeyframeInfo[] = samples.map((s) => ({
    path: "",
    timestampMs: s.timestampMs,
  }));
  return buildSaturationWindowsFromValues(satValues, keyframes, config);
}

/**
 * Pass 2 — run the 3-state black-screen debouncer over the keyframes inside
 * a single Pass-1 window. Emits START / END / SCORE_SCREEN events with the
 * same shape as the primary gameDetector, so the orchestrator can merge
 * outputs from either path uniformly.
 */
export function detectBlackScreensInWindow(
  samples: FrameSample[],
  window: SaturationWindow,
  opts: BlackScreenDetectorOptions
): GameDetectorEvent[] {
  const { config } = opts;
  const refRes = config.reference_resolution;
  const procRes = opts.processingResolution ?? refRes;
  const notkdaRoi = scaleRoi(config.roi_zones.notkda, refRes, procRes);
  const brightnessThreshold = config.thresholds.brightness_threshold;
  const startConfirm = Math.max(1, Math.floor(config.thresholds.start_confirm_frames));
  const scoreOffsetMs = Math.round(config.thresholds.score_offset_s * 1000);

  type FsmState = "undetermined" | "waiting_for_start" | "waiting_for_end";
  let state: FsmState = "undetermined";
  let runKind: "black" | "non-black" | null = null;
  let runCount = 0;
  let runFirstTs = 0;
  let lastNonBlackTs = 0;

  const events: GameDetectorEvent[] = [];

  for (let i = window.startIndex; i <= window.endIndex; i++) {
    const sample = samples[i];
    const brightness = grayscaleMean(sample.buffer, notkdaRoi);
    const isBlack = brightness < brightnessThreshold;
    const observed: "black" | "non-black" = isBlack ? "black" : "non-black";

    // Bookkeeping shared by all branches — used to time END events.
    if (observed === "non-black") lastNonBlackTs = sample.timestampMs;

    // Accumulate or reset the streak of like-kind frames. Same gating as
    // gameDetector: every transition (including the FSM seed in the
    // `undetermined` state) waits for `start_confirm_frames` consecutive
    // observations before it fires, so a single noisy frame at a window
    // edge never produces a false START.
    if (runKind !== observed) {
      runKind = observed;
      runCount = 1;
      runFirstTs = sample.timestampMs;
    } else {
      runCount++;
    }

    if (runCount < startConfirm) continue;

    if (state === "undetermined") {
      // Sustained run at the front of the window seeds the FSM. Non-black
      // ⇒ we're inside a game (emit START at the run's first ts); black
      // ⇒ we're between games (no event, just transition).
      if (observed === "non-black") {
        state = "waiting_for_end";
        events.push({ type: "START", timestamp_ms: runFirstTs });
      } else {
        state = "waiting_for_start";
      }
      runKind = null;
      runCount = 0;
      continue;
    }

    if (state === "waiting_for_start" && observed === "non-black") {
      // Sustained brightness in a region we believed to be off — game START.
      state = "waiting_for_end";
      events.push({ type: "START", timestamp_ms: runFirstTs });
      runKind = null;
      runCount = 0;
      continue;
    }

    if (state === "waiting_for_end" && observed === "black") {
      // Sustained black inside a game — END at the last non-black frame.
      state = "waiting_for_start";
      const endTs = lastNonBlackTs;
      events.push({ type: "END", timestamp_ms: endTs });
      events.push({
        type: "SCORE_SCREEN",
        timestamp_ms: endTs + scoreOffsetMs,
      });
      runKind = null;
      runCount = 0;
      continue;
    }
  }

  // Window ended while we were inside a game — synthesise END at the last
  // observed non-black frame so the segment is closed.
  if (state === "waiting_for_end") {
    const endTs = lastNonBlackTs;
    events.push({ type: "END", timestamp_ms: endTs });
    events.push({
      type: "SCORE_SCREEN",
      timestamp_ms: endTs + scoreOffsetMs,
    });
  }

  return events;
}

/**
 * Convenience wrapper: run the full two-pass fallback over a sequence of
 * keyframe samples. Delegates to scanSaturationWindows + per-window
 * detectBlackScreensInWindow.
 */
export function detectGameEventsFallback(
  samples: FrameSample[],
  opts: BlackScreenDetectorOptions
): GameDetectorEvent[] {
  const windows = scanSaturationWindows(samples, opts);
  const all: GameDetectorEvent[] = [];
  for (const w of windows) {
    all.push(...detectBlackScreensInWindow(samples, w, opts));
  }
  return all;
}

/**
 * Legacy helper retained for the pre-7.5 segmentation path used by
 * processingPipeline.ts checkpoints. Converts a series of black-screen
 * windows from a frame sample stream into TimestampRange[]. Story 2.5
 * removes the last call site once the new segmentation lands.
 */
export function blackScreenRangesFromSamples(
  samples: FrameSample[],
  opts: BlackScreenDetectorOptions
): TimestampRange[] {
  const { config } = opts;
  const refRes = config.reference_resolution;
  const procRes = opts.processingResolution ?? refRes;
  const notkdaRoi = scaleRoi(config.roi_zones.notkda, refRes, procRes);
  const brightnessThreshold = config.thresholds.brightness_threshold;
  const ranges: TimestampRange[] = [];
  let openStart: number | null = null;
  let lastBlackTs = 0;

  for (const s of samples) {
    const isBlack =
      grayscaleMean(s.buffer, notkdaRoi) < brightnessThreshold;
    if (isBlack && openStart === null) {
      openStart = s.timestampMs;
      lastBlackTs = s.timestampMs;
    } else if (isBlack) {
      lastBlackTs = s.timestampMs;
    } else if (!isBlack && openStart !== null) {
      ranges.push({ startMs: openStart, endMs: lastBlackTs });
      openStart = null;
    }
  }
  if (openStart !== null) ranges.push({ startMs: openStart, endMs: lastBlackTs });
  return ranges;
}
