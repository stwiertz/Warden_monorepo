"""The three mode panels + thin adapters over the reused image_inspector
primitives (Story 9.12 — Tasks 4 & 5).

AC2 anti-reinvention: ``ROIMode`` and ``HSVFilterMode`` are written for the
standalone ``InspectorApp``. They are reused here via :class:`_InspectorShim`
(supplies the ``toolbar`` / ``set_status`` / ``last_pick_hsv`` / ``image_path``
attributes those classes read) plus *minimal* subclasses that override only the
non-math hooks — :class:`CapturingROIMode` captures the committed rect by
calling ``super()._add_roi`` (so ``_to_ref`` / canvas coordinate math is reused
verbatim, never forked); :class:`SeedableHSVFilterMode` adds get/set band
helpers around the existing entry widgets without touching the ``cv2.inRange``
mask math in ``_apply``.

The three mode classes (:class:`HudVersionMode` / :class:`InMatchMode` /
:class:`PerMapMode`) are pure descriptors: each declares its input pooling (the
AC4 table) and its fragment target. They are Tk-free themselves (the pooling is
filesystem enumeration) so the Tk coupling stays isolated in :mod:`app`.
"""

from __future__ import annotations

import glob
import os
from pathlib import Path

from tools.common.labels import MAP_LABELS
from tools.image_inspector.modes import HSVFilterMode, ROIMode
from tools.common.zones import HsvBand

# Non-map "negative"/state classes Tool 6 produces alongside the 14 map slugs.
_NON_MAP_CLASSES = ("lobby", "score", "transition")


# ---------------------------------------------------------------------------
# PNG enumeration — mirror tools.roi_detection_tester.iter_labeled_frames order
# (sorted(listdir) over class dirs, sorted(glob *.png) within) WITHOUT importing
# Tool 9 (AC3: mirror the order, don't couple to the validator).
# ---------------------------------------------------------------------------


def _class_dirs(version_dir: Path) -> list[str]:
    if not version_dir.is_dir():
        return []
    return [
        name
        for name in sorted(os.listdir(version_dir))
        if (version_dir / name).is_dir()
    ]


def _pngs_in(class_dir: Path) -> list[str]:
    return sorted(glob.glob(os.path.join(str(class_dir), "*.png")))


def pooled_pngs(version_dir: Path, classes: list[str]) -> list[str]:
    """Sorted ``(class, file)`` PNG paths pooled over ``classes`` — the exact
    order Tool 9's ``iter_labeled_frames`` would yield, so the picker and the
    downstream validator see frames identically (AC3)."""
    out: list[str] = []
    for class_name in classes:
        if class_name in _class_dirs(version_dir):
            out.extend(_pngs_in(version_dir / class_name))
    return out


# ---------------------------------------------------------------------------
# Reused-primitive adapters (AC2 — adapt, do not fork)
# ---------------------------------------------------------------------------


class _InspectorShim:
    """The subset of ``InspectorApp`` that ``ROIMode`` / ``HSVFilterMode`` read.

    They expect ``toolbar`` (a Tk container to pack their widgets into),
    ``set_status(text)``, ``last_pick_hsv`` (an ``(h, s, v)`` seed tuple), and
    ``image_path`` (the inspector logger writes ``inspector_log.jsonl`` beside
    it — harmless next to the gitignored labeled PNGs). ``set_swatch_color`` is
    only used by the unused ColorPickerMode; a no-op keeps the contract total.
    """

    def __init__(self, toolbar, status_cb):
        self.toolbar = toolbar
        self._status_cb = status_cb
        self.last_pick_hsv = (0, 50, 50)
        self.image_path = ""

    def set_status(self, text):
        self._status_cb(text)

    def set_swatch_color(self, r, g, b):  # pragma: no cover - unused path
        pass


class CapturingROIMode(ROIMode):
    """``ROIMode`` that also reports each committed rect (image- + ref-space).

    Only the non-math ``_add_roi`` hook is overridden: it calls
    ``super()._add_roi`` (which runs the verbatim ``_to_ref`` reference-space
    conversion + overlay drawing) and then hands the freshly appended ROI to
    ``on_commit``. No coordinate or pixel math is duplicated.
    """

    def __init__(self, on_commit):
        super().__init__()
        self._on_commit = on_commit

    def _add_roi(self, x, y, w, h, name=None):
        super()._add_roi(x, y, w, h, name=name)
        # self._rois[-1] is (x, y, w, h, color, rect_id, label_id, name) in
        # image-pixel space; _to_ref reuses ROIMode's own scale math.
        ix, iy, iw, ih = self._rois[-1][:4]
        rx, ry, rw, rh = self._to_ref(ix, iy, iw, ih)
        self._on_commit((rx, ry, rw, rh))


