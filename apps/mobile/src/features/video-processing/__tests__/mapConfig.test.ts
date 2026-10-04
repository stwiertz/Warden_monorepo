// Story 12.4c AC4 / AC5 — the bundled config, its validation, and HUD selection.
// Story 1.13 AC1 / AC4 / AC6 — the bundled registry and the widened seam.

import fs from "fs";
import path from "path";

import {
  __resetMapConfigCacheForTests,
  assertRefsMatchConfig,
  getPrimaryMapConfig,
  listMapConfigCandidates,
  normalizeHudVersion,
  resolveSessionHudVersion,
  summariseClassifiers,
} from "../mapConfig";
import type { RuleRef } from "../engineScoring";
import { BUNDLED_MAP_CONFIG_REVISION } from "../bundledMapConfigs";
import {
  MAP_CONFIG_OVERLAY_STORAGE_KEY,
  writeCachedOverlay,
  type DetectionConfigEnvelope,
} from "../mapConfigOverlayCache";
import { storage } from "../../../shared/services/storage";

// eslint-disable-next-line @typescript-eslint/no-require-imports
const FIXTURE: DetectionConfigEnvelope = require("./fixtures/overlay-envelope.json");
const FIXTURE_TEXT = FIXTURE.configs.v2!.config_json;

let logSpy: jest.SpyInstance;
let warnSpy: jest.SpyInstance;

beforeEach(() => {
  __resetMapConfigCacheForTests();
  logSpy = jest.spyOn(console, "log").mockImplementation(() => {});
  warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});
});

afterEach(() => {
  logSpy.mockRestore();
  warnSpy.mockRestore();
});

describe("the bundled v2 config", () => {
  it("is the one the tooling emitted, byte for byte", () => {
    // 🔴 THE DRIFT GUARD. The config is COPIED into `assets/detection/` so it
    // ships in the JS bundle; the emitter writes to `apps/tooling/output/`. A
    // copy with no check is a second source of truth, and a stale copy presents
    // as "the engine stopped recognising a map" long after the edit.
    // Skipped rather than failed when the tooling output is absent: that
    // directory is a gitignored build artifact, so a fresh clone legitimately
    // has no emitter output to compare against.
    const emitted = path.join(
      __dirname, "..", "..", "..", "..", "..", "tooling",
      "output", "map_configs", "map_config.v2.json"
    );
    if (!fs.existsSync(emitted)) {
      console.warn(
        `[mapConfig.test] ${emitted} is absent (gitignored build artifact); ` +
          "skipping the bundled-copy drift check."
      );
      return;
    }
    const bundled = path.join(
      __dirname, "..", "..", "..", "..", "assets", "detection", "map_config.v2.json"
    );
    expect(fs.readFileSync(bundled, "utf8")).toBe(
      fs.readFileSync(emitted, "utf8")
    );
  });

  it("validates against the shipped contract and carries the expected shape", () => {
    const candidate = getPrimaryMapConfig();
    expect(candidate.source).toBe("bundled");
    expect(candidate.hudVersion).toBe("v2");
    expect(candidate.config.schema_version).toBe(1); // E1: no bump in this story
    expect(candidate.config.reference_resolution).toEqual({
      width: 1920,
      height: 1080,
    });
    expect(candidate.config.score_screen_duration_ms).toBe(15_000);
    expect(candidate.config.hud_version_detection).toHaveLength(10);
    expect(candidate.config.in_match_detection).toHaveLength(3);
    expect(
      Object.keys(candidate.config.minimap_identification.maps)
    ).toHaveLength(13);
  });

  it("🔴 validates the ZONE fields, not just the top level", () => {
    // Before this story `MapConfigSchema` was generated without resolving
    // `$defs`, so zones were `z.any()` — the parse succeeded on anything and the
    // mobile side "validated" nothing. This asserts the tightened generator is
    // actually in the build: the first zone must carry a real HSV band.
    const zone = getPrimaryMapConfig().config.in_match_detection[0];
    expect(typeof zone.id).toBe("string");
    expect(typeof zone.x).toBe("number");
    expect(typeof zone.hsv.h_center).toBe("number");
    expect(typeof zone.hsv.h_tol).toBe("number");
    expect(typeof zone.min_ratio).toBe("number");
    expect(zone).toHaveProperty("weight_override");
  });

  it("re-serializes the config with map order preserved", () => {
    // The native packer recovers map iteration order by scanning the raw JSON
    // TEXT (org.json.JSONObject is a HashMap). If `rawJson`'s order ever
    // diverged from the parsed object's, every map rule's texel index would
    // permute while each rule stayed individually correct.
    const candidate = getPrimaryMapConfig();
    const reparsed = JSON.parse(candidate.rawJson);
    expect(Object.keys(reparsed.minimap_identification.maps)).toEqual(
      Object.keys(candidate.config.minimap_identification.maps)
    );
    // And the packer's own anchor assumption holds: exactly one `"maps"` key
    // after `"minimap_identification"`, or it refuses to guess.
    const section = candidate.rawJson.indexOf('"minimap_identification"');
    expect(section).toBeGreaterThanOrEqual(0);
    const firstMaps = candidate.rawJson.indexOf('"maps"', section);
    expect(firstMaps).toBeGreaterThan(section);
    expect(candidate.rawJson.indexOf('"maps"', firstMaps + 1)).toBe(-1);
  });

  it("with no overlay cached, the seam returns the bundled registry alone", () => {
    const candidates = listMapConfigCandidates();
    expect(candidates).toHaveLength(1);
    expect(candidates[0].source).toBe("bundled");
    expect(candidates[0].revision).toBe(BUNDLED_MAP_CONFIG_REVISION);
  });

  it("logs which config the session got", () => {
    getPrimaryMapConfig();
    expect(logSpy).toHaveBeenCalledWith(
      `[map-config] source=bundled revision=${BUNDLED_MAP_CONFIG_REVISION} hud=v2`
    );
  });
});

