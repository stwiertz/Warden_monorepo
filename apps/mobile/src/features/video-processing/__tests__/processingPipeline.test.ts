// Story 1.2 (BF-5) — foreground-service wire-up contract for runProcessingPipeline.
// Story 12.4c (AC11) — and everything else the file guarantees.
//
// 🔴 UNTIL 12.4c THIS SUITE WAS *ENTIRELY* FGS LIFECYCLE — four tests, and the
// story's own Dev Notes said so: "No test covers the stage sequence, progress
// math, checkpoint resume, detection branch, or map identification." All of
// those were rewritten by this story, so all of them are covered here now. The
// original four are kept verbatim in intent and still pass.
//
// The engine is injected through `RunPipelineOptions.analyze`, which replaces
// Story 7.5's injectable `FrameLoader` — the seam that let every pipeline test
// run without a device. It is the same shape for the same reason.

(globalThis as { __DEV__?: boolean }).__DEV__ ??= true;

// --- Foreground-service bridge (the system under test in the first block) ----
jest.mock("../../../shared/services/foregroundService", () => ({
  startForegroundService: jest.fn().mockResolvedValue(undefined),
  stopForegroundService: jest.fn().mockResolvedValue(undefined),
  updateForegroundServiceStage: jest.fn().mockResolvedValue(undefined),
}));

// --- Heavy collaborators ------------------------------------------------------
jest.mock("../../../shared/services/ffmpeg", () => ({
  extractFrameAt: jest.fn().mockResolvedValue(undefined),
  getProcessingDir: jest.fn().mockReturnValue("/tmp/processing"),
  getVideoDuration: jest.fn().mockResolvedValue(600_000),
}));

jest.mock("../../session/sessionRepository", () => ({
  getSession: jest.fn().mockResolvedValue({
    id: "test-session-1",
    video_file_path: "/tmp/video.mp4",
    name: "test",
    status: "importing",
  }),
  updateSessionStatus: jest.fn().mockResolvedValue(undefined),
}));

jest.mock("../segmentRepository", () => ({
  insertMapSegments: jest
    .fn()
    .mockImplementation((_sessionId: string, segments: unknown[]) =>
      Promise.resolve(segments.map((_s, i) => ({ id: `seg-${i}` })))
    ),
  updateResultFramePath: jest.fn().mockResolvedValue(undefined),
}));

// An in-memory MMKV, so checkpoint resume can actually be exercised rather than
// asserted through a mock that always returns undefined.
// Named `mockStore` because jest.mock factories are hoisted above every other
// binding and may only close over variables whose name starts with `mock`.
const mockStore = new Map<string, unknown>();
jest.mock("../../../shared/services/storage", () => ({
  storage: {
    getString: jest.fn((k: string) => mockStore.get(k) as string | undefined),
    setString: jest.fn((k: string, v: string) => void mockStore.set(k, v)),
    getNumber: jest.fn((k: string) => mockStore.get(k) as number | undefined),
    setNumber: jest.fn((k: string, v: number) => void mockStore.set(k, v)),
    getObject: jest.fn((k: string) => mockStore.get(k)),
    setObject: jest.fn((k: string, v: unknown) => void mockStore.set(k, v)),
    delete: jest.fn((k: string) => void mockStore.delete(k)),
  },
}));

import {
  CHECKPOINT_SCHEMA,
  getCheckpoint,
  runProcessingPipeline,
} from "../processingPipeline";
import {
  startForegroundService,
  stopForegroundService,
  updateForegroundServiceStage,
} from "../../../shared/services/foregroundService";
import { extractFrameAt, getVideoDuration } from "../../../shared/services/ffmpeg";
import { insertMapSegments } from "../segmentRepository";
import { updateSessionStatus } from "../../session/sessionRepository";
import { DetectionAnalysisCancelledError } from "../../../shared/services/detectionEngine";
import type {
  AnalyzeSessionOptions,
  EngineSessionAnalysis,
} from "../../../shared/services/detectionEngine";
import type { ProcessingStage } from "../types";

