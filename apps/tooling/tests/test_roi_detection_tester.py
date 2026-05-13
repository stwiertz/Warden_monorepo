"""Pure-logic unit tests for Tool 9 (roi_detection_tester) — no Tk, all tmp_path-based.

Covers: loader (yaml/json split into game-state + per-map; empty class lists; unknown
class warns + lands in ignored_classes; bad-shape clean error), band-fire test
(synthetic frame + known band → fires True/False; hue-wrap band; rect off-frame
clipped), frame resize (preserves aspect; marker pixel survives), evaluate_frame
(per-zone fires + score-vectors + predicted class with tie-break + threshold-or-
unknown), aggregate_metrics (per-zone TP/FP/FN/TN + /0 guard + confusion matrices +
top-line accuracy), end-to-end main() smoke (2-class fixture → 100% accuracy +
report.json/summary.md), and CLI guards.
"""

from __future__ import annotations

import json
import os

import cv2
import numpy as np
import pytest
import yaml

from tools.auto_roi_discoverer.model import HsvBand, Rect, TARGET_CLASSES
from tools.frame_labeler import MAP_LABELS

from tools.roi_detection_tester import (
    FrameResult,
    ZoneSpec,
    ZonesFragment,
    _argmax_with_threshold,
    _folder_to_gs,
    _resize_to_ref,
    _version_sort_key,
    aggregate_metrics,
    evaluate_frame,
    iter_labeled_frames,
    load_zones_fragment,
    main,
    zone_fires_on_frame,
)


# ===========================================================================
# Helpers
# ===========================================================================


def _solid_bgr(h: int, w: int, color_bgr: tuple[int, int, int]) -> np.ndarray:
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    arr[:, :, 0] = color_bgr[0]
    arr[:, :, 1] = color_bgr[1]
    arr[:, :, 2] = color_bgr[2]
    return arr


def _hsv_user_for_bgr(color_bgr: tuple[int, int, int]) -> tuple[int, int, int]:
    """Convert a solid BGR colour to user-space HSV (H 0-360, S/V 0-100)."""
    px = np.array([[list(color_bgr)]], dtype=np.uint8)
    hsv = cv2.cvtColor(px, cv2.COLOR_BGR2HSV)[0, 0]
    h_user = int(round(float(hsv[0]) * 2.0))
    s_user = int(round(float(hsv[1]) * 100.0 / 255.0))
    v_user = int(round(float(hsv[2]) * 100.0 / 255.0))
    return h_user, s_user, v_user


def _band_for_bgr(color_bgr: tuple[int, int, int], *, tol_h: int = 15,
                  tol_sv: int = 30, min_ratio: float = 0.3) -> HsvBand:
    h, s, v = _hsv_user_for_bgr(color_bgr)
    return HsvBand(h_center=h, h_tol=tol_h, s_center=s, s_tol=tol_sv,
                   v_center=v, v_tol=tol_sv, min_ratio=min_ratio)


def _write_yaml(path, payload):
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(payload, fh, sort_keys=False)


# ===========================================================================
# load_zones_fragment
# ===========================================================================


