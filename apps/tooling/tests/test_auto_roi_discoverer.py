"""Pure-logic unit tests for Tool 8 (auto_roi_discoverer) — no Tk, all tmp_path-based.

Covers: loader (synthetic overlay_stacks tree → 4 target classes incl. the Chan-pooled
in_match; mixed-shape / missing-npz / missing-summary clean errors; legacy-ROI read),
discoverer (stable-rect detection, HSV band derivation + clamps, scoring + closest-
confuser, exclusion masking, HSV-space conversions), validator (TP/FP proxy +
separability), exclusions (parse / apply / round-trip / fallback), and export
(discovered_zones.{json,yaml} + report.json + preview PNGs, re-export overwrites).
"""

import json
import math

import cv2
import numpy as np
import pytest

from tools.frame_labeler import MAP_LABELS
from tools.overlay_stack_analyzer import _stats_npz_bytes

from tools.auto_roi_discoverer import discoverer as disc
from tools.auto_roi_discoverer import exclusions as excl
from tools.auto_roi_discoverer import export as exp
from tools.auto_roi_discoverer.loader import (
    LoaderError,
    default_export_root,
    default_input_dir,
    load_legacy_rois,
    load_overlay_stacks,
)
from tools.auto_roi_discoverer.model import (
    TARGET_CLASSES,
    Candidate,
    DiscoveredZone,
    ExclusionRect,
    HsvBand,
    Rect,
    TargetClassStats,
    comparison_classes,
)
from tools.auto_roi_discoverer.validator import FP_MAX, TP_MIN, GameStateValidator


# ===========================================================================
# Synthetic-tree helpers (Tool 7's output shape)
# ===========================================================================


def _cell_summary(version, cls, *, frame_count, frame_shape, stability_score=1.0, with_npz=True):
    fs = list(int(d) for d in frame_shape)
    return {
        "version": version, "class": cls, "status": "ok", "reason": None,
        "frame_count": int(frame_count), "frame_shape": fs, "resized_count": 0,
        "stability_score": float(stability_score),
        "most_stable_hsv": [0.0, 255.0, 255.0],
        "stability_percentiles": {"p10": 0.0, "p50": 1.0, "p90": 5.0},
        "outputs": ({"mean": f"{version}/{cls}/mean.png", "stddev": f"{version}/{cls}/stddev.png",
                     "stats": f"{version}/{cls}/stats.npz"} if with_npz else
                    {"mean": f"{version}/{cls}/mean.png", "stddev": f"{version}/{cls}/stddev.png"}),
    }


def _write_cell_npz(root, version, cls, *, mean_bgr, std_bgr, mean_hsv, std_hsv, frame_count):
    cell_dir = root / version / cls
    cell_dir.mkdir(parents=True, exist_ok=True)
    fs = tuple(int(d) for d in mean_bgr.shape)
    (cell_dir / "stats.npz").write_bytes(
        _stats_npz_bytes(mean_bgr, std_bgr, mean_hsv, std_hsv, frame_count, fs)
    )


def _write_summary(root, cells, *, ref_height=None):
    summary = {
        "input_dir": str(root), "output_dir": str(root),
        "generated_at": "2026-05-12T00:00:00+00:00",
        "heatmap": False, "ref_height": ref_height, "min_frames": 2, "cells": cells,
    }
    (root / "overlay_stacks_summary.json").write_text(json.dumps(summary, indent=2))


def _const_arrays(shape, bgr=(10, 20, 30), std=2.0, hsv=(90, 100, 100)):
    mb = np.full(shape, bgr, dtype=np.float32)
    sb = np.full(shape, std, dtype=np.float32)
    mh = np.full(shape, hsv, dtype=np.float32)
    sh = np.full(shape, 1.0, dtype=np.float32)
    return mb, sb, mh, sh


def _build_synthetic_tree(root, *, shape=(8, 6, 3), map_labels=None, ref_height=None,
                          extra_shape_for_first_map=None):
    """A minimal Tool-7-style tree: lobby / score / transition + a few MAP_LABELS cells."""
    map_labels = list(map_labels if map_labels is not None else MAP_LABELS[:3])
    cells = []
    for cls in ("lobby", "score", "transition"):
        mb, sb, mh, sh = _const_arrays(shape, bgr=(50, 60, 70), std=3.0, hsv=(20, 200, 210))
        _write_cell_npz(root, "v2.0", cls, mean_bgr=mb, std_bgr=sb, mean_hsv=mh, std_hsv=sh,
                        frame_count=12)
        cells.append(_cell_summary("v2.0", cls, frame_count=12, frame_shape=shape, stability_score=8.5))
    fcounts = [10, 20, 5, 7, 13, 9]
    for i, ml in enumerate(map_labels):
        cell_shape = (extra_shape_for_first_map if (i == 0 and extra_shape_for_first_map) else shape)
        # Distinct constant values per map so the pool is exercised.
        mb = np.full(cell_shape, (10 + i * 5, 100 + i * 7, 200 - i * 3), dtype=np.float32)
        sb = np.full(cell_shape, 4.0 + i, dtype=np.float32)
        mh = np.full(cell_shape, (5 + i * 11, 120 + i * 5, 130 + i * 4), dtype=np.float32)
        sh = np.full(cell_shape, 2.0 + i * 0.5, dtype=np.float32)
        n = fcounts[i % len(fcounts)]
        _write_cell_npz(root, "v2.0", ml, mean_bgr=mb, std_bgr=sb, mean_hsv=mh, std_hsv=sh, frame_count=n)
        cells.append(_cell_summary("v2.0", ml, frame_count=n, frame_shape=cell_shape, stability_score=20.0 + i))
    _write_summary(root, cells, ref_height=ref_height)
    return map_labels, fcounts


