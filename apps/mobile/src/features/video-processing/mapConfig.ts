// Story 12.4c (AC0c / AC4 / AC5) — the v2 detection config, on the device.
//
// 🔴 THIS IS THE V2 CONFIG. It is NOT `detectionConfig.ts`, which is the v1
// pHash-era Firestore document (`detection_config/latest`: `roi_zones`,
// `thresholds`, `maps: slug -> 16-hex pHash`). That apparatus is deliberately
// left running — the first-launch-offline gate is Story 1.13's AC7 to remove —
// but it is no longer a detection input. Nothing in the engine path reads it.
//
// AC0c verdict (Stephane, at create-story): 12.4c bundles the config MINIMALLY
// and Story 1.13 generalises. The mechanics chosen here, and the seam 1.13 takes:
//
//   * the config ships as a **Metro-bundled JSON module** (`assets/detection/
//     map_config.v2.json`), not as a copied file or an adb-staged path. It is
//     62 kB of text that must exist on first launch, offline, before any
//     Firestore call — a bundled module is the only shape with no I/O and no
//     failure mode. `WardenEngineBench` keeps its own adb-staged path; it is a
//     bench.
//   * the native side receives the config as a **JSON string over the bridge**,
//     re-serialized from the parsed module. It does NOT read a file, and the
//     hardcoded `File(workDir, "map_config.v2.json")` at WardenEngineBench.kt:53
//     is not on this path (AC3).
//     🔴 Re-serializing is load-bearing: `WardenRulePacker.orderedMapNames`
//     recovers map iteration order by scanning the raw JSON TEXT, because
//     `org.json.JSONObject` is a HashMap and loses insertion order. JS objects
//     preserve string-key insertion order, so `JSON.stringify` round-trips the
//     order the emitter wrote. Permuting it would permute every map rule's texel
//     index — each rule still correct, the ORDER wrong, which is the failure
//     12.2 lost a full parity run to.
//   * **THE SEAM FOR STORY 1.13** is [listMapConfigCandidates]. It returns the
//     bundled config today; 1.13 makes it return the Firestore
//     stale-while-revalidate overlay first and the bundled copy as the fallback,
//     adds `schema_version` migration and reads the per-HUD manifest. Every
//     consumer in this story goes through it, so 1.13 changes this function and
//     nothing else.
//
// AC4 — validation is real, not decorative. `MapConfigSchema` from
// `@warden/contracts` used to be near-useless here: `json-schema-to-zod` does
// not follow `$ref`, so `hud_version_detection`/`in_match_detection` were
// `z.array(z.any())`, `roi` was `z.any()` and every map entry was `z.any()` —
// zero type safety on exactly the zone fields this engine consumes. Story 12.4c
// fixed the GENERATOR (`packages/contracts/scripts/generate-zod.mjs` now inlines
// local `$defs`) rather than hand-rolling a mobile-side zone type, so the
// contract stays single-source and the Python `jsonschema` side and the TS side
// keep agreeing. This is also what finally makes the `@warden/contracts`
// dependency in `apps/mobile/package.json` real — it was declared and imported
// by nothing.
//
// E1 binds: no `schema_version` bump, rules stay rectangles.

import { MapConfigSchema } from "@warden/contracts";
import type { z } from "zod";

import bundledV2 from "../../../assets/detection/map_config.v2.json";
import type { RuleKind, RuleRef } from "./engineScoring";
import { HUD_THRESHOLD, scoreFromFires } from "./engineScoring";

export type MapConfig = z.infer<typeof MapConfigSchema>;
export type MapConfigZone = MapConfig["in_match_detection"][number];

/** Thrown when a config fails the shipped contract. Never swallowed. */
export class MalformedMapConfigError extends Error {
  constructor(source: string, issues: string) {
    super(
      `map config from ${source} does not match contracts/map-config.schema.json: ${issues}`
    );
    this.name = "MalformedMapConfigError";
  }
}

export interface MapConfigCandidate {
  /** Normalized HUD version this config is calibrated for (e.g. "v2"). */
  hudVersion: string;
  config: MapConfig;
  /**
   * The exact JSON text handed to the native side. Map iteration order lives in
   * this string and nowhere else — see the header.
   */
  rawJson: string;
  source: "bundled" | "remote";
}

/**
 * The classifier-shaped projection of a config — everything the three formulas
 * and the phase machine need, and nothing else.
 */