def test_load_zones_fragment_yaml_splits_game_state_and_map(tmp_path):
    payload = {
        "_metadata": {"hud_version": "v2.0", "frame_shape": [1080, 1920, 3]},
        "lobby": [
            {"name": "lobby_z1", "x": 1, "y": 2, "width": 10, "height": 10,
             "hsv": {"h_center": 0, "h_tol": 10, "s_center": 0, "s_tol": 5,
                     "v_center": 50, "v_tol": 5}, "min_ratio": 0.3},
        ],
        "in_match": [],
        "score": [],
        "transition": [],
        "artefact": [
            {"name": "artefact_z1", "x": 5, "y": 5, "width": 4, "height": 4,
             "hsv": {"h_center": 20, "h_tol": 10, "s_center": 80, "s_tol": 10,
                     "v_center": 80, "v_tol": 10}, "min_ratio": 0.3},
        ],
        "atlantis": [],
    }
    p = tmp_path / "discovered_zones.yaml"
    _write_yaml(p, payload)

    fragment = load_zones_fragment(str(p))
    assert isinstance(fragment, ZonesFragment)
    # game-state ordering follows TARGET_CLASSES
    assert list(fragment.game_state_zones.keys()) == list(TARGET_CLASSES)
    assert len(fragment.game_state_zones["lobby"]) == 1
    assert fragment.game_state_zones["lobby"][0].kind == "game_state"
    assert fragment.game_state_zones["lobby"][0].owning_class == "lobby"
    # map ordering follows MAP_LABELS
    assert list(fragment.map_zones.keys()) == list(MAP_LABELS)
    assert len(fragment.map_zones["artefact"]) == 1
    assert fragment.map_zones["artefact"][0].kind == "map"
    assert fragment.metadata.get("hud_version") == "v2.0"
    assert fragment.ignored_classes == []


def test_load_zones_fragment_json_also_works(tmp_path):
    payload = {
        "_metadata": {"hud_version": "v2.0"},
        "lobby": [{"name": "lobby_z1", "x": 0, "y": 0, "width": 5, "height": 5,
                   "hsv": {"h_center": 0, "h_tol": 10, "s_center": 0, "s_tol": 5,
                           "v_center": 50, "v_tol": 5}, "min_ratio": 0.3}],
    }
    p = tmp_path / "discovered_zones.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    fragment = load_zones_fragment(str(p))
    assert len(fragment.game_state_zones["lobby"]) == 1


def test_load_zones_fragment_unknown_class_warns_and_records(tmp_path, capsys):
    payload = {
        "_metadata": {},
        "made_up_class": [{"name": "x", "x": 0, "y": 0, "width": 1, "height": 1,
                           "hsv": {"h_center": 0, "h_tol": 5, "s_center": 0, "s_tol": 5,
                                   "v_center": 0, "v_tol": 5}}],
    }
    p = tmp_path / "discovered_zones.yaml"
    _write_yaml(p, payload)
    fragment = load_zones_fragment(str(p))
    assert "made_up_class" in fragment.ignored_classes
    captured = capsys.readouterr()
    assert "made_up_class" in captured.err


def test_load_zones_fragment_bad_shape_raises(tmp_path):
    # missing required 'width' field
    payload = {"lobby": [{"name": "x", "x": 0, "y": 0, "height": 1,
                          "hsv": {"h_center": 0, "h_tol": 5, "s_center": 0, "s_tol": 5,
                                  "v_center": 0, "v_tol": 5}}]}
    p = tmp_path / "discovered_zones.yaml"
    _write_yaml(p, payload)
    with pytest.raises(ValueError, match="missing required keys"):
        load_zones_fragment(str(p))


def test_load_zones_fragment_empty_lists_tolerated(tmp_path):
    payload = {"_metadata": {}, "lobby": [], "in_match": [], "score": [], "transition": []}
    p = tmp_path / "discovered_zones.yaml"
    _write_yaml(p, payload)
    fragment = load_zones_fragment(str(p))
    for cls in TARGET_CLASSES:
        assert fragment.game_state_zones[cls] == []


# ===========================================================================
# zone_fires_on_frame
# ===========================================================================


def test_zone_fires_on_uniform_matching_band():
    # 100x100 solid red frame, 10x10 rect at (10, 10) — band matches → fires.
    frame = _solid_bgr(100, 100, (0, 0, 255))  # BGR red
    band = _band_for_bgr((0, 0, 255))
    spec = ZoneSpec(name="z", owning_class="x", kind="map",
                    rect=Rect(x=10, y=10, width=10, height=10), band=band)
    fired, ratio = zone_fires_on_frame(spec, frame)
    assert fired is True
    assert ratio > 0.9


