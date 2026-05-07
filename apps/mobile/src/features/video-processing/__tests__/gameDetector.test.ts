import {
  createGameDetector,
  pairEventsIntoSegments,
} from "../gameDetector";
import type { DetectionConfig } from "../detectionConfig";
import type { FrameBuffer } from "../../../shared/services/opencv";
import type { GameDetectorEvent } from "../types";

// Build a 16x16 RGB frame. The kda ROI lives in the top-left 8x8, the
// notkda ROI in the bottom-right 8x8 — so we can independently set them.
const FRAME_SIZE = 16;

function buildFrame(opts: {
  kdaWhite: boolean; // top-left 8x8 white-on-black or all dark
  notkdaDark: boolean; // bottom-right 8x8 dark or bright
}): FrameBuffer {
  const data = new Uint8ClampedArray(FRAME_SIZE * FRAME_SIZE * 3);
  for (let y = 0; y < FRAME_SIZE; y++) {
    for (let x = 0; x < FRAME_SIZE; x++) {
      const i = (y * FRAME_SIZE + x) * 3;
      const inKda = x < 8 && y < 8;
      const inNotkda = x >= 8 && y >= 8;
      let v = 0;
      if (inKda && opts.kdaWhite) v = 255;
      else if (inNotkda) v = opts.notkdaDark ? 30 : 200;
      data[i] = v;
      data[i + 1] = v;
      data[i + 2] = v;
    }
  }
  return { data, width: FRAME_SIZE, height: FRAME_SIZE };
}

function buildConfig(overrides?: Partial<DetectionConfig["thresholds"]>): DetectionConfig {
  return {
    version: 1,
    reference_resolution: { width: FRAME_SIZE, height: FRAME_SIZE },
    roi_zones: {
      minimap: { x: 0, y: 0, width: 1, height: 1 },
      vertical: { x: 0, y: 0, width: 1, height: 1 },
      team_bar: { x: 0, y: 0, width: 1, height: 1 },
      kda: { x: 0, y: 0, width: 8, height: 8 },
      notkda: { x: 8, y: 8, width: 8, height: 8 },
      map_name: { x: 0, y: 0, width: 1, height: 1 },
    },
    thresholds: {
      brightness_threshold: 15,
      start_confirm_frames: 2,
      end_confirm_frames: 3,
      sat_max: 12,
      val_min: 230,
      min_ratio: 0.01,
      team_bar_min_sat: 25,
      hud_brightness_max: 100,
      score_offset_s: 14.5,
      collision_threshold: 12,
      ...overrides,
    },
    maps: {},
  };
}

const inGame = buildFrame({ kdaWhite: true, notkdaDark: true });
const offGame = buildFrame({ kdaWhite: false, notkdaDark: false });

describe("createGameDetector", () => {
  it("emits no events on the very first in-game frame (start_confirm_frames=2)", () => {
    const detector = createGameDetector({ config: buildConfig() });
    const events = detector.processFrame(inGame, 1000);
    expect(events).toEqual([]);
    expect(detector.getState()).toBe("not_in_game");
  });

  it("emits START at the first confirming frame after start_confirm_frames consecutive in-game frames", () => {
    const detector = createGameDetector({ config: buildConfig() });
    expect(detector.processFrame(inGame, 1000)).toEqual([]);
    const events = detector.processFrame(inGame, 2000);
    expect(events).toEqual([{ type: "START", timestamp_ms: 1000 }]);
    expect(detector.getState()).toBe("in_game");
  });

  it("does NOT emit START when the candidate run is broken before confirm_frames is reached", () => {
    const detector = createGameDetector({ config: buildConfig() });
    expect(detector.processFrame(inGame, 1000)).toEqual([]);
    // off frame breaks the run
    expect(detector.processFrame(offGame, 1500)).toEqual([]);
    expect(detector.processFrame(inGame, 2000)).toEqual([]);
    // Two consecutive in-game now from 2000 ⇒ START at 2000
    expect(detector.processFrame(inGame, 3000)).toEqual([
      { type: "START", timestamp_ms: 2000 },
    ]);
  });

  it("emits END+SCORE_SCREEN at the last in-game timestamp after end_confirm_frames consecutive off frames", () => {
    const detector = createGameDetector({ config: buildConfig() });
    detector.processFrame(inGame, 1000);
    detector.processFrame(inGame, 2000); // → START @ 1000
    detector.processFrame(inGame, 3000); // last in-game @ 3000
    expect(detector.processFrame(offGame, 4000)).toEqual([]);
    expect(detector.processFrame(offGame, 5000)).toEqual([]);
    const events = detector.processFrame(offGame, 6000);
    expect(events).toEqual([
      { type: "END", timestamp_ms: 3000 },
      // 3000 + 14.5*1000 = 17500
      { type: "SCORE_SCREEN", timestamp_ms: 17500 },
    ]);
    expect(detector.getState()).toBe("not_in_game");
  });

  it("flush() emits END+SCORE_SCREEN if state ends in_game (trailing segment)", () => {
    const detector = createGameDetector({ config: buildConfig() });
    detector.processFrame(inGame, 1000);
    detector.processFrame(inGame, 2000); // START
    detector.processFrame(inGame, 3000);
    const flushed = detector.flush();
    expect(flushed).toEqual([
      { type: "END", timestamp_ms: 3000 },
      { type: "SCORE_SCREEN", timestamp_ms: 17500 },
    ]);
    expect(detector.getState()).toBe("not_in_game");
  });

  it("flush() is a no-op when not in a game", () => {
    const detector = createGameDetector({ config: buildConfig() });
    expect(detector.flush()).toEqual([]);
  });

  it("requires both kda and notkda predicates simultaneously (HUD must also be dark)", () => {
    const detector = createGameDetector({ config: buildConfig() });
    // KDA bright but HUD strip also bright (a menu) ⇒ NOT in game.
    const kdaBrightHudBright = buildFrame({
      kdaWhite: true,
      notkdaDark: false,
    });
    expect(detector.processFrame(kdaBrightHudBright, 1000)).toEqual([]);
    expect(detector.processFrame(kdaBrightHudBright, 2000)).toEqual([]);
    expect(detector.getState()).toBe("not_in_game");
  });
});

describe("pairEventsIntoSegments", () => {
  it("pairs START → END → SCORE_SCREEN triples in order", () => {
    const events: GameDetectorEvent[] = [
      { type: "START", timestamp_ms: 1000 },
      { type: "END", timestamp_ms: 5000 },
      { type: "SCORE_SCREEN", timestamp_ms: 19500 },
      { type: "START", timestamp_ms: 25000 },
      { type: "END", timestamp_ms: 30000 },
      { type: "SCORE_SCREEN", timestamp_ms: 44500 },
    ];
    const segments = pairEventsIntoSegments(events);
    expect(segments).toEqual([
      { startMs: 1000, endMs: 5000, scoreScreenMs: 19500 },
      { startMs: 25000, endMs: 30000, scoreScreenMs: 44500 },
    ]);
  });

  it("drops a trailing START with no END", () => {
    const events: GameDetectorEvent[] = [
      { type: "START", timestamp_ms: 1000 },
      { type: "END", timestamp_ms: 5000 },
      { type: "SCORE_SCREEN", timestamp_ms: 19500 },
      { type: "START", timestamp_ms: 25000 },
    ];
    const segments = pairEventsIntoSegments(events);
    expect(segments).toEqual([
      { startMs: 1000, endMs: 5000, scoreScreenMs: 19500 },
    ]);
  });
});
