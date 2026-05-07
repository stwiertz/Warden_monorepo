// Mocks Firebase to keep these tests offline + deterministic.
// The service module is required after each jest.doMock so the mocks bind.

const mockGetDoc = jest.fn();

jest.mock("firebase/firestore", () => ({
  getFirestore: jest.fn(() => ({})),
  doc: jest.fn((_db: unknown, path: string) => ({ path })),
  getDoc: (...args: unknown[]) => mockGetDoc(...args),
}));

jest.mock("../../auth/firebaseConfig", () => ({
  app: {},
  auth: {},
}));

import {
  getDetectionConfig,
  refreshDetectionConfig,
  getCachedDetectionConfig,
  OfflineFirstLaunchError,
  MalformedRemoteConfigError,
  DETECTION_CONFIG_STORAGE_KEY,
  __clearDetectionConfigCacheForTests,
} from "../detectionConfigService";
import { storage } from "../../../shared/services/storage";

function validRemotePayload(version: number) {
  return {
    version,
    reference_resolution: { width: 1920, height: 1080 },
    roi_zones: {
      minimap: { x: 0, y: 0, width: 10, height: 10 },
      vertical: { x: 0, y: 0, width: 10, height: 10 },
      team_bar: { x: 0, y: 0, width: 10, height: 10 },
      kda: { x: 0, y: 0, width: 10, height: 10 },
      notkda: { x: 0, y: 0, width: 10, height: 10 },
      map_name: { x: 0, y: 0, width: 10, height: 10 },
    },
    thresholds: {
      brightness_threshold: 18,
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
    maps: { ascent: "deadbeef" },
  };
}

function mockSnapshot(payload: unknown) {
  return {
    exists: () => payload !== null && payload !== undefined,
    data: () => payload,
  };
}

let errorSpy: jest.SpyInstance;
let warnSpy: jest.SpyInstance;

beforeEach(() => {
  __clearDetectionConfigCacheForTests();
  mockGetDoc.mockReset();
  // The service intentionally logs on failure paths; silence to keep test
  // output clean while still letting tests assert thrown/returned behaviour.
  errorSpy = jest.spyOn(console, "error").mockImplementation(() => {});
  warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});
});

afterEach(() => {
  errorSpy.mockRestore();
  warnSpy.mockRestore();
});

