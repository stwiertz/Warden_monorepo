// Story 12.4c (AC0c / AC4 / AC5) — the v2 detection config, on the device.
//
// Story 1.13 deleted the v1 pHash-era detection-config apparatus (its Firestore
// payload, MMKV cache and the first-launch-offline gate). `detection_config/latest`
// now carries the map-config OVERLAY envelope instead — see mapConfigOverlay.ts.
//
// AC0c verdict (Stephane, at create-story): 12.4c bundles the config MINIMALLY
// and Story 1.13 generalises. The mechanics chosen here, and the seam 1.13 takes:
//
//   * the config ships as a **Metro-bundled JSON module** (`assets/detection/
//     map_config.v2.json`, registered in `bundledMapConfigs.ts` since 1.13), not as a copied file or an adb-staged path. It is
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
//   * **THE SEAM** is [listMapConfigCandidates]. Story 1.13 widened it, and
//     nothing else: per HUD it returns the cached post-auth Firestore overlay
//     (when its envelope revision beats the bundle's) and then the bundled copy
//     from the `bundledMapConfigs.ts` registry as the always-present fallback.
//     A remote candidate's `rawJson` is the envelope's `config_json` text
//     VERBATIM — Firestore maps lose key order, text does not. There is no
//     `schema_version` migration: only shape 1 exists, and an overlay entry with
//     another shape fails the contract and is dropped (that IS the forward-compat
//     behaviour for an old app meeting a future shape).
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

import {
  BUNDLED_MAP_CONFIG_REVISION,
  BUNDLED_MAP_CONFIGS,
  DEFAULT_HUD_VERSION,
} from "./bundledMapConfigs";
import type { RuleKind, RuleRef } from "./engineScoring";
import { HUD_THRESHOLD, scoreFromFires } from "./engineScoring";
import { nativeConfigProblem } from "./mapConfigNativePreconditions";
import {
  __resetMapConfigOverlayCacheForTests,
  discardCachedOverlay,
  getOverlayCacheGeneration,
  readCachedOverlay,
} from "./mapConfigOverlayCache";

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
  /**
   * Story 1.13: BUNDLED_MAP_CONFIG_REVISION for a bundled candidate, the
   * overlay envelope's `revision` for a remote one.
   */
  revision: number;
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

function parseCandidate(
  raw: unknown,
  source: MapConfigCandidate["source"],
  revision: number,
  label: string,
  rawJson: string
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
    rawJson,
    source,
    revision,
  };
}

/**
 * Story 1.13 AC1 — a registry entry, validated, its key checked against its
 * content. A broken BUNDLED config is a broken build and stays loud (throws).
 */
function parseBundledEntry(key: string, raw: unknown): MapConfigCandidate {
  const label = `assets/detection/map_config.${key}.json`;
  // Bundled modules are parsed objects: re-serialising them is order-safe
  // (map slugs are non-integer-like strings, so insertion order survives).
  const candidate = parseCandidate(
    raw,
    "bundled",
    BUNDLED_MAP_CONFIG_REVISION,
    label,
    JSON.stringify(raw)
  );
  if (candidate.hudVersion !== normalizeHudVersion(key)) {
    throw new MalformedMapConfigError(
      label,
      `registry key ${key} does not match the config's hud_version ${candidate.config.hud_version}`
    );
  }
  return candidate;
}

/**
 * Story 1.13 AC4 / AC6 — remote candidates from the cached overlay.
 *
 * 🔴 `rawJson` IS the envelope entry's `config_json`, verbatim: never
 * re-serialised, because that text is the only carrier of map order the native
 * packer can read. Returns `[]` (and discards the cache) when the overlay is
 * absent, not newer than the bundle, or any entry fails re-validation — a
 * cached overlay that an app update's tightened contract rejects must not
 * crash the seam, only fall back to the bundle.
 */