export interface ClassifierConfig {
  hudVersion: string;
  nHudZones: number;
  nInMatchZones: number;
  /** Map slug -> zone count, in CONFIG ORDER (the order is load-bearing). */
  mapZoneCounts: Record<string, number>;
  identificationThreshold: number;
  scoreScreenDurationMs: number;
}

/**
 * Bridge the labeled-dir naming (`v2.0`) and the schema enum (`v2`): lowercase,
 * strip a single trailing `.0`. Mirrors `_normalize_hud`
 * (roi_detection_tester.py:108) and `WardenRulePacker.normalizeHud`, which the
 * packer applies to every HUD zone's `owning_class` — so a mismatch here would
 * make every HUD rule fail to match its own class.
 */
export function normalizeHudVersion(value: string): string {
  const out = value.trim().toLowerCase();
  return out.endsWith(".0") ? out.slice(0, -2) : out;
}

let cachedBundled: MapConfigCandidate | undefined;

function parseCandidate(
  raw: unknown,
  source: MapConfigCandidate["source"],
  label: string
): MapConfigCandidate {
  const parsed = MapConfigSchema.safeParse(raw);
  if (!parsed.success) {
    // The first few issues only: a wholly wrong file produces hundreds, and an
    // unreadable error is a error nobody acts on.
    const issues = parsed.error.issues
      .slice(0, 5)
      .map((i) => `${i.path.join(".") || "<root>"}: ${i.message}`)
      .join("; ");
    throw new MalformedMapConfigError(label, issues);
  }
  const config = parsed.data;
  return {
    hudVersion: normalizeHudVersion(config.hud_version),
    config,
    rawJson: JSON.stringify(raw),
    source,
  };
}

/**
 * 🔴 STORY 1.13'S SEAM. Every config consumer in the app goes through here.
 *
 * Today: the single bundled v2 config. Story 1.13 adds the hybrid
 * stale-while-revalidate Firestore overlay (returned FIRST, bundled second as
 * the offline fallback), `schema_version` migration and the per-HUD manifest —
 * by changing this function, not its callers.
 *
 * Ordered by preference. Never empty: a build with no config is a broken build,
 * and failing at the seam beats failing per-keyframe.
 */
export function listMapConfigCandidates(): MapConfigCandidate[] {
  if (!cachedBundled) {
    cachedBundled = parseCandidate(
      bundledV2,
      "bundled",
      "assets/detection/map_config.v2.json"
    );
  }
  return [cachedBundled];
}

/** The config a session runs with before HUD-version selection refines it. */
export function getPrimaryMapConfig(): MapConfigCandidate {
  const candidates = listMapConfigCandidates();
  if (candidates.length === 0) {
    throw new Error(
      "no map config is available — the bundled asset is missing from this build"
    );
  }
  return candidates[0];
}

/** Test seam: drop the memoized parse so a test can re-enter the parser. */
export function __resetMapConfigCacheForTests(): void {
  cachedBundled = undefined;
}

export function summariseClassifiers(candidate: MapConfigCandidate): ClassifierConfig {
  const { config } = candidate;
  const mapZoneCounts: Record<string, number> = {};
  // Object.entries preserves the config's insertion order, which is the texel
  // order the native packer used. Sorting here would silently re-key the
  // aggregation against a different rule order.
  for (const [slug, entry] of Object.entries(config.minimap_identification.maps)) {
    mapZoneCounts[slug] = entry.zones.length;
  }
  return {
    hudVersion: candidate.hudVersion,
    nHudZones: config.hud_version_detection.length,
    nInMatchZones: config.in_match_detection.length,
    mapZoneCounts,
    identificationThreshold:
      config.minimap_identification.identification_threshold,
    scoreScreenDurationMs: config.score_screen_duration_ms,
  };
}

/**
 * Assert that the rule index the native side returned is the one this config
 * describes, before a single bit is interpreted.
 *
 * Cheap, and it catches the one failure that is invisible downstream: a
 * `refs` array whose ORDER differs from the config's zone order scores every
 * fire against the wrong classifier and the wrong map while looking entirely
 * plausible. 12.2 lost a full parity run to exactly that.
 */
