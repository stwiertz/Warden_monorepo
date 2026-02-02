import * as DocumentPicker from "expo-document-picker";
import type { ValidationError, ImportOutcome } from "./types";
import { createSession } from "../session/sessionRepository";

const ALLOWED_MIME_TYPES = ["video/mp4"];
const ALLOWED_EXTENSIONS = [".mp4"];

function validateVideoFile(
  uri: string,
  mimeType: string | null | undefined,
  name: string | null | undefined
): ValidationError | null {
  const extension = name
    ? name.substring(name.lastIndexOf(".")).toLowerCase()
    : "";

  const hasValidMime =
    mimeType && ALLOWED_MIME_TYPES.includes(mimeType.toLowerCase());
  const hasValidExtension =
    extension && ALLOWED_EXTENSIONS.includes(extension);

  if (!hasValidMime && !hasValidExtension) {
    return {
      code: "INVALID_FORMAT",
      message:
        "Only MP4 video files (H.264/AAC) are supported. Please select a valid .mp4 file.",
    };
  }

  return null;
}

export async function pickAndImportVideo(): Promise<ImportOutcome> {
  const result = await DocumentPicker.getDocumentAsync({
    type: ALLOWED_MIME_TYPES,
    copyToCacheDirectory: false,
  });

  if (result.canceled) {
    return {
      success: false,
      error: {
        code: "PICKER_CANCELLED",
        message: "File selection was cancelled.",
      },
    };
  }

  const asset = result.assets[0];
  if (!asset) {
    return {
      success: false,
      error: {
        code: "FILE_NOT_FOUND",
        message: "No file was selected.",
      },
    };
  }

  const validationError = validateVideoFile(
    asset.uri,
    asset.mimeType,
    asset.name
  );
  if (validationError) {
    return { success: false, error: validationError };
  }

  const sessionName =
    asset.name?.replace(/\.mp4$/i, "") ?? "Untitled Session";
  const session = await createSession(asset.uri, sessionName);

  return {
    success: true,
    result: {
      sessionId: session.id,
      videoFilePath: asset.uri,
      name: sessionName,
    },
  };
}