# ===========================================================================
# loader.py
# ===========================================================================


def test_default_dirs_track_tool7_and_are_absolute():
    from tools.overlay_stack_analyzer import _default_output_dir as tool7_out
    assert default_input_dir() == tool7_out()
    assert default_input_dir().endswith(("output/overlay_stacks", "output\\overlay_stacks"))
    assert default_export_root().endswith(("output/auto_rois", "output\\auto_rois"))


def test_loader_builds_target_classes_pools_in_match_and_exposes_per_map(tmp_path):
    root = tmp_path / "overlay_stacks"
    map_labels, fcounts = _build_synthetic_tree(root, shape=(8, 6, 3), map_labels=MAP_LABELS[:3],
                                                ref_height=1080)
    loaded = load_overlay_stacks(str(root))
    assert loaded.version == "v2.0"
    assert loaded.ref_height == 1080
    assert loaded.frame_shape == (8, 6, 3)
    # Game-state classes + each present per-map cell.
    assert set(loaded.target_classes) == {"lobby", "in_match", "score", "transition", *map_labels}
    # Ordering: game-state classes (TARGET_CLASSES order) then per-map cells (MAP_LABELS order).
    keys = list(loaded.target_classes)
    assert keys[:4] == ["lobby", "in_match", "score", "transition"]
    assert keys[4:] == [m for m in MAP_LABELS if m in map_labels]
    # The per-map targets are direct (not pooled), with the summary's stability_score.
    for ml in map_labels:
        ts = loaded.target_classes[ml]
        assert not ts.is_pooled and ts.stability_score is not None
        assert ts.source_cells == (f"v2.0/{ml}",)
        assert ts.mean_bgr.shape == loaded.frame_shape
    im = loaded.target_classes["in_match"]
    assert im.is_pooled and not loaded.target_classes["lobby"].is_pooled
    assert im.stability_score is None
    assert loaded.target_classes["lobby"].stability_score == pytest.approx(8.5)
    ns = [fcounts[i % len(fcounts)] for i in range(3)]   # 10, 20, 5
    assert im.frame_count == sum(ns)
    assert len(im.source_cells) == 3

    # Cross-check the Chan-pooled BGR mean/std against a direct computation.
    means = np.stack([np.full((8, 6, 3), (10 + i * 5, 100 + i * 7, 200 - i * 3), np.float64) for i in range(3)])
    stds = np.stack([np.full((8, 6, 3), 4.0 + i, np.float64) for i in range(3)])
    w = np.array(ns, dtype=np.float64)[:, None, None, None]
    total = float(sum(ns))
    exp_mean = (means * w).sum(0) / total
    exp_var = (w * (stds ** 2 + (means - exp_mean) ** 2)).sum(0) / total
    exp_std = np.sqrt(np.maximum(exp_var, 0.0))
    np.testing.assert_allclose(im.mean_bgr, exp_mean.astype(np.float32), rtol=1e-4, atol=1e-3)
    np.testing.assert_allclose(im.std_bgr, exp_std.astype(np.float32), rtol=1e-4, atol=1e-3)
    # Pooled HSV S/V channels likewise; the circular Hue mean is in [0, 180).
    assert (im.mean_hsv[..., 0] >= 0).all() and (im.mean_hsv[..., 0] < 180).all()
    assert (im.std_hsv[..., 0] >= 0).all() and (im.std_hsv[..., 0] <= 90).all()


def test_loader_circular_hue_pool_is_weighted_circular_mean(tmp_path):
    # Two map cells with constant hues 10 and 170 (OpenCV), frame counts 30 and 10.
    root = tmp_path / "overlay_stacks"
    shape = (4, 4, 3)
    cells = []
    for cls in ("lobby", "score", "transition"):
        mb, sb, mh, sh = _const_arrays(shape)
        _write_cell_npz(root, "v2.0", cls, mean_bgr=mb, std_bgr=sb, mean_hsv=mh, std_hsv=sh, frame_count=4)
        cells.append(_cell_summary("v2.0", cls, frame_count=4, frame_shape=shape))
    specs = [(MAP_LABELS[0], 10.0, 30), (MAP_LABELS[1], 170.0, 10)]
    for ml, hue, n in specs:
        mh = np.full(shape, (hue, 200.0, 200.0), dtype=np.float32)
        _write_cell_npz(root, "v2.0", ml, mean_bgr=np.full(shape, 30.0, np.float32),
                        std_bgr=np.full(shape, 2.0, np.float32), mean_hsv=mh,
                        std_hsv=np.full(shape, 1.0, np.float32), frame_count=n)
        cells.append(_cell_summary("v2.0", ml, frame_count=n, frame_shape=shape))
    _write_summary(root, cells)
    loaded = load_overlay_stacks(str(root))
    # Direct: weighted circular mean of {10° cv (×30), 170° cv (×10)} angles.
    rad = 2.0 * np.pi / 180.0
    sin = (30 * np.sin(10 * rad) + 10 * np.sin(170 * rad)) / 40.0
    cos = (30 * np.cos(10 * rad) + 10 * np.cos(170 * rad)) / 40.0
    exp_h = (math.degrees(math.atan2(sin, cos)) % 360.0) / 2.0 % 180.0
    assert float(loaded.target_classes["in_match"].mean_hsv[0, 0, 0]) == pytest.approx(exp_h, abs=0.5)


