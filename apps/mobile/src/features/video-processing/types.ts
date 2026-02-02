export interface KeyframeInfo {
  path: string;
  timestampMs: number;
}

export interface TimestampRange {
  startMs: number;
  endMs: number;
}

export interface BlackScreenResult {
  ranges: TimestampRange[];
  frameCount: number;
  blackFrameCount: number;
}

export interface TemplateMatchResult {
  timestampMs: number;
  confidence: number;
  templateName: string;
}

export interface MapSegmentData {
  mapIndex: number;
  startTimeMs: number;
  endTimeMs: number;
  mapName: string | null;
  resultFramePath: string | null;
}

export type ProcessingStage =
  | "keyframes"
  | "detection"
  | "segmentation"
  | "results";

export interface ProcessingState {
  sessionId: string;
  stage: ProcessingStage;
  progress: number; // 0-100
  error: string | null;
}

export interface ProgressCallback {
  (stage: ProcessingStage, stageProgress: number): void;
}
