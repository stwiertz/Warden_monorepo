"""Interaction modes for the Warden Image Inspector."""

import colorsys
import tkinter as tk

import cv2
import numpy as np
from PIL import Image

from . import logger

# HSV scale conversions:
# - Color Picker uses colorsys (H:0-1, S:0-1, V:0-1) → displayed as H:0-360, S:0-100, V:0-100
# - HSV Filter converts user-facing values to OpenCV scale (H:0-179, S:0-255, V:0-255)
_H_USER_TO_CV = 179 / 360  # multiply user H (0-360) to get OpenCV H (0-179)
_SV_USER_TO_CV = 255 / 100  # multiply user S/V (0-100) to get OpenCV S/V (0-255)


# ---------------------------------------------------------------------------
# Color Picker Mode
# ---------------------------------------------------------------------------

class ColorPickerMode:
    """Click to read HSV/RGB values at a pixel."""

    def __init__(self):
        self._canvas = None
        self._app = None
        self._click_binding = None

    def activate(self, canvas, app):
        self._canvas = canvas
        self._app = app
        self._click_binding = canvas.bind("<ButtonPress-1>", self._on_click)
        app.set_status("Color Picker: click on the image to pick a color")

    def deactivate(self):
        if self._canvas and self._click_binding:
            self._canvas.unbind("<ButtonPress-1>", self._click_binding)
        self._click_binding = None

    def _on_click(self, event):
        coords = self._canvas.canvas_to_image(event.x, event.y)
        if coords is None:
            return

        ix, iy = coords
        img = self._canvas.original_image
        r, g, b = img.getpixel((ix, iy))[:3]

        # colorsys expects 0-1 floats, we scale to user-facing H:0-360, S/V:0-100
        h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
        h_deg = round(h * 360)
        s_pct = round(s * 100)
        v_pct = round(v * 100)

        text = (
            f"HSV({h_deg}, {s_pct}, {v_pct})  "
            f"RGB({r}, {g}, {b})  "
            f"@ ({ix}, {iy})"
        )
        self._app.set_status(text)
        self._app.set_swatch_color(r, g, b)

        # Store last pick for HSV filter pre-population
        self._app.last_pick_hsv = (h_deg, s_pct, v_pct)

        logger.log_entry(
            self._app.image_path,
            "color_pick",
            {"x": ix, "y": iy, "rgb": [r, g, b], "hsv": [h_deg, s_pct, v_pct]},
        )


# ---------------------------------------------------------------------------
# HSV Filter Preview Mode
# ---------------------------------------------------------------------------