def test_loader_mixed_shape_target_cells_raises(tmp_path):
    root = tmp_path / "overlay_stacks"
    _build_synthetic_tree(root, shape=(8, 6, 3), map_labels=MAP_LABELS[:2],
                          extra_shape_for_first_map=(10, 6, 3))
    with pytest.raises(LoaderError, match="frame_shape"):
        load_overlay_stacks(str(root))


def test_loader_missing_stats_npz_raises(tmp_path):
    root = tmp_path / "overlay_stacks"
    _build_synthetic_tree(root, shape=(8, 6, 3), map_labels=MAP_LABELS[:2])
    # Delete the lobby cell's npz but keep its "ok" summary entry.
    (root / "v2.0" / "lobby" / "stats.npz").unlink()
    with pytest.raises(LoaderError, match="stats.npz"):
        load_overlay_stacks(str(root))


def test_loader_missing_or_empty_summary_raises(tmp_path):
    with pytest.raises(LoaderError, match="overlay_stacks_summary"):
        load_overlay_stacks(str(tmp_path / "nope"))
    root = tmp_path / "overlay_stacks"
    root.mkdir(parents=True)
    _write_summary(root, [])
    with pytest.raises(LoaderError, match="no .ok. cells"):
        load_overlay_stacks(str(root))


def test_loader_legacy_rois(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "reference_resolution: {width: 1920, height: 1080}\n"
        "black_detection:\n  roi_zones:\n"
        "    - {name: minimap, x: 10, y: 0, width: 200, height: 40}\n"
        "    - {name: map_name, x: 800, y: 80, width: 250, height: 22}\n"
        "minimap_identification:\n  configs:\n"
        "    - id: default\n      roi: {name: minimap, x: 0, y: 0, width: 450, height: 400}\n"
        "      maps:\n        artefact:\n          zones:\n"
        "            - {id: zone_0, x: 5, y: 6, width: 8, height: 8, "
        "hsv: {h_center: 159, h_tol: 10, s_center: 86, s_tol: 26, v_center: 48, v_tol: 24}, min_ratio: 0.3}\n"
    )
    rois = load_legacy_rois(str(cfg))
    assert rois is not None
    assert rois["reference_resolution"] == {"width": 1920, "height": 1080}
    labels = {r["label"] for r in rois["rects"]}
    assert "bd:minimap" in labels and "bd:map_name" in labels
    assert any(r["label"].startswith("mm:default:artefact") for r in rois["rects"])
    # config zones are offset by their config's roi (here roi origin is 0,0 → unchanged).
    z = next(r for r in rois["rects"] if r["label"].startswith("mm:default:artefact"))
    assert (z["x"], z["y"], z["width"], z["height"]) == (5, 6, 8, 8)
    assert load_legacy_rois(None) is None
    assert load_legacy_rois(str(tmp_path / "missing.yaml")) is None


# ===========================================================================
# model.comparison_classes — the containment-aware "other classes" set (AC15)
# ===========================================================================


def test_comparison_classes_is_containment_aware():
    maps3 = list(MAP_LABELS[:3])  # artefact, atlantis, bastion
    avail = ["lobby", "in_match", "score", "transition", *maps3]
    # game-state class → only the *other* game-state classes (NOT the maps).
    assert set(comparison_classes("in_match", avail, map_classes=MAP_LABELS)) == {"lobby", "score", "transition"}
    assert set(comparison_classes("lobby", avail, map_classes=MAP_LABELS)) == {"in_match", "score", "transition"}
    # per-map class → the *other* maps + {lobby, score, transition}, NEVER in_match.
    cc = comparison_classes("artefact", avail, map_classes=MAP_LABELS)
    assert "in_match" not in cc
    assert set(cc) == {"atlantis", "bastion", "lobby", "score", "transition"}
    # order preserved: other maps first (MAP_LABELS order), then lobby/score/transition.
    assert cc == ["atlantis", "bastion", "lobby", "score", "transition"]
    # missing classes are simply absent from the comparison set.
    small = ["lobby", "in_match", "artefact"]
    assert comparison_classes("in_match", small, map_classes=MAP_LABELS) == ["lobby"]
    assert comparison_classes("artefact", small, map_classes=MAP_LABELS) == ["lobby"]


# ===========================================================================
# discoverer.py — HSV-space helpers
# ===========================================================================


