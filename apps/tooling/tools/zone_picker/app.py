"""Tk shell + mode router for the Unified Zone Picker (Story 9.12, Task 4-6).

Imports tkinter — **never imported by the test suite** (AC11). All testable
logic lives in :mod:`fragments` / :mod:`variance`; this module is the GUI glue:
mode/selection routing, PNG stepping (sorted (class,file) order mirrored from
Tool 9 via :mod:`modes`), the reused ``ImageCanvas`` + ``ROIMode`` +
``HSVFilterMode`` primitives, the AC6 band auto-seed, the AC7 fire-ratio /
aggregate-score readout (fenced — Tool 9/13/14 own authoritative accuracy), the
AC8 per-map weight controls, and the AC9 merge-safe save + AC10 emitter
round-trip.
"""

from __future__ import annotations

import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

import cv2
import numpy as np
from PIL import Image

from tools.common.zones import HsvBand, Rect, band_inrange_ratio
from tools.image_inspector.canvas import ImageCanvas

from . import fragments as F
from .modes import (
    ALL_MODES,
    CapturingROIMode,
    SeedableHSVFilterMode,
    _InspectorShim,
    mode_by_key,
)
from .variance import ClassStats, class_stats

_REF_H = 1080  # ROIMode.REF_H — frames are resized to this so zone rects (ref
_REF_W = 1920  # space) align with the mean image band_inrange_ratio reads.


# ---------------------------------------------------------------------------
# Frame I/O — mirror Tool 9's read/resize plumbing (NOT imported; AC3 says
# mirror the order, and this is trivial I/O, not protected math).
# ---------------------------------------------------------------------------


def _read_bgr(path: str) -> np.ndarray | None:
    """Windows non-ASCII-path-safe PNG read (np.fromfile + imdecode)."""
    try:
        buf = np.fromfile(path, dtype=np.uint8)
    except OSError:
        return None
    if buf.size == 0:
        return None
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


def _resize_to_ref(frame_bgr: np.ndarray, ref_h: int = _REF_H) -> np.ndarray:
    h, w = int(frame_bgr.shape[0]), int(frame_bgr.shape[1])
    if h <= 0 or h == ref_h:
        return frame_bgr
    target_w = max(1, int(round(w * (ref_h / float(h)))))
    interp = cv2.INTER_AREA if ref_h < h else cv2.INTER_LINEAR
    return cv2.resize(frame_bgr, (target_w, ref_h), interpolation=interp)


def _bgr_to_pil(frame_bgr: np.ndarray) -> Image.Image:
    return Image.fromarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------


