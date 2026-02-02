/**
 * Types for session persistence feature (FR26-28).
 */

export interface SessionState {
  currentSessionId: string | null;
  currentPosition: number;
  currentMapIndex: number;
  lastSavedAt: string | null;
}

export const AUTO_SAVE_INTERVAL_MS = 30_000;
