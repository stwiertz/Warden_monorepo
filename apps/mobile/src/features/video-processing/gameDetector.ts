// Story 12.4c (AC6 / AC9) — the game-state detector, rewritten onto the v2
// engine. The TypeScript port of Tool 12's `phases.py`.
//
// 🔴 WHAT THIS REPLACED. Until 12.4c this file was Story 7.5's KDA detector: a
// white-pixel-ratio + HSV classifier over the `kda`/`notkda` ROIs of a decoded
// JPEG, behind a debounced two-state FSM (`start_confirm_frames` /
// `end_confirm_frames`) emitting START / END / SCORE_SCREEN events. All of it is
// gone: the v1 config's ROIs and thresholds do not exist in the v2 schema, the
// engine no longer produces a `FrameBuffer` to classify, and
// `thresholds.score_offset_s` is SUPERSEDED by the config's
// `score_screen_duration_ms` (15000).
//
// What replaces it is the BINARY `in_match` classifier (engineScoring.ts) plus
// the phase machine below. The debounce is gone too, and not by omission: it was
// a per-frame confirmation counter over ~1 s keyframes, while this machine works
// on ~4.2 s keyframes and gets its stability from doubt-holding and the
// score-screen window instead.
//
// ───────────────────────────────────────────────────────────────────────────────
// 🔴 DOUBT IS FIRST-CLASS, AND DOUBT *HOLDS*. (Epic 12 constraint E4.)
//
// The in_match score is `fires / n_im` — with the 3 shipped in_match zones it
// quantizes to {0, 1/3, 2/3, 1}. A UNANIMOUS vote is confident; a SPLIT vote is
// doubt. Formally `doubt iff |ratio - threshold| < doubtMargin`, default 0.2;
// `doubtMargin = 0` disables doubt and reproduces Story 9.13 exactly.
//
// A doubtful frame is EMITTED as `doubt` — never rounded to the nearest class —
// and it does NOT advance the machine: the internal state HOLDS, so the
// surrounding reliable context (the confident frames that opened the span, the
// score-screen timer armed by a confident falling edge) is what gives the
// doubtful stretch its meaning. One forward pass; holding uses only what is
// already known, never lookahead.
//
// 🔴 CONSEQUENTLY EVERY FRAME HAS TWO STATES: an emitted one (which may be
// `doubt`) and an internal one (which never is). **SPANS ARE CUT FROM THE
// INTERNAL STATE.** Get this wrong and every in_match -> doubt -> in_match blip
// shreds one match into two segments.
// ───────────────────────────────────────────────────────────────────────────────

export const STATE_IN_MATCH = "in_match";
export const STATE_SCORE_SCREEN = "score_screen";
export const STATE_NOT_IN_MATCH = "not_in_match";
export const STATE_DOUBT = "doubt";

/**
 * Story 9.13's enum EXTENDED with `doubt`, not mapped onto an existing member:
 * mapping it to `not_in_match` is exactly the "forced to the nearest class" that
 * E4 forbids, and it would make an unreliable frame indistinguishable from a
 * confidently-negative one downstream.
 */
export type PhaseState =
  | typeof STATE_IN_MATCH
  | typeof STATE_SCORE_SCREEN
  | typeof STATE_NOT_IN_MATCH
  | typeof STATE_DOUBT;

/** The internal state can never be `doubt`. */
export type InternalPhaseState = Exclude<PhaseState, typeof STATE_DOUBT>;

export type InMatchCall = "yes" | "no" | "doubt";

/** Split-vote band around the in_match threshold. 0 disables doubt (9.13 parity). */
export const DEFAULT_DOUBT_MARGIN = 0.2;

/**
 * in_match score -> `yes` | `no` | `doubt`. PURE.
 *
 * `doubtMargin = 0` collapses this to Tool 9's hard-binary call.
 */
export function inMatchCall(
  ratio: number,
  opts: { threshold?: number; doubtMargin?: number } = {}
): InMatchCall {
  const threshold = opts.threshold ?? 0.5;
  const doubtMargin = opts.doubtMargin ?? DEFAULT_DOUBT_MARGIN;
  if (doubtMargin > 0 && Math.abs(ratio - threshold) < doubtMargin) {
    return "doubt";
  }
  return ratio > 0 && ratio >= threshold ? "yes" : "no";
}

export interface PhaseResolver {
  /** One keyframe -> its EMITTED state. Advances the machine unless doubtful. */
  push(timestampMs: number, call: InMatchCall): PhaseState;
  /** The INTERNAL state — never `doubt`. Spans are cut from this. */
  state(): InternalPhaseState;
  /** Timestamp of the last confident falling edge, or null. */
  fallingTs(): number | null;
}

/**
 * Streaming phase state machine with first-class doubt.
 *
 * Inherited unchanged from Story 9.13 apart from doubt: `in_match` rising ->
 * span; falling -> `score_screen` for `scoreScreenDurationMs`; then
 * `not_in_match`.
 */
