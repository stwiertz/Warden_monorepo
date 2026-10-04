"""Unit tests for detection_config_envelope.py (Story 1.13 AC11).

Covers:
- the shipped bundled configs build into a schema-valid envelope whose
  `config_json` is the file text verbatim and whose `sha256` is over the bytes;
- map order survives (non-alphabetical fixture);
- atomic refusal: filename HUD outside the enum, filename/content HUD mismatch,
  schema-invalid config, invalid JSON, BOM, empty dir, bad revision;
- the envelope schema's KNOWN `configs` keys equal the map-config `hud_version`
  enum (they are two copies of one list), and unknown keys are tolerated when
  their value is a well-formed entry (forward compat, code-review D1);
- the committed mobile fixture envelope is what this tool builds from the
  committed tiny source config (the cross-language sha256 parity anchor).

No credentials, no network.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import jsonschema
import pytest

from tools import detection_config_envelope as env

REPO = Path(__file__).resolve().parents[3]
BUNDLED_DIR = REPO / "apps" / "mobile" / "assets" / "detection"
FIXTURES = REPO / "apps" / "mobile" / "src" / "features" / "video-processing" / "__tests__" / "fixtures"
FIXTURE_SOURCE = FIXTURES / "overlay-source"
FIXTURE_ENVELOPE = FIXTURES / "overlay-envelope.json"


def _copy_fixture_config(tmp_path: Path, name: str = "map_config.v2.json") -> Path:
    dst = tmp_path / name
    shutil.copyfile(FIXTURE_SOURCE / "map_config.v2.json", dst)
    return dst


class TestBuildFromShippedConfigs:
    def test_bundled_configs_build_and_validate(self):
        envelope = env.build_envelope(BUNDLED_DIR, 2)
        assert envelope["envelope_version"] == 1
        assert envelope["revision"] == 2
        assert list(envelope["configs"]) == ["v2"]
        schema = json.loads(env.ENVELOPE_SCHEMA_PATH.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(envelope)

    def test_config_json_is_the_file_text_verbatim_and_sha_is_over_the_bytes(self):
        envelope = env.build_envelope(BUNDLED_DIR, 2)
        data = (BUNDLED_DIR / "map_config.v2.json").read_bytes()
        entry = envelope["configs"]["v2"]
        assert entry["config_json"] == data.decode("utf-8")
        assert entry["sha256"] == hashlib.sha256(data).hexdigest()
        assert hashlib.sha256(entry["config_json"].encode("utf-8")).hexdigest() == entry["sha256"]

    def test_map_order_survives_in_the_text(self, tmp_path):
        _copy_fixture_config(tmp_path)
        envelope = env.build_envelope(tmp_path, 3)
        config = json.loads(envelope["configs"]["v2"]["config_json"])
        assert list(config["minimap_identification"]["maps"]) == ["zeta_map", "alpha_map", "mu_map"]


class TestAtomicRefusal:
    def test_filename_hud_outside_enum_rejected(self, tmp_path):
        _copy_fixture_config(tmp_path, "map_config.v3.json")
        with pytest.raises(env.EnvelopeBuildError, match="not in the map-config hud_version enum"):
            env.build_envelope(tmp_path, 2)

    def test_traversal_shaped_filename_rejected(self, tmp_path):
        _copy_fixture_config(tmp_path, "map_config....json")
        with pytest.raises(env.EnvelopeBuildError, match="enum"):
            env.build_envelope(tmp_path, 2)

    def test_filename_content_hud_mismatch_rejected(self, tmp_path):
        _copy_fixture_config(tmp_path, "map_config.v1.json")  # content says v2
        with pytest.raises(env.EnvelopeBuildError, match="does not match content hud_version"):
            env.build_envelope(tmp_path, 2)

    def test_schema_invalid_config_rejected(self, tmp_path):
        path = _copy_fixture_config(tmp_path)
        config = json.loads(path.read_text(encoding="utf-8"))
        config["schema_version"] = 2
        path.write_text(json.dumps(config), encoding="utf-8")
        with pytest.raises(env.EnvelopeBuildError, match="map-config.schema.json"):
            env.build_envelope(tmp_path, 2)

    def test_invalid_json_rejected(self, tmp_path):
        (tmp_path / "map_config.v2.json").write_text("{not json", encoding="utf-8")
        with pytest.raises(env.EnvelopeBuildError, match="invalid JSON"):
            env.build_envelope(tmp_path, 2)

    def test_bom_rejected(self, tmp_path):
        data = (FIXTURE_SOURCE / "map_config.v2.json").read_bytes()
        (tmp_path / "map_config.v2.json").write_bytes(b"\xef\xbb\xbf" + data)
        with pytest.raises(env.EnvelopeBuildError, match="BOM"):
            env.build_envelope(tmp_path, 2)

    def test_duplicate_key_rejected(self, tmp_path):
        text = (FIXTURE_SOURCE / "map_config.v2.json").read_text(encoding="utf-8")
        dup = text.replace('"zeta_map":', '"alpha_map": {}, "zeta_map":', 1)
        assert dup != text
        (tmp_path / "map_config.v2.json").write_text(dup, encoding="utf-8")
        with pytest.raises(env.EnvelopeBuildError, match="duplicate object key 'alpha_map'"):
            env.build_envelope(tmp_path, 2)

    def test_nan_rejected(self, tmp_path):
        (tmp_path / "map_config.v2.json").write_text('{"schema_version": NaN}', encoding="utf-8")
        with pytest.raises(env.EnvelopeBuildError, match="NaN"):
            env.build_envelope(tmp_path, 2)

    def test_missing_schema_is_a_clean_error(self, tmp_path):
        _copy_fixture_config(tmp_path)
        with pytest.raises(env.EnvelopeBuildError, match="cannot load schema"):
            env.build_envelope(tmp_path, 2, map_config_schema_path=tmp_path / "nope.json")

    def test_unreadable_config_path_is_a_clean_error(self, tmp_path):
        # A directory named like a config must exit 1 cleanly, not traceback.
        (tmp_path / "map_config.v2.json").mkdir()
        with pytest.raises(env.EnvelopeBuildError, match="cannot be read"):
            env.build_envelope(tmp_path, 2)

    def test_empty_dir_rejected(self, tmp_path):
        with pytest.raises(env.EnvelopeBuildError, match="no map_config"):
            env.build_envelope(tmp_path, 2)

    def test_missing_dir_rejected(self, tmp_path):
        with pytest.raises(env.EnvelopeBuildError, match="does not exist"):
            env.build_envelope(tmp_path / "nope", 2)

    @pytest.mark.parametrize("revision", [0, -1, True])
    def test_bad_revision_rejected(self, tmp_path, revision):
        _copy_fixture_config(tmp_path)
        with pytest.raises(env.EnvelopeBuildError, match="revision"):
            env.build_envelope(tmp_path, revision)

    def test_cli_failure_writes_nothing(self, tmp_path, capsys):
        out = tmp_path / "out" / "latest.json"
        (tmp_path / "map_config.v2.json").write_text("{not json", encoding="utf-8")
        assert env.main(["--configs-dir", str(tmp_path), "--revision", "2", "--out", str(out)]) == 1
        assert not out.exists()
        assert "invalid JSON" in capsys.readouterr().err


class TestCli:
    def test_cli_writes_a_valid_envelope(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        _copy_fixture_config(src)
        out = tmp_path / "out" / "latest.json"
        assert env.main(["--configs-dir", str(src), "--revision", "4", "--out", str(out)]) == 0
        written = json.loads(out.read_text(encoding="utf-8"))
        assert written["revision"] == 4
        assert written == env.build_envelope(src, 4)

    def test_write_is_atomic_and_leaves_no_temp_file(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        _copy_fixture_config(src)
        out = tmp_path / "out" / "latest.json"
        out.parent.mkdir()
        out.write_text("stale", encoding="utf-8")
        assert env.main(["--configs-dir", str(src), "--revision", "4", "--out", str(out)]) == 0
        assert json.loads(out.read_text(encoding="utf-8"))["revision"] == 4
        assert sorted(p.name for p in out.parent.iterdir()) == ["latest.json"]

    def test_revision_is_required(self):
        with pytest.raises(SystemExit):
            env.main([])


class TestContractsAgree:
    def test_envelope_config_keys_equal_the_map_config_hud_enum(self):
        envelope_schema = json.loads(env.ENVELOPE_SCHEMA_PATH.read_text(encoding="utf-8"))
        map_schema = json.loads(env.MAP_CONFIG_SCHEMA_PATH.read_text(encoding="utf-8"))
        configs = envelope_schema["properties"]["configs"]
        assert sorted(configs["properties"]) == sorted(map_schema["properties"]["hud_version"]["enum"])
        # D1 (code review 2026-10-04): unknown HUD keys pass the envelope when
        # their value is a ConfigEntry; the client drops them one by one.
        assert configs["additionalProperties"] == {"$ref": "#/$defs/ConfigEntry"}
        assert configs["minProperties"] == 1

    def test_unknown_hud_key_with_a_wellformed_entry_passes_the_envelope(self):
        schema = json.loads(env.ENVELOPE_SCHEMA_PATH.read_text(encoding="utf-8"))
        entry = {"config_json": "{}", "sha256": "0" * 64}
        jsonschema.Draft202012Validator(schema).validate(
            {"envelope_version": 1, "revision": 2, "configs": {"v2": entry, "v3": entry}}
        )

    def test_unknown_hud_key_with_a_malformed_entry_is_rejected(self):
        schema = json.loads(env.ENVELOPE_SCHEMA_PATH.read_text(encoding="utf-8"))
        with pytest.raises(jsonschema.exceptions.ValidationError):
            jsonschema.Draft202012Validator(schema).validate(
                {"envelope_version": 1, "revision": 2, "configs": {"v3": {"config_json": "{}"}}}
            )

    def test_nested_object_config_is_not_an_envelope(self):
        # What a naive upload of the bare config file would produce.
        schema = json.loads(env.ENVELOPE_SCHEMA_PATH.read_text(encoding="utf-8"))
        bare = json.loads((FIXTURE_SOURCE / "map_config.v2.json").read_text(encoding="utf-8"))
        with pytest.raises(jsonschema.exceptions.ValidationError):
            jsonschema.Draft202012Validator(schema).validate(bare)
        nested = {"envelope_version": 1, "revision": 2, "configs": {"v2": bare}}
        with pytest.raises(jsonschema.exceptions.ValidationError):
            jsonschema.Draft202012Validator(schema).validate(nested)


class TestCommittedMobileFixture:
    def test_fixture_envelope_is_what_this_tool_builds(self):
        committed = json.loads(FIXTURE_ENVELOPE.read_text(encoding="utf-8"))
        rebuilt = env.build_envelope(FIXTURE_SOURCE, committed["revision"])
        # Compare modulo line endings: a Windows `core.autocrlf` checkout turns
        # the committed LF source into CRLF on disk, which changes the bytes the
        # tool reads (and therefore the sha) without changing the config.
        c_text = committed["configs"]["v2"]["config_json"]
        r_text = rebuilt["configs"]["v2"]["config_json"]
        assert c_text.replace("\r\n", "\n") == r_text.replace("\r\n", "\n")

    def test_fixture_sha_matches_its_own_text(self):
        committed = json.loads(FIXTURE_ENVELOPE.read_text(encoding="utf-8"))
        entry = committed["configs"]["v2"]
        assert hashlib.sha256(entry["config_json"].encode("utf-8")).hexdigest() == entry["sha256"]
        assert "\r" not in entry["config_json"]  # the fixture is LF, independent of checkout
