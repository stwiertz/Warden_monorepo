// Story 12.4c — the phase machine's own behaviours.
//
// The Tool-12 PARITY of this module lives in `tool12Parity.test.ts`, where every
// expectation is generated from `phases.py`. This suite covers what a fixture
// cannot: the boundaries and the segment shapes the pipeline depends on, stated
// as their own assertions so a regression names itself.
//
// Story 7.5's suite tested `createGameDetector` (a KDA white-pixel ratio behind
// a debounced two-state FSM) and `pairEventsIntoSegments`. Both are gone with
// the v1 config they read; see gameDetector.ts's header.

import {
  buildGameSegments,
  createPhaseResolver,
  DEFAULT_DOUBT_MARGIN,
  inMatchCall,
  resolvePhases,
  spansFromStates,
  type InternalPhaseState,
} from "../gameDetector";

const KF = 4167; // the capture's keyframe interval, ms

describe("inMatchCall — the doubt band", () => {
  it("treats a unanimous vote as confident and a split vote as doubt", () => {
    // 3 in_match zones quantize the score to {0, 1/3, 2/3, 1}.
    expect(inMatchCall(0)).toBe("no");
    expect(inMatchCall(1)).toBe("yes");
    expect(inMatchCall(1 / 3)).toBe("doubt");
    expect(inMatchCall(2 / 3)).toBe("doubt");
  });

  it("doubtMargin = 0 disables doubt entirely (Story 9.13 parity)", () => {
    expect(inMatchCall(1 / 3, { doubtMargin: 0 })).toBe("no");
    expect(inMatchCall(2 / 3, { doubtMargin: 0 })).toBe("yes");
    // Exactly at the threshold: `ratio >= threshold` is inclusive.
    expect(inMatchCall(0.5, { doubtMargin: 0 })).toBe("yes");
  });

  it("is a band around the threshold, not a fixed pair of values", () => {
    expect(DEFAULT_DOUBT_MARGIN).toBe(0.2);
    expect(inMatchCall(0.31)).toBe("doubt");
    expect(inMatchCall(0.29)).toBe("no");
    expect(inMatchCall(0.69)).toBe("doubt");
    expect(inMatchCall(0.71)).toBe("yes");
  });

  it("never calls a zero score in-match, even at threshold 0", () => {
    // `ratio > 0 && ratio >= threshold` — no zone fired, so there is nothing to
    // be confident about.
    expect(inMatchCall(0, { threshold: 0, doubtMargin: 0 })).toBe("no");
  });
});

describe("createPhaseResolver — doubt holds, the clock does not stop", () => {
  it("holds the internal state through a doubtful frame", () => {
    const r = createPhaseResolver(15_000);
    r.push(0, "yes");
    expect(r.state()).toBe("in_match");
    expect(r.push(KF, "doubt")).toBe("doubt");
    expect(r.state()).toBe("in_match");
  });

  it("keeps the score-screen timer running underneath a doubtful frame", () => {
    const r = createPhaseResolver(10_000);
    r.push(0, "yes");
    r.push(KF, "no"); // falling edge -> score_screen
    expect(r.state()).toBe("score_screen");
    expect(r.push(KF + 4_000, "doubt")).toBe("doubt");
    expect(r.state()).toBe("score_screen");
    // 10 s after the falling edge the window is over even though the only
    // frames since were doubtful.
    expect(r.push(KF + 10_000, "doubt")).toBe("doubt");
    expect(r.state()).toBe("not_in_match");
  });

  it("cannot open a span from doubt alone", () => {
    const r = createPhaseResolver(15_000);
    expect(r.push(0, "doubt")).toBe("doubt");
    expect(r.state()).toBe("not_in_match");
  });

  it("makes the falling-edge frame the FIRST score_screen frame", () => {
    // Elapsed time since the falling edge is 0 by definition on that frame, so
    // `0 >= dur` is the correct evaluation of "is the window already over?".
    const r = createPhaseResolver(15_000);
    r.push(0, "yes");
    expect(r.push(KF, "no")).toBe("score_screen");
    expect(r.fallingTs()).toBe(KF);
  });

  it("skips score_screen entirely when the duration is 0", () => {
    const r = createPhaseResolver(0);
    r.push(0, "yes");
    expect(r.push(KF, "no")).toBe("not_in_match");
  });

  it("lets a rising edge abort the score window", () => {
    const r = createPhaseResolver(15_000);
    r.push(0, "yes");
    r.push(KF, "no");
    expect(r.push(2 * KF, "yes")).toBe("in_match");
  });
});

