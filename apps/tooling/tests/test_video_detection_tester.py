"""Pure-logic unit tests for Tool 11 (video_test) — no Tk, no real video, no
ffmpeg, no new deps; all ``tmp_path``-based; ``cv2.VideoCapture`` mocked.

Covers (AC10):
* state-machine truth table — all AC7 edge cases (start-mid-match,
  EOF-open-span, zero-duration score window, rising-edge-during-score,
  single-frame blip);
* ``_load_config`` — valid unified config → ZoneSpec lists per classifier;
  missing required field → clean ``ValueError``; empty-zone scaffold tolerated
  (AC8);
* the unified ``Zone`` → ``ZoneSpec`` mapping incl. ``min_ratio`` carried
  explicitly (NOT the ``HsvBand`` 0.3 default);
* weighted map-ID aggregation incl. ``weight_override`` null vs number;
* stride / timestamp math (fps-derived default + override + POS_MSEC fallback);
* ``results.json`` determinism (serialize twice → byte-identical);
* the reused-symbol contract pin (synthetic frame + known band through
  ``zone_fires_on_frame`` → expected ``(fired, ratio)``; argmax tie-break).
"""

from __future__ import annotations

import json
import os

import cv2
import numpy as np
import pytest

from tools.common.zones import HsvBand, Rect
from tools.roi_detection_tester import (
    ZoneSpec,
    _argmax_with_threshold,
    _resize_to_ref,
    zone_fires_on_frame,
)
from tools import video_test
from tools.video_test import (
    _FrameRecord,
    _MapZone,
    Span,
    _aggregate_span_map,
    _build_results,
    _classify_in_match,
    _frame_source,
    _load_config,
    _ordered_map_slugs,
    _run_state_machine,
    _score_maps,
    _write_results,
    _zone_to_spec,
)


# ===========================================================================
# Helpers
# ===========================================================================


def _solid_bgr(h: int, w: int, color_bgr: tuple[int, int, int]) -> np.ndarray:
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    arr[:, :] = color_bgr
    return arr


def _hsv_user_for_bgr(color_bgr: tuple[int, int, int]) -> tuple[int, int, int]:
    px = np.array([[list(color_bgr)]], dtype=np.uint8)
    hsv = cv2.cvtColor(px, cv2.COLOR_BGR2HSV)[0, 0]
    return (
        int(round(float(hsv[0]) * 2.0)),
        int(round(float(hsv[1]) * 100.0 / 255.0)),
        int(round(float(hsv[2]) * 100.0 / 255.0)),
    )


def _zone_dict(
    zid: str,
    color_bgr: tuple[int, int, int] = (0, 0, 255),
    *,
    x: int = 0,
    y: int = 0,
    width: int = 4,
    height: int = 4,
    min_ratio: float = 0.3,
    weight: float = 1.0,
    weight_override=None,
) -> dict:
    h, s, v = _hsv_user_for_bgr(color_bgr)
    return {
        "id": zid,
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "hsv": {
            "h_center": h,
            "h_tol": 15,
            "s_center": s,
            "s_tol": 40,
            "v_center": v,
            "v_tol": 40,
        },
        "min_ratio": min_ratio,
        "weight": weight,
        "weight_override": weight_override,
    }


def _valid_config(
    *,
    hud_version: str = "v2",
    hud_zones=None,
    in_match_zones=None,
    maps=None,
    score_screen_duration_ms: int = 5000,
    identification_threshold: float = 0.5,
) -> dict:
    return {
        "schema_version": 1,
        "reference_resolution": {"width": 8, "height": 8},
        "hud_version": hud_version,
        "score_screen_duration_ms": score_screen_duration_ms,
        "hud_version_detection": hud_zones if hud_zones is not None else [],
        "in_match_detection": (
            in_match_zones if in_match_zones is not None else []
        ),
        "minimap_identification": {
            "id": "test",
            "identification_threshold": identification_threshold,
            "roi": {"name": "mm", "x": 0, "y": 0, "width": 8, "height": 8},
            "maps": maps if maps is not None else {},
        },
    }


