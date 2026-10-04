// Story 1.13 AC4 / AC5 / AC8 / AC9 / AC10 — the post-auth Firestore overlay.
//
// HOIST NOTE (carried over from the deleted v1 detectionConfigService.test.ts):
// jest hoists jest.mock() factories above the file's imports, AND Babel's
// ES-module compilation hoists `import` → `require()` above the module-scope
// `const mockX = jest.fn()` declarations. So factories run BEFORE those consts
// initialize — a direct `default: mockFn` ref dereferences `undefined`. The
// factory reference is wrapped in a lazy thunk that defers the deref to call time.

import { createHash } from "crypto";

const mockGet: jest.Mock = jest.fn();
const mockDoc: jest.Mock = jest.fn(() => ({
  get: (...a: unknown[]) => mockGet(...a),
}));
const mockCollection: jest.Mock = jest.fn(() => ({
  doc: (...a: unknown[]) => mockDoc(...a),
}));
const mockFirestoreFn: jest.Mock = jest.fn(() => ({
  collection: (...a: unknown[]) => mockCollection(...a),
}));

jest.mock("@react-native-firebase/firestore", () => {
  function lazyFirestore(...args: unknown[]): unknown {
    return mockFirestoreFn(...args);
  }
  return { __esModule: true, default: lazyFirestore };
});

// expo-crypto's digest is native; back it with node's SHA-256 over the UTF-8
// bytes — exactly what the device computes. The fixture's sha256 was produced
// by the Python builder (hashlib over the file bytes): this suite is the
// cross-language parity check.
jest.mock("expo-crypto", () => ({
  CryptoDigestAlgorithm: { SHA256: "SHA-256" },
  digestStringAsync: jest.fn(async (_alg: string, data: string) =>
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    require("crypto").createHash("sha256").update(data, "utf8").digest("hex")
  ),
}));

import { storage } from "../../../shared/services/storage";
import {
  BUNDLED_MAP_CONFIG_REVISION,
} from "../bundledMapConfigs";
import {
  __resetMapConfigCacheForTests,
  getPrimaryMapConfig,
  listMapConfigCandidates,
} from "../mapConfig";
import {
  LEGACY_DETECTION_STORAGE_KEYS,
  refreshMapConfigOverlay,
  type DetectionConfigEnvelope,
} from "../mapConfigOverlay";
import {
  MAP_CONFIG_OVERLAY_STORAGE_KEY,
  readCachedOverlay,
} from "../mapConfigOverlayCache";

// eslint-disable-next-line @typescript-eslint/no-require-imports
const FIXTURE: DetectionConfigEnvelope = require("./fixtures/overlay-envelope.json");
const FIXTURE_TEXT = FIXTURE.configs.v2!.config_json;

function sha(text: string): string {
  return createHash("sha256").update(text, "utf8").digest("hex");
}

function snapshot(payload: unknown) {
  return {
    exists: () => payload !== null && payload !== undefined,
    data: () => payload,
  };
}

function firestoreError(code: string): Error {
  return Object.assign(new Error(`[${code}] simulated`), { code });
}

function envelopeWith(revision: number, configs: Record<string, { config_json: string; sha256?: string }>) {
  return {
    envelope_version: 1,
    revision,
    configs: Object.fromEntries(
      Object.entries(configs).map(([k, v]) => [k, { config_json: v.config_json, sha256: v.sha256 ?? sha(v.config_json) }])
    ),
  };
}

function fixtureConfigWith(patch: (c: Record<string, unknown>) => void): string {
  const c = JSON.parse(FIXTURE_TEXT) as Record<string, unknown>;
  patch(c);
  return JSON.stringify(c, null, 2);
}

let warnSpy: jest.SpyInstance;
let logSpy: jest.SpyInstance;

beforeEach(() => {
  __resetMapConfigCacheForTests();
  mockGet.mockReset();
  mockFirestoreFn.mockClear();
  mockCollection.mockClear();
  mockDoc.mockClear();
  warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});
  logSpy = jest.spyOn(console, "log").mockImplementation(() => {});
});

