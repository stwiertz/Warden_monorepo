/**
 * Types for video processing feature (FR5-10).
 */

export type ProcessingStatus = 'idle' | 'extracting' | 'detecting' | 'matching' | 'completed' | 'failed';

export interface ProcessingProgress {
  status: ProcessingStatus;
  progress: number; // 0-1
  currentStep: string;
}

export interface BlackScreenResult {
  timestampMs: number;
  confidence: number;
}

export interface TemplateMatchResult {
  timestampMs: number;
  mapName: string;
  confidence: number;
}