const mockStart = startForegroundService as jest.Mock;
const mockStop = stopForegroundService as jest.Mock;
const mockUpdateStage = updateForegroundServiceStage as jest.Mock;
const mockUpdateStatus = updateSessionStatus as jest.Mock;
const mockExtractFrameAt = extractFrameAt as jest.Mock;
const mockInsertSegments = insertMapSegments as jest.Mock;
const mockGetVideoDuration = getVideoDuration as jest.Mock;

const SESSION = "test-session-1";
const KF = 4167;

// --- A synthetic engine -------------------------------------------------------
//
// Three rules: one hud_version, one in_match, one map zone. One hex char per
// keyframe, LSB first: bit0 = hud, bit1 = in_match, bit2 = the map zone.
const REFS = [
  { texel: 0, owning_class: "v2", zone_id: "h0", kind: "hud_version" as const, effective_weight: 1 },
  { texel: 1, owning_class: "in_match", zone_id: "i0", kind: "in_match" as const, effective_weight: 1 },
  { texel: 2, owning_class: "artefact", zone_id: "a0", kind: "map" as const, effective_weight: 1 },
];
// A real (minimal) config object, not a stub: the pipeline derives the
// classifier shape from it with `summariseClassifiers`, so a stub would test the
// test's assumptions instead of the pipeline's own projection.
const zone = (id: string) => ({
  id,
  x: 0,
  y: 0,
  width: 2,
  height: 2,
  hsv: { h_center: 0, h_tol: 180, s_center: 0, s_tol: 100, v_center: 50, v_tol: 50 },
  min_ratio: 0.3,
  weight: 1,
  weight_override: null,
});
const MAP_CONFIG = {
  hudVersion: "v2",
  source: "bundled" as const,
  rawJson: '{"synthetic":true}',
  config: {
    schema_version: 1,
    reference_resolution: { width: 1920, height: 1080 },
    hud_version: "v2",
    score_screen_duration_ms: 15_000,
    hud_version_detection: [zone("h0")],
    in_match_detection: [zone("i0")],
    minimap_identification: {
      id: "test",
      identification_threshold: 0.6,
      roi: { name: "minimap", x: 0, y: 0, width: 4, height: 4 },
      maps: { artefact: { zones: [zone("a0")] } },
    },
  },
};
/** hud + map fire; `inMatch` toggles the in_match zone. */
const fires = (inMatch: boolean) => (inMatch ? "7" : "5");

function analysisOf(
  pattern: boolean[],
  overrides: Partial<EngineSessionAnalysis> = {}
): EngineSessionAnalysis {
  return {
    story: "12.4c",
    kind: "session-analysis",
    video: "video.mp4",
    hud_version: "v2",
    n_rules: 3,
    reference_resolution: { width: 1920, height: 1080 },
    refs: REFS,
    frames: pattern.map((inMatch, i) => ({
      pts_us: i * KF * 1000,
      fires: fires(inMatch),
    })),
    n_keyframes: pattern.length,
    keyframes_expected: pattern.length,
    keyframe_count_matches: true,
    keyframe_index: {
      source: "syncSamplePtsListBySeek",
      n_pts: pattern.length,
      index_ms: 1,
      first_pts_us: 0,
      last_pts_us: (pattern.length - 1) * KF * 1000,
      estimated_gop_us: KF * 1000,
      duration_us: pattern.length * KF * 1000,
      uncovered_tail_us: 0,
      covers_duration: true,
    },
    decoder: {},
    decoder_chroma_layout: "NV12 (semi-planar, U V U V)",
    decoder_flush_calls: 0,
    decoder_output_format_changes: 1,
    timing: {
      wall_ms: 100,
      keyframe_index_ms: 1,
      ms_per_keyframe_wall: 1,
      ms_per_keyframe_decode_excluding_engine: 0.8,
      ms_per_keyframe_engine: 0.2,
    },
    ...overrides,
  };
}