def test_zone_fires_on_miss_does_not_fire():
    frame = _solid_bgr(100, 100, (0, 0, 255))  # red frame
    # Band looking for green — should NOT fire.
    band = _band_for_bgr((0, 255, 0), tol_h=5, tol_sv=10)
    spec = ZoneSpec(name="z", owning_class="x", kind="map",
                    rect=Rect(x=10, y=10, width=10, height=10), band=band)
    fired, ratio = zone_fires_on_frame(spec, frame)
    assert fired is False
    assert ratio < 0.1


def test_zone_fires_hue_wrap_band():
    # OpenCV red is at H=0 (and wraps); a band centered at 0 with wide tol must
    # still match a red region (hue-wrap-aware via the bitwise_or in band_inrange_ratio).
    frame = _solid_bgr(100, 100, (0, 0, 255))
    # H=355 user (≈177 OpenCV), tol=15 user → crosses 0; band_inrange_ratio handles wrap.
    band = HsvBand(h_center=355, h_tol=15, s_center=100, s_tol=10,
                   v_center=100, v_tol=10, min_ratio=0.3)
    spec = ZoneSpec(name="z", owning_class="x", kind="map",
                    rect=Rect(x=10, y=10, width=10, height=10), band=band)
    fired, ratio = zone_fires_on_frame(spec, frame)
    assert fired is True
    assert ratio > 0.9


def test_zone_fires_rect_partially_off_frame_is_clipped():
    frame = _solid_bgr(100, 100, (0, 0, 255))
    band = _band_for_bgr((0, 0, 255))
    # rect extends past the frame — clamp_to should clip it in zone_fires_on_frame.
    spec = ZoneSpec(name="z", owning_class="x", kind="map",
                    rect=Rect(x=90, y=90, width=50, height=50), band=band)
    fired, ratio = zone_fires_on_frame(spec, frame)
    # Clipped region is still all red → fires.
    assert fired is True
    assert ratio > 0.9


# ===========================================================================
# _resize_to_ref
# ===========================================================================


def test_resize_to_ref_preserves_aspect_and_marker():
    # 720x1280 frame with a marker block at (100, 100) — after upscale to 1080,
    # the marker pixel maps to a recognisable region.
    frame = _solid_bgr(720, 1280, (0, 0, 0))
    frame[100:110, 100:110] = (0, 0, 255)  # red marker
    resized = _resize_to_ref(frame, ref_height=1080)
    assert resized.shape[0] == 1080
    # Aspect: 1280 * (1080/720) = 1920
    assert resized.shape[1] == 1920
    # The marker block at row ≈ 100 * 1.5 = 150 in resized coords should still be red.
    marker_region = resized[145:165, 145:165]
    # Median R > G and B in the marker region.
    median = np.median(marker_region.reshape(-1, 3), axis=0)
    assert median[2] > median[1]  # R > G
    assert median[2] > median[0]  # R > B


def test_resize_to_ref_noop_when_same_height():
    frame = _solid_bgr(1080, 1920, (50, 50, 50))
    out = _resize_to_ref(frame, ref_height=1080)
    assert out.shape == (1080, 1920, 3)


# ===========================================================================
# _folder_to_gs
# ===========================================================================


def test_folder_to_gs_direct_classes():
    assert _folder_to_gs("lobby", MAP_LABELS) == "lobby"
    assert _folder_to_gs("score", MAP_LABELS) == "score"
    assert _folder_to_gs("transition", MAP_LABELS) == "transition"


def test_folder_to_gs_map_folder_maps_to_in_match():
    assert _folder_to_gs("artefact", MAP_LABELS) == "in_match"
    assert _folder_to_gs(MAP_LABELS[0], MAP_LABELS) == "in_match"


def test_folder_to_gs_unknown_returns_none():
    assert _folder_to_gs("weirdo", MAP_LABELS) is None


# ===========================================================================
# evaluate_frame
# ===========================================================================


