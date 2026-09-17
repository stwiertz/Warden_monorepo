// Story 12.4c AC4 / AC5 — the bundled config, its validation, and HUD selection.

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

beforeEach(() => {
  __resetMapConfigCacheForTests();
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

  it("exposes exactly one candidate today — the seam Story 1.13 widens", () => {
    const candidates = listMapConfigCandidates();
    expect(candidates).toHaveLength(1);
    expect(candidates[0].source).toBe("bundled");
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
});
