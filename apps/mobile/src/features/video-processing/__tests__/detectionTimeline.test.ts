// Story 12.4c review — `ptsUsToMs` must reproduce the PC oracle's
// `int(round(pts_s * 1000.0))`, including Python's half-to-even rounding.

import { ptsUsToMs } from "../detectionTimeline";

describe("ptsUsToMs", () => {
  it("rounds to the nearest millisecond", () => {
    expect(ptsUsToMs(0)).toBe(0);
    expect(ptsUsToMs(4_166_667)).toBe(4167);
    expect(ptsUsToMs(4_166_333)).toBe(4166);
  });

  it("rounds an exact half to EVEN, as Python's round() does", () => {
    // Math.round would give 4167 and 2 here — 1 ms off the oracle.
    expect(ptsUsToMs(4_166_500)).toBe(4166);
    expect(ptsUsToMs(4_167_500)).toBe(4168);
    expect(ptsUsToMs(1_500)).toBe(2);
    expect(ptsUsToMs(2_500)).toBe(2);
  });
});