def test_evaluate_frame_picks_red_lobby_on_red_frame_below_threshold():
    # 3-zone fragment: 1 red-lobby + 1 blue-score + 1 red-artefact.
    red_band = _band_for_bgr((0, 0, 255))
    blue_band = _band_for_bgr((255, 0, 0))
    rect = Rect(x=10, y=10, width=10, height=10)

    fragment = ZonesFragment(
        metadata={"frame_shape": [100, 100, 3]},
        game_state_zones={
            "lobby": [ZoneSpec("lobby_z1", "lobby", "game_state", rect, red_band)],
            "in_match": [],
            "score": [ZoneSpec("score_z1", "score", "game_state", rect, blue_band)],
            "transition": [],
        },
        map_zones={cls: [] for cls in MAP_LABELS},
        ignored_classes=[],
    )
    fragment.map_zones["artefact"] = [ZoneSpec("artefact_z1", "artefact", "map", rect, red_band)]

    frame = _solid_bgr(100, 100, (0, 0, 255))  # red
    result = evaluate_frame(frame, fragment, folder="lobby", game_state_threshold=0.5)
    assert result.gt_game_state == "lobby"
    # Lobby zone fires (red), score zone doesn't (blue band on red).
    assert result.zone_fires[("lobby", "lobby_z1")] is True
    assert result.zone_fires[("score", "score_z1")] is False
    assert result.gs_scores["lobby"] == 1.0
    assert result.gs_scores["score"] == 0.0
    assert result.gs_predicted == "lobby"
    assert result.gs_max_score == 1.0
    # folder "lobby" is NOT in MAP_LABELS → no map-ID prediction.
    assert result.map_predicted is None


def test_evaluate_frame_below_threshold_is_unknown():
    # 4-zone lobby fragment; only 1 fires → score=0.25 < 0.5 → "unknown".
    red_band = _band_for_bgr((0, 0, 255))
    blue_band = _band_for_bgr((255, 0, 0))
    rect = Rect(x=10, y=10, width=10, height=10)
    fragment = ZonesFragment(
        metadata={},
        game_state_zones={
            "lobby": [
                ZoneSpec("lobby_z1", "lobby", "game_state", rect, red_band),
                ZoneSpec("lobby_z2", "lobby", "game_state", rect, blue_band),
                ZoneSpec("lobby_z3", "lobby", "game_state", rect, blue_band),
                ZoneSpec("lobby_z4", "lobby", "game_state", rect, blue_band),
            ],
            "in_match": [],
            "score": [],
            "transition": [],
        },
        map_zones={cls: [] for cls in MAP_LABELS},
        ignored_classes=[],
    )
    frame = _solid_bgr(100, 100, (0, 0, 255))  # red
    result = evaluate_frame(frame, fragment, folder="lobby", game_state_threshold=0.5)
    # 1/4 = 0.25 < 0.5 → unknown
    assert result.gs_scores["lobby"] == 0.25
    assert result.gs_predicted == "unknown"


def test_evaluate_frame_map_id_only_for_map_folders():
    red_band = _band_for_bgr((0, 0, 255))
    rect = Rect(x=10, y=10, width=10, height=10)
    fragment = ZonesFragment(
        metadata={},
        game_state_zones={cls: [] for cls in TARGET_CLASSES},
        map_zones={cls: [] for cls in MAP_LABELS},
        ignored_classes=[],
    )
    fragment.map_zones["artefact"] = [ZoneSpec("artefact_z1", "artefact", "map", rect, red_band)]
    fragment.game_state_zones["in_match"] = [
        ZoneSpec("in_match_z1", "in_match", "game_state", rect, red_band)
    ]
    frame = _solid_bgr(100, 100, (0, 0, 255))

    # MAP_LABELS folder → map-ID prediction made.
    result_map = evaluate_frame(frame, fragment, folder="artefact")
    assert result_map.gt_game_state == "in_match"
    assert result_map.gt_map == "artefact"
    assert result_map.map_predicted == "artefact"

    # lobby folder → no map-ID prediction.
    result_lobby = evaluate_frame(frame, fragment, folder="lobby")
    assert result_lobby.gt_map is None
    assert result_lobby.map_predicted is None


