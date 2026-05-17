"""Pure-logic unit tests for Tool 9 (roi_detection_tester) — no Tk, all
tmp_path-based, synthetic emitted-config-shaped JSON only (no real dataset /
video / config.yaml).

Refit for the Story 9.9c unified schema (Story 9.14): the predecessor
game-state-cascade tests are deleted and rebuilt as the binary-in_match + new
HUD-version + adapted weighted per-map shape. Covers: ZoneSpec id/name alias +
weighted effective_weight; _normalize_hud (v2.0↔v2); load_map_config (valid +
malformed clean-error, required-key strictness, no silent defaults); band-fire
test; frame resize; _folder_to_in_match; evaluate_frame (three classifiers,
per-HUD gating, empty-zones short-circuit, weighted per-map aggregate);
aggregate_metrics (three blocks, per-zone partitioning, zones_unpopulated);
end-to-end main() smoke + frame-predictions CSV + HUD-dir normalization; CLI
guards; iter_labeled_frames; and the preserved regression locks.
"""

from __future__ import annotations

import json
import os

import cv2
import numpy as np
import pytest

from tools.common.zones import HsvBand, Rect
from tools.common.labels import MAP_LABELS

from tools import roi_detection_tester as rdt
from tools.roi_detection_tester import (
    FrameResult,
    MapConfig,
    ZoneSpec,
    _argmax_with_threshold,
    _default_config_path,
    _folder_to_in_match,
    _normalize_hud,
    _resize_to_ref,
    _version_sort_key,
    aggregate_metrics,
    evaluate_frame,
    iter_labeled_frames,
    load_map_config,
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
    px = np.array([[list(color_bgr)]], dtype=np.uint8)
    hsv = cv2.cvtColor(px, cv2.COLOR_BGR2HSV)[0, 0]
    h_user = int(round(float(hsv[0]) * 2.0))
    s_user = int(round(float(hsv[1]) * 100.0 / 255.0))
    v_user = int(round(float(hsv[2]) * 100.0 / 255.0))
    return h_user, s_user, v_user


def _band_for_bgr(color_bgr, *, tol_h=15, tol_sv=30, min_ratio=0.3) -> HsvBand:
    h, s, v = _hsv_user_for_bgr(color_bgr)
    return HsvBand(h_center=h, h_tol=tol_h, s_center=s, s_tol=tol_sv,
                   v_center=v, v_tol=tol_sv, min_ratio=min_ratio)


def _hsv_dict_for_bgr(color_bgr, *, tol_h=15, tol_sv=30) -> dict:
    h, s, v = _hsv_user_for_bgr(color_bgr)
    return {"h_center": h, "h_tol": tol_h, "s_center": s, "s_tol": tol_sv,
            "v_center": v, "v_tol": tol_sv}


def _zone_dict(zid, x, y, w, h, hsv, *, min_ratio=0.3, weight=1.0,
               weight_override=None) -> dict:
    return {
        "id": zid, "x": x, "y": y, "width": w, "height": h, "hsv": hsv,
        "min_ratio": min_ratio, "weight": weight,
        "weight_override": weight_override,
    }


def _config_dict(*, hud_version="v2", ref_height=100, hud_zones=None,
                  in_match_zones=None, maps=None, identification_threshold=0.5,
                  minimap_id="test") -> dict:
    return {
        "schema_version": 1,
        "reference_resolution": {"width": ref_height * 16 // 9, "height": ref_height},
        "hud_version": hud_version,
        "score_screen_duration_ms": 3000,
        "hud_version_detection": hud_zones or [],
        "in_match_detection": in_match_zones or [],
        "minimap_identification": {
            "id": minimap_id,
            "identification_threshold": identification_threshold,
            "roi": {"name": "minimap", "x": 0, "y": 0, "width": 50, "height": 50},
            "maps": maps or {},
        },
    }


def _write_config(tmp_path, payload, name="map_config.v2.json") -> str:
    p = tmp_path / name
    p.write_text(json.dumps(payload), encoding="utf-8")
    return str(p)


# ===========================================================================
# ZoneSpec — id / name alias + weighted effective_weight (AC5 / AC6 / 9.13)
# ===========================================================================


def test_zonespec_id_is_canonical_name_is_alias():
    rect = Rect(0, 0, 4, 4)
    band = _band_for_bgr((0, 0, 255))
    z = ZoneSpec(id="z1", owning_class="artefact", kind="map", rect=rect, band=band)
    assert z.id == "z1"
    assert z.name == "z1"               # backward-compat read-alias (frozen for 9.13)
    assert z.weight == 1.0             # default
    assert z.weight_override is None
    assert z.effective_weight == 1.0


def test_zonespec_accepts_legacy_name_kwarg():
    # Story 9.13's video_test.py constructs ZoneSpec(name=..., ...) — must work.
    rect = Rect(0, 0, 4, 4)
    band = _band_for_bgr((0, 0, 255))
    z = ZoneSpec(name="legacy", owning_class="m", kind="map", rect=rect, band=band)
    assert z.id == "legacy"
    assert z.name == "legacy"


def test_zonespec_effective_weight_prefers_override():
    rect = Rect(0, 0, 4, 4)
    band = _band_for_bgr((0, 0, 255))
    z = ZoneSpec(id="z", owning_class="m", kind="map", rect=rect, band=band,
                 weight=2.0, weight_override=5.0)
    assert z.effective_weight == 5.0
    z2 = ZoneSpec(id="z", owning_class="m", kind="map", rect=rect, band=band,
                  weight=2.0, weight_override=None)
    assert z2.effective_weight == 2.0


def test_zonespec_requires_an_identifier():
    with pytest.raises(TypeError):
        ZoneSpec(owning_class="m", kind="map", rect=Rect(0, 0, 1, 1),
                 band=_band_for_bgr((0, 0, 255)))


# ===========================================================================
# _normalize_hud (AC0b — v2.0 ↔ v2)
# ===========================================================================


def test_normalize_hud_strips_trailing_dot_zero_and_lowercases():
    assert _normalize_hud("v2.0") == "v2"
    assert _normalize_hud("v2") == "v2"
    assert _normalize_hud("v10.0") == "v10"
    assert _normalize_hud("V2.0 ") == "v2"
    # Idempotent.
    assert _normalize_hud(_normalize_hud("v2.0")) == "v2"


def test_version_sort_key_natural_order_v10_beats_v2():
    assert _version_sort_key("v10") > _version_sort_key("v2")
    assert _version_sort_key("v2.0") > _version_sort_key("v1.9")
    assert _version_sort_key("v0.1") < _version_sort_key("v0.2")


# ===========================================================================
# _default_config_path
# ===========================================================================


def test_default_config_path_picks_newest_by_version_then_mtime(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "output" / "map_configs"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "map_config.v2.json").write_text("{}", encoding="utf-8")
    (cfg_dir / "map_config.v10.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(rdt, "_tooling_root", lambda: str(tmp_path))
    picked = _default_config_path()
    assert picked is not None
    assert os.path.basename(picked) == "map_config.v10.json"


def test_default_config_path_none_when_absent_or_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(rdt, "_tooling_root", lambda: str(tmp_path))
    assert _default_config_path() is None              # dir absent
    (tmp_path / "output" / "map_configs").mkdir(parents=True)
    assert _default_config_path() is None              # glob empty


# ===========================================================================
# load_map_config — valid + malformed (AC5: no silent defaults)
# ===========================================================================


def test_load_map_config_valid_full_shape(tmp_path):
    red = _hsv_dict_for_bgr((0, 0, 255))
    payload = _config_dict(
        hud_version="v2", ref_height=120,
        hud_zones=[_zone_dict("hud1", 0, 0, 10, 10, red)],
        in_match_zones=[_zone_dict("im1", 5, 5, 10, 10, red, weight=2.0)],
        maps={
            "artefact": {"zones": [_zone_dict("a1", 1, 1, 4, 4, red,
                                              weight=3.0, weight_override=7.0)]},
            "bastion": {"zones": []},
        },
        identification_threshold=0.4,
    )
    cfg = load_map_config(_write_config(tmp_path, payload))
    assert isinstance(cfg, MapConfig)
    assert cfg.hud_version == "v2"
    assert cfg.ref_height == 120                       # from reference_resolution.height
    assert len(cfg.hud_version_detection) == 1
    assert cfg.hud_version_detection[0].kind == "hud_version"
    assert cfg.hud_version_detection[0].owning_class == "v2"   # normalized
    assert cfg.in_match_detection[0].kind == "in_match"
    assert cfg.in_match_detection[0].weight == 2.0
    assert cfg.identification_threshold == 0.4
    # Insertion order preserved (REL-005).
    assert list(cfg.map_zones.keys()) == ["artefact", "bastion"]
    a1 = cfg.map_zones["artefact"][0]
    assert a1.kind == "map" and a1.owning_class == "artefact"
    assert a1.effective_weight == 7.0                  # weight_override wins
    assert cfg.map_zones["bastion"] == []


def test_load_map_config_missing_top_level_key_raises(tmp_path):
    payload = _config_dict()
    del payload["in_match_detection"]
    with pytest.raises(ValueError, match="missing required keys"):
        load_map_config(_write_config(tmp_path, payload))


def test_load_map_config_zone_missing_required_key_no_silent_default(tmp_path):
    # min_ratio / weight / weight_override are REQUIRED — a missing key is a
    # malformed-config error, NOT a .get(..., 0.3) default (AC5 / disaster #2).
    red = _hsv_dict_for_bgr((0, 0, 255))
    bad_zone = {"id": "z", "x": 0, "y": 0, "width": 4, "height": 4, "hsv": red,
                "weight": 1.0, "weight_override": None}  # min_ratio missing
    payload = _config_dict(in_match_zones=[bad_zone])
    with pytest.raises(ValueError, match="missing required keys.*min_ratio"):
        load_map_config(_write_config(tmp_path, payload))


def test_load_map_config_hsv_missing_key_raises(tmp_path):
    bad_hsv = {"h_center": 0, "h_tol": 5, "s_center": 0, "s_tol": 5,
               "v_center": 0}  # v_tol missing
    payload = _config_dict(in_match_zones=[_zone_dict("z", 0, 0, 4, 4, bad_hsv)])
    with pytest.raises(ValueError, match="hsv.*missing"):
        load_map_config(_write_config(tmp_path, payload))


def test_load_map_config_weight_override_wrong_type_raises(tmp_path):
    red = _hsv_dict_for_bgr((0, 0, 255))
    z = _zone_dict("z", 0, 0, 4, 4, red)
    z["weight_override"] = "not-a-number"
    payload = _config_dict(in_match_zones=[z])
    with pytest.raises(ValueError, match="weight_override"):
        load_map_config(_write_config(tmp_path, payload))


def test_load_map_config_non_numeric_scalar_clean_error_not_typeerror(tmp_path):
    # Regression (code review 2026-05-17): a present-but-wrong-typed geometry
    # value (null/list/object) used to reach Rect/HsvBand.__post_init__'s
    # int(...) -> uncaught TypeError (main only catches ValueError) -> AC5
    # "no traceback" violation. _parse_zone_dict now re-raises as ValueError.
    red = _hsv_dict_for_bgr((0, 0, 255))
    z = _zone_dict("z", 0, 0, 4, 4, red)
    z["x"] = None  # wrong type, key present (passes the required-key check)
    payload = _config_dict(in_match_zones=[z])
    with pytest.raises(ValueError, match="non-numeric or invalid"):
        load_map_config(_write_config(tmp_path, payload))


def test_main_non_numeric_scalar_clean_error_no_traceback(tmp_path, capsys):
    red = _hsv_dict_for_bgr((0, 0, 255))
    z = _zone_dict("z", 0, 0, 4, 4, red)
    z["min_ratio"] = [0.3]  # wrong type -> would TypeError in float()
    payload = _config_dict(in_match_zones=[z])
    cfg = _write_config(tmp_path, payload)
    labeled = tmp_path / "labeled"
    (labeled / "v2.0").mkdir(parents=True)
    rc = main(["--config", cfg, "--labeled", str(labeled)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "cannot load map config" in err
    assert "Traceback" not in err


def test_load_map_config_non_object_top_level_raises(tmp_path):
    p = tmp_path / "map_config.v2.json"
    p.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="must be an object"):
        load_map_config(str(p))


def test_main_malformed_config_clean_error_no_traceback(tmp_path, capsys):
    labeled = tmp_path / "labeled"
    (labeled / "v2.0").mkdir(parents=True)
    payload = _config_dict()
    del payload["minimap_identification"]
    cfg = _write_config(tmp_path, payload)
    rc = main(["--config", cfg, "--labeled", str(labeled)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "cannot load map config" in err
    assert "Traceback" not in err


# ===========================================================================
# zone_fires_on_frame  (band-fire — preserved, new Zone shape)
# ===========================================================================


def test_zone_fires_on_uniform_matching_band():
    frame = _solid_bgr(100, 100, (0, 0, 255))
    spec = ZoneSpec(id="z", owning_class="x", kind="map",
                    rect=Rect(10, 10, 10, 10), band=_band_for_bgr((0, 0, 255)))
    fired, ratio = zone_fires_on_frame(spec, frame)
    assert fired is True
    assert ratio > 0.9


def test_zone_fires_on_miss_does_not_fire():
    frame = _solid_bgr(100, 100, (0, 0, 255))
    spec = ZoneSpec(id="z", owning_class="x", kind="map",
                    rect=Rect(10, 10, 10, 10),
                    band=_band_for_bgr((0, 255, 0), tol_h=5, tol_sv=10))
    fired, ratio = zone_fires_on_frame(spec, frame)
    assert fired is False
    assert ratio < 0.1


def test_zone_fires_hue_wrap_band():
    frame = _solid_bgr(100, 100, (0, 0, 255))
    band = HsvBand(h_center=355, h_tol=15, s_center=100, s_tol=10,
                   v_center=100, v_tol=10, min_ratio=0.3)
    spec = ZoneSpec(id="z", owning_class="x", kind="map",
                    rect=Rect(10, 10, 10, 10), band=band)
    fired, ratio = zone_fires_on_frame(spec, frame)
    assert fired is True
    assert ratio > 0.9


def test_zone_fires_rect_partially_off_frame_is_clipped():
    frame = _solid_bgr(100, 100, (0, 0, 255))
    spec = ZoneSpec(id="z", owning_class="x", kind="map",
                    rect=Rect(90, 90, 50, 50), band=_band_for_bgr((0, 0, 255)))
    fired, ratio = zone_fires_on_frame(spec, frame)
    assert fired is True
    assert ratio > 0.9


# ===========================================================================
# _resize_to_ref  (preserved)
# ===========================================================================


def test_resize_to_ref_preserves_aspect_and_marker():
    frame = _solid_bgr(720, 1280, (0, 0, 0))
    frame[100:110, 100:110] = (0, 0, 255)
    resized = _resize_to_ref(frame, ref_height=1080)
    assert resized.shape[0] == 1080
    assert resized.shape[1] == 1920
    marker_region = resized[145:165, 145:165]
    median = np.median(marker_region.reshape(-1, 3), axis=0)
    assert median[2] > median[1]
    assert median[2] > median[0]


def test_resize_to_ref_noop_when_same_height():
    frame = _solid_bgr(1080, 1920, (50, 50, 50))
    out = _resize_to_ref(frame, ref_height=1080)
    assert out.shape == (1080, 1920, 3)


def test_resize_to_ref_zero_height_frame_returns_as_is():
    frame = np.zeros((0, 100, 3), dtype=np.uint8)
    out = _resize_to_ref(frame, ref_height=1080)
    assert out.shape == (0, 100, 3)


# ===========================================================================
# _folder_to_in_match  (binary GT collapse — AC3)
# ===========================================================================


def test_folder_to_in_match_map_slug_is_in_match():
    assert _folder_to_in_match("artefact") == "in_match"
    assert _folder_to_in_match(MAP_LABELS[0]) == "in_match"


def test_folder_to_in_match_non_map_is_not_in_match():
    assert _folder_to_in_match("lobby") == "not_in_match"
    assert _folder_to_in_match("score") == "not_in_match"
    assert _folder_to_in_match("transition") == "not_in_match"


# ===========================================================================
# _argmax_with_threshold  (all-zero regression lock — preserved, retargeted)
# ===========================================================================


def test_argmax_all_zero_scores_returns_unknown_even_with_threshold_zero():
    scores = {"artefact": 0.0, "bastion": 0.0}
    counts = {"artefact": 1, "bastion": 1}
    predicted, max_score = _argmax_with_threshold(
        scores, threshold=0.0, ordered_classes=MAP_LABELS, zone_counts=counts,
    )
    assert predicted == "unknown"
    assert max_score == 0.0


# ===========================================================================
# evaluate_frame — three classifiers
# ===========================================================================


def _cfg_obj(**kw) -> MapConfig:
    """Build a MapConfig directly (no JSON round-trip) for evaluate_frame tests."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "map_config.v2.json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(_config_dict(**kw), fh)
        return load_map_config(p)


def test_evaluate_frame_hud_version_fires_predicts_config_hud():
    red = _hsv_dict_for_bgr((0, 0, 255))
    cfg = _cfg_obj(hud_version="v2",
                   hud_zones=[_zone_dict("h1", 0, 0, 50, 50, red)])
    frame = _solid_bgr(100, 100, (0, 0, 255))
    fr = evaluate_frame(frame, cfg, hud_dir="v2.0", folder="lobby")
    assert fr.gt_hud == "v2"            # normalized parent dir
    assert fr.pred_hud == "v2"
    assert fr.same_hud is True


def test_evaluate_frame_cross_hud_frame_counts_as_negative():
    red = _hsv_dict_for_bgr((0, 0, 255))
    cfg = _cfg_obj(hud_version="v2",
                   hud_zones=[_zone_dict("h1", 0, 0, 50, 50, red)])
    frame = _solid_bgr(100, 100, (0, 0, 255))
    fr = evaluate_frame(frame, cfg, hud_dir="v1.0", folder="lobby")
    assert fr.gt_hud == "v1"
    assert fr.pred_hud == "v2"          # per-HUD detector still says "v2"
    assert fr.same_hud is False
    # in_match + map not evaluated for other-HUD frames (csv blanks).
    assert fr.gt_in_match is None
    assert fr.pred_in_match is None
    assert fr.gt_map is None


def test_evaluate_frame_binary_in_match_true_on_map_folder():
    red = _hsv_dict_for_bgr((0, 0, 255))
    cfg = _cfg_obj(in_match_zones=[_zone_dict("im", 10, 10, 50, 50, red)])
    frame = _solid_bgr(100, 100, (0, 0, 255))
    fr = evaluate_frame(frame, cfg, hud_dir="v2.0", folder="artefact")
    assert fr.gt_in_match == "in_match"
    assert fr.pred_in_match == "in_match"


def test_evaluate_frame_binary_below_threshold_is_not_in_match_not_unknown():
    red = _hsv_dict_for_bgr((0, 0, 255))
    blue = _hsv_dict_for_bgr((255, 0, 0))
    # 2 in_match zones; only 1 fires on a red frame → ratio 0.5 < 0.8.
    cfg = _cfg_obj(in_match_zones=[
        _zone_dict("im_red", 10, 10, 40, 40, red),
        _zone_dict("im_blue", 10, 10, 40, 40, blue),
    ])
    frame = _solid_bgr(100, 100, (0, 0, 255))
    fr = evaluate_frame(frame, cfg, hud_dir="v2.0", folder="lobby",
                        in_match_threshold=0.8)
    assert fr.in_match_conf == 0.5
    assert fr.pred_in_match == "not_in_match"   # NOT "unknown"
    assert fr.gt_in_match == "not_in_match"


def test_evaluate_frame_empty_in_match_zones_short_circuits_unknown():
    cfg = _cfg_obj(in_match_zones=[])
    frame = _solid_bgr(100, 100, (0, 0, 255))
    fr = evaluate_frame(frame, cfg, hud_dir="v2.0", folder="artefact")
    assert fr.pred_in_match == "unknown"
    assert fr.in_match_conf == 0.0


def test_evaluate_frame_weighted_per_map_aggregate_and_override():
    red = _hsv_dict_for_bgr((0, 0, 255))
    # Two single-zone maps; both zones fire on the red frame.
    cfg = _cfg_obj(
        identification_threshold=0.5,
        maps={
            "artefact": {"zones": [_zone_dict("a", 10, 10, 40, 40, red,
                                              weight=1.0)]},
            "bastion": {"zones": [_zone_dict("b", 10, 10, 40, 40, red,
                                             weight=1.0, weight_override=5.0)]},
        },
    )
    frame = _solid_bgr(100, 100, (0, 0, 255))
    fr = evaluate_frame(frame, cfg, hud_dir="v2.0", folder="artefact")
    # bastion's effective weight (override 5.0) beats artefact's 1.0 aggregate.
    assert fr.gt_map == "artefact"
    assert fr.pred_map == "bastion"
    assert fr.map_conf == 5.0


def test_evaluate_frame_map_prediction_only_on_map_folders_regression_lock():
    """Per-map zones are scored on every same-HUD frame so per-zone FP/TN
    tallies cover non-map folders, but a map-ID *prediction* commits only on
    MAP_LABELS folders (preserved invariant from the pre-refit lock)."""
    red = _hsv_dict_for_bgr((0, 0, 255))
    cfg = _cfg_obj(maps={MAP_LABELS[0]: {"zones": [
        _zone_dict("m1", 0, 0, 8, 8, red)]}})
    frame = _solid_bgr(8, 8, (0, 0, 255))   # all-red → the map zone false-fires
    fr = evaluate_frame(frame, cfg, hud_dir="v2.0", folder="lobby")
    assert fr.gt_map is None
    assert fr.pred_map is None              # non-map folder → no prediction
    # But the zone WAS scored (its fire is recorded for per-zone FP/TN).
    assert (MAP_LABELS[0], "m1") in fr.zone_fires
    assert fr.zone_fires[(MAP_LABELS[0], "m1")] is True


def test_evaluate_frame_map_threshold_override_below_returns_unknown():
    red = _hsv_dict_for_bgr((0, 0, 255))
    cfg = _cfg_obj(identification_threshold=0.5,
                   maps={"artefact": {"zones": [_zone_dict("a", 10, 10, 40, 40,
                                                           red, weight=1.0)]}})
    frame = _solid_bgr(100, 100, (0, 0, 255))
    fr = evaluate_frame(frame, cfg, hud_dir="v2.0", folder="artefact",
                        map_threshold=2.0)   # aggregate 1.0 < 2.0
    assert fr.pred_map == "unknown"


# ===========================================================================
# aggregate_metrics — three blocks, zones_unpopulated, per-zone
# ===========================================================================


def _fr(**kw) -> FrameResult:
    base = dict(
        frame_path="f.png", hud_dir="v2.0", folder="lobby", same_hud=True,
        gt_hud="v2", pred_hud="v2", hud_conf=1.0,
        gt_in_match="not_in_match", pred_in_match="not_in_match", in_match_conf=0.0,
        gt_map=None, pred_map=None, map_conf=0.0, zone_fires={},
    )
    base.update(kw)
    return FrameResult(**base)


def test_aggregate_metrics_three_blocks_present_and_accuracy():
    cfg = _cfg_obj(
        hud_zones=[_zone_dict("h", 0, 0, 4, 4, _hsv_dict_for_bgr((0, 0, 255)))],
        in_match_zones=[_zone_dict("im", 0, 0, 4, 4, _hsv_dict_for_bgr((0, 0, 255)))],
        maps={"artefact": {"zones": [_zone_dict("a", 0, 0, 4, 4,
                                                _hsv_dict_for_bgr((0, 0, 255)))]}},
    )
    frames = [
        _fr(folder="artefact", gt_in_match="in_match", pred_in_match="in_match",
            gt_map="artefact", pred_map="artefact",
            zone_fires={("v2", "h"): True, ("in_match", "im"): True,
                        ("artefact", "a"): True}),
        _fr(folder="lobby", gt_in_match="not_in_match",
            pred_in_match="not_in_match",
            zone_fires={("v2", "h"): True, ("in_match", "im"): False,
                        ("artefact", "a"): False}),
    ]
    rep = aggregate_metrics(frames, cfg)
    assert set(rep.hud_version_classifier) >= {
        "accuracy", "n_evaluated", "n_correct", "confusion", "per_class",
        "per_zone", "zones_unpopulated"}
    assert rep.hud_version_classifier["accuracy"] == 1.0    # both → v2
    assert rep.in_match_classifier["accuracy"] == 1.0       # 2/2
    assert rep.map_id_classifier["accuracy"] == 1.0         # 1/1 (artefact)
    # Per-zone partitioned by classifier kind.
    assert [z["kind"] for z in rep.hud_version_classifier["per_zone"]] == ["hud_version"]
    assert [z["kind"] for z in rep.in_match_classifier["per_zone"]] == ["in_match"]
    assert [z["kind"] for z in rep.map_id_classifier["per_zone"]] == ["map"]


def test_aggregate_metrics_empty_hud_zones_marks_unpopulated():
    cfg = _cfg_obj(hud_zones=[], in_match_zones=[
        _zone_dict("im", 0, 0, 4, 4, _hsv_dict_for_bgr((0, 0, 255)))])
    frames = [_fr(pred_hud="unknown")]
    rep = aggregate_metrics(frames, cfg)
    assert rep.hud_version_classifier["zones_unpopulated"] is True
    assert rep.hud_version_classifier["accuracy"] == 0.0
    assert rep.in_match_classifier["zones_unpopulated"] is False


def test_aggregate_metrics_empty_in_match_zones_marks_unpopulated():
    cfg = _cfg_obj(in_match_zones=[])
    frames = [_fr(pred_in_match="unknown")]
    rep = aggregate_metrics(frames, cfg)
    assert rep.in_match_classifier["zones_unpopulated"] is True
    assert rep.in_match_classifier["accuracy"] == 0.0


def test_aggregate_metrics_all_empty_maps_marks_map_unpopulated():
    cfg = _cfg_obj(maps={"artefact": {"zones": []}, "bastion": {"zones": []}})
    frames = [_fr(folder="artefact", gt_in_match="in_match",
                  gt_map="artefact", pred_map="unknown")]
    rep = aggregate_metrics(frames, cfg)
    assert rep.map_id_classifier["zones_unpopulated"] is True


def test_aggregate_metrics_per_zone_div_zero_guard():
    cfg = _cfg_obj(maps={"artefact": {"zones": [
        _zone_dict("z", 0, 0, 4, 4, _hsv_dict_for_bgr((0, 0, 255)))]}})
    # A non-map folder frame where the map zone did not fire → tp=fn=0.
    frames = [_fr(folder="lobby", zone_fires={("artefact", "z"): False})]
    rep = aggregate_metrics(frames, cfg)
    pz = next(z for z in rep.map_id_classifier["per_zone"] if z["zone_id"] == "z")
    assert pz["precision"] == 0.0
    assert pz["recall"] == 0.0
    assert pz["f1"] == 0.0


def test_aggregate_metrics_hud_per_hud_detector_vs_multi_hud_gt():
    """A v1 frame (other-HUD) is a negative for the v2 HUD detector: it appears
    as its own confusion row, prediction lands in the {v2, unknown} columns,
    and it is counted under skipped_other_hud."""
    cfg = _cfg_obj(hud_zones=[_zone_dict("h", 0, 0, 4, 4,
                                         _hsv_dict_for_bgr((0, 0, 255)))])
    frames = [
        _fr(hud_dir="v2.0", gt_hud="v2", pred_hud="v2", same_hud=True),
        _fr(hud_dir="v1.0", gt_hud="v1", pred_hud="v2", same_hud=False,
            gt_in_match=None, pred_in_match=None),
    ]
    rep = aggregate_metrics(frames, cfg)
    hv = rep.hud_version_classifier
    assert hv["n_evaluated"] == 2
    assert hv["accuracy"] == 0.5
    assert "v1" in hv["confusion"]
    assert hv["confusion"]["v1"]["v2"] == 1
    assert rep.skipped_other_hud == 1


# ===========================================================================
# End-to-end main() smoke (synthetic JSON config + labeled tree)
# ===========================================================================


def _frame_with_hud_marker(class_color) -> np.ndarray:
    """100x100 class-color frame with a 10x10 green HUD marker at (0,0)."""
    arr = _solid_bgr(100, 100, class_color)
    arr[0:10, 0:10] = (0, 255, 0)   # green HUD marker (common to all frames)
    return arr


def _make_labeled_tree(root, hud_dir, *, red_count, blue_count):
    v_dir = os.path.join(root, hud_dir)
    os.makedirs(os.path.join(v_dir, "lobby"), exist_ok=True)
    os.makedirs(os.path.join(v_dir, "artefact"), exist_ok=True)
    blue = _frame_with_hud_marker((255, 0, 0))   # blue class → lobby
    red = _frame_with_hud_marker((0, 0, 255))    # red class → artefact
    for i in range(blue_count):
        cv2.imwrite(os.path.join(v_dir, "lobby", f"{i:03d}.png"), blue)
    for i in range(red_count):
        cv2.imwrite(os.path.join(v_dir, "artefact", f"{i:03d}.png"), red)


def test_main_end_to_end_smoke_three_classifiers(tmp_path):
    labeled = tmp_path / "labeled"
    # labeled dir uses "v2.0"; config hud_version is "v2" — normalization must
    # bridge them or the HUD-version classifier scores spurious 0%.
    _make_labeled_tree(str(labeled), "v2.0", red_count=3, blue_count=3)

    green = _hsv_dict_for_bgr((0, 255, 0))
    red = _hsv_dict_for_bgr((0, 0, 255))
    payload = _config_dict(
        hud_version="v2", ref_height=100,
        hud_zones=[_zone_dict("hud_green", 0, 0, 10, 10, green)],
        in_match_zones=[_zone_dict("im_red", 40, 40, 30, 30, red)],
        maps={"artefact": {"zones": [_zone_dict("art_red", 40, 40, 30, 30, red,
                                                weight=1.0)]}},
        identification_threshold=0.5,
    )
    cfg = _write_config(tmp_path, payload)
    output_root = tmp_path / "reports"
    rc = main(["--config", cfg, "--labeled", str(labeled),
               "--output", str(output_root)])
    assert rc == 0

    out_v = output_root / "v2"           # normalized hud segment
    ts_dirs = list(out_v.iterdir())
    assert len(ts_dirs) == 1
    out = ts_dirs[0]
    assert (out / "report.json").exists()
    assert (out / "summary.md").exists()
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert set(report) >= {"hud_version_classifier", "in_match_classifier",
                           "map_id_classifier"}
    assert "game_state" not in report     # predecessor block removed (AC1)
    # HUD marker is common to all 6 frames → HUD-version 6/6.
    assert report["hud_version_classifier"]["accuracy"] == 1.0
    assert report["hud_version_classifier"]["n_evaluated"] == 6
    # in_match: 3 artefact (in_match, red fires) + 3 lobby (not_in_match, no
    # fire) → 6/6.
    assert report["in_match_classifier"]["accuracy"] == 1.0
    assert report["in_match_classifier"]["n_evaluated"] == 6
    # map-ID: 3 artefact frames, all correct.
    assert report["map_id_classifier"]["accuracy"] == 1.0
    assert report["map_id_classifier"]["n_evaluated"] == 3
    summary = (out / "summary.md").read_text(encoding="utf-8")
    assert summary.index("HUD-version classifier") < summary.index(
        "Binary in_match classifier") < summary.index("Per-map ID classifier")


def test_main_save_frame_predictions_new_columns(tmp_path):
    labeled = tmp_path / "labeled"
    _make_labeled_tree(str(labeled), "v2.0", red_count=2, blue_count=2)
    payload = _config_dict(hud_version="v2")  # all empty zones
    cfg = _write_config(tmp_path, payload)
    output_root = tmp_path / "reports"
    rc = main(["--config", cfg, "--labeled", str(labeled),
               "--output", str(output_root), "--save-frame-predictions"])
    assert rc == 0
    out_dirs = list((output_root / "v2").iterdir())
    csv_path = out_dirs[0] / "frame_predictions.csv"
    assert csv_path.exists()
    text = csv_path.read_text(encoding="utf-8")
    header = text.splitlines()[0]
    assert header == (
        "frame_path,ground_truth_hud_version,predicted_hud_version,"
        "hud_version_confidence,ground_truth_in_match,predicted_in_match,"
        "in_match_confidence,ground_truth_map_id,predicted_map_id,"
        "map_id_confidence"
    )
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert len(lines) == 5            # 4 frames + 1 header


def test_main_empty_zones_smoke_accuracy_zero_unpopulated(tmp_path, capsys):
    labeled = tmp_path / "labeled"
    _make_labeled_tree(str(labeled), "v2.0", red_count=2, blue_count=2)
    payload = _config_dict(hud_version="v2")   # every zone array empty
    cfg = _write_config(tmp_path, payload)
    output_root = tmp_path / "reports"
    rc = main(["--config", cfg, "--labeled", str(labeled),
               "--output", str(output_root)])
    assert rc == 0
    out = list((output_root / "v2").iterdir())[0]
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert report["hud_version_classifier"]["zones_unpopulated"] is True
    assert report["in_match_classifier"]["zones_unpopulated"] is True
    assert report["map_id_classifier"]["zones_unpopulated"] is True
    summary = (out / "summary.md").read_text(encoding="utf-8")
    assert "zones unpopulated" in summary
    assert "ERROR" not in capsys.readouterr().err


# ===========================================================================
# CLI guards
# ===========================================================================


def _min_cfg(tmp_path):
    return _write_config(tmp_path, _config_dict())


def test_main_negative_limit_argparse_errors(tmp_path):
    labeled = tmp_path / "labeled"
    (labeled / "v2.0").mkdir(parents=True)
    with pytest.raises(SystemExit):
        main(["--config", _min_cfg(tmp_path), "--labeled", str(labeled),
              "--limit", "-1"])


def test_main_zero_ref_height_argparse_errors(tmp_path):
    labeled = tmp_path / "labeled"
    (labeled / "v2.0").mkdir(parents=True)
    with pytest.raises(SystemExit):
        main(["--config", _min_cfg(tmp_path), "--labeled", str(labeled),
              "--ref-height", "0"])


def test_main_hud_threshold_out_of_range_errors(tmp_path):
    labeled = tmp_path / "labeled"
    (labeled / "v2.0").mkdir(parents=True)
    with pytest.raises(SystemExit):
        main(["--config", _min_cfg(tmp_path), "--labeled", str(labeled),
              "--hud-version-threshold", "1.5"])


def test_main_in_match_threshold_out_of_range_errors(tmp_path):
    labeled = tmp_path / "labeled"
    (labeled / "v2.0").mkdir(parents=True)
    with pytest.raises(SystemExit):
        main(["--config", _min_cfg(tmp_path), "--labeled", str(labeled),
              "--in-match-threshold", "-0.1"])


def test_main_map_threshold_out_of_range_errors(tmp_path):
    labeled = tmp_path / "labeled"
    (labeled / "v2.0").mkdir(parents=True)
    with pytest.raises(SystemExit):
        main(["--config", _min_cfg(tmp_path), "--labeled", str(labeled),
              "--map-threshold", "2.0"])


def test_main_nonexistent_config_errors(tmp_path):
    labeled = tmp_path / "labeled"
    (labeled / "v2.0").mkdir(parents=True)
    with pytest.raises(SystemExit):
        main(["--config", str(tmp_path / "nope.json"),
              "--labeled", str(labeled)])


def test_main_missing_labeled_errors(tmp_path):
    with pytest.raises(SystemExit):
        main(["--config", _min_cfg(tmp_path),
              "--labeled", str(tmp_path / "no_such_dir")])


# ===========================================================================
# iter_labeled_frames
# ===========================================================================


def test_iter_labeled_frames_respects_limit_and_yields_hud_dir(tmp_path):
    labeled = tmp_path / "labeled"
    _make_labeled_tree(str(labeled), "v2.0", red_count=5, blue_count=5)
    results = list(iter_labeled_frames(str(labeled), limit_per_class=2))
    assert all(len(r) == 4 for r in results)        # (path, hud_dir, folder, bgr)
    hud_dirs = {r[1] for r in results}
    assert hud_dirs == {"v2.0"}
    folders = [r[2] for r in results]
    assert folders.count("lobby") == 2
    assert folders.count("artefact") == 2


def test_iter_labeled_frames_scans_all_v_dirs(tmp_path):
    labeled = tmp_path / "labeled"
    _make_labeled_tree(str(labeled), "v1.0", red_count=1, blue_count=1)
    _make_labeled_tree(str(labeled), "v2.0", red_count=1, blue_count=1)
    results = list(iter_labeled_frames(str(labeled)))
    assert {r[1] for r in results} == {"v1.0", "v2.0"}


def test_iter_labeled_frames_missing_root_returns_empty(tmp_path):
    assert list(iter_labeled_frames(str(tmp_path / "absent"))) == []
