import { createMapIdentifier } from "../mapIdentifier";
import {
  cropToGrayscale,
  phash,
  type FrameBuffer,
} from "../../../shared/services/opencv";
import type { DetectionConfig } from "../detectionConfig";

const FRAME_SIZE = 64;

function buildFrame(fill: (x: number, y: number) => number): FrameBuffer {
  const data = new Uint8ClampedArray(FRAME_SIZE * FRAME_SIZE * 3);
  for (let y = 0; y < FRAME_SIZE; y++) {
    for (let x = 0; x < FRAME_SIZE; x++) {
      const i = (y * FRAME_SIZE + x) * 3;
      const v = fill(x, y);
      data[i] = v;
      data[i + 1] = v;
      data[i + 2] = v;
    }
  }
  return { data, width: FRAME_SIZE, height: FRAME_SIZE };
}

function fingerprintOf(frame: FrameBuffer): string {
  const gray = cropToGrayscale(frame, {
    x: 0,
    y: 0,
    width: FRAME_SIZE,
    height: FRAME_SIZE,
  });
  return phash(gray);
}

function buildConfig(maps: Record<string, string>): DetectionConfig {
  return {
    version: 1,
    reference_resolution: { width: FRAME_SIZE, height: FRAME_SIZE },
    roi_zones: {
      minimap: { x: 0, y: 0, width: 1, height: 1 },
      vertical: { x: 0, y: 0, width: 1, height: 1 },
      team_bar: { x: 0, y: 0, width: 1, height: 1 },
      kda: { x: 0, y: 0, width: 1, height: 1 },
      notkda: { x: 0, y: 0, width: 1, height: 1 },
      map_name: { x: 0, y: 0, width: FRAME_SIZE, height: FRAME_SIZE },
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
    },
    maps,
  };
}

describe("createMapIdentifier", () => {
  it("matches a frame against its own fingerprint with Hamming distance 0", () => {
    const frame = buildFrame((x, y) => (x * 4 + y * 7) & 0xff);
    const config = buildConfig({ ascent: fingerprintOf(frame) });
    const identifier = createMapIdentifier({ config });
    const result = identifier.identify(frame);
    expect(result.match).toEqual({ mapName: "ascent", hammingDistance: 0 });
  });

  it("returns null when no fingerprint is within collision_threshold", () => {
    const target = buildFrame((x, y) => (x * 4 + y * 7) & 0xff);
    const decoy = buildFrame((x, y) => (x < 32 ? 0 : 255) ^ (y < 32 ? 255 : 0));
    const config = buildConfig({ decoy: fingerprintOf(decoy) });
    const identifier = createMapIdentifier({ config });
    const result = identifier.identify(target);
    expect(result.match).toBeNull();
    // Hash is still returned so the orchestrator can log it.
    expect(result.hash).toMatch(/^[0-9a-f]{16}$/);
  });

  it("picks the lowest-distance map when multiple fingerprints are within threshold", () => {
    const target = buildFrame((x, y) => (x * 4 + y * 7) & 0xff);
    const config = buildConfig({
      // Same fingerprint registered under two map names — both within
      // threshold, but the first encountered with the lowest distance wins.
      ascent: fingerprintOf(target),
      bind: fingerprintOf(target),
    });
    const identifier = createMapIdentifier({ config });
    const result = identifier.identify(target);
    expect(result.match?.mapName).toBe("ascent");
    expect(result.match?.hammingDistance).toBe(0);
  });

  it("ignores fingerprints with mismatched lengths", () => {
    const frame = buildFrame((x) => x * 4);
    const config = buildConfig({
      malformed: "abcd", // 4 hex chars vs the 16 the hasher emits
      good: fingerprintOf(frame),
    });
    const identifier = createMapIdentifier({ config });
    const result = identifier.identify(frame);
    expect(result.match?.mapName).toBe("good");
  });
});
