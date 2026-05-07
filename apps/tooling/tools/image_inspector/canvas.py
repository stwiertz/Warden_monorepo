"""ImageCanvas — zoomable, pannable image display widget."""

import tkinter as tk
from PIL import Image, ImageTk


class ImageCanvas(tk.Canvas):
    """Canvas that displays a PIL Image with zoom and pan support.

    All coordinate methods map between canvas (display) space and
    original image pixel space.
    """

    # Zoom multiplier per scroll step
    ZOOM_STEP = 1.25
    MAX_ZOOM = 50.0  # max relative to fit-to-window

    def __init__(self, parent, pil_image, **kwargs):
        super().__init__(parent, bg="#2b2b2b", highlightthickness=0, **kwargs)

        self._original_image = pil_image
        self._img_w, self._img_h = pil_image.size

        # Display image (can be swapped for HSV filter overlay)
        self._display_image = pil_image

        # Zoom / pan state
        self._zoom = 1.0  # 1.0 = fit-to-window
        self._offset_x = 0.0  # image-pixel x at canvas top-left
        self._offset_y = 0.0  # image-pixel y at canvas top-left

        # Cached PhotoImage for tkinter display
        self._photo = None
        self._photo_id = None

        # Persistent background rectangle (avoids recreating each redraw)
        self._bg_id = self.create_rectangle(0, 0, 0, 0, fill="#2b2b2b", outline="")

        # Overlay redraw callback — modes can register a function that gets
        # called after every redraw so overlays stay in sync with zoom/pan.
        self._overlay_redraw_cb = None

        # Redraw throttling — coalesce rapid pan/zoom events
        self._redraw_pending = False

        # Bindings
        self.bind("<Configure>", self._on_resize)
        self.bind("<MouseWheel>", self._on_mousewheel)  # Windows / macOS
        self.bind("<Button-4>", lambda e: self._do_zoom(e, zoom_in=True))  # Linux up
        self.bind("<Button-5>", lambda e: self._do_zoom(e, zoom_in=False))  # Linux down

        # Pan via right-click drag.
        # Note: spec suggested canvas.scan_mark()/scan_dragto(), but those operate
        # on tkinter's internal scroll region which is incompatible with our
        # tile-based rendering. Custom offset tracking gives correct results.
        self.bind("<ButtonPress-3>", self._on_pan_start)
        self.bind("<B3-Motion>", self._on_pan_move)
        # Also support middle-click
        self.bind("<ButtonPress-2>", self._on_pan_start)
        self.bind("<B2-Motion>", self._on_pan_move)

        self._pan_start_x = 0
        self._pan_start_y = 0
        self._pan_start_offset_x = 0.0
        self._pan_start_offset_y = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def canvas_to_image(self, cx, cy):
        """Convert canvas (display) coordinates to original image pixel coordinates.

        Returns:
            (int, int): x, y in original image pixel space, or None if out of bounds.
        """
        cw = self.winfo_width()
        ch = self.winfo_height()
        if cw <= 1 or ch <= 1:
            return None

        fit_scale = self._fit_scale()
        effective_scale = fit_scale * self._zoom

        ix = self._offset_x + cx / effective_scale
        iy = self._offset_y + cy / effective_scale

        ix, iy = int(ix), int(iy)
        if 0 <= ix < self._img_w and 0 <= iy < self._img_h:
            return ix, iy
        return None

    def image_to_canvas(self, ix, iy):
        """Convert original image pixel coordinates to canvas (display) coordinates.

        Returns:
            (float, float): x, y in canvas pixel space.
        """
        fit_scale = self._fit_scale()
        effective_scale = fit_scale * self._zoom
        cx = (ix - self._offset_x) * effective_scale
        cy = (iy - self._offset_y) * effective_scale
        return cx, cy

    def set_overlay_redraw(self, callback):
        """Register a callback invoked after each redraw for overlay updates.

        The callback receives no arguments. Pass None to unregister.
        """
        self._overlay_redraw_cb = callback

    def set_display_image(self, pil_image):
        """Replace the displayed image (e.g. for HSV filter overlay).

        The replacement must have the same dimensions as the original image.
        """
        self._display_image = pil_image
        self._redraw()

    def reset_display_image(self):
        """Restore the original image."""
        self._display_image = self._original_image
        self._redraw()

    @property
    def original_image(self):
        return self._original_image

    @property
    def image_size(self):
        return self._img_w, self._img_h

    # ------------------------------------------------------------------
    # Zoom
    # ------------------------------------------------------------------

    def _fit_scale(self):
        """Scale factor that fits the full image into the current canvas."""
        cw = self.winfo_width()
        ch = self.winfo_height()
        if cw <= 1 or ch <= 1:
            return 1.0
        return min(cw / self._img_w, ch / self._img_h)

    def _on_mousewheel(self, event):
        # Windows: event.delta is ±120 per notch
        if event.delta > 0:
            self._do_zoom(event, zoom_in=True)
        elif event.delta < 0:
            self._do_zoom(event, zoom_in=False)

    def _do_zoom(self, event, zoom_in):
        old_zoom = self._zoom
        if zoom_in:
            new_zoom = old_zoom * self.ZOOM_STEP
        else:
            new_zoom = old_zoom / self.ZOOM_STEP

        # Clamp
        new_zoom = max(1.0, min(self.MAX_ZOOM, new_zoom))
        if new_zoom == old_zoom:
            return

        fit_scale = self._fit_scale()

        # Cursor position in image space before zoom
        cx, cy = event.x, event.y
        img_x = self._offset_x + cx / (fit_scale * old_zoom)
        img_y = self._offset_y + cy / (fit_scale * old_zoom)

        self._zoom = new_zoom

        # Adjust offset so the image point under the cursor stays put
        self._offset_x = img_x - cx / (fit_scale * new_zoom)
        self._offset_y = img_y - cy / (fit_scale * new_zoom)

        self._clamp_offset()
        self._redraw()

    # ------------------------------------------------------------------
    # Pan
    # ------------------------------------------------------------------

    def _on_pan_start(self, event):
        self._pan_start_x = event.x
        self._pan_start_y = event.y
        self._pan_start_offset_x = self._offset_x
        self._pan_start_offset_y = self._offset_y

    def _on_pan_move(self, event):
        fit_scale = self._fit_scale()
        effective_scale = fit_scale * self._zoom

        dx = (self._pan_start_x - event.x) / effective_scale
        dy = (self._pan_start_y - event.y) / effective_scale

        self._offset_x = self._pan_start_offset_x + dx
        self._offset_y = self._pan_start_offset_y + dy

        self._clamp_offset()
        self._schedule_redraw()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _clamp_offset(self):
        """Ensure the offset doesn't scroll past image edges."""
        fit_scale = self._fit_scale()
        effective_scale = fit_scale * self._zoom
        cw = self.winfo_width()
        ch = self.winfo_height()

        # Visible region size in image pixels
        vis_w = cw / effective_scale
        vis_h = ch / effective_scale

        if vis_w >= self._img_w:
            # Image fits horizontally — center it
            self._offset_x = -(vis_w - self._img_w) / 2
        else:
            self._offset_x = max(0, min(self._offset_x, self._img_w - vis_w))

        if vis_h >= self._img_h:
            self._offset_y = -(vis_h - self._img_h) / 2
        else:
            self._offset_y = max(0, min(self._offset_y, self._img_h - vis_h))

    def _on_resize(self, event):
        self._clamp_offset()
        self._redraw()

    def _schedule_redraw(self):
        """Coalesce rapid redraw requests (e.g. during pan) via after_idle."""
        if not self._redraw_pending:
            self._redraw_pending = True
            self.after_idle(self._do_deferred_redraw)

    def _do_deferred_redraw(self):
        self._redraw_pending = False
        self._redraw()

    def _redraw(self):
        cw = self.winfo_width()
        ch = self.winfo_height()
        if cw <= 1 or ch <= 1:
            return

        fit_scale = self._fit_scale()
        effective_scale = fit_scale * self._zoom

        # Visible region in image pixels
        vis_w = cw / effective_scale
        vis_h = ch / effective_scale

        # Crop box (in image pixel coords)
        left = max(0, int(self._offset_x))
        top = max(0, int(self._offset_y))
        right = min(self._img_w, int(self._offset_x + vis_w) + 1)
        bottom = min(self._img_h, int(self._offset_y + vis_h) + 1)

        if right <= left or bottom <= top:
            return

        # Crop the visible region from the display image
        tile = self._display_image.crop((left, top, right, bottom))

        # Scale tile to fill the canvas area it occupies
        tile_display_w = int((right - left) * effective_scale)
        tile_display_h = int((bottom - top) * effective_scale)
        if tile_display_w < 1 or tile_display_h < 1:
            return

        resample = Image.NEAREST if self._zoom > 4.0 else Image.LANCZOS
        tile = tile.resize((tile_display_w, tile_display_h), resample)

        # Position on canvas
        canvas_x = int((left - self._offset_x) * effective_scale)
        canvas_y = int((top - self._offset_y) * effective_scale)

        self._photo = ImageTk.PhotoImage(tile)

        # Update persistent background rectangle
        self.coords(self._bg_id, 0, 0, cw, ch)

        # Reuse or create the photo item
        if self._photo_id is not None:
            self.itemconfig(self._photo_id, image=self._photo)
            self.coords(self._photo_id, canvas_x, canvas_y)
        else:
            self._photo_id = self.create_image(
                canvas_x, canvas_y, anchor=tk.NW, image=self._photo
            )

        # Ensure overlays (ROI rectangles etc.) stay on top
        self.tag_raise("overlay")

        # Notify mode to reposition overlays
        if self._overlay_redraw_cb is not None:
            self._overlay_redraw_cb()