def test_hsv_space_conversions_round_trip():
    for (h, s, v) in [(0, 0, 50), (120, 80, 60), (240, 100, 100), (358, 12, 99)]:
        cv = disc.hsv_user_to_cv(h, s, v)
        back = disc.hsv_cv_to_user(*cv)
        assert back[1] == pytest.approx(s, abs=1)
        assert back[2] == pytest.approx(v, abs=1)
        # H may wrap (358 → 358, 360 → 0); compare circularly.
        assert disc.circular_dist_user(back[0], h) <= 2


def test_circular_helpers():
    assert disc.circular_mean_cv(np.array([42, 42, 42])) == pytest.approx(42.0, abs=1e-6)
    assert disc.circular_std_cv(np.array([7, 7, 7, 7])) == pytest.approx(0.0, abs=1e-4)
    # wrap-around: mean of {178, 179, 0, 1} OpenCV ≈ 179.25 (or equivalently ~ -0.75)
    m = disc.circular_mean_cv(np.array([178, 179, 0, 1]))
    assert disc.circular_dist_user(m * 2.0, 358.5) <= 2.0
    assert disc.circular_dist_user(10, 350) == pytest.approx(20.0)
    assert disc.circular_dist_user(0, 180) == pytest.approx(180.0)
    assert disc.tol_h_cv_to_user(0.0) == disc._MIN_H_TOL
    assert disc.tol_sv_cv_to_user(0.0) == disc._MIN_SV_TOL
    assert disc.tol_h_cv_to_user(20.0) == 40   # 20 H-units → 40° user


# ===========================================================================
# discoverer.py — suggest_candidates
# ===========================================================================


def _lobby_with_two_stable_blocks():
    """40×40 lobby cell: high-noise background, a 25×20 stable RED block A at (8,5) and
    a 10×10 stable TEAL block B at (2,30). Other classes match the background everywhere
    except block A (in_match orange-ish, score green, transition white)."""
    shape = (40, 40, 3)
    bg_hsv = (90.0, 100.0, 100.0)
    std_bgr = np.full(shape, 50.0, dtype=np.float32)
    std_bgr[5:25, 8:33] = 0.5     # block A — very stable
    std_bgr[30:40, 2:12] = 0.5    # block B — very stable
    mean_bgr = np.full(shape, (80.0, 80.0, 80.0), dtype=np.float32)
    mean_bgr[5:25, 8:33] = (0.0, 0.0, 255.0)   # red (BGR)
    mean_hsv = np.full(shape, bg_hsv, dtype=np.float32)
    mean_hsv[5:25, 8:33] = (0.0, 255.0, 255.0)        # red, OpenCV HSV
    std_hsv = np.full(shape, 1.0, dtype=np.float32)
    lobby = TargetClassStats(name="lobby", mean_bgr=mean_bgr, std_bgr=std_bgr,
                             mean_hsv=mean_hsv, std_hsv=std_hsv, frame_count=100,
                             frame_shape=shape, source_cells=("v2.0/lobby",), stability_score=12.0)

    def _other(blockA_hsv):
        mh = np.full(shape, bg_hsv, dtype=np.float32)
        mh[5:25, 8:33] = blockA_hsv
        return mh

    others = {
        "in_match": _other((15.0, 255.0, 255.0)),   # orange-ish — closest to red
        "score": _other((60.0, 255.0, 255.0)),      # green
        "transition": _other((0.0, 0.0, 255.0)),    # white (same hue, no saturation)
    }
    return lobby, others


def test_suggest_candidates_finds_stable_rect_with_clamped_band_and_confuser():
    lobby, others = _lobby_with_two_stable_blocks()
    cands = disc.suggest_candidates(lobby, others, exclusion_mask=None)
    assert len(cands) == 2                                  # block A + block B
    top = cands[0]
    assert top.rect.as_tuple() == (8, 5, 25, 20)            # block A's bbox
    assert top.closest_confuser == "in_match"
    # constant block → tolerances hit the _MIN_* floors; centers = red in user space.
    assert top.band.h_center == 0
    assert top.band.s_center == 100 and top.band.v_center == 100
    assert top.band.h_tol == disc._MIN_H_TOL
    assert top.band.s_tol == disc._MIN_SV_TOL and top.band.v_tol == disc._MIN_SV_TOL
    assert top.band.min_ratio == pytest.approx(0.3)
    assert 0.0 < top.size_score <= 1.0 and 0.0 < top.stability_score <= 1.0
    assert 0.0 < top.discriminativeness_score <= 1.0
    assert math.isfinite(top.instability)


def test_suggest_candidates_exclusion_mask_suppresses_a_region():
    lobby, others = _lobby_with_two_stable_blocks()
    mask = excl.build_mask([ExclusionRect("b", 2, 30, 10, 10)], lobby.frame_shape)
    cands = disc.suggest_candidates(lobby, others, exclusion_mask=mask)
    assert len(cands) == 1
    assert cands[0].rect.as_tuple() == (8, 5, 25, 20)       # only block A survives


def test_suggest_candidates_no_other_classes_gives_full_disc_score():
    lobby, _ = _lobby_with_two_stable_blocks()
    cands = disc.suggest_candidates(lobby, {}, exclusion_mask=None)
    assert cands
    assert cands[0].closest_confuser is None
    assert cands[0].discriminativeness_score == pytest.approx(1.0)


