"""Export the accepted zones for the Auto ROI/HSV Discoverer (Tool 8).

Writes, under ``apps/tooling/output/auto_rois/<version>/``:

* ``discovered_zones.json`` **and** ``discovered_zones.yaml`` — the accepted zones per
  target class as **config-shaped fragments** (``{class → [{name, x, y, width, height,
  hsv: {h_center, h_tol, s_center, s_tol, v_center, v_tol}, min_ratio}, ...]}``), with a
  ``_metadata`` block / comment header stating this is a **hand-merge fragment** for the
  future game-detector re-fingerprinting story — **never** auto-merged into
  ``config/config.yaml``, the coordinate frame, and that these zones feed the game-state
  detector cascade, **not** the ``minimap_identification`` per-map fingerprints;
* ``report.json`` — all ranked candidates (not just accepted) + the ``GameStateValidator``
  separability proxy on the accepted set + run metadata;
* ``<class>_preview.png`` per target class — that class's ``mean.png`` with the **accepted**
  zones drawn + labelled (and exclusions, faded), written ``cv2.imencode`` + ``Path.write_bytes``.

Re-runs overwrite. Pure logic — no Tk; a write failure raises and the GUI surfaces it.
"""

import datetime
import json
import math
import os
from pathlib import Path

import cv2
import numpy as np

from tools.frame_labeler import MAP_LABELS

from .model import TARGET_CLASSES
from .validator import FP_MAX, TP_MIN


_HAND_MERGE_NOTE = (
    "HAND-MERGE FRAGMENT for the future game-detector re-fingerprinting story. "
    "NOT auto-merged into config/config.yaml — Tool 8 never edits config/config.yaml. "
    "The game-state target classes (lobby / in_match / score / transition) feed the "
    "game-state detector cascade; the per-map classes (artefact, atlantis, ...) are "
    "candidate map-identification fingerprints (the minimap_identification / map-ID "
    "config). Coordinates are in {coord_frame}."
)


def _ordered_classes(names) -> list[str]:
    """``names`` ordered as: game-state classes (TARGET_CLASSES order), then per-map
    classes (MAP_LABELS order), then any other extras (in the original iteration order)."""
    names = list(names)
    present = set(names)
    out = [c for c in TARGET_CLASSES if c in present]
    out += [c for c in MAP_LABELS if c in present]
    out += [c for c in names if c not in TARGET_CLASSES and c not in MAP_LABELS]
    return out


def _coord_frame_str(ref_height, frame_shape) -> str:
    """Coordinate-frame description, always anchored on the *actual* ``frame_shape``
    (rather than just the configured ``ref_height``) so the metadata never silently
    advertises ``<ref_height>-row`` when the cell shape disagrees."""
    fh = int(frame_shape[0]) if frame_shape is not None else 0
    fw = int(frame_shape[1]) if frame_shape is not None else 0
    if ref_height:
        return f"{fh}x{fw} cell pixel space (Tool 7 ran with --ref-height {int(ref_height)})"
    return f"{fh}x{fw} modal cell pixel space"


# ---------------------------------------------------------------------------
# Fragment + report builders (no I/O)
# ---------------------------------------------------------------------------


def build_fragment(zones_by_class: dict, *, version, ref_height, frame_shape,
                   generated_at: str | None = None) -> dict:
    """The config-shaped fragment dict — a ``_metadata`` block + one key per target
    class → list of config-shaped zone dicts (user-space HSV)."""
    generated_at = generated_at or datetime.datetime.now().astimezone().isoformat()
    coord = _coord_frame_str(ref_height, frame_shape)
    frag: dict = {
        "_metadata": {
            "tool": "auto_roi_discoverer (Tool 8)",
            "hud_version": version,
            "generated_at": generated_at,
            "ref_height": ref_height,
            "coordinate_frame": coord,
            "frame_shape": [int(d) for d in frame_shape],
            "note": _HAND_MERGE_NOTE.format(coord_frame=coord),
        }
    }
    for cls in _ordered_classes(zones_by_class):
        frag[cls] = [z.zone_dict() for z in zones_by_class[cls]]
    return frag