describe("Story 1.13 AC1 — the bundled registry", () => {
  it("a registry key that differs from its config's hud_version throws at the seam", () => {
    try {
      jest.isolateModules(() => {
        jest.doMock("../bundledMapConfigs", () => ({
          // eslint-disable-next-line @typescript-eslint/no-require-imports
          BUNDLED_MAP_CONFIGS: { v1: require("../../../../assets/detection/map_config.v2.json") },
          DEFAULT_HUD_VERSION: "v1",
          BUNDLED_MAP_CONFIG_REVISION: 1,
        }));
        // eslint-disable-next-line @typescript-eslint/no-require-imports
        const isolated = require("../mapConfig");
        expect(() => isolated.listMapConfigCandidates()).toThrow(isolated.MalformedMapConfigError);
        expect(() => isolated.listMapConfigCandidates()).toThrow(/registry key v1/);
      });
    } finally {
      // Even when an assertion above throws, the override must not leak.
      jest.dontMock("../bundledMapConfigs");
    }
  });

  it("the revision is a positive integer", () => {
    expect(Number.isInteger(BUNDLED_MAP_CONFIG_REVISION)).toBe(true);
    expect(BUNDLED_MAP_CONFIG_REVISION).toBeGreaterThanOrEqual(1);
  });
});

