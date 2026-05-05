import {
  validateDetectionConfig,
  DEFAULT_DETECTION_CONFIG,
  type DetectionConfig,
} from "../detectionConfig";

function buildValidPayload(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    version: 1,
    reference_resolution: { width: 1920, height: 1080 },
    roi_zones: {
      minimap: { x: 1, y: 2, width: 10, height: 10 },
      vertical: { x: 1, y: 2, width: 10, height: 10 },
      team_bar: { x: 1, y: 2, width: 10, height: 10 },
      kda: { x: 1, y: 2, width: 10, height: 10 },
      notkda: { x: 1, y: 2, width: 10, height: 10 },
      map_name: { x: 1, y: 2, width: 10, height: 10 },
    },
    thresholds: {
      brightness_threshold: 15,
      start_confirm_frames: 3,
      end_confirm_frames: 5,
      sat_max: 0.4,
      val_min: 0.3,
      min_ratio: 0.5,
      team_bar_min_sat: 25,
      hud_brightness_max: 60,
      score_offset_s: -1.5,
      collision_threshold: 12,
    },
    maps: { map_a: "abcd1234abcd1234" },
    ...overrides,
  };
}

describe("validateDetectionConfig", () => {
  it("accepts a fully formed payload", () => {
    const result = validateDetectionConfig(buildValidPayload());
    expect(result.version).toBe(1);
    expect(result.thresholds.brightness_threshold).toBe(15);
    expect(result.maps.map_a).toBe("abcd1234abcd1234");
  });

  it("rejects non-object payload", () => {
    expect(() => validateDetectionConfig(null)).toThrow(/payload must be an object/);
    expect(() => validateDetectionConfig("nope")).toThrow();
    expect(() => validateDetectionConfig([])).toThrow();
  });

  it("rejects negative or non-integer version", () => {
    expect(() =>
      validateDetectionConfig(buildValidPayload({ version: -1 }))
    ).toThrow(/version/);
    expect(() =>
      validateDetectionConfig(buildValidPayload({ version: 1.5 }))
    ).toThrow(/version/);
    expect(() =>
      validateDetectionConfig(buildValidPayload({ version: "1" }))
    ).toThrow(/version/);
  });

  it("rejects malformed reference_resolution", () => {
    expect(() =>
      validateDetectionConfig(
        buildValidPayload({ reference_resolution: { width: 0, height: 1080 } })
      )
    ).toThrow(/reference_resolution/);
    expect(() =>
      validateDetectionConfig(
        buildValidPayload({ reference_resolution: "1920x1080" })
      )
    ).toThrow(/reference_resolution/);
  });

  it("rejects when an roi_zone is missing", () => {
    const payload = buildValidPayload();
    delete (payload.roi_zones as Record<string, unknown>).minimap;
    expect(() => validateDetectionConfig(payload)).toThrow(/roi_zones\.minimap/);
  });

  it("rejects an roi_zone with non-finite values", () => {
    const payload = buildValidPayload();
    (payload.roi_zones as Record<string, unknown>).kda = {
      x: NaN,
      y: 0,
      width: 10,
      height: 10,
    };
    expect(() => validateDetectionConfig(payload)).toThrow(/roi_zones\.kda\.x/);
  });

  it("rejects an roi_zone with non-positive width or height", () => {
    const zeroWidth = buildValidPayload();
    (zeroWidth.roi_zones as Record<string, unknown>).minimap = {
      x: 0,
      y: 0,
      width: 0,
      height: 10,
    };
    expect(() => validateDetectionConfig(zeroWidth)).toThrow(
      /roi_zones\.minimap\.width and roi_zones\.minimap\.height must be positive/
    );

    const negativeHeight = buildValidPayload();
    (negativeHeight.roi_zones as Record<string, unknown>).team_bar = {
      x: 0,
      y: 0,
      width: 10,
      height: -5,
    };
    expect(() => validateDetectionConfig(negativeHeight)).toThrow(
      /roi_zones\.team_bar/
    );
  });

  it("rejects when a threshold is missing or non-numeric", () => {
    const payload = buildValidPayload();
    delete (payload.thresholds as Record<string, unknown>).brightness_threshold;
    expect(() => validateDetectionConfig(payload)).toThrow(
      /thresholds\.brightness_threshold/
    );

    const payload2 = buildValidPayload();
    (payload2.thresholds as Record<string, unknown>).sat_max = "hi";
    expect(() => validateDetectionConfig(payload2)).toThrow(
      /thresholds\.sat_max/
    );
  });

  it("rejects malformed maps entries", () => {
    expect(() =>
      validateDetectionConfig(buildValidPayload({ maps: { x: 123 } }))
    ).toThrow(/maps\.x/);
    expect(() =>
      validateDetectionConfig(buildValidPayload({ maps: { x: "" } }))
    ).toThrow(/maps\.x/);
  });

  it("DEFAULT_DETECTION_CONFIG is itself valid against the schema", () => {
    const result: DetectionConfig = validateDetectionConfig(
      JSON.parse(JSON.stringify(DEFAULT_DETECTION_CONFIG))
    );
    expect(result.thresholds.brightness_threshold).toBe(
      DEFAULT_DETECTION_CONFIG.thresholds.brightness_threshold
    );
  });
});
