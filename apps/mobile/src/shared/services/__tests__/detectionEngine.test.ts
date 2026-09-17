// Story 12.2 (Epic 12) — wrapper-level guarantees of detectionEngine.ts.
// Story 12.4b — the BENCH_MODES lockstep guard RE-POINTED, not deleted.
//
// 🔴 AC9 is explicit that this file's cross-language guard "must be re-pointed,
// not deleted — it is a genuine cross-language contract guard and it is more
// valuable after this story, not less." It is: 12.4b retired two committed native modes
// (`cpugpu`, `pngdump`; the temporary `cpucolor` gate never reached main), and a
// TS union still exporting them would type-check, resolve successfully, and hand back a report
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
const mockAnalyzeSession = jest.fn();
const mockCancelAnalysis = jest.fn();

let mockPlatformOS = "android";
let mockNativePresent = true;

// A minimal DeviceEventEmitter, so the progress-subscription contract can be
// exercised: listeners are captured, `remove()` is observable, and an event can
// be delivered from the "native" side mid-call.
const mockListeners: Array<{
  event: string;
  handler: (payload: unknown) => void;
  removed: boolean;
}> = [];

jest.mock("react-native", () => ({
  get Platform() {
    return { OS: mockPlatformOS, Version: 34 };
  },
  DeviceEventEmitter: {
    addListener: (event: string, handler: (payload: unknown) => void) => {
      const entry = { event, handler, removed: false };
      mockListeners.push(entry);
      return {
        remove: () => {
          entry.removed = true;
        },
      };
    },
  },
  get NativeModules() {
    return mockNativePresent
      ? {
          WardenDetectionEngine: {
            runBench: (...args: unknown[]) => mockRunBench(...args),
            describeDevice: (...args: unknown[]) => mockDescribeDevice(...args),
            analyzeSession: (...args: unknown[]) => mockAnalyzeSession(...args),
            cancelAnalysis: (...args: unknown[]) => mockCancelAnalysis(...args),
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
    mockListeners.length = 0;
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
    // Story 12.4c dropped the 4th positional argument (`cpuFrames`): it sized
    // the retired `cpugpu` comparison, was inert from 12.4b, and the whole
    // chain — Kotlin bench, RN module, bench Activity and this seam — came off
    // in one edit so nothing can call the old shape.
    mockRunBench.mockResolvedValue(JSON.stringify({ story: "12.2", mode: "timing" }));
    await loadModule().runBench("timing", "/sdcard/warden12_2/capture.mp4", 100);
    expect(mockRunBench).toHaveBeenCalledWith(
      "timing",
      "/sdcard/warden12_2/capture.mp4",
      100
    );
  });

  it("keeps the bench bridge arity in lockstep with the Kotlin @ReactMethod", () => {
    // Same cross-language guard as BENCH_MODES, for the argument list this story
    // shortened. A TS seam passing four arguments to a three-parameter
    // @ReactMethod does not fail loudly — the legacy bridge drops the extra.
    const kotlin = fs.readFileSync(
      path.resolve(__dirname, "../../../../plugins/kotlin/WardenDetectionEngineModule.kt"),
      "utf8"
    );
    expect(kotlin).toMatch(
      /fun runBench\(mode: String, video: String\?, limit: Int, promise: Promise\)/
    );
    const ts = fs.readFileSync(path.resolve(__dirname, "../detectionEngine.ts"), "utf8");
    // Comments stripped before the check: both files RECORD the removal in
    // prose, and that record is the point — what must not come back is the
    // argument.
    const strip = (src: string) =>
      src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
    expect(strip(kotlin)).not.toMatch(/cpuFrames/);
    expect(strip(ts)).not.toMatch(/cpuFrames/);
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
    // inequality. Named explicitly because these were LIVE modes whose removal
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
    // `cpucolor` was 12.4b's own AC3(B) gate — an A/B against the GPU arm, run from
    // the working tree and never committed (result banked in bench/12-4b/REPORT.md).
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

// ---------------------------------------------------------------------------
// Story 12.4c — the PRODUCTION seam. Different contract from the bench above,
// deliberately: `analyzeSession` THROWS where the bench entry points resolve
// null. A probe that cannot run is a reportable fact; a session the user asked
// to process that cannot be analysed is an outcome the pipeline must handle, and
// a `null` here would reach the checkpoint logic as "no matches found".
// ---------------------------------------------------------------------------

describe("analyzeSession — the production detection call (Story 12.4c)", () => {
  const ANALYSIS = {
    story: "12.4c",
    n_rules: 3,
    refs: [],
    frames: [{ pts_us: 0, fires: "7" }],
    n_keyframes: 1,
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockListeners.length = 0;
    mockPlatformOS = "android";
    mockNativePresent = true;
    jest.spyOn(console, "warn").mockImplementation(() => {});
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("passes the request id, path, config text and limit in that order", async () => {
    mockAnalyzeSession.mockResolvedValue(JSON.stringify(ANALYSIS));
    const result = await loadModule().analyzeSession({
      requestId: "sess-1",
      videoPath: "/sd/video.mp4",
      configJson: '{"hud_version":"v2"}',
      limit: 0,
    });
    expect(mockAnalyzeSession).toHaveBeenCalledWith(
      "sess-1",
      "/sd/video.mp4",
      '{"hud_version":"v2"}',
      0
    );
    expect(result).toEqual(ANALYSIS);
  });

  it("keeps the analyze bridge signature in lockstep with the Kotlin", () => {
    const kotlin = fs.readFileSync(
      path.resolve(__dirname, "../../../../plugins/kotlin/WardenDetectionEngineModule.kt"),
      "utf8"
    );
    // The argument ORDER is the contract: the legacy bridge marshals
    // positionally, so a reordering type-checks on both sides and mistypes
    // silently at run time.
    expect(kotlin).toMatch(
      /fun analyzeSession\(\s*requestId: String,\s*videoPath: String,\s*configJson: String,\s*limit: Int,\s*promise: Promise,?\s*\)/
    );
    expect(kotlin).toMatch(/fun cancelAnalysis\(requestId: String, promise: Promise\)/);
    // NativeEventEmitter needs these on a legacy module, or every subscribe logs
    // a warning that reads like a broken bridge.
    expect(kotlin).toMatch(/fun addListener\(/);
    expect(kotlin).toMatch(/fun removeListeners\(/);
  });

  it("keeps the progress event name in lockstep with the Kotlin constant", () => {
    const kotlin = fs.readFileSync(
      path.resolve(__dirname, "../../../../plugins/kotlin/WardenDetectionEngineModule.kt"),
      "utf8"
    );
    const constant = /const val EVENT_PROGRESS = "([A-Za-z]+)"/.exec(kotlin);
    expect(constant).not.toBeNull();
    expect(loadModule().ENGINE_PROGRESS_EVENT).toBe(constant![1]);
  });

  it("delivers progress for THIS request and ignores another run's", async () => {
    const seen: number[] = [];
    mockAnalyzeSession.mockImplementation(async () => {
      // The native side emits while the promise is in flight.
      for (const l of mockListeners) {
        l.handler({ requestId: "someone-else", keyframesDone: 999, keyframesTotal: 1000 });
        l.handler({ requestId: "sess-1", keyframesDone: 12, keyframesTotal: 100 });
      }
      return JSON.stringify(ANALYSIS);
    });
    await loadModule().analyzeSession({
      requestId: "sess-1",
      videoPath: "/sd/video.mp4",
      configJson: "{}",
      onProgress: (e) => seen.push(e.keyframesDone),
    });
    // A stale subscription from a previous session must not move this one's bar.
    expect(seen).toEqual([12]);
  });

  it("removes its progress subscription on success AND on failure", async () => {
    mockAnalyzeSession.mockResolvedValue(JSON.stringify(ANALYSIS));
    const mod = loadModule();
    await mod.analyzeSession({
      requestId: "sess-1",
      videoPath: "/v.mp4",
      configJson: "{}",
      onProgress: () => {},
    });
    expect(mockListeners.every((l) => l.removed)).toBe(true);

    mockAnalyzeSession.mockRejectedValue(new Error("decoder wedged"));
    await expect(
      mod.analyzeSession({
        requestId: "sess-2",
        videoPath: "/v.mp4",
        configJson: "{}",
        onProgress: () => {},
      })
    ).rejects.toThrow("decoder wedged");
    // A leaked listener per failed run would accumulate for the life of the JS
    // context and keep calling a dead screen's setState.
    expect(mockListeners.every((l) => l.removed)).toBe(true);
  });

  it("maps the native cancel code onto a typed, non-failure error", async () => {
    const mod = loadModule();
    mockAnalyzeSession.mockRejectedValue(
      Object.assign(new Error("cancelled after 12 of 1061 keyframes"), {
        code: "WARDEN_ANALYSIS_CANCELLED",
      })
    );
    await expect(
      mod.analyzeSession({ requestId: "s", videoPath: "/v.mp4", configJson: "{}" })
    ).rejects.toBeInstanceOf(mod.DetectionAnalysisCancelledError);
  });

  it("maps an unsupported capture geometry onto its own error type", async () => {
    const mod = loadModule();
    mockAnalyzeSession.mockRejectedValue(
      Object.assign(new Error("the capture is 2560x1440"), {
        code: "WARDEN_UNSUPPORTED_GEOMETRY",
      })
    );
    await expect(
      mod.analyzeSession({ requestId: "s", videoPath: "/v.mp4", configJson: "{}" })
    ).rejects.toBeInstanceOf(mod.UnsupportedCaptureError);
  });

  it("rethrows any other native failure unchanged", async () => {
    const mod = loadModule();
    mockAnalyzeSession.mockRejectedValue(
      Object.assign(new Error("no output for 5000 ms"), {
        code: "WARDEN_ANALYSIS_FAILED",
      })
    );
    await expect(
      mod.analyzeSession({ requestId: "s", videoPath: "/v.mp4", configJson: "{}" })
    ).rejects.toThrow("no output for 5000 ms");
  });

  it("throws rather than resolving null when the bridge is absent", async () => {
    mockNativePresent = false;
    const mod = loadModule();
    await expect(
      mod.analyzeSession({ requestId: "s", videoPath: "/v.mp4", configJson: "{}" })
    ).rejects.toBeInstanceOf(mod.DetectionEngineUnavailableError);
    expect(mockAnalyzeSession).not.toHaveBeenCalled();
  });

  it("throws off android without touching the bridge (amendment 5c)", async () => {
    mockPlatformOS = "ios";
    const mod = loadModule();
    await expect(
      mod.analyzeSession({ requestId: "s", videoPath: "/v.mp4", configJson: "{}" })
    ).rejects.toBeInstanceOf(mod.DetectionEngineUnavailableError);
    expect(mockAnalyzeSession).not.toHaveBeenCalled();
  });

  it("never throws from cancelAnalysis — it is reached from unmount paths", async () => {
    mockCancelAnalysis.mockResolvedValue(true);
    await expect(loadModule().cancelAnalysis("sess-1")).resolves.toBe(true);

    mockCancelAnalysis.mockRejectedValue(new Error("bridge gone"));
    await expect(loadModule().cancelAnalysis("sess-1")).resolves.toBe(false);

    mockNativePresent = false;
    await expect(loadModule().cancelAnalysis("sess-1")).resolves.toBe(false);
  });
});