def _write_config(tmp_path, cfg: dict) -> str:
    p = tmp_path / "map_config.v2.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    return str(p)


class _FakeCapture:
    """Minimal ``cv2.VideoCapture`` stand-in yielding synthetic BGR frames."""

    def __init__(self, frames, *, fps=30.0, opened=True, pos_msec=None):
        self._frames = frames
        self._i = 0
        self._fps = fps
        self._opened = opened
        self._pos = pos_msec  # list aligned to decode index, or None

    def isOpened(self):  # noqa: N802 (cv2 API name)
        return self._opened

    def get(self, prop):
        if prop == cv2.CAP_PROP_FPS:
            return self._fps
        if prop == cv2.CAP_PROP_POS_MSEC:
            j = self._i - 1
            if self._pos is not None and 0 <= j < len(self._pos):
                return self._pos[j]
            return 0.0
        return 0.0

    def read(self):
        if self._i >= len(self._frames):
            return False, None
        frame = self._frames[self._i]
        self._i += 1
        return True, frame

    def release(self):
        pass


def _patch_capture(monkeypatch, capture):
    monkeypatch.setattr(
        video_test.cv2, "VideoCapture", lambda *_a, **_k: capture
    )


# ===========================================================================
# State machine — AC7 truth table
# ===========================================================================


def _sm(frames, dur):
    return _run_state_machine(frames, dur)


def test_state_machine_basic_rising_and_falling():
    # not_in_match -> in_match -> score_screen -> not_in_match
    frames = [
        (0, 0, False),
        (1, 100, True),
        (2, 200, True),
        (3, 300, False),     # falling edge -> score_screen (dur=500)
        (4, 400, False),     # still within score window
        (5, 900, False),     # 900-300 >= 500 -> not_in_match
    ]
    states, spans = _sm(frames, 500)
    assert states == [
        "not_in_match",
        "in_match",
        "in_match",
        "score_screen",
        "score_screen",
        "not_in_match",
    ]
    assert spans == [(1, 2)]


def test_state_machine_starts_mid_match():
    frames = [(0, 0, True), (1, 100, True), (2, 200, False)]
    states, spans = _sm(frames, 1000)
    assert states[0] == "in_match"
    assert spans == [(0, 1)]


def test_state_machine_in_match_at_eof_no_score_screen():
    frames = [(0, 0, False), (1, 100, True), (2, 200, True)]
    states, spans = _sm(frames, 1000)
    assert states == ["not_in_match", "in_match", "in_match"]
    assert spans == [(1, 2)]
    assert "score_screen" not in states


def test_state_machine_zero_duration_score_window():
    frames = [(0, 0, True), (1, 100, False), (2, 200, False)]
    states, spans = _sm(frames, 0)
    # falling-edge frame is immediately not_in_match — zero score frames
    assert states == ["in_match", "not_in_match", "not_in_match"]
    assert "score_screen" not in states
    assert spans == [(0, 0)]


def test_state_machine_rising_edge_during_score_window():
    frames = [
        (0, 0, True),
        (1, 100, False),     # falling edge -> score_screen (dur=10000)
        (2, 200, True),      # rising edge during score -> in_match, new span
        (3, 300, False),     # falling again -> score_screen
        (4, 400, False),
    ]
    states, spans = _sm(frames, 10000)
    assert states == [
        "in_match",
        "score_screen",
        "in_match",
        "score_screen",
        "score_screen",
    ]
    assert spans == [(0, 0), (2, 2)]


def test_state_machine_single_frame_blip_is_valid_span():
    frames = [(0, 0, False), (1, 100, True), (2, 200, False), (3, 300, False)]
    states, spans = _sm(frames, 0)
    assert spans == [(1, 1)]


def test_state_machine_empty_input():
    states, spans = _sm([], 1000)
    assert states == []
    assert spans == []


# ===========================================================================
# _load_config + Zone -> ZoneSpec mapping
# ===========================================================================