class ZonePickerApp(tk.Tk):
    def __init__(self, *, hud_version, labeled_dir, zones_dir, initial_mode=None):
        super().__init__()
        self.title(f"Unified Zone Picker — {hud_version}")
        self.geometry("1400x900")

        self._hud_version = hud_version
        self._labeled_dir = Path(labeled_dir)
        self._zones_dir = Path(zones_dir)
        self._version_dir = self._labeled_dir / hud_version

        # Per-target accumulated zones: list of (Rect, HsvBand, weight, wo).
        # Keyed by ("hud_version_detection" | "in_match_detection" | slug).
        self._zones: dict[str, list[tuple]] = {}

        self._frames: list[np.ndarray] = []
        self._frame_paths: list[str] = []
        self._frame_idx = 0
        self._stats: ClassStats | None = None
        self._last_rect: Rect | None = None
        self._view = "raw"

        self._mode = mode_by_key(initial_mode)
        self._canvas: ImageCanvas | None = None
        self._roi_mode: CapturingROIMode | None = None
        self._hsv_mode: SeedableHSVFilterMode | None = None

        self._build_ui()
        self._refresh_selections()

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        top = tk.Frame(self)
        top.pack(side=tk.TOP, fill=tk.X, padx=6, pady=4)

        tk.Label(top, text="Mode:").pack(side=tk.LEFT)
        self._mode_var = tk.StringVar(value=self._mode.key)
        for m in ALL_MODES:
            tk.Radiobutton(
                top, text=m.label, value=m.key, variable=self._mode_var,
                command=self._on_mode_change,
            ).pack(side=tk.LEFT, padx=2)

        tk.Label(top, text="  Class/Map:").pack(side=tk.LEFT)
        self._sel_var = tk.StringVar()
        self._sel_combo = ttk.Combobox(
            top, textvariable=self._sel_var, state="readonly", width=28
        )
        self._sel_combo.pack(side=tk.LEFT, padx=2)
        self._sel_combo.bind("<<ComboboxSelected>>", lambda e: self._on_selection())

        tk.Button(top, text="◀ Prev", command=lambda: self._step(-1)).pack(
            side=tk.LEFT, padx=(10, 1)
        )
        tk.Button(top, text="Next ▶", command=lambda: self._step(1)).pack(side=tk.LEFT)
        self._frame_lbl = tk.Label(top, text="–/–")
        self._frame_lbl.pack(side=tk.LEFT, padx=4)

        for view in ("raw", "mean", "stddev", "heatmap"):
            tk.Button(
                top, text=view.capitalize(),
                command=lambda v=view: self._set_view(v),
            ).pack(side=tk.LEFT, padx=1)

        tk.Button(top, text="＋ Add zone", command=self._add_zone).pack(
            side=tk.LEFT, padx=(12, 2)
        )
        tk.Button(top, text="💾 Save + Emit", command=self._save).pack(side=tk.LEFT)

        # Reused-primitive toolbar (ROIMode + HSVFilterMode pack into here).
        self._toolbar = tk.Frame(self)
        self._toolbar.pack(side=tk.TOP, fill=tk.X, padx=6)

        wf = tk.Frame(self)
        wf.pack(side=tk.TOP, fill=tk.X, padx=6, pady=2)
        tk.Label(wf, text="weight:").pack(side=tk.LEFT)
        self._weight_var = tk.StringVar(value="1.0")
        tk.Entry(wf, textvariable=self._weight_var, width=6).pack(side=tk.LEFT, padx=2)
        tk.Label(wf, text="weight_override (blank=null):").pack(side=tk.LEFT)
        self._wo_var = tk.StringVar(value="")
        tk.Entry(wf, textvariable=self._wo_var, width=6).pack(side=tk.LEFT, padx=2)
        tk.Label(wf, text="ident_threshold:").pack(side=tk.LEFT)
        self._thr_var = tk.StringVar(value="0.6")
        tk.Entry(wf, textvariable=self._thr_var, width=6).pack(side=tk.LEFT, padx=2)
        self._weight_frame = wf

        self._canvas_holder = tk.Frame(self, bg="#2b2b2b")
        self._canvas_holder.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self._status = tk.Label(self, text="", anchor="w", relief=tk.SUNKEN)
        self._status.pack(side=tk.BOTTOM, fill=tk.X)

        self._shim = _InspectorShim(self._toolbar, self.set_status)

    def set_status(self, text):
        self._status.config(text=str(text))

    # -------------------------------------------------------------- routing

    def _on_mode_change(self):
        self._mode = mode_by_key(self._mode_var.get())
        self._weight_frame.pack_configure()  # keep visible; per-map uses it
        self._refresh_selections()

    def _refresh_selections(self):
        sels = self._mode.selections(self._version_dir)
        self._sel_combo["values"] = sels
        if sels:
            self._sel_var.set(sels[0])
            self._on_selection()
        else:
            self.set_status(f"No labeled classes under {self._version_dir}")

    def _on_selection(self):
        sel = self._sel_var.get()
        paths = self._mode.pool_for(self._version_dir, sel)
        if not paths:
            self.set_status(f"No PNGs for selection '{sel}'")
            return
        self.set_status(f"Loading {len(paths)} frame(s) for '{sel}' …")
        self.update_idletasks()

        frames: list[np.ndarray] = []
        kept_paths: list[str] = []
        for p in paths:
            img = _read_bgr(p)
            if img is None:
                continue
            frames.append(_resize_to_ref(img))
            kept_paths.append(p)
        if not frames:
            self.set_status(f"No readable PNGs for '{sel}'")
            return

        self._frames = frames
        self._frame_paths = kept_paths
        self._frame_idx = 0
        try:
            self._stats = class_stats(frames)
        except ValueError as exc:
            self.set_status(f"variance error: {exc}")
            self._stats = None
        self._rebuild_canvas()
        self.set_status(
            f"'{sel}': {len(frames)} frames · mode={self._mode.label} · "
            f"target={self._target_key()}"
        )

    def _target_key(self) -> str:
        if self._mode.needs_map_selector:
            return self._sel_var.get()
        return self._mode.fragment_target

    # --------------------------------------------------------- canvas/view

    def _current_display_bgr(self) -> np.ndarray:
        if self._view == "mean" and self._stats is not None:
            return self._stats.mean_view_u8()
        if self._view == "stddev" and self._stats is not None:
            return self._stats.stddev_view_u8()
        if self._view == "heatmap" and self._stats is not None:
            return self._stats.heatmap_bgr
        if self._frames:
            return self._frames[self._frame_idx]
        return np.zeros((_REF_H, _REF_W, 3), np.uint8)

    def _rebuild_canvas(self):
        # ImageCanvas' original_image is immutable; rebuild it on frame/view
        # change and re-activate the reused modes on the fresh canvas.
        if self._roi_mode is not None:
            self._roi_mode.deactivate()
        if self._hsv_mode is not None:
            self._hsv_mode.deactivate()
        if self._canvas is not None:
            self._canvas.destroy()

        pil = _bgr_to_pil(self._current_display_bgr())
        self._canvas = ImageCanvas(self._canvas_holder, pil)
        self._canvas.pack(fill=tk.BOTH, expand=True)

        if self._frame_paths:
            self._shim.image_path = self._frame_paths[self._frame_idx]

        self._roi_mode = CapturingROIMode(on_commit=self._on_roi)
        self._roi_mode.activate(self._canvas, self._shim)
        self._hsv_mode = SeedableHSVFilterMode()
        self._hsv_mode.activate(self._canvas, self._shim)

        self._frame_lbl.config(
            text=f"{self._frame_idx + 1}/{len(self._frame_paths) or '–'}"
        )

    def _set_view(self, view):
        self._view = view
        self._rebuild_canvas()

    def _step(self, delta):
        if not self._frames:
            return
        self._frame_idx = (self._frame_idx + delta) % len(self._frames)
        if self._view == "raw":
            self._rebuild_canvas()
        else:
            self._frame_lbl.config(
                text=f"{self._frame_idx + 1}/{len(self._frame_paths)}"
            )

    # ------------------------------------------------------- ROI + band-seed

    def _on_roi(self, ref_rect):
        rx, ry, rw, rh = ref_rect
        self._last_rect = Rect(rx, ry, rw, rh)
        if self._stats is None:
            self.set_status("ROI captured (no variance stats — band not seeded)")
            return
        band = self._stats.derive_band(self._last_rect)  # AC6 auto-seed
        if self._hsv_mode is not None:
            self._hsv_mode.seed_band(band)
        self._report_fire(self._last_rect, band)

    def _report_fire(self, rect: Rect, band: HsvBand):
        """AC7 fast-loop readout — fire ratio on the class mean image (and, for
        per-map mode, the aggregate weighted score vs identification_threshold).
        Deliberately NOT a confusion matrix (Tool 9/13/14 own that)."""
        if self._stats is None:
            return
        ratio = band_inrange_ratio(band, rect.clamp_to(self._stats.mean_bgr.shape), self._stats.mean_bgr)
        msg = f"fire ratio = {ratio:.3f} (min_ratio {band.min_ratio:.2f})"
        if self._mode.needs_map_selector:
            msg += "  ·  " + self._aggregate_msg()
        self.set_status(msg)

    def _aggregate_msg(self) -> str:
        zones = self._zones.get(self._target_key(), [])
        if self._stats is None or not zones:
            return "aggregate = 0.000"
        total = 0.0
        fired = 0.0
        for rect, band, weight, wo in zones:
            eff = float(weight if wo is None else wo)
            total += eff
            r = band_inrange_ratio(
                band, rect.clamp_to(self._stats.mean_bgr.shape), self._stats.mean_bgr
            )
            if r >= band.min_ratio:
                fired += eff
        score = fired / total if total else 0.0
        try:
            thr = float(self._thr_var.get())
        except ValueError:
            thr = 0.6
        flag = "✓" if score >= thr else "✗"
        return f"aggregate = {score:.3f} vs threshold {thr:.2f} {flag}"

    # ------------------------------------------------------------ add/save

    def _add_zone(self):
        if self._last_rect is None:
            self.set_status("Drag an ROI first.")
            return
        if self._hsv_mode is None:
            return
        band = self._hsv_mode.read_band()
        if band is None:
            self.set_status("Could not read HSV band — enter integer values.")
            return
        try:
            weight = float(self._weight_var.get())
        except ValueError:
            weight = 1.0
        wo_text = self._wo_var.get().strip()
        weight_override: float | None
        if wo_text == "":
            weight_override = None
        else:
            try:
                weight_override = float(wo_text)
            except ValueError:
                weight_override = None
        key = self._target_key()
        self._zones.setdefault(key, []).append(
            (self._last_rect, band, weight, weight_override)
        )
        self.set_status(
            f"Added zone to '{key}' (now {len(self._zones[key])}).  "
            + (self._aggregate_msg() if self._mode.needs_map_selector else "")
        )

    def _ensure_manifest(self, frags: dict) -> bool:
        if isinstance(frags.get("manifest"), dict):
            # Keep an existing manifest; only refresh hud_version to the session.
            frags["manifest"]["hud_version"] = self._hud_version
            return True
        dur = simpledialog.askinteger(
            "Manifest",
            "score_screen_duration_ms (timing offset after in_match ends):",
            parent=self, minvalue=0, initialvalue=12000,
        )
        if dur is None:
            return False
        frags["manifest"] = {
            "hud_version": self._hud_version,
            "score_screen_duration_ms": int(dur),
            "reference_resolution": {"width": _REF_W, "height": _REF_H},
        }
        return True

    def _save(self):
        frags = F.load_existing(self._zones_dir)
        if not self._ensure_manifest(frags):
            self.set_status("Save cancelled (manifest required).")
            return

        # Write back ONLY the targets this session touched (anti-clobber: the
        # untouched fragments were loaded above and write_all re-emits them).
        for key, zones in self._zones.items():
            if key in ("hud_version_detection", "in_match_detection"):
                F.set_zone_list(frags, key, zones)
            else:  # a map slug (per-map mode)
                F.set_map_zones(frags, key, zones)

        if self._mode.needs_map_selector:
            try:
                thr = float(self._thr_var.get())
            except ValueError:
                thr = 0.6
            roi = None
            if self._last_rect is not None:
                roi = {
                    "name": "minimap",
                    "x": self._last_rect.x, "y": self._last_rect.y,
                    "width": self._last_rect.width, "height": self._last_rect.height,
                }
            F.set_minimap(frags, identification_threshold=thr, roi=roi)

        try:
            F.write_all(self._zones_dir, frags)
        except (ValueError, OSError) as exc:
            messagebox.showerror("Save failed", str(exc))
            return

        ok, detail = self._emit_roundtrip()
        if ok:
            messagebox.showinfo(
                "Saved + Emitted",
                f"Fragments written to {self._zones_dir}\n\n{detail}",
            )
        else:
            messagebox.showerror(
                "Emitter rejected fragments",
                f"Fragments written, but map_config_emitter failed:\n\n{detail}",
            )
        self.set_status(f"Saved to {self._zones_dir} · emitter {'OK' if ok else 'FAILED'}")

    def _emit_roundtrip(self) -> tuple[bool, str]:
        """AC10 — run the *unchanged* emitter on the zones-dir; surface the
        jsonschema error verbatim on failure (treat it as a black-box gate)."""
        emitter_py = Path(__file__).resolve().parents[1] / "map_config_emitter.py"
        try:
            proc = subprocess.run(
                [sys.executable, str(emitter_py), "--zones-dir", str(self._zones_dir)],
                capture_output=True, text=True, timeout=120,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return False, f"could not run emitter: {exc}"
        out = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode == 0, out.strip() or f"exit {proc.returncode}"


def main(argv=None):  # convenience for `python tools/zone_picker/app.py`
    from .__main__ import main as _m

    return _m(argv)
