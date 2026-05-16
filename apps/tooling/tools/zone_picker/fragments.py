"""Merge-safe zone-fragment load / mutate / serialize — the testable contract.

Pure logic — stdlib + ``tools.common`` only. **No tkinter, no numpy, no cv2.**
This module owns the four JSON fragment files the *unchanged*
``map_config_emitter.py`` (Story 9.9c) consumes:

* ``manifest.json``                  — operator-supplied per-HUD-version metadata
* ``hud_version_detection.json``     — ``Zone[]``
* ``in_match_detection.json``        — ``Zone[]``
* ``minimap_identification.json``    — ``{id, identification_threshold, roi, maps}``

The anti-clobber contract (Story 9.12 AC9): the picker mutates only the one
fragment the active mode targets, but :func:`write_all` always writes **all
four** so a per-map run never wipes ``in_match_detection.json`` etc. Untouched
fragments are preserved verbatim; never-yet-populated fragments are scaffolded
schema-valid-empty.

Zone serialization produces *exactly* the 9 schema keys (``id, x, y, width,
height, hsv{6}, min_ratio, weight, weight_override``). The emitter does **no**
coercion — the jsonschema gate is the only enforcement point — so this module
clamps every field into its schema range before it ever reaches disk
(``hsv`` centers/tolerances are schema **integers**; ``weight_override`` is
``number | null``, never boolean).
"""

from __future__ import annotations

import json
from pathlib import Path

from tools.common.labels import MAP_LABELS
from tools.common.zones import HsvBand, Rect

# The emitter's exact fragment-file basenames + read order.
FRAGMENT_NAMES = (
    "manifest",
    "hud_version_detection",
    "in_match_detection",
    "minimap_identification",
)

# The two flat-array fragment targets + their stable zone-id prefixes (AC9:
# ids must be stable and meaningful — `hud_z00`, `inmatch_z00`, `<slug>_z00`).
_ARRAY_TARGETS = {
    "hud_version_detection": "hud",
    "in_match_detection": "inmatch",
}

# Schema-valid placeholder for a never-populated minimap roi (operator overrides
# it in per-map mode). width/height >= 1 satisfies $defs.Rect.
_DEFAULT_ROI = {"name": "minimap", "x": 0, "y": 0, "width": 1, "height": 1}
_DEFAULT_MINIMAP_ID = "test"
_DEFAULT_IDENT_THRESHOLD = 0.6


# ---------------------------------------------------------------------------
# Zone serialization — produce exactly the 9 schema keys, every field clamped
# ---------------------------------------------------------------------------


def _clamp_int(value, lo: int, hi: int) -> int:
    return int(max(lo, min(hi, round(float(value)))))


def serialize_zone(
    zone_id: str,
    rect: Rect,
    band: HsvBand,
    weight: float,
    weight_override: float | None,
) -> dict:
    """``(Rect, HsvBand, weight, weight_override)`` → the exact 9-key Zone dict.

    Every field is clamped into its ``contracts/map-config.schema.json`` range:
    ``x/y >= 0``; ``width/height >= 1``; ``hsv`` centers/tolerances are integers
    in their schema bounds (the recovered band-seed math can overshoot
    ``h_tol`` past 180 — clamp it here, the emitter will not); ``min_ratio`` in
    ``[0, 1]``; ``weight >= 0``; ``weight_override`` is ``None`` or a number
    ``>= 0`` (**never** a bool — the unified schema rejects the pre-9.9c boolean
    shape and a test locks that).
    """
    x = max(0, int(rect.x))
    y = max(0, int(rect.y))
    width = max(1, int(rect.width))
    height = max(1, int(rect.height))

    # bool is an int subclass — a stray True/False would serialize as the
    # pre-9.9c boolean shape the unified schema rejects, so coerce it to null.
    if weight_override is None or isinstance(weight_override, bool):
        wo: float | None = None
    else:
        wo = max(0.0, float(weight_override))

    return {
        "id": str(zone_id),
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "hsv": {
            "h_center": _clamp_int(band.h_center, 0, 360),
            "h_tol": _clamp_int(band.h_tol, 0, 180),
            "s_center": _clamp_int(band.s_center, 0, 100),
            "s_tol": _clamp_int(band.s_tol, 0, 100),
            "v_center": _clamp_int(band.v_center, 0, 100),
            "v_tol": _clamp_int(band.v_tol, 0, 100),
        },
        "min_ratio": max(0.0, min(1.0, float(band.min_ratio))),
        "weight": max(0.0, float(weight)),
        "weight_override": wo,
    }


