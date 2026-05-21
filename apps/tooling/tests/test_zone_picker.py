"""Pure-logic unit tests for the zone_picker package (Story 9.12, AC11).

Covers ONLY the Tk-free modules — ``tools.zone_picker.fragments`` and
``tools.zone_picker.variance``. **No tkinter / GUI instantiation** (Tool 6/8/9
precedent; ``conftest.py`` is a sys.path shim only — no fixtures here).
Synthetic ``tmp_path`` / in-memory data only — no real dataset, video, or
``apps/tooling/config.yaml``.

fragments.py:
* load existing (all four present)
* merge-not-clobber (mutate one target, the other three round-trip verbatim)
* schema-valid-empty scaffold
* stable zone ids + MAP_LABELS ordering
* round-trip through the *unchanged* map_config_emitter
  (``_load_fragments`` + ``_assemble_output`` + ``_validate_against_schema``)
* serialize_zone clamps (h_tol overshoot; boolean weight_override → null)

variance.py:
* Welford mean / population-stddev correctness on a synthetic stack
* circular-Hue wrap correctness ({179, 0} → near-zero circular std, not ~90)
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from tools import map_config_emitter as emitter
from tools.common.labels import MAP_LABELS
from tools.common.zones import HsvBand, Rect
from tools.zone_picker import fragments as F
from tools.zone_picker import variance as V


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _manifest(hud_version="v2", dur=12000, w=1920, h=1080):
    return {
        "hud_version": hud_version,
        "score_screen_duration_ms": dur,
        "reference_resolution": {"width": w, "height": h},
    }


def _zone_tuple(h_center=120, weight=1.0, weight_override=None):
    rect = Rect(10, 20, 30, 40)
    band = HsvBand(h_center, 5, 50, 10, 60, 15, 0.3)
    return (rect, band, weight, weight_override)


# ===========================================================================
# fragments.py
# ===========================================================================


class TestScaffold:
    def test_scaffold_empty_is_schema_valid_via_emitter(self):
        frags = F.scaffold_empty(_manifest())
        assembled = emitter._assemble_output(
            {
                "manifest": frags["manifest"],
                "hud_version_detection": frags["hud_version_detection"],
                "in_match_detection": frags["in_match_detection"],
                "minimap_identification": frags["minimap_identification"],
            }
        )
        emitter._validate_against_schema(assembled)  # must not raise

    def test_scaffold_arrays_empty_and_minimap_shaped(self):
        frags = F.scaffold_empty(_manifest())
        assert frags["hud_version_detection"] == []
        assert frags["in_match_detection"] == []
        mm = frags["minimap_identification"]
        assert set(mm) == {"id", "identification_threshold", "roi", "maps"}
        assert mm["maps"] == {}
        assert set(mm["roi"]) == {"name", "x", "y", "width", "height"}


class TestLoadExisting:
    def test_loads_all_four_when_present(self, tmp_path):
        frags = F.scaffold_empty(_manifest("v1", 11000))
        F.set_zone_list(frags, "hud_version_detection", [_zone_tuple()])
        F.write_all(tmp_path, frags)

        loaded = F.load_existing(tmp_path)
        assert loaded["manifest"]["hud_version"] == "v1"
        assert loaded["manifest"]["score_screen_duration_ms"] == 11000
        assert len(loaded["hud_version_detection"]) == 1
        assert loaded["in_match_detection"] == []
        assert loaded["minimap_identification"]["maps"] == {}

    def test_missing_manifest_returns_none_other_scaffolded(self, tmp_path):
        loaded = F.load_existing(tmp_path)  # empty dir
        assert loaded["manifest"] is None
        assert loaded["hud_version_detection"] == []
        assert loaded["in_match_detection"] == []
        assert loaded["minimap_identification"]["maps"] == {}

    def test_malformed_json_raises_value_error_with_path(self, tmp_path):
        (tmp_path / "in_match_detection.json").write_text("not json {{{", encoding="utf-8")
        with pytest.raises(ValueError, match="in_match_detection.json"):
            F.load_existing(tmp_path)

    def test_utf8_bom_tolerated(self, tmp_path):
        frags = F.scaffold_empty(_manifest())
        F.write_all(tmp_path, frags)
        (tmp_path / "manifest.json").write_text(
            "﻿" + json.dumps(_manifest("v1")), encoding="utf-8"
        )
        loaded = F.load_existing(tmp_path)
        assert loaded["manifest"]["hud_version"] == "v1"


class TestMergeNotClobber:
    def test_per_map_write_preserves_other_three_fragments(self, tmp_path):
        # Seed all four with content.
        frags = F.scaffold_empty(_manifest())
        F.set_zone_list(frags, "hud_version_detection", [_zone_tuple(h_center=200)])
        F.set_zone_list(frags, "in_match_detection", [_zone_tuple(h_center=300)])
        F.set_map_zones(frags, "artefact", [_zone_tuple(h_center=159)])
        F.write_all(tmp_path, frags)

        hud_before = (tmp_path / "hud_version_detection.json").read_text("utf-8")
        inmatch_before = (tmp_path / "in_match_detection.json").read_text("utf-8")

        # Simulate a *separate* per-map session: load, touch ONLY one map, save.
        reloaded = F.load_existing(tmp_path)
        F.set_map_zones(reloaded, "bastion", [_zone_tuple(h_center=42)])
        F.write_all(tmp_path, reloaded)

        # The two array fragments must be byte-identical (not wiped).
        assert (tmp_path / "hud_version_detection.json").read_text("utf-8") == hud_before
        assert (tmp_path / "in_match_detection.json").read_text("utf-8") == inmatch_before
        final = F.load_existing(tmp_path)
        assert set(final["minimap_identification"]["maps"]) == {"artefact", "bastion"}


class TestStableIdsAndOrdering:
    def test_zone_ids_are_stable_and_prefixed(self):
        frags = F.scaffold_empty(_manifest())
        F.set_zone_list(frags, "hud_version_detection", [_zone_tuple(), _zone_tuple()])
        F.set_zone_list(frags, "in_match_detection", [_zone_tuple()])
        F.set_map_zones(frags, "the_cliff", [_zone_tuple(), _zone_tuple()])
        assert [z["id"] for z in frags["hud_version_detection"]] == ["hud_z00", "hud_z01"]
        assert [z["id"] for z in frags["in_match_detection"]] == ["inmatch_z00"]
        assert [z["id"] for z in frags["minimap_identification"]["maps"]["the_cliff"]["zones"]] == [
            "the_cliff_z00",
            "the_cliff_z01",
        ]

    def test_maps_written_in_map_labels_order(self, tmp_path):
        frags = F.scaffold_empty(_manifest())
        # Insert deliberately out of MAP_LABELS order.
        for slug in ("the_rock", "artefact", "helios"):
            F.set_map_zones(frags, slug, [_zone_tuple()])
        F.write_all(tmp_path, frags)
        written = json.loads((tmp_path / "minimap_identification.json").read_text("utf-8"))
        keys = list(written["maps"].keys())
        # Order must follow MAP_LABELS, not insertion order.
        assert keys == [s for s in MAP_LABELS if s in ("the_rock", "artefact", "helios")]
        assert keys == ["artefact", "helios", "the_rock"]


class TestEmitterRoundTrip:
    def test_full_populated_fragments_pass_unchanged_emitter(self, tmp_path):
        frags = F.scaffold_empty(_manifest("v2", 9000))
        F.set_zone_list(frags, "hud_version_detection", [_zone_tuple(h_center=200)])
        F.set_zone_list(frags, "in_match_detection", [_zone_tuple(h_center=300)])
        F.set_minimap(
            frags,
            id="test",
            identification_threshold=0.7,
            roi={"name": "minimap", "x": 1500, "y": 50, "width": 400, "height": 380},
        )
        F.set_map_zones(frags, "artefact", [_zone_tuple(h_center=159, weight_override=2.0)])
        F.set_map_zones(frags, "engine", [])  # not-yet-fingerprinted is valid
        F.write_all(tmp_path, frags)

        # Round-trip through the *unchanged* emitter contract surface.
        loaded = emitter._load_fragments(tmp_path)
        assembled = emitter._assemble_output(loaded)
        emitter._validate_against_schema(assembled)  # the real contract gate

        assert assembled["schema_version"] == 1
        assert assembled["hud_version"] == "v2"
        assert assembled["minimap_identification"]["maps"]["artefact"]["zones"][0][
            "weight_override"
        ] == 2.0

    def test_emit_end_to_end_writes_map_config(self, tmp_path):
        frags = F.scaffold_empty(_manifest("v1", 11000))
        F.set_zone_list(frags, "hud_version_detection", [_zone_tuple()])
        F.write_all(tmp_path, frags)
        out_dir = tmp_path / "out"
        emitter.emit(tmp_path, out_dir)
        target = out_dir / "map_config.v1.json"
        assert target.is_file()
        assert json.loads(target.read_text("utf-8"))["hud_version"] == "v1"


class TestSerializeZoneClamps:
    def test_h_tol_overshoot_clamped_to_180(self):
        # The recovered band-seed math can produce h_tol far past the schema's
        # 0..180 — the picker must clamp (the emitter does NO coercion).
        band = HsvBand(120, 500, 50, 200, 60, 200, 0.3)
        z = F.serialize_zone("z0", Rect(0, 0, 5, 5), band, 1.0, None)
        assert z["hsv"]["h_tol"] == 180
        assert z["hsv"]["s_tol"] == 100
        assert z["hsv"]["v_tol"] == 100

    def test_boolean_weight_override_coerced_to_null(self):
        z = F.serialize_zone("z0", Rect(0, 0, 5, 5), HsvBand(1, 1, 1, 1, 1, 1), 1.0, True)
        assert z["weight_override"] is None

    def test_negative_coords_and_zero_size_clamped(self):
        z = F.serialize_zone("z0", Rect(-5, -3, 0, 0), HsvBand(1, 1, 1, 1, 1, 1), -2.0, -1.0)
        assert z["x"] == 0 and z["y"] == 0
        assert z["width"] == 1 and z["height"] == 1
        assert z["weight"] == 0.0
        assert z["weight_override"] == 0.0

    def test_serialized_zone_has_exactly_nine_keys(self):
        z = F.serialize_zone("z0", Rect(1, 2, 3, 4), HsvBand(10, 5, 20, 5, 30, 5), 1.0, None)
        assert set(z) == {
            "id", "x", "y", "width", "height",
            "hsv", "min_ratio", "weight", "weight_override",
        }
        assert set(z["hsv"]) == {
            "h_center", "h_tol", "s_center", "s_tol", "v_center", "v_tol",
        }


# ===========================================================================
# variance.py
# ===========================================================================


class TestWelfordCorrectness:
    def test_class_stats_mean_and_population_stddev_match_numpy(self):
        rng = np.random.default_rng(42)
        frames = [
            rng.integers(0, 256, size=(6, 8, 3), dtype=np.uint8) for _ in range(11)
        ]
        stats = V.class_stats(frames)
        stack = np.stack([f.astype(np.float64) for f in frames], axis=0)

        assert stats.frame_count == 11
        np.testing.assert_allclose(stats.mean_bgr, stack.mean(axis=0), rtol=1e-9, atol=1e-7)
        # Population stddev (ddof=0) — Welford finalize divides M2 by n.
        np.testing.assert_allclose(
            stats.stddev_bgr, stack.std(axis=0), rtol=1e-7, atol=1e-6
        )

    def test_single_frame_has_zero_stddev(self):
        frame = np.full((4, 4, 3), 128, np.uint8)
        stats = V.class_stats([frame])
        assert stats.frame_count == 1
        np.testing.assert_array_equal(stats.stddev_bgr, np.zeros((4, 4, 3)))

    def test_empty_frame_list_raises(self):
        with pytest.raises(ValueError, match="at least one frame"):
            V.class_stats([])


class TestCircularHueWrap:
    def test_hues_179_and_0_give_near_zero_circular_std_not_90(self):
        # OpenCV H 179 = 358°, H 0 = 0° — adjacent reds, ~2° apart. A *linear*
        # stddev would scream ~90 H units; the circular stat must be tiny.
        std = V.circular_std_cv(np.array([179, 0, 179, 0], dtype=np.float64))
        assert std < 2.0, f"circular std should be ~0 for wrapped reds, got {std}"

        linear = float(np.std(np.array([179.0, 0.0, 179.0, 0.0])))
        assert linear > 80.0  # sanity: the naive metric really is ~89.5

    def test_constant_hue_gives_zero_circular_std(self):
        assert V.circular_std_cv(np.full(50, 90.0)) == pytest.approx(0.0, abs=1e-9)

    def test_circular_mean_of_wrapped_reds_is_near_the_wrap(self):
        # Mean of {179, 0} should sit at the wrap (~179.5 ≡ ~0), NOT at ~90.
        mean = V.circular_mean_cv(np.array([179.0, 0.0]))
        assert mean < 1.0 or mean > 179.0

    def test_class_stats_hue_channel_is_circular(self):
        # Two solid-red frames whose OpenCV hue straddles the 0/179 wrap must
        # yield a small std_hsv hue channel, not ~90.
        red_hi = np.zeros((3, 3, 3), np.uint8)
        red_hi[:] = (0, 0, 255)  # BGR pure red -> OpenCV H ~0
        hsv = np.zeros((3, 3, 3), np.uint8)
        hsv[:] = (179, 255, 255)  # OpenCV H 179
        red_lo = __import__("cv2").cvtColor(hsv, __import__("cv2").COLOR_HSV2BGR)
        stats = V.class_stats([red_hi, red_lo, red_hi, red_lo])
        assert float(stats.std_hsv[..., 0].mean()) < 10.0


class TestDeriveBand:
    def test_band_seed_floors_and_returns_user_space(self):
        mean_hsv = np.zeros((10, 10, 3), np.float64)
        mean_hsv[..., 0] = 30.0   # OpenCV H
        mean_hsv[..., 1] = 200.0  # S
        mean_hsv[..., 2] = 180.0  # V
        std_hsv = np.zeros((10, 10, 3), np.float64)  # perfectly stable
        band = V.derive_band_for_rect(Rect(0, 0, 10, 10), mean_hsv, std_hsv)
        # Stable region → tolerances clamp to the floors (user space).
        assert band.h_tol == 10  # _MIN_H_TOL
        assert band.s_tol == 5 and band.v_tol == 5  # _MIN_SV_TOL
        # H center: 30 cv * 2 = 60 user.
        assert band.h_center == 60
        assert isinstance(band.h_center, int)

    def test_empty_rect_returns_floor_band(self):
        band = V.derive_band_for_rect(
            Rect(0, 0, 0, 0), np.zeros((5, 5, 3)), np.zeros((5, 5, 3))
        )
        assert band.h_tol == 10 and band.s_tol == 5 and band.v_tol == 5


class TestEvaluateZoneSet:
    """The no-redraw re-check (Story 9.12 follow-up) — pure aggregate/weight
    math. ``min_ratio`` extremes (0.0 → always fires, 2.0 → never fires) isolate
    the weighting from the HSV ratio so the assertions are deterministic."""

    _MEAN = np.zeros((4, 4, 3), np.uint8)

    def test_empty_zone_set_is_zeroed(self):
        r = V.evaluate_zone_set([], self._MEAN)
        assert r.n_zones == 0 and r.aggregate == 0.0
        assert r.ratios == [] and r.fired == []

    def test_weighted_aggregate_and_fired_flags(self):
        always = HsvBand(0, 360, 50, 100, 50, 100, min_ratio=0.0)  # ratio≥0 → fires
        never = HsvBand(0, 360, 50, 100, 50, 100, min_ratio=2.0)   # ratio<2 → dark
        zones = [
            (Rect(0, 0, 4, 4), always, 1.0, None),  # eff 1.0, fired
            (Rect(0, 0, 4, 4), never, 3.0, None),   # eff 3.0, dark
        ]
        r = V.evaluate_zone_set(zones, self._MEAN)
        assert r.n_zones == 2
        assert r.fired == [True, False]
        assert all(0.0 <= x <= 1.0 for x in r.ratios)
        assert r.aggregate == pytest.approx(1.0 / 4.0)  # 1.0 / (1.0 + 3.0)

    def test_weight_override_supersedes_weight(self):
        always = HsvBand(0, 360, 50, 100, 50, 100, min_ratio=0.0)
        never = HsvBand(0, 360, 50, 100, 50, 100, min_ratio=2.0)
        zones = [
            (Rect(0, 0, 4, 4), always, 1.0, 10.0),  # eff = wo 10.0, fired
            (Rect(0, 0, 4, 4), never, 5.0, None),   # eff = weight 5.0, dark
        ]
        r = V.evaluate_zone_set(zones, self._MEAN)
        assert r.aggregate == pytest.approx(10.0 / 15.0)


class TestZoneDiscrimination:
    """Live positive-VS-negative readout. White (V≈100) positive mean and black
    (V≈0) negative mean with a high-V band separate deterministically without
    HSV hand-math."""

    _WHITE = np.full((4, 4, 3), 255, np.uint8)
    _BLACK = np.zeros((4, 4, 3), np.uint8)
    # Wide H/S, V locked high → matches white, misses black.
    _HIGH_V = HsvBand(0, 180, 0, 100, 100, 10, min_ratio=0.3)

    def test_fires_positive_dark_negative_is_discriminant(self):
        d = V.zone_discrimination(
            Rect(0, 0, 4, 4), self._HIGH_V, self._WHITE, self._BLACK
        )
        assert d.pos_fires and not d.neg_fires
        assert d.discriminant is True
        assert d.pos_ratio == pytest.approx(1.0)
        assert d.neg_ratio == pytest.approx(0.0)

    def test_fires_on_both_is_not_discriminant(self):
        wide_v = HsvBand(0, 180, 0, 100, 50, 100, min_ratio=0.3)  # V any → both fire
        d = V.zone_discrimination(
            Rect(0, 0, 4, 4), wide_v, self._WHITE, self._BLACK
        )
        assert d.pos_fires and d.neg_fires
        assert d.discriminant is False