class HSVFilterMode:
    """Enter HSV range, preview matching pixels on the image."""

    def __init__(self):
        self._canvas = None
        self._app = None
        self._filter_frame = None

    def activate(self, canvas, app):
        self._canvas = canvas
        self._app = app
        self._build_ui()
        app.set_status("HSV Filter: enter values and click Apply")

    def deactivate(self):
        if self._filter_frame:
            self._filter_frame.destroy()
            self._filter_frame = None
        # Restore original image
        if self._canvas:
            self._canvas.reset_display_image()

    def _build_ui(self):
        self._filter_frame = tk.Frame(self._app.toolbar)
        self._filter_frame.pack(side=tk.LEFT, padx=(10, 0))

        # Pre-populate from last color pick
        h_val, s_val, v_val = self._app.last_pick_hsv

        labels = ["H", "S", "V"]
        defaults = [h_val, s_val, v_val]
        tolerances = [10, 40, 40]

        self._center_vars = []
        self._tol_vars = []

        for i, (label, default, tol) in enumerate(zip(labels, defaults, tolerances)):
            tk.Label(self._filter_frame, text=label).grid(row=0, column=i * 2, padx=2)
            cv = tk.StringVar(value=str(default))
            self._center_vars.append(cv)
            e = tk.Entry(self._filter_frame, textvariable=cv, width=4)
            e.grid(row=0, column=i * 2 + 1, padx=1)

            tk.Label(self._filter_frame, text="\u00b1").grid(row=1, column=i * 2, padx=2)
            tv = tk.StringVar(value=str(tol))
            self._tol_vars.append(tv)
            e2 = tk.Entry(self._filter_frame, textvariable=tv, width=4)
            e2.grid(row=1, column=i * 2 + 1, padx=1)

        btn_frame = tk.Frame(self._filter_frame)
        btn_frame.grid(row=0, column=6, rowspan=2, padx=(6, 0))
        tk.Button(btn_frame, text="Apply", command=self._apply).pack(side=tk.TOP, pady=1)
        tk.Button(btn_frame, text="Clear", command=self._clear).pack(side=tk.TOP, pady=1)

    def _apply(self):
        try:
            h_c = int(self._center_vars[0].get())
            s_c = int(self._center_vars[1].get())
            v_c = int(self._center_vars[2].get())
            h_t = int(self._tol_vars[0].get())
            s_t = int(self._tol_vars[1].get())
            v_t = int(self._tol_vars[2].get())
        except ValueError:
            self._app.set_status("HSV Filter: enter integer values")
            return

        # Validate ranges
        if not (0 <= h_c <= 360 and 0 <= s_c <= 100 and 0 <= v_c <= 100):
            self._app.set_status("HSV Filter: H must be 0-360, S and V must be 0-100")
            return
        if h_t < 0 or s_t < 0 or v_t < 0:
            self._app.set_status("HSV Filter: tolerances must be non-negative")
            return

        img = self._canvas.original_image
        bgr = np.array(img)[:, :, ::-1]  # PIL RGB -> OpenCV BGR
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

        # Convert user-facing values to OpenCV scale (H:0-179, S:0-255, V:0-255)
        h_lo = round((h_c - h_t) * _H_USER_TO_CV)
        h_hi = round((h_c + h_t) * _H_USER_TO_CV)
        s_lo = round((s_c - s_t) * _SV_USER_TO_CV)
        s_hi = round((s_c + s_t) * _SV_USER_TO_CV)
        v_lo = round((v_c - v_t) * _SV_USER_TO_CV)
        v_hi = round((v_c + v_t) * _SV_USER_TO_CV)

        # Clamp S and V
        s_lo, s_hi = max(0, s_lo), min(255, s_hi)
        v_lo, v_hi = max(0, v_lo), min(255, v_hi)

        # Handle hue wraparound
        if h_lo < 0 or h_hi > 179:
            # Split into two ranges for the wrapped hue
            mask1 = cv2.inRange(
                hsv,
                np.array([max(0, h_lo % 180), s_lo, v_lo]),
                np.array([179, s_hi, v_hi]),
            )
            mask2 = cv2.inRange(
                hsv,
                np.array([0, s_lo, v_lo]),
                np.array([min(179, h_hi % 180), s_hi, v_hi]),
            )
            mask = cv2.bitwise_or(mask1, mask2)
        else:
            mask = cv2.inRange(
                hsv,
                np.array([h_lo, s_lo, v_lo]),
                np.array([h_hi, s_hi, v_hi]),
            )

        # Composite: in-range at full color, out-of-range grayed at 30% opacity
        rgb = np.array(img)
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        gray_rgb = np.stack([gray, gray, gray], axis=-1)

        mask_3ch = mask[:, :, np.newaxis] / 255.0
        composite = (rgb * mask_3ch + gray_rgb * (1.0 - mask_3ch) * 0.3).astype(
            np.uint8
        )

        overlay = Image.fromarray(composite)
        self._canvas.set_display_image(overlay)

        # Clamp logged values to valid user-space ranges
        h_log_lo = max(0, h_c - h_t) if (h_c - h_t) >= 0 else (h_c - h_t) % 360
        h_log_hi = min(360, h_c + h_t) if (h_c + h_t) <= 360 else (h_c + h_t) % 360
        s_log_lo = max(0, s_c - s_t)
        s_log_hi = min(100, s_c + s_t)
        v_log_lo = max(0, v_c - v_t)
        v_log_hi = min(100, v_c + v_t)

        self._app.set_status(
            f"HSV Filter applied: H={h_c}\u00b1{h_t} S={s_c}\u00b1{s_t} V={v_c}\u00b1{v_t}"
        )

        logger.log_entry(
            self._app.image_path,
            "hsv_filter",
            {
                "h": [h_log_lo, h_log_hi],
                "s": [s_log_lo, s_log_hi],
                "v": [v_log_lo, v_log_hi],
            },
        )

    def _clear(self):
        self._canvas.reset_display_image()
        self._app.set_status("HSV Filter cleared")


