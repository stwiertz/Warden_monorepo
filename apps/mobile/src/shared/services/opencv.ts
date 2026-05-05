// Frame primitives library used by Story 7.5 detectors (gameDetector,
// mapIdentifier, blackScreenDetector fallback). The story's algorithms are
// pure-data: they consume a typed RGB FrameBuffer plus an ROI and return
// scalar/hash results, with no native dependency. JPEG decoding (turning a
// keyframe path on disk into a FrameBuffer) is the only step that still
// requires a native binding (react-native-fast-opencv); that boundary lives
// behind `loadFrameFromPath` and currently throws until the native wrapper
// is wired up. Tests construct synthetic FrameBuffers directly.
//
// All primitives operate on tightly packed byte arrays so the same code paths
// run on Android, iOS, and Node (jest). HSV is computed from RGB on demand —
// we never need a separate HSV buffer.

export interface FrameBuffer {
  // RGB packed: data[i*3+0]=R, data[i*3+1]=G, data[i*3+2]=B, all 0..255.
  data: Uint8ClampedArray;
  width: number;
  height: number;
}

export interface GrayBuffer {
  // Single-channel grayscale, 0..255, length = width*height.
  data: Uint8ClampedArray;
  width: number;
  height: number;
}

export interface ROI {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface Resolution {
  width: number;
  height: number;
}

function clipRoi(frame: { width: number; height: number }, roi: ROI): ROI {
  const x0 = Math.max(0, Math.floor(roi.x));
  const y0 = Math.max(0, Math.floor(roi.y));
  const x1 = Math.min(frame.width, Math.floor(roi.x + roi.width));
  const y1 = Math.min(frame.height, Math.floor(roi.y + roi.height));
  return { x: x0, y: y0, width: Math.max(0, x1 - x0), height: Math.max(0, y1 - y0) };
}

/**
 * Scale an ROI defined in `from` reference resolution to `to` processing
 * resolution. ROIs in DetectionConfig are 1920x1080-relative; videos at
 * 720p need to be scaled before pixel reads.
 */
export function scaleRoi(roi: ROI, from: Resolution, to: Resolution): ROI {
  if (from.width === to.width && from.height === to.height) return { ...roi };
  const sx = to.width / from.width;
  const sy = to.height / from.height;
  // Round the right/bottom edges from (x+width)*sx so they track the source
  // ROI's edges to within ±0.5 px instead of compounding a separate width
  // rounding on top of an already-rounded x.
  const x = Math.round(roi.x * sx);
  const y = Math.round(roi.y * sy);
  return {
    x,
    y,
    width: Math.round((roi.x + roi.width) * sx) - x,
    height: Math.round((roi.y + roi.height) * sy) - y,
  };
}

/**
 * Fraction of pixels inside the ROI that satisfy the "near-white" predicate
 * in HSV: saturation ≤ satMax AND value ≥ valMin (both 0..255). Computed
 * inline from RGB without materialising an HSV buffer.
 *
 * KDA digits ("3 / 7 / 12" etc.) are rendered in pure white over a darkened
 * HUD strip; counting white pixels in the kda ROI is the cheapest reliable
 * "is gameplay HUD on screen" signal per the Warden-tooling methodology.
 */
export function hsvWhitePixelRatio(
  frame: FrameBuffer,
  roi: ROI,
  satMax: number,
  valMin: number
): number {
  const { x, y, width, height } = clipRoi(frame, roi);
  if (width === 0 || height === 0) return 0;

  const data = frame.data;
  const rowStride = frame.width * 3;
  let total = 0;
  let hits = 0;
  for (let row = y; row < y + height; row++) {
    let idx = row * rowStride + x * 3;
    for (let col = 0; col < width; col++, idx += 3) {
      const r = data[idx];
      const g = data[idx + 1];
      const b = data[idx + 2];
      const max = r >= g ? (r >= b ? r : b) : g >= b ? g : b;
      const min = r <= g ? (r <= b ? r : b) : g <= b ? g : b;
      const v = max;
      // OpenCV HSV-8U scales sat to 0..255 as ((max-min)/max)*255 when max>0.
      // We use the same formula so config thresholds calibrated against
      // OpenCV/Python tools stay valid.
      const s = max > 0 ? Math.round(((max - min) * 255) / max) : 0;
      if (s <= satMax && v >= valMin) hits++;
      total++;
    }
  }
  return total === 0 ? 0 : hits / total;
}

/**
 * ITU-R BT.601 luma mean of the ROI: 0.299R + 0.587G + 0.114B per pixel,
 * then averaged. Matches the brightness measure used by OpenCV's
 * cvtColor(..., COLOR_BGR2GRAY) and by the original Sprint 2 detector.
 */
export function grayscaleMean(frame: FrameBuffer, roi: ROI): number {
  const { x, y, width, height } = clipRoi(frame, roi);
  if (width === 0 || height === 0) return 0;
  const data = frame.data;
  const rowStride = frame.width * 3;
  let sum = 0;
  let count = 0;
  for (let row = y; row < y + height; row++) {
    let idx = row * rowStride + x * 3;
    for (let col = 0; col < width; col++, idx += 3) {
      sum += 0.299 * data[idx] + 0.587 * data[idx + 1] + 0.114 * data[idx + 2];
      count++;
    }
  }
  return count === 0 ? 0 : sum / count;
}

/**
 * Mean saturation (HSV-8U scale, 0..255) over the ROI. Used by the long-GOP
 * black-screen Pass-1 to find candidate transition windows: gameplay frames
 * have high mean saturation (colourful UI), lobby/black frames are near-zero.
 */
export function saturationMean(frame: FrameBuffer, roi: ROI): number {
  const { x, y, width, height } = clipRoi(frame, roi);
  if (width === 0 || height === 0) return 0;
  const data = frame.data;
  const rowStride = frame.width * 3;
  let sum = 0;
  let count = 0;
  for (let row = y; row < y + height; row++) {
    let idx = row * rowStride + x * 3;
    for (let col = 0; col < width; col++, idx += 3) {
      const r = data[idx];
      const g = data[idx + 1];
      const b = data[idx + 2];
      const max = r >= g ? (r >= b ? r : b) : g >= b ? g : b;
      const min = r <= g ? (r <= b ? r : b) : g <= b ? g : b;
      sum += max > 0 ? ((max - min) * 255) / max : 0;
      count++;
    }
  }
  return count === 0 ? 0 : sum / count;
}

/**
 * Crop the ROI out of an RGB frame and convert to grayscale in one pass.
 * Used by mapIdentifier before pHash.
 */
export function cropToGrayscale(frame: FrameBuffer, roi: ROI): GrayBuffer {
  const { x, y, width, height } = clipRoi(frame, roi);
  const out = new Uint8ClampedArray(Math.max(1, width * height));
  if (width === 0 || height === 0) {
    return { data: out, width: Math.max(1, width), height: Math.max(1, height) };
  }
  const src = frame.data;
  const srcStride = frame.width * 3;
  let o = 0;
  for (let row = y; row < y + height; row++) {
    let idx = row * srcStride + x * 3;
    for (let col = 0; col < width; col++, idx += 3, o++) {
      out[o] = Math.round(
        0.299 * src[idx] + 0.587 * src[idx + 1] + 0.114 * src[idx + 2]
      );
    }
  }
  return { data: out, width, height };
}

/**
 * Bilinear resize for grayscale buffers. Bilinear (rather than nearest) is
 * the right choice here: pHash quality drops sharply with nearest-neighbor
 * because aliasing fakes high-frequency content the DCT then encodes as
 * bits, raising false-collision rates.
 */
export function resizeGrayscale(src: GrayBuffer, w: number, h: number): GrayBuffer {
  if (w <= 0 || h <= 0) {
    throw new Error(`resizeGrayscale: target dimensions must be positive, got ${w}x${h}`);
  }
  const out = new Uint8ClampedArray(w * h);
  if (src.width === w && src.height === h) {
    out.set(src.data);
    return { data: out, width: w, height: h };
  }
  const sx = src.width / w;
  const sy = src.height / h;
  for (let dy = 0; dy < h; dy++) {
    const fy = (dy + 0.5) * sy - 0.5;
    const y0 = Math.max(0, Math.floor(fy));
    const y1 = Math.min(src.height - 1, y0 + 1);
    const wy = fy - y0;
    for (let dx = 0; dx < w; dx++) {
      const fx = (dx + 0.5) * sx - 0.5;
      const x0 = Math.max(0, Math.floor(fx));
      const x1 = Math.min(src.width - 1, x0 + 1);
      const wx = fx - x0;
      const a = src.data[y0 * src.width + x0];
      const b = src.data[y0 * src.width + x1];
      const c = src.data[y1 * src.width + x0];
      const d = src.data[y1 * src.width + x1];
      const top = a + (b - a) * wx;
      const bot = c + (d - c) * wx;
      out[dy * w + dx] = Math.round(top + (bot - top) * wy);
    }
  }
  return { data: out, width: w, height: h };
}

/**
 * 1D DCT-II of a length-N row, in place is unsafe because output uses a
 * different basis — we materialise a new array. Implementation is the
 * straightforward O(N²) form; N is small (32 or 64) so FFT-based DCTs aren't
 * worth the complexity.
 */
function dct1D(src: number[]): number[] {
  const n = src.length;
  const out = new Array<number>(n);
  for (let k = 0; k < n; k++) {
    let sum = 0;
    const factor = (Math.PI * k) / (2 * n);
    for (let i = 0; i < n; i++) {
      sum += src[i] * Math.cos((2 * i + 1) * factor);
    }
    out[k] = sum;
  }
  return out;
}

/**
 * 2D DCT-II via separable 1D DCT (row pass + column pass). Result is
 * unnormalised — pHash only cares about relative ordering of coefficients.
 */
function dct2D(src: GrayBuffer): number[] {
  const { width: w, height: h, data } = src;
  // Row pass — produces an h×w grid of row-DCT coefficients.
  const rowDct: number[][] = new Array(h);
  const row = new Array<number>(w);
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) row[x] = data[y * w + x];
    rowDct[y] = dct1D(row);
  }
  // Column pass.
  const out = new Array<number>(w * h);
  const col = new Array<number>(h);
  for (let x = 0; x < w; x++) {
    for (let y = 0; y < h; y++) col[y] = rowDct[y][x];
    const dctCol = dct1D(col);
    for (let y = 0; y < h; y++) out[y * w + x] = dctCol[y];
  }
  return out;
}

