"""Main application window for the Warden Image Inspector."""

import sys
import tkinter as tk
from tkinter import filedialog, messagebox

from PIL import Image

from .canvas import ImageCanvas
from .modes import ColorPickerMode, HSVFilterMode, ROIMode


class InspectorApp(tk.Tk):
    """Top-level window: toolbar + image canvas."""

    def __init__(self, image_path=None):
        super().__init__()

        # If no path provided, open file dialog using this Tk root (avoids
        # creating and destroying a separate Tk instance).
        if image_path is None:
            self.withdraw()
            image_path = filedialog.askopenfilename(
                title="Select an image",
                filetypes=[
                    ("Image files", "*.png *.jpg *.jpeg *.bmp"),
                    ("All files", "*.*"),
                ],
            )
            if not image_path:
                self.destroy()
                print("No image selected. Exiting.", file=sys.stderr)
                sys.exit(1)
            self.deiconify()

        self.image_path = image_path
        self.last_pick_hsv = (0, 0, 0)

        self.title(f"Warden Image Inspector \u2014 {image_path}")
        self.geometry("1200x800")
        self.minsize(640, 480)

        # Load image
        try:
            self._pil_image = Image.open(image_path).convert("RGB")
        except Exception as e:
            messagebox.showerror("Image Error", f"Could not open image:\n{e}")
            self.destroy()
            sys.exit(1)

        # --- Toolbar ---
        self.toolbar = tk.Frame(self, relief=tk.RAISED, bd=1)
        self.toolbar.pack(side=tk.TOP, fill=tk.X)

        # Mode switching
        self._mode_var = tk.StringVar(value="color_picker")
        modes_frame = tk.Frame(self.toolbar)
        modes_frame.pack(side=tk.LEFT, padx=4, pady=2)

        for text, value in [
            ("Color Picker", "color_picker"),
            ("HSV Filter", "hsv_filter"),
            ("ROI", "roi"),
        ]:
            tk.Radiobutton(
                modes_frame,
                text=text,
                variable=self._mode_var,
                value=value,
                command=self._on_mode_change,
            ).pack(side=tk.LEFT, padx=2)

        # Color swatch
        self._swatch = tk.Canvas(self.toolbar, width=24, height=24, bd=1, relief=tk.SUNKEN)
        self._swatch.pack(side=tk.LEFT, padx=(8, 4), pady=2)
        self._swatch_rect = self._swatch.create_rectangle(0, 0, 24, 24, fill="#000000", outline="")

        # Status label
        self._status_label = tk.Label(self.toolbar, text="", anchor=tk.W, padx=8)
        self._status_label.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=2)

        # --- Canvas ---
        self._canvas = ImageCanvas(self, self._pil_image)
        self._canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # --- Modes ---
        self._modes = {
            "color_picker": ColorPickerMode(),
            "hsv_filter": HSVFilterMode(),
            "roi": ROIMode(),
        }
        self._active_mode = None
        self._on_mode_change()

    # ------------------------------------------------------------------
    # Public helpers for modes
    # ------------------------------------------------------------------

    def set_status(self, text):
        self._status_label.config(text=text)

    def set_swatch_color(self, r, g, b):
        color = f"#{r:02x}{g:02x}{b:02x}"
        self._swatch.itemconfig(self._swatch_rect, fill=color)

    # ------------------------------------------------------------------
    # Mode switching
    # ------------------------------------------------------------------

    def _on_mode_change(self):
        if self._active_mode is not None:
            self._active_mode.deactivate()

        mode_key = self._mode_var.get()
        self._active_mode = self._modes[mode_key]
        self._active_mode.activate(self._canvas, self)