# ---------------------------------------------------------------------------
# ROI Selection Mode
# ---------------------------------------------------------------------------

class ROIMode:
    """Click-drag to select a rectangular ROI, or input coordinates manually."""

    # Cycle through colors for multiple ROIs
    _COLORS = ["cyan", "lime", "magenta", "yellow", "orange", "red"]

    # Reference resolution used in config for ROI coordinates
    REF_W, REF_H = 1920, 1080

    def __init__(self):
        self._canvas = None
        self._app = None
        self._press_binding = None
        self._drag_binding = None
        self._release_binding = None
        self._drag_rect_id = None
        self._start_cx = 0
        self._start_cy = 0
        # Persistent ROIs: list of (x, y, w, h, color, canvas_rect_id, label_id)
        self._rois = []
        self._input_frame = None
        self._scale_x = 1.0
        self._scale_y = 1.0

    def activate(self, canvas, app):
        self._canvas = canvas
        self._app = app
        # Compute scale from image pixels to reference resolution
        img_w, img_h = canvas.image_size
        self._scale_x = self.REF_W / img_w
        self._scale_y = self.REF_H / img_h
        self._press_binding = canvas.bind("<ButtonPress-1>", self._on_press)
        self._drag_binding = canvas.bind("<B1-Motion>", self._on_drag)
        self._release_binding = canvas.bind("<ButtonRelease-1>", self._on_release)
        canvas.set_overlay_redraw(self._redraw_overlays)
        self._build_input_ui()
        app.set_status(
            f"ROI: drag to select, or enter coordinates  |  "
            f"Image: {img_w}x{img_h}  Ref: {self.REF_W}x{self.REF_H}"
        )

    def deactivate(self):
        if self._canvas:
            if self._press_binding:
                self._canvas.unbind("<ButtonPress-1>", self._press_binding)
            if self._drag_binding:
                self._canvas.unbind("<B1-Motion>", self._drag_binding)
            if self._release_binding:
                self._canvas.unbind("<ButtonRelease-1>", self._release_binding)
            if self._drag_rect_id:
                self._canvas.delete(self._drag_rect_id)
            self._canvas.set_overlay_redraw(None)
            self._clear_all_overlays()
        if self._input_frame:
            self._input_frame.destroy()
            self._input_frame = None
        self._press_binding = None
        self._drag_binding = None
        self._release_binding = None
        self._drag_rect_id = None

    # ------------------------------------------------------------------
    # Input UI
    # ------------------------------------------------------------------

    def _build_input_ui(self):
        self._input_frame = tk.Frame(self._app.toolbar)
        self._input_frame.pack(side=tk.LEFT, padx=(10, 0), pady=2)

        self._name_var = tk.StringVar(value="")
        self._x_var = tk.StringVar(value="0")
        self._y_var = tk.StringVar(value="0")
        self._w_var = tk.StringVar(value="100")
        self._h_var = tk.StringVar(value="100")

        for label, var, width in [
            ("Name", self._name_var, 8),
            ("X", self._x_var, 5),
            ("Y", self._y_var, 5),
            ("W", self._w_var, 5),
            ("H", self._h_var, 5),
        ]:
            tk.Label(self._input_frame, text=label).pack(side=tk.LEFT, padx=1)
            tk.Entry(self._input_frame, textvariable=var, width=width).pack(
                side=tk.LEFT, padx=1
            )

        tk.Button(self._input_frame, text="Add", command=self._add_from_input).pack(
            side=tk.LEFT, padx=(4, 2)
        )
        tk.Button(self._input_frame, text="Clear All", command=self._clear_all).pack(
            side=tk.LEFT, padx=2
        )

    def _add_from_input(self):
        try:
            x = int(self._x_var.get())
            y = int(self._y_var.get())
            w = int(self._w_var.get())
            h = int(self._h_var.get())
        except ValueError:
            self._app.set_status("ROI: x, y, w, h must be integers")
            return

        if w <= 0 or h <= 0:
            self._app.set_status("ROI: width and height must be > 0")
            return

        name = self._name_var.get().strip() or None
        self._add_roi(x, y, w, h, name=name)

    def _clear_all(self):
        self._clear_all_overlays()
        self._rois.clear()
        self._app.set_status("ROI: all cleared")

    # ------------------------------------------------------------------
    # ROI management
    # ------------------------------------------------------------------

    def _next_color(self):
        idx = len(self._rois) % len(self._COLORS)
        return self._COLORS[idx]

    def _to_ref(self, x, y, w, h):
        """Convert image-pixel ROI to reference resolution coordinates."""
        return (
            round(x * self._scale_x),
            round(y * self._scale_y),
            round(w * self._scale_x),
            round(h * self._scale_y),
        )

    def _add_roi(self, x, y, w, h, name=None):
        color = self._next_color()
        rect_id, label_id = self._draw_roi_overlay(x, y, w, h, color, name)
        self._rois.append((x, y, w, h, color, rect_id, label_id, name))

        rx, ry, rw, rh = self._to_ref(x, y, w, h)
        display_name = f" ({name})" if name else ""
        self._app.set_status(
            f"ROI{display_name}:  "
            f"img: x={x}, y={y}, w={w}, h={h}  |  "
            f"ref({self.REF_W}x{self.REF_H}): x={rx}, y={ry}, w={rw}, h={rh}"
        )

        logger.log_entry(
            self._app.image_path,
            "roi",
            {
                "x": x, "y": y, "width": w, "height": h, "name": name,
                "ref": {"x": rx, "y": ry, "width": rw, "height": rh},
            },
        )

    def _draw_roi_overlay(self, ix, iy, iw, ih, color, name=None):
        """Draw a rectangle in image-pixel coords, returns (rect_id, label_id)."""
        cx1, cy1 = self._canvas.image_to_canvas(ix, iy)
        cx2, cy2 = self._canvas.image_to_canvas(ix + iw, iy + ih)
        rect_id = self._canvas.create_rectangle(
            cx1, cy1, cx2, cy2,
            outline=color, width=2, tags="overlay",
        )
        label = name or f"{iw}x{ih}"
        label_cy = cy1 + 12 if cy1 < 15 else cy1 - 5
        label_id = self._canvas.create_text(
            cx1 + 3, label_cy, text=label, fill=color,
            anchor=tk.NW, font=("Consolas", 9), tags="overlay",
        )
        return rect_id, label_id

    def _redraw_overlays(self):
        """Reposition all ROI overlays after zoom/pan/resize."""
        for i, (x, y, w, h, color, rect_id, label_id, name) in enumerate(self._rois):
            cx1, cy1 = self._canvas.image_to_canvas(x, y)
            cx2, cy2 = self._canvas.image_to_canvas(x + w, y + h)
            self._canvas.coords(rect_id, cx1, cy1, cx2, cy2)
            label_cy = cy1 + 12 if cy1 < 15 else cy1 - 5
            self._canvas.coords(label_id, cx1 + 3, label_cy)

    def _clear_all_overlays(self):
        for (_, _, _, _, _, rect_id, label_id, _) in self._rois:
            self._canvas.delete(rect_id)
            self._canvas.delete(label_id)

    # ------------------------------------------------------------------
    # Click-drag (still works as before, but ROI persists)
    # ------------------------------------------------------------------

    def _on_press(self, event):
        self._start_cx = event.x
        self._start_cy = event.y
        if self._drag_rect_id:
            self._canvas.delete(self._drag_rect_id)
            self._drag_rect_id = None

    def _on_drag(self, event):
        if self._drag_rect_id:
            self._canvas.delete(self._drag_rect_id)
        self._drag_rect_id = self._canvas.create_rectangle(
            self._start_cx, self._start_cy, event.x, event.y,
            outline="cyan", dash=(4, 4), width=2, tags="overlay",
        )

    def _on_release(self, event):
        if self._drag_rect_id:
            self._canvas.delete(self._drag_rect_id)
            self._drag_rect_id = None

        start = self._canvas.canvas_to_image(self._start_cx, self._start_cy)
        end = self._canvas.canvas_to_image(event.x, event.y)

        if start is None or end is None:
            self._app.set_status("ROI: selection out of image bounds")
            return

        x1, y1 = start
        x2, y2 = end
        x = min(x1, x2)
        y = min(y1, y2)
        w = abs(x2 - x1)
        h = abs(y2 - y1)

        if w == 0 or h == 0:
            return

        # Populate input fields with the drawn values
        self._x_var.set(str(x))
        self._y_var.set(str(y))
        self._w_var.set(str(w))
        self._h_var.set(str(h))

        self._add_roi(x, y, w, h)
