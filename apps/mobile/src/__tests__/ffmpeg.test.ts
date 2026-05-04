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
    const { extractKeyframes } = require("../shared/services/ffmpeg");
    await expect(extractKeyframes("/v.mp4", "sess")).rejects.toThrow(
      /FFmpeg native module not available/
    );
  });

  it("throws clear error when module loads but exports are misshapen", async () => {
    jest.doMock(
      "@wokcito/ffmpeg-kit-react-native",
      () => ({ /* missing FFmpegKit + FFprobeKit */ }),
      { virtual: true }
    );
    const { extractKeyframes } = require("../shared/services/ffmpeg");
    await expect(extractKeyframes("/v.mp4", "sess")).rejects.toThrow(
      /exports missing/
    );
  });

  it("uses executeWithArguments (no shell tokenization) for keyframe extraction", async () => {
    const executeWithArguments = jest.fn().mockResolvedValue({
      getReturnCode: async () => ({ isValueSuccess: () => true }),
      getOutput: async () => "",
      getAllLogs: async () => [
        { getMessage: () => "[showinfo @ 0x0] n:0 pts_time:1.234" },
      ],
    });
    jest.doMock(
      "@wokcito/ffmpeg-kit-react-native",
      () => ({
        FFmpegKit: { executeWithArguments },
        FFprobeKit: { executeWithArguments: jest.fn() },
      }),
      { virtual: true }
    );

    // Pretend the file was written so we get the timestamp pairing path.
    const fileSystem = require("expo-file-system");
    fileSystem.Directory.mockImplementation(() => ({
      exists: true,
      create: jest.fn(),
      delete: jest.fn(),
      list: jest.fn(() => [{ name: "frame_0001.jpg" }]),
    }));

    const { extractKeyframes } = require("../shared/services/ffmpeg");
    const result = await extractKeyframes(
      '/sd/My "Quoted" Video.mp4',
      "sess"
    );

    expect(executeWithArguments).toHaveBeenCalledTimes(1);
    const args = executeWithArguments.mock.calls[0][0];
    // The hostile path is passed as a discrete argv token, not interpolated
    // into a shell-tokenized command string.
    expect(args).toContain('/sd/My "Quoted" Video.mp4');
    expect(args.join(" ")).not.toMatch(/"\/sd\/My/); // no surrounding quotes added
    expect(result).toEqual([
      { path: "file:///tmp/cache/processing/sess/keyframes/frame_0001.jpg", timestampMs: 1234 },
    ]);
  });
});