describe("Story 1.13 AC4 / AC6 — the cached overlay through the seam", () => {
  it("orders the overlay first and the bundled copy second, per HUD", () => {
    writeCachedOverlay(FIXTURE);
    const candidates = listMapConfigCandidates();
    expect(candidates.map((c) => [c.hudVersion, c.source, c.revision])).toEqual([
      ["v2", "remote", 2],
      ["v2", "bundled", BUNDLED_MAP_CONFIG_REVISION],
    ]);
    expect(getPrimaryMapConfig().source).toBe("remote");
  });

  it("🔴 (a) rawJson IS config_json verbatim, and its NON-alphabetical map order survives", () => {
    writeCachedOverlay(FIXTURE);
    const remote = getPrimaryMapConfig();
    expect(remote.rawJson).toBe(FIXTURE_TEXT);
    const order = ["zeta_map", "alpha_map", "mu_map"];
    expect(Object.keys(remote.config.minimap_identification.maps)).toEqual(order);
    expect(Object.keys(summariseClassifiers(remote).mapZoneCounts)).toEqual(order);
    expect(summariseClassifiers(remote).mapZoneCounts).toEqual({ zeta_map: 1, alpha_map: 2, mu_map: 0 });
    // The packer's text scan sees the same order.
    const positions = order.map((slug) => remote.rawJson.indexOf(`"${slug}"`));
    expect([...positions].sort((a, b) => a - b)).toEqual(positions);
  });

  it("🔴 (c) JSON.parse(rawJson) deep-equals candidate.config", () => {
    writeCachedOverlay(FIXTURE);
    const remote = getPrimaryMapConfig();
    expect(JSON.parse(remote.rawJson)).toEqual(remote.config);
  });

  it("ignores an overlay whose revision does not beat the bundle", () => {
    writeCachedOverlay({ ...FIXTURE, revision: BUNDLED_MAP_CONFIG_REVISION });
    expect(listMapConfigCandidates().map((c) => c.source)).toEqual(["bundled"]);
  });

  it("a cached overlay that fails re-validation on read is deleted and ignored", () => {
    const tightened = JSON.parse(FIXTURE_TEXT);
    tightened.schema_version = 2; // e.g. a contract an app update no longer accepts
    storage.setString(
      MAP_CONFIG_OVERLAY_STORAGE_KEY,
      JSON.stringify({
        envelope_version: 1,
        revision: 3,
        configs: { v2: { config_json: JSON.stringify(tightened), sha256: "0".repeat(64) } },
      })
    );
    expect(listMapConfigCandidates().map((c) => c.source)).toEqual(["bundled"]);
    expect(storage.getString(MAP_CONFIG_OVERLAY_STORAGE_KEY)).toBeUndefined();
    expect(warnSpy).toHaveBeenCalledTimes(1);
  });

  it("a cache entry stored as a nested object (no text) is deleted and ignored", () => {
    storage.setString(
      MAP_CONFIG_OVERLAY_STORAGE_KEY,
      JSON.stringify({ envelope_version: 1, revision: 3, configs: { v2: JSON.parse(FIXTURE_TEXT) } })
    );
    expect(listMapConfigCandidates().map((c) => c.source)).toEqual(["bundled"]);
    expect(storage.getString(MAP_CONFIG_OVERLAY_STORAGE_KEY)).toBeUndefined();
  });

  it("D2: a cached config the native packer would reject is deleted and ignored on read", () => {
    const escapedKey = FIXTURE_TEXT.replace('"alpha_map": {', '"alpha\\u005fmap": {');
    storage.setString(
      MAP_CONFIG_OVERLAY_STORAGE_KEY,
      JSON.stringify({
        envelope_version: 1,
        revision: 3,
        configs: { v2: { config_json: escapedKey, sha256: "0".repeat(64) } },
      })
    );
    expect(listMapConfigCandidates().map((c) => c.source)).toEqual(["bundled"]);
    expect(storage.getString(MAP_CONFIG_OVERLAY_STORAGE_KEY)).toBeUndefined();
    expect(String(warnSpy.mock.calls[0][1])).toMatch(/native packer would reject it/);
  });

  it("D1: an unknown HUD key in a cached overlay is skipped, not a reason to discard", () => {
    writeCachedOverlay({
      ...FIXTURE,
      revision: 3,
      configs: { ...FIXTURE.configs, v3: FIXTURE.configs.v2! },
    });
    expect(listMapConfigCandidates().map((c) => [c.hudVersion, c.source])).toEqual([
      ["v2", "remote"],
      ["v2", "bundled"],
    ]);
    expect(storage.getString(MAP_CONFIG_OVERLAY_STORAGE_KEY)).toBeDefined();
  });

  it("a corrupted (non-JSON) cache is deleted and ignored", () => {
    storage.setString(MAP_CONFIG_OVERLAY_STORAGE_KEY, "{truncated");
    expect(getPrimaryMapConfig().source).toBe("bundled");
    expect(storage.getString(MAP_CONFIG_OVERLAY_STORAGE_KEY)).toBeUndefined();
  });

  it("is memoised, and the memo drops when the overlay cache is written", () => {
    const first = listMapConfigCandidates();
    expect(listMapConfigCandidates()).toBe(first);
    writeCachedOverlay(FIXTURE);
    const second = listMapConfigCandidates();
    expect(second).not.toBe(first);
    expect(second[0].source).toBe("remote");
    expect(listMapConfigCandidates()).toBe(second);
  });
});