def test_derive_band_for_rect_clamps_and_centers():
    shape = (10, 10, 3)
    mh = np.full(shape, (60.0, 128.0, 200.0), dtype=np.float32)   # OpenCV hue 60 = green
    sh = np.zeros(shape, dtype=np.float32)
    band = disc.derive_band_for_rect(Rect(0, 0, 10, 10), mh, sh)
    assert band.h_center == 120                                   # 60 cv → 120° user
    assert band.s_center == round(128 * 100 / 255)
    assert band.v_center == round(200 * 100 / 255)
    assert band.h_tol == disc._MIN_H_TOL and band.s_tol == disc._MIN_SV_TOL


# ===========================================================================
# validator.py
# ===========================================================================


def _two_class_stats(score_block_bgr):
    shape = (16, 16, 3)
    lobby_mb = np.full(shape, (90.0, 90.0, 90.0), dtype=np.float32)
    lobby_mb[4:12, 4:12] = (0.0, 0.0, 255.0)         # red
    score_mb = np.full(shape, (90.0, 90.0, 90.0), dtype=np.float32)
    score_mb[4:12, 4:12] = score_block_bgr
    std_bgr = np.full(shape, 3.0, dtype=np.float32)
    std_hsv = np.full(shape, 2.0, dtype=np.float32)
    def _hsv_of(bgr_img):
        u8 = np.clip(np.round(bgr_img), 0, 255).astype(np.uint8)
        return cv2.cvtColor(u8, cv2.COLOR_BGR2HSV).astype(np.float32)
    return {
        "lobby": TargetClassStats("lobby", lobby_mb, std_bgr, _hsv_of(lobby_mb), std_hsv,
                                  100, shape, ("v2.0/lobby",), 9.0),
        "score": TargetClassStats("score", score_mb, std_bgr, _hsv_of(score_mb), std_hsv,
                                  100, shape, ("v2.0/score",), 9.0),
    }


def _red_zone(name="z1", cls="lobby"):
    return DiscoveredZone(name=name, target_class=cls, rect=Rect(4, 4, 8, 8),
                          band=HsvBand(0, 12, 100, 30, 100, 30, 0.3), origin="manual")


def test_validator_separable_when_band_fires_only_on_assigned_class():
    stats = _two_class_stats(score_block_bgr=(255.0, 0.0, 0.0))   # score block = blue, not red
    report = GameStateValidator.evaluate({"lobby": [_red_zone()]}, stats)
    zv = report.zone("z1")
    assert zv is not None and zv.fires_on_assigned
    assert zv.tp_proxy >= TP_MIN
    assert zv.fp_proxy <= FP_MAX
    # fp_proxy == 0 on every other class → no real confuser; worst_confuser stays None
    # (post-/bmad-code-review 2026-05-14: misleading "worst confuser when fp=0" fix).
    assert zv.fp_proxy == 0.0
    assert zv.worst_confuser is None
    assert zv.separable
    cl = report.klass("lobby")
    assert cl.separable and "z1" in cl.contributing_zones
    # the other class with no zones still appears, not separable.
    assert report.klass("score") is not None and not report.klass("score").separable


def test_validator_not_separable_when_band_fires_on_a_sibling_too():
    stats = _two_class_stats(score_block_bgr=(0.0, 0.0, 255.0))   # score block ALSO red
    report = GameStateValidator.evaluate({"lobby": [_red_zone()]}, stats)
    zv = report.zone("z1")
    assert zv.fp_proxy > FP_MAX
    assert not zv.separable
    assert not report.klass("lobby").separable


def test_validator_comparison_classes_excludes_containment_pair():
    """An in_match marker that's present (identically) on a map cell must NOT be
    penalised for matching that map — the comparison set excludes the containment pair."""
    shape = (16, 16, 3)
    std_bgr = np.full(shape, 3.0, dtype=np.float32)
    std_hsv = np.full(shape, 2.0, dtype=np.float32)

    def _ts(name, block_bgr):
        mb = np.full(shape, (90.0, 90.0, 90.0), dtype=np.float32)
        mb[4:12, 4:12] = block_bgr
        u8 = np.clip(np.round(mb), 0, 255).astype(np.uint8)
        return TargetClassStats(name, mb, std_bgr, cv2.cvtColor(u8, cv2.COLOR_BGR2HSV).astype(np.float32),
                                std_hsv, 100, shape, (f"v2.0/{name}",), 9.0)

    classes = {
        "lobby": _ts("lobby", (90.0, 90.0, 90.0)),     # gray block
        "in_match": _ts("in_match", (0.0, 0.0, 255.0)),  # red block
        "artefact": _ts("artefact", (0.0, 0.0, 255.0)),  # red block too — it's part of in_match
    }
    zone = DiscoveredZone("im1", "in_match", Rect(4, 4, 8, 8), HsvBand(0, 12, 100, 30, 100, 30, 0.3), "manual")

    # All-others (no comparison_classes): the in_match zone matches artefact's red block → high FP.
    r_all = GameStateValidator.evaluate({"in_match": [zone]}, classes)
    assert r_all.zone("im1").fp_proxy > FP_MAX
    assert r_all.zone("im1").worst_confuser == "artefact"
    assert not r_all.zone("im1").separable

    # Containment-aware: in_match compares only against lobby (the gray block) → low FP → separable.
    cc = {c: comparison_classes(c, classes, map_classes=MAP_LABELS) for c in classes}
    assert "artefact" not in cc["in_match"] and cc["in_match"] == ["lobby"]
    r_cc = GameStateValidator.evaluate({"in_match": [zone]}, classes, comparison_classes=cc)
    zv = r_cc.zone("im1")
    assert zv.fp_proxy <= FP_MAX
    # The single comparison class (lobby) is gray, our band is red → fp_proxy == 0 →
    # worst_confuser stays None (post-/bmad-code-review 2026-05-14 fix).
    assert zv.fp_proxy == 0.0
    assert zv.worst_confuser is None
    assert zv.separable
    assert r_cc.klass("in_match").separable


