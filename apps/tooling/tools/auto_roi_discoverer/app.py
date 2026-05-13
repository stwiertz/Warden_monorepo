"""AutoRoiDiscovererApp — the Tk GUI for the Auto ROI/HSV Discoverer (Tool 8).

The GUI is confined to this module (+ ``__main__``); the engine / loader / validator /
exclusions / export are pure and unit-tested without Tk. Layout mirrors
``minimap_zone_selector/app.py``: a toolbar (target-class + image-view comboboxes;
Suggest zones / Save exclusions / Export buttons; an exclusion-draw toggle), a paned
canvas (left, ``image_inspector.ImageCanvas``) + right panel (a reused
``minimap_zone_selector.HSVEditor`` + a ``GameStateValidator``-driven separability
panel), and a status bar. Single ``tk.Tk`` root; dialogs are ``messagebox`` /
``simpledialog`` only. **Not** unit-tested (Tool 6 / minimap_zone_selector precedent).
"""

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

import cv2
import numpy as np
from PIL import Image

from tools.frame_labeler import MAP_LABELS
from tools.minimap_zone_selector.hsv_editor import HSVEditor
from tools.minimap_zone_selector.zone_model import Zone as _MzsZone

from .discoverer import DiscoverParams, derive_band_for_rect, suggest_candidates
from .exclusions import (
    add_exclusion,
    build_mask,
    exclusion_rects_for,
    parse_exclusions,
    remove_exclusion,
    save_exclusions,
)
from .export import export_all
from .loader import DEFAULT_EXCLUSIONS_PATH, default_export_root
from .model import TARGET_CLASSES, DiscoveredZone, ExclusionRect, HsvBand, Rect, comparison_classes
from .validator import GameStateValidator

_CANDIDATE_COLORS = ["cyan", "lime", "magenta", "yellow", "orange", "red"]
_ACCEPTED_COLOR = "#00ff66"
_SELECTED_COLOR = "#ffffff"
_EXCLUSION_COLOR = "#ff4040"
_LEGACY_COLOR = "#7a7a7a"
_CLICK_SLOP = 3  # px — a drag smaller than this on both axes counts as a click (select), not a draw