describe("summariseClassifiers", () => {
  it("projects the config onto the three classifiers, in config order", () => {
    const cfg = summariseClassifiers(getPrimaryMapConfig());
    expect(cfg).toMatchObject({
      hudVersion: "v2",
      nHudZones: 10,
      nInMatchZones: 3,
      identificationThreshold: 0.6,
      scoreScreenDurationMs: 15_000,
    });
    const slugs = Object.keys(cfg.mapZoneCounts);
    expect(slugs).toHaveLength(13);
    expect(slugs[0]).toBe("artefact");
    // 134 rules total: 10 hud + 3 in_match + 121 map zones.
    const mapZones = Object.values(cfg.mapZoneCounts).reduce((a, b) => a + b, 0);
    expect(mapZones).toBe(121);
    expect(cfg.nHudZones + cfg.nInMatchZones + mapZones).toBe(134);
  });
});

describe("normalizeHudVersion", () => {
  it("bridges the labeled-dir naming and the schema enum", () => {
    expect(normalizeHudVersion("v2.0")).toBe("v2");
    expect(normalizeHudVersion("V2")).toBe("v2");
    expect(normalizeHudVersion("v2")).toBe("v2");
    expect(normalizeHudVersion("v10.0")).toBe("v10");
    // Idempotent, and it strips ONE trailing `.0` — not every trailing zero.
    expect(normalizeHudVersion(normalizeHudVersion("v2.0"))).toBe("v2");
    expect(normalizeHudVersion("v2.10")).toBe("v2.10");
  });
});

describe("assertRefsMatchConfig — the texel-order guard", () => {
  const cfg = {
    hudVersion: "v2",
    nHudZones: 1,
    nInMatchZones: 1,
    mapZoneCounts: { artefact: 2, atlantis: 1 },
    identificationThreshold: 0.6,
    scoreScreenDurationMs: 15_000,
  };
  const ok: RuleRef[] = [
    { texel: 0, owningClass: "v2", zoneId: "hud", kind: "hud_version", effectiveWeight: 1 },
    { texel: 1, owningClass: "in_match", zoneId: "im", kind: "in_match", effectiveWeight: 1 },
    { texel: 2, owningClass: "artefact", zoneId: "a0", kind: "map", effectiveWeight: 1 },
    { texel: 3, owningClass: "artefact", zoneId: "a1", kind: "map", effectiveWeight: 1 },
    { texel: 4, owningClass: "atlantis", zoneId: "b0", kind: "map", effectiveWeight: 1 },
  ];

  it("accepts the canonical order", () => {
    expect(() => assertRefsMatchConfig(ok, cfg)).not.toThrow();
  });

  it("rejects a permuted map order", () => {
    // Each rule individually correct, the ORDER wrong — the failure 12.2 lost a
    // full parity run to, and the one that "produces plausible-looking
    // detections from garbage".
    const permuted = [ok[0], ok[1], ok[4], ok[2], ok[3]];
    expect(() => assertRefsMatchConfig(permuted, cfg)).toThrow(/canonical texel order/);
  });

  it("rejects a rule count that disagrees with the config", () => {
    expect(() => assertRefsMatchConfig(ok.slice(0, 4), cfg)).toThrow(
      /returned 4 rules but the config describes 5/
    );
  });
});

