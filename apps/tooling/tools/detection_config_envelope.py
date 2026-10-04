"""Detection Config Envelope builder (Story 1.13 AC11) - no credentials, no network.

Builds the Firestore `detection_config/latest` OVERLAY document from the
`map_config.<hud_version>.json` files that ship in the app, and writes it as a
local JSON file. Uploading it is Story 1.16's job (an operator step with the
operator's own credentials); this tool never talks to Firebase.

The envelope (`contracts/detection-config-envelope.schema.json`):

    {"envelope_version": 1, "revision": N,
     "configs": {"<hud>": {"config_json": "<file text, verbatim>", "sha256": "<hex>"}}}

Why the config travels as TEXT and not as a nested object: Firestore does not
preserve map-key order, and the native packer (`WardenRulePacker.orderedMapNames`)
recovers `minimap_identification.maps` order - every map rule's texel index -
by scanning the raw JSON text. A string field carries that order byte for byte.
So `config_json` is the file's text exactly as read (no re-serialisation, line
endings included) and `sha256` is over the file's bytes.

Per file, before anything is written (atomic refusal, exit 1):
  * the filename must be `map_config.<hud>.json` with `<hud>` in the
    map-config `hud_version` enum - nothing else is picked up, and a crafted
    name cannot smuggle a path segment into the envelope key;
  * the text must be UTF-8 without a BOM and parse as JSON;
  * it must validate against `contracts/map-config.schema.json`;
  * its `hud_version` must equal the filename's `<hud>`.
The assembled envelope is then validated against its own schema.

Usage:
    python tools/detection_config_envelope.py --revision N
        [--configs-dir apps/mobile/assets/detection]
        [--out apps/tooling/output/detection_config/latest.json]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

import jsonschema

_REPO_ROOT = Path(__file__).resolve().parents[3]
MAP_CONFIG_SCHEMA_PATH = _REPO_ROOT / "contracts" / "map-config.schema.json"
ENVELOPE_SCHEMA_PATH = _REPO_ROOT / "contracts" / "detection-config-envelope.schema.json"

# What ships: the Metro-bundled per-HUD configs.
_DEFAULT_CONFIGS_DIR = _REPO_ROOT / "apps" / "mobile" / "assets" / "detection"
# Gitignored by apps/tooling/.gitignore `output/*`.
_DEFAULT_OUT = Path(__file__).resolve().parent.parent / "output" / "detection_config" / "latest.json"

ENVELOPE_VERSION = 1

_FILENAME_RE = re.compile(r"^map_config\.([^/\\]+)\.json$")


class EnvelopeBuildError(ValueError):
    """A config file or the assembled envelope failed a check. Nothing was written."""


def _load_schema(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise EnvelopeBuildError(f"cannot load schema {path}: {e}") from e


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    # json.loads would silently keep the LAST value of a duplicated key (and so
    # would JSON.parse on the device), while the native packer's text scan of
    # `minimap_identification.maps` would see the slug twice -> rule-count drift.
    seen: dict = {}
    for key, value in pairs:
        if key in seen:
            raise ValueError(f"duplicate object key {key!r}")
        seen[key] = value
    return seen


def _reject_constant(name: str) -> float:
    # Python accepts NaN/Infinity; JSON.parse on the device does not.
    raise ValueError(f"non-standard JSON constant {name}")


def _hud_enum(map_config_schema: dict) -> list[str]:
    return list(map_config_schema["properties"]["hud_version"]["enum"])


def _format_error(e: jsonschema.exceptions.ValidationError) -> str:
    path = "$" + "".join(f"[{p!r}]" if isinstance(p, str) else f"[{p}]" for p in e.absolute_path)
    return f"{path}: {e.message}"


def _entry_for_file(path: Path, hud: str, map_config_schema: dict) -> dict:
    try:
        data = path.read_bytes()
    except OSError as e:  # a directory named like a config, unreadable file, ...
        raise EnvelopeBuildError(f"{path.name}: cannot be read: {e}") from e
    if data.startswith(b"\xef\xbb\xbf"):
        raise EnvelopeBuildError(f"{path.name}: starts with a UTF-8 BOM (JSON.parse on the device would reject it)")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as e:
        raise EnvelopeBuildError(f"{path.name}: not valid UTF-8: {e}") from e
    try:
        config = json.loads(text, object_pairs_hook=_reject_duplicate_keys, parse_constant=_reject_constant)
    except ValueError as e:  # JSONDecodeError is a ValueError
        raise EnvelopeBuildError(f"{path.name}: invalid JSON: {e}") from e
    try:
        jsonschema.Draft202012Validator(map_config_schema).validate(config)
    except jsonschema.exceptions.ValidationError as e:
        raise EnvelopeBuildError(f"{path.name}: fails map-config.schema.json at {_format_error(e)}") from e
    if config["hud_version"] != hud:
        raise EnvelopeBuildError(
            f"{path.name}: filename HUD {hud!r} does not match content hud_version {config['hud_version']!r}"
        )
    # sha256 over the exact bytes; `text` is those bytes decoded, so the device's
    # digest of the UTF-8 encoding of `config_json` reproduces it.
    return {"config_json": text, "sha256": hashlib.sha256(data).hexdigest()}


def build_envelope(
    configs_dir: Path,
    revision: int,
    *,
    map_config_schema_path: Path = MAP_CONFIG_SCHEMA_PATH,
    envelope_schema_path: Path = ENVELOPE_SCHEMA_PATH,
) -> dict:
    """Assemble and validate the envelope. Raises EnvelopeBuildError on any failure."""
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        raise EnvelopeBuildError(f"--revision must be an integer >= 1 (got {revision!r})")
    if not configs_dir.is_dir():
        raise EnvelopeBuildError(f"configs dir does not exist: {configs_dir}")

    map_config_schema = _load_schema(map_config_schema_path)
    allowed = _hud_enum(map_config_schema)

    configs: dict[str, dict] = {}
    for path in sorted(configs_dir.glob("map_config.*.json")):
        m = _FILENAME_RE.match(path.name)
        hud = m.group(1) if m else None
        if hud not in allowed:
            raise EnvelopeBuildError(
                f"{path.name}: HUD {hud!r} from the filename is not in the map-config hud_version enum {allowed}"
            )
        configs[hud] = _entry_for_file(path, hud, map_config_schema)

    if not configs:
        raise EnvelopeBuildError(f"no map_config.<hud>.json files in {configs_dir}")

    envelope = {"envelope_version": ENVELOPE_VERSION, "revision": revision, "configs": configs}
    try:
        jsonschema.Draft202012Validator(_load_schema(envelope_schema_path)).validate(envelope)
    except jsonschema.exceptions.ValidationError as e:
        raise EnvelopeBuildError(f"envelope fails detection-config-envelope.schema.json at {_format_error(e)}") from e
    return envelope


def write_envelope(envelope: dict, out: Path) -> None:
    """Write atomically: an interrupted run must never leave a truncated envelope to upload."""
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    tmp.write_text(json.dumps(envelope, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--configs-dir", type=Path, default=_DEFAULT_CONFIGS_DIR)
    parser.add_argument("--revision", type=int, required=True)
    parser.add_argument("--out", type=Path, default=_DEFAULT_OUT)
    args = parser.parse_args(argv)
    try:
        envelope = build_envelope(args.configs_dir, args.revision)
    except EnvelopeBuildError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    write_envelope(envelope, args.out)
    huds = ", ".join(envelope["configs"])
    print(f"wrote {args.out} (revision {args.revision}; configs: {huds})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