def test_load_config_valid_splits_by_classifier(tmp_path):
    cfg = _valid_config(
        hud_zones=[_zone_dict("hud_a")],
        in_match_zones=[_zone_dict("im_a"), _zone_dict("im_b")],
        maps={"the_cliff": {"zones": [_zone_dict("cliff_a", weight=2.0)]}},
    )
    parsed = _load_config(_write_config(tmp_path, cfg))
    assert parsed.hud_version == "v2"
    assert parsed.reference_resolution == {"width": 8, "height": 8}
    assert parsed.score_screen_duration_ms == 5000
    assert parsed.identification_threshold == 0.5
    assert [z.name for z in parsed.hud_zones] == ["hud_a"]
    assert [z.name for z in parsed.in_match_zones] == ["im_a", "im_b"]
    assert isinstance(parsed.hud_zones[0], ZoneSpec)
    cliff = parsed.map_zones["the_cliff"]
    assert len(cliff) == 1
    assert isinstance(cliff[0], _MapZone)
    assert cliff[0].weight == 2.0
    assert cliff[0].weight_override is None


def test_load_config_missing_top_level_key_clean_valueerror(tmp_path):
    cfg = _valid_config()
    del cfg["score_screen_duration_ms"]
    with pytest.raises(ValueError, match="missing required keys"):
        _load_config(_write_config(tmp_path, cfg))


def test_load_config_empty_zone_scaffold_tolerated_with_notes(tmp_path):
    # AC8 — fully unpopulated config must parse, not crash, and surface notes.
    parsed = _load_config(_write_config(tmp_path, _valid_config()))
    assert parsed.hud_zones == []
    assert parsed.in_match_zones == []
    assert parsed.map_zones == {}
    joined = " ".join(parsed.notes)
    assert "hud_version_detection unpopulated" in joined
    assert "in_match_detection unpopulated" in joined
    assert "minimap_identification.maps unpopulated" in joined


def test_load_config_bad_zone_missing_field_clean_valueerror(tmp_path):
    bad = _zone_dict("bad")
    del bad["min_ratio"]
    cfg = _valid_config(in_match_zones=[bad])
    with pytest.raises(ValueError, match="missing required keys"):
        _load_config(_write_config(tmp_path, cfg))


def test_zone_to_spec_carries_min_ratio_explicitly_not_default():
    raw = _zone_dict("z", min_ratio=0.77)
    spec = _zone_to_spec(raw, "in_match", "game_state")
    assert spec.name == "z"
    assert spec.owning_class == "in_match"
    assert spec.kind == "game_state"
    # Must be the zone's authored min_ratio, NOT HsvBand's 0.3 dataclass default.
    assert spec.band.min_ratio == pytest.approx(0.77)
    assert HsvBand.min_ratio == 0.3  # the trap default we must not rely on


def test_zone_to_spec_rect_and_band_mapping():
    raw = _zone_dict("z", (0, 0, 255), x=3, y=5, width=7, height=9)
    spec = _zone_to_spec(raw, "the_cliff", "map")
    assert (spec.rect.x, spec.rect.y, spec.rect.width, spec.rect.height) == (3, 5, 7, 9)
    assert isinstance(spec.rect, Rect)
    assert isinstance(spec.band, HsvBand)


# ===========================================================================
# Weighted map-ID aggregation (AC7) — weight_override null vs number
# ===========================================================================


def test_score_maps_weight_override_null_uses_weight():
    frame = _solid_bgr(8, 8, (0, 0, 255))
    spec = _zone_to_spec(_zone_dict("z", (0, 0, 255), width=8, height=8), "m", "map")
    mz = _MapZone(spec=spec, weight=3.0, weight_override=None)
    scores = _score_maps(frame, {"m": [mz]})
    # zone fires ratio 1.0 -> contrib = 1.0 * 3.0; total_w = 3.0 -> score 1.0
    assert scores["m"] == pytest.approx(1.0)


