jest.mock("../videoImportService", () => ({
  pickAndImportVideo: jest.fn(),
}));

import { pickAndImportVideo } from "../videoImportService";
import { executeImportFlow } from "../useVideoImport";
import type { ImportOutcome } from "../types";

const mockedPick = pickAndImportVideo as jest.MockedFunction<
  typeof pickAndImportVideo
>;

beforeEach(() => {
  jest.clearAllMocks();
});

describe("executeImportFlow", () => {
  it("calls onSuccess with the session id when import succeeds", async () => {
    mockedPick.mockResolvedValue({
      success: true,
      result: {
        sessionId: "session-1",
        videoFilePath: "file:///x.mp4",
        name: "x",
      },
    } satisfies ImportOutcome);
    const onError = jest.fn();
    const onSuccess = jest.fn();

    await executeImportFlow({ onError, onSuccess });

    expect(onSuccess).toHaveBeenCalledWith("session-1");
    expect(onError).not.toHaveBeenCalled();
  });

  it("calls onError with INVALID_FORMAT when validation fails", async () => {
    mockedPick.mockResolvedValue({
      success: false,
      error: { code: "INVALID_FORMAT", message: "Only MP4 supported." },
    } satisfies ImportOutcome);
    const onError = jest.fn();
    const onSuccess = jest.fn();

    await executeImportFlow({ onError, onSuccess });

    expect(onError).toHaveBeenCalledWith({
      code: "INVALID_FORMAT",
      message: "Only MP4 supported.",
    });
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it("silently swallows PICKER_CANCELLED — neither callback fires", async () => {
    mockedPick.mockResolvedValue({
      success: false,
      error: { code: "PICKER_CANCELLED", message: "Cancelled." },
    } satisfies ImportOutcome);
    const onError = jest.fn();
    const onSuccess = jest.fn();

    await executeImportFlow({ onError, onSuccess });

    expect(onError).not.toHaveBeenCalled();
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it("surfaces unexpected exceptions as UNKNOWN_ERROR with the original message", async () => {
    mockedPick.mockRejectedValue(new Error("DB write failed"));
    const onError = jest.fn();
    const onSuccess = jest.fn();

    await executeImportFlow({ onError, onSuccess });

    expect(onError).toHaveBeenCalledWith({
      code: "UNKNOWN_ERROR",
      message: "DB write failed",
    });
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it("falls back to a generic message when a non-Error is thrown", async () => {
    mockedPick.mockRejectedValue("string boom");
    const onError = jest.fn();

    await executeImportFlow({ onError, onSuccess: jest.fn() });

    expect(onError).toHaveBeenCalledWith({
      code: "UNKNOWN_ERROR",
      message: "An unexpected error occurred during import.",
    });
  });

  it("forwards FILE_NOT_FOUND from the service to onError", async () => {
    mockedPick.mockResolvedValue({
      success: false,
      error: { code: "FILE_NOT_FOUND", message: "No file was selected." },
    } satisfies ImportOutcome);
    const onError = jest.fn();
    const onSuccess = jest.fn();

    await executeImportFlow({ onError, onSuccess });

    expect(onError).toHaveBeenCalledWith({
      code: "FILE_NOT_FOUND",
      message: "No file was selected.",
    });
    expect(onSuccess).not.toHaveBeenCalled();
  });
});