export function createPhaseResolver(scoreScreenDurationMs: number): PhaseResolver {
  const dur = Math.trunc(scoreScreenDurationMs);
  let state: InternalPhaseState = STATE_NOT_IN_MATCH;
  let falling: number | null = null;

  const windowElapsed = (ts: number): boolean =>
    falling === null ? true : ts - falling >= dur;

  return {
    push(timestampMs: number, call: InMatchCall): PhaseState {
      const ts = Math.trunc(timestampMs);

      if (call === "doubt") {
        // HOLD. The score-screen timer, if armed, keeps running underneath — a
        // doubtful frame does not stop the clock.
        if (state === STATE_SCORE_SCREEN && windowElapsed(ts)) {
          state = STATE_NOT_IN_MATCH;
        }
        return STATE_DOUBT;
      }

      const inMatch = call === "yes";

      if (state === STATE_IN_MATCH) {
        if (inMatch) {
          state = STATE_IN_MATCH;
        } else {
          // Falling edge. Elapsed time since the falling edge is 0 BY
          // DEFINITION on this frame, so a zero-length window is already over
          // and a positive one makes this frame the FIRST score_screen frame.
          // (`phases.py` records why this is correct rather than the "latent
          // bug" the story text flagged in `video_test.py`.)
          falling = ts;
          state = dur <= 0 ? STATE_NOT_IN_MATCH : STATE_SCORE_SCREEN;
        }
      } else if (state === STATE_SCORE_SCREEN) {
        if (inMatch) {
          state = STATE_IN_MATCH; // rising edge aborts the score window
        } else if (windowElapsed(ts)) {
          state = STATE_NOT_IN_MATCH;
        } else {
          state = STATE_SCORE_SCREEN;
        }
      } else {
        state = inMatch ? STATE_IN_MATCH : STATE_NOT_IN_MATCH;
      }

      return state;
    },
    state: () => state,
    fallingTs: () => falling,
  };
}

export interface PhaseInputFrame {
  timestampMs: number;
  call: InMatchCall;
}

export interface ResolvedPhases {
  /** The timeline. May contain `doubt`. */
  emitted: PhaseState[];
  /** What spans are cut from. Never contains `doubt`. */
  internal: InternalPhaseState[];
}

/** One forward pass over the keyframes. */
export function resolvePhases(
  frames: readonly PhaseInputFrame[],
  scoreScreenDurationMs: number
): ResolvedPhases {
  const resolver = createPhaseResolver(scoreScreenDurationMs);
  const emitted: PhaseState[] = [];
  const internal: InternalPhaseState[] = [];
  for (const frame of frames) {
    emitted.push(resolver.push(frame.timestampMs, frame.call));
    internal.push(resolver.state());
  }
  return { emitted, internal };
}

export interface PhaseSpan {
  startFrame: number;
  endFrame: number;
}

/**
 * Maximal `in_match` runs over the INTERNAL states.
 *
 * Post-hoc run detection over the already-resolved list (still one pass, not a
 * second pass over the video). Naturally handles a mid-match start, a span still
 * open at EOF, and a rising edge during a score window splitting two runs.
 */
export function spansFromStates(
  internal: readonly InternalPhaseState[]
): PhaseSpan[] {
  const spans: PhaseSpan[] = [];
  let runStart: number | null = null;
  let lastIdx = 0;
  for (let i = 0; i < internal.length; i++) {
    if (internal[i] === STATE_IN_MATCH) {
      if (runStart === null) runStart = i;
      lastIdx = i;
    } else if (runStart !== null) {
      spans.push({ startFrame: runStart, endFrame: lastIdx });
      runStart = null;
    }
  }
  if (runStart !== null) spans.push({ startFrame: runStart, endFrame: lastIdx });
  return spans;
}

/**
 * A match, in wall-clock time.
 *
 * Shape preserved from Story 7.5 (`startMs` / `endMs` / `scoreScreenMs`) so
 * `segmentation.ts`, `segmentRepository` and the results stage keep working —
 * only the way the numbers are DERIVED changed.
 */
export interface GameSegmentTimeline {
  startMs: number;
  endMs: number;
  /**
   * Where to grab the result thumbnail.
   *
   * 🔴 TIMING-DERIVED, NOT A DETECTED CLASS (9.9c). It is the timestamp of the
   * first keyframe the machine resolved to `score_screen` — the confident
   * falling edge — because that is where the score screen IS by the config's own
   * `score_screen_duration_ms` contract. Story 7.5 used
   * `endMs + thresholds.score_offset_s * 1000`, a v1 threshold that no longer
   * exists.
   *
   * Falls back to `endMs` when there is no falling edge at all: a span still
   * open at EOF, or `score_screen_duration_ms = 0`. The results stage then
   * grabs the last in-match frame, which still leaves the segment a thumbnail.
   */
  scoreScreenMs: number;
}

/**
 * Spans + per-keyframe timestamps/states -> match segments.
 *
 * `internal` is required, not optional: the score-screen frame is found from the
 * internal states, and passing the emitted ones would place the thumbnail on a
 * doubtful frame.
 */
export function buildGameSegments(
  timestampsMs: readonly number[],
  internal: readonly InternalPhaseState[],
  spans: readonly PhaseSpan[]
): GameSegmentTimeline[] {
  return spans.map((span) => {
    const startMs = timestampsMs[span.startFrame];
    const endMs = timestampsMs[span.endFrame];
    // The falling edge is ALWAYS the frame right after the span — spans are cut
    // from the internal states, so `internal[endFrame + 1]` is by construction
    // the first frame that left `in_match`. Searching further would find a LATER
    // match's score window and hang this segment's thumbnail on it.
    const after = span.endFrame + 1;
    const scoreScreenMs =
      after < internal.length && internal[after] === STATE_SCORE_SCREEN
        ? timestampsMs[after]
        : endMs;
    return { startMs, endMs, scoreScreenMs };
  });
}
