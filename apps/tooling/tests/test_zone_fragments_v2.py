"""Regression guard for the committed v2 zone fragments (Story 9.15 follow-up).

Story 9.15 committed `output/zones/v2/*.json` as the **source of truth** and left
`map_config.v2.json` gitignored on the grounds that it is regenerable from them.
That makes the fragments -> config round-trip a load-bearing invariant, and 9.15
deliberately shipped no guard for it (AC0b Option A: "adds no test because it adds
no code" -- but it does add an invariant).

This module is that guard. It re-proves 9.15's AC2 on every run, on any machine:

    committed fragments -> unmodified emitter -> the exact config blessed on
    2026-07-16, whose CPU baseline (hud 0.9805 / in_match 1.0 / map_id 1.0) is
    pinned in the story file.

Unlike the rest of this suite it reads REAL committed data rather than synthetic
fixtures. That is deliberate and it stays hermetic: every input is tracked in git.
9.15's own AC2 could not be re-proven off the author's machine, because its
comparison target (`map_config.v2.json`) is gitignored -- `_EXPECTED_SHA256` below
is that vanished comparison target, reduced to 32 bytes that survive a `git clean`.

The digest is taken over **LF-normalized** bytes. The emitter writes text-mode
(`map_config_emitter.py:145`), so it emits CRLF on Windows (62476 B) and LF on
Linux/macOS (59987 B) from identical fragments. A raw-byte digest would pin the
suite to one platform; normalizing makes the gate portable without a
`.gitattributes` renormalization sweep.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from tools import map_config_emitter as emitter

_TOOLING_ROOT = Path(__file__).resolve().parents[1]
_ZONES_V2 = _TOOLING_ROOT / "output" / "zones" / "v2"

# SHA256 over the LF-normalized emitter output. Pinned 2026-07-16 from the
# fragments committed in e4b9c29, verified byte-identical to the tuned
# `map_config.v2.json` that produced the story's pinned CPU baseline.
_EXPECTED_SHA256 = "eb33f1ee59635a9515606a3f9458e7e31c8c3e333d9f26da83c4c29b10619185"

# Story 9.15 AC3 -- the emitter's own summary line, asserted as structure so a
# drift names what moved instead of only reporting a digest mismatch.
_EXPECTED_HUD_ZONES = 10
_EXPECTED_IN_MATCH_ZONES = 3
_EXPECTED_MAPS = 13
_EXPECTED_MAP_ZONES = 121


def _emit_to(tmp_path: Path) -> tuple[dict, bytes]:
    """Run the unmodified emitter against the committed fragments."""
    output = emitter.emit(_ZONES_V2, tmp_path)
    raw = (tmp_path / "map_config.v2.json").read_bytes()
    return output, raw.replace(b"\r\n", b"\n")


def test_all_four_fragments_are_committed():
    """The emitter hard-requires all four exact names; a missing one is a
    FileNotFoundError at runtime, not a test failure somewhere downstream."""
    missing = [
        name
        for name in ("manifest", "hud_version_detection", "in_match_detection",
                     "minimap_identification")
        if not (_ZONES_V2 / f"{name}.json").is_file()
    ]
    assert not missing, f"zone fragments missing from git: {missing}"


def test_manifest_does_not_carry_schema_version():
    """`schema_version` is emitter-inserted (map_config_emitter.py:92). A manifest
    carrying its own would be rejected by `additionalProperties: false`."""
    import json

    manifest = json.loads((_ZONES_V2 / "manifest.json").read_text(encoding="utf-8-sig"))
    assert "schema_version" not in manifest
    assert set(manifest) == {"hud_version", "reference_resolution", "score_screen_duration_ms"}


def test_fragments_emit_expected_shape(tmp_path):
    """Structural drift, reported in the emitter's own vocabulary."""
    output, _ = _emit_to(tmp_path)
    maps = output["minimap_identification"]["maps"]

    assert len(output["hud_version_detection"]) == _EXPECTED_HUD_ZONES
    assert len(output["in_match_detection"]) == _EXPECTED_IN_MATCH_ZONES
    assert len(maps) == _EXPECTED_MAPS
    assert sum(len(m["zones"]) for m in maps.values()) == _EXPECTED_MAP_ZONES


def test_fragments_regenerate_the_pinned_config(tmp_path):
    """Story 9.15 AC2, re-proven. Any change to any zone value breaks this.

    If this fails, the committed fragments no longer produce the config whose
    accuracy baseline is pinned in `9-15-pilot-zone-set-for-engine-poc.md`. The
    baseline is therefore no longer describing the shipped data. Do NOT re-pin
    the digest to make this pass -- re-run Tool 9 and re-pin the baseline too, or
    revert the zone change.
    """
    _, lf_bytes = _emit_to(tmp_path)
    actual = hashlib.sha256(lf_bytes).hexdigest()

    assert actual == _EXPECTED_SHA256, (
        "committed zone fragments no longer regenerate the pinned map_config.v2.json.\n"
        f"  expected sha256 (LF-normalized): {_EXPECTED_SHA256}\n"
        f"  actual   sha256 (LF-normalized): {actual}\n"
        "The pinned CPU baseline (hud 0.9805 / in_match 1.0 / map_id 1.0) no longer "
        "describes these fragments. Re-run Tool 9 and re-pin, or revert the zone change."
    )