# ===========================================================================
# aggregate_metrics
# ===========================================================================


def test_aggregate_metrics_per_zone_metrics_with_div_zero_guard():
    # Single per-map zone, single frame from its map → TP=1, all others 0.
    rect = Rect(x=0, y=0, width=10, height=10)
    band = _band_for_bgr((0, 0, 255))
    fragment = ZonesFragment(
        metadata={},
        game_state_zones={cls: [] for cls in TARGET_CLASSES},
        map_zones={cls: [] for cls in MAP_LABELS},
        ignored_classes=[],
    )
    fragment.map_zones["artefact"] = [ZoneSpec("z", "artefact", "map", rect, band)]
    per_frame = [
        FrameResult(
            frame_path="a.png", folder="artefact", gt_game_state="in_match",
            gt_map="artefact",
            zone_fires={("artefact", "z"): True},
            gs_scores={}, gs_predicted="unknown", gs_max_score=0.0,
            map_scores={"artefact": 1.0}, map_predicted="artefact", map_max_score=1.0,
        ),
    ]
    report = aggregate_metrics(per_frame, fragment)
    pz = next(z for z in report.per_zone if z["name"] == "z")
    assert pz["tp"] == 1 and pz["fp"] == 0 and pz["fn"] == 0 and pz["tn"] == 0
    assert pz["precision"] == 1.0
    assert pz["recall"] == 1.0
    assert pz["f1"] == 1.0


def test_aggregate_metrics_divide_by_zero_returns_zero():
    rect = Rect(x=0, y=0, width=10, height=10)
    band = _band_for_bgr((0, 0, 255))
    fragment = ZonesFragment(
        metadata={},
        game_state_zones={cls: [] for cls in TARGET_CLASSES},
        map_zones={cls: [] for cls in MAP_LABELS},
        ignored_classes=[],
    )
    fragment.map_zones["artefact"] = [ZoneSpec("z", "artefact", "map", rect, band)]
    # No frames from artefact folder → tp=fn=0 → recall=0/0 guarded to 0.0.
    per_frame = [
        FrameResult(
            frame_path="a.png", folder="lobby", gt_game_state="lobby", gt_map=None,
            zone_fires={("artefact", "z"): False},
            gs_scores={}, gs_predicted="unknown", gs_max_score=0.0,
            map_scores={}, map_predicted=None, map_max_score=0.0,
        ),
    ]
    report = aggregate_metrics(per_frame, fragment)
    pz = next(z for z in report.per_zone if z["name"] == "z")
    assert pz["recall"] == 0.0
    assert pz["precision"] == 0.0
    assert pz["f1"] == 0.0


def test_aggregate_metrics_confusion_and_accuracy():
    rect = Rect(x=0, y=0, width=10, height=10)
    band = _band_for_bgr((0, 0, 255))
    fragment = ZonesFragment(
        metadata={},
        game_state_zones={
            "lobby": [ZoneSpec("lobby_z", "lobby", "game_state", rect, band)],
            "in_match": [], "score": [], "transition": [],
        },
        map_zones={cls: [] for cls in MAP_LABELS},
        ignored_classes=[],
    )
    per_frame = [
        FrameResult(frame_path="a.png", folder="lobby", gt_game_state="lobby", gt_map=None,
                    zone_fires={("lobby", "lobby_z"): True},
                    gs_scores={"lobby": 1.0}, gs_predicted="lobby", gs_max_score=1.0,
                    map_scores={}, map_predicted=None, map_max_score=0.0),
        FrameResult(frame_path="b.png", folder="lobby", gt_game_state="lobby", gt_map=None,
                    zone_fires={("lobby", "lobby_z"): False},
                    gs_scores={"lobby": 0.0}, gs_predicted="unknown", gs_max_score=0.0,
                    map_scores={}, map_predicted=None, map_max_score=0.0),
    ]
    report = aggregate_metrics(per_frame, fragment)
    assert report.game_state["accuracy"] == 0.5  # 1 of 2 right
    assert report.game_state["confusion"]["lobby"]["lobby"] == 1
    assert report.game_state["confusion"]["lobby"]["unknown"] == 1


