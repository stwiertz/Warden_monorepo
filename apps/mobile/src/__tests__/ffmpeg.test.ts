// Unit tests for src/shared/services/ffmpeg.ts that DO NOT require the native
// FFmpeg module. We verify (a) the JS wrapper loads the wokcito package's
// expected named exports, (b) it surfaces a clear error when the module is
// missing, (c) it surfaces a different clear error when the module loads but
// exports are misshapen, and (d) the sessionId path-traversal guard.

jest.mock("expo-file-system", () => ({
  Paths: { cache: { uri: "file:///tmp/cache/" } },
  Directory: jest.fn().mockImplementation(() => ({
    exists: false,
    create: jest.fn(),
    delete: jest.fn(),
    list: jest.fn(() => []),
  })),
}));

describe("ffmpeg service — JS wrapper contract (no native module)", () => {
  beforeEach(() => {
    jest.resetModules();
  });

  it("getProcessingDir composes the cache path", () => {
    const { getProcessingDir } = require("../shared/services/ffmpeg");
    expect(getProcessingDir("abc-123")).toBe(
      "file:///tmp/cache/processing/abc-123"
    );
  });

  it("getProcessingDir rejects path-traversal sessionId", () => {
    const { getProcessingDir } = require("../shared/services/ffmpeg");
    expect(() => getProcessingDir("../evil")).toThrow(/Invalid sessionId/);
    expect(() => getProcessingDir("")).toThrow(/Invalid sessionId/);
    expect(() => getProcessingDir("a/b")).toThrow(/Invalid sessionId/);
  });

  it("cleanupProcessingFiles refuses unsafe sessionId before touching disk", () => {
    const { cleanupProcessingFiles } = require("../shared/services/ffmpeg");
    expect(() => cleanupProcessingFiles("..")).toThrow(/Invalid sessionId/);
  });

  it("assertSafeSessionId accepts UUIDs and alphanumerics", () => {
    const { __testing } = require("../shared/services/ffmpeg");
    expect(() =>
      __testing.assertSafeSessionId("550e8400-e29b-41d4-a716-446655440000")
    ).not.toThrow();
    expect(() => __testing.assertSafeSessionId("session_42")).not.toThrow();
  });

  it("throws clear error when @wokcito/ffmpeg-kit-react-native is missing", async () => {
    jest.doMock("@wokcito/ffmpeg-kit-react-native", () => {
      throw new Error("module not found");
    }, { virtual: true });
    const { extractFrameAt } = require("../shared/services/ffmpeg");
    await expect(
      extractFrameAt("/v.mp4", 1000, "/out/frame.jpg")
    ).rejects.toThrow(/FFmpeg native module not available/);
  });

  it("throws clear error when module loads but exports are misshapen", async () => {
    jest.doMock(
      "@wokcito/ffmpeg-kit-react-native",
      () => ({ /* missing FFmpegKit + FFprobeKit */ }),
      { virtual: true }
    );
    const { extractFrameAt } = require("../shared/services/ffmpeg");
    await expect(
      extractFrameAt("/v.mp4", 1000, "/out/frame.jpg")
    ).rejects.toThrow(/exports missing/);
  });

  // Story 12.4c re-pointed this from `extractKeyframes` (deleted with the
  // JPEG-to-disk stage) onto `extractFrameAt`, which is now the ONLY FFmpeg
  // call that takes a user-supplied video path. The property under test is the
  // one that matters for a path the user picked from their gallery: it is passed
  // as a discrete argv token, never interpolated into a shell-tokenized string.
  it("uses executeWithArguments (no shell tokenization) for frame extraction", async () => {
    const executeWithArguments = jest.fn().mockResolvedValue({
      getReturnCode: async () => ({ isValueSuccess: () => true }),
      getOutput: async () => "",
    });
    jest.doMock(
      "@wokcito/ffmpeg-kit-react-native",
      () => ({
        FFmpegKit: { executeWithArguments },
        FFprobeKit: { executeWithArguments: jest.fn() },
      }),
      { virtual: true }
    );

    const { extractFrameAt } = require("../shared/services/ffmpeg");
    const out = await extractFrameAt(
      '/sd/My "Quoted" Video.mp4',
      12_500,
      "/tmp/cache/processing/sess/results/map_0.jpg"
    );

    expect(executeWithArguments).toHaveBeenCalledTimes(1);
    const args = executeWithArguments.mock.calls[0][0];
    // The hostile path is passed as a discrete argv token, not interpolated
    // into a shell-tokenized command string.
    expect(args).toContain('/sd/My "Quoted" Video.mp4');
    expect(args.join(" ")).not.toMatch(/"\/sd\/My/); // no surrounding quotes added
    // The seek timestamp is seconds with ms precision, before -i.
    expect(args[args.indexOf("-ss") + 1]).toBe("12.500");
    expect(args.indexOf("-ss")).toBeLessThan(args.indexOf("-i"));
    expect(out).toBe("/tmp/cache/processing/sess/results/map_0.jpg");
  });
});
