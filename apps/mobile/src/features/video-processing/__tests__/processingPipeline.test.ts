// Story 1.2 (BF-5) — foreground-service wire-up contract for runProcessingPipeline.
//
// Scope: the start/stop bridge calls only. The native bridge is mocked at the
// JS-wrapper layer (foregroundService.ts), so these tests never touch Kotlin —
// they assert the try/finally lifecycle:
//   1. start is called once on entry with the sessionId.
//   2. stop is called on successful completion.
//   3. stop is called when an inner stage throws (and status → "error").
//   4. stop is called even when start itself throws (outer-wrap shape).
//
// The pipeline's heavy collaborators (ffmpeg, opencv, detectors, repositories,
// storage) are mocked to no-ops so the happy path runs to completion with an
// empty keyframe set.

(globalThis as { __DEV__?: boolean }).__DEV__ ??= true;

// --- Foreground-service bridge (the system under test) -----------------------
jest.mock("../../../shared/services/foregroundService", () => ({
  startForegroundService: jest.fn().mockResolvedValue(undefined),
  stopForegroundService: jest.fn().mockResolvedValue(undefined),
  updateForegroundServiceStage: jest.fn().mockResolvedValue(undefined),
}));

// --- Heavy collaborators (mocked to keep the run trivial) --------------------
jest.mock("../../../shared/services/ffmpeg", () => ({
  extractKeyframes: jest.fn().mockResolvedValue([]),
  extractFrameAt: jest.fn().mockResolvedValue(undefined),
  getGopInfo: jest
    .fn()
    .mockResolvedValue({ hasShortGop: true, averageGopSeconds: 1 }),
  getProcessingDir: jest.fn().mockReturnValue("/tmp/processing"),
  getVideoDuration: jest.fn().mockResolvedValue(60_000),
}));

jest.mock("../../../shared/services/opencv", () => ({
  loadFrameFromPath: jest.fn().mockResolvedValue({
    data: new Uint8ClampedArray(0),
    width: 0,
    height: 0,
  }),
  saturationMean: jest.fn().mockReturnValue(0),
  scaleRoi: jest.fn((roi: unknown) => roi),
}));

jest.mock("../../session/sessionRepository", () => ({
  getSession: jest.fn().mockResolvedValue({
    id: "test-session-1",
    video_file_path: "/tmp/video.mp4",
    name: "test",
    status: "importing",
  }),
  updateSessionStatus: jest.fn().mockResolvedValue(undefined),
}));

jest.mock("../segmentRepository", () => ({
  insertMapSegments: jest.fn().mockResolvedValue([]),
  updateResultFramePath: jest.fn().mockResolvedValue(undefined),
}));

jest.mock("../../../shared/services/storage", () => ({
  storage: {
    getString: jest.fn().mockReturnValue(undefined),
    setString: jest.fn(),
    getNumber: jest.fn().mockReturnValue(0),
    setNumber: jest.fn(),
    getObject: jest.fn().mockReturnValue(undefined),
    setObject: jest.fn(),
    delete: jest.fn(),
  },
}));

jest.mock("../detectionConfigService", () => ({
  getDetectionConfig: jest.fn().mockResolvedValue({
    version: 1,
    reference_resolution: { width: 1920, height: 1080 },
    roi_zones: { team_bar: { x: 0, y: 0, width: 1, height: 1 } },
    thresholds: {},
  }),
}));

jest.mock("../gameDetector", () => ({
  createGameDetector: jest.fn().mockReturnValue({
    processFrame: jest.fn().mockReturnValue([]),
    flush: jest.fn().mockReturnValue([]),
  }),
  pairEventsIntoSegments: jest.fn().mockReturnValue([]),
}));

jest.mock("../mapIdentifier", () => ({
  createMapIdentifier: jest.fn().mockReturnValue({
    identify: jest.fn().mockReturnValue({ match: null, hash: "" }),
  }),
}));

jest.mock("../blackScreenDetector", () => ({
  buildSaturationWindowsFromValues: jest.fn().mockReturnValue([]),
  detectBlackScreensInWindow: jest.fn().mockReturnValue([]),
}));

jest.mock("../segmentation", () => ({
  buildMapSegments: jest.fn().mockReturnValue([]),
}));

import { runProcessingPipeline } from "../processingPipeline";
import {
  startForegroundService,
  stopForegroundService,
  updateForegroundServiceStage,
} from "../../../shared/services/foregroundService";
import { extractKeyframes } from "../../../shared/services/ffmpeg";
import { updateSessionStatus } from "../../session/sessionRepository";

const mockStart = startForegroundService as jest.Mock;
const mockStop = stopForegroundService as jest.Mock;
const mockUpdateStage = updateForegroundServiceStage as jest.Mock;
const mockExtractKeyframes = extractKeyframes as jest.Mock;
const mockUpdateStatus = updateSessionStatus as jest.Mock;

describe("runProcessingPipeline — foreground service wire-up (Story 1.2)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Re-prime the default resolved values cleared above.
    mockStart.mockResolvedValue(undefined);
    mockStop.mockResolvedValue(undefined);
    mockUpdateStage.mockResolvedValue(undefined);
    mockExtractKeyframes.mockResolvedValue([]);
    mockUpdateStatus.mockResolvedValue(undefined);
  });

  it("starts the foreground service once on entry with the sessionId", async () => {
    await runProcessingPipeline("test-session-1");
    expect(mockStart).toHaveBeenCalledTimes(1);
    expect(mockStart).toHaveBeenCalledWith("test-session-1");
  });

  it("stops the foreground service on successful completion and pushes stages", async () => {
    await runProcessingPipeline("test-session-1");
    expect(mockStop).toHaveBeenCalledTimes(1);
    // Owner-token contract: the finally-stop passes the owning sessionId so a
    // stale stop can never strip a newer pipeline's service.
    expect(mockStop).toHaveBeenCalledWith("test-session-1");
    // Lifecycle ordering: start strictly precedes stop.
    expect(mockStart.mock.invocationCallOrder[0]).toBeLessThan(
      mockStop.mock.invocationCallOrder[0]
    );
    expect(mockUpdateStatus).toHaveBeenCalledWith("test-session-1", "ready");
    // Stage is pushed to the notification as the pipeline advances.
    expect(mockUpdateStage).toHaveBeenCalledWith("keyframes");
  });

  it("stops the foreground service when an inner stage throws", async () => {
    mockExtractKeyframes.mockRejectedValueOnce(new Error("synthetic"));
    await expect(runProcessingPipeline("test-session-1")).rejects.toThrow(
      "synthetic"
    );
    expect(mockStop).toHaveBeenCalledTimes(1);
    expect(mockUpdateStatus).toHaveBeenCalledWith("test-session-1", "error");
  });

  it("stops the foreground service even when start itself throws", async () => {
    mockStart.mockRejectedValueOnce(new Error("native start failed"));
    await expect(runProcessingPipeline("test-session-1")).rejects.toThrow(
      "native start failed"
    );
    // The outer-wrap finally guarantees stop is still called, with the owner
    // token (start claims ownership before the native call can throw).
    expect(mockStop).toHaveBeenCalledTimes(1);
    expect(mockStop).toHaveBeenCalledWith("test-session-1");
    expect(mockUpdateStatus).toHaveBeenCalledWith("test-session-1", "error");
  });
});
