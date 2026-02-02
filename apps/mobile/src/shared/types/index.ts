/**
 * Global shared types used across multiple features.
 */

export interface Session {
  id: string;
  videoUri: string;
  name: string;
  durationMs: number;
  createdAt: string;
  updatedAt: string;
}

export interface MapSegment {
  id: string;
  sessionId: string;
  mapIndex: number;
  startTimeMs: number;
  endTimeMs: number;
  mapName?: string;
}

export interface AudioComment {
  id: string;
  sessionId: string;
  startTimeMs: number;
  endTimeMs: number;
  audioUri: string;
  createdAt: string;
}

export interface ClipExport {
  id: string;
  sessionId: string;
  startTimeMs: number;
  endTimeMs: number;
  quality: ExportQuality;
  outputUri?: string;
  status: ExportStatus;
  createdAt: string;
}

export type ExportQuality = 'mobile' | 'hd';
export type ExportStatus = 'pending' | 'processing' | 'completed' | 'failed';