def _serialize_zone_list(prefix: str, zones: list[tuple]) -> list[dict]:
    """Serialize ``[(rect, band, weight, weight_override), ...]`` with stable,
    position-derived ids (``<prefix>_z00`` ...). Ids are stable as long as the
    operator-fixed ordering is stable — the picker owns ordering, the emitter
    preserves it."""
    out: list[dict] = []
    for idx, item in enumerate(zones):
        rect, band, weight, weight_override = item
        out.append(
            serialize_zone(f"{prefix}_z{idx:02d}", rect, band, weight, weight_override)
        )
    return out


# ---------------------------------------------------------------------------
# Scaffolding
# ---------------------------------------------------------------------------


def _scaffold_minimap() -> dict:
    """A schema-valid-empty ``minimap_identification`` (no maps fingerprinted)."""
    return {
        "id": _DEFAULT_MINIMAP_ID,
        "identification_threshold": _DEFAULT_IDENT_THRESHOLD,
        "roi": dict(_DEFAULT_ROI),
        "maps": {},
    }


def scaffold_empty(manifest: dict) -> dict:
    """Full schema-valid-empty fragment set around an operator-supplied manifest.

    Arrays are ``[]`` (schema-valid); minimap is the empty scaffold. The manifest
    is taken verbatim — the caller is responsible for its
    ``hud_version`` / ``score_screen_duration_ms`` / ``reference_resolution``
    fields (the picker prompts for them; they cannot be inferred from PNGs).
    """
    return {
        "manifest": dict(manifest),
        "hud_version_detection": [],
        "in_match_detection": [],
        "minimap_identification": _scaffold_minimap(),
    }


# ---------------------------------------------------------------------------
# Load existing (anti-clobber: read whatever is present, scaffold the rest)
# ---------------------------------------------------------------------------


def _read_json(path: Path):
    """Read a fragment file with ``utf-8-sig`` (BOM-tolerant — the emitter reads
    the same way). Returns the parsed JSON, or raises ``ValueError`` naming the
    offending path on malformed JSON."""
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc


def load_existing(zones_dir) -> dict:
    """Load whatever fragments already exist under ``zones_dir``; scaffold the rest.

    Missing array fragment → ``[]``. Missing ``minimap_identification.json`` →
    the empty minimap scaffold. Missing ``manifest.json`` → ``None`` (the picker
    must supply manifest fields before :func:`write_all` — it prompts for the
    bits it cannot infer). This is the anti-clobber read half: a per-map session
    that never touches ``in_match_detection.json`` still round-trips its
    content unchanged because it was loaded here and written back by
    :func:`write_all`.
    """
    zones_dir = Path(zones_dir)
    manifest_path = zones_dir / "manifest.json"
    hud_path = zones_dir / "hud_version_detection.json"
    inmatch_path = zones_dir / "in_match_detection.json"
    minimap_path = zones_dir / "minimap_identification.json"

    return {
        "manifest": _read_json(manifest_path) if manifest_path.is_file() else None,
        "hud_version_detection": (
            _read_json(hud_path) if hud_path.is_file() else []
        ),
        "in_match_detection": (
            _read_json(inmatch_path) if inmatch_path.is_file() else []
        ),
        "minimap_identification": (
            _read_json(minimap_path) if minimap_path.is_file() else _scaffold_minimap()
        ),
    }


# ---------------------------------------------------------------------------
# Mutation — touch only the active mode's target fragment
# ---------------------------------------------------------------------------


