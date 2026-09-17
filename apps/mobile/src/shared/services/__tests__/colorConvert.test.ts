// Story 12.4b AC1/AC2 — the colour-constants cross-language guard.
//
// This replaces nothing and guards something new. When Story 12.4b deleted
// `WardenDetectionEngine.kt` it deleted `RESOLVE_YUV_FRAG`, which had been the
// single source of truth for the bt709 limited-range constants since 12.2 — and
// which 12.2 proved EXHAUSTIVELY offline over all 2^24 (Y, Cb, Cr) triples after
// finding TWO silent colour bugs the hard way (`bench/12-2/REPORT.md` §6).
//
// The constants now live in `plugins/kotlin/WardenColorConvert.kt`. Three things
// must not be allowed to drift apart silently:
//
//   1. the Kotlin literals,
//   2. `bench/12-2/ac3_numpy_reference.py`'s transcription of them (that script
//      is the exhaustive offline proof; its whole claim to independence is that
//      a human read the source and wrote the arithmetic again),
//   3. the pinned digest of the reference's output over the whole domain, which
//      the device re-computes in `WardenEngineBench.colorConstantsCheck()`.
//
// Jest cannot run Kotlin, and this repo has no Kotlin test framework by
// deliberate choice (Dev Notes → Testing standards). What jest CAN do is hold
// the two sides of a cross-language contract together, which is exactly where
// the `BENCH_MODES` guard earns its keep — and exactly where both colour bugs
// 12.2 found would have been caught a build cycle earlier.

import fs from "fs";
import path from "path";

const KOTLIN = path.resolve(
  __dirname,
  "../../../../plugins/kotlin/WardenColorConvert.kt"
);
const NUMPY = path.resolve(
  __dirname,
  "../../../../bench/12-2/ac3_numpy_reference.py"
);

function read(p: string): string {
  return fs.readFileSync(p, "utf8");
}

/** `const val NAME = 1.234` → "1.234". */
function kotlinConst(src: string, name: string): string | undefined {
  return new RegExp(`const val ${name}\\s*=\\s*([0-9.]+)`).exec(src)?.[1];
}

/** `NAME = 1.234` → "1.234". */
function pyConst(src: string, name: string): string | undefined {
  return new RegExp(`^${name}\\s*=\\s*([0-9.]+)`, "m").exec(src)?.[1];
}

describe("WardenColorConvert constants (Story 12.4b)", () => {
  it("carries the bt709 limited-range constants the shader was proved with", () => {
    const src = read(KOTLIN);
    // Transcribed from RESOLVE_YUV_FRAG, which is what `ac3_numpy_constants.json`
    // bounded at 1 unit on green over 0.179% of the 2^24 domain. These are the
    // ITU-R BT.709 PUBLISHED four-decimal values, which is also what FFmpeg uses
    // — agreement WITH FFmpeg, not deviation from it. Do not "improve" them to
    // the exact primaries-derived coefficients; that is a DIFFERENT conversion.
    expect(kotlinConst(src, "Y_OFFSET")).toBe("16.0");
    expect(kotlinConst(src, "Y_SCALE")).toBe("219.0");
    expect(kotlinConst(src, "C_OFFSET")).toBe("128.0");
    expect(kotlinConst(src, "C_SCALE")).toBe("224.0");
    expect(kotlinConst(src, "KR_CR")).toBe("1.5748");
    expect(kotlinConst(src, "KG_CB")).toBe("0.1873");
    expect(kotlinConst(src, "KG_CR")).toBe("0.4681");
    expect(kotlinConst(src, "KB_CB")).toBe("1.8556");
  });

  it("keeps the Kotlin and the exhaustive numpy reference on the same numbers", () => {
    const kt = read(KOTLIN);
    const py = read(NUMPY);
    for (const name of [
      "Y_OFFSET",
      "Y_SCALE",
      "C_OFFSET",
      "C_SCALE",
      "KR_CR",
      "KG_CB",
      "KG_CR",
      "KB_CB",
    ]) {
      const k = kotlinConst(kt, name);
      const p = pyConst(py, name);
      expect(k).toBeDefined();
      expect(p).toBeDefined();
      // Compared as NUMBERS: "16.0" and "16.0" are the same constant whether or
      // not the two languages spell trailing zeros the same way.
      expect(Number(k)).toBe(Number(p));
    }
  });

  it("re-points the numpy transcription guard at the file that now owns them", () => {
    // `verify_shader_transcription()` re-read `WardenDetectionEngine.kt` — a file
    // this story DELETES. Left alone it would have raised FileNotFoundError on
    // the one script that proves the constants, i.e. the exhaustive proof would
    // have become unrunnable at exactly the moment it became the only proof.
    const py = read(NUMPY);
    expect(py).not.toContain("WardenDetectionEngine.kt");
    expect(py).toContain("WardenColorConvert.kt");
  });

  it("samples chroma NEAREST, not interpolated", () => {
    // Trap 2. The ~2.46 dS residual against FFmpeg's rgb24 is a chroma-upsampling
    // POLICY difference (nearest vs swscale), not a matrix error. Bilinear would
    // change the fire bits, break AC3's parity, and diverge from lut.py / Tool 12
    // — which Story 9.16 re-points at this engine.
    const code = read(KOTLIN)
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/\/\/.*$/gm, "");
    expect(code).toMatch(/x\s*\/\s*2/);
    expect(code).toMatch(/y\s*\/\s*2/);
    expect(code).not.toMatch(/\blerp\b|\bbilinear\b|0\.5[fF]?\s*\*\s*\(/);
  });

  it("asserts geometry rather than rescaling it", () => {
    // Trap 4. `requireGeometry()` hard-failed off-1920x1080; Path Z had no such
    // assertion and silently rescaled, so every rect evaluated against resampled
    // pixels. Zone coordinates are calibrated at reference_resolution 1920x1080.
    const src = read(KOTLIN);
    expect(src).toContain("fun requireGeometry");
    expect(src).toMatch(/throw\s+IllegalArgumentException/);
  });

  it("keeps the device sweep pinned to the reference digest", () => {
    // The Kotlin constants can be right and the Kotlin ARITHMETIC still wrong —
    // a `+` where the shader has a `-` passes every literal check above. The
    // device re-computes all 2^24 triples and hashes them; this holds the pin
    // that hash is compared against in lockstep with the numpy reference that
    // produced it.
    const bench = read(
      path.resolve(__dirname, "../../../../plugins/kotlin/WardenEngineBench.kt")
    );
    const pinned = /REFERENCE_YUV_SWEEP_SHA256\s*=\s*\n?\s*"([0-9a-f]{64})"/.exec(
      bench
    );
    expect(pinned).not.toBeNull();
    const py = read(NUMPY);
    expect(py).toContain(pinned![1]);
  });
});