# ===========================================================================
# End-to-end main() smoke
# ===========================================================================


def _make_labeled_tree(root, version, *, red_count: int, blue_count: int):
    v_dir = os.path.join(root, version)
    os.makedirs(os.path.join(v_dir, "lobby"), exist_ok=True)
    os.makedirs(os.path.join(v_dir, "artefact"), exist_ok=True)
    blue = _solid_bgr(100, 100, (255, 0, 0))   # blue → lobby
    red = _solid_bgr(100, 100, (0, 0, 255))    # red → artefact
    for i in range(blue_count):
        cv2.imwrite(os.path.join(v_dir, "lobby", f"{i:03d}.png"), blue)
    for i in range(red_count):
        cv2.imwrite(os.path.join(v_dir, "artefact", f"{i:03d}.png"), red)


def test_main_end_to_end_smoke_perfect_recognition(tmp_path):
    labeled = tmp_path / "labeled"
    _make_labeled_tree(str(labeled), "v2.0", red_count=3, blue_count=3)

    # Synthetic fragment: 1 lobby zone matching blue, 1 artefact zone matching red.
    red_band_user = _band_for_bgr((0, 0, 255))
    blue_band_user = _band_for_bgr((255, 0, 0))
    payload = {
        "_metadata": {"hud_version": "v2.0", "frame_shape": [100, 100, 3]},
        "lobby": [{"name": "lobby_z1", "x": 10, "y": 10, "width": 50, "height": 50,
                   "hsv": {"h_center": blue_band_user.h_center, "h_tol": blue_band_user.h_tol,
                           "s_center": blue_band_user.s_center, "s_tol": blue_band_user.s_tol,
                           "v_center": blue_band_user.v_center, "v_tol": blue_band_user.v_tol},
                   "min_ratio": 0.3}],
        # in_match zone must fire on the artefact (red) frames so the game-state
        # classifier predicts "in_match" for them — matching their folder→GT mapping.
        "in_match": [{"name": "in_match_z1", "x": 10, "y": 10, "width": 50, "height": 50,
                      "hsv": {"h_center": red_band_user.h_center, "h_tol": red_band_user.h_tol,
                              "s_center": red_band_user.s_center, "s_tol": red_band_user.s_tol,
                              "v_center": red_band_user.v_center, "v_tol": red_band_user.v_tol},
                      "min_ratio": 0.3}],
        "score": [],
        "transition": [],
        "artefact": [{"name": "artefact_z1", "x": 10, "y": 10, "width": 50, "height": 50,
                      "hsv": {"h_center": red_band_user.h_center, "h_tol": red_band_user.h_tol,
                              "s_center": red_band_user.s_center, "s_tol": red_band_user.s_tol,
                              "v_center": red_band_user.v_center, "v_tol": red_band_user.v_tol},
                      "min_ratio": 0.3}],
    }
    zones_path = tmp_path / "discovered_zones.yaml"
    _write_yaml(zones_path, payload)

    output_root = tmp_path / "reports"
    rc = main([
        "--zones", str(zones_path),
        "--labeled", str(labeled),
        "--output", str(output_root),
    ])
    assert rc == 0

    # Find the timestamped subdir.
    v_dir = output_root / "v2.0"
    timestamp_dirs = list(v_dir.iterdir())
    assert len(timestamp_dirs) == 1
    out = timestamp_dirs[0]
    report_path = out / "report.json"
    summary_path = out / "summary.md"
    assert report_path.exists()
    assert summary_path.exists()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    # 6 frames evaluated for game-state (3 lobby + 3 artefact-as-in_match), all correct.
    assert report["game_state"]["accuracy"] == 1.0
    assert report["game_state"]["n_evaluated"] == 6
    # Map-ID: 3 artefact frames, all correct.
    assert report["map_id"]["accuracy"] == 1.0
    assert report["map_id"]["n_evaluated"] == 3


