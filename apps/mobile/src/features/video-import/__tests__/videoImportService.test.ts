jest.mock("expo-document-picker", () => ({
  getDocumentAsync: jest.fn(),
}));
jest.mock("../../session/sessionRepository", () => ({
  createSession: jest.fn(),
}));

import * as DocumentPicker from "expo-document-picker";
import { pickAndImportVideo } from "../videoImportService";
import { createSession } from "../../session/sessionRepository";

const mockedPicker = DocumentPicker as jest.Mocked<typeof DocumentPicker>;
const mockedCreateSession = createSession as jest.MockedFunction<
  typeof createSession
>;

beforeEach(() => {
  jest.clearAllMocks();
});

describe("pickAndImportVideo", () => {
  it("invokes picker filtered to video/mp4 without copying to cache", async () => {
    mockedPicker.getDocumentAsync.mockResolvedValue({
      canceled: true,
      assets: null,
    } as Awaited<ReturnType<typeof DocumentPicker.getDocumentAsync>>);

    await pickAndImportVideo();

    expect(mockedPicker.getDocumentAsync).toHaveBeenCalledWith({
      type: ["video/mp4"],
      copyToCacheDirectory: false,
    });
  });

  it("returns PICKER_CANCELLED when the user cancels selection", async () => {
    mockedPicker.getDocumentAsync.mockResolvedValue({
      canceled: true,
      assets: null,
    } as Awaited<ReturnType<typeof DocumentPicker.getDocumentAsync>>);

    const outcome = await pickAndImportVideo();

    expect(outcome.success).toBe(false);
    if (!outcome.success) {
      expect(outcome.error.code).toBe("PICKER_CANCELLED");
    }
    expect(mockedCreateSession).not.toHaveBeenCalled();
  });

  it("returns INVALID_FORMAT when neither MIME type nor extension matches MP4", async () => {
    mockedPicker.getDocumentAsync.mockResolvedValue({
      canceled: false,
      assets: [
        {
          uri: "file:///storage/clip.mov",
          name: "clip.mov",
          mimeType: "video/quicktime",
          size: 1024,
        },
      ],
    } as Awaited<ReturnType<typeof DocumentPicker.getDocumentAsync>>);

    const outcome = await pickAndImportVideo();

    expect(outcome.success).toBe(false);
    if (!outcome.success) {
      expect(outcome.error.code).toBe("INVALID_FORMAT");
      expect(outcome.error.message).toMatch(/MP4/);
    }
    expect(mockedCreateSession).not.toHaveBeenCalled();
  });

  it("rejects files whose MIME contradicts MP4 even if the extension is .mp4", async () => {
    mockedPicker.getDocumentAsync.mockResolvedValue({
      canceled: false,
      assets: [
        {
          uri: "file:///storage/fake.mp4",
          name: "fake.mp4",
          mimeType: "image/jpeg",
          size: 1024,
        },
      ],
    } as Awaited<ReturnType<typeof DocumentPicker.getDocumentAsync>>);

    const outcome = await pickAndImportVideo();

    expect(outcome.success).toBe(false);
    if (!outcome.success) {
      expect(outcome.error.code).toBe("INVALID_FORMAT");
    }
    expect(mockedCreateSession).not.toHaveBeenCalled();
  });

  it("rejects files whose extension is not .mp4 even if MIME is missing", async () => {
    mockedPicker.getDocumentAsync.mockResolvedValue({
      canceled: false,
      assets: [
        {
          uri: "file:///storage/clip.mkv",
          name: "clip.mkv",
          mimeType: null,
          size: 1024,
          lastModified: 0,
        },
      ],
    } as unknown as Awaited<
      ReturnType<typeof DocumentPicker.getDocumentAsync>
    >);

    const outcome = await pickAndImportVideo();

    expect(outcome.success).toBe(false);
    if (!outcome.success) {
      expect(outcome.error.code).toBe("INVALID_FORMAT");
    }
  });

  it("accepts MP4 by extension when MIME type is missing", async () => {
    mockedPicker.getDocumentAsync.mockResolvedValue({
      canceled: false,
      assets: [
        {
          uri: "file:///storage/raw.MP4",
          name: "raw.MP4",
          mimeType: null,
          size: 2048,
          lastModified: 0,
        },
      ],
    } as unknown as Awaited<
      ReturnType<typeof DocumentPicker.getDocumentAsync>
    >);
    mockedCreateSession.mockResolvedValue({
      id: "session-1",
      video_file_path: "file:///storage/raw.MP4",
      name: "raw",
      duration_ms: null,
      status: "importing",
      created_at: "2026-05-02T00:00:00.000Z",
      updated_at: "2026-05-02T00:00:00.000Z",
    });

    const outcome = await pickAndImportVideo();

    expect(outcome.success).toBe(true);
    expect(mockedCreateSession).toHaveBeenCalledWith(
      "file:///storage/raw.MP4",
      "raw"
    );
  });

  it("creates a session with the picked URI and strips the .mp4 extension from the name", async () => {
    mockedPicker.getDocumentAsync.mockResolvedValue({
      canceled: false,
      assets: [
        {
          uri: "file:///storage/training.mp4",
          name: "training.mp4",
          mimeType: "video/mp4",
          size: 4096,
        },
      ],
    } as Awaited<ReturnType<typeof DocumentPicker.getDocumentAsync>>);
    mockedCreateSession.mockResolvedValue({
      id: "session-42",
      video_file_path: "file:///storage/training.mp4",
      name: "training",
      duration_ms: null,
      status: "importing",
      created_at: "2026-05-02T00:00:00.000Z",
      updated_at: "2026-05-02T00:00:00.000Z",
    });

    const outcome = await pickAndImportVideo();

    expect(mockedCreateSession).toHaveBeenCalledWith(
      "file:///storage/training.mp4",
      "training"
    );
    expect(outcome.success).toBe(true);
    if (outcome.success) {
      expect(outcome.result).toEqual({
        sessionId: "session-42",
        videoFilePath: "file:///storage/training.mp4",
        name: "training",
      });
    }
  });

  it("references the picked file in-place rather than copying it", async () => {
    mockedPicker.getDocumentAsync.mockResolvedValue({
      canceled: false,
      assets: [
        {
          uri: "content://com.android.providers.media/external/raw.mp4",
          name: "raw.mp4",
          mimeType: "video/mp4",
          size: 1024,
        },
      ],
    } as Awaited<ReturnType<typeof DocumentPicker.getDocumentAsync>>);
    mockedCreateSession.mockResolvedValue({
      id: "s",
      video_file_path: "content://com.android.providers.media/external/raw.mp4",
      name: "raw",
      duration_ms: null,
      status: "importing",
      created_at: "2026-05-02T00:00:00.000Z",
      updated_at: "2026-05-02T00:00:00.000Z",
    });

    await pickAndImportVideo();

    expect(mockedPicker.getDocumentAsync).toHaveBeenCalledWith(
      expect.objectContaining({ copyToCacheDirectory: false })
    );
    expect(mockedCreateSession).toHaveBeenCalledWith(
      "content://com.android.providers.media/external/raw.mp4",
      "raw"
    );
  });

  it("returns FILE_NOT_FOUND when picker returns no assets", async () => {
    mockedPicker.getDocumentAsync.mockResolvedValue({
      canceled: false,
      assets: [],
    } as unknown as Awaited<
      ReturnType<typeof DocumentPicker.getDocumentAsync>
    >);

    const outcome = await pickAndImportVideo();

    expect(outcome.success).toBe(false);
    if (!outcome.success) {
      expect(outcome.error.code).toBe("FILE_NOT_FOUND");
    }
    expect(mockedCreateSession).not.toHaveBeenCalled();
  });
});