# ===========================================================================
# exclusions.py
# ===========================================================================


_EXCL_YAML = """\
exclusions:
  v2.0:
    _all:
      - {name: ko_counter, x: 1, y: 2, width: 3, height: 4}
    lobby:
      - {name: rotating_banner, x: 5, y: 6, width: 7, height: 8}
    in_match: []
    score: []
    transition: []
"""


def test_exclusions_parse_apply_and_mask(tmp_path):
    path = tmp_path / "exclusions.yaml"
    path.write_text(_EXCL_YAML)
    data = excl.parse_exclusions(str(path))
    assert set(data) == {"v2.0"}
    lobby_rects = excl.exclusion_rects_for(data, "v2.0", "lobby")
    assert {r.name for r in lobby_rects} == {"ko_counter", "rotating_banner"}      # _all + per-class
    score_rects = excl.exclusion_rects_for(data, "v2.0", "score")
    assert [r.name for r in score_rects] == ["ko_counter"]                          # just _all
    mask = excl.build_mask([excl.ExclusionRect("k", 1, 2, 3, 4)], (20, 20))
    assert mask.shape == (20, 20) and bool(mask[2, 1]) and not bool(mask[0, 0])
    assert bool(mask[5, 3]) and not bool(mask[6, 4])                                # x∈[1,4), y∈[2,6)


def test_exclusions_round_trip_save_reload(tmp_path):
    src = tmp_path / "src.yaml"
    src.write_text(_EXCL_YAML)
    data = excl.parse_exclusions(str(src))
    out = tmp_path / "auto_rois" / "exclusions.yaml"
    excl.save_exclusions(str(out), data)
    assert out.exists()
    reloaded = excl.parse_exclusions(str(out))
    assert set(reloaded) == set(data)
    for v in data:
        for cls in data[v]:
            a = [(r.name, r.x, r.y, r.width, r.height) for r in data[v][cls]]
            b = [(r.name, r.x, r.y, r.width, r.height) for r in reloaded[v][cls]]
            assert a == b


def test_exclusions_missing_and_malformed_fall_back_to_empty(tmp_path):
    assert excl.parse_exclusions(None) == {}
    assert excl.parse_exclusions(str(tmp_path / "nope.yaml")) == {}
    bad = tmp_path / "bad.yaml"
    bad.write_text("just: a scalar\nnot_exclusions: 1\n")
    assert excl.parse_exclusions(str(bad)) == {}
    garbled = tmp_path / "garbled.yaml"
    garbled.write_text("exclusions:\n  v2.0:\n    lobby:\n      - {name: x, x: 1}\n")  # missing y/w/h
    parsed = excl.parse_exclusions(str(garbled))
    assert parsed.get("v2.0", {}).get("lobby") == []     # malformed rect dropped, no crash


def test_exclusions_add_and_remove():
    data: dict = {}
    excl.add_exclusion(data, "v2.0", "lobby", excl.ExclusionRect("a", 1, 1, 2, 2))
    excl.add_exclusion(data, "v2.0", "lobby", excl.ExclusionRect("b", 3, 3, 2, 2))
    assert [r.name for r in data["v2.0"]["lobby"]] == ["a", "b"]
    excl.remove_exclusion(data, "v2.0", "lobby", "a")
    assert [r.name for r in data["v2.0"]["lobby"]] == ["b"]


# ===========================================================================
# export.py
# ===========================================================================


