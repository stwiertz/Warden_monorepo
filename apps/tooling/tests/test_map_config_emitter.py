"""Unit tests for map_config_emitter.py (Story 9.9c — unified schema).

Covers:
- `_load_fragments` — all four fragment files present + valid; missing file
  raises FileNotFoundError; malformed JSON raises json.JSONDecodeError.
- `_assemble_output` — output has all 7 required top-level keys with
  `schema_version: 1` first; empty zone arrays preserved; map iteration order
  preserved from the input fragment.
- `_validate_against_schema` — accepts the unified shape; rejects missing /
  unknown top-level fields, out-of-enum `schema_version` / `hud_version`,
  negative `score_screen_duration_ms`, out-of-range HSV, missing Zone field,
  wrong-type `weight_override`.
- `emit()` — end-to-end with synthetic v1 / v2 fragments writes
  `map_config.<hud_version>.json`; atomic refusal on schema violation;
  missing zones-dir exits before any I/O; first written key is
  `schema_version`.

All synthetic — no real video, no labeled dataset, no `apps/tooling/config/config.yaml`.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from tools import map_config_emitter as emitter


# ---------------------------------------------------------------------------
# Fragment-building helpers
# ---------------------------------------------------------------------------


def _make_zone(
    zone_id: str = "zone_0",
    *,
    h_center: int = 100,
    weight: float = 1.0,
    weight_override: float | None = None,
) -> dict:
    return {
        "id": zone_id,
        "x": 10,
        "y": 20,
        "width": 30,
        "height": 40,
        "hsv": {
            "h_center": h_center,
            "h_tol": 5,
            "s_center": 50,
            "s_tol": 10,
            "v_center": 60,
            "v_tol": 15,
        },
        "min_ratio": 0.3,
        "weight": weight,
        "weight_override": weight_override,
    }


def _make_manifest(
    hud_version: str = "v2",
    score_screen_duration_ms: int = 12000,
    *,
    width: int = 1920,
    height: int = 1080,
) -> dict:
    return {
        "hud_version": hud_version,
        "score_screen_duration_ms": score_screen_duration_ms,
        "reference_resolution": {"width": width, "height": height},
    }


def _make_minimap(maps_dict: dict[str, list[dict]] | None = None) -> dict:
    if maps_dict is None:
        maps_dict = {"artefact": [_make_zone("artefact_z0", h_center=159)]}
    return {
        "id": "test",
        "identification_threshold": 0.6,
        "roi": {"name": "minimap", "x": 0, "y": 0, "width": 450, "height": 400},
        "maps": {slug: {"zones": zones} for slug, zones in maps_dict.items()},
    }


def _write_fragments(
    tmp_path: Path,
    *,
    manifest: dict | None = None,
    hud_version_detection: list | None = None,
    in_match_detection: list | None = None,
    minimap_identification: dict | None = None,
) -> Path:
    zones_dir = tmp_path / "zones"
    zones_dir.mkdir(parents=True, exist_ok=True)

    fragments = {
        "manifest": manifest if manifest is not None else _make_manifest(),
        "hud_version_detection": (
            hud_version_detection
            if hud_version_detection is not None
            else [_make_zone("hud_z0", h_center=200)]
        ),
        "in_match_detection": (
            in_match_detection
            if in_match_detection is not None
            else [_make_zone("inmatch_z0", h_center=300)]
        ),
        "minimap_identification": (
            minimap_identification
            if minimap_identification is not None
            else _make_minimap()
        ),
    }

    for name, content in fragments.items():
        (zones_dir / f"{name}.json").write_text(
            json.dumps(content, indent=2), encoding="utf-8"
        )
    return zones_dir


def _valid_output(**overrides) -> dict:
    """Helper: build a known-valid output via _assemble_output then apply
    test-case-specific mutations. Negative-test cases mutate the dict in
    place after calling this."""
    zones_dir = overrides.pop("zones_dir", None)
    if zones_dir is None:
        # Build fragments in memory without touching disk.
        fragments = {
            "manifest": _make_manifest(),
            "hud_version_detection": [_make_zone("hud_z0", h_center=200)],
            "in_match_detection": [_make_zone("inmatch_z0", h_center=300)],
            "minimap_identification": _make_minimap(),
        }
        return emitter._assemble_output(fragments)
    fragments = emitter._load_fragments(zones_dir)
    return emitter._assemble_output(fragments)


# ---------------------------------------------------------------------------
# _load_fragments
# ---------------------------------------------------------------------------


class TestLoadFragments:
    def test_all_four_files_present_returns_dict_with_four_keys(self, tmp_path):
        zones_dir = _write_fragments(tmp_path)
        out = emitter._load_fragments(zones_dir)
        assert set(out) == {
            "manifest",
            "hud_version_detection",
            "in_match_detection",
            "minimap_identification",
        }
        assert out["manifest"]["hud_version"] == "v2"
        assert isinstance(out["hud_version_detection"], list)
        assert isinstance(out["in_match_detection"], list)
        assert isinstance(out["minimap_identification"], dict)

    def test_missing_manifest_raises_file_not_found(self, tmp_path):
        zones_dir = _write_fragments(tmp_path)
        (zones_dir / "manifest.json").unlink()
        with pytest.raises(FileNotFoundError, match="manifest.json"):
            emitter._load_fragments(zones_dir)

    def test_missing_hud_version_detection_raises_file_not_found(self, tmp_path):
        zones_dir = _write_fragments(tmp_path)
        (zones_dir / "hud_version_detection.json").unlink()
        with pytest.raises(FileNotFoundError, match="hud_version_detection.json"):
            emitter._load_fragments(zones_dir)

    def test_malformed_json_raises_value_error_with_path(self, tmp_path):
        zones_dir = _write_fragments(tmp_path)
        (zones_dir / "in_match_detection.json").write_text(
            "not valid json {{{", encoding="utf-8"
        )
        with pytest.raises(ValueError, match="in_match_detection.json"):
            emitter._load_fragments(zones_dir)

    def test_utf8_bom_in_fragment_tolerated(self, tmp_path):
        zones_dir = _write_fragments(tmp_path)
        bom_content = "﻿" + json.dumps(_make_manifest(), indent=2)
        (zones_dir / "manifest.json").write_text(bom_content, encoding="utf-8")
        out = emitter._load_fragments(zones_dir)
        assert out["manifest"]["hud_version"] == "v2"


# ---------------------------------------------------------------------------
# _assemble_output
# ---------------------------------------------------------------------------


class TestAssembleOutput:
    def test_output_has_seven_required_keys_with_schema_version_first(self):
        out = _valid_output()
        assert list(out.keys()) == [
            "schema_version",
            "reference_resolution",
            "hud_version",
            "score_screen_duration_ms",
            "hud_version_detection",
            "in_match_detection",
            "minimap_identification",
        ]
        assert out["schema_version"] == 1

    def test_empty_hud_version_detection_preserved_not_omitted(self):
        fragments = {
            "manifest": _make_manifest(),
            "hud_version_detection": [],
            "in_match_detection": [],
            "minimap_identification": _make_minimap(),
        }
        out = emitter._assemble_output(fragments)
        assert out["hud_version_detection"] == []
        assert out["in_match_detection"] == []
        assert "hud_version_detection" in out
        assert "in_match_detection" in out

    def test_map_iteration_order_matches_input(self):
        ordered_maps = {
            "zeta_map": [_make_zone("z0", h_center=10)],
            "alpha_map": [_make_zone("z1", h_center=20)],
            "mu_map": [_make_zone("z2", h_center=30)],
        }
        fragments = {
            "manifest": _make_manifest(),
            "hud_version_detection": [],
            "in_match_detection": [],
            "minimap_identification": _make_minimap(ordered_maps),
        }
        out = emitter._assemble_output(fragments)
        assert list(out["minimap_identification"]["maps"].keys()) == [
            "zeta_map",
            "alpha_map",
            "mu_map",
        ]

    @pytest.mark.parametrize(
        "missing_manifest_key",
        ["hud_version", "score_screen_duration_ms", "reference_resolution"],
    )
    def test_manifest_missing_required_key_raises_clean_value_error(
        self, missing_manifest_key
    ):
        manifest = _make_manifest()
        del manifest[missing_manifest_key]
        fragments = {
            "manifest": manifest,
            "hud_version_detection": [],
            "in_match_detection": [],
            "minimap_identification": _make_minimap(),
        }
        with pytest.raises(ValueError, match=missing_manifest_key):
            emitter._assemble_output(fragments)


# ---------------------------------------------------------------------------
# _validate_against_schema
# ---------------------------------------------------------------------------


class TestJsonschemaValidationGate:
    def test_valid_output_passes(self):
        emitter._validate_against_schema(_valid_output())

    def test_missing_schema_version_rejected(self):
        out = _valid_output()
        del out["schema_version"]
        with pytest.raises(jsonschema.exceptions.ValidationError):
            emitter._validate_against_schema(out)

    def test_schema_version_2_rejected(self):
        out = _valid_output()
        out["schema_version"] = 2
        with pytest.raises(jsonschema.exceptions.ValidationError):
            emitter._validate_against_schema(out)

    def test_extra_unknown_top_level_field_rejected(self):
        out = _valid_output()
        out["wat_is_this"] = "extra"
        with pytest.raises(jsonschema.exceptions.ValidationError):
            emitter._validate_against_schema(out)

    def test_hud_version_v3_rejected(self):
        out = _valid_output()
        out["hud_version"] = "v3"
        with pytest.raises(jsonschema.exceptions.ValidationError):
            emitter._validate_against_schema(out)

    def test_negative_score_screen_duration_rejected(self):
        out = _valid_output()
        out["score_screen_duration_ms"] = -1
        with pytest.raises(jsonschema.exceptions.ValidationError):
            emitter._validate_against_schema(out)

    def test_hsv_h_center_out_of_range_rejected(self):
        out = _valid_output()
        out["hud_version_detection"][0]["hsv"]["h_center"] = 720
        with pytest.raises(jsonschema.exceptions.ValidationError):
            emitter._validate_against_schema(out)

    def test_zone_missing_weight_override_rejected(self):
        out = _valid_output()
        del out["hud_version_detection"][0]["weight_override"]
        with pytest.raises(jsonschema.exceptions.ValidationError):
            emitter._validate_against_schema(out)

    def test_zone_weight_override_string_rejected(self):
        out = _valid_output()
        out["hud_version_detection"][0]["weight_override"] = "auto"
        with pytest.raises(jsonschema.exceptions.ValidationError):
            emitter._validate_against_schema(out)

    def test_zone_weight_override_null_accepted(self):
        out = _valid_output()
        out["hud_version_detection"][0]["weight_override"] = None
        emitter._validate_against_schema(out)

    def test_zone_weight_override_number_accepted(self):
        out = _valid_output()
        out["hud_version_detection"][0]["weight_override"] = 2.5
        emitter._validate_against_schema(out)

    def test_zone_weight_override_boolean_rejected(self):
        # Pre-9.9c V1 zones used boolean weight_override; the unified schema
        # restricts to {number, null}. This test locks the documented behavior
        # change so a regression to boolean accept is caught.
        out = _valid_output()
        out["hud_version_detection"][0]["weight_override"] = False
        with pytest.raises(jsonschema.exceptions.ValidationError):
            emitter._validate_against_schema(out)

    @pytest.mark.parametrize(
        "missing_top_level_key",
        [
            "hud_version",
            "reference_resolution",
            "score_screen_duration_ms",
            "hud_version_detection",
            "in_match_detection",
            "minimap_identification",
        ],
    )
    def test_missing_required_top_level_field_rejected(self, missing_top_level_key):
        out = _valid_output()
        del out[missing_top_level_key]
        with pytest.raises(jsonschema.exceptions.ValidationError):
            emitter._validate_against_schema(out)

    def test_zone_extra_unknown_field_rejected(self):
        out = _valid_output()
        out["hud_version_detection"][0]["color"] = "red"
        with pytest.raises(jsonschema.exceptions.ValidationError):
            emitter._validate_against_schema(out)

    def test_map_slug_uppercase_rejected(self):
        out = _valid_output()
        out["minimap_identification"]["maps"] = {
            "Artefact": {"zones": [_make_zone("zone_0", h_center=159)]}
        }
        with pytest.raises(jsonschema.exceptions.ValidationError):
            emitter._validate_against_schema(out)

    def test_map_slug_hyphen_rejected(self):
        out = _valid_output()
        out["minimap_identification"]["maps"] = {
            "the-cliff": {"zones": [_make_zone("zone_0", h_center=159)]}
        }
        with pytest.raises(jsonschema.exceptions.ValidationError):
            emitter._validate_against_schema(out)


# ---------------------------------------------------------------------------
# emit() end-to-end
# ---------------------------------------------------------------------------


class TestEmit:
    def test_v1_fragments_write_v1_filename(self, tmp_path):
        zones_dir = _write_fragments(tmp_path, manifest=_make_manifest("v1", 11000))
        output_dir = tmp_path / "out"
        emitter.emit(zones_dir, output_dir)
        target = output_dir / "map_config.v1.json"
        assert target.is_file()
        data = json.loads(target.read_text(encoding="utf-8"))
        assert data["hud_version"] == "v1"
        assert data["score_screen_duration_ms"] == 11000

    def test_v2_fragments_write_v2_filename(self, tmp_path):
        zones_dir = _write_fragments(tmp_path, manifest=_make_manifest("v2", 12000))
        output_dir = tmp_path / "out"
        emitter.emit(zones_dir, output_dir)
        target = output_dir / "map_config.v2.json"
        assert target.is_file()
        data = json.loads(target.read_text(encoding="utf-8"))
        assert data["hud_version"] == "v2"
        assert data["score_screen_duration_ms"] == 12000

    def test_schema_invalid_fragment_aborts_before_write(self, tmp_path):
        bad_hud = [_make_zone("hud_z0", h_center=9999)]
        zones_dir = _write_fragments(tmp_path, hud_version_detection=bad_hud)
        output_dir = tmp_path / "out"
        with pytest.raises(SystemExit) as ei:
            emitter.emit(zones_dir, output_dir)
        assert ei.value.code == 1
        # Atomic refusal: validation runs BEFORE any os.makedirs, so the
        # output dir must not exist at all (not just be empty). A future
        # refactor moving os.makedirs ahead of validation must fail this.
        assert not output_dir.exists()

    def test_missing_zones_dir_exits_before_io(self, tmp_path, monkeypatch):
        bogus = tmp_path / "does_not_exist"
        output_dir = tmp_path / "out"
        monkeypatch.setattr(
            "sys.argv",
            [
                "map_config_emitter.py",
                "--zones-dir",
                str(bogus),
                "--output-dir",
                str(output_dir),
            ],
        )
        with pytest.raises(SystemExit) as ei:
            emitter.main()
        assert ei.value.code == 1
        assert not output_dir.exists()

    def test_first_key_in_written_file_is_schema_version(self, tmp_path):
        zones_dir = _write_fragments(tmp_path, manifest=_make_manifest("v1", 11000))
        output_dir = tmp_path / "out"
        emitter.emit(zones_dir, output_dir)
        raw = (output_dir / "map_config.v1.json").read_text(encoding="utf-8")
        # json.dump preserves insertion order; the raw text must start with
        # "schema_version" as the first key.
        first_key_idx = raw.find('"schema_version"')
        # Guard against the pathological "schema_version absent" case: find()
        # returns -1, which would make every subsequent `> first_key_idx`
        # assertion trivially pass.
        assert first_key_idx >= 0, '"schema_version" key must appear in the written file'
        # Confirm no other key appears before it.
        for other in (
            '"reference_resolution"',
            '"hud_version"',
            '"score_screen_duration_ms"',
            '"hud_version_detection"',
            '"in_match_detection"',
            '"minimap_identification"',
        ):
            assert raw.find(other) > first_key_idx