def test_score_maps_weight_override_number_replaces_weight():
    frame = _solid_bgr(8, 8, (0, 0, 255))
    fire = _zone_to_spec(_zone_dict("fire", (0, 0, 255), width=8, height=8), "m", "map")
    miss = _zone_to_spec(
        _zone_dict("miss", (0, 255, 0), width=8, height=8), "m", "map"
    )
    # fire: eff weight via override = 1.0 ; miss: eff weight = weight = 3.0
    z_fire = _MapZone(spec=fire, weight=99.0, weight_override=1.0)
    z_miss = _MapZone(spec=miss, weight=3.0, weight_override=None)
    scores = _score_maps(frame, {"m": [z_fire, z_miss]})
    # contrib = 1.0(ratio)*1.0(eff)  ; total_w = 1.0 + 3.0 = 4.0 -> 0.25
    assert scores["m"] == pytest.approx(0.25)


def test_score_maps_empty_map_skipped():
    assert _score_maps(_solid_bgr(8, 8, (0, 0, 255)), {"m": []}) == {}


def test_aggregate_span_map_modal_and_confidence():
    recs = [
        _FrameRecord(0, 0, True, "the_cliff", {"the_cliff": 0.8, "helios": 0.1}),
        _FrameRecord(1, 100, True, "the_cliff", {"the_cliff": 0.6, "helios": 0.2}),
        _FrameRecord(2, 200, True, "helios", {"the_cliff": 0.1, "helios": 0.9}),
    ]
    map_id, conf = _aggregate_span_map(recs, ["helios", "the_cliff"])
    assert map_id == "the_cliff"
    assert conf == pytest.approx(round((0.8 + 0.6 + 0.1) / 3, 6))


def test_aggregate_span_map_all_unknown():
    recs = [_FrameRecord(0, 0, True, "unknown", {})]
    assert _aggregate_span_map(recs, []) == ("unknown", 0.0)


def test_aggregate_span_map_tie_broken_by_mean_confidence():
    recs = [
        _FrameRecord(0, 0, True, "a", {"a": 0.4, "b": 0.9}),
        _FrameRecord(1, 1, True, "b", {"a": 0.4, "b": 0.9}),
    ]
    # 1 vote each -> tie -> higher mean score wins (b: 0.9 > a: 0.4)
    map_id, conf = _aggregate_span_map(recs, ["a", "b"])
    assert map_id == "b"
    assert conf == pytest.approx(0.9)


def test_aggregate_span_map_residual_tie_broken_by_canonical_order():
    # Equal vote count AND equal mean score for x/y -> residual tie must break
    # by ordered_slugs position (deterministic across configs), NOT by
    # Counter insertion order. y precedes x in canonical order here.
    recs = [
        _FrameRecord(0, 0, True, "x", {"x": 0.5, "y": 0.5}),
        _FrameRecord(1, 1, True, "y", {"x": 0.5, "y": 0.5}),
    ]
    # Same records, two configs presenting the maps in opposite order:
    a = _aggregate_span_map(recs, ["y", "x"])
    b = _aggregate_span_map(recs, ["y", "x"])
    assert a == b == ("y", pytest.approx(0.5))
    # Flip the canonical order -> winner flips deterministically to x.
    assert _aggregate_span_map(recs, ["x", "y"]) == ("x", pytest.approx(0.5))


def test_ordered_map_slugs_uses_map_labels_order():
    # helios + the_cliff are both MAP_LABELS; order follows MAP_LABELS not dict.
    mz = lambda: [_MapZone(spec=None, weight=1.0, weight_override=None)]  # noqa: E731
    # Dict insertion order is the_cliff-before-helios; MAP_LABELS order is the
    # reverse (helios idx 6 < the_cliff idx 12). The function MUST follow
    # MAP_LABELS, not dict insertion order.
    ordered = _ordered_map_slugs({"the_cliff": mz(), "helios": mz(), "zz_x": mz()})
    assert ordered.index("helios") < ordered.index("the_cliff")
    # Both MAP_LABELS slugs precede any non-MAP_LABELS slug...
    assert ordered.index("the_cliff") < ordered.index("zz_x")
    # ...and the non-MAP_LABELS slug is still appended (config insertion order).
    assert ordered == ["helios", "the_cliff", "zz_x"]