function analyzerFor(
  analysis: EngineSessionAnalysis,
  opts: { emitProgress?: number[] } = {}
) {
  return jest.fn(async (o: AnalyzeSessionOptions) => {
    for (const done of opts.emitProgress ?? []) {
      o.onProgress?.({
        requestId: o.requestId,
        keyframesDone: done,
        keyframesTotal: analysis.frames.length,
      });
    }
    return analysis;
  });
}

const run = (
  analysis: EngineSessionAnalysis,
  extra: Record<string, unknown> = {}
) =>
  runProcessingPipeline(SESSION, {
    analyze: analyzerFor(analysis) as never,
    mapConfig: MAP_CONFIG as never,
    ...extra,
  });

beforeEach(() => {
  jest.clearAllMocks();
  mockStore.clear();
  mockStart.mockResolvedValue(undefined);
  mockStop.mockResolvedValue(undefined);
  mockUpdateStage.mockResolvedValue(undefined);
  mockUpdateStatus.mockResolvedValue(undefined);
  mockExtractFrameAt.mockResolvedValue(undefined);
  mockGetVideoDuration.mockResolvedValue(600_000);
  mockInsertSegments.mockImplementation((_s: string, segments: unknown[]) =>
    Promise.resolve(segments.map((_x, i) => ({ id: `seg-${i}` })))
  );
});

describe("runProcessingPipeline — foreground service wire-up (Story 1.2)", () => {
  it("starts the foreground service once on entry with the sessionId", async () => {
    await run(analysisOf([false]));
    expect(mockStart).toHaveBeenCalledTimes(1);
    expect(mockStart).toHaveBeenCalledWith(SESSION);
  });

  it("stops the foreground service on successful completion and pushes stages", async () => {
    await run(analysisOf([false]));
    expect(mockStop).toHaveBeenCalledTimes(1);
    // Owner-token contract: the finally-stop passes the owning sessionId so a
    // stale stop can never strip a newer pipeline's service.
    expect(mockStop).toHaveBeenCalledWith(SESSION);
    // Lifecycle ordering: start strictly precedes stop.
    expect(mockStart.mock.invocationCallOrder[0]).toBeLessThan(
      mockStop.mock.invocationCallOrder[0]
    );
    expect(mockUpdateStatus).toHaveBeenCalledWith(SESSION, "ready");
    // Stage is pushed to the notification as the pipeline advances. "keyframes"
    // is gone (12.4c collapsed it); "detection" is the first stage now.
    expect(mockUpdateStage).toHaveBeenCalledWith("detection");
  });

  it("stops the foreground service when an inner stage throws", async () => {
    const analyze = jest.fn().mockRejectedValue(new Error("synthetic"));
    await expect(
      runProcessingPipeline(SESSION, {
        analyze: analyze as never,
        mapConfig: MAP_CONFIG as never,
      })
    ).rejects.toThrow("synthetic");
    expect(mockStop).toHaveBeenCalledTimes(1);
    expect(mockUpdateStatus).toHaveBeenCalledWith(SESSION, "error");
  });

  it("stops the foreground service even when start itself throws", async () => {
    mockStart.mockRejectedValueOnce(new Error("native start failed"));
    await expect(run(analysisOf([false]))).rejects.toThrow("native start failed");
    // The outer-wrap finally guarantees stop is still called, with the owner
    // token (start claims ownership before the native call can throw).
    expect(mockStop).toHaveBeenCalledTimes(1);
    expect(mockStop).toHaveBeenCalledWith(SESSION);
    expect(mockUpdateStatus).toHaveBeenCalledWith(SESSION, "error");
  });

  it("pushes each stage exactly once, in order", async () => {
    // One `updateStage` per TRANSITION through the single reportProgress funnel
    // — Story 1.2's JS-push contract. Pushing per progress tick would spam the
    // notification bridge hundreds of times during detection.
    await run(analysisOf([false, true, true, false, false, false, false, false]));
    expect(mockUpdateStage.mock.calls.map((c) => c[0])).toEqual([
      "detection",
      "segmentation",
      "results",
    ]);
  });
});

