"""Map Config Emitter - config-driven map_config.json writer.

Reads apps/tooling/config/config.yaml, detects which schema version the input
shape implies (v1 = legacy minimap_identification.configs[0] wrapper; v2 = Tool 8
flat shape with game_state_zones cascade), assembles the matching map_config.json
output dict, validates against contracts/map-config.schema.json, and writes the
file. ROI+HSV detection only - perceptual hashing was a research thread that
never shipped and has been removed (Story 9.9a Scope Adjustment #2, 2026-05-15).

Usage:
    python tools/map_config_emitter.py                         # uses config/config.yaml + config.output.default_dir
    python tools/map_config_emitter.py -c path/to/config.yaml
    python tools/map_config_emitter.py -o path/to/output_dir
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import jsonschema

from utils.config import load_config

# Schema source-of-truth lives at the repo root: <repo>/contracts/map-config.schema.json.
# From this file (apps/tooling/tools/map_config_emitter.py), three .parents hops
# reach <repo>.
SCHEMA_PATH = Path(__file__).resolve().parents[3] / "contracts" / "map-config.schema.json"


# ---------------------------------------------------------------------------
# Schema version detection
# ---------------------------------------------------------------------------


def _detect_schema_version(config_yaml_dict: dict) -> int:
    """Detect v1 vs v2 input shape from the parsed config.yaml dict.

    Returns 2 if EITHER:
      - top-level `game_state_zones` is present and non-empty, OR
      - `minimap_identification` is the Tool 8 flat shape: top-level values are
        lists of dicts that have `hsv` + `min_ratio` (no `configs` wrapper, no
        per-map `zones` wrapper).

    Returns 1 if `minimap_identification.configs` exists (the legacy HUD V1
    shape) OR if neither v2 marker is present.
    """
    if config_yaml_dict.get("game_state_zones"):
        return 2

    minimap = config_yaml_dict.get("minimap_identification")
    if isinstance(minimap, dict):
        if "configs" in minimap:
            return 1
        for value in minimap.values():
            if (isinstance(value, list) and value
                    and isinstance(value[0], dict)
                    and "hsv" in value[0] and "min_ratio" in value[0]):
                return 2
    return 1


# ---------------------------------------------------------------------------
# v1 emit - flatten the legacy minimap_identification.configs[0] wrapper
# ---------------------------------------------------------------------------


def _build_v1_output(config_yaml_dict: dict) -> dict:
    """Assemble the v1 output dict from the legacy config.yaml shape.

    Reads `minimap_identification.configs[0]` (single config, by convention) and
    flattens the array wrapper. Per-map `zones` lists pass through unchanged
    (each zone keeps its `id`/`x`/`y`/`width`/`height`/`hsv`/`min_ratio`/`weight`/
    `weight_override`).
    """
    ref = config_yaml_dict["reference_resolution"]
    minimap_block = config_yaml_dict.get("minimap_identification") or {}
    configs = minimap_block.get("configs") or []
    if not configs:
        raise ValueError(
            "v1 emit requires `minimap_identification.configs` in config.yaml "
            "(legacy HUD V1 shape)"
        )
    cfg = configs[0]
    roi = cfg["roi"]

    return {
        "schema_version": 1,
        "reference_resolution": {"width": int(ref["width"]), "height": int(ref["height"])},
        "minimap_identification": {
            "id": str(cfg["id"]),
            "identification_threshold": float(cfg["identification_threshold"]),
            "roi": {
                "name": str(roi["name"]),
                "x": int(roi["x"]),
                "y": int(roi["y"]),
                "width": int(roi["width"]),
                "height": int(roi["height"]),
            },
            "maps": {
                map_name: {"zones": [_coerce_v1_zone(z) for z in entry.get("zones") or []]}
                for map_name, entry in (cfg.get("maps") or {}).items()
            },
        },
    }


def _coerce_v1_zone(zone: dict) -> dict:
    """Pass-through coercion for a HUD V1 zone dict - copy the 9 required keys
    in canonical order and ignore unknowns (defensive against yaml drift)."""
    return {
        "id": str(zone["id"]),
        "x": int(zone["x"]),
        "y": int(zone["y"]),
        "width": int(zone["width"]),
        "height": int(zone["height"]),
        "hsv": {
            "h_center": int(zone["hsv"]["h_center"]),
            "h_tol": int(zone["hsv"]["h_tol"]),
            "s_center": int(zone["hsv"]["s_center"]),
            "s_tol": int(zone["hsv"]["s_tol"]),
            "v_center": int(zone["hsv"]["v_center"]),
            "v_tol": int(zone["hsv"]["v_tol"]),
        },
        "min_ratio": float(zone["min_ratio"]),
        "weight": float(zone["weight"]),
        "weight_override": bool(zone["weight_override"]),
    }


# ---------------------------------------------------------------------------
# v2 emit - Tool 8 flat shape with game_state_zones cascade
# ---------------------------------------------------------------------------


def _build_v2_output(config_yaml_dict: dict) -> dict:
    """Assemble the v2 output dict from the post-9.9b hand-merged config.yaml.

    Reads `game_state_zones` + `minimap_identification` (flat shape: keys are
    map names, values are lists of zone dicts). Maps iterate in MAP_LABELS
    canonical order for stable diffs across re-emits.
    """
    from tools.frame_labeler import MAP_LABELS

    ref = config_yaml_dict["reference_resolution"]
    gsz_in = config_yaml_dict.get("game_state_zones") or {}
    gsz = {
        cls: [_coerce_v2_zone(z) for z in (gsz_in.get(cls) or [])]
        for cls in ("lobby", "in_match", "score", "transition")
    }

    minimap = config_yaml_dict.get("minimap_identification") or {}
    if not isinstance(minimap, dict):
        minimap = {}
    maps = {}
    for label in MAP_LABELS:
        zones = minimap.get(label)
        if isinstance(zones, list):
            maps[label] = [_coerce_v2_zone(z) for z in zones]
    for name, zones in minimap.items():
        if name in maps:
            continue
        if (isinstance(zones, list) and zones
                and isinstance(zones[0], dict) and "hsv" in zones[0]):
            maps[name] = [_coerce_v2_zone(z) for z in zones]

    return {
        "schema_version": 2,
        "reference_resolution": {"width": int(ref["width"]), "height": int(ref["height"])},
        "game_state_zones": gsz,
        "maps": maps,
    }


def _coerce_v2_zone(zone: dict) -> dict:
    """Coerce a HUD V2 zone dict into the v2 ZoneSpec shape.

    Tool 8's fragment writes `{name, x, y, width, height, hsv, min_ratio}`.
    Legacy HUD V1 zones (`{id, ..., weight, weight_override}`) get coerced:
    rename `id` -> `name` and drop `weight`/`weight_override` (re-introduction is
    a future-config-version decision, NOT v2's job).
    """
    return {
        "name": zone.get("name") or zone.get("id") or "zone",
        "x": int(zone["x"]),
        "y": int(zone["y"]),
        "width": int(zone["width"]),
        "height": int(zone["height"]),
        "hsv": {
            "h_center": int(zone["hsv"]["h_center"]),
            "h_tol": int(zone["hsv"]["h_tol"]),
            "s_center": int(zone["hsv"]["s_center"]),
            "s_tol": int(zone["hsv"]["s_tol"]),
            "v_center": int(zone["hsv"]["v_center"]),
            "v_tol": int(zone["hsv"]["v_tol"]),
        },
        "min_ratio": float(zone["min_ratio"]),
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


def emit(config: dict, output_dir: str) -> dict:
    """Top-level emit pipeline - detect, build, validate, write.

    Returns the output dict that was written. Calls `sys.exit(1)` on schema
    validation failure (no partial file written).
    """
    version = _detect_schema_version(config)
    if version == 1:
        output = _build_v1_output(config)
    else:
        output = _build_v2_output(config)

    try:
        _validate_against_schema(output)
    except jsonschema.exceptions.ValidationError as e:
        print(f"Error: {_format_validation_error(e)}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "map_config.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"\n{'=' * 50}")
    print(f"Map Config Emitter (v{version})")
    if version == 1:
        n_maps = len(output["minimap_identification"]["maps"])
        total_zones = sum(len(m["zones"]) for m in output["minimap_identification"]["maps"].values())
        print(f"  Maps: {n_maps}")
        print(f"  Total zones: {total_zones}")
    else:
        print(f"  Maps: {len(output['maps'])}")
        for cls in ("lobby", "in_match", "score", "transition"):
            print(f"  game_state_zones.{cls}: {len(output['game_state_zones'][cls])} zone(s)")
    print(f"  Output: {os.path.abspath(output_path)}")
    print(f"{'=' * 50}")
    return output


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Emit map_config.json from config.yaml (ROI+HSV; v1 or v2 by input shape)."
    )
    parser.add_argument(
        "-c", "--config",
        default="config/config.yaml",
        help="Path to config file (default: config/config.yaml)",
    )
    parser.add_argument(
        "-o", "--output-dir",
        default=None,
        help="Output directory for map_config.json (default: config.output.default_dir)",
    )
    args = parser.parse_args()

    if not os.path.isfile(args.config):
        print(f"Error: Config file not found: {args.config}", file=sys.stderr)
        sys.exit(1)

    config = load_config(args.config)
    output_dir = args.output_dir if args.output_dir else config["output"]["default_dir"]

    try:
        emit(config, output_dir)
    except (KeyError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