describe("spansFromStates", () => {
  const states = (...s: InternalPhaseState[]) => s;

  it("cuts maximal in_match runs", () => {
    expect(
      spansFromStates(
        states(
          "not_in_match",
          "in_match",
          "in_match",
          "score_screen",
          "not_in_match",
          "in_match"
        )
      )
    ).toEqual([
      { startFrame: 1, endFrame: 2 },
      { startFrame: 5, endFrame: 5 },
    ]);
  });

  it("closes a span still open at EOF rather than dropping it", () => {
    expect(spansFromStates(states("in_match", "in_match"))).toEqual([
      { startFrame: 0, endFrame: 1 },
    ]);
  });

  it("returns nothing for a session with no match at all", () => {
    expect(spansFromStates(states("not_in_match", "score_screen"))).toEqual([]);
  });
});

describe("buildGameSegments — where the thumbnail timestamp comes from", () => {
  it("uses the first score_screen frame after the span (timing-derived)", () => {
    const timestamps = [0, KF, 2 * KF, 3 * KF, 4 * KF];
    const internal = [
      "not_in_match",
      "in_match",
      "in_match",
      "score_screen",
      "not_in_match",
    ] as InternalPhaseState[];
    const spans = spansFromStates(internal);
    expect(buildGameSegments(timestamps, internal, spans)).toEqual([
      { startMs: KF, endMs: 2 * KF, scoreScreenMs: 3 * KF },
    ]);
  });

  it("falls back to the last in-match frame when there is no score screen", () => {
    // An EOF-open span: the match was still running when the capture ended, so
    // there is no falling edge to derive a score screen from. The results stage
    // still gets a usable timestamp rather than `undefined`.
    const timestamps = [0, KF, 2 * KF];
    const internal = ["not_in_match", "in_match", "in_match"] as InternalPhaseState[];
    expect(
      buildGameSegments(timestamps, internal, spansFromStates(internal))
    ).toEqual([{ startMs: KF, endMs: 2 * KF, scoreScreenMs: 2 * KF }]);
  });

  it("never hangs one segment's thumbnail on a later match's score screen", () => {
    // Two matches back to back with the score window aborted by the rising edge:
    // the first segment must fall back to its own end, not reach forward.
    const timestamps = [0, KF, 2 * KF, 3 * KF];
    const internal = [
      "in_match",
      "in_match",
      "not_in_match",
      "in_match",
    ] as InternalPhaseState[];
    const segments = buildGameSegments(
      timestamps,
      internal,
      spansFromStates(internal)
    );
    expect(segments).toHaveLength(2);
    expect(segments[0].scoreScreenMs).toBe(KF);
  });
});

describe("resolvePhases — one forward pass", () => {
  it("returns an emitted timeline that may contain doubt and an internal one that never does", () => {
    const frames = [
      { timestampMs: 0, call: "yes" as const },
      { timestampMs: KF, call: "doubt" as const },
      { timestampMs: 2 * KF, call: "yes" as const },
    ];
    const { emitted, internal } = resolvePhases(frames, 15_000);
    expect(emitted).toEqual(["in_match", "doubt", "in_match"]);
    expect(internal).toEqual(["in_match", "in_match", "in_match"]);
    expect(spansFromStates(internal)).toEqual([{ startFrame: 0, endFrame: 2 }]);
  });
});