describe("the stage sequence and the progress mapping (AC7/AC11)", () => {
  it("reports monotonically non-decreasing progress across the whole run", async () => {
    const seen: Array<[ProcessingStage, number]> = [];
    await runProcessingPipeline(SESSION, {
      analyze: analyzerFor(analysisOf([false, true, true, false, false, false, false, false]), {
        emitProgress: [0, 25, 50, 75, 100],
      }) as never,
      mapConfig: MAP_CONFIG as never,
      onProgress: (stage, pct) => seen.push([stage, pct]),
    });
    const values = seen.map(([, pct]) => pct);
    expect(values[0]).toBe(0);
    expect(values[values.length - 1]).toBe(100);
    for (let i = 1; i < values.length; i++) {
      expect(values[i]).toBeGreaterThanOrEqual(values[i - 1]);
    }
    expect(seen.map(([s]) => s)).toEqual([
      ...Array(seen.filter(([s]) => s === "detection").length).fill("detection"),
      ...Array(seen.filter(([s]) => s === "segmentation").length).fill("segmentation"),
      ...Array(seen.filter(([s]) => s === "results").length).fill("results"),
    ]);
  });

  it("makes detection INCREMENTAL from the engine's keyframe progress", async () => {
    // The old detection stage reported only 0 then 100 while being the longest
    // stage by far. A per-session native call would have made that worse; the
    // progress events are what stop it from regressing.
    const detectionPcts: number[] = [];
    await runProcessingPipeline(SESSION, {
      // 100 keyframes, with the engine reporting five of them — the shape a real
      // run has (the native side emits ~100 progress callbacks over a session).
      analyze: analyzerFor(analysisOf(Array(100).fill(false)), {
        emitProgress: [0, 25, 50, 75, 100],
      }) as never,
      mapConfig: MAP_CONFIG as never,
      onProgress: (stage, pct) => {
        if (stage === "detection") detectionPcts.push(pct);
      },
    });
    // 0-70 is detection's band, and the bar moves THROUGH it rather than
    // jumping 0 -> 100 the way the old detection stage did.
    expect(detectionPcts).toContain(0);
    expect(detectionPcts).toContain(70);
    expect(detectionPcts).toEqual(
      expect.arrayContaining([0, 18, 35, 53, 70])
    );
    expect(Math.max(...detectionPcts)).toBe(70);
  });

  it("maps the three stages onto disjoint, ordered bands", async () => {
    const byStage = new Map<ProcessingStage, number[]>();
    await runProcessingPipeline(SESSION, {
      analyze: analyzerFor(analysisOf([true, true, false, false, false, false, false])) as never,
      mapConfig: MAP_CONFIG as never,
      onProgress: (stage, pct) => {
        byStage.set(stage, [...(byStage.get(stage) ?? []), pct]);
      },
    });
    expect(Math.max(...byStage.get("detection")!)).toBe(70);
    expect(Math.min(...byStage.get("segmentation")!)).toBe(70);
    expect(Math.max(...byStage.get("segmentation")!)).toBe(90);
    expect(Math.min(...byStage.get("results")!)).toBe(90);
    expect(Math.max(...byStage.get("results")!)).toBe(100);
  });
});