describe("detectionConfigService — fetch + cache", () => {
  it("AC 1 — first launch with no cache fetches and writes to MMKV", async () => {
    mockGetDoc.mockResolvedValueOnce(mockSnapshot(validRemotePayload(1)));

    const config = await getDetectionConfig();

    expect(config.version).toBe(1);
    expect(config.thresholds.brightness_threshold).toBe(18);
    expect(getCachedDetectionConfig()).toBeDefined();
    expect(storage.getObject(DETECTION_CONFIG_STORAGE_KEY)).toMatchObject({
      config: { version: 1 },
    });
  });

  it("AC 2 — version-based refresh: cached version equal to remote keeps cache untouched", async () => {
    mockGetDoc.mockResolvedValue(mockSnapshot(validRemotePayload(2)));

    // Seed cache at version 2
    storage.setObject(DETECTION_CONFIG_STORAGE_KEY, {
      config: { ...validRemotePayload(2) },
      fetchedAt: 100,
    });

    const updated = await refreshDetectionConfig();
    expect(updated).toBe(false);

    // Cache fetchedAt unchanged because we did not rewrite
    const cached = storage.getObject<{ fetchedAt: number }>(
      DETECTION_CONFIG_STORAGE_KEY
    );
    expect(cached?.fetchedAt).toBe(100);
  });

  it("AC 2 — version-based refresh: remote > cached triggers rewrite", async () => {
    mockGetDoc.mockResolvedValue(mockSnapshot(validRemotePayload(5)));

    storage.setObject(DETECTION_CONFIG_STORAGE_KEY, {
      config: { ...validRemotePayload(2) },
      fetchedAt: 100,
    });

    const updated = await refreshDetectionConfig();
    expect(updated).toBe(true);

    expect(getCachedDetectionConfig()?.version).toBe(5);
  });

  it("AC 3 — offline + cache present: returns cached config without throwing", async () => {
    mockGetDoc.mockRejectedValue(new Error("network unreachable"));

    storage.setObject(DETECTION_CONFIG_STORAGE_KEY, {
      config: { ...validRemotePayload(3) },
      fetchedAt: 100,
    });

    const result = await getDetectionConfig();
    expect(result.version).toBe(3);
  });

  it("AC 4 — offline + no cache: throws OfflineFirstLaunchError", async () => {
    mockGetDoc.mockRejectedValue(new Error("network unreachable"));

    await expect(getDetectionConfig()).rejects.toBeInstanceOf(
      OfflineFirstLaunchError
    );
  });

  it("AC 6 — malformed config is rejected and cache untouched", async () => {
    // Seed valid cache first
    storage.setObject(DETECTION_CONFIG_STORAGE_KEY, {
      config: { ...validRemotePayload(2) },
      fetchedAt: 100,
    });

    // Remote returns garbage
    mockGetDoc.mockResolvedValue(mockSnapshot({ version: -1, broken: true }));

    const updated = await refreshDetectionConfig();
    expect(updated).toBe(false);

    // Cache version still 2
    expect(getCachedDetectionConfig()?.version).toBe(2);
  });

  it("AC 6 — Firestore document missing is rejected without writing the cache", async () => {
    mockGetDoc.mockResolvedValue(mockSnapshot(undefined));

    await expect(getDetectionConfig()).rejects.toBeInstanceOf(
      OfflineFirstLaunchError
    );
    expect(getCachedDetectionConfig()).toBeUndefined();
  });

  it("AC 6 — malformed remote on no-cache path throws MalformedRemoteConfigError (not OfflineFirstLaunchError)", async () => {
    mockGetDoc.mockResolvedValue(mockSnapshot({ version: -1, broken: true }));

    await expect(getDetectionConfig()).rejects.toBeInstanceOf(
      MalformedRemoteConfigError
    );
    expect(getCachedDetectionConfig()).toBeUndefined();
  });

  it("singleflight: concurrent first-launch fetches share a single Firestore round-trip", async () => {
    mockGetDoc.mockImplementation(
      () =>
        new Promise((resolve) =>
          setTimeout(
            () => resolve(mockSnapshot(validRemotePayload(1))),
            10
          )
        )
    );

    const [a, b, c] = await Promise.all([
      getDetectionConfig(),
      getDetectionConfig(),
      getDetectionConfig(),
    ]);

    expect(a.version).toBe(1);
    expect(b.version).toBe(1);
    expect(c.version).toBe(1);
    expect(mockGetDoc).toHaveBeenCalledTimes(1);
  });

  it("singleflight: concurrent refreshDetectionConfig calls share a single fetch", async () => {
    mockGetDoc.mockImplementation(
      () =>
        new Promise((resolve) =>
          setTimeout(
            () => resolve(mockSnapshot(validRemotePayload(7))),
            10
          )
        )
    );

    const results = await Promise.all([
      refreshDetectionConfig(),
      refreshDetectionConfig(),
    ]);

    expect(results).toEqual([true, true]);
    expect(mockGetDoc).toHaveBeenCalledTimes(1);
    expect(getCachedDetectionConfig()?.version).toBe(7);
  });

  it("getCachedDetectionConfig discards a corrupt cache and returns undefined", () => {
    // Seed a payload that fails schema validation
    storage.setObject(DETECTION_CONFIG_STORAGE_KEY, {
      config: { version: -1, broken: true },
      fetchedAt: 100,
    });

    expect(getCachedDetectionConfig()).toBeUndefined();
    // Corrupt entry was deleted on read
    expect(
      storage.getObject(DETECTION_CONFIG_STORAGE_KEY)
    ).toBeUndefined();
  });
});