export const PHASH_CANVAS_SIZE = 64;
export const PHASH_HASH_SIZE = 8;

/**
 * Perceptual hash of a grayscale buffer. Pipeline:
 *   1. Resize to canvasSize × canvasSize (default 64×64) bilinear.
 *   2. 2D DCT-II of the canvas.
 *   3. Take the top-left hashSize × hashSize block of low-frequency coefs.
 *   4. Drop the DC coefficient at [0,0] (it's the overall brightness; keeping
 *      it makes the hash sensitive to global luma shifts, defeating the
 *      "robust to encoding/lighting" property).
 *   5. Median over the remaining 63 coefficients; bits = 1 if coef > median.
 *   6. Encode 64 bits as 16-char lowercase hex (MSB-first).
 *
 * The hash format matches the reference Python `imagehash.phash` layout so
 * fingerprints generated offline can be compared byte-for-byte.
 */
export function phash(
  src: GrayBuffer,
  canvasSize: number = PHASH_CANVAS_SIZE,
  hashSize: number = PHASH_HASH_SIZE
): string {
  if (canvasSize < hashSize) {
    throw new Error(
      `phash: canvasSize (${canvasSize}) must be ≥ hashSize (${hashSize})`
    );
  }

  const canvas = resizeGrayscale(src, canvasSize, canvasSize);
  const dct = dct2D(canvas);

  const lowFreq: number[] = [];
  for (let y = 0; y < hashSize; y++) {
    for (let x = 0; x < hashSize; x++) {
      lowFreq.push(dct[y * canvasSize + x]);
    }
  }

  const withoutDC = lowFreq.slice(1).sort((a, b) => a - b);
  const mid = withoutDC.length >> 1;
  const median =
    withoutDC.length % 2 === 0
      ? (withoutDC[mid - 1] + withoutDC[mid]) / 2
      : withoutDC[mid];

  const bits: number[] = lowFreq.map((c) => (c > median ? 1 : 0));
  // Force the DC bit to 0 so the median comparison can't accidentally pin it
  // to 1 (the DC magnitude is typically orders larger). This matches the
  // reference imagehash implementation's "ignore DC" behaviour.
  bits[0] = 0;

  return bitsToHex(bits);
}

