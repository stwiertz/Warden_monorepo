/**
 * Types for audio commentary feature (FR16-20).
 */

export type RecordingState = 'idle' | 'recording' | 'paused';

export interface CommentaryTrack {
  id: string;
  sessionId: string;
  startTimeMs: number;
  endTimeMs: number;
  audioUri: string;
}