describe("resolveSessionHudVersion — once per session (AC5)", () => {
  const cfg = {
    hudVersion: "v2",
    nHudZones: 2,
    nInMatchZones: 1,
    mapZoneCounts: { artefact: 1 },
    identificationThreshold: 0.6,
    scoreScreenDurationMs: 15_000,
  };
  const refs: RuleRef[] = [
    { texel: 0, owningClass: "v2", zoneId: "h0", kind: "hud_version", effectiveWeight: 1 },
    { texel: 1, owningClass: "v2", zoneId: "h1", kind: "hud_version", effectiveWeight: 1 },
    { texel: 2, owningClass: "in_match", zoneId: "i0", kind: "in_match", effectiveWeight: 1 },
    { texel: 3, owningClass: "artefact", zoneId: "a0", kind: "map", effectiveWeight: 1 },
  ];
  const candidate = { hudVersion: "v2", source: "bundled" as const } as never;
  // 4 rules -> 1 hex char, LSB first: bit0 = h0, bit1 = h1.
  const BOTH_HUD = "3";
  const NO_HUD = "8";

  it("matches when the HUD zones fire across the session", () => {
    const verdict = resolveSessionHudVersion(
      [BOTH_HUD, BOTH_HUD, BOTH_HUD],
      refs,
      candidate,
      cfg
    );
    expect(verdict).toMatchObject({
      hudVersion: "v2",
      matched: true,
      agreement: 1,
      meanConfidence: 1,
    });
  });

  it("reports unknown — not a crash — when the footage is another HUD", () => {
    const verdict = resolveSessionHudVersion([NO_HUD, NO_HUD], refs, candidate, cfg);
    expect(verdict.hudVersion).toBe("unknown");
    expect(verdict.matched).toBe(false);
    expect(verdict.meanConfidence).toBe(0);
  });

  it("short-circuits to unknown on an EMPTY hud_version_detection", () => {
    // Legal per the schema (a partially-staged HUD version) and it must not
    // crash or divide by zero.
    const empty = { ...cfg, nHudZones: 0 };
    const verdict = resolveSessionHudVersion([BOTH_HUD], refs, candidate, empty);
    expect(verdict.hudVersion).toBe("unknown");
    expect(verdict.sampledKeyframes).toBe(0);
  });

  it("handles a session with no keyframes at all", () => {
    expect(resolveSessionHudVersion([], refs, candidate, cfg).hudVersion).toBe(
      "unknown"
    );
  });

  it("samples ACROSS the session rather than taking a prefix", () => {
    // The leading keyframes of a capture are frequently black. A prefix sample
    // would decide a 73-minute session's config from its intro.
    const frames = [NO_HUD, NO_HUD, NO_HUD, ...Array(60).fill(BOTH_HUD)];
    const verdict = resolveSessionHudVersion(frames, refs, candidate, cfg, 8);
    expect(verdict.matched).toBe(true);
    expect(verdict.sampledKeyframes).toBeLessThan(frames.length);
  });

  it("never samples more than sampleSize keyframes", () => {
    // floor(127 / 64) = 1 sampled all 127; the bound is the point of sampling.
    const frames = Array(127).fill(BOTH_HUD);
    const verdict = resolveSessionHudVersion(frames, refs, candidate, cfg, 64);
    expect(verdict.sampledKeyframes).toBeLessThanOrEqual(64);
  });
});

describe("what the native side is handed", () => {
  it("is the same config the TS side validated — zod adds and drops nothing", () => {
    // Native receives `rawJson` (the TEXT, because map order lives in it) while
    // TS scores with the zod-parsed object. A schema default or a stripped key
    // would let the two sides read different configs without any check.
    const candidate = getPrimaryMapConfig();
    expect(JSON.parse(candidate.rawJson)).toEqual(candidate.config);
  });
});
