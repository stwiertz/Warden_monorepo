// Story 1.2 (BF-5) — wrapper-level guarantees of foregroundService.ts.
//
// The pipeline tests (processingPipeline.test.ts) mock this wrapper away, so
// the guarantees it advertises are asserted here against a mocked react-native
// surface (Platform=android, NativeModules.WardenProcessing stubbed):
//   1. stop NEVER rejects, even when the native stop fails (finally-safety).
//   2. Owner token: a stale stop after a newer start is a no-op.
//   3. start does not await the POST_NOTIFICATIONS dialog (AC9 — never block).
//   4. Launch reconciliation force-stops regardless of owner.

(globalThis as { __DEV__?: boolean }).__DEV__ ??= true;

const mockNativeStart = jest.fn();
const mockNativeUpdateStage = jest.fn();
const mockNativeStop = jest.fn();
const mockPermissionRequest = jest.fn();

jest.mock("react-native", () => ({
  Platform: { OS: "android", Version: 34 },
  NativeModules: {
    WardenProcessing: {
      start: (...args: unknown[]) => mockNativeStart(...args),
      updateStage: (...args: unknown[]) => mockNativeUpdateStage(...args),
      stop: (...args: unknown[]) => mockNativeStop(...args),
    },
  },
  PermissionsAndroid: {
    PERMISSIONS: { POST_NOTIFICATIONS: "android.permission.POST_NOTIFICATIONS" },
    RESULTS: { GRANTED: "granted" },
    request: (...args: unknown[]) => mockPermissionRequest(...args),
  },
}));

type ForegroundServiceModule =
  typeof import("../foregroundService");

describe("foregroundService wrapper (Story 1.2)", () => {
  let fgs: ForegroundServiceModule;

  beforeEach(() => {
    jest.clearAllMocks();
    // Fresh module instance per test: resets the module-level owner token.
    jest.resetModules();
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    fgs = require("../foregroundService");
    mockNativeStart.mockResolvedValue(undefined);
    mockNativeUpdateStage.mockResolvedValue(undefined);
    mockNativeStop.mockResolvedValue(undefined);
    mockPermissionRequest.mockResolvedValue("granted");
    jest.spyOn(console, "warn").mockImplementation(() => undefined);
  });

  afterEach(() => {
    (console.warn as jest.Mock).mockRestore();
  });

  it("stop never rejects when the native stop fails (finally-safety)", async () => {
    await fgs.startForegroundService("session-a");
    mockNativeStop.mockRejectedValueOnce(new Error("WARDEN_FGS_STOP_FAILED"));
    await expect(
      fgs.stopForegroundService("session-a")
    ).resolves.toBeUndefined();
  });

  it("skips a stale owner's stop after a newer pipeline takes the service", async () => {
    await fgs.startForegroundService("session-a");
    await fgs.startForegroundService("session-b");
    await fgs.stopForegroundService("session-a");
    expect(mockNativeStop).not.toHaveBeenCalled();
    await fgs.stopForegroundService("session-b");
    expect(mockNativeStop).toHaveBeenCalledTimes(1);
  });

  it("still stops natively when start claimed ownership but the native start threw", async () => {
    mockNativeStart.mockRejectedValueOnce(new Error("native start failed"));
    await expect(fgs.startForegroundService("session-a")).rejects.toThrow(
      "native start failed"
    );
    await fgs.stopForegroundService("session-a");
    expect(mockNativeStop).toHaveBeenCalledTimes(1);
  });

  it("does not await the POST_NOTIFICATIONS dialog before starting (AC9)", async () => {
    // A dialog the user never answers: the request promise never settles.
    mockPermissionRequest.mockReturnValueOnce(new Promise(() => undefined));
    await fgs.startForegroundService("session-a");
    expect(mockPermissionRequest).toHaveBeenCalledTimes(1);
    expect(mockNativeStart).toHaveBeenCalledWith("session-a");
  });

  it("launch reconciliation force-stops regardless of prior owner", async () => {
    await fgs.startForegroundService("session-a");
    await fgs.reconcileForegroundServiceAtLaunch();
    expect(mockNativeStop).toHaveBeenCalledTimes(1);
  });
});
