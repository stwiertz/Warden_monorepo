/**
 * Types for video playback feature (FR11-15).
 */

export type ViewMode = 'pov' | 'minimap';

export interface PlaybackState {
  isPlaying: boolean;
  positionMs: number;
  durationMs: number;
  viewMode: ViewMode;
  currentMapIndex: number;
}

export interface RoiCropConfig {
  x: number;
  y: number;
  width: number;
  height: number;
}
