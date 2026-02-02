import type { KeyframeInfo, TemplateMatchResult } from "./types";

// TODO: Replace stub with real template matching algorithm.
// The real implementation will:
// - Run only on specific frames extracted before certain black screens
//   (at the end of each game)
// - Use OpenCV template matching against map end-screen templates
// - The user is developing the detection script externally
//
// Interface is ready for drop-in replacement.

export const TEMPLATE_CONFIDENCE_THRESHOLD = 0.7;

/**
 * Match keyframes against map end-screen templates.
 *
 * STUB IMPLEMENTATION: Returns empty array (no matches).
 * The segmentation pipeline will fall back to black-screen-only mode,
 * which is the expected behavior until real templates are integrated.
 *
 * @param keyframes - Array of keyframe info from FFmpeg extraction
 * @param _templateDir - Path to template images directory (unused in stub)
 * @returns Promise<TemplateMatchResult[]> — empty until real implementation
 */
export async function matchMapEndScreens(
  keyframes: KeyframeInfo[],
  _templateDir: string
): Promise<TemplateMatchResult[]> {
  // --- STUB: Return empty to trigger black-screen-only fallback ---
  return [];
  // --- END STUB ---
}