# ===========================================================================
# Reused-symbol contract pin (frozen against a future 9.14 Tool-9 refit)
# ===========================================================================


def test_zone_fires_on_frame_contract_pin():
    frame = _solid_bgr(8, 8, (0, 0, 255))  # pure red
    h, s, v = _hsv_user_for_bgr((0, 0, 255))
    band = HsvBand(h_center=h, h_tol=10, s_center=s, s_tol=30,
                   v_center=v, v_tol=30, min_ratio=0.3)
    spec = ZoneSpec(name="z", owning_class="m", kind="map",
                    rect=Rect(0, 0, 8, 8), band=band)
    fired, ratio = zone_fires_on_frame(spec, frame)
    assert fired is True
    assert ratio == pytest.approx(1.0)

    # A band that cannot match the frame -> no fire, ratio 0.0.
    off = HsvBand(h_center=h, h_tol=2, s_center=0, s_tol=1,
                  v_center=0, v_tol=1, min_ratio=0.3)
    spec_off = ZoneSpec(name="z", owning_class="m", kind="map",
                        rect=Rect(0, 0, 8, 8), band=off)
    fired_off, ratio_off = zone_fires_on_frame(spec_off, frame)
    assert fired_off is False
    assert ratio_off == pytest.approx(0.0)


def test_argmax_with_threshold_contract_pin():
    # empty -> unknown
    assert _argmax_with_threshold(
        {}, threshold=0.5, ordered_classes=[], zone_counts={}
    ) == ("unknown", 0.0)
    # below threshold -> unknown
    pred, score = _argmax_with_threshold(
        {"a": 0.2}, threshold=0.5, ordered_classes=["a"], zone_counts={"a": 1}
    )
    assert pred == "unknown"
    # tie -> more zones wins
    pred2, _ = _argmax_with_threshold(
        {"a": 0.8, "b": 0.8},
        threshold=0.5,
        ordered_classes=["a", "b"],
        zone_counts={"a": 1, "b": 5},
    )
    assert pred2 == "b"


def test_resize_to_ref_contract_pin():
    # AC6 lists _resize_to_ref among the three reused symbols whose contract
    # must be pinned so a future 9.14 Tool-9 refit cannot silently drift it.
    frame = _solid_bgr(200, 100, (0, 0, 255))  # h=200, w=100 (BGR red)
    out = _resize_to_ref(frame, 100)
    assert out.shape[0] == 100                       # resized to ref height
    assert out.shape[1] == 50                        # aspect-preserved (100/200)
    assert out.shape[2] == 3
    # No-op when already at the reference height (same object/values).
    same = _resize_to_ref(frame, 200)
    assert same.shape[:2] == (200, 100)


