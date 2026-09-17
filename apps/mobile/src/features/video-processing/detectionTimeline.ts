// Story 12.4c — fire bits -> a session's detection timeline. PURE.
//
// The composition layer: it takes the ONE native call's output
// (`analyzeSession`, one fire-bit row per keyframe plus the rule index) and runs
// the three classifiers and the phase machine over it, producing everything the
// orchestrator persists. No native calls, no MMKV, no SQLite — so the whole
// detection semantic is testable under jest against Tool 12's fixture, which is
// AC0b's reason for putting it here.
//
// The order of operations mirrors Tool 12's `_run_video` exactly, because the
// fixture's expectations come from it:
//   1. per frame: `scoreFromFires` -> the three verdicts
//   2. per frame: `inMatchCall(in_match_conf)` -> yes | no | doubt
//   3. streaming: `PhaseResolver.push` -> emitted state; internal state recorded
//   4. post-hoc: `spansFromStates(internal)` -> maximal in_match runs
//   5. per span: sum the per-frame map aggregates -> one map label per match

import {
  buildGameSegments,
  createPhaseResolver,
  DEFAULT_DOUBT_MARGIN,
  inMatchCall,
  spansFromStates,
  STATE_DOUBT,
  type GameSegmentTimeline,
  type InMatchCall,
  type InternalPhaseState,
  type PhaseSpan,
  type PhaseState,
} from "./gameDetector";
import { scoreFromFires, type RuleRef } from "./engineScoring";
import {
  aggregateSpanScores,
  identifySpanMap,
  type MapIdentification,
} from "./mapIdentifier";
import {
  assertRefsMatchConfig,
  resolveSessionHudVersion,
  type ClassifierConfig,
  type HudVersionVerdict,
  type MapConfigCandidate,
} from "./mapConfig";
import type { EngineSessionAnalysis } from "../../shared/services/detectionEngine";
import type { MapIdentificationResult } from "./types";

export interface TimelineFrame {
  frameIdx: number;
  ptsUs: number;
  timestampMs: number;
  /** May be `doubt`. This is the timeline. */
  emitted: PhaseState;
  /** Never `doubt`. Spans are cut from this. */
  internal: InternalPhaseState;
  call: InMatchCall;
  inMatchConf: number;
  predHud: string;
  hudConf: number;
  predMap: string;
  mapConf: number;
}

export interface SessionDetection {
  frames: TimelineFrame[];
  spans: PhaseSpan[];
  segments: GameSegmentTimeline[];
  identifications: MapIdentificationResult[];
  hud: HudVersionVerdict;
  stats: {
    keyframes: number;
    inMatchFrames: number;
    scoreScreenFrames: number;
    notInMatchFrames: number;
    doubtFrames: number;
    unknownMapSegments: number;
  };
}

/**
 * MediaCodec presentation timestamps are microseconds; the whole app speaks
 * milliseconds (segment rows, FFmpeg seeks, the progress UI).
 *
 * Rounded, not truncated: a keyframe at 4166667 us is 4167 ms, and truncating
 * would drift every timestamp down by up to 1 ms — harmless for a thumbnail,
 * but it would also stop the PC oracle's `timestamp_ms` from matching, which is
 * how the phase timeline is compared at all.
 */
export function ptsUsToMs(ptsUs: number): number {
  return Math.round(ptsUs / 1000);
}

export function buildSessionDetection(
  analysis: EngineSessionAnalysis,
  candidate: MapConfigCandidate,
  cfg: ClassifierConfig,
  opts: { doubtMargin?: number } = {}
): SessionDetection {
  const doubtMargin = opts.doubtMargin ?? DEFAULT_DOUBT_MARGIN;
  const refs: RuleRef[] = analysis.refs.map((r) => ({
    texel: r.texel,
    owningClass: r.owning_class,
    zoneId: r.zone_id,
    kind: r.kind,
    effectiveWeight: r.effective_weight,
  }));
  // Before a single bit is interpreted: the rule index must be the one this
  // config describes, in the same order.
  assertRefsMatchConfig(refs, cfg);
  if (analysis.n_rules !== refs.length) {
    throw new Error(
      `the engine reported ${analysis.n_rules} rules but returned ${refs.length} refs`
    );
  }

  const resolver = createPhaseResolver(cfg.scoreScreenDurationMs);
  const frames: TimelineFrame[] = [];
  const internal: InternalPhaseState[] = [];
  const timestamps: number[] = [];
  const perFrameMapScores: Record<string, number>[] = [];

  for (let i = 0; i < analysis.frames.length; i++) {
    const row = analysis.frames[i];
    const scores = scoreFromFires(row.fires, refs, cfg);
    const call = inMatchCall(scores.inMatchConf, { doubtMargin });
    const timestampMs = ptsUsToMs(row.pts_us);
    const emitted = resolver.push(timestampMs, call);
    const internalState = resolver.state();
    frames.push({
      frameIdx: i,
      ptsUs: row.pts_us,
      timestampMs,
      emitted,
      internal: internalState,
      call,
      inMatchConf: scores.inMatchConf,
      predHud: scores.predHud,
      hudConf: scores.hudConf,
      predMap: scores.predMap,
      mapConf: scores.mapConf,
    });
    internal.push(internalState);
    timestamps.push(timestampMs);
    perFrameMapScores.push(scores.mapScores);
  }

  const spans = spansFromStates(internal);
  const segments = buildGameSegments(timestamps, internal, spans);
  const identifications: MapIdentificationResult[] = spans.map((span, index) => {
    const id: MapIdentification = identifySpanMap(
      aggregateSpanScores(perFrameMapScores, span.startFrame, span.endFrame),
      cfg
    );
    return {
      segmentIndex: index,
      mapName: id.mapName,
      confidence: id.confidence,
      startFrame: span.startFrame,
      endFrame: span.endFrame,
    };
  });

  const hud = resolveSessionHudVersion(
    analysis.frames.map((f) => f.fires),
    refs,
    candidate,
    cfg
  );

  return {
    frames,
    spans,
    segments,
    identifications,
    hud,
    stats: {
      keyframes: frames.length,
      inMatchFrames: frames.filter((f) => f.emitted === "in_match").length,
      scoreScreenFrames: frames.filter((f) => f.emitted === "score_screen").length,
      notInMatchFrames: frames.filter((f) => f.emitted === "not_in_match").length,
      doubtFrames: frames.filter((f) => f.emitted === STATE_DOUBT).length,
      unknownMapSegments: identifications.filter((i) => i.mapName === null).length,
    },
  };
}
