/**
 * Types for video import feature (FR1-4).
 */

export interface VideoImportResult {
  uri: string;
  fileName: string;
  durationMs: number;
  sizeBytes: number;
  codec: string;
}

export interface VideoValidationError {
  code: 'INVALID_FORMAT' | 'UNSUPPORTED_CODEC' | 'FILE_TOO_LARGE' | 'FILE_NOT_FOUND';
  message: string;
}