class SeedableHSVFilterMode(HSVFilterMode):
    """``HSVFilterMode`` + seed/read helpers around its existing entry widgets.

    ``_apply`` (the ``cv2.inRange`` overlay-preview math) is untouched —
    :meth:`seed_band` only writes the entry StringVars (so the AC6 auto-seed
    lands in the same widgets the operator then tweaks) and :meth:`read_band`
    parses them back into a user-space :class:`HsvBand`.
    """

    def seed_band(self, band: HsvBand) -> None:
        if not getattr(self, "_center_vars", None):
            return
        for var, value in zip(
            self._center_vars, (band.h_center, band.s_center, band.v_center)
        ):
            var.set(str(int(value)))
        for var, value in zip(
            self._tol_vars, (band.h_tol, band.s_tol, band.v_tol)
        ):
            var.set(str(int(value)))

    def read_band(self, min_ratio: float = 0.3) -> HsvBand | None:
        if not getattr(self, "_center_vars", None):
            return None
        try:
            h_c, s_c, v_c = (int(v.get()) for v in self._center_vars)
            h_t, s_t, v_t = (int(v.get()) for v in self._tol_vars)
        except (ValueError, AttributeError):
            return None
        return HsvBand(h_c, h_t, s_c, s_t, v_c, v_t, min_ratio)


# ---------------------------------------------------------------------------
# The three mode descriptors (AC4 table)
# ---------------------------------------------------------------------------


class _Mode:
    """Base mode descriptor — declares its fragment target + input pooling."""

    key: str = ""
    label: str = ""
    fragment_target: str = ""  # set_zone_list target, or "" for per-map
    needs_map_selector: bool = False
    needs_weights: bool = False

    def selections(self, version_dir: Path) -> list[str]:
        """The choices the operator picks from (a class set or the 14 maps)."""
        raise NotImplementedError

    def pool_for(self, version_dir: Path, selection: str | None) -> list[str]:
        """Sorted PNG paths feeding the variance preprocessing for ``selection``."""
        raise NotImplementedError


class HudVersionMode(_Mode):
    """HUD-version detection — pool = every class under this ``v<hud>/`` (the
    zones distinguish HUD generations). Target: ``hud_version_detection``."""

    key = "hud"
    label = "HUD-version detection"
    fragment_target = "hud_version_detection"

    def selections(self, version_dir: Path) -> list[str]:
        return ["<all classes pooled>"]

    def pool_for(self, version_dir: Path, selection: str | None) -> list[str]:
        return pooled_pngs(version_dir, _class_dirs(version_dir))


class InMatchMode(_Mode):
    """Binary in-match detection — positive = pooled MAP_LABELS folders,
    negative = pooled lobby/score/transition. Target: ``in_match_detection``."""

    key = "in_match"
    label = "In-match detection (binary)"
    fragment_target = "in_match_detection"

    def selections(self, version_dir: Path) -> list[str]:
        return ["positive (pooled maps)", "negative (lobby/score/transition)"]

    def pool_for(self, version_dir: Path, selection: str | None) -> list[str]:
        present = set(_class_dirs(version_dir))
        if selection and selection.startswith("negative"):
            classes = [c for c in _NON_MAP_CLASSES if c in present]
        else:
            classes = [c for c in MAP_LABELS if c in present]
        return pooled_pngs(version_dir, classes)


class PerMapMode(_Mode):
    """Per-map weighted ID — pool = the single selected map slug. Target:
    ``minimap_identification.maps.<slug>.zones`` (weights editable)."""

    key = "per_map"
    label = "Per-map identification"
    fragment_target = ""  # routed through fragments.set_map_zones instead
    needs_map_selector = True
    needs_weights = True

    def selections(self, version_dir: Path) -> list[str]:
        present = set(_class_dirs(version_dir))
        return [slug for slug in MAP_LABELS if slug in present] or list(MAP_LABELS)

    def pool_for(self, version_dir: Path, selection: str | None) -> list[str]:
        if not selection:
            return []
        return pooled_pngs(version_dir, [selection])


ALL_MODES = (HudVersionMode(), InMatchMode(), PerMapMode())


def mode_by_key(key: str | None) -> _Mode:
    for mode in ALL_MODES:
        if mode.key == key:
            return mode
    return ALL_MODES[0]
