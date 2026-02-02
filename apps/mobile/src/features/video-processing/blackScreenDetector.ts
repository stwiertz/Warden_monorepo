import type { KeyframeInfo, TimestampRange, BlackScreenResult } from "./types";

// TODO: Replace stub with real detection algorithm.
// The real implementation will analyze specific ROIs on extracted keyframes
// to detect black screens. The user is developing this externally and will
// provide the script to integrate here.

export const BLACK_SCREEN_LUMINOSITY_THRESHOLD = 15;
const GAP_TOLERANCE_MS = 5000;

/**
 * Detect black screen timestamp ranges from extracted keyframes.
 *
 * STUB IMPLEMENTATION: Returns fake black screen ranges for development.
 * The real implementation will:
 * - Load each keyframe image
 * - Analyze specific ROIs for luminosity
 * - Flag frames below threshold as black screens
 * - Group consecutive frames into timestamp ranges
 *
 * @param keyframes - Array of keyframe info from FFmpeg extraction
 * @returns Promise<BlackScreenResult> with detected timestamp ranges
 */
export async function detectBlackScreens(
  keyframes: KeyframeInfo[]
): Promise<BlackScreenResult> {
  if (keyframes.length === 0) {
    return { ranges: [], frameCount: 0, blackFrameCount: 0 };
  }

  // --- STUB: Generate fake black screen ranges ---
  // Simulate detection by placing black screens at regular intervals.
  // A typical Valorant VOD (~80 min) has ~3-5 map transitions.
  const totalDurationMs =
    keyframes[keyframes.length - 1].timestampMs - keyframes[0].timestampMs;

  if (totalDurationMs <= 0) {
    return { ranges: [], frameCount: keyframes.length, blackFrameCount: 0 };
  }

  const fakeRanges: TimestampRange[] = [];
  const mapCount = Math.max(2, Math.min(5, Math.floor(totalDurationMs / (20 * 60 * 1000))));
  const segmentDuration = totalDurationMs / (mapCount + 1);

  // First black screen: ~lobby end
  fakeRanges.push({
    startMs: Math.round(segmentDuration * 0.15),
    endMs: Math.round(segmentDuration * 0.15) + 2000,
  });

  // Black screens between maps
  for (let i = 1; i <= mapCount; i++) {
    const position = Math.round(segmentDuration * i);
    fakeRanges.push({
      startMs: position,
      endMs: position + 2000,
    });
  }

  return {
    ranges: fakeRanges,
    frameCount: keyframes.length,
    blackFrameCount: fakeRanges.length * 2,
  };
  // --- END STUB ---
}

/**
 * Merge close timestamp ranges that are within gap tolerance.
 * Utility for the real implementation.
 */
export function mergeCloseRanges(
  ranges: TimestampRange[],
  gapToleranceMs: number = GAP_TOLERANCE_MS
): TimestampRange[] {
  if (ranges.length === 0) return [];

  const sorted = [...ranges].sort((a, b) => a.startMs - b.startMs);
  const merged: TimestampRange[] = [{ ...sorted[0] }];

  for (let i = 1; i < sorted.length; i++) {
    const current = sorted[i];
    const last = merged[merged.length - 1];

    if (current.startMs - last.endMs <= gapToleranceMs) {
      last.endMs = Math.max(last.endMs, current.endMs);
    } else {
      merged.push({ ...current });
    }
  }

  return merged;
}
