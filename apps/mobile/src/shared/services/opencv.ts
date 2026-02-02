// OpenCV service — sole entry point for all OpenCV operations.
// Uses react-native-fast-opencv (JSI/C++ bindings).
//
// TODO: Integrate real react-native-fast-opencv when detection
// algorithms are finalized. Currently a placeholder service.

/**
 * Load an image from disk and return an OpenCV Mat handle.
 * Placeholder — will use cv.imread() from react-native-fast-opencv.
 */
export async function loadImage(_imagePath: string): Promise<unknown> {
  // Will be: const mat = cv.imread(imagePath);
  throw new Error("OpenCV not yet integrated. Waiting for detection script.");
}

/**
 * Convert an image to grayscale.
 */
export async function convertToGrayscale(_mat: unknown): Promise<unknown> {
  throw new Error("OpenCV not yet integrated.");
}

/**
 * Compute mean pixel value (luminosity) of an image/ROI.
 */
export async function computeMean(_mat: unknown): Promise<number> {
  throw new Error("OpenCV not yet integrated.");
}

/**
 * Run template matching on an image against a template.
 * Returns confidence score 0.0-1.0.
 */
export async function matchTemplate(
  _image: unknown,
  _template: unknown
): Promise<{ confidence: number; location: { x: number; y: number } }> {
  throw new Error("OpenCV not yet integrated.");
}