afterEach(() => {
  warnSpy.mockRestore();
  logSpy.mockRestore();
});

describe("refreshMapConfigOverlay — success", () => {
  it("reads detection_config/latest through the RNFB namespaced chain and caches a newer envelope", async () => {
    mockGet.mockResolvedValueOnce(snapshot(FIXTURE));

    const result = await refreshMapConfigOverlay();

    expect(mockCollection).toHaveBeenCalledWith("detection_config");
    expect(mockDoc).toHaveBeenCalledWith("latest");
    expect(result).toEqual({ reason: "updated", revision: 2, droppedEntries: [] });
    // Stored as the envelope's JSON text; the config text inside is untouched.
    const stored = JSON.parse(storage.getString(MAP_CONFIG_OVERLAY_STORAGE_KEY)!);
    expect(stored.revision).toBe(2);
    expect(stored.configs.v2.config_json).toBe(FIXTURE_TEXT);
  });

  it("the fixture's Python-computed sha256 matches the device-side digest (cross-language parity)", () => {
    expect(FIXTURE.configs.v2!.sha256).toBe(sha(FIXTURE_TEXT));
  });

  it("🔴 the next session's candidate is the remote config with rawJson === config_json verbatim", async () => {
    const before = getPrimaryMapConfig();
    expect(before.source).toBe("bundled");

    mockGet.mockResolvedValueOnce(snapshot(FIXTURE));
    await refreshMapConfigOverlay();

    // A session that captured its candidate at start keeps it.
    expect(before.source).toBe("bundled");
    // The memo was invalidated by the write: the next session gets the overlay.
    const after = getPrimaryMapConfig();
    expect(after.source).toBe("remote");
    expect(after.revision).toBe(2);
    expect(after.rawJson).toBe(FIXTURE_TEXT);
    expect(Object.keys(after.config.minimap_identification.maps)).toEqual([
      "zeta_map",
      "alpha_map",
      "mu_map",
    ]);
    expect(logSpy).toHaveBeenCalledWith("[map-config] source=remote revision=2 hud=v2");
  });

  it("keeps the good entries of a partly-bad envelope (per-HUD fallback)", async () => {
    const badV1 = fixtureConfigWith((c) => {
      c.hud_version = "v1";
    });
    mockGet.mockResolvedValueOnce(
      snapshot(envelopeWith(4, { v1: { config_json: badV1, sha256: "0".repeat(64) }, v2: { config_json: FIXTURE_TEXT } }))
    );

    const result = await refreshMapConfigOverlay();

    expect(result.reason).toBe("updated");
    expect(result.droppedEntries.map((d) => [d.hudVersion, d.problem])).toEqual([["v1", "sha256-mismatch"]]);
    expect(Object.keys(readCachedOverlay()!.configs)).toEqual(["v2"]);
  });

  it("🔴 D1: an envelope carrying {v2, v3} still delivers the v2 update to this (v2-only) build", async () => {
    mockGet.mockResolvedValueOnce(
      snapshot(envelopeWith(5, { v2: { config_json: FIXTURE_TEXT }, v3: { config_json: "{\"future\": true}" } }))
    );

    const result = await refreshMapConfigOverlay();

    expect(result.reason).toBe("updated");
    expect(result.revision).toBe(5);
    expect(result.droppedEntries.map((d) => [d.hudVersion, d.problem])).toEqual([["v3", "unknown-hud"]]);
    expect(Object.keys(readCachedOverlay()!.configs)).toEqual(["v2"]);
    const primary = getPrimaryMapConfig();
    expect(primary.source).toBe("remote");
    expect(primary.revision).toBe(5);
    expect(primary.rawJson).toBe(FIXTURE_TEXT);
  });

  it("D1: an unknown HUD key with a MALFORMED entry still fails the envelope (known entries stay strict too)", async () => {
    mockGet.mockResolvedValueOnce(
      snapshot({
        envelope_version: 1,
        revision: 5,
        configs: { v2: { config_json: FIXTURE_TEXT, sha256: sha(FIXTURE_TEXT) }, v3: { config_json: "{}" } },
      })
    );
    await expect(refreshMapConfigOverlay()).resolves.toMatchObject({ reason: "malformed-envelope" });
    mockGet.mockResolvedValueOnce(
      snapshot({ envelope_version: 1, revision: 5, configs: { v2: { config_json: FIXTURE_TEXT, sha256: "x" } } })
    );
    await expect(refreshMapConfigOverlay()).resolves.toMatchObject({ reason: "malformed-envelope" });
    expect(getPrimaryMapConfig().source).toBe("bundled");
  });

  it("D2: a config the native packer would reject is dropped at receive time; the bundle stays in use", async () => {
    const duplicatedSlug = FIXTURE_TEXT.replace('"zeta_map": {', '"alpha_map": { "zones": [] },\n      "zeta_map": {');
    mockGet.mockResolvedValueOnce(snapshot(envelopeWith(5, { v2: { config_json: duplicatedSlug } })));

    const result = await refreshMapConfigOverlay();

    expect(result.reason).toBe("malformed-entry");
    expect(result.droppedEntries.map((d) => d.problem)).toEqual(["native-invalid"]);
    expect(warnSpy).toHaveBeenCalledTimes(1);
    expect(storage.getString(MAP_CONFIG_OVERLAY_STORAGE_KEY)).toBeUndefined();
    expect(getPrimaryMapConfig().source).toBe("bundled");
  });

  it("is singleflighted: concurrent callers share one Firestore read", async () => {
    let release!: (v: unknown) => void;
    mockGet.mockImplementationOnce(() => new Promise((r) => (release = r)));

    const a = refreshMapConfigOverlay();
    const b = refreshMapConfigOverlay();
    expect(a).toBe(b);
    release(snapshot(FIXTURE));
    await expect(a).resolves.toMatchObject({ reason: "updated" });
    expect(mockGet).toHaveBeenCalledTimes(1);
  });
});

