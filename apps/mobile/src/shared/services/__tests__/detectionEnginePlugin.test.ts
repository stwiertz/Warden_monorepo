// Story 12.2 AC4 — the verbatim-shader guard, tested.
//
// AC4 requires the equality between the tooling `.frag` and the Android copy to
// be asserted MECHANICALLY "so drift fails loudly rather than silently". The
// plugin's `readVerbatimFrag` is that mechanism and it is pure, so it is the one
// part of the native surface that can be unit-tested with no device and no GL.
//
// This is deliberately a test of the GUARD, not of the shader: the shader's
// correctness is 12.1's (0 disagreements over 2666 frames) and its on-device
// behaviour is the bench's.

const path = require("path");

type Plugin = {
  readVerbatimFrag: () => string;
  FRAG_SHA256: string;
};

// The plugin is plain CommonJS outside src/, loaded the way Expo loads it.
// eslint-disable-next-line @typescript-eslint/no-var-requires
const plugin: Plugin = require(
  path.join(__dirname, "..", "..", "..", "..", "plugins", "with-detection-engine.js")
);

describe("with-detection-engine AC4 guard", () => {
  it("reads the tooling shader and it matches the pinned checksum", () => {
    // Fails loudly if apps/tooling/.../keyframe_engine_bench.frag changed without
    // AC4's procedure (change the TOOLING file, re-gate BOTH dialects via
    // --gate-glsl, re-run the tooling pytest suite, then update FRAG_SHA256).
    expect(() => plugin.readVerbatimFrag()).not.toThrow();
  });

  it("returns the shader body with no #version line (the dialect is prepended)", () => {
    const body = plugin.readVerbatimFrag();
    // E2: ONE body, two dialects, differing ONLY in the #version preamble. A
    // #version line inside the body would make the Android copy a second source
    // of truth.
    expect(body).not.toMatch(/^\s*#version/m);
    expect(body).toContain("precision highp float;");
    expect(body).toContain("precision highp sampler2D;");
  });

  it("carries the ES-3.0 invariants the port depends on", () => {
    const body = plugin.readVerbatimFrag();
    // AC6 — no gl_FragColor (ES 3.00 uses an out variable). Checked against
    // CODE, not the raw text: the shader's own comments say "never
    // gl_FragColor", so a naive substring test matches the documentation rather
    // than a violation.
    const code = body
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/\/\/.*$/gm, "");
    expect(code).not.toContain("gl_FragColor");
    expect(code).toContain("out vec4 fragColor");
    // AC5 — the loop cap must stay in lockstep with WardenRulePacker's.
    expect(body).toContain("const int MAX_RECT_TEXELS = 4096;");
    // AC10 — the integer HSV port must not have been replaced by a float
    // rgb2hsv, whose 1e-10 epsilon flushes to zero at mediump and yields NaN on
    // greys — and our 68 low-saturation rules ARE the greys.
    expect(body).toContain("ivec3 hsv_cv(int b, int g, int r)");
    expect(body).not.toContain("1e-10");
  });

  it("is normalized to LF so the checksum is stable across checkouts", () => {
    // The tooling file is CRLF on Windows and LF on CI. Hashing raw bytes would
    // make the guard fail on line endings rather than on content.
    expect(plugin.readVerbatimFrag()).not.toContain("\r\n");
    expect(plugin.FRAG_SHA256).toMatch(/^[0-9a-f]{64}$/);
  });
});