function remoteCandidates(): MapConfigCandidate[] {
  const overlay = readCachedOverlay();
  if (!overlay || overlay.revision <= BUNDLED_MAP_CONFIG_REVISION) return [];
  const out: MapConfigCandidate[] = [];
  try {
    for (const [key, entry] of Object.entries(overlay.configs)) {
      if (!entry) continue;
      // A HUD this build's contract does not know (code-review D1): never
      // written by the refresh, but tolerate it here rather than discard.
      if (!MapConfigSchema.shape.hud_version.options.includes(key as never)) continue;
      const label = `detection_config/latest revision ${overlay.revision} (${key})`;
      const candidate = parseCandidate(
        JSON.parse(entry.config_json),
        "remote",
        overlay.revision,
        label,
        entry.config_json
      );
      if (candidate.hudVersion !== normalizeHudVersion(key)) {
        throw new MalformedMapConfigError(label, `entry key ${key} carries hud_version ${candidate.config.hud_version}`);
      }
      // Code-review D2: a config the native packer would throw on must never
      // reach a session (it would fail every session, with no fallback).
      const nativeProblem = nativeConfigProblem(candidate.rawJson, candidate.config);
      if (nativeProblem) throw new MalformedMapConfigError(label, `native packer would reject it: ${nativeProblem}`);
      out.push(candidate);
    }
  } catch (err) {
    console.warn(
      "[map-config] cached overlay failed re-validation; discarding it and using the bundled config",
      err instanceof Error ? err.message : err
    );
    discardCachedOverlay();
    return [];
  }
  return out;
}

let cachedBundled: MapConfigCandidate[] | undefined;
let cachedCandidates: { generation: number; list: MapConfigCandidate[] } | undefined;

/**
 * 🔴 STORY 1.13'S SEAM. Every config consumer in the app goes through here.
 *
 * Synchronous, never touches the network, never empty. Ordered by preference:
 * for each HUD, the cached Firestore overlay entry (only when the overlay's
 * `revision` exceeds BUNDLED_MAP_CONFIG_REVISION) and then the bundled entry,
 * which is always present as the fallback. HUDs follow the bundled registry's
 * order; an overlay-only HUD (no bundled file) is appended after them.
 *
 * Memoised; the memo is dropped when `refreshMapConfigOverlay` writes or the
 * cache is discarded. A running session holds the candidate it captured at
 * start, so an overlay landing mid-session only affects the next session.
 */
export function listMapConfigCandidates(): MapConfigCandidate[] {
  if (!cachedBundled) {
    cachedBundled = Object.entries(BUNDLED_MAP_CONFIGS).map(([key, raw]) =>
      parseBundledEntry(key, raw)
    );
  }
  const generation = getOverlayCacheGeneration();
  if (cachedCandidates && cachedCandidates.generation === generation) {
    return cachedCandidates.list;
  }
  const remote = remoteCandidates();
  // remoteCandidates() may discard the cache, which bumps the generation.
  const settledGeneration = getOverlayCacheGeneration();
  const list: MapConfigCandidate[] = [];
  const huds = [
    ...cachedBundled.map((c) => c.hudVersion),
    ...remote.map((c) => c.hudVersion),
  ].filter((hud, i, all) => all.indexOf(hud) === i);
  for (const hud of huds) {
    list.push(...remote.filter((c) => c.hudVersion === hud));
    list.push(...cachedBundled.filter((c) => c.hudVersion === hud));
  }
  cachedCandidates = { generation: settledGeneration, list };
  return list;
}

/**
 * The config a session runs with: the preferred candidate for
 * DEFAULT_HUD_VERSION (real HUD selection before `analyzeSession` is deferred
 * to the first story that bundles a second HUD's config). Called once per
 * session, which is why it logs which config the session got.
 */
export function getPrimaryMapConfig(): MapConfigCandidate {
  const candidates = listMapConfigCandidates();
  const primary =
    candidates.find((c) => c.hudVersion === DEFAULT_HUD_VERSION) ?? candidates[0];
  if (!primary) {
    throw new Error(
      "no map config is available — the bundled asset is missing from this build"
    );
  }
  console.log(
    `[map-config] source=${primary.source} revision=${primary.revision} hud=${primary.hudVersion}`
  );
  return primary;
}

/** Test seam: drop the memoized parse (and the overlay memo) so a test can re-enter the parser. */
export function __resetMapConfigCacheForTests(): void {
  cachedBundled = undefined;
  cachedCandidates = undefined;
  __resetMapConfigOverlayCacheForTests();
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
  // ceil, so the sample never exceeds `sampleSize` (floor sampled up to
  // 2×sampleSize−1 frames, e.g. 127 frames at size 64 → step 1).
  const step = Math.max(1, Math.ceil(frameFires.length / sampleSize));
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
