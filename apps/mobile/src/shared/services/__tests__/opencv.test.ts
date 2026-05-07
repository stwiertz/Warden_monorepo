// Pure-TS primitives backing the Story 7.5 detectors. No native deps:
// every test constructs synthetic FrameBuffers / GrayBuffers in memory.

import {
  cropToGrayscale,
  grayscaleMean,
  hammingDistance,
  hsvWhitePixelRatio,
  loadFrameFromPath,
  phash,
  resizeGrayscale,
  saturationMean,
  scaleRoi,
  type FrameBuffer,
  type GrayBuffer,
} from "../opencv";

function makeFrame(
  width: number,
  height: number,
  fill: (x: number, y: number) => [number, number, number]
): FrameBuffer {
  const data = new Uint8ClampedArray(width * height * 3);
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const [r, g, b] = fill(x, y);
      const i = (y * width + x) * 3;
      data[i] = r;
      data[i + 1] = g;
      data[i + 2] = b;
    }
  }
  return { data, width, height };
}

function makeGray(
  width: number,
  height: number,
  fill: (x: number, y: number) => number
): GrayBuffer {
  const data = new Uint8ClampedArray(width * height);
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      data[y * width + x] = fill(x, y);
    }
  }
  return { data, width, height };
}

describe("hsvWhitePixelRatio", () => {
  it("counts pure-white pixels as fully matching the near-white predicate", () => {
    const frame = makeFrame(10, 10, () => [255, 255, 255]);
    const ratio = hsvWhitePixelRatio(
      frame,
      { x: 0, y: 0, width: 10, height: 10 },
      12,
      230
    );
    expect(ratio).toBe(1);
  });

  it("returns 0 when the patch is fully saturated colour", () => {
    const frame = makeFrame(10, 10, () => [255, 0, 0]);
    const ratio = hsvWhitePixelRatio(
      frame,
      { x: 0, y: 0, width: 10, height: 10 },
      12,
      230
    );
    expect(ratio).toBe(0);
  });

  it("returns 0 when value is below valMin (dark grayscale)", () => {
    const frame = makeFrame(10, 10, () => [50, 50, 50]);
    const ratio = hsvWhitePixelRatio(
      frame,
      { x: 0, y: 0, width: 10, height: 10 },
      12,
      230
    );
    expect(ratio).toBe(0);
  });

  it("computes the fraction for a half-and-half synthetic patch", () => {
    // Left half: pure white. Right half: pure red. Predicate accepts only
    // the left half ⇒ ratio = 0.5.
    const frame = makeFrame(10, 10, (x) =>
      x < 5 ? [255, 255, 255] : [255, 0, 0]
    );
    const ratio = hsvWhitePixelRatio(
      frame,
      { x: 0, y: 0, width: 10, height: 10 },
      12,
      230
    );
    expect(ratio).toBe(0.5);
  });

  it("clips out-of-bounds ROI coordinates", () => {
    const frame = makeFrame(10, 10, () => [255, 255, 255]);
    const ratio = hsvWhitePixelRatio(
      frame,
      { x: -5, y: -5, width: 10, height: 10 },
      12,
      230
    );
    // Effective ROI is the top-left 5x5 ⇒ all white ⇒ 1.
    expect(ratio).toBe(1);
  });

  it("returns 0 for an empty/clipped-to-zero ROI", () => {
    const frame = makeFrame(10, 10, () => [255, 255, 255]);
    const ratio = hsvWhitePixelRatio(
      frame,
      { x: 100, y: 100, width: 10, height: 10 },
      12,
      230
    );
    expect(ratio).toBe(0);
  });
});

describe("grayscaleMean", () => {
  it("equals the gray value for a uniform patch", () => {
    const frame = makeFrame(8, 8, () => [128, 128, 128]);
    const mean = grayscaleMean(frame, { x: 0, y: 0, width: 8, height: 8 });
    expect(mean).toBeCloseTo(128, 5);
  });

  it("weights channels per BT.601", () => {
    // Pure red at full intensity ⇒ 0.299*255 ≈ 76.245
    const frame = makeFrame(4, 4, () => [255, 0, 0]);
    expect(grayscaleMean(frame, { x: 0, y: 0, width: 4, height: 4 })).toBeCloseTo(
      76.245,
      2
    );
  });
});