def test_main_save_frame_predictions_writes_csv(tmp_path):
    labeled = tmp_path / "labeled"
    _make_labeled_tree(str(labeled), "v2.0", red_count=2, blue_count=2)
    payload = {
        "_metadata": {"hud_version": "v2.0", "frame_shape": [100, 100, 3]},
        "lobby": [], "in_match": [], "score": [], "transition": [],
    }
    zones_path = tmp_path / "discovered_zones.yaml"
    _write_yaml(zones_path, payload)
    output_root = tmp_path / "reports"
    rc = main([
        "--zones", str(zones_path), "--labeled", str(labeled),
        "--output", str(output_root), "--save-frame-predictions",
    ])
    assert rc == 0
    out_dirs = list((output_root / "v2.0").iterdir())
    csv_path = out_dirs[0] / "frame_predictions.csv"
    assert csv_path.exists()
    text = csv_path.read_text(encoding="utf-8")
    assert "frame_path" in text  # header present
    # 4 frames + 1 header = 5 lines (plus possibly trailing newline).
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert len(lines) == 5


# ===========================================================================
# CLI guards
# ===========================================================================


def test_main_negative_limit_argparse_errors(tmp_path):
    payload = {"_metadata": {"frame_shape": [100, 100, 3]},
               "lobby": [], "in_match": [], "score": [], "transition": []}
    zones_path = tmp_path / "discovered_zones.yaml"
    _write_yaml(zones_path, payload)
    labeled = tmp_path / "labeled"
    (labeled / "v2.0").mkdir(parents=True)
    with pytest.raises(SystemExit):
        main([
            "--zones", str(zones_path), "--labeled", str(labeled),
            "--limit", "-1",
        ])


def test_main_zero_ref_height_argparse_errors(tmp_path):
    payload = {"_metadata": {"frame_shape": [100, 100, 3]},
               "lobby": [], "in_match": [], "score": [], "transition": []}
    zones_path = tmp_path / "discovered_zones.yaml"
    _write_yaml(zones_path, payload)
    labeled = tmp_path / "labeled"
    (labeled / "v2.0").mkdir(parents=True)
    with pytest.raises(SystemExit):
        main([
            "--zones", str(zones_path), "--labeled", str(labeled),
            "--ref-height", "0",
        ])


def test_main_threshold_out_of_range_errors(tmp_path):
    payload = {"_metadata": {"frame_shape": [100, 100, 3]},
               "lobby": [], "in_match": [], "score": [], "transition": []}
    zones_path = tmp_path / "discovered_zones.yaml"
    _write_yaml(zones_path, payload)
    labeled = tmp_path / "labeled"
    (labeled / "v2.0").mkdir(parents=True)
    with pytest.raises(SystemExit):
        main([
            "--zones", str(zones_path), "--labeled", str(labeled),
            "--game-state-threshold", "1.5",
        ])


def test_main_nonexistent_zones_errors(tmp_path):
    labeled = tmp_path / "labeled"
    (labeled / "v2.0").mkdir(parents=True)
    with pytest.raises(SystemExit):
        main([
            "--zones", str(tmp_path / "does_not_exist.yaml"),
            "--labeled", str(labeled),
        ])


def test_main_missing_labeled_errors(tmp_path):
    payload = {"_metadata": {"frame_shape": [100, 100, 3]},
               "lobby": [], "in_match": [], "score": [], "transition": []}
    zones_path = tmp_path / "discovered_zones.yaml"
    _write_yaml(zones_path, payload)
    with pytest.raises(SystemExit):
        main([
            "--zones", str(zones_path),
            "--labeled", str(tmp_path / "no_such_dir"),
        ])


