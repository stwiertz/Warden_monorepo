"""Parse / apply / save ``exclusions.yaml`` — per-HUD-version, per-target-class
named rectangles masked out before discovery (the discoverer treats their pixels as
max-instability so they're never proposed). Pure logic — no Tk.

YAML shape::

    exclusions:
      v2.0:
        _all:
          - {name: ko_counter, x: ..., y: ..., width: ..., height: ...}
        lobby:
          - {name: rotating_banner, x: ..., y: ..., width: ..., height: ...}
        in_match: []
        score: []
        transition: []

Coords are in the cell pixel space (the ``--ref-height`` resized space if Tool 7
used one). A missing file → no exclusions. A parse error / wrong shape → warn + no
exclusions (never crash).
"""

import os
import sys

import numpy as np

from .model import ExclusionRect

ALL_KEY = "_all"


# ---------------------------------------------------------------------------
# Parse
# ---------------------------------------------------------------------------


def parse_exclusions(path: str | None) -> dict:
    """Read ``path`` → ``{version: {class_or__all: [ExclusionRect, ...]}}`` (``{}``
    on a missing/None path, a parse error, or the wrong top-level shape)."""
    if not path or not os.path.isfile(path):
        return {}
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}
    except Exception as exc:  # noqa: BLE001 — any parse trouble degrades to "no exclusions"
        print(f"  ⚠ exclusions disabled: could not parse {path!r}: {exc}.",
              file=sys.stderr, flush=True)
        return {}

    block = raw.get("exclusions") if isinstance(raw, dict) else None
    if not isinstance(block, dict):
        if raw:
            print(f"  ⚠ {path!r} has no top-level 'exclusions:' mapping — ignoring.",
                  file=sys.stderr, flush=True)
        return {}

    out: dict = {}
    for version, classes in block.items():
        if not isinstance(classes, dict):
            continue
        per_class: dict = {}
        for cls, rects in classes.items():
            parsed: list[ExclusionRect] = []
            for rd in rects or []:
                try:
                    raw_name = rd.get("name") if isinstance(rd, dict) else None
                    name = str(raw_name) if raw_name not in (None, "") else "exclusion"
                    parsed.append(ExclusionRect(
                        name=name,
                        x=rd["x"], y=rd["y"], width=rd["width"], height=rd["height"],
                    ))
                except (AttributeError, KeyError, TypeError, ValueError):
                    print(f"  ⚠ skipping malformed exclusion in {path!r}: {rd!r}",
                          file=sys.stderr, flush=True)
            per_class[str(cls)] = parsed
        out[str(version)] = per_class
    return out


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------


def exclusion_rects_for(data: dict, version, target_class) -> list[ExclusionRect]:
    """The version's ``_all`` bucket + its per-class list for ``target_class`` — merged."""
    per_version = (data or {}).get(str(version)) or {}
    rects = list(per_version.get(ALL_KEY) or [])
    rects += list(per_version.get(str(target_class)) or [])
    return rects


def build_mask(rects, shape) -> np.ndarray:
    """Boolean ``(h, w)`` mask — ``True`` where any rect in ``rects`` covers a pixel.
    Out-of-bounds rects are clipped; an empty list → all-``False``."""
    h, w = int(shape[0]), int(shape[1])
    mask = np.zeros((h, w), dtype=bool)
    for r in rects or []:
        x0, y0 = max(0, int(r.x)), max(0, int(r.y))
        x1 = min(w, int(r.x) + int(r.width))
        y1 = min(h, int(r.y) + int(r.height))
        if x1 > x0 and y1 > y0:
            mask[y0:y1, x0:x1] = True
    return mask


# ---------------------------------------------------------------------------
# Mutate (used by the GUI)
# ---------------------------------------------------------------------------


def add_exclusion(data: dict, version, target_class, rect: ExclusionRect) -> dict:
    """Append ``rect`` to ``data[version][target_class]`` in place (creating nested
    dicts/lists as needed). Returns ``data``."""
    data.setdefault(str(version), {}).setdefault(str(target_class), []).append(rect)
    return data


def remove_exclusion(data: dict, version, target_class, name: str) -> dict:
    """Drop the first exclusion named ``name`` from ``data[version][target_class]``
    in place. Returns ``data``."""
    lst = (data.get(str(version)) or {}).get(str(target_class))
    if lst:
        for i, r in enumerate(lst):
            if r.name == name:
                del lst[i]
                break
    return data


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------


_HEADER = (
    "# Auto ROI/HSV Discoverer (Tool 8) — exclusion masks.\n"
    "# Per HUD version -> per target class (lobby / in_match / score / transition),\n"
    "# plus an `_all` bucket applied to every class of that version. Coords are in the\n"
    "# cell pixel space (the --ref-height resized space if Tool 7 used one).\n"
    "# Hand-editable; also written by the GUI's \"Save exclusions\".\n"
)


def save_exclusions(path: str, data: dict) -> None:
    """Write ``data`` (the parsed nested form) back to ``path`` as
    ``{"exclusions": {version: {class: [{name,x,y,width,height}, ...]}}}`` — creating
    parent dirs first, with a short comment header. Empty per-class lists are kept so
    the file is self-documenting."""
    import yaml
    serialised: dict = {}
    for version, classes in (data or {}).items():
        serialised[str(version)] = {
            str(cls): [r.as_dict() for r in (rects or [])]
            for cls, rects in (classes or {}).items()
        }
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(_HEADER)
        yaml.safe_dump({"exclusions": serialised}, handle,
                       default_flow_style=False, allow_unicode=True, sort_keys=True)