def _read_png(path) -> np.ndarray | None:
    data = np.fromfile(str(path), dtype=np.uint8)
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def test_export_writes_fragment_report_and_previews_and_overwrites(tmp_path):
    shape = (16, 16, 3)
    classes = {
        "lobby": TargetClassStats("lobby", np.full(shape, (40, 60, 200), np.float32),
                                  np.full(shape, 2.0, np.float32), np.full(shape, (0, 200, 200), np.float32),
                                  np.full(shape, 1.0, np.float32), 80, shape, ("v2.0/lobby",), 9.0),
        "in_match": TargetClassStats("in_match", np.full(shape, (30, 30, 30), np.float32),
                                     np.full(shape, 9.0, np.float32), np.full(shape, (90, 100, 100), np.float32),
                                     np.full(shape, 4.0, np.float32), 200, shape, ("v2.0/horizon", "v2.0/silva"),
                                     None, True),
    }
    zones = {"lobby": [DiscoveredZone("lobby_z1", "lobby", Rect(2, 2, 6, 6),
                                      HsvBand(0, 10, 80, 5, 80, 5, 0.3), origin="candidate")],
             "in_match": []}   # the GUI always passes a key per loaded class (possibly empty)
    candidates = {"lobby": [Candidate(Rect(2, 2, 6, 6), HsvBand(0, 10, 80, 5, 80, 5, 0.3),
                                      0.61, 0.6, 0.7, 0.55, "in_match", 1.2)]}
    report = GameStateValidator.evaluate(zones, classes)
    excl_by_class = {"lobby": [ExclusionRect("ko", 10, 10, 3, 3)], "in_match": []}
    out_dir = exp.export_all(
        export_root=str(tmp_path / "auto_rois"), version="v2.0", target_classes=classes,
        zones_by_class=zones, candidates_by_class=candidates, validation_report=report,
        exclusion_rects_by_class=excl_by_class, ref_height=1080, frame_shape=shape,
        input_dir=str(tmp_path / "overlay_stacks"), summary_path=str(tmp_path / "overlay_stacks" / "s.json"),
        exclusions_path=str(tmp_path / "auto_rois" / "exclusions.yaml"),
    )
    out = tmp_path / "auto_rois" / "v2.0"
    assert (out / "discovered_zones.json").exists() and (out / "discovered_zones.yaml").exists()
    assert (out / "report.json").exists()
    frag = json.loads((out / "discovered_zones.json").read_text())
    assert "_metadata" in frag and "lobby" in frag and "in_match" in frag
    assert "NOT auto-merged" in frag["_metadata"]["note"]
    # New coord-frame string anchors on the actual frame_shape (h x w) and notes
    # the ref_height that produced it — see _coord_frame_str (post-/bmad-code-review fix).
    assert "1080" in frag["_metadata"]["coordinate_frame"]   # mentions --ref-height 1080
    assert f"{shape[0]}x{shape[1]}" in frag["_metadata"]["coordinate_frame"]
    z = frag["lobby"][0]
    assert set(z) == {"name", "x", "y", "width", "height", "hsv", "min_ratio"}
    assert set(z["hsv"]) == {"h_center", "h_tol", "s_center", "s_tol", "v_center", "v_tol"}
    rep = json.loads((out / "report.json").read_text())
    assert set(rep) >= {"classes", "validation", "note", "hud_version", "input_dir", "coordinate_frame"}
    assert rep["classes"]["lobby"]["n_candidates"] == 1
    assert rep["validation"]["rule"]["tp_min"] == TP_MIN
    # YAML fragment parses to the same shape.
    import yaml
    yfrag = yaml.safe_load((out / "discovered_zones.yaml").read_text())
    assert yfrag["lobby"][0]["name"] == "lobby_z1"
    # previews are readable 3-channel images.
    for cls in classes:
        img = _read_png(out / f"{cls}_preview.png")
        assert img is not None and img.ndim == 3 and img.shape[2] == 3
    # re-export overwrites cleanly.
    out_dir2 = exp.export_all(
        export_root=str(tmp_path / "auto_rois"), version="v2.0", target_classes=classes,
        zones_by_class={}, candidates_by_class={}, validation_report=None,
        exclusion_rects_by_class={}, ref_height=None, frame_shape=shape,
        input_dir="x", summary_path="y", exclusions_path=None,
    )
    assert out_dir2 == out_dir
    frag2 = json.loads((out / "discovered_zones.json").read_text())
    assert frag2.get("lobby", []) == []      # the no-zones re-export overwrote


def test_build_fragment_keys_only_present_classes_in_target_order():
    shape = (4, 4, 3)
    zones = {
        "score": [DiscoveredZone("s1", "score", Rect(0, 0, 2, 2), HsvBand(10, 10, 50, 5, 50, 5), "manual")],
        "lobby": [DiscoveredZone("l1", "lobby", Rect(0, 0, 2, 2), HsvBand(0, 10, 50, 5, 50, 5), "manual")],
    }
    frag = exp.build_fragment(zones, version="v2.0", ref_height=None, frame_shape=shape)
    # _metadata first; class keys in TARGET_CLASSES order among those present.
    keys = [k for k in frag if k != "_metadata"]
    assert keys == ["lobby", "score"]
    assert all(c in TARGET_CLASSES for c in keys)
    assert frag["_metadata"]["coordinate_frame"].startswith("4x4")


# ===========================================================================
# Post-/bmad-code-review (2026-05-14) regression locks
# ===========================================================================


def test_tol_h_user_to_cv_clamps_but_does_not_wrap():
    """A wide hue tolerance must NOT wrap modulo 180 — it's a magnitude, not a
    position. Pre-fix `hsv_user_to_cv` applied % 180 and collapsed h_tol=360 → 0."""
    assert disc.tol_h_user_to_cv(0) == 0.0
    assert disc.tol_h_user_to_cv(20) == 10.0    # 20° user = 10 CV units
    assert disc.tol_h_user_to_cv(180) == 90.0   # full half-circle
    assert disc.tol_h_user_to_cv(360) == 90.0   # full circle → clamped (NOT wrapped to 0)
    assert disc.tol_h_user_to_cv(999) == 90.0


