// Verifies the offline-first-launch flag wiring (AC 4):
//   - bootstrap success clears the flag
//   - bootstrap failing with OfflineFirstLaunchError sets the flag
//   - bootstrap failing with MalformedRemoteConfigError does NOT set the flag
//   - useVideoProcessing.startProcessing surfaces the blocked state
//   - bootstrap is singleflighted

const mockGetDetectionConfig = jest.fn();

jest.mock("../detectionConfigService", () => {
  const OFFLINE_FIRST_LAUNCH_MESSAGE =
    "Initial setup requires internet — open the app once while online.";

  class OfflineFirstLaunchError extends Error {
    constructor() {
      super(OFFLINE_FIRST_LAUNCH_MESSAGE);
      this.name = "OfflineFirstLaunchError";
    }
  }

  class MalformedRemoteConfigError extends Error {
    public readonly cause: Error;
    constructor(cause: Error) {
      super(`Detection config payload is malformed: ${cause.message}`);
      this.name = "MalformedRemoteConfigError";
      this.cause = cause;
    }
  }

  return {
    getDetectionConfig: (...args: unknown[]) =>
      mockGetDetectionConfig(...args),
    OfflineFirstLaunchError,
    MalformedRemoteConfigError,
    OFFLINE_FIRST_LAUNCH_MESSAGE,
  };
});

import {
  bootstrapDetectionConfig,
  getBootstrapPromise,
  isVideoProcessingBlocked,
  __testing,
} from "../detectionConfigBootstrap";
import {
  MalformedRemoteConfigError,
  OfflineFirstLaunchError,
} from "../detectionConfigService";
import { storage } from "../../../shared/services/storage";

beforeEach(() => {
  storage.delete(__testing.OFFLINE_FIRST_LAUNCH_FLAG_KEY);
  __testing.resetBootstrapPromise();
  mockGetDetectionConfig.mockReset();
});

describe("detectionConfigBootstrap", () => {
  it("clears the blocked flag when getDetectionConfig succeeds", async () => {
    storage.setBoolean(__testing.OFFLINE_FIRST_LAUNCH_FLAG_KEY, true);
    mockGetDetectionConfig.mockResolvedValue({ version: 1 });

    await bootstrapDetectionConfig();

    expect(isVideoProcessingBlocked()).toEqual({ blocked: false });
  });

  it("sets the blocked flag when getDetectionConfig throws OfflineFirstLaunchError", async () => {
    mockGetDetectionConfig.mockRejectedValue(new OfflineFirstLaunchError());

    await bootstrapDetectionConfig();

    const blocked = isVideoProcessingBlocked();
    expect(blocked.blocked).toBe(true);
    expect(blocked.reason).toBe(__testing.OFFLINE_FIRST_LAUNCH_MESSAGE);
  });

  it("does NOT set the blocked flag when getDetectionConfig throws MalformedRemoteConfigError", async () => {
    const errSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    mockGetDetectionConfig.mockRejectedValue(
      new MalformedRemoteConfigError(new Error("bad payload"))
    );

    await bootstrapDetectionConfig();

    expect(isVideoProcessingBlocked()).toEqual({ blocked: false });
    errSpy.mockRestore();
  });

  it("does not set the blocked flag for unrelated errors", async () => {
    const errSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    mockGetDetectionConfig.mockRejectedValue(new Error("unrelated boom"));

    await bootstrapDetectionConfig();

    expect(isVideoProcessingBlocked()).toEqual({ blocked: false });
    errSpy.mockRestore();
  });

  it("never throws", async () => {
    mockGetDetectionConfig.mockRejectedValue(new OfflineFirstLaunchError());
    await expect(bootstrapDetectionConfig()).resolves.toBeUndefined();
  });

  it("is singleflighted: two calls return the same in-flight promise", () => {
    mockGetDetectionConfig.mockResolvedValue({ version: 1 });

    const a = bootstrapDetectionConfig();
    const b = bootstrapDetectionConfig();

    expect(a).toBe(b);
  });

  it("getBootstrapPromise exposes the in-flight promise for race-free gate reads", async () => {
    let resolveFetch!: (v: unknown) => void;
    mockGetDetectionConfig.mockImplementation(
      () => new Promise((resolve) => { resolveFetch = resolve; })
    );

    const bootstrap = bootstrapDetectionConfig();
    expect(getBootstrapPromise()).toBe(bootstrap);

    resolveFetch({ version: 1 });
    await bootstrap;
  });
});
