import * as DocumentPicker from "expo-document-picker";
import type { ValidationError, ImportOutcome } from "./types";
import { createSession } from "../session/sessionRepository";

const ALLOWED_MIME_TYPES = ["video/mp4"];
const ALLOWED_EXTENSIONS = [".mp4"];

// Container-only check (MIME + extension). Codec verification (H.264/AAC) is
// deferred to the Story 2.2 FFmpeg pipeline — files with a valid .mp4
// container but unsupported codecs will surface there as a processing error.
function validateVideoFile(
  uri: string,
  mimeType: string | null | undefined,
  name: string | null | undefined
): ValidationError | null {
  const invalidFormat: ValidationError = {
    code: "INVALID_FORMAT",
    message:
      "Only MP4 video files (H.264/AAC) are supported. Please select a valid .mp4 file.",
  };

  // If the picker reported a MIME type, it must match. We deliberately do NOT
  // fall back to extension when MIME explicitly disagrees — that would let a
  // renamed image/audio file slip through.
  if (mimeType) {
    return ALLOWED_MIME_TYPES.includes(mimeType.toLowerCase())
      ? null
      : invalidFormat;
  }

  // No MIME reported — fall back to extension.
  const extension = name
    ? name.substring(name.lastIndexOf(".")).toLowerCase()
    : "";
  return ALLOWED_EXTENSIONS.includes(extension) ? null : invalidFormat;
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
