// Story 12.2 (Epic 12) — wrapper-level guarantees of detectionEngine.ts.
// Story 12.4b — the BENCH_MODES lockstep guard RE-POINTED, not deleted.
//
// 🔴 AC9 is explicit that this file's cross-language guard "must be re-pointed,
// not deleted — it is a genuine cross-language contract guard and it is more
// valuable after this story, not less." It is: 12.4b retired THREE native modes
// (`cpugpu`, `pngdump` and the temporary `cpucolor` gate), and a TS union still
// exporting them would type-check, resolve successfully, and hand back a report
// with no measurements and no `error` field — the exact defect the 2026-09-15
// review found with `"profile"`. The guard is what turns "we remembered to update
// both sides" into something CI checks.
//
// Its sibling `detectionEnginePlugin.test.ts` was DELETED in the same story, and
// the difference is worth stating: that one tested the plugin's `readVerbatimFrag`
// — the shader-asset copy mechanism 12.4b removes — so it had no subject left. The
// ES-3.0 invariants it also asserted are still gated, by the tooling pytest suite
// over `read_frag_body()` (apps/tooling/tests/test_keyframe_engine_bench.py), which
// is where a GLSL guard belongs now that no Kotlin reads that file. Tool 12's
// `.frag` itself is untouched and must stay so (AC6).
//
// Device-free by construction, following the foregroundService.test.ts
// precedent: `jest.mock("react-native")` + a stubbed NativeModules entry. There
// is NO androidTest/instrumentation harness in this repo (android/app/src has
// only main/, debug/, debugOptimized/, and app/build.gradle declares no
// testInstrumentationRunner), and Story 12.1's AC16 explicitly forbade a GL
// context in its test suite. 12.2 keeps that line: the GL/MediaCodec surface is
// verified by the on-device bench and its REPORT.md, exactly as 12.1 did, and
// what is unit-tested here is the SEAM. (Pre-12.4b that GL surface was a GPU
// mega-shader; it is now MediaCodec plus plain Kotlin, and the reasoning is
// unchanged — jest still cannot run Kotlin.)
//
// Guarantees asserted:
//   1. Android-only: every call no-ops off Android (amendment 5c — MediaCodec +
//      GLES is Android-only by construction).
//   2. Native-module-missing swallow: jest never sees the bridge.
//   3. Neither entry point ever rejects — a probe that cannot run is a
//      reportable fact, not an error condition.
//   4. Arguments reach the bridge in the documented order.
//   5. The seam is TRANSPARENT: it narrows, renames and drops nothing.
//   6. Cross-language contracts that jest CAN hold: the BenchMode union matches
//      the native BENCH_MODES set, and AC0b's count assertion is not vacuous.
//      (Added 2026-09-15 after review found two tests here that mocked a value
//      and then asserted the mocked value — tautologies labelled as AC coverage.)

import fs from "fs";
import path from "path";

(globalThis as { __DEV__?: boolean }).__DEV__ ??= true;

const mockRunBench = jest.fn();
const mockDescribeDevice = jest.fn();

let mockPlatformOS = "android";
let mockNativePresent = true;

jest.mock("react-native", () => ({
  get Platform() {
    return { OS: mockPlatformOS, Version: 34 };
  },
  get NativeModules() {
    return mockNativePresent
      ? {
          WardenDetectionEngine: {
            runBench: (...args: unknown[]) => mockRunBench(...args),
            describeDevice: (...args: unknown[]) => mockDescribeDevice(...args),
          },
        }
      : {};
  },
}));

type DetectionEngineModule = typeof import("../detectionEngine");

function loadModule(): DetectionEngineModule {
  jest.resetModules();
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  return require("../detectionEngine");
}