# ===========================================================================
# iter_labeled_frames
# ===========================================================================


def test_iter_labeled_frames_respects_limit_per_class(tmp_path):
    labeled = tmp_path / "labeled"
    _make_labeled_tree(str(labeled), "v2.0", red_count=5, blue_count=5)
    results = list(iter_labeled_frames(str(labeled), "v2.0", limit_per_class=2))
    folders = [r[1] for r in results]
    assert folders.count("lobby") == 2
    assert folders.count("artefact") == 2


def test_iter_labeled_frames_missing_version_returns_empty(tmp_path):
    labeled = tmp_path / "labeled"
    labeled.mkdir()
    results = list(iter_labeled_frames(str(labeled), "v99.0"))
    assert results == []


# ===========================================================================
# Post-/bmad-code-review (2026-05-14) regression locks
# ===========================================================================


def test_argmax_all_zero_scores_returns_unknown_even_with_threshold_zero():
    """When no zone fires (every class scores 0), the prediction must be "unknown",
    even if the user lowered ``--game-state-threshold`` to 0.0 (legal per the CLI's
    `[0.0, 1.0]` range). Pre-fix `< threshold` returned a class for max_score=0
    when threshold=0."""
    scores = {"lobby": 0.0, "in_match": 0.0, "score": 0.0, "transition": 0.0}
    counts = {"lobby": 1, "in_match": 1, "score": 1, "transition": 1}
    predicted, max_score = _argmax_with_threshold(
        scores, threshold=0.0, ordered_classes=TARGET_CLASSES, zone_counts=counts,
    )
    assert predicted == "unknown"
    assert max_score == 0.0


def test_version_sort_key_natural_order_v10_beats_v2():
    """Natural sort so ``v10.0`` > ``v2.0`` (lex would give the opposite)."""
    assert _version_sort_key("v10.0") > _version_sort_key("v2.0")
    assert _version_sort_key("v2.0") > _version_sort_key("v1.9")
    assert _version_sort_key("v0.1") < _version_sort_key("v0.2")


def test_resize_to_ref_zero_height_frame_returns_as_is():
    """A degenerate zero-height frame must not crash with ZeroDivisionError —
    return as-is, caller's subsequent zone-fire check on a 0-row region will see
    `region.size == 0` and return ratio=0.0."""
    frame = np.zeros((0, 100, 3), dtype=np.uint8)
    out = _resize_to_ref(frame, ref_height=1080)
    assert out.shape == (0, 100, 3)


def test_evaluate_frame_preserves_map_scores_on_non_map_folders(tmp_path):
    """Per-map zone scores are computed for every frame so per-zone TP/FP/TN tallies
    cover non-map folders (FrameResult.map_scores is the source of truth for the CSV
    + downstream debug). Pre-fix the dict was wiped to {} when folder ∉ MAP_LABELS."""
    # Single map-class zone matching red.
    fragment = ZonesFragment(
        metadata={},
        game_state_zones={cls: [] for cls in TARGET_CLASSES},
        map_zones={MAP_LABELS[0]: [ZoneSpec(
            name="m1", owning_class=MAP_LABELS[0], kind="map",
            rect=Rect(0, 0, 8, 8),
            band=HsvBand(h_center=0, h_tol=12, s_center=100, s_tol=30,
                         v_center=100, v_tol=30, min_ratio=0.3),
        )]},
        ignored_classes=[],
    )
    # All-red frame against a "lobby" folder (non-map) → zone false-fires.
    frame = np.full((8, 8, 3), (0, 0, 255), dtype=np.uint8)
    result = evaluate_frame(frame, fragment, folder="lobby")
    assert result.map_predicted is None              # no map-ID prediction for non-map folders
    # But map_scores must STILL carry the per-class score — caller uses it for the CSV.
    assert MAP_LABELS[0] in result.map_scores
    assert result.map_scores[MAP_LABELS[0]] == pytest.approx(1.0)
