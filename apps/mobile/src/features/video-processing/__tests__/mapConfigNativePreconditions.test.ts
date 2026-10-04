// Story 1.13 code review, decision D2 — one test per native packer
// precondition (apps/mobile/plugins/kotlin/WardenRulePacker.kt), plus the
// "accepts what native accepts" side.

import { MapConfigSchema } from "@warden/contracts";

import {
  NATIVE_MAX_RECT_TEXELS,
  NATIVE_MAX_RULES,
  nativeConfigProblem,
  nativeOrderedMapNames,
} from "../mapConfigNativePreconditions";
import type { DetectionConfigEnvelope } from "../mapConfigOverlayCache";
import { getPrimaryMapConfig, __resetMapConfigCacheForTests, type MapConfig } from "../mapConfig";

// eslint-disable-next-line @typescript-eslint/no-require-imports
const FIXTURE: DetectionConfigEnvelope = require("./fixtures/overlay-envelope.json");
const FIXTURE_TEXT = FIXTURE.configs.v2!.config_json;

/** The problem for a text that must still be schema-valid (else the test is moot). */
function problemOf(text: string): string | null {
  const parsed = MapConfigSchema.safeParse(JSON.parse(text));
  if (!parsed.success) throw new Error(`test text is not schema-valid: ${parsed.error.message}`);
  return nativeConfigProblem(text, parsed.data as MapConfig);
}

function mutated(patch: (c: MapConfig) => void): string {
  const c = JSON.parse(FIXTURE_TEXT) as MapConfig;
  patch(c);
  return JSON.stringify(c, null, 2);
}

function zone(id: string, x: number, y: number, width: number, height: number) {
  return {
    id,
    x,
    y,
    width,
    height,
    hsv: { h_center: 0, h_tol: 10, s_center: 50, s_tol: 10, v_center: 50, v_tol: 10 },
    min_ratio: 0.3,
    weight: 1,
    weight_override: null,
  };
}

let logSpy: jest.SpyInstance;
beforeEach(() => {
  __resetMapConfigCacheForTests();
  logSpy = jest.spyOn(console, "log").mockImplementation(() => {});
});
afterEach(() => logSpy.mockRestore());

describe("accepts what the native packer accepts", () => {
  it("the shipped bundled config", () => {
    const bundled = getPrimaryMapConfig();
    expect(nativeConfigProblem(bundled.rawJson, bundled.config)).toBeNull();
  });

  it("the overlay fixture (non-alphabetical map order, CRLF or LF)", () => {
    expect(problemOf(FIXTURE_TEXT)).toBeNull();
    expect(problemOf(FIXTURE_TEXT.replace(/\n/g, "\r\n"))).toBeNull();
    expect(nativeOrderedMapNames(FIXTURE_TEXT)).toEqual(["zeta_map", "alpha_map", "mu_map"]);
  });

  it("an off-frame zone whose CLAMPED area is under the cap (clampRect, :199-205)", () => {
    const text = mutated((c) => {
      c.in_match_detection.push(zone("edge", 1910, 1070, 100, 100)); // clamps to 10x10
    });
    expect(problemOf(text)).toBeNull();
  });
});

describe("rejects what the native packer throws on", () => {
  it(':268-269 — no "minimap_identification" literal in the text (escaped key)', () => {
    const text = FIXTURE_TEXT.replace('"minimap_identification"', '"minimap\\u005fidentification"');
    expect(problemOf(text)).toMatch(/no minimap_identification$/);
  });

  it(':270-271 — no "maps" literal after it (escaped key)', () => {
    const text = FIXTURE_TEXT.replace('"maps"', '"m\\u0061ps"');
    expect(problemOf(text)).toMatch(/no minimap_identification\.maps/);
  });

  it(':272-278 — the "maps" literal appears twice after minimap_identification', () => {
    const text = FIXTURE_TEXT.replace('"id": "zeta_z00"', '"id": "maps"');
    expect(problemOf(text)).toMatch(/more than once/);
  });

  it(":279 and :315 — the scanner's own malformed / unterminated guards (port fidelity)", () => {
    expect(() => nativeOrderedMapNames('{"minimap_identification": {"maps": 1}}')).toThrow(
      "malformed maps object"
    );
    expect(() => nativeOrderedMapNames('{"minimap_identification": {"maps": {"a": {')).toThrow(
      "unterminated maps object in config"
    );
  });

  it(":241-246 — a map slug written twice (parsed object keeps one; the scan sees two)", () => {
    const text = FIXTURE_TEXT.replace('"zeta_map": {', '"alpha_map": { "zones": [] },\n      "zeta_map": {');
    expect(problemOf(text)).toMatch(/"alpha_map" appears more than once/);
  });

  it(":241-246 — an escaped map key (Kotlin keeps the escape; getJSONObject(name) throws)", () => {
    const text = FIXTURE_TEXT.replace('"alpha_map": {', '"alpha\\u005fmap": {');
    expect(problemOf(text)).toMatch(/not a key of the parsed maps/);
  });

  it(`:335-338 — more than MAX_RULES = ${NATIVE_MAX_RULES} rules in total`, () => {
    const total = (c: MapConfig) =>
      c.hud_version_detection.length +
      c.in_match_detection.length +
      Object.values(c.minimap_identification.maps).reduce((n, m) => n + m.zones.length, 0);
    const atCap = mutated((c) => {
      const pad = NATIVE_MAX_RULES - total(c);
      for (let i = 0; i < pad; i++) c.in_match_detection.push(zone(`pad_${i}`, 0, 0, 1, 1));
    });
    expect(problemOf(atCap)).toBeNull();
    const over = mutated((c) => {
      const pad = NATIVE_MAX_RULES - total(c) + 1;
      for (let i = 0; i < pad; i++) c.in_match_detection.push(zone(`pad_${i}`, 0, 0, 1, 1));
    });
    expect(problemOf(over)).toMatch(/151 rules/);
  });

  it(`:350-361 — a zone above MAX_RECT_TEXELS = ${NATIVE_MAX_RECT_TEXELS} after clamping`, () => {
    expect(problemOf(mutated((c) => c.in_match_detection.push(zone("big_ok", 0, 0, 64, 64))))).toBeNull();
    const over = mutated((c) => {
      c.minimap_identification.maps.mu_map!.zones.push(zone("big", 0, 0, 65, 64));
    });
    expect(problemOf(over)).toMatch(/zone big clamps to 65x64 = 4160 px/);
  });
});