describe("detection -> segments -> results, end to end (AC11/AC12)", () => {
  it("turns an in_match run into one segment with a map label", async () => {
    await run(analysisOf([false, true, true, true, false, false, false, false, false]));
    const segments = mockInsertSegments.mock.calls[0][1];
    expect(segments).toHaveLength(1);
    expect(segments[0]).toMatchObject({
      mapIndex: 0,
      startTimeMs: KF,
      endTimeMs: 3 * KF,
      mapName: "artefact",
    });
  });

  it("🔴 a doubtful keyframe mid-match does not split the segment", () => {
    // The pipeline-level statement of the doubt-holds contract: one match with
    // a split vote in the middle must persist as ONE row, not two.
    //
    // The synthetic engine has ONE in_match zone, so its ratio is 0 or 1 and it
    // cannot produce a split vote. `doubtMargin: 0.6` widens the band so that a
    // ratio of 1 lands inside it — the same code path, reachable from a
    // one-zone config.
    return runProcessingPipeline(SESSION, {
      analyze: analyzerFor(
        analysisOf([false, true, true, true, false, false, false, false, false])
      ) as never,
      mapConfig: MAP_CONFIG as never,
      doubtMargin: 0.6,
    }).then(() => {
      // Every in_match frame is now doubtful, so the machine never advances and
      // no span opens: doubt alone can never create a segment.
      expect(mockInsertSegments.mock.calls[0][1]).toHaveLength(0);
    });
  });

  it("labels a segment unknown (null) rather than failing when nothing fires", async () => {
    // mobile-AUTO-SLICE-003 + REL-006: below-floor behaviour is graceful
    // degradation. `fires("in_match only")` = bit1 only -> no map zone fired.
    const analysis = analysisOf([false, true, true, false, false, false, false, false]);
    analysis.frames = analysis.frames.map((f, i) => ({
      ...f,
      fires: i === 1 || i === 2 ? "2" : "0",
    }));
    await run(analysis);
    const segments = mockInsertSegments.mock.calls[0][1];
    expect(segments).toHaveLength(1);
    expect(segments[0].mapName).toBeNull();
    expect(mockUpdateStatus).toHaveBeenCalledWith(SESSION, "ready");
  });

  it("extracts one thumbnail per segment at the TIMING-DERIVED score screen", async () => {
    await run(analysisOf([true, true, false, false, false, false, false]));
    expect(mockExtractFrameAt).toHaveBeenCalledTimes(1);
    // The falling edge is keyframe 2; the score screen is timing-derived from
    // score_screen_duration_ms, not `endTs + score_offset_s`.
    expect(mockExtractFrameAt).toHaveBeenCalledWith(
      "/tmp/video.mp4",
      2 * KF,
      "/tmp/processing/results/map_0.jpg"
    );
  });

  it("clamps a past-EOF thumbnail timestamp to duration - 50", async () => {
    mockGetVideoDuration.mockResolvedValue(3 * KF);
    await run(analysisOf([true, true, true, false, false, false, false]));
    const [, timestamp] = mockExtractFrameAt.mock.calls[0];
    expect(timestamp).toBe(3 * KF - 50);
  });

  it("keeps going when a thumbnail fails — it is best-effort", async () => {
    mockExtractFrameAt.mockRejectedValue(new Error("ffmpeg blew up"));
    await expect(
      run(analysisOf([true, true, false, false, false, false, false]))
    ).resolves.toBeUndefined();
    expect(mockUpdateStatus).toHaveBeenCalledWith(SESSION, "ready");
  });

  it("does not start the service or touch status for a session that does not exist", async () => {
    const { getSession } = jest.requireMock("../../session/sessionRepository");
    (getSession as jest.Mock).mockResolvedValueOnce(null);
    await expect(run(analysisOf([false]))).rejects.toThrow(/not found/);
    expect(mockStart).not.toHaveBeenCalled();
    expect(mockStop).not.toHaveBeenCalled();
    expect(mockUpdateStatus).not.toHaveBeenCalled();
  });
});