def test_default_config_path_picks_newest_by_version_then_mtime(tmp_path,
                                                                monkeypatch):
    cfg_dir = tmp_path / "output" / "map_configs"
    cfg_dir.mkdir(parents=True)
    # v2 written first, v10 second: natural-version order must pick v10 even
    # though lexicographic "v10" < "v2".
    (cfg_dir / "map_config.v2.json").write_text("{}", encoding="utf-8")
    (cfg_dir / "map_config.v10.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(video_test, "_tooling_root", lambda: str(tmp_path))
    picked = video_test._default_config_path()
    assert picked is not None
    assert os.path.basename(picked) == "map_config.v10.json"


def test_default_config_path_none_when_dir_or_glob_empty(tmp_path,
                                                         monkeypatch):
    monkeypatch.setattr(video_test, "_tooling_root", lambda: str(tmp_path))
    assert video_test._default_config_path() is None          # dir absent
    (tmp_path / "output" / "map_configs").mkdir(parents=True)
    assert video_test._default_config_path() is None          # glob empty


def test_classify_in_match_empty_zones_is_false():
    assert _classify_in_match(_solid_bgr(8, 8, (0, 0, 255)), []) is False


def test_classify_in_match_fires_when_group_clears_gate():
    frame = _solid_bgr(8, 8, (0, 0, 255))
    z = _zone_to_spec(_zone_dict("z", (0, 0, 255), width=8, height=8), "in_match",
                      "game_state")
    assert _classify_in_match(frame, [z]) is True


# ===========================================================================
# Frame extraction — stride / timestamp math (cv2.VideoCapture mocked)
# ===========================================================================


def test_frame_source_default_stride_from_fps(monkeypatch):
    frames = [_solid_bgr(4, 4, (0, 0, 0)) for _ in range(90)]
    _patch_capture(monkeypatch, _FakeCapture(frames, fps=30.0))
    stride, it = _frame_source("dummy.mp4", None)
    assert stride == 30
    kept = list(it)
    assert [idx for idx, _ts, _f in kept] == [0, 30, 60]
    # POS_MSEC unavailable (0.0) -> fps fallback: idx / fps * 1000
    assert [ts for _i, ts, _f in kept] == [0, 1000, 2000]


def test_frame_source_stride_override(monkeypatch):
    frames = [_solid_bgr(4, 4, (0, 0, 0)) for _ in range(10)]
    _patch_capture(monkeypatch, _FakeCapture(frames, fps=24.0))
    stride, it = _frame_source("dummy.mp4", 5)
    assert stride == 5
    assert [idx for idx, _ts, _f in list(it)] == [0, 5]


def test_frame_source_pos_msec_used_when_available(monkeypatch):
    frames = [_solid_bgr(4, 4, (0, 0, 0)) for _ in range(3)]
    cap = _FakeCapture(frames, fps=30.0, pos_msec=[33.4, 66.7, 100.9])
    _patch_capture(monkeypatch, cap)
    stride, it = _frame_source("dummy.mp4", 1)
    kept = list(it)
    assert [ts for _i, ts, _f in kept] == [33, 67, 101]  # round(POS_MSEC)


def test_frame_source_not_opened_raises(monkeypatch):
    _patch_capture(monkeypatch, _FakeCapture([], opened=False))
    with pytest.raises(video_test.VideoOpenError):
        _frame_source("dummy.mp4", None)


def test_frame_source_skips_corrupt_decode(monkeypatch):
    frames = [_solid_bgr(4, 4, (0, 0, 0)), None, _solid_bgr(4, 4, (0, 0, 0))]
    _patch_capture(monkeypatch, _FakeCapture(frames, fps=30.0))
    stride, it = _frame_source("dummy.mp4", 1)
    # index 1 is a None decode -> skipped; the read after it (idx 2) is kept.
    idxs = [idx for idx, _ts, _f in list(it)]
    assert idxs == [0, 2]


# ===========================================================================
# results.json determinism (REL-005 / AC9)
# ===========================================================================


def _sample_results() -> dict:
    recs = [
        _FrameRecord(0, 0, True, "the_cliff", {"the_cliff": 0.812345678}),
        _FrameRecord(30, 1000, False, "unknown", {}),
    ]
    states = ["in_match", "not_in_match"]
    spans = [Span(0, 0, "the_cliff", 0.812345678)]
    return _build_results(
        hud_version="v2",
        video="/abs/path/EVA_capture.mp4",
        stride=30,
        config="/abs/path/map_config.v2.json",
        records=recs,
        states=states,
        spans=spans,
    )


def test_results_shape_and_basenames():
    r = _sample_results()
    assert list(r.keys()) == [
        "hud_version",
        "video",
        "stride",
        "config",
        "frames",
        "matches",
    ]
    assert r["video"] == "EVA_capture.mp4"
    assert r["config"] == "map_config.v2.json"
    assert r["frames"][0] == {
        "frame_idx": 0,
        "timestamp_ms": 0,
        "state": "in_match",
    }
    assert r["matches"][0]["map_id"] == "the_cliff"
    # confidence rounded to 6 dp
    assert r["matches"][0]["confidence"] == pytest.approx(0.812346)


def test_results_byte_identical_on_reserialize(tmp_path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    _write_results(_sample_results(), str(a))
    _write_results(_sample_results(), str(b))
    assert a.read_bytes() == b.read_bytes()
    assert a.read_text(encoding="utf-8").endswith("}\n")  # trailing newline


# ===========================================================================
# main() end-to-end smoke (mocked capture; empty-zone config per AC8)
# ===========================================================================


def test_main_empty_zone_config_smoke(tmp_path, monkeypatch):
    cfg_path = _write_config(tmp_path, _valid_config())  # fully unpopulated
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"not-a-real-video")  # existence check only; capture mocked
    frames = [_solid_bgr(8, 8, (10, 20, 30)) for _ in range(20)]
    _patch_capture(monkeypatch, _FakeCapture(frames, fps=10.0))
    out = tmp_path / "results.json"

    rc = video_test.main(
        [str(video), "--config", cfg_path, "--output", str(out)]
    )
    assert rc == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["hud_version"] == "v2"
    assert payload["stride"] == 10  # round(fps=10.0)
    # in_match_detection empty -> every frame not_in_match -> no matches
    assert all(f["state"] == "not_in_match" for f in payload["frames"])
    assert payload["matches"] == []


def test_main_missing_video_returns_1(tmp_path, capsys):
    cfg_path = _write_config(tmp_path, _valid_config())
    rc = video_test.main(["no_such_video.mp4", "--config", cfg_path])
    assert rc == 1
    assert "video not found" in capsys.readouterr().err


def test_main_missing_config_returns_1(tmp_path, capsys):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"x")
    rc = video_test.main([str(video), "--config", str(tmp_path / "nope.json")])
    assert rc == 1
    assert "config not found" in capsys.readouterr().err