def _candidate_dict(c) -> dict:
    inst = c.instability
    return {
        "rect": {"x": c.rect.x, "y": c.rect.y, "width": c.rect.width, "height": c.rect.height},
        "hsv": c.band.hsv_dict(),
        "min_ratio": c.band.min_ratio,
        "score": round(float(c.score), 5),
        "size_score": round(float(c.size_score), 5),
        "stability_score": round(float(c.stability_score), 5),
        "discriminativeness_score": round(float(c.discriminativeness_score), 5),
        "closest_confuser": c.closest_confuser,
        "mean_instability": (round(float(inst), 4) if isinstance(inst, (int, float)) and math.isfinite(inst) else None),
    }


def _validation_dict(report) -> dict | None:
    if report is None:
        return None
    return {
        "rule": {
            "tp_min": TP_MIN, "fp_max": FP_MAX,
            "description": (
                "a zone is separable if tp_proxy >= tp_min and fp_proxy <= fp_max; "
                "a class is separable if it has >= 1 separable zone. PROXY ONLY — "
                "mean/std-based, not per-frame (exact per-frame validation is the future "
                "re-fingerprinting story's job)."
            ),
        },
        "zones": [
            {
                "zone_name": z.zone_name, "target_class": z.target_class,
                "tp_proxy": round(z.tp_proxy, 5), "fp_proxy": round(z.fp_proxy, 5),
                "inrange_on_assigned": round(z.inrange_on_assigned, 5),
                "coverage_estimate": round(z.coverage_estimate, 5),
                "fires_on_assigned": z.fires_on_assigned,
                "worst_confuser": z.worst_confuser, "separable": z.separable,
            }
            for z in report.zones
        ],
        "classes": [
            {
                "target_class": c.target_class, "separable": c.separable,
                "contributing_zones": list(c.contributing_zones),
                "best_tp_proxy": round(c.best_tp_proxy, 5),
                "worst_fp_proxy": round(c.worst_fp_proxy, 5), "n_zones": c.n_zones,
            }
            for c in report.classes
        ],
    }


def build_report(zones_by_class: dict, candidates_by_class: dict, validation_report, *,
                 version, ref_height, frame_shape, target_classes: dict, input_dir,
                 summary_path, exclusions_path, generated_at: str | None = None) -> dict:
    """The ``report.json`` dict — per-class ranked candidates (all proposed) + the
    validator proxy on the accepted set + run metadata."""
    generated_at = generated_at or datetime.datetime.now().astimezone().isoformat()
    coord = _coord_frame_str(ref_height, frame_shape)
    per_class: dict = {}
    all_cls = _ordered_classes(set(target_classes or {}) | set(zones_by_class or {}) | set(candidates_by_class or {}))
    for cls in all_cls:
        ts = (target_classes or {}).get(cls)
        cands = (candidates_by_class or {}).get(cls, []) or []
        accepted = (zones_by_class or {}).get(cls, []) or []
        per_class[cls] = {
            "present": ts is not None,
            "kind": ("map" if cls in MAP_LABELS else "game_state"),
            "frame_count": (ts.frame_count if ts else None),
            "is_pooled": (ts.is_pooled if ts else None),
            "source_cells": (list(ts.source_cells) if ts else []),
            "stability_score": (ts.stability_score if ts else None),
            "n_candidates": len(cands),
            "n_accepted": len(accepted),
            "candidates": [_candidate_dict(c) for c in cands],
            "accepted_zone_names": [z.name for z in accepted],
        }
    return {
        "tool": "auto_roi_discoverer (Tool 8)",
        "generated_at": generated_at,
        "hud_version": version,
        "input_dir": input_dir,
        "summary_path": summary_path,
        "exclusions_path": exclusions_path,
        "ref_height": ref_height,
        "frame_shape": [int(d) for d in frame_shape],
        "coordinate_frame": coord,
        "note": _HAND_MERGE_NOTE.format(coord_frame=coord),
        "classes": per_class,
        "validation": _validation_dict(validation_report),
    }