describe("refreshMapConfigOverlay — AC10 failure table: every failure falls back, labelled, silently", () => {
  type Case = {
    name: string;
    arrange: () => void;
    reason: string;
    problem?: string;
    code?: string;
    envelopeProblem?: string;
  };

  const cases: Case[] = [
    {
      name: "permission-denied (today's rules, until 1.14 + 1.15)",
      arrange: () => mockGet.mockRejectedValueOnce(firestoreError("firestore/permission-denied")),
      reason: "permission-denied",
      code: "firestore/permission-denied",
    },
    {
      name: "unavailable",
      arrange: () => mockGet.mockRejectedValueOnce(firestoreError("firestore/unavailable")),
      reason: "unavailable",
      code: "firestore/unavailable",
    },
    {
      name: "error without a code (a bug, not the network)",
      arrange: () => mockGet.mockRejectedValueOnce(new TypeError("snap.exists is not a function")),
      reason: "error",
    },
    {
      name: "document missing",
      arrange: () => mockGet.mockResolvedValueOnce(snapshot(undefined)),
      reason: "not-found",
    },
    {
      name: "malformed envelope",
      arrange: () => mockGet.mockResolvedValueOnce(snapshot({ revision: 9, configs: "nope" })),
      reason: "malformed-envelope",
      envelopeProblem: "invalid",
    },
    {
      name: "unknown envelope_version",
      arrange: () =>
        mockGet.mockResolvedValueOnce(
          snapshot({ ...envelopeWith(9, { v2: { config_json: FIXTURE_TEXT } }), envelope_version: 2 })
        ),
      reason: "malformed-envelope",
      envelopeProblem: "unknown-envelope-version",
    },
    {
      name: "sha256 mismatch",
      arrange: () =>
        mockGet.mockResolvedValueOnce(
          snapshot(envelopeWith(9, { v2: { config_json: FIXTURE_TEXT, sha256: "a".repeat(64) } }))
        ),
      reason: "malformed-entry",
      problem: "sha256-mismatch",
    },
    {
      name: "config_json is not JSON",
      arrange: () => mockGet.mockResolvedValueOnce(snapshot(envelopeWith(9, { v2: { config_json: "{not json" } }))),
      reason: "malformed-entry",
      problem: "not-json",
    },
    {
      name: "config fails MapConfigSchema (schema_version 2)",
      arrange: () =>
        mockGet.mockResolvedValueOnce(
          snapshot(
            envelopeWith(9, {
              v2: {
                config_json: fixtureConfigWith((c) => {
                  c.schema_version = 2;
                }),
              },
            })
          )
        ),
      reason: "malformed-entry",
      problem: "schema-invalid",
    },
    {
      name: "entry key ≠ hud_version",
      arrange: () => mockGet.mockResolvedValueOnce(snapshot(envelopeWith(9, { v1: { config_json: FIXTURE_TEXT } }))),
      reason: "malformed-entry",
      problem: "hud-mismatch",
    },
    {
      name: "only an unknown HUD key (code-review D1)",
      arrange: () => mockGet.mockResolvedValueOnce(snapshot(envelopeWith(9, { v3: { config_json: FIXTURE_TEXT } }))),
      reason: "malformed-entry",
      problem: "unknown-hud",
    },
    {
      name: "config the native packer would reject (code-review D2)",
      arrange: () =>
        mockGet.mockResolvedValueOnce(
          snapshot(
            envelopeWith(9, {
              v2: { config_json: FIXTURE_TEXT.replace('"alpha_map": {', '"alpha\\u005fmap": {') },
            })
          )
        ),
      reason: "malformed-entry",
      problem: "native-invalid",
    },
    {
      name: "revision not newer than the cache",
      arrange: () => mockGet.mockResolvedValueOnce(snapshot(envelopeWith(2, { v2: { config_json: FIXTURE_TEXT } }))),
      reason: "not-newer",
    },
  ];

  it.each(cases)("$name → $reason, cache intact, one warning, no throw", async (c) => {
    // A valid cache (revision 2) exists before the failing refresh.
    mockGet.mockResolvedValueOnce(snapshot(FIXTURE));
    await refreshMapConfigOverlay();
    const cachedBefore = storage.getString(MAP_CONFIG_OVERLAY_STORAGE_KEY);
    warnSpy.mockClear();

    c.arrange();
    const result = await refreshMapConfigOverlay(); // resolves — never rejects

    expect(result.reason).toBe(c.reason);
    if (c.code) expect(result.code).toBe(c.code);
    expect(result.envelopeProblem).toBe(c.envelopeProblem);
    if (c.problem) expect(result.droppedEntries.map((d) => d.problem)).toEqual([c.problem]);
    expect(warnSpy).toHaveBeenCalledTimes(1);
    if (c.code) expect(String(warnSpy.mock.calls[0][0])).toContain(c.code);
    expect(storage.getString(MAP_CONFIG_OVERLAY_STORAGE_KEY)).toBe(cachedBefore);
    expect(getPrimaryMapConfig().source).toBe("remote");
  });

  it("every condition is distinguishable by (reason, problem, envelopeProblem)", async () => {
    // Computed from what the CODE returns (not from the table's own labels):
    // run each case on a clean slate and collect the result's discriminators.
    const keys: string[] = [];
    for (const c of cases) {
      __resetMapConfigCacheForTests();
      mockGet.mockReset();
      mockGet.mockResolvedValueOnce(snapshot(FIXTURE));
      await refreshMapConfigOverlay();
      c.arrange();
      const r = await refreshMapConfigOverlay();
      keys.push(`${r.reason}/${r.droppedEntries.map((d) => d.problem).join(",")}/${r.envelopeProblem ?? ""}`);
    }
    expect(new Set(keys).size).toBe(cases.length);
  });

  it("with no cache, a failure leaves the session on the bundled config", async () => {
    mockGet.mockRejectedValueOnce(firestoreError("firestore/permission-denied"));
    await expect(refreshMapConfigOverlay()).resolves.toMatchObject({ reason: "permission-denied" });
    expect(storage.getString(MAP_CONFIG_OVERLAY_STORAGE_KEY)).toBeUndefined();
    expect(getPrimaryMapConfig().source).toBe("bundled");
  });

  it("a revision that does not beat the shipped bundle is not cached", async () => {
    mockGet.mockResolvedValueOnce(
      snapshot(envelopeWith(BUNDLED_MAP_CONFIG_REVISION, { v2: { config_json: FIXTURE_TEXT } }))
    );
    await expect(refreshMapConfigOverlay()).resolves.toMatchObject({ reason: "not-newer" });
    expect(storage.getString(MAP_CONFIG_OVERLAY_STORAGE_KEY)).toBeUndefined();
  });

  it("never throws, even when firestore() itself throws synchronously", async () => {
    mockFirestoreFn.mockImplementationOnce(() => {
      throw firestoreError("app/no-app");
    });
    await expect(refreshMapConfigOverlay()).resolves.toMatchObject({ reason: "error", code: "app/no-app" });
  });
});

