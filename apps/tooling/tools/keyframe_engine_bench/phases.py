"""PURE phase resolution — state machine, first-class doubt, circular buffer.

No GL, no cv2, no I/O. Stream processing only: ONE forward pass, no sliding
window, no lookahead, no two-pass (AC8).

WHY DOUBT IS NEW HERE (AC8)
---------------------------
There is no upstream ``unknown`` on the path that matters.
``_argmax_with_threshold``'s ``unknown`` serves the HUD-version and map-ID
classifiers only. The **in_match** classifier -- the one that drives this state
machine and therefore AC10's timeline -- is hard-binary and never returns
unknown (``roi_detection_tester.py:725-729``, verbatim: *"Binary: clears
threshold -> in_match, else not_in_match (NOT unknown)"*). So doubt on the phase
axis is INTRODUCED by Story 12.1; it is not inherited. AC10's "9.13's enum has no
doubt member" is a symptom of that, not the cause.

THE DOUBT MECHANISM
-------------------
The only specification that exists is one clause (``SCP:46``, verbatim): doubt is
*"resolved by the reliability of surrounding transition screens"*, constrained to
stream processing. Design chosen, and stated plainly so the report can carry it:

1. **Detect.** The in_match score is ``fires / n_im`` -- with 3 shipped in_match
   zones it quantizes to {0, 1/3, 2/3, 1}. A UNANIMOUS vote (0 or 1) is
   confident; a SPLIT vote is doubt. Formally: doubt iff
   ``|ratio - threshold| < doubt_margin``. The default 0.2 makes exactly the
   split votes doubtful on today's 3-zone config, and ``doubt_margin = 0.0``
   disables doubt entirely, reproducing 9.13's behaviour exactly.
2. **Never force.** A doubtful frame is EMITTED as ``doubt`` -- it is never
   rounded to the nearest class (E4).
3. **Resolve by surrounding reliability.** A doubtful frame does NOT advance the
   machine: the internal state HOLDS. So the reliable context around it -- the
   confident frames that opened the span, and the score-screen timer armed by a
   confident falling edge -- is what determines the meaning of the doubtful
   stretch, and match spans are not shredded by an unreliable frame. This is
   one forward pass: holding uses only what is already known, never lookahead.

Consequently a frame has BOTH an emitted state (which may be ``doubt``) and an
internal state (which never is). Spans are cut from the internal state, so a
doubtful frame mid-match neither splits the span nor is silently relabelled
``in_match`` in the timeline.

ON THE "LATENT BUG" THE STORY WARNS ABOUT
-----------------------------------------
The Dev Notes flag ``video_test.py:606-614`` -- ``falling_ts = ts`` assigned
immediately before ``(ts - falling_ts) >= dur`` is evaluated, "so the
falling-edge expression is always ``0 >= dur``". The observation is accurate but
the conclusion (that the code does not implement the documented intent) does not
hold: on the falling-edge frame the elapsed time since the falling edge IS zero,
by definition. ``0 >= dur`` is therefore the CORRECT evaluation of "is the score
window already over?" -- it yields zero score frames when ``dur == 0`` and makes
the falling-edge frame the first ``score_screen`` frame when ``dur > 0``, which
is exactly what the comment describes. Elapsed time genuinely does start
mattering on the FOLLOWING frames, which take the ``score_screen`` branch where
the same expression is live. Ported as intent, with the zero made explicit
rather than laundered through a self-cancelling subtraction. Tool 11 is
untouched either way (AC18).
"""

from dataclasses import dataclass

STATE_IN_MATCH = "in_match"
STATE_SCORE_SCREEN = "score_screen"
STATE_NOT_IN_MATCH = "not_in_match"
# AC10 verdict: EXTEND 9.13's enum rather than map doubt -> not_in_match.
# Mapping it onto an existing class is precisely the "forced to the nearest
# class" that E4 forbids, and it would make an unreliable frame indistinguishable
# from a confidently-negative one downstream.
STATE_DOUBT = "doubt"

TIMELINE_STATES = (STATE_IN_MATCH, STATE_SCORE_SCREEN, STATE_NOT_IN_MATCH, STATE_DOUBT)

CALL_YES = "yes"
CALL_NO = "no"
CALL_DOUBT = "doubt"

# Split-vote band around the in_match threshold. 0.0 disables doubt (9.13 parity).
DEFAULT_DOUBT_MARGIN = 0.2


def in_match_call(
    ratio: float,
    *,
    threshold: float = 0.5,
    doubt_margin: float = DEFAULT_DOUBT_MARGIN,
) -> str:
    """in_match score -> ``yes`` | ``no`` | ``doubt``. PURE.

    ``doubt_margin = 0.0`` collapses this to Tool 9's hard-binary call.
    """
    if doubt_margin > 0.0 and abs(float(ratio) - float(threshold)) < float(doubt_margin):
        return CALL_DOUBT
    return CALL_YES if (ratio > 0.0 and ratio >= threshold) else CALL_NO