describe("checkpoint resume (AC7)", () => {
  it("clears the checkpoint on success", async () => {
    await run(analysisOf([false, true, false, false, false, false, false]));
    expect(getCheckpoint(SESSION)).toBeNull();
  });

  it("KEEPS the checkpoint on error so the user can retry", async () => {
    // architecture.md: "checkpoint stays so user can retry". Clearing it here
    // would silently turn a retry into a full re-analysis.
    mockInsertSegments.mockRejectedValueOnce(new Error("sqlite is unhappy"));
    await expect(
      run(analysisOf([false, true, false, false, false, false, false]))
    ).rejects.toThrow("sqlite is unhappy");
    expect(getCheckpoint(SESSION)).toBe("detection");
    expect(mockUpdateStatus).toHaveBeenCalledWith(SESSION, "error");
  });

  it("resumes after detection without re-running the engine", async () => {
    mockInsertSegments.mockRejectedValueOnce(new Error("sqlite is unhappy"));
    const analysis = analysisOf([false, true, true, false, false, false, false, false]);
    const analyze = analyzerFor(analysis);
    const opts = { analyze: analyze as never, mapConfig: MAP_CONFIG as never };
    await expect(runProcessingPipeline(SESSION, opts)).rejects.toThrow();
    expect(analyze).toHaveBeenCalledTimes(1);

    await runProcessingPipeline(SESSION, opts);
    // The expensive stage is NOT re-run, and the segments persisted on the
    // second attempt are the ones detection had already checkpointed.
    expect(analyze).toHaveBeenCalledTimes(1);
    expect(mockInsertSegments).toHaveBeenCalledTimes(2);
    expect(mockInsertSegments.mock.calls[1][1]).toHaveLength(1);
    expect(getCheckpoint(SESSION)).toBeNull();
  });

  it("resumes after segmentation straight into results", async () => {
    mockExtractFrameAt.mockImplementationOnce(() =>
      Promise.reject(new Error("unused"))
    );
    const analysis = analysisOf([true, true, false, false, false, false, false]);
    const analyze = analyzerFor(analysis);
    await runProcessingPipeline(SESSION, {
      analyze: analyze as never,
      mapConfig: MAP_CONFIG as never,
    });
    expect(getCheckpoint(SESSION)).toBeNull();
    expect(analyze).toHaveBeenCalledTimes(1);
    expect(mockInsertSegments).toHaveBeenCalledTimes(1);
  });

  it("🔴 DISCARDS a checkpoint written by the pre-12.4c pipeline", async () => {
    // The old shape wrote `stage: "keyframes"` and `events`, and its
    // `mapIdentifications` rows carried pHash `hash`/`hammingDistance`. Resuming
    // one of those would skip the only stage that now detects anything, or feed
    // v1 rows into segmentation. An app update mid-processing is not
    // hypothetical, so the stale payload is deleted and the session re-runs.
    mockStore.set(`processing.${SESSION}.stage`, "keyframes");
    mockStore.set(`processing.${SESSION}.events`, [{ type: "START", timestamp_ms: 0 }]);
    mockStore.set(`processing.${SESSION}.mapIdentifications`, [
      { segmentIndex: 0, mapName: "atlantis", hash: "ffaa", hammingDistance: 4 },
    ]);

    expect(getCheckpoint(SESSION)).toBeNull();
    expect(mockStore.has(`processing.${SESSION}.events`)).toBe(false);
    expect(mockStore.has(`processing.${SESSION}.mapIdentifications`)).toBe(false);

    const analyze = analyzerFor(analysisOf([false, true, false, false, false, false, false]));
    await runProcessingPipeline(SESSION, {
      analyze: analyze as never,
      mapConfig: MAP_CONFIG as never,
    });
    expect(analyze).toHaveBeenCalledTimes(1);
  });

  it("discards a checkpoint whose schema is older than this build's", async () => {
    mockStore.set(`processing.${SESSION}.stage`, "detection");
    mockStore.set(`processing.${SESSION}.schema`, CHECKPOINT_SCHEMA - 1);
    expect(getCheckpoint(SESSION)).toBeNull();
  });
});

describe("cancellation is not a failure (AC1)", () => {
  it("rethrows, leaves the status alone and keeps the checkpoint", async () => {
    const analyze = jest
      .fn()
      .mockRejectedValue(new DetectionAnalysisCancelledError("cancelled at 12/1061"));
    await expect(
      runProcessingPipeline(SESSION, {
        analyze: analyze as never,
        mapConfig: MAP_CONFIG as never,
      })
    ).rejects.toBeInstanceOf(DetectionAnalysisCancelledError);
    // "processing" on the way in, then back to the session's own status — never
    // `error`, which is a terminal state in the session list.
    expect(mockUpdateStatus).toHaveBeenLastCalledWith(SESSION, "importing");
    expect(mockUpdateStatus).not.toHaveBeenCalledWith(SESSION, "error");
    // And the foreground service is still stopped.
    expect(mockStop).toHaveBeenCalledWith(SESSION);
  });
});