describe("🔴 AC4(b) / AC9 — shapes that must be rejected, never accepted-and-reordered", () => {
  it("a config uploaded as a nested object (no envelope — a naive upload of the bare file) is rejected", async () => {
    mockGet.mockResolvedValueOnce(snapshot(JSON.parse(FIXTURE_TEXT)));
    await expect(refreshMapConfigOverlay()).resolves.toMatchObject({ reason: "malformed-envelope" });
    expect(getPrimaryMapConfig().source).toBe("bundled");
  });

  it("an envelope whose entry is a nested object instead of config_json text is rejected", async () => {
    mockGet.mockResolvedValueOnce(
      snapshot({ envelope_version: 1, revision: 5, configs: { v2: JSON.parse(FIXTURE_TEXT) } })
    );
    await expect(refreshMapConfigOverlay()).resolves.toMatchObject({ reason: "malformed-envelope" });
    expect(getPrimaryMapConfig().source).toBe("bundled");
  });

  it("the v1 pHash document still in production `latest` is rejected and the bundle is used", async () => {
    mockGet.mockResolvedValueOnce(
      snapshot({
        version: 3,
        reference_resolution: { width: 1920, height: 1080 },
        roi_zones: { minimap: { x: 0, y: 0, width: 10, height: 10 } },
        thresholds: { brightness_threshold: 18 },
        maps: { ascent: "deadbeefdeadbeef" },
      })
    );
    await expect(refreshMapConfigOverlay()).resolves.toMatchObject({ reason: "malformed-envelope" });
    expect(storage.getString(MAP_CONFIG_OVERLAY_STORAGE_KEY)).toBeUndefined();
    expect(getPrimaryMapConfig().source).toBe("bundled");
  });

  it("an envelope with an empty configs map is rejected", async () => {
    mockGet.mockResolvedValueOnce(snapshot({ envelope_version: 1, revision: 5, configs: {} }));
    await expect(refreshMapConfigOverlay()).resolves.toMatchObject({ reason: "malformed-envelope" });
  });
});

describe("AC8 — legacy v1 MMKV keys", () => {
  it("are deleted once at overlay-module init (idempotent)", () => {
    jest.isolateModules(() => {
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      const { storage: isolated } = require("../../../shared/services/storage");
      isolated.setString("detection.config", "{}");
      isolated.setBoolean("detection.offlineFirstLaunchBlocked", true);
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      require("../mapConfigOverlay");
      expect(isolated.getString("detection.config")).toBeUndefined();
      expect(isolated.getBoolean("detection.offlineFirstLaunchBlocked")).toBeUndefined();
    });
    expect([...LEGACY_DETECTION_STORAGE_KEYS]).toEqual([
      "detection.config",
      "detection.offlineFirstLaunchBlocked",
    ]);
  });

  it("the seam never depends on them: no candidate list is empty", () => {
    expect(listMapConfigCandidates().length).toBeGreaterThan(0);
  });
});
