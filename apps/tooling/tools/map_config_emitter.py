"""Map Config Emitter - fragment-driven map_config.<hud_version>.json writer.

Reads four JSON zone fragments from a zones directory written by `zone_picker`
(Story 9.12) — `manifest.json`, `hud_version_detection.json`,
`in_match_detection.json`, `minimap_identification.json` — assembles them into
a single unified map_config dict matching contracts/map-config.schema.json,
validates strictly via Draft202012Validator, and writes the result to
`<output_dir>/map_config.<hud_version>.json` (one file per HUD version).
On validation failure the emitter calls `sys.exit(1)` BEFORE any file write
(atomic refusal). The emitter does NOT read `config.yaml` and has no
dependency on legacy tooling — decoupled ahead of Story 9.11.

Usage:
    python tools/map_config_emitter.py --zones-dir <dir> [--output-dir <dir>]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import jsonschema

# Schema source-of-truth lives at the repo root: <repo>/contracts/map-config.schema.json.
# From this file (apps/tooling/tools/map_config_emitter.py), three .parents hops
# reach <repo>.
SCHEMA_PATH = Path(__file__).resolve().parents[3] / "contracts" / "map-config.schema.json"

# Anchor to __file__ so the wardentooling subprocess (cwd=apps/tooling/) and
# direct CLI invocations (cwd=repo root) both resolve to the same target.
_DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output" / "map_configs"

_FRAGMENT_FILES = (
    "manifest",
    "hud_version_detection",
    "in_match_detection",
    "minimap_identification",
)


# ---------------------------------------------------------------------------
# Input layer - read disk-resident zone fragments
# ---------------------------------------------------------------------------


def _load_fragments(zones_dir: Path) -> dict:
    """Read the four zone-fragment JSON files from `zones_dir`.

    Returns a dict with keys `manifest`, `hud_version_detection`,
    `in_match_detection`, `minimap_identification`. Raises `FileNotFoundError`
    with the offending path if any fragment file is missing; lets
    `json.JSONDecodeError` bubble up if any file is malformed.
    """
    fragments: dict = {}
    for name in _FRAGMENT_FILES:
        path = zones_dir / f"{name}.json"
        if not path.is_file():
            raise FileNotFoundError(f"missing zone fragment: {path}")
        try:
            fragments[name] = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as e:
            raise ValueError(f"invalid JSON in {path}: {e}") from e
    return fragments


# ---------------------------------------------------------------------------
# Assembly - turn fragments into the unified output dict
# ---------------------------------------------------------------------------


def _assemble_output(fragments: dict) -> dict:
    """Build the unified output dict from loaded fragments.

    No coercion, no field renaming: `zone_picker` writes fragments in the
    target shape, and human-edited fragments are expected to match. The
    validation gate (`_validate_against_schema`) is the single enforcement
    point — keep this function dumb so atomic refusal works.

    `schema_version: 1` is inserted as the first key for readable diffs.
    """
    manifest = fragments["manifest"]
    for key in ("hud_version", "score_screen_duration_ms", "reference_resolution"):
        if key not in manifest:
            raise ValueError(f"manifest.json missing required field {key!r}")
    return {
        "schema_version": 1,
        "reference_resolution": manifest["reference_resolution"],
        "hud_version": manifest["hud_version"],
        "score_screen_duration_ms": manifest["score_screen_duration_ms"],
        "hud_version_detection": fragments["hud_version_detection"],
        "in_match_detection": fragments["in_match_detection"],
        "minimap_identification": fragments["minimap_identification"],
    }


# ---------------------------------------------------------------------------
# Strict-validation gate + write
# ---------------------------------------------------------------------------


def _validate_against_schema(output_dict: dict, schema_path: Path = SCHEMA_PATH) -> None:
    """Validate an in-memory output dict against the cross-language JSON Schema.

    Raises `jsonschema.exceptions.ValidationError` on mismatch. Caller is
    responsible for rewrapping the error into a stderr line + non-zero exit
    code (atomic - never write a partial/invalid file to disk).
    """
    schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(output_dict)


def _format_validation_error(e: jsonschema.exceptions.ValidationError) -> str:
    path = "$" + "".join(
        f"[{p!r}]" if isinstance(p, str) else f"[{p}]" for p in e.absolute_path
    )
    return f"map_config validation failed at {path}: {e.message}"


def emit(zones_dir: Path, output_dir: Path) -> dict:
    """Top-level emit pipeline - load, assemble, validate, write.

    Reads the four zone fragments from `zones_dir`, builds the unified output
    dict, runs the strict-validation gate, and writes
    `<output_dir>/map_config.<hud_version>.json` (filename derived from the
    manifest's `hud_version`). Returns the dict that was written. Calls
    `sys.exit(1)` on schema validation failure (no partial file written).
    """
    fragments = _load_fragments(zones_dir)
    output = _assemble_output(fragments)

    try:
        _validate_against_schema(output)
    except jsonschema.exceptions.ValidationError as e:
        print(f"Error: {_format_validation_error(e)}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)
    output_path = Path(output_dir) / f"map_config.{output['hud_version']}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    maps = output["minimap_identification"]["maps"]
    total_map_zones = sum(len(entry["zones"]) for entry in maps.values())
    print(f"\n{'=' * 50}")
    print(f"Map Config Emitter ({output['hud_version']})")
    print(f"  hud_version_detection: {len(output['hud_version_detection'])} zone(s)")
    print(f"  in_match_detection: {len(output['in_match_detection'])} zone(s)")
    print(f"  minimap_identification.maps: {len(maps)} map(s), {total_map_zones} total zone(s)")
    print(f"  Output: {output_path.resolve()}")
    print(f"{'=' * 50}")
    return output


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Emit map_config.<hud_version>.json from zone fragments produced by zone_picker "
            "(Story 9.12). Single unified schema (no v1/v2 branches)."
        )
    )
    parser.add_argument(
        "--zones-dir",
        required=True,
        help=(
            "Directory containing manifest.json, hud_version_detection.json, "
            "in_match_detection.json, minimap_identification.json"
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=str(_DEFAULT_OUTPUT_DIR),
        help=f"Output directory for map_config.<hud_version>.json (default: {_DEFAULT_OUTPUT_DIR})",
    )
    args = parser.parse_args()

    zones_dir = Path(args.zones_dir)
    if not zones_dir.is_dir():
        print(f"Error: Zones directory not found: {zones_dir}", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(args.output_dir)

    try:
        emit(zones_dir, output_dir)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON in zone fragment: {e}", file=sys.stderr)
        sys.exit(1)
    except (KeyError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
