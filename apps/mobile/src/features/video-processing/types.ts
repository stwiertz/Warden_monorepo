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

// Story 7.5 — Game detector + map identifier outputs.

export type GameDetectorEventType = "START" | "END" | "SCORE_SCREEN";

export interface GameDetectorEvent {
  type: GameDetectorEventType;
  timestamp_ms: number;
}

export interface GameSegment {
  startMs: number;
  endMs: number;
  scoreScreenMs: number; // endMs + score_offset_s*1000, clamped to video duration
}

export interface MapIdentificationResult {
  segmentIndex: number; // index into the GameSegment[] array
  mapName: string | null;
  hash: string;
  hammingDistance: number | null; // null when mapName is null (no match)
}
