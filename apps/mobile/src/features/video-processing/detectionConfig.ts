// DetectionConfig schema and validator.
//
// This is the typed contract for the remote detection-tuning document
// (Firestore: detection_config/latest). It is consumed by the KDA/HSV
// gameDetector + pHash mapIdentifier landed in Story 7.5 and by the
// existing blackScreenDetector via a no-op shim until then.
//
// See docs/planning-artifacts/architecture.md#Detection Methodology.

export interface ROI {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface DetectionConfigROIs {
  minimap: ROI;
  vertical: ROI;
  team_bar: ROI;
  kda: ROI;
  notkda: ROI;
  map_name: ROI;
}

export interface DetectionConfigThresholds {
  brightness_threshold: number;
  start_confirm_frames: number;
  end_confirm_frames: number;
  sat_max: number;
  val_min: number;
  min_ratio: number;
  // Mean saturation (HSV-8U, 0..255) the team_bar ROI must beat for the
  // long-GOP fallback's Pass-1 to count a keyframe as "high-saturation
  // gameplay." Independent of `min_ratio` so the kda white-pixel ratio and
  // the team_bar saturation floor can be tuned separately.
  team_bar_min_sat: number;
  hud_brightness_max: number;
  score_offset_s: number;
  collision_threshold: number;
}

export interface DetectionConfig {
  version: number;
  reference_resolution: { width: number; height: number };
  roi_zones: DetectionConfigROIs;
  thresholds: DetectionConfigThresholds;
  maps: Record<string, string>;
}

const ROI_KEYS: ReadonlyArray<keyof DetectionConfigROIs> = [
  "minimap",
  "vertical",
  "team_bar",
  "kda",
  "notkda",
  "map_name",
];

const THRESHOLD_KEYS: ReadonlyArray<keyof DetectionConfigThresholds> = [
  "brightness_threshold",
  "start_confirm_frames",
  "end_confirm_frames",
  "sat_max",
  "val_min",
  "min_ratio",
  "team_bar_min_sat",
  "hud_brightness_max",
  "score_offset_s",
  "collision_threshold",
];

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function assertROI(value: unknown, path: string): ROI {
  if (!isObject(value)) {
    throw new Error(`DetectionConfig: ${path} must be an object`);
  }
  for (const key of ["x", "y", "width", "height"] as const) {
    if (!isFiniteNumber(value[key])) {
      throw new Error(`DetectionConfig: ${path}.${key} must be a finite number`);
    }
  }
  if ((value.width as number) <= 0 || (value.height as number) <= 0) {
    throw new Error(
      `DetectionConfig: ${path}.width and ${path}.height must be positive`
    );
  }
  return {
    x: value.x as number,
    y: value.y as number,
    width: value.width as number,
    height: value.height as number,
  };
}

/**
 * Validate an unknown payload against the DetectionConfig contract.
 * Throws if any field is missing, mistyped, or non-finite. Used both for
 * Firestore-fetched documents and for the offline-fallback default. The
 * thrown error must not be swallowed silently — callers log + reject the
 * fetch and keep the existing cached config.
 */
export function validateDetectionConfig(raw: unknown): DetectionConfig {
  if (!isObject(raw)) {
    throw new Error("DetectionConfig: payload must be an object");
  }

  if (!isFiniteNumber(raw.version) || !Number.isInteger(raw.version) || raw.version < 0) {
    throw new Error("DetectionConfig: version must be a non-negative integer");
  }

  if (!isObject(raw.reference_resolution)) {
    throw new Error("DetectionConfig: reference_resolution must be an object");
  }
  const { width, height } = raw.reference_resolution as Record<string, unknown>;
  if (!isFiniteNumber(width) || !isFiniteNumber(height) || width <= 0 || height <= 0) {
    throw new Error(
      "DetectionConfig: reference_resolution.width/height must be positive numbers"
    );
  }

  if (!isObject(raw.roi_zones)) {
    throw new Error("DetectionConfig: roi_zones must be an object");
  }
  const roi_zones = {} as DetectionConfigROIs;
  for (const key of ROI_KEYS) {
    roi_zones[key] = assertROI(
      (raw.roi_zones as Record<string, unknown>)[key],
      `roi_zones.${key}`
    );
  }

  if (!isObject(raw.thresholds)) {
    throw new Error("DetectionConfig: thresholds must be an object");
  }
  const thresholds = {} as DetectionConfigThresholds;
  for (const key of THRESHOLD_KEYS) {
    const value = (raw.thresholds as Record<string, unknown>)[key];
    if (!isFiniteNumber(value)) {
      throw new Error(`DetectionConfig: thresholds.${key} must be a finite number`);
    }
    thresholds[key] = value;
  }

  if (!isObject(raw.maps)) {
    throw new Error("DetectionConfig: maps must be an object");
  }
  const maps: Record<string, string> = {};
  for (const [k, v] of Object.entries(raw.maps)) {
    if (typeof v !== "string" || v.length === 0) {
      throw new Error(`DetectionConfig: maps.${k} must be a non-empty string`);
    }
    maps[k] = v;
  }

  return {
    version: raw.version,
    reference_resolution: { width, height },
    roi_zones,
    thresholds,
    maps,
  };
}

/**
 * Bundled fallback used by detectionConfigService when no remote config has
 * been fetched yet (e.g. offline-first launch on first install). Threshold
 * values mirror the Python reference defaults documented in Story 7.5 Dev
 * Notes so a freshly-fetched cache and the bundled fallback agree on tuning.
 *
 * ROI dimensions are nominal `1×1` placeholders — the bootstrap gate blocks
 * video processing while this fallback is active, so detectors never run
 * with these ROIs in practice. The thresholds are still kept realistic so
 * any code path that consults DEFAULT_DETECTION_CONFIG outside the bootstrap
 * gate degrades gracefully instead of silently classifying every frame as
 * not-in-game.
 */
export const DEFAULT_DETECTION_CONFIG: DetectionConfig = {
  version: 0,
  reference_resolution: { width: 1920, height: 1080 },
  roi_zones: {
    minimap: { x: 0, y: 0, width: 1, height: 1 },
    vertical: { x: 0, y: 0, width: 1, height: 1 },
    team_bar: { x: 0, y: 0, width: 1, height: 1 },
    kda: { x: 0, y: 0, width: 1, height: 1 },
    notkda: { x: 0, y: 0, width: 1, height: 1 },
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
  },
  maps: {},
};