# ===========================================================================
# Code-review regression pins (2026-05-17 /bmad-code-review patches P1-P8)
# ===========================================================================


def test_load_config_negative_weight_clean_valueerror(tmp_path):
    # P3: negative weight / weight_override must be a clean ValueError, not a
    # silent total_w<=0 -> score 0.0 masking a misconfigured map.
    cfg = _valid_config(
        maps={"the_cliff": {"zones": [_zone_dict("z", weight_override=-2.0)]}}
    )
    p = _write_config(tmp_path, cfg)
    with pytest.raises(ValueError, match="non-negative"):
        _load_config(p)


def test_load_config_negative_score_duration_emits_note(tmp_path):
    # P4a: a negative score_screen_duration_ms is tolerated (behaves like 0)
    # but must be surfaced as an AC8-style note rather than passing silently.
    cfg = _valid_config(score_screen_duration_ms=-500)
    parsed = _load_config(_write_config(tmp_path, cfg))
    assert parsed.score_screen_duration_ms == -500
    assert any("score_screen_duration_ms is negative" in n for n in parsed.notes)


def test_main_null_present_config_value_clean_error_no_traceback(
    tmp_path, capsys
):
    # P1: a key that is present but null (int(None)/float(None)) must be a
    # clean CLI error (rc 1), never an uncaught TypeError traceback.
    cfg = _valid_config()
    cfg["score_screen_duration_ms"] = None
    cfg_path = _write_config(tmp_path, cfg)
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"x")
    rc = video_test.main([str(video), "--config", cfg_path])
    assert rc == 1
    assert "cannot load config" in capsys.readouterr().err


def test_main_threshold_out_of_range_returns_1(tmp_path, capsys):
    # P4b: --threshold outside [0,1] is rejected with a clean error.
    cfg_path = _write_config(tmp_path, _valid_config())
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"x")
    rc = video_test.main(
        [str(video), "--config", cfg_path, "--threshold", "1.5"]
    )
    assert rc == 1
    assert "--threshold must be in" in capsys.readouterr().err


def test_frame_source_nan_fps_falls_back_to_30(monkeypatch):
    # P2: a NaN CAP_PROP_FPS must not blow up int(round(fps)); fall back to 30.
    frames = [_solid_bgr(4, 4, (0, 0, 0)) for _ in range(31)]
    _patch_capture(monkeypatch, _FakeCapture(frames, fps=float("nan")))
    stride, it = _frame_source("dummy.mp4", None)
    assert stride == 30
    assert [idx for idx, _ts, _f in list(it)] == [0, 30]