function bitsToHex(bits: number[]): string {
  // Pad up to a multiple of 4 with trailing zeros so any hashSize works.
  while (bits.length % 4 !== 0) bits.push(0);
  let hex = "";
  for (let i = 0; i < bits.length; i += 4) {
    const nibble = (bits[i] << 3) | (bits[i + 1] << 2) | (bits[i + 2] << 1) | bits[i + 3];
    hex += nibble.toString(16);
  }
  return hex;
}

const POPCOUNT16: Uint8Array = (() => {
  const t = new Uint8Array(256);
  for (let i = 0; i < 256; i++) {
    let v = i;
    let c = 0;
    while (v) {
      c += v & 1;
      v >>= 1;
    }
    t[i] = c;
  }
  return t;
})();

/**
 * Hamming distance between two equal-length lowercase hex strings. Uses a
 * 256-entry popcount table so per-frame map identification stays cheap when
 * scanning ~dozens of fingerprints per segment.
 */
export function hammingDistance(a: string, b: string): number {
  if (a.length !== b.length) {
    throw new Error(
      `hammingDistance: hash length mismatch (${a.length} vs ${b.length})`
    );
  }
  let dist = 0;
  for (let i = 0; i < a.length; i += 2) {
    const byteA = parseInt(a.slice(i, i + 2), 16);
    const byteB = parseInt(b.slice(i, i + 2), 16);
    if (Number.isNaN(byteA) || Number.isNaN(byteB)) {
      throw new Error(
        `hammingDistance: non-hex characters at position ${i}`
      );
    }
    dist += POPCOUNT16[byteA ^ byteB];
  }
  return dist;
}

/**
 * Decode a JPEG (or PNG) keyframe on disk into an RGB FrameBuffer. The
 * native binding (react-native-fast-opencv) is not yet wired into the dev
 * client, so this throws — call sites that need full pipeline execution
 * pass an alternative loader (tests synthesise FrameBuffers directly).
 *
 * The boundary is intentionally narrow: every detection algorithm above is
 * pure TS and works on any FrameBuffer source.
 */
export async function loadFrameFromPath(_path: string): Promise<FrameBuffer> {
  throw new Error(
    "loadFrameFromPath: JPEG decode requires react-native-fast-opencv. Wire up the native module to enable on-device processing."
  );
}