class AutoRoiDiscovererApp(tk.Tk):
    """Interactive review window for Tool 8."""

    def __init__(self, *, loaded, legacy_rois=None, exclusions_path=None):
        super().__init__()
        self.title(f"Auto ROI/HSV Discoverer — Tool 8  [{loaded.version}]")
        self.geometry("1500x920")
        self.minsize(1100, 720)

        self._loaded = loaded
        self._legacy_rois = legacy_rois
        self._exclusions_path = exclusions_path
        self._exclusions = parse_exclusions(exclusions_path)   # {version: {class: [ExclusionRect]}}
        self._version = loaded.version
        self._classes = dict(loaded.target_classes)            # name -> TargetClassStats
        self._available = [c for c in TARGET_CLASSES if c in self._classes] + \
            [c for c in self._classes if c not in TARGET_CLASSES]
        if not self._available:                                # defensive — __main__ already guards
            raise RuntimeError("No target classes loaded.")
        self._current_class = self._available[0]
        self._current_view = "mean"
        self._params = DiscoverParams()

        self._candidates: dict[str, list] = {c: [] for c in self._available}
        self._accepted: dict[str, list[DiscoveredZone]] = {c: [] for c in self._available}
        self._selected_zone: DiscoveredZone | None = None
        self._validation = None
        self._zone_counter = 0

        # Canvas drag state.
        self._canvas: object | None = None
        self._drag_cx = self._drag_cy = 0
        self._dragging = False

        self._build_ui()
        self._reload_canvas_image()
        self._revalidate()
        self._refresh_panels()
        n_maps = sum(1 for c in self._classes if c in MAP_LABELS)
        self._set_status(
            f"Loaded {len(self._classes)} target(s) for {self._version} "
            f"({loaded.frame_shape[1]}x{loaded.frame_shape[0]} cell pixel space): "
            f"the game-state classes + {n_maps} per-map cell(s). Pick a target, hit “Suggest zones”."
        )

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        # --- Toolbar ---
        toolbar = tk.Frame(self, relief=tk.RAISED, bd=1)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=4, pady=2)

        tk.Label(toolbar, text="Target:").pack(side=tk.LEFT, padx=(4, 2))
        self._class_var = tk.StringVar(value=self._current_class)
        self._class_combo = ttk.Combobox(
            toolbar, textvariable=self._class_var, state="readonly",
            values=self._available, width=15,
        )
        self._class_combo.pack(side=tk.LEFT, padx=2)
        self._class_combo.bind("<<ComboboxSelected>>", self._on_class_change)
        self._class_info = tk.Label(toolbar, text="", fg="#555")
        self._class_info.pack(side=tk.LEFT, padx=(4, 12))

        tk.Label(toolbar, text="View:").pack(side=tk.LEFT, padx=(4, 2))
        self._view_var = tk.StringVar(value=self._current_view)
        self._view_combo = ttk.Combobox(
            toolbar, textvariable=self._view_var, state="readonly",
            values=["mean", "stddev", "heatmap"], width=9,
        )
        self._view_combo.pack(side=tk.LEFT, padx=2)
        self._view_combo.bind("<<ComboboxSelected>>", self._on_view_change)

        tk.Button(toolbar, text="Suggest zones", command=self._on_suggest).pack(side=tk.LEFT, padx=(12, 2))
        tk.Button(toolbar, text="Save exclusions", command=self._on_save_exclusions).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="Export", command=self._on_export).pack(side=tk.LEFT, padx=2)

        self._excl_mode_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            toolbar, text="Draw exclusions (or hold Shift)", variable=self._excl_mode_var,
        ).pack(side=tk.LEFT, padx=(12, 2))

        # --- Paned: canvas (left) | right panel ---
        paned = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, sashwidth=6)
        paned.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=4, pady=2)
        self._canvas_frame = tk.Frame(paned, bg="#2b2b2b")
        paned.add(self._canvas_frame, stretch="always", minsize=400)
        self._right = tk.Frame(paned)
        paned.add(self._right, width=400, minsize=340)

        # HSV editor (reused from minimap_zone_selector).
        self._hsv_editor = HSVEditor(self._right, on_change=self._on_band_change)
        self._hsv_editor.pack(side=tk.TOP, fill=tk.X, padx=4, pady=(4, 2))

        # --- Candidates ---
        cand_box = tk.LabelFrame(self._right, text="Candidates (Suggest zones)", padx=4, pady=2)
        cand_box.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=4, pady=2)
        cand_inner = tk.Frame(cand_box)
        cand_inner.pack(fill=tk.BOTH, expand=True)
        cand_scroll = tk.Scrollbar(cand_inner, orient=tk.VERTICAL)
        self._cand_list = tk.Listbox(cand_inner, height=8, yscrollcommand=cand_scroll.set,
                                     font=("Consolas", 8), exportselection=False)
        cand_scroll.config(command=self._cand_list.yview)
        cand_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._cand_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._cand_list.bind("<<ListboxSelect>>", self._on_select_candidate)
        tk.Button(cand_box, text="Accept selected →", command=self._on_accept_candidate).pack(
            side=tk.TOP, anchor="e", pady=(2, 0))

        # --- Accepted zones ---
        acc_box = tk.LabelFrame(self._right, text="Accepted zones (exported)", padx=4, pady=2)
        acc_box.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=4, pady=2)
        acc_inner = tk.Frame(acc_box)
        acc_inner.pack(fill=tk.BOTH, expand=True)
        acc_scroll = tk.Scrollbar(acc_inner, orient=tk.VERTICAL)
        self._acc_list = tk.Listbox(acc_inner, height=7, yscrollcommand=acc_scroll.set,
                                    font=("Consolas", 8), exportselection=False)
        acc_scroll.config(command=self._acc_list.yview)
        acc_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._acc_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._acc_list.bind("<<ListboxSelect>>", self._on_select_zone)
        acc_btns = tk.Frame(acc_box)
        acc_btns.pack(side=tk.TOP, anchor="e", pady=(2, 0))
        tk.Button(acc_btns, text="Delete selected", fg="red", command=self._on_delete_zone).pack(side=tk.LEFT)

        # --- Separability verdict ---
        verdict_box = tk.LabelFrame(self._right, text="Separability (GameStateValidator — proxy)", padx=4, pady=2)
        verdict_box.pack(side=tk.TOP, fill=tk.X, padx=4, pady=(2, 4))
        self._verdict_label = tk.Label(verdict_box, text="", justify=tk.LEFT, anchor="w",
                                       font=("Consolas", 8))
        self._verdict_label.pack(fill=tk.X)

        # --- Status bar ---
        self._status = tk.Label(self, text="", anchor="w", relief=tk.SUNKEN, bd=1)
        self._status.pack(side=tk.BOTTOM, fill=tk.X)

    # ------------------------------------------------------ image / canvas
    def _stats(self, class_name=None):
        return self._classes[class_name or self._current_class]

    def _pil_for(self, class_name: str, view: str) -> Image.Image:
        ts = self._classes[class_name]
        if view == "stddev":
            arr = np.clip(np.round(np.asarray(ts.std_bgr, dtype=np.float64)), 0, 255).astype(np.uint8)
            rgb = cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)
        elif view == "heatmap":
            scalar = np.asarray(ts.std_hsv, dtype=np.float64)[..., 1:].mean(axis=2)
            lo, hi = float(scalar.min()), float(scalar.max())
            norm = (np.zeros_like(scalar, dtype=np.uint8) if hi <= lo
                    else np.round((scalar - lo) / (hi - lo) * 255.0).astype(np.uint8))
            heat = cv2.applyColorMap(norm, cv2.COLORMAP_JET)
            rgb = cv2.cvtColor(heat, cv2.COLOR_BGR2RGB)
        else:  # "mean"
            arr = np.clip(np.round(np.asarray(ts.mean_bgr, dtype=np.float64)), 0, 255).astype(np.uint8)
            rgb = cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)
        return Image.fromarray(np.ascontiguousarray(rgb))

    def _reload_canvas_image(self):
        from tools.image_inspector.canvas import ImageCanvas  # lazy — Pillow/Tk only when needed
        pil = self._pil_for(self._current_class, self._current_view)
        if self._canvas is None:
            self._canvas = ImageCanvas(self._canvas_frame, pil)
            self._canvas.pack(fill=tk.BOTH, expand=True)
            self._canvas.bind("<ButtonPress-1>", self._on_press)
            self._canvas.bind("<B1-Motion>", self._on_motion)
            self._canvas.bind("<ButtonRelease-1>", self._on_release)
            self._canvas.set_overlay_redraw(self._redraw_overlays)
        else:
            self._canvas.set_display_image(pil)
        self._redraw_overlays()

    def _exclusion_rects(self, class_name: str):
        return exclusion_rects_for(self._exclusions, self._version, class_name)

    def _exclusion_mask(self, class_name: str) -> np.ndarray:
        return build_mask(self._exclusion_rects(class_name), self._classes[class_name].frame_shape)

    def _comparison_classes(self, name: str) -> list[str]:
        """Containment-aware "other classes" for ``name`` — see ``model.comparison_classes``."""
        return comparison_classes(name, self._classes, map_classes=MAP_LABELS)

    def _other_means_hsv(self, class_name: str) -> dict:
        return {n: self._classes[n].mean_hsv for n in self._comparison_classes(class_name)}

    # ------------------------------------------------------------ overlays
    def _img_rect_to_canvas(self, x, y, w, h):
        cx0, cy0 = self._canvas.image_to_canvas(x, y)
        cx1, cy1 = self._canvas.image_to_canvas(x + w, y + h)
        return cx0, cy0, cx1, cy1

    def _redraw_overlays(self):
        if self._canvas is None:
            return
        self._canvas.delete("overlay")
        # Legacy config ROIs (faded), scaled from reference resolution to this cell.
        # Use a single isotropic scale (aspect-preserving) — applying sx and sy
        # independently distorts legacy rects when the source aspect differs from the
        # config's reference_resolution aspect.
        if self._legacy_rois:
            fh, fw = self._classes[self._current_class].frame_shape[:2]
            ref = self._legacy_rois.get("reference_resolution") or {"width": fw, "height": fh}
            ref_w = max(1, int(ref.get("width", fw)))
            ref_h = max(1, int(ref.get("height", fh)))
            scale = min(fw / ref_w, fh / ref_h)
            for r in self._legacy_rois.get("rects", []):
                cx0, cy0, cx1, cy1 = self._img_rect_to_canvas(r["x"] * scale, r["y"] * scale,
                                                              r["width"] * scale, r["height"] * scale)
                self._canvas.create_rectangle(cx0, cy0, cx1, cy1, outline=_LEGACY_COLOR,
                                              dash=(2, 2), tags=("overlay",))
        # Exclusion rects for the current class.
        for er in self._exclusion_rects(self._current_class):
            cx0, cy0, cx1, cy1 = self._img_rect_to_canvas(er.x, er.y, er.width, er.height)
            self._canvas.create_rectangle(cx0, cy0, cx1, cy1, outline=_EXCLUSION_COLOR,
                                          dash=(3, 3), tags=("overlay",))
            self._canvas.create_text(cx0 + 2, cy0 + 2, text=f"✕ {er.name}", anchor="nw",
                                     fill=_EXCLUSION_COLOR, font=("TkDefaultFont", 7), tags=("overlay",))
        # Ranked candidates (numbered, colour-cycled).
        for i, c in enumerate(self._candidates.get(self._current_class, [])):
            colour = _CANDIDATE_COLORS[i % len(_CANDIDATE_COLORS)]
            cx0, cy0, cx1, cy1 = self._img_rect_to_canvas(c.rect.x, c.rect.y, c.rect.width, c.rect.height)
            self._canvas.create_rectangle(cx0, cy0, cx1, cy1, outline=colour, tags=("overlay",))
            self._canvas.create_text(cx0 + 2, cy0 + 2, text=str(i + 1), anchor="nw", fill=colour,
                                     font=("TkDefaultFont", 8, "bold"), tags=("overlay",))
        # Accepted zones (green; selected = white, thicker).
        for z in self._accepted.get(self._current_class, []):
            sel = z is self._selected_zone
            cx0, cy0, cx1, cy1 = self._img_rect_to_canvas(z.rect.x, z.rect.y, z.rect.width, z.rect.height)
            self._canvas.create_rectangle(cx0, cy0, cx1, cy1, outline=(_SELECTED_COLOR if sel else _ACCEPTED_COLOR),
                                          width=(3 if sel else 2), tags=("overlay",))
            self._canvas.create_text(cx0 + 2, cy1 + 2, text=z.name, anchor="nw",
                                     fill=(_SELECTED_COLOR if sel else _ACCEPTED_COLOR),
                                     font=("TkDefaultFont", 8), tags=("overlay",))

    # -------------------------------------------------------- canvas mouse
    def _on_press(self, event):
        self._drag_cx, self._drag_cy = event.x, event.y
        self._dragging = True

    def _on_motion(self, event):
        if not self._dragging or self._canvas is None:
            return
        self._canvas.delete("dragrect")
        self._canvas.create_rectangle(self._drag_cx, self._drag_cy, event.x, event.y,
                                      outline="white", dash=(2, 2), tags=("overlay", "dragrect"))

    def _on_release(self, event):
        if not self._dragging or self._canvas is None:
            return
        self._dragging = False
        self._canvas.delete("dragrect")
        dx, dy = abs(event.x - self._drag_cx), abs(event.y - self._drag_cy)
        if dx < _CLICK_SLOP and dy < _CLICK_SLOP:
            self._handle_click(event.x, event.y)
            return
        p0 = self._canvas.canvas_to_image(self._drag_cx, self._drag_cy)
        p1 = self._canvas.canvas_to_image(event.x, event.y)
        if p0 is None or p1 is None:
            self._set_status("Drag must start and end inside the image — try again.")
            return
        x0, y0 = min(p0[0], p1[0]), min(p0[1], p1[1])
        x1, y1 = max(p0[0], p1[0]), max(p0[1], p1[1])
        rect = Rect(x0, y0, max(1, x1 - x0), max(1, y1 - y0)).clamp_to(
            self._classes[self._current_class].frame_shape)
        shift_held = bool(event.state & 0x0001)
        if self._excl_mode_var.get() or shift_held:
            self._add_exclusion_rect(rect)
        else:
            self._add_manual_zone(rect)

    def _handle_click(self, cx, cy):
        pt = self._canvas.canvas_to_image(cx, cy)
        if pt is None:
            return
        px, py = pt
        # Prefer an accepted zone hit (topmost), else a candidate.
        for idx, z in enumerate(self._accepted.get(self._current_class, [])):
            if z.rect.x <= px < z.rect.x + z.rect.width and z.rect.y <= py < z.rect.y + z.rect.height:
                self._acc_list.selection_clear(0, tk.END)
                self._acc_list.selection_set(idx)
                self._select_zone(z)
                return
        for idx, c in enumerate(self._candidates.get(self._current_class, [])):
            if c.rect.x <= px < c.rect.x + c.rect.width and c.rect.y <= py < c.rect.y + c.rect.height:
                self._cand_list.selection_clear(0, tk.END)
                self._cand_list.selection_set(idx)
                self._load_band_into_editor(c.band, owner=None)
                self._set_status(f"Candidate #{idx + 1} selected (display only — Accept it to edit/export).")
                return

    # ----------------------------------------------------------- mutators
    def _next_zone_name(self, class_name: str) -> str:
        self._zone_counter += 1
        return f"{class_name}_z{self._zone_counter}"

    def _add_manual_zone(self, rect: Rect):
        ts = self._classes[self._current_class]
        band = derive_band_for_rect(rect, ts.mean_hsv, ts.std_hsv, self._params)
        zone = DiscoveredZone(name=self._next_zone_name(self._current_class),
                              target_class=self._current_class, rect=rect, band=band, origin="manual")
        self._accepted[self._current_class].append(zone)
        self._revalidate()
        self._refresh_panels()
        self._select_zone(zone)
        self._set_status(f"Added manual zone {zone.name} @ {rect.as_tuple()} (HSV sampled from the mean image).")

    def _add_exclusion_rect(self, rect: Rect):
        name = simpledialog.askstring("Exclusion name",
                                      "Name this exclusion rect (e.g. ko_counter):", parent=self)
        if not name:
            self._set_status("Exclusion cancelled.")
            return
        er = ExclusionRect(name=name.strip(), x=rect.x, y=rect.y, width=rect.width, height=rect.height)
        add_exclusion(self._exclusions, self._version, self._current_class, er)
        self._refresh_panels()
        self._redraw_overlays()
        self._set_status(f"Excluded {er.name} @ {er.as_dict()} for {self._current_class}. "
                         "“Save exclusions” to persist; “Suggest zones” to re-propose without it.")

    def _select_zone(self, zone: DiscoveredZone | None):
        self._selected_zone = zone
        if zone is not None:
            self._load_band_into_editor(zone.band, owner=zone)
        self._redraw_overlays()

    def _load_band_into_editor(self, band: HsvBand, owner: DiscoveredZone | None):
        # HSVEditor expects a minimap_zone_selector Zone; build a shim. ``owner`` is the
        # DiscoveredZone the editor writes back to (None ⇒ display-only).
        self._editor_owner = owner
        shim = _MzsZone(
            zone_id=(owner.name if owner else "candidate"),
            x=0, y=0, width=0, height=0,
            h_center=band.h_center, h_tol=band.h_tol,
            s_center=band.s_center, s_tol=band.s_tol,
            v_center=band.v_center, v_tol=band.v_tol,
            min_ratio=band.min_ratio, weight=0.0, weight_override=False,
        )
        self._hsv_editor.load_zone(shim)

    def _on_band_change(self, shim_zone):
        owner = getattr(self, "_editor_owner", None)
        if owner is None:
            return  # editing a candidate / nothing — nothing to persist
        owner.band = HsvBand(shim_zone.h_center, shim_zone.h_tol, shim_zone.s_center, shim_zone.s_tol,
                             shim_zone.v_center, shim_zone.v_tol, shim_zone.min_ratio)
        self._revalidate()
        self._refresh_panels()
        self._redraw_overlays()
        self._set_status(f"Updated band of {owner.name}.")

    # -------------------------------------------------------------- panels
    def _revalidate(self):
        self._validation = GameStateValidator.evaluate(
            self._accepted, self._classes,
            comparison_classes={c: self._comparison_classes(c) for c in self._classes},
        )

    def _class_info_text(self, class_name: str) -> str:
        ts = self._classes[class_name]
        bits = [f"{ts.frame_count}f"]
        if ts.is_pooled:
            bits.append(f"pooled×{len(ts.source_cells)}")
        if ts.stability_score is not None:
            bits.append(f"stab {ts.stability_score:.2f}")
        return "  ".join(bits)

    def _refresh_panels(self):
        self._class_info.config(text=self._class_info_text(self._current_class))
        # Candidates list.
        self._cand_list.delete(0, tk.END)
        for i, c in enumerate(self._candidates.get(self._current_class, [])):
            self._cand_list.insert(
                tk.END,
                f"#{i + 1:>2} sc{c.score:.2f} [sz{c.size_score:.2f} st{c.stability_score:.2f} "
                f"dc{c.discriminativeness_score:.2f}] vs {c.closest_confuser or '-'} "
                f"@({c.rect.x},{c.rect.y},{c.rect.width}x{c.rect.height})",
            )
        # Accepted list.
        self._acc_list.delete(0, tk.END)
        for z in self._accepted.get(self._current_class, []):
            zv = self._validation.zone(z.name) if self._validation else None
            tail = (f" TP{zv.tp_proxy:.2f} FP{zv.fp_proxy:.2f} {'OK' if zv.separable else 'x'}"
                    if zv else "")
            self._acc_list.insert(
                tk.END,
                f"{z.name} [{z.origin[:4]}] @({z.rect.x},{z.rect.y},{z.rect.width}x{z.rect.height}){tail}",
            )
        # Verdict.
        if self._validation:
            lines = []
            for cv in self._validation.classes:
                star = "SEPARABLE " if cv.separable else "not-sep    "
                lines.append(f"{star} {cv.target_class:<11} {cv.n_zones}z  "
                             f"bestTP {cv.best_tp_proxy:.2f}  worstFP {cv.worst_fp_proxy:.2f}")
            self._verdict_label.config(text="\n".join(lines) or "(no zones yet)")
        else:
            self._verdict_label.config(text="(no zones yet)")

    # ---------------------------------------------------------- callbacks
    def _on_class_change(self, _event=None):
        self._current_class = self._class_var.get()
        self._selected_zone = None
        self._editor_owner = None
        self._reload_canvas_image()
        self._refresh_panels()
        self._set_status(f"Class → {self._current_class}.")

    def _on_view_change(self, _event=None):
        self._current_view = self._view_var.get()
        self._reload_canvas_image()
        self._set_status(f"View → {self._current_view}.")

    def _on_suggest(self):
        cls = self._current_class
        ts = self._classes[cls]
        try:
            cands = suggest_candidates(ts, self._other_means_hsv(cls), self._exclusion_mask(cls),
                                       params=self._params)
        except Exception as exc:  # noqa: BLE001 — never let a discoverer hiccup kill the GUI
            messagebox.showerror("Suggest zones failed", str(exc), parent=self)
            return
        self._candidates[cls] = cands
        self._refresh_panels()
        self._redraw_overlays()
        self._set_status(f"{len(cands)} candidate(s) for {cls}"
                         + (" — top picks should land on stable HUD chrome." if cands else " — none above the area floor; try fewer exclusions."))

    def _on_accept_candidate(self):
        sel = self._cand_list.curselection()
        cls = self._current_class
        cands = self._candidates.get(cls, [])
        if not sel or sel[0] >= len(cands):
            self._set_status("Pick a candidate first.")
            return
        c = cands[sel[0]]
        zone = DiscoveredZone(name=self._next_zone_name(cls), target_class=cls,
                              rect=Rect(c.rect.x, c.rect.y, c.rect.width, c.rect.height),
                              band=HsvBand(c.band.h_center, c.band.h_tol, c.band.s_center, c.band.s_tol,
                                           c.band.v_center, c.band.v_tol, c.band.min_ratio),
                              origin="candidate")
        self._accepted[cls].append(zone)
        self._revalidate()
        self._refresh_panels()
        self._select_zone(zone)
        self._set_status(f"Accepted candidate #{sel[0] + 1} as {zone.name}.")

    def _on_select_candidate(self, _event=None):
        sel = self._cand_list.curselection()
        cands = self._candidates.get(self._current_class, [])
        if not sel or sel[0] >= len(cands):
            return
        self._load_band_into_editor(cands[sel[0]].band, owner=None)

    def _on_select_zone(self, _event=None):
        sel = self._acc_list.curselection()
        zones = self._accepted.get(self._current_class, [])
        if not sel or sel[0] >= len(zones):
            return
        self._select_zone(zones[sel[0]])

    def _on_delete_zone(self):
        sel = self._acc_list.curselection()
        cls = self._current_class
        zones = self._accepted.get(cls, [])
        if not sel or sel[0] >= len(zones):
            self._set_status("Pick an accepted zone to delete.")
            return
        removed = zones.pop(sel[0])
        if self._selected_zone is removed:
            self._selected_zone = None
            self._editor_owner = None
        self._revalidate()
        self._refresh_panels()
        self._redraw_overlays()
        self._set_status(f"Deleted {removed.name}.")

    def _on_save_exclusions(self):
        path = self._exclusions_path or DEFAULT_EXCLUSIONS_PATH
        try:
            save_exclusions(path, self._exclusions)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Save exclusions failed", str(exc), parent=self)
            return
        self._exclusions_path = path
        messagebox.showinfo("Exclusions saved", f"Wrote {path}", parent=self)
        self._set_status(f"Exclusions saved → {path}")

    def _on_export(self):
        self._revalidate()
        excl_by_class = {c: self._exclusion_rects(c) for c in self._classes}
        try:
            out_dir = export_all(
                export_root=default_export_root(), version=self._version,
                target_classes=self._classes, zones_by_class=self._accepted,
                candidates_by_class=self._candidates, validation_report=self._validation,
                exclusion_rects_by_class=excl_by_class, ref_height=self._loaded.ref_height,
                frame_shape=self._loaded.frame_shape, input_dir=self._loaded.input_dir,
                summary_path=self._loaded.summary_path, exclusions_path=self._exclusions_path,
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Export failed", str(exc), parent=self)
            return
        messagebox.showinfo(
            "Exported",
            f"Wrote discovered_zones.{{json,yaml}} + report.json + <class>_preview.png to:\n{out_dir}\n\n"
            "discovered_zones is a HAND-MERGE fragment — Tool 8 never edits config/config.yaml.",
            parent=self,
        )
        self._set_status(f"Exported → {out_dir}")

    # ----------------------------------------------------------------- misc
    def _set_status(self, text: str):
        self._status.config(text=text)
