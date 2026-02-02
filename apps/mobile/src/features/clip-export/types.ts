/**
 * Types for clip export feature (FR21-25).
 */

export type ExportQuality = 'mobile' | 'hd';

export interface ExportConfig {
  sessionId: string;
  startTimeMs: number;
  endTimeMs: number;
  quality: ExportQuality;
  includeAudio: boolean;
}

export interface ExportProgress {
  progress: number; // 0-1
  stage: 'demux' | 'process' | 'mux' | 'complete';
}
