import {
  detectBlackScreensInWindow,
  detectGameEventsFallback,
  scanSaturationWindows,
  type FrameSample,
} from "../blackScreenDetector";
import type { DetectionConfig } from "../detectionConfig";
import type { FrameBuffer } from "../../../shared/services/opencv";

const FRAME_SIZE = 16;

function uniformFrame(rgb: [number, number, number]): FrameBuffer {
  const data = new Uint8ClampedArray(FRAME_SIZE * FRAME_SIZE * 3);
  for (let i = 0; i < FRAME_SIZE * FRAME_SIZE; i++) {
    data[i * 3] = rgb[0];
    data[i * 3 + 1] = rgb[1];
    data[i * 3 + 2] = rgb[2];
  }
  return { data, width: FRAME_SIZE, height: FRAME_SIZE };
}

function buildConfig(): DetectionConfig {
  return {
    version: 1,
    reference_resolution: { width: FRAME_SIZE, height: FRAME_SIZE },
    roi_zones: {
      minimap: { x: 0, y: 0, width: 1, height: 1 },
      vertical: { x: 0, y: 0, width: 1, height: 1 },
      team_bar: { x: 0, y: 0, width: FRAME_SIZE, height: FRAME_SIZE },
      kda: { x: 0, y: 0, width: 1, height: 1 },
      notkda: { x: 0, y: 0, width: FRAME_SIZE, height: FRAME_SIZE },
      map_name: { x: 0, y: 0, width: 1, height: 1 },
    },
    thresholds: {
      brightness_threshold: 30,
      start_confirm_frames: 2,
      end_confirm_frames: 2,
      sat_max: 12,
      val_min: 230,
      min_ratio: 0.01,
      // Team-bar saturation must beat 102 to count as "high-sat" gameplay
      // — well above the 8-floor in the impl. Decoupled from min_ratio.
      team_bar_min_sat: 102,
      hud_brightness_max: 100,
      score_offset_s: 14.5,
      collision_threshold: 12,
    },
    maps: {},
  };
}

const black = uniformFrame([0, 0, 0]);
const bright = uniformFrame([200, 200, 200]); // high luma, zero saturation
const colourful = uniformFrame([200, 0, 0]); // high luma, max saturation

function samples(
  frames: FrameBuffer[],
  startMs = 0,
  stepMs = 1000
): FrameSample[] {
  return frames.map((buffer, i) => ({
    timestampMs: startMs + i * stepMs,
    buffer,
  }));
}

describe("scanSaturationWindows", () => {
  it("opens a window over a contiguous run of high-sat frames", () => {
    const stream = samples([black, colourful, colourful, colourful, black]);
    const windows = scanSaturationWindows(stream, { config: buildConfig() });
    expect(windows).toEqual([
      { startIndex: 1, endIndex: 3, startMs: 1000, endMs: 3000 },
    ]);
  });

  it("treats high-luma but zero-saturation (UI menus) as outside a window", () => {
    const stream = samples([bright, bright, bright]);
    expect(scanSaturationWindows(stream, { config: buildConfig() })).toEqual(
      []
    );
  });

  it("closes an open window at end-of-stream", () => {
    const stream = samples([colourful, colourful, colourful]);
    const windows = scanSaturationWindows(stream, { config: buildConfig() });
    expect(windows).toEqual([
      { startIndex: 0, endIndex: 2, startMs: 0, endMs: 2000 },
    ]);
  });
});

describe("detectBlackScreensInWindow", () => {
  it("emits START at the first non-black frame; auto-closes at window end if game still open", () => {
    // Sequence: [black, black, colourful, colourful]. start_confirm_frames=2
    // ⇒ the run of two non-black frames at index 2-3 confirms START at the
    // first non-black frame (ts=2000). The window ends with the game still
    // open, so the impl synthesises END at the last non-black frame.
    const stream = samples([black, black, colourful, colourful]);
    const events = detectBlackScreensInWindow(
      stream,
      { startIndex: 0, endIndex: 3, startMs: 0, endMs: 3000 },
      { config: buildConfig() }
    );
    expect(events).toEqual([
      { type: "START", timestamp_ms: 2000 },
      { type: "END", timestamp_ms: 3000 },
      { type: "SCORE_SCREEN", timestamp_ms: 17500 },
    ]);
  });

  it("does not emit START on a single non-black frame at the window edge (confirm-gate)", () => {
    // A single colourful frame at the start of the window followed by black
    // is not a real game start — start_confirm_frames=2 should prevent the
    // FSM from firing on the lone bright frame at index 0. Regression guard
    // for the pre-fix behavior where `undetermined` immediately emitted.
    const stream = samples([colourful, black, black]);
    const events = detectBlackScreensInWindow(
      stream,
      { startIndex: 0, endIndex: 2, startMs: 0, endMs: 2000 },
      { config: buildConfig() }
    );
    expect(events).toEqual([]);
  });

  it("emits START + END + SCORE_SCREEN across a black → game → black arc", () => {
    // Seeded with one black frame, then 3 non-black, then 2 black. The first
    // non-black at ts=1000 is the START (the second non-black at ts=2000
    // confirms after start_confirm_frames=2). END is the last non-black
    // (ts=3000) once 2 consecutive black frames confirm the transition out.
    const stream = samples([black, colourful, colourful, colourful, black, black]);
    const events = detectBlackScreensInWindow(
      stream,
      { startIndex: 0, endIndex: 5, startMs: 0, endMs: 5000 },
      { config: buildConfig() }
    );
    expect(events).toEqual([
      { type: "START", timestamp_ms: 1000 },
      { type: "END", timestamp_ms: 3000 },
      { type: "SCORE_SCREEN", timestamp_ms: 17500 },
    ]);
  });
});

describe("detectGameEventsFallback", () => {
  it("yields zero events for a video with no high-sat content", () => {
    const stream = samples([black, bright, black, bright]);
    expect(
      detectGameEventsFallback(stream, { config: buildConfig() })
    ).toEqual([]);
  });
});