describe("saturationMean", () => {
  it("is 0 for a pure grayscale patch", () => {
    const frame = makeFrame(4, 4, () => [128, 128, 128]);
    expect(saturationMean(frame, { x: 0, y: 0, width: 4, height: 4 })).toBe(0);
  });

  it("approaches 255 for fully saturated colours", () => {
    const frame = makeFrame(4, 4, () => [255, 0, 0]);
    expect(saturationMean(frame, { x: 0, y: 0, width: 4, height: 4 })).toBeCloseTo(
      255,
      0
    );
  });
});

describe("scaleRoi", () => {
  it("returns the input unchanged when source and target match", () => {
    const roi = { x: 100, y: 50, width: 200, height: 100 };
    expect(
      scaleRoi(roi, { width: 1920, height: 1080 }, { width: 1920, height: 1080 })
    ).toEqual(roi);
  });

  it("scales 1920x1080 ROIs into 1280x720", () => {
    const roi = { x: 1920, y: 1080, width: 1920, height: 1080 };
    expect(
      scaleRoi(roi, { width: 1920, height: 1080 }, { width: 1280, height: 720 })
    ).toEqual({ x: 1280, y: 720, width: 1280, height: 720 });
  });
});

describe("cropToGrayscale + resizeGrayscale", () => {
  it("crops to the requested ROI and converts to luma", () => {
    const frame = makeFrame(10, 10, (x) =>
      x < 5 ? [255, 255, 255] : [0, 0, 0]
    );
    const gray = cropToGrayscale(frame, { x: 0, y: 0, width: 5, height: 5 });
    expect(gray.width).toBe(5);
    expect(gray.height).toBe(5);
    for (const pixel of gray.data) expect(pixel).toBeGreaterThan(254);
  });

  it("bilinearly resizes a checkerboard without dropping all detail", () => {
    const src = makeGray(8, 8, (x, y) => ((x + y) % 2 === 0 ? 255 : 0));
    const out = resizeGrayscale(src, 4, 4);
    expect(out.width).toBe(4);
    expect(out.height).toBe(4);
    // Bilinear blends opposite cells ⇒ output should sit near the midpoint.
    const sum = out.data.reduce((a: number, b: number) => a + b, 0);
    expect(sum / out.data.length).toBeGreaterThan(80);
    expect(sum / out.data.length).toBeLessThan(175);
  });
});

describe("phash + hammingDistance", () => {
  it("produces a 64-bit (16-hex-char) hash by default", () => {
    const gray = makeGray(64, 64, (x, y) => (x ^ y) & 0xff);
    const hash = phash(gray);
    expect(hash).toMatch(/^[0-9a-f]{16}$/);
  });

  it("hashes two visually different images to a large Hamming distance", () => {
    const a = makeGray(64, 64, (x) => (x < 32 ? 0 : 255));
    const b = makeGray(64, 64, (_x, y) => (y < 32 ? 0 : 255));
    const ha = phash(a);
    const hb = phash(b);
    expect(hammingDistance(ha, hb)).toBeGreaterThan(12);
  });

  it("hashes the same image to itself with Hamming distance 0", () => {
    const a = makeGray(64, 64, (x, y) => (x ^ y) & 0xff);
    expect(hammingDistance(phash(a), phash(a))).toBe(0);
  });

  it("hashes a slightly perturbed image to a small Hamming distance (≤ 12)", () => {
    // Perturb only ~5% of pixels by ±10 — pHash should be robust to this.
    const base = (x: number, y: number) => (x * 4 + y * 7) & 0xff;
    const a = makeGray(64, 64, base);
    const b = makeGray(64, 64, (x, y) => {
      const v = base(x, y);
      if ((x * 13 + y * 17) % 19 === 0) {
        return Math.max(0, Math.min(255, v + 10));
      }
      return v;
    });
    expect(hammingDistance(phash(a), phash(b))).toBeLessThanOrEqual(12);
  });

  it("rejects mismatched-length hashes", () => {
    expect(() => hammingDistance("abcd", "abcdef")).toThrow(/length mismatch/);
  });

  it("rejects non-hex characters", () => {
    expect(() => hammingDistance("zzzz", "0000")).toThrow(/non-hex/);
  });
});

describe("loadFrameFromPath", () => {
  it("throws a descriptive error until the native binding is wired up", async () => {
    await expect(loadFrameFromPath("ignored.jpg")).rejects.toThrow(
      /react-native-fast-opencv/
    );
  });
});