export function assertRefsMatchConfig(
  refs: readonly RuleRef[],
  cfg: ClassifierConfig
): void {
  const expected: RuleKind[] = [
    ...Array<RuleKind>(cfg.nHudZones).fill("hud_version"),
    ...Array<RuleKind>(cfg.nInMatchZones).fill("in_match"),
  ];
  const expectedClasses: string[] = [
    ...Array<string>(cfg.nHudZones).fill(cfg.hudVersion),
    ...Array<string>(cfg.nInMatchZones).fill("in_match"),
  ];
  for (const [slug, count] of Object.entries(cfg.mapZoneCounts)) {
    for (let i = 0; i < count; i++) {
      expected.push("map");
      expectedClasses.push(slug);
    }
  }
  if (refs.length !== expected.length) {
    throw new Error(
      `the engine returned ${refs.length} rules but the config describes ` +
        `${expected.length} (${cfg.nHudZones} hud + ${cfg.nInMatchZones} in_match + ` +
        `${expected.length - cfg.nHudZones - cfg.nInMatchZones} map zones). ` +
        "Fire bits are indexed by texel order; a count mismatch means the " +
        "native side packed a different config than the one being scored."
    );
  }
  for (let i = 0; i < refs.length; i++) {
    if (refs[i].kind !== expected[i] || refs[i].owningClass !== expectedClasses[i]) {
      throw new Error(
        `rule ${i} is ${refs[i].kind}/${refs[i].owningClass} but the config has ` +
          `${expected[i]}/${expectedClasses[i]} there (zone ${refs[i].zoneId}). ` +
          "The canonical texel order is hud_version zones, then in_match, then " +
          "map zones in config order — a permutation here produces " +
          "plausible-looking detections from the wrong rules."
      );
    }
  }
}

export interface HudVersionVerdict {
  /** The config's HUD version, or `"unknown"` when the footage does not match it. */
  hudVersion: string;
  /** Mean HUD-classifier confidence over the sampled keyframes. */
  meanConfidence: number;
  /** Fraction of sampled keyframes that predicted this config's HUD version. */
  agreement: number;
  sampledKeyframes: number;
  matched: boolean;
}

/**
 * AC5 — HUD-version selection, ONCE PER SESSION, not per frame.
 *
 * The schema's own contract: *"Runtime picks the matching
 * `map_config.<hud_version>.json` once per session via `hud_version_detection`"*.
 * With one bundled config the outcome is nearly foregone, and it is implemented
 * as the real mechanism anyway because it is the seam 1.13 and every future HUD
 * version extend: score each candidate's HUD zones over a sample of the
 * session's keyframes and take the one that clears [HUD_THRESHOLD].
 *
 * Two behaviours worth stating:
 *   * **Empty `hud_version_detection` is legal** (a partially-staged HUD
 *     version) and short-circuits to `"unknown"` — it must not crash, and it
 *     must not be read as "this footage is the wrong HUD".
 *   * **`"unknown"` does NOT abort the session.** REL-006's below-floor
 *     behaviour is graceful degradation, so an unmatched HUD is reported and the
 *     session proceeds with the only config there is; the alternative is
 *     refusing to analyse footage we can still partly read.
 *
 * Sampling rather than every frame: the verdict is per-session, the classifier
 * is a mean over confident frames, and a lobby-heavy capture would otherwise let
 * a long menu stretch outvote the gameplay. `sampleSize` spreads the sample
 * evenly across the session instead of taking a prefix, because the first
 * keyframes of a capture are frequently black.
 */
export function resolveSessionHudVersion(
  frameFires: readonly string[],
  refs: readonly RuleRef[],
  candidate: MapConfigCandidate,
  cfg: ClassifierConfig,
  sampleSize = 64
): HudVersionVerdict {
  if (cfg.nHudZones === 0 || frameFires.length === 0) {
    return {
      hudVersion: "unknown",
      meanConfidence: 0,
      agreement: 0,
      sampledKeyframes: 0,
      matched: false,
    };
  }
  const step = Math.max(1, Math.floor(frameFires.length / sampleSize));
  let sampled = 0;
  let confSum = 0;
  let agreed = 0;
  for (let i = 0; i < frameFires.length; i += step) {
    const scores = scoreFromFires(frameFires[i], refs, cfg);
    sampled++;
    confSum += scores.hudConf;
    if (scores.predHud === candidate.hudVersion) agreed++;
  }
  const meanConfidence = confSum / sampled;
  const agreement = agreed / sampled;
  // The per-frame classifier already applies HUD_THRESHOLD; the session-level
  // verdict asks the same question of the session's mean, so one noisy frame
  // cannot decide which config a 73-minute capture is scored with.
  const matched = meanConfidence >= HUD_THRESHOLD;
  return {
    hudVersion: matched ? candidate.hudVersion : "unknown",
    meanConfidence,
    agreement,
    sampledKeyframes: sampled,
    matched,
  };
}
