"""Unit tests for map_config_emitter.py (Story 9.9a, post Scope Adjustment #2).

Covers:
- `_detect_schema_version` — v1 (configs wrapper present), v2 (game_state_zones
  or flat minimap_identification), edge cases (empty config, None values, both
  v1 and v2 markers present).
- `_build_v1_output` — assembles the flattened HUD V1 shape; preserves
  weight/weight_override; coerces types defensively.
- `_build_v2_output` — assembles the HUD V2 shape; coerces legacy zone dicts;
  drops weight/weight_override; map iteration in MAP_LABELS canonical order.
- `_validate_against_schema` — accepts valid v1/v2; rejects unknown fields,
  missing schema_version, mixed v1+v2 shape, HSV out-of-range values.
- `emit()` — end-to-end pipeline against synthetic v1 and v2 configs; atomic
  refusal on schema violation (no file written).

All synthetic — no real video, no labeled dataset.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from tools import map_config_emitter as emitter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_v1_zone(zone_id: str = "zone_0", h_center: int = 100) -> dict:
    return {
        "id": zone_id, "x": 10, "y": 20, "width": 30, "height": 40,
        "hsv": {"h_center": h_center, "h_tol": 5, "s_center": 50, "s_tol": 10,
                "v_center": 60, "v_tol": 15},
        "min_ratio": 0.3, "weight": 0.75, "weight_override": False,
    }


def _v1_input_config() -> dict:
    """Synthetic config.yaml with the legacy HUD V1 minimap_identification.configs[0] shape."""
    return {
        "reference_resolution": {"width": 1920, "height": 1080},
        "minimap_identification": {
            "configs": [{
                "id": "test",
                "identification_threshold": 0.6,
                "roi": {"name": "minimap", "x": 0, "y": 0, "width": 450, "height": 400},
                "maps": {
                    "artefact": {"zones": [_make_v1_zone("zone_0", 159), _make_v1_zone("zone_2", 157)]},
                    "atlantis": {"zones": [_make_v1_zone("zone_8", 163)]},
                },
            }],
        },
    }


def _v2_input_config() -> dict:
    """Synthetic config.yaml with the HUD V2 flat shape + game_state_zones cascade."""
    zone = lambda nm, h_center: {
        "name": nm, "x": 10, "y": 20, "width": 30, "height": 40,
        "hsv": {"h_center": h_center, "h_tol": 5, "s_center": 50,
                "s_tol": 10, "v_center": 60, "v_tol": 15},
        "min_ratio": 0.3,
    }
    return {
        "reference_resolution": {"width": 1920, "height": 1080},
        "game_state_zones": {
            "lobby": [zone("zone_0", 100)],
            "in_match": [],
            "score": [zone("zone_1", 200)],
            "transition": [zone("zone_2", 300)],
        },
        "minimap_identification": {
            "artefact": [zone("z_a", 150)],
            "atlantis": [zone("z_b", 250)],
        },
    }


# ---------------------------------------------------------------------------
# _detect_schema_version
# ---------------------------------------------------------------------------


class TestDetectSchemaVersion:
    def test_empty_config_returns_1(self):
        assert emitter._detect_schema_version({}) == 1

    def test_legacy_configs_wrapper_returns_1(self):
        assert emitter._detect_schema_version(_v1_input_config()) == 1

    def test_minimap_identification_none_returns_1(self):
        assert emitter._detect_schema_version({"minimap_identification": None}) == 1

    def test_game_state_zones_present_returns_2(self):
        assert emitter._detect_schema_version({"game_state_zones": {"lobby": [{"name": "z"}]}}) == 2

    def test_empty_game_state_zones_does_not_trigger_v2(self):
        assert emitter._detect_schema_version({"game_state_zones": {}}) == 1

    def test_flat_minimap_identification_with_hsv_zone_returns_2(self):
        cfg = {"minimap_identification": {
            "artefact": [{"name": "z", "x": 1, "y": 1, "width": 1, "height": 1,
                          "hsv": {}, "min_ratio": 0.3}],
        }}
        assert emitter._detect_schema_version(cfg) == 2

    def test_full_v2_config_returns_2(self):
        assert emitter._detect_schema_version(_v2_input_config()) == 2


# ---------------------------------------------------------------------------
# _build_v1_output
# ---------------------------------------------------------------------------


class TestBuildV1Output:
    def test_top_level_shape(self):
        out = emitter._build_v1_output(_v1_input_config())
        assert out["schema_version"] == 1
        assert out["reference_resolution"] == {"width": 1920, "height": 1080}
        assert set(out) == {"schema_version", "reference_resolution", "minimap_identification"}

    def test_configs_wrapper_flattened(self):
        out = emitter._build_v1_output(_v1_input_config())
        mid = out["minimap_identification"]
        assert "configs" not in mid          # flattened
        assert mid["id"] == "test"
        assert mid["identification_threshold"] == 0.6
        assert mid["roi"] == {"name": "minimap", "x": 0, "y": 0, "width": 450, "height": 400}

    def test_zones_preserved_with_weight_fields(self):
        out = emitter._build_v1_output(_v1_input_config())
        zones = out["minimap_identification"]["maps"]["artefact"]["zones"]
        assert len(zones) == 2
        z = zones[0]
        assert z["id"] == "zone_0"
        assert z["weight"] == 0.75
        assert z["weight_override"] is False
        assert z["hsv"]["h_center"] == 159

    def test_missing_configs_raises_value_error(self):
        with pytest.raises(ValueError, match="configs"):
            emitter._build_v1_output({"reference_resolution": {"width": 1, "height": 1},
                                       "minimap_identification": {}})


# ---------------------------------------------------------------------------
# _build_v2_output
# ---------------------------------------------------------------------------


class TestBuildV2Output:
    def test_top_level_shape(self):
        out = emitter._build_v2_output(_v2_input_config())
        assert out["schema_version"] == 2
        assert set(out) == {"schema_version", "reference_resolution", "game_state_zones", "maps"}
        assert set(out["game_state_zones"]) == {"lobby", "in_match", "score", "transition"}

    def test_in_match_present_even_when_input_empty(self):
        out = emitter._build_v2_output(_v2_input_config())
        assert out["game_state_zones"]["in_match"] == []

    def test_maps_iterate_in_map_labels_order(self):
        from tools.frame_labeler import MAP_LABELS
        out = emitter._build_v2_output(_v2_input_config())
        ordered = [m for m in MAP_LABELS if m in out["maps"]]
        assert list(out["maps"].keys()) == ordered

    def test_legacy_id_renamed_to_name(self):
        cfg = _v2_input_config()
        cfg["minimap_identification"]["artefact"][0] = {
            **cfg["minimap_identification"]["artefact"][0],
            "id": "legacy_id",
        }
        del cfg["minimap_identification"]["artefact"][0]["name"]
        out = emitter._build_v2_output(cfg)
        assert out["maps"]["artefact"][0]["name"] == "legacy_id"

    def test_weight_and_weight_override_dropped(self):
        cfg = _v2_input_config()
        cfg["minimap_identification"]["artefact"][0]["weight"] = 0.75
        cfg["minimap_identification"]["artefact"][0]["weight_override"] = False
        out = emitter._build_v2_output(cfg)
        assert "weight" not in out["maps"]["artefact"][0]
        assert "weight_override" not in out["maps"]["artefact"][0]


# ---------------------------------------------------------------------------
# _validate_against_schema
# ---------------------------------------------------------------------------


def _valid_v1_output():
    return emitter._build_v1_output(_v1_input_config())


def _valid_v2_output():
    return emitter._build_v2_output(_v2_input_config())


class TestJsonschemaValidationGate:
    def test_valid_v1_passes(self):
        emitter._validate_against_schema(_valid_v1_output())

    def test_valid_v2_passes(self):
        emitter._validate_against_schema(_valid_v2_output())

    def test_extra_unknown_top_level_field_rejected(self):
        out = _valid_v1_output()
        out["wat_is_this"] = "extra"
        with pytest.raises(jsonschema.exceptions.ValidationError):
            emitter._validate_against_schema(out)

    def test_missing_schema_version_rejected(self):
        out = _valid_v1_output()
        del out["schema_version"]
        with pytest.raises(jsonschema.exceptions.ValidationError):
            emitter._validate_against_schema(out)

    def test_v1_shape_with_schema_version_2_rejected(self):
        out = _valid_v1_output()
        out["schema_version"] = 2
        with pytest.raises(jsonschema.exceptions.ValidationError):
            emitter._validate_against_schema(out)

    def test_v1_zone_missing_weight_rejected(self):
        out = _valid_v1_output()
        zones = out["minimap_identification"]["maps"]["artefact"]["zones"]
        del zones[0]["weight"]
        with pytest.raises(jsonschema.exceptions.ValidationError):
            emitter._validate_against_schema(out)

    def test_v2_zone_with_extra_weight_rejected(self):
        out = _valid_v2_output()
        out["maps"]["artefact"][0]["weight"] = 0.5
        with pytest.raises(jsonschema.exceptions.ValidationError):
            emitter._validate_against_schema(out)

    def test_hsv_h_center_out_of_range_rejected(self):
        out = _valid_v2_output()
        out["maps"]["artefact"][0]["hsv"]["h_center"] = 720
        with pytest.raises(jsonschema.exceptions.ValidationError):
            emitter._validate_against_schema(out)


# ---------------------------------------------------------------------------
# emit() end-to-end
# ---------------------------------------------------------------------------


class TestEmit:
    def test_v1_emit_writes_correct_file(self, tmp_path):
        emitter.emit(_v1_input_config(), str(tmp_path))
        out = json.loads((tmp_path / "map_config.json").read_text())
        assert out["schema_version"] == 1
        assert out["minimap_identification"]["id"] == "test"
        assert out["minimap_identification"]["maps"]["artefact"]["zones"][0]["weight"] == 0.75
        # Validates against the live schema (the gate is wired up).
        emitter._validate_against_schema(out)

    def test_v2_emit_writes_correct_file(self, tmp_path):
        emitter.emit(_v2_input_config(), str(tmp_path))
        out = json.loads((tmp_path / "map_config.json").read_text())
        assert out["schema_version"] == 2
        assert set(out["game_state_zones"]) == {"lobby", "in_match", "score", "transition"}
        assert "weight" not in out["maps"]["artefact"][0]
        emitter._validate_against_schema(out)

    def test_v1_emit_uses_v1_path_when_detected(self, tmp_path):
        emitter.emit(_v1_input_config(), str(tmp_path))
        out = json.loads((tmp_path / "map_config.json").read_text())
        assert out["schema_version"] == 1

    def test_v2_emit_uses_v2_path_when_detected(self, tmp_path):
        emitter.emit(_v2_input_config(), str(tmp_path))
        out = json.loads((tmp_path / "map_config.json").read_text())
        assert out["schema_version"] == 2

    def test_invalid_dict_aborts_before_write(self, tmp_path):
        """Atomic guarantee: validation failure → sys.exit(1) + no file."""
        bad = _v2_input_config()
        bad["minimap_identification"]["artefact"][0]["hsv"]["h_center"] = 9999
        with pytest.raises(SystemExit):
            emitter.emit(bad, str(tmp_path))
        assert not (tmp_path / "map_config.json").exists()

    def test_first_key_is_schema_version(self, tmp_path):
        """Keep the discriminator first for readable diffs."""
        emitter.emit(_v1_input_config(), str(tmp_path))
        out = json.loads((tmp_path / "map_config.json").read_text())
        assert list(out.keys())[0] == "schema_version"


# ---------------------------------------------------------------------------
# Smoke against the live config.yaml — validates the shipped detector tuning
# round-trips cleanly through the new emit + validation pipeline.
# ---------------------------------------------------------------------------


class TestLiveConfigSmoke:
    """The repo's apps/tooling/config/config.yaml is the live HUD V1 detector
    tuning. Smoke-test that the emitter produces a schema-valid v1 map_config.json
    from it (regression lock against accidental yaml drift)."""

    def test_live_config_emits_valid_v1(self, tmp_path):
        from utils.config import load_config
        config_path = Path(__file__).resolve().parents[1] / "config" / "config.yaml"
        config = load_config(str(config_path))
        out = emitter.emit(config, str(tmp_path))
        assert out["schema_version"] == 1
        emitter._validate_against_schema(out)
        # Sanity: the live config has 10 maps and ~50 zones.
        n_maps = len(out["minimap_identification"]["maps"])
        assert n_maps >= 10