def test_band_inrange_ratio_full_circle_tolerance_matches_any_hue():
    """A band covering the full hue circle must match every pixel whose s/v fit —
    pre-fix the wrap-mask logic produced only two narrow slivers when h_tol ≥ 90 CV."""
    region = np.array([[[0, 0, 255], [255, 0, 0], [0, 255, 0]]], dtype=np.uint8)  # red, blue, green
    rect = Rect(0, 0, 3, 1)
    band = HsvBand(h_center=0, h_tol=360, s_center=50, s_tol=100, v_center=50, v_tol=100, min_ratio=0.3)
    ratio = disc.band_inrange_ratio = None  # ignore stale ref
    from tools.auto_roi_discoverer.validator import band_inrange_ratio
    # The 3-pixel region is BGR; cvtColor → HSV; with full-tolerance band every pixel matches.
    r = band_inrange_ratio(band, rect, region.astype(np.float32))
    assert r == pytest.approx(1.0)


def test_choose_version_natural_sort_v10_beats_v2(tmp_path):
    """Lexicographic sort would pick v2.0 over v10.0; natural sort picks v10.0."""
    from tools.auto_roi_discoverer.loader import _choose_version
    cells = [
        {"version": "v2.0", "class": "lobby"},
        {"version": "v2.0", "class": "score"},
        {"version": "v10.0", "class": "lobby"},
        {"version": "v10.0", "class": "score"},   # same count → ties on count
    ]
    assert _choose_version(cells) == "v10.0"   # natural sort: 10 > 2


def test_rect_clamp_to_fully_off_frame_returns_zero_area():
    """Pre-fix, a rect entirely off-frame was clipped to a 1×1 sliver at the boundary
    and could silently false-fire. Post-fix, it returns a 0-area rect → band fire = 0.0."""
    r = Rect(200, 200, 50, 50).clamp_to((100, 100, 3))
    assert r.width == 0 or r.height == 0
    assert r.area == 0


def test_rect_clamp_to_partial_overlap_preserves_visible_area():
    """A partially off-frame rect is still clipped to the visible portion (regression
    lock for the existing test_zone_fires_rect_partially_off_frame_is_clipped)."""
    r = Rect(90, 90, 50, 50).clamp_to((100, 100, 3))
    assert (r.x, r.y, r.width, r.height) == (90, 90, 10, 10)


def test_pool_in_match_skips_zero_frame_cells(tmp_path):
    """Zero-frame map cells must not silently inflate the pool weights — they're dropped
    (pre-fix `max(1, frame_count)` synthesised a phantom 1-frame contribution)."""
    from tools.auto_roi_discoverer.loader import _pool_in_match
    shape = (4, 4, 3)
    mb = np.full(shape, 100.0, dtype=np.float32)
    sb = np.full(shape, 1.0, dtype=np.float32)
    mh = np.full(shape, 50.0, dtype=np.float32)
    sh = np.full(shape, 1.0, dtype=np.float32)
    map_labels = list(MAP_LABELS[:2])
    cells = [
        {"class": map_labels[0], "stats": {"frame_count": 0, "mean_bgr": mb, "std_bgr": sb,
                                            "mean_hsv": mh, "std_hsv": sh}},
        {"class": map_labels[1], "stats": {"frame_count": 10, "mean_bgr": mb, "std_bgr": sb,
                                            "mean_hsv": mh, "std_hsv": sh}},
    ]
    pooled = _pool_in_match(cells, shape, "v2.0")
    assert pooled is not None
    # Only the 10-frame cell contributes; total should equal that count, NOT 11 (= 1+10).
    assert pooled.frame_count == 10


# ===========================================================================
# A tiny end-to-end-ish flow over the synthetic tree (load → suggest → validate → export)
# ===========================================================================


def test_load_suggest_validate_export_round_trip(tmp_path):
    root = tmp_path / "overlay_stacks"
    _build_synthetic_tree(root, shape=(24, 24, 3), map_labels=MAP_LABELS[:2], ref_height=1080)
    loaded = load_overlay_stacks(str(root))
    cls = "lobby"
    cands = disc.suggest_candidates(loaded.target_classes[cls],
                                    {n: ts.mean_hsv for n, ts in loaded.target_classes.items() if n != cls},
                                    exclusion_mask=None)
    # Constant synthetic cells → instability is uniform → percentile cutoff selects the
    # whole frame → one big candidate (the engine still returns something sane).
    accepted = {cls: ([DiscoveredZone(f"{cls}_z1", cls, cands[0].rect, cands[0].band, "candidate")]
                      if cands else [])}
    report = GameStateValidator.evaluate(accepted, loaded.target_classes)
    out_dir = exp.export_all(
        export_root=str(tmp_path / "auto_rois"), version=loaded.version,
        target_classes=loaded.target_classes, zones_by_class=accepted, candidates_by_class={cls: cands},
        validation_report=report, exclusion_rects_by_class={c: [] for c in loaded.target_classes},
        ref_height=loaded.ref_height, frame_shape=loaded.frame_shape, input_dir=loaded.input_dir,
        summary_path=loaded.summary_path, exclusions_path=None,
    )
    assert (tmp_path / "auto_rois" / loaded.version / "report.json").exists()
    for c in loaded.target_classes:
        assert (tmp_path / "auto_rois" / loaded.version / f"{c}_preview.png").exists()