describe("detectionEngine wrapper (Story 12.2)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockPlatformOS = "android";
    mockNativePresent = true;
    jest.spyOn(console, "warn").mockImplementation(() => {});
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("reports the bridge as available on android when the module is linked", () => {
    expect(loadModule().isEngineAvailable()).toBe(true);
  });

  it("returns the device profile verbatim, dropping no field the native side sent", async () => {
    // NOTE (review 2026-09-15): this used to assert that specific mocked
    // literals came back — i.e. that `JSON.parse(JSON.stringify(x))` equals `x`,
    // which is true of any implementation and was labelled as AC2 coverage it
    // did not provide. What the seam is actually responsible for is being
    // TRANSPARENT: it must not narrow, rename, or drop fields on the way
    // through, because the ACs are closed by fields it has never heard of.
    const native = {
      android_release: "14",
      android_sdk_int: 34,
      model: "22101320G",
      engine: {
        kind: "CPU integer rule evaluation on MediaCodec keyframe decode",
        color_conversion: "WardenColorConvert — bt709 limited range, nearest chroma",
        gpu_used: false,
      },
      a_field_the_seam_has_never_heard_of: { nested: [1, 2, 3] },
    };
    mockDescribeDevice.mockResolvedValue(JSON.stringify(native));
    const profile = await loadModule().describeDevice();
    expect(profile).toEqual(native);
  });

  it("passes bench arguments through in the documented order", async () => {
    mockRunBench.mockResolvedValue(JSON.stringify({ story: "12.2", mode: "timing" }));
    await loadModule().runBench("timing", "/sdcard/warden12_2/capture.mp4", 100, 400);
    expect(mockRunBench).toHaveBeenCalledWith(
      "timing",
      "/sdcard/warden12_2/capture.mp4",
      100,
      400
    );
  });

  // These two replace a test that mocked `keyframe_count_matches: true` and then
  // asserted it was true (review 2026-09-15). That would have passed unchanged
  // even though the native expression was `limit > 0 || nFrames == syncCount`,
  // i.e. unconditionally true on every limited run. Jest cannot run Kotlin, but
  // it CAN hold the two sides of a cross-language contract together — which is
  // where both defects the review found actually lived.

  it("keeps BenchMode in lockstep with the native BENCH_MODES set", () => {
    const kotlin = fs.readFileSync(
      path.resolve(__dirname, "../../../../plugins/kotlin/WardenEngineBench.kt"),
      "utf8"
    );
    const block = /val BENCH_MODES = setOf\(([\s\S]*?)\)/.exec(kotlin);
    expect(block).not.toBeNull();
    const nativeModes = [...block![1].matchAll(/"([a-z]+)"/g)].map((m) => m[1]).sort();

    const ts = fs.readFileSync(
      path.resolve(__dirname, "../detectionEngine.ts"),
      "utf8"
    );
    const union = /export type BenchMode =([\s\S]*?);/.exec(ts);
    expect(union).not.toBeNull();
    const tsModes = [...union![1].matchAll(/"([a-z]+)"/g)].map((m) => m[1]).sort();

    // A mode present in TS but not in Kotlin resolves to a successful-looking
    // report with no measurements and no error; a mode present in Kotlin but not
    // in TS is unreachable through the only sanctioned seam (AC18b).
    expect(tsModes).toEqual(nativeModes);
  });

  it("exports no mode the native bench has stopped dispatching on", () => {
    // The lockstep test above would catch these too, but only as an opaque array
    // inequality. Named explicitly because all three were LIVE modes whose removal
    // is the story's substance, and because a TS-only mode is the silent failure:
    // it type-checks and returns a successful-looking report with no measurements.
    const ts = fs.readFileSync(
      path.resolve(__dirname, "../detectionEngine.ts"),
      "utf8"
    );
    const union = /export type BenchMode =([\s\S]*?);/.exec(ts);
    expect(union).not.toBeNull();
    const tsModes = [...union![1].matchAll(/"([a-z]+)"/g)].map((m) => m[1]);
    // `cpugpu` lost its GPU arm; `pngdump` dumped the resolved GPU frame texture;
    // `cpucolor` was 12.4b's own AC3(B) gate — an A/B against the GPU arm, so it
    // could not outlive it (result banked in bench/12-4b/REPORT.md).
    expect(tsModes).not.toContain("cpugpu");
    expect(tsModes).not.toContain("pngdump");
    expect(tsModes).not.toContain("cpucolor");
    expect(tsModes).not.toContain("profile");
  });

  it("keeps the native side free of the deleted GLES/EGL surface", () => {
    // AC5/AC18b. The bench is the only Kotlin the TS seam can reach, and it is the
    // file that held every GL call site. A re-introduced import here would mean the
    // GPU arm came back without anyone re-opening Decision #13 — which rejected it
    // on a MEASUREMENT (GPU 6.4x slower for bit-identical output), not a preference.
    const kotlin = fs.readFileSync(
      path.resolve(__dirname, "../../../../plugins/kotlin/WardenEngineBench.kt"),
      "utf8"
    );
    const code = kotlin
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/\/\/.*$/gm, "");
    expect(code).not.toMatch(/import android\.opengl/);
    expect(code).not.toMatch(/GLES30|EGL14|WardenEglContext|WardenGlUtil/);
    expect(code).not.toMatch(/WardenDetectionEngine\s*\(/);
  });

  it("holds the native keyframe-count assertion to a non-vacuous form", () => {
    const kotlin = fs.readFileSync(
      path.resolve(__dirname, "../../../../plugins/kotlin/WardenEngineBench.kt"),
      "utf8"
    );
    // AC0b's assertion is binding or it is decoration. The shipped artifacts
    // showed `60 decoded / 1061 reported / matches: true` because the expression
    // short-circuited on `limit > 0`.
    expect(kotlin).not.toMatch(/keyframe_count_matches",\s*limit > 0 \|\|/);
    // A limited run must assert against its OWN target and say which it used.
    expect(kotlin).toContain("keyframe_count_expected");
    expect(kotlin).toContain("keyframe_count_assertion");
  });

  it("no-ops off android rather than calling the bridge (amendment 5c)", async () => {
    mockPlatformOS = "ios";
    const mod = loadModule();
    expect(mod.isEngineAvailable()).toBe(false);
    await expect(mod.runBench("all")).resolves.toBeNull();
    await expect(mod.describeDevice()).resolves.toBeNull();
    expect(mockRunBench).not.toHaveBeenCalled();
    expect(mockDescribeDevice).not.toHaveBeenCalled();
  });

  it("swallows a missing native module so jest never sees the bridge", async () => {
    mockNativePresent = false;
    const mod = loadModule();
    expect(mod.isEngineAvailable()).toBe(false);
    await expect(mod.runBench("all")).resolves.toBeNull();
    await expect(mod.describeDevice()).resolves.toBeNull();
  });

  it("never rejects when the native call fails", async () => {
    mockRunBench.mockRejectedValue(new Error("EGL context creation failed"));
    mockDescribeDevice.mockRejectedValue(new Error("no GL"));
    const mod = loadModule();
    await expect(mod.runBench("all")).resolves.toBeNull();
    await expect(mod.describeDevice()).resolves.toBeNull();
  });

  it("never rejects when the bridge returns malformed JSON", async () => {
    mockRunBench.mockResolvedValue("{not json");
    await expect(loadModule().runBench("all")).resolves.toBeNull();
  });
});