# ---------------------------------------------------------------------------
# Previews + the top-level export
# ---------------------------------------------------------------------------


def _write_png_safe(path: str, arr: np.ndarray) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    ok, buf = cv2.imencode(".png", arr)
    if not ok:
        raise RuntimeError(f"cv2.imencode returned False for {path}")
    Path(path).write_bytes(buf.tobytes())


def write_preview(out_path: str, mean_bgr: np.ndarray, accepted_zones, exclusion_rects) -> None:
    """That class's mean image with the accepted zones drawn (green + labelled) and the
    exclusions faded (grey). Windows non-ASCII-path-safe write."""
    img = np.clip(np.round(np.asarray(mean_bgr, dtype=np.float64)), 0, 255).astype(np.uint8)
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    else:
        img = img.copy()
    h, w = img.shape[:2]

    def _box(x, y, ww, hh):
        return (max(0, min(int(x), w - 1)), max(0, min(int(y), h - 1)),
                max(0, min(int(x) + int(ww) - 1, w - 1)), max(0, min(int(y) + int(hh) - 1, h - 1)))

    for er in exclusion_rects or []:
        x0, y0, x1, y1 = _box(er.x, er.y, er.width, er.height)
        cv2.rectangle(img, (x0, y0), (x1, y1), (130, 130, 130), 1)
    for z in accepted_zones or []:
        r = z.rect
        x0, y0, x1, y1 = _box(r.x, r.y, r.width, r.height)
        cv2.rectangle(img, (x0, y0), (x1, y1), (0, 255, 0), 1)
        cv2.putText(img, str(z.name), (x0, max(9, y0 - 3)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 0), 1, cv2.LINE_AA)
    _write_png_safe(out_path, img)


def export_all(*, export_root: str, version, target_classes: dict, zones_by_class: dict,
               candidates_by_class: dict, validation_report, exclusion_rects_by_class: dict,
               ref_height, frame_shape, input_dir, summary_path, exclusions_path) -> str:
    """Write ``discovered_zones.{json,yaml}`` + ``report.json`` + ``<class>_preview.png``
    under ``export_root/<version>/`` (``os.makedirs(..., exist_ok=True)`` first; re-runs
    overwrite). Returns the version directory. Raises ``OSError`` / ``RuntimeError`` on a
    write failure — the GUI catches it and shows a ``messagebox``."""
    out_dir = os.path.join(str(export_root), str(version))
    os.makedirs(out_dir, exist_ok=True)
    generated_at = datetime.datetime.now().astimezone().isoformat()

    frag = build_fragment(zones_by_class, version=version, ref_height=ref_height,
                          frame_shape=frame_shape, generated_at=generated_at)
    with open(os.path.join(out_dir, "discovered_zones.json"), "w", encoding="utf-8") as fh:
        json.dump(frag, fh, indent=2)

    import yaml
    meta = frag["_metadata"]
    with open(os.path.join(out_dir, "discovered_zones.yaml"), "w", encoding="utf-8") as fh:
        fh.write("# " + meta["note"] + "\n")
        fh.write(f"# HUD version: {version} | coordinate frame: {meta['coordinate_frame']}\n")
        fh.write("# Shape: { class -> [ {name, x, y, width, height, "
                 "hsv: {h_center, h_tol, s_center, s_tol, v_center, v_tol}, min_ratio}, ... ] }\n")
        yaml.safe_dump(frag, fh, default_flow_style=False, allow_unicode=True, sort_keys=False)

    report = build_report(zones_by_class, candidates_by_class, validation_report,
                          version=version, ref_height=ref_height, frame_shape=frame_shape,
                          target_classes=target_classes, input_dir=input_dir,
                          summary_path=summary_path, exclusions_path=exclusions_path,
                          generated_at=generated_at)
    with open(os.path.join(out_dir, "report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    for cls, ts in (target_classes or {}).items():
        write_preview(os.path.join(out_dir, f"{cls}_preview.png"), ts.mean_bgr,
                      zones_by_class.get(cls, []), (exclusion_rects_by_class or {}).get(cls, []))
    return out_dir
