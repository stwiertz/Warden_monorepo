export interface ImportResult {
  sessionId: string;
  videoFilePath: string;
  name: string;
}

export interface ValidationError {
  code: "INVALID_FORMAT" | "FILE_NOT_FOUND" | "PICKER_CANCELLED";
  message: string;
}

export type ImportOutcome =
  | { success: true; result: ImportResult }
  | { success: false; error: ValidationError };