def set_zone_list(fragments: dict, target: str, zones: list[tuple]) -> None:
    """Replace one flat-array fragment (``hud_version_detection`` or
    ``in_match_detection``) with serialized, stably-id'd zones. Other fragments
    are left untouched (the anti-clobber write half lives in
    :func:`write_all`)."""
    if target not in _ARRAY_TARGETS:
        raise ValueError(
            f"set_zone_list target must be one of {sorted(_ARRAY_TARGETS)}, got {target!r}"
        )
    fragments[target] = _serialize_zone_list(_ARRAY_TARGETS[target], zones)


def set_map_zones(fragments: dict, slug: str, zones: list[tuple]) -> None:
    """Set one map slug's zone list under ``minimap_identification.maps``.

    The slug must match the emitter's ``^[a-z][a-z0-9_]*$`` pattern (all 14
    ``MAP_LABELS`` comply). Zone ids are ``<slug>_z00`` ... — stable per slug.
    Insertion happens here; :func:`write_all` re-orders ``maps`` into
    ``MAP_LABELS`` order so the emitted config is deterministic."""
    minimap = fragments.setdefault("minimap_identification", _scaffold_minimap())
    minimap.setdefault("maps", {})[slug] = {
        "zones": _serialize_zone_list(slug, zones)
    }


def set_minimap(
    fragments: dict,
    *,
    id: str | None = None,
    identification_threshold: float | None = None,
    roi: dict | None = None,
) -> None:
    """Update the minimap-level fields (shared ROI / id / threshold) without
    touching per-map zone lists."""
    minimap = fragments.setdefault("minimap_identification", _scaffold_minimap())
    if id is not None:
        minimap["id"] = str(id)
    if identification_threshold is not None:
        minimap["identification_threshold"] = max(
            0.0, min(1.0, float(identification_threshold))
        )
    if roi is not None:
        minimap["roi"] = {
            "name": str(roi.get("name", "minimap")) or "minimap",
            "x": max(0, int(roi["x"])),
            "y": max(0, int(roi["y"])),
            "width": max(1, int(roi["width"])),
            "height": max(1, int(roi["height"])),
        }


# ---------------------------------------------------------------------------
# Write all four (anti-clobber: never partial)
# ---------------------------------------------------------------------------


def _ordered_maps(maps: dict) -> dict:
    """``maps`` re-ordered into ``MAP_LABELS`` order (known slugs first, in the
    canonical order; any unrecognised slugs appended in insertion order). The
    emitter preserves dict insertion order — the picker owns stable ordering."""
    ordered: dict = {}
    for slug in MAP_LABELS:
        if slug in maps:
            ordered[slug] = maps[slug]
    for slug, entry in maps.items():
        if slug not in ordered:
            ordered[slug] = entry
    return ordered


def write_all(zones_dir, fragments: dict) -> None:
    """Write **all four** fragment files (anti-clobber — never a partial set).

    Requires a complete ``manifest`` (the picker prompts for the fields it
    cannot infer before calling this). ``maps`` is re-ordered into
    ``MAP_LABELS`` order. Files are ``json.dump(indent=2)``, ``utf-8`` — the
    same shape ``test_map_config_emitter._write_fragments`` writes, so the
    unchanged emitter round-trips them.
    """
    manifest = fragments.get("manifest")
    if not isinstance(manifest, dict):
        raise ValueError(
            "cannot write fragments: manifest is missing — supply hud_version / "
            "score_screen_duration_ms / reference_resolution first"
        )

    minimap = fragments.get("minimap_identification") or _scaffold_minimap()
    minimap = dict(minimap)
    minimap["maps"] = _ordered_maps(minimap.get("maps", {}))

    payload = {
        "manifest": manifest,
        "hud_version_detection": fragments.get("hud_version_detection", []),
        "in_match_detection": fragments.get("in_match_detection", []),
        "minimap_identification": minimap,
    }

    zones_dir = Path(zones_dir)
    zones_dir.mkdir(parents=True, exist_ok=True)
    for name in FRAGMENT_NAMES:
        (zones_dir / f"{name}.json").write_text(
            json.dumps(payload[name], indent=2), encoding="utf-8"
        )
