"""PURE CPU-side scoring — Tool 9's THREE per-classifier formulas (AC13).

No GL, no cv2, no I/O: this takes the shader's ``[bool] * n_rules`` and produces
the same predictions Tool 9's ``evaluate_frame`` would, so AC11's accuracy number
is a like-for-like parity measure.

AC13 is the trap. ``sprint-change-proposal-2026-07-16.md:285`` says "Tool 9 sums
raw weighted" -- that is true of the **map-ID classifier only**. Verified in code,
Tool 9 uses three different formulas, and implementing one of them everywhere
silently breaks two of the three accuracy numbers:

============  ==========================================  =============================
classifier    formula                                     source
============  ==========================================  =============================
HUD-version   ``fires / n_hud`` -- normalized, unweighted  roi_detection_tester.py:675
in_match      ``fires / n_im`` -- normalized, unweighted,  roi_detection_tester.py:723
              then HARD-BINARY (never "unknown")
map-ID        ``sum(effective_weight x fired)`` -- RAW,    roi_detection_tester.py:742
              unnormalized
============  ==========================================  =============================

Tool 10's live preview normalizes weight-aware and Tool 11 uses a fourth form.
Tool 9 is the gate (AC13), so Tool 9's forms are what this reproduces. The
divergence is documented, not silently reconciled.

Known-degenerate today, and reproduced AS-IS rather than "fixed" (that is 9.16's
call): all 134 rules carry ``weight = 1.0`` / ``weight_override = null``, so the
map-ID "weighted aggregate" reduces to a plain count of fired zones. Against
``identification_threshold = 0.6`` on an UNNORMALIZED sum, any map with >= 1
fired zone clears the threshold -- so map-ID is effectively ``argmax(fired_count)``
and the threshold is near-inert.
"""

from dataclasses import dataclass, field

# Sanctioned sibling reuse — Tool 9 is `done`; module import is side-effect-free
# (its main() is __main__-guarded). Story 12.1 reaches Tool 9's argmax
# tie-breaking via _argmax_with_threshold and its HUD-dir naming bridge via
# _normalize_hud. Reproducing rather than importing these would be exactly the
# silent drift AC13 warns about. Tool 9 itself is READ-ONLY here (9.16 owns it).
from tools.common.labels import MAP_LABELS
from tools.roi_detection_tester import _argmax_with_threshold, _normalize_hud

# Tool 9's game-state defaults.
HUD_THRESHOLD = 0.5
IN_MATCH_THRESHOLD = 0.5


@dataclass
class FrameScores:
    """One frame's three classifier verdicts — mirrors Tool 9's ``FrameResult``."""

    pred_hud: str
    hud_conf: float
    pred_in_match: str | None
    in_match_conf: float
    pred_map: str | None
    map_conf: float
    map_scores: dict[str, float] = field(default_factory=dict)


def score_from_fires(
    fires,
    packed,
    config,
    *,
    folder: str | None = None,
    hud_dir: str | None = None,
    hud_threshold: float = HUD_THRESHOLD,
    in_match_threshold: float = IN_MATCH_THRESHOLD,
    map_threshold: float | None = None,
) -> FrameScores:
    """``[bool] * n_rules`` (texel order) -> the three classifier predictions.

    ``folder``/``hud_dir`` mirror Tool 9's labeled-corpus gating: in_match and
    map zones are only committed on same-HUD frames (other-HUD frames aren't
    calibrated for this config), and a map-ID prediction is only committed on a
    MAP_LABELS folder. Pass both as ``None`` for the video path, where every
    frame is same-HUD by construction and every frame gets a map score.
    """
    if len(fires) != packed.n_rules:
        raise ValueError(
            f"got {len(fires)} fires for {packed.n_rules} rules — texel order "
            f"would be misaligned"
        )

    norm_cfg_hud = _normalize_hud(config.hud_version)
    same_hud = True if hud_dir is None else (_normalize_hud(hud_dir) == norm_cfg_hud)

    # --- HUD-version classifier: normalized, unweighted (evaluated on EVERY frame)
    n_hud = len(config.hud_version_detection)
    hud_scores: dict[str, float] = {}
    if n_hud:
        hud_fires = sum(
            1 for r, f in zip(packed.refs, fires) if f and r.kind == "hud_version"
        )
        hud_scores[norm_cfg_hud] = hud_fires / float(n_hud)
    pred_hud, hud_conf = _argmax_with_threshold(
        hud_scores,
        threshold=float(hud_threshold),
        ordered_classes=[norm_cfg_hud],
        zone_counts={norm_cfg_hud: n_hud},
    )

    if not same_hud:
        return FrameScores(
            pred_hud=pred_hud, hud_conf=float(hud_conf),
            pred_in_match=None, in_match_conf=0.0,
            pred_map=None, map_conf=0.0, map_scores={},
        )

    # --- in_match classifier: normalized, unweighted, then HARD-BINARY --------
    n_im = len(config.in_match_detection)
    if n_im == 0:
        pred_in_match = "unknown"
        in_match_conf = 0.0
    else:
        im_fires = sum(
            1 for r, f in zip(packed.refs, fires) if f and r.kind == "in_match"
        )
        ratio = im_fires / float(n_im)
        in_match_conf = ratio
        # Binary: clears threshold -> in_match, else not_in_match (NOT unknown).
        # This is the classifier that drives the phase state machine, and it is
        # why AC8's "doubt" has no upstream `unknown` to inherit -- see phases.py.
        pred_in_match = (
            "in_match" if (ratio > 0.0 and ratio >= float(in_match_threshold))
            else "not_in_match"
        )

    # --- per-map ID classifier: RAW weighted aggregate ------------------------
    map_scores: dict[str, float] = {}
    map_zone_counts: dict[str, int] = {}
    agg: dict[str, float] = {}
    for r, f in zip(packed.refs, fires):
        if r.kind != "map":
            continue
        agg[r.owning_class] = agg.get(r.owning_class, 0.0) + (
            r.effective_weight if f else 0.0
        )
    for slug, zones in config.map_zones.items():
        n_z = len(zones)
        map_zone_counts[slug] = n_z
        if n_z == 0:
            continue
        map_scores[slug] = agg.get(slug, 0.0)

    resolved_map_threshold = (
        config.identification_threshold if map_threshold is None
        else float(map_threshold)
    )
    commit_map = True if folder is None else (folder in MAP_LABELS)
    if commit_map:
        pred_map, map_conf = _argmax_with_threshold(
            map_scores,
            threshold=float(resolved_map_threshold),
            ordered_classes=list(MAP_LABELS),
            zone_counts=map_zone_counts,
        )
    else:
        pred_map = None
        map_conf = 0.0

    return FrameScores(
        pred_hud=pred_hud, hud_conf=float(hud_conf),
        pred_in_match=pred_in_match, in_match_conf=float(in_match_conf),
        pred_map=pred_map, map_conf=float(map_conf),
        map_scores=map_scores,
    )