@dataclass(frozen=True)
class PhaseFrame:
    """One resolved keyframe on the timeline."""

    frame_idx: int
    timestamp_ms: int
    state: str
    confidence: float


class PhaseResolver:
    """Streaming phase state machine with first-class doubt.

    Feed keyframes in order via :meth:`push`; it returns the emitted state for
    that frame using only what it has already seen. Inherited unchanged from
    9.13 apart from doubt: ``in_match`` rising -> span; falling -> ``score_screen``
    for ``score_screen_duration_ms``; then ``not_in_match``.
    """

    def __init__(self, score_screen_duration_ms: int):
        self.dur = int(score_screen_duration_ms)
        self.state = STATE_NOT_IN_MATCH
        self.falling_ts: int | None = None

    def push(self, timestamp_ms: int, call: str) -> str:
        """One keyframe -> its emitted state. Advances the machine unless doubtful."""
        ts = int(timestamp_ms)

        if call == CALL_DOUBT:
            # Hold: the surrounding reliable context keeps its meaning. The
            # score-screen timer, if armed, keeps running underneath -- a
            # doubtful frame does not stop the clock.
            if self.state == STATE_SCORE_SCREEN and self._score_window_elapsed(ts):
                self.state = STATE_NOT_IN_MATCH
            return STATE_DOUBT

        im = call == CALL_YES

        if self.state == STATE_IN_MATCH:
            if im:
                self.state = STATE_IN_MATCH
            else:
                # Falling edge. Elapsed since the falling edge is 0 BY DEFINITION
                # on this frame, so a zero-length window is already over and a
                # positive one makes this frame the first score_screen frame.
                self.falling_ts = ts
                self.state = STATE_NOT_IN_MATCH if self.dur <= 0 else STATE_SCORE_SCREEN
        elif self.state == STATE_SCORE_SCREEN:
            if im:
                self.state = STATE_IN_MATCH       # rising edge aborts the score window
            elif self._score_window_elapsed(ts):
                self.state = STATE_NOT_IN_MATCH
            else:
                self.state = STATE_SCORE_SCREEN
        else:  # not_in_match
            self.state = STATE_IN_MATCH if im else STATE_NOT_IN_MATCH

        return self.state

    def _score_window_elapsed(self, ts: int) -> bool:
        if self.falling_ts is None:
            return True
        return (ts - self.falling_ts) >= self.dur


def resolve_phases(frames, score_screen_duration_ms: int):
    """``[(frame_idx, timestamp_ms, call)]`` -> ``(emitted_states, internal_states)``.

    One forward pass. ``internal_states`` never contains ``doubt`` and is what
    :func:`spans_from_states` cuts spans from; ``emitted_states`` is the timeline.
    """
    resolver = PhaseResolver(score_screen_duration_ms)
    emitted: list[str] = []
    internal: list[str] = []
    for _idx, ts, call in frames:
        emitted.append(resolver.push(ts, call))
        internal.append(resolver.state)
    return emitted, internal


def spans_from_states(frames, internal_states) -> list[tuple[int, int]]:
    """Maximal ``in_match`` runs -> ``[(start_frame_idx, end_frame_idx)]``.

    Post-hoc run detection over the already-computed internal states (still one
    pass over the resolved list, not a second pass over the video). Naturally
    handles mid-match start, an EOF-open span, and a rising-edge-during-score
    splitting the runs.
    """
    spans: list[tuple[int, int]] = []
    run_start: int | None = None
    last_idx: int | None = None
    for (idx, _ts, _call), st in zip(frames, internal_states):
        if st == STATE_IN_MATCH:
            if run_start is None:
                run_start = idx
            last_idx = idx
        else:
            if run_start is not None:
                spans.append((run_start, last_idx))
                run_start = None
    if run_start is not None:
        spans.append((run_start, last_idx))
    return spans


class KeyframeRing:
    """3-keyframe circular buffer emitting frame N-2 on a phase change (AC9).

    Retroactive thumbnails: the frame at the moment a phase change is DETECTED
    is already inside the new phase, so the useful thumbnail is the one two
    keyframes back. Holds exactly N, N-1, N-2 — never more (1061 keyframes x
    6.2 MB = 6.6 GB if you accumulate).
    """

    def __init__(self):
        self._buf: list[tuple[int, int, object]] = []

    def push(self, frame_idx: int, timestamp_ms: int, frame) -> None:
        self._buf.append((frame_idx, timestamp_ms, frame))
        if len(self._buf) > 3:
            self._buf.pop(0)

    def retro(self):
        """Frame N-2, or ``None`` until the buffer has seen 3 keyframes."""
        if len(self._buf) < 3:
            return None
        return self._buf[0]

    def __len__(self) -> int:
        return len(self._buf)
