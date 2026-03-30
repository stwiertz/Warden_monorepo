"""MinimapZoneSelectorApp — main GUI application."""

import copy
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from PIL import Image

from tools.frame_labeler import MAP_LABELS
from tools.image_inspector.canvas import ImageCanvas
from utils.image import extract_roi, scale_roi

from .config_manager import ConfigManager
from .data_loader import MinimapDataLoader
from .hsv_editor import HSVEditor
from .stats_panel import StatsPanel
from .validator import ValidationResult, ZoneValidator
from .zone_model import MinimapConfig, Zone

ZONE_COLORS = ["cyan", "lime", "magenta", "yellow", "orange", "red"]

DEFAULT_ROI = {"name": "minimap", "x": 104, "y": 0, "width": 234, "height": 264}

REF_W, REF_H = 1920, 1080


class MinimapZoneSelectorApp(tk.Tk):
    """Main application window for the Minimap Zone Selector tool."""

    def __init__(self, labeled_dir: str, config_path: str):
        super().__init__()
        self.title("Minimap Zone Selector")
        self.geometry("1400x900")
        self.minsize(1000, 700)

        self._config_path = config_path
        self._config_manager = ConfigManager(config_path)

        # Load existing configs
        self._configs: list[MinimapConfig] = self._config_manager.load()
        self._active_config: MinimapConfig | None = None

        # Determine the ROI to use for loading data
        roi = self._resolve_roi()

        # Load labeled images
        self._loader = MinimapDataLoader(labeled_dir, roi, REF_W, REF_H)

        # Current state
        self._selected_map: str = ""
        self._current_frame_index: int = 0
        self._canvas: ImageCanvas | None = None
        self._zone_overlays: list[tuple] = []  # (zone_id, rect_id, label_id)
        self._validation_result: ValidationResult | None = None

        # Zone drawing state
        self._draw_start_cx = 0
        self._draw_start_cy = 0
        self._drag_rect_id = None
        self._zone_counter = 0  # monotonic ID counter per session

        self._build_ui()
        self._init_state()

    def _resolve_roi(self) -> dict:
        if self._configs:
            return dict(self._configs[0].roi)
        return dict(DEFAULT_ROI)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        # --- Toolbar ---
        toolbar = tk.Frame(self, relief=tk.RAISED, bd=1)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=4, pady=2)

        # Version selector
        tk.Label(toolbar, text="Config:").pack(side=tk.LEFT, padx=(4, 2))
        self._version_var = tk.StringVar()
        self._version_combo = ttk.Combobox(
            toolbar, textvariable=self._version_var, state="readonly", width=14
        )
        self._version_combo.pack(side=tk.LEFT, padx=2)
        self._version_combo.bind("<<ComboboxSelected>>", self._on_version_change)

        tk.Button(toolbar, text="New", command=self._new_config).pack(
            side=tk.LEFT, padx=2
        )
        tk.Button(toolbar, text="Clone", command=self._clone_config).pack(
            side=tk.LEFT, padx=2
        )
        tk.Button(toolbar, text="Delete", command=self._delete_config).pack(
            side=tk.LEFT, padx=2
        )

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(
            side=tk.LEFT, fill=tk.Y, padx=6, pady=2
        )

        # Map selector
        tk.Label(toolbar, text="Map:").pack(side=tk.LEFT, padx=(4, 2))
        self._map_var = tk.StringVar()
        self._map_combo = ttk.Combobox(
            toolbar, textvariable=self._map_var, state="readonly", width=14
        )
        self._map_combo.pack(side=tk.LEFT, padx=2)
        self._map_combo.bind("<<ComboboxSelected>>", self._on_map_change)

        # Image nav
        tk.Button(toolbar, text="\u25c0", command=self._prev_image).pack(
            side=tk.LEFT, padx=2
        )
        self._frame_label = tk.Label(toolbar, text="0/0")
        self._frame_label.pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="\u25b6", command=self._next_image).pack(
            side=tk.LEFT, padx=2
        )

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(
            side=tk.LEFT, fill=tk.Y, padx=6, pady=2
        )

        tk.Button(toolbar, text="Export", command=self._export).pack(
            side=tk.LEFT, padx=4
        )

        # --- Main content ---
        content = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashwidth=6)
        content.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # Left: canvas placeholder
        self._canvas_frame = tk.Frame(content, bg="#2b2b2b")
        content.add(self._canvas_frame, width=700)

        # Right: stats + HSV editor
        right_panel = tk.Frame(content)
        content.add(right_panel, width=400)

        self._stats_panel = StatsPanel(
            right_panel,
            on_delete_zone=self._delete_zone,
            on_weight_override_change=self._on_weight_override,
            on_select_zone=self._on_select_zone,
        )
        self._stats_panel.pack(fill=tk.BOTH, expand=True)

        self._hsv_editor = HSVEditor(right_panel, on_change=self._on_hsv_change)
        self._hsv_editor.pack(fill=tk.X, padx=4, pady=(4, 4))

        # Status bar
        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, anchor="w", fg="gray").pack(
            side=tk.BOTTOM, fill=tk.X, padx=4, pady=2
        )

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def _init_state(self):
        self._refresh_version_combo()

        # Select first config or create empty state
        if self._configs:
            self._version_var.set(self._configs[0].id)
            self._active_config = self._configs[0]
        else:
            self._active_config = None

        # Populate map selector with all MAP_LABELS (annotate missing ones)
        # _map_display_to_label maps display string -> map label for reliable lookup
        self._map_display_to_label = {}
        map_values = []
        for m in MAP_LABELS:
            count = self._loader.frame_count(m)
            suffix = f" ({count})" if count > 0 else " (no images)"
            display = m + suffix
            map_values.append(display)
            self._map_display_to_label[display] = m
        self._map_combo["values"] = map_values

        # Select first map with images
        available = self._loader.all_map_names()
        if available:
            self._selected_map = available[0]
            idx = MAP_LABELS.index(self._selected_map)
            self._map_combo.current(idx)
        elif MAP_LABELS:
            self._selected_map = MAP_LABELS[0]
            self._map_combo.current(0)

        self._current_frame_index = 0
        self._load_canvas_image()
        self._run_validation()

    def _refresh_version_combo(self):
        ids = [c.id for c in self._configs]
        self._version_combo["values"] = ids

    # ------------------------------------------------------------------
    # Canvas management
    # ------------------------------------------------------------------

    def _load_canvas_image(self):
        """Load the current map/frame image into the canvas."""
        # Destroy old canvas
        if self._canvas is not None:
            self._canvas.destroy()
            self._canvas = None
        self._zone_overlays.clear()

        roi = self._get_active_roi()
        pil_img = self._loader.get_reference_image(
            self._selected_map, self._current_frame_index
        )

        if pil_img is None:
            # No image — show placeholder
            placeholder = Image.new("RGB", (roi["width"], roi["height"]), (43, 43, 43))
            self._canvas = ImageCanvas(self._canvas_frame, placeholder)
            self._canvas.pack(fill=tk.BOTH, expand=True)
            self._update_frame_label()
            return

        # Crop to minimap ROI
        img_w, img_h = pil_img.size
        scale_x = img_w / REF_W
        scale_y = img_h / REF_H
        rx = int(roi["x"] * scale_x)
        ry = int(roi["y"] * scale_y)
        rw = int(roi["width"] * scale_x)
        rh = int(roi["height"] * scale_y)
        cropped = pil_img.crop((rx, ry, rx + rw, ry + rh))

        self._canvas = ImageCanvas(self._canvas_frame, cropped)
        self._canvas.pack(fill=tk.BOTH, expand=True)

        # Bind zone drawing
        self._canvas.bind("<ButtonPress-1>", self._on_draw_start)
        self._canvas.bind("<B1-Motion>", self._on_draw_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_draw_release)
        self._canvas.set_overlay_redraw(self._redraw_zone_overlays)

        self._update_frame_label()
        self._redraw_zone_overlays()

    def _get_active_roi(self) -> dict:
        if self._active_config and self._active_config.roi:
            return self._active_config.roi
        return dict(DEFAULT_ROI)

    def _update_frame_label(self):
        total = self._loader.frame_count(self._selected_map)
        current = self._current_frame_index + 1 if total > 0 else 0
        self._frame_label.config(text=f"{current}/{total}")

    # ------------------------------------------------------------------
    # Zone drawing
    # ------------------------------------------------------------------

    def _on_draw_start(self, event):
        self._draw_start_cx = event.x
        self._draw_start_cy = event.y
        if self._drag_rect_id and self._canvas:
            self._canvas.delete(self._drag_rect_id)
            self._drag_rect_id = None

    def _on_draw_drag(self, event):
        if self._canvas is None:
            return
        if self._drag_rect_id:
            self._canvas.delete(self._drag_rect_id)
        self._drag_rect_id = self._canvas.create_rectangle(
            self._draw_start_cx, self._draw_start_cy, event.x, event.y,
            outline="cyan", dash=(4, 4), width=2, tags="overlay",
        )

    def _on_draw_release(self, event):
        if self._canvas is None or self._active_config is None:
            return
        if self._drag_rect_id:
            self._canvas.delete(self._drag_rect_id)
            self._drag_rect_id = None

        # Check if map has images
        if self._loader.frame_count(self._selected_map) == 0:
            self._status_var.set("Cannot draw zones on a map with no images")
            return

        start = self._canvas.canvas_to_image(self._draw_start_cx, self._draw_start_cy)
        end = self._canvas.canvas_to_image(event.x, event.y)
        if start is None or end is None:
            return

        x1, y1 = start
        x2, y2 = end
        crop_x = min(x1, x2)
        crop_y = min(y1, y2)
        crop_w = abs(x2 - x1)
        crop_h = abs(y2 - y1)

        if crop_w == 0 or crop_h == 0:
            return

        # Convert crop coords to full-frame reference coords
        roi = self._get_active_roi()
        pil_img = self._loader.get_reference_image(
            self._selected_map, self._current_frame_index
        )
        if pil_img is None:
            return
        frame_w, frame_h = pil_img.size

        # Crop coords are in the cropped minimap image pixel space.
        # Convert to full-frame reference coords:
        #   crop_pixel -> fraction of ROI -> reference ROI offset + fraction * ROI size
        crop_img_w, crop_img_h = self._canvas.image_size
        ref_x = round(roi["x"] + crop_x / crop_img_w * roi["width"])
        ref_y = round(roi["y"] + crop_y / crop_img_h * roi["height"])
        ref_w = round(crop_w / crop_img_w * roi["width"])
        ref_h = round(crop_h / crop_img_h * roi["height"])

        if ref_w <= 0 or ref_h <= 0:
            return

        # Create zone
        zones = self._active_config.maps.setdefault(self._selected_map, [])
        zone_id = f"zone_{self._zone_counter}"
        self._zone_counter += 1
        zone = Zone(
            zone_id=zone_id,
            x=ref_x, y=ref_y, width=ref_w, height=ref_h,
            h_center=0, h_tol=180,
            s_center=0, s_tol=12,
            v_center=100, v_tol=15,
            min_ratio=0.3,
            weight=0.0,
            weight_override=False,
        )
        zones.append(zone)

        self._status_var.set(
            f"Added {zone_id}: ref({ref_x}, {ref_y}, {ref_w}, {ref_h})"
        )
        self._run_validation()
        self._redraw_zone_overlays()

    # ------------------------------------------------------------------
    # Zone overlays
    # ------------------------------------------------------------------

    def _redraw_zone_overlays(self):
        """Clear and redraw all zone rectangles on the canvas."""
        if self._canvas is None:
            return

        # Remove old overlays
        for _, rect_id, label_id in self._zone_overlays:
            self._canvas.delete(rect_id)
            self._canvas.delete(label_id)
        self._zone_overlays.clear()

        if self._active_config is None:
            return

        zones = self._active_config.maps.get(self._selected_map, [])
        roi = self._get_active_roi()

        # We need to convert zone ref coords -> crop image coords
        # Zone is in ref resolution. Crop image is the minimap ROI area.
        # crop_x = (zone.x - roi.x) / ROI_w_ref * crop_img_w
        crop_w, crop_h = self._canvas.image_size
        roi_w_ref = roi["width"]
        roi_h_ref = roi["height"]

        for i, zone in enumerate(zones):
            # Zone position relative to ROI in reference coords
            zx = zone.x - roi["x"]
            zy = zone.y - roi["y"]

            # Scale to crop image pixel coords
            img_x = zx / roi_w_ref * crop_w
            img_y = zy / roi_h_ref * crop_h
            img_x2 = (zx + zone.width) / roi_w_ref * crop_w
            img_y2 = (zy + zone.height) / roi_h_ref * crop_h

            # Convert to canvas coords
            cx1, cy1 = self._canvas.image_to_canvas(img_x, img_y)
            cx2, cy2 = self._canvas.image_to_canvas(img_x2, img_y2)

            color = ZONE_COLORS[i % len(ZONE_COLORS)]
            rect_id = self._canvas.create_rectangle(
                cx1, cy1, cx2, cy2,
                outline=color, width=2, tags="overlay",
            )
            label_cy = cy1 + 12 if cy1 < 15 else cy1 - 5
            label_id = self._canvas.create_text(
                cx1 + 3, label_cy, text=zone.zone_id, fill=color,
                anchor=tk.NW, font=("Consolas", 9), tags="overlay",
            )
            self._zone_overlays.append((zone.zone_id, rect_id, label_id))

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _run_validation(self):
        if self._active_config is None:
            return

        # Update auto-weights before validation
        result = ZoneValidator.compute(self._active_config, self._loader)
        self._validation_result = result

        # Apply auto-weights to non-override zones
        for map_label, zones in self._active_config.maps.items():
            for zone in zones:
                if not zone.weight_override:
                    zs = result.zone_stats.get(zone.zone_id)
                    if zs:
                        zone.weight = zs.auto_weight

        # Re-run with updated weights
        result = ZoneValidator.compute(self._active_config, self._loader)
        self._validation_result = result

        self._stats_panel.refresh(result, self._active_config, self._selected_map)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_version_change(self, event=None):
        selected_id = self._version_var.get()
        for c in self._configs:
            if c.id == selected_id:
                self._active_config = c
                break
        self._load_canvas_image()
        self._run_validation()

    def _on_map_change(self, event=None):
        raw = self._map_var.get()
        map_name = self._map_display_to_label.get(raw, raw)
        self._selected_map = map_name
        self._current_frame_index = 0
        self._load_canvas_image()
        self._run_validation()

    def _prev_image(self):
        if self._current_frame_index > 0:
            self._current_frame_index -= 1
            self._load_canvas_image()

    def _next_image(self):
        total = self._loader.frame_count(self._selected_map)
        if self._current_frame_index < total - 1:
            self._current_frame_index += 1
            self._load_canvas_image()

    def _on_hsv_change(self, zone: Zone):
        """Called after HSVEditor Apply with updated zone."""
        self._run_validation()
        self._hsv_editor.load_zone(zone)  # refresh weight display

    def _on_select_zone(self, zone_id: str):
        if self._active_config is None:
            return
        zones = self._active_config.maps.get(self._selected_map, [])
        for zone in zones:
            if zone.zone_id == zone_id:
                self._hsv_editor.load_zone(zone)
                break

    def _on_weight_override(self, zone_id: str, override: bool, manual_weight: float):
        if self._active_config is None:
            return
        zones = self._active_config.maps.get(self._selected_map, [])
        for zone in zones:
            if zone.zone_id == zone_id:
                zone.weight_override = override
                if override:
                    zone.weight = manual_weight
                else:
                    # Revert to auto-weight
                    if self._validation_result:
                        zs = self._validation_result.zone_stats.get(zone_id)
                        if zs:
                            zone.weight = zs.auto_weight
                break
        self._run_validation()

    def _delete_zone(self, zone_id: str):
        if self._active_config is None:
            return
        zones = self._active_config.maps.get(self._selected_map, [])
        self._active_config.maps[self._selected_map] = [
            z for z in zones if z.zone_id != zone_id
        ]
        self._run_validation()
        self._redraw_zone_overlays()

    # ------------------------------------------------------------------
    # Config version CRUD
    # ------------------------------------------------------------------

    def _new_config(self):
        new_id = simpledialog.askstring("New Config", "Enter config ID:")
        if not new_id:
            return
        # Check for duplicate
        if any(c.id == new_id for c in self._configs):
            messagebox.showerror("Error", f"Config '{new_id}' already exists.")
            return

        roi = self._resolve_roi()
        cfg = MinimapConfig(
            id=new_id,
            roi=roi,
            identification_threshold=0.6,
            maps={},
        )
        self._configs.append(cfg)
        self._refresh_version_combo()
        self._version_var.set(new_id)
        self._active_config = cfg
        self._load_canvas_image()
        self._run_validation()

    def _clone_config(self):
        if self._active_config is None:
            messagebox.showinfo("Info", "No config selected to clone.")
            return
        new_id = simpledialog.askstring(
            "Clone Config", f"Clone '{self._active_config.id}' as:"
        )
        if not new_id:
            return
        if any(c.id == new_id for c in self._configs):
            messagebox.showerror("Error", f"Config '{new_id}' already exists.")
            return

        cloned = copy.deepcopy(self._active_config)
        cloned.id = new_id
        self._configs.append(cloned)
        self._refresh_version_combo()
        self._version_var.set(new_id)
        self._active_config = cloned
        self._load_canvas_image()
        self._run_validation()

    def _delete_config(self):
        if self._active_config is None:
            return
        if not messagebox.askyesno(
            "Delete Config",
            f"Delete config '{self._active_config.id}'?",
        ):
            return
        deleted_id = self._active_config.id
        self._configs = [
            c for c in self._configs if c.id != deleted_id
        ]
        self._config_manager.save(self._configs)
        self._refresh_version_combo()
        if self._configs:
            self._version_var.set(self._configs[0].id)
            self._active_config = self._configs[0]
        else:
            self._version_var.set("")
            self._active_config = None
        self._load_canvas_image()
        self._run_validation()

    def _export(self):
        if self._active_config is None:
            messagebox.showinfo("Info", "No config to export.")
            return
        # Save all in-memory configs to disk (preserves current references)
        self._config_manager.save(self._configs)
        self._status_var.set(
            f"Exported '{self._active_config.id}' to {self._config_path}"
        )