def test_frame_source_non_monotonic_pos_msec_clamped(monkeypatch):
    # P8: a backwards-jittering POS_MSEC must be clamped non-decreasing so the
    # score-screen exit can't stall.
    frames = [_solid_bgr(4, 4, (0, 0, 0)) for _ in range(3)]
    cap = _FakeCapture(frames, fps=30.0, pos_msec=[100.0, 50.0, 120.0])
    _patch_capture(monkeypatch, cap)
    _stride, it = _frame_source("dummy.mp4", 1)
    ts = [t for _i, t, _f in list(it)]
    assert ts == [100, 100, 120]  # second frame clamped up from 50 -> 100


# ===========================================================================
# Re-review patches (2026-05-17, second /bmad-code-review pass) — P1–P5, P8
# ===========================================================================


def test_load_config_nan_weight_clean_valueerror(tmp_path):
    # P1: NaN weight bypasses the `< 0` guard (float('nan') < 0 is False) and
    # would silently make total_w / every map score NaN. Must be a clean
    # ValueError, never a silent NaN.
    cfg = _valid_config(
        maps={"the_cliff": {"zones": [_zone_dict("z", weight=float("nan"))]}}
    )
    with pytest.raises(ValueError, match="finite and non-negative"):
        _load_config(_write_config(tmp_path, cfg))


def test_load_config_identification_threshold_out_of_range_clean_valueerror(
    tmp_path,
):
    # P2: the config-side identification_threshold is now range-validated too
    # (symmetrical to the CLI --threshold guard) — out-of-range no longer
    # silently makes every map predict `unknown`.
    cfg = _valid_config(identification_threshold=1.5)
    with pytest.raises(ValueError, match="identification_threshold must be in"):
        _load_config(_write_config(tmp_path, cfg))


def test_load_config_nonpositive_reference_resolution_clean_valueerror(
    tmp_path,
):
    # P3: a 0/negative reference_resolution height would drive a degenerate
    # _resize_to_ref and silently mis-detect every zone. Must fail clean.
    cfg = _valid_config()
    cfg["reference_resolution"]["height"] = 0
    with pytest.raises(ValueError, match="must be positive"):
        _load_config(_write_config(tmp_path, cfg))


def test_load_config_min_ratio_out_of_range_clean_valueerror(tmp_path):
    # P4: min_ratio outside [0,1] silently makes a zone never/always fire.
    cfg = _valid_config(in_match_zones=[_zone_dict("z", min_ratio=1.5)])
    with pytest.raises(ValueError, match="min_ratio must be in"):
        _load_config(_write_config(tmp_path, cfg))


def test_load_config_null_array_clean_valueerror_not_raw_typeerror(tmp_path):
    # P5: a present-but-null in_match_detection must raise the documented
    # ValueError ("must be a list"), not a raw `for z in None` TypeError that
    # violates _load_config's contract.
    cfg = _valid_config()
    cfg["in_match_detection"] = None
    with pytest.raises(ValueError, match="in_match_detection must be a list"):
        _load_config(_write_config(tmp_path, cfg))


def test_load_config_maps_not_object_clean_valueerror(tmp_path):
    # P5: minimap_identification.maps as a list (not an object) must raise a
    # clean ValueError, not a raw AttributeError from `.items()`.
    cfg = _valid_config()
    cfg["minimap_identification"]["maps"] = []
    with pytest.raises(ValueError, match="maps must be an object"):
        _load_config(_write_config(tmp_path, cfg))


def test_degradation_notes_are_ascii(tmp_path):
    # P8: degradation NOTE strings are printed to a Windows cp1252 console;
    # a non-ASCII separator renders as a mojibake box. They must be ASCII.
    cfg = _valid_config(score_screen_duration_ms=-1)
    parsed = _load_config(_write_config(tmp_path, cfg))
    assert parsed.notes  # unpopulated hud/in_match/maps + negative duration
    for note in parsed.notes:
        assert note.isascii(), f"non-ASCII in NOTE: {note!r}"
