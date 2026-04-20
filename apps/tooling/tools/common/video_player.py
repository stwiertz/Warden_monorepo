"""Interactive video player widget for Tk.

Wraps an OpenCV VideoCapture in a Tk frame with a canvas, timeline slider,
play/pause/restart controls, and a pluggable per-frame processor (used by
the minimap-view-mode "shader").

Design notes:
- Random-access seeking uses cv2.VideoCapture.set(CAP_PROP_POS_MSEC). This is
  good enough for a preview tool; exact-keyframe seeking isn't needed.
- Playback pacing is driven by tk.after() scheduling rather than a thread,
  to keep all Tk calls on the main thread.
- The widget exposes a frame_processor hook: the caller can install a
  callable that receives the raw BGR frame and returns a BGR frame to
  display. That's how the view-mode shader plugs in.
- The timeline can be clamped to a sub-range via set_time_range(start, end)
  so the slider only scrubs within that window. Used by the match-preview
  tool to restrict seeking to a single detected match.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

import cv2
import numpy as np
from PIL import Image, ImageTk


FrameProcessor = Callable[[np.ndarray, float], np.ndarray]
"""Takes (bgr_frame, timestamp_seconds), returns a BGR frame to display."""


def _format_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h:d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


class VideoPlayer(tk.Frame):
    """Self-contained video player widget.

    Public API:
        load(path)                         : open a video file
        play() / pause() / toggle_play()   : playback control
        restart()                          : seek to range start and pause
        seek(seconds)                      : seek to absolute timestamp
        set_time_range(start, end)         : clamp timeline window
        set_frame_processor(fn)            : install shader hook
        current_frame()                    : return the latest BGR frame
        current_time()                     : seconds (absolute in the file)
        canvas_to_video(cx, cy)            : map canvas coords -> frame pixels
        video_to_canvas(vx, vy)            : map frame pixels -> canvas coords
    """

    def __init__(self, parent, show_controls: bool = True, **kwargs):
        super().__init__(parent, **kwargs)

        self._cap: Optional[cv2.VideoCapture] = None
        self._video_w = 0
        self._video_h = 0
        self._fps = 30.0
        self._duration = 0.0
        self._range_start = 0.0
        self._range_end = 0.0

        self._playing = False
        self._after_id: Optional[str] = None
        self._last_bgr: Optional[np.ndarray] = None  # before processor
        self._last_displayed_bgr: Optional[np.ndarray] = None  # after processor
        self._last_ts = 0.0
        self._processor: Optional[FrameProcessor] = None

        # Cached display geometry for coord conversion.
        # Maps a frame pixel to canvas pixel via: cx = off_x + ix*scale
        self._display_offset = (0, 0)
        self._display_scale = 1.0

        # Listeners (used by app to react to pause/seek for ROI workflows).
        self._on_frame_listeners: list[Callable[[np.ndarray, float], None]] = []

        self._build_ui(show_controls)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self, show_controls: bool):
        self.canvas = tk.Canvas(
            self, bg="black", highlightthickness=0, cursor="crosshair"
        )
        self.canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", lambda e: self._redraw())

        self._photo: Optional[ImageTk.PhotoImage] = None
        self._photo_id: Optional[int] = None

        if not show_controls:
            return

        controls = tk.Frame(self)
        controls.pack(side=tk.BOTTOM, fill=tk.X, padx=4, pady=4)

        self._play_btn = tk.Button(
            controls, text="\u25b6", width=3, command=self.toggle_play
        )
        self._play_btn.pack(side=tk.LEFT)

        tk.Button(
            controls, text="\u23ee", width=3, command=self.restart
        ).pack(side=tk.LEFT, padx=(4, 8))

        self._time_label = tk.Label(controls, text="00:00 / 00:00", width=14)
        self._time_label.pack(side=tk.LEFT)

        # Timeline slider — full width of the player.
        self._slider_var = tk.DoubleVar(value=0.0)
        self._slider = ttk.Scale(
            controls,
            from_=0.0,
            to=1.0,
            orient=tk.HORIZONTAL,
            variable=self._slider_var,
            command=self._on_slider_drag,
        )
        self._slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        # Suppress the slider callback while we programmatically set it.
        self._suppress_slider_cb = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, path: str):
        """Open a video file and display its first frame."""
        self.pause()
        if self._cap is not None:
            self._cap.release()
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            raise RuntimeError(f"Could not open video: {path}")
        self._cap = cap
        self._video_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self._video_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        self._fps = fps if fps and fps > 1.0 else 30.0
        total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        self._duration = (total_frames / self._fps) if self._fps else 0.0
        self._range_start = 0.0
        self._range_end = self._duration
        self.seek(0.0)

    def set_frame_processor(self, fn: Optional[FrameProcessor]):
        """Install a BGR-in/BGR-out per-frame hook. Pass None to remove."""
        self._processor = fn
        # Re-render the current frame with the new processor.
        if self._last_bgr is not None:
            self._render(self._last_bgr, self._last_ts)

    def add_frame_listener(self, fn: Callable[[np.ndarray, float], None]):
        """Called every time a new frame is rendered, with (raw_bgr, ts)."""
        self._on_frame_listeners.append(fn)

    def set_time_range(self, start: float, end: float):
        """Clamp the timeline to [start, end]. Seeks into range if outside."""
        start = max(0.0, min(start, self._duration))
        end = max(start, min(end, self._duration))
        self._range_start = start
        self._range_end = end
        if self._last_ts < start or self._last_ts > end:
            self.seek(start)
        else:
            self._update_time_ui()

    def play(self):
        if self._cap is None or self._playing:
            return
        self._playing = True
        if hasattr(self, "_play_btn"):
            self._play_btn.config(text="\u23f8")  # pause glyph
        self._schedule_next_frame()

    def pause(self):
        if not self._playing:
            return
        self._playing = False
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        if hasattr(self, "_play_btn"):
            self._play_btn.config(text="\u25b6")

    def toggle_play(self):
        if self._playing:
            self.pause()
        else:
            self.play()

    def restart(self):
        self.pause()
        self.seek(self._range_start)

    def seek(self, seconds: float):
        if self._cap is None:
            return
        seconds = max(self._range_start, min(seconds, self._range_end))
        self._cap.set(cv2.CAP_PROP_POS_MSEC, seconds * 1000.0)
        ok, frame = self._cap.read()
        if not ok or frame is None:
            return
        self._last_bgr = frame
        self._last_ts = seconds
        self._render(frame, seconds)
        self._update_time_ui()

    def current_frame(self) -> Optional[np.ndarray]:
        """Return the most recent raw BGR frame (pre-processor)."""
        return self._last_bgr

    def current_time(self) -> float:
        return self._last_ts

    def video_size(self) -> tuple[int, int]:
        return self._video_w, self._video_h

    def is_playing(self) -> bool:
        return self._playing

    # ------------------------------------------------------------------
    # Coordinate conversion
    # ------------------------------------------------------------------

    def canvas_to_video(self, cx: float, cy: float) -> Optional[tuple[int, int]]:
        """Map canvas coords to video pixel coords. None if outside image."""
        off_x, off_y = self._display_offset
        scale = self._display_scale
        if scale <= 0:
            return None
        vx = (cx - off_x) / scale
        vy = (cy - off_y) / scale
        if 0 <= vx < self._video_w and 0 <= vy < self._video_h:
            return int(vx), int(vy)
        return None

    def video_to_canvas(self, vx: float, vy: float) -> tuple[float, float]:
        off_x, off_y = self._display_offset
        scale = self._display_scale
        return off_x + vx * scale, off_y + vy * scale

    # ------------------------------------------------------------------
    # Playback loop
    # ------------------------------------------------------------------

    def _schedule_next_frame(self):
        delay_ms = max(1, int(1000.0 / self._fps))
        self._after_id = self.after(delay_ms, self._advance)

    def _advance(self):
        if not self._playing or self._cap is None:
            return
        ok, frame = self._cap.read()
        if not ok or frame is None:
            self.pause()
            return
        # Approximate timestamp from CAP_PROP_POS_MSEC (falls back to fps delta).
        pos_ms = self._cap.get(cv2.CAP_PROP_POS_MSEC)
        ts = pos_ms / 1000.0 if pos_ms > 0 else (self._last_ts + 1.0 / self._fps)
        if ts > self._range_end:
            self.pause()
            return
        self._last_bgr = frame
        self._last_ts = ts
        self._render(frame, ts)
        self._update_time_ui()
        self._schedule_next_frame()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render(self, bgr: np.ndarray, ts: float):
        if self._processor is not None:
            try:
                out = self._processor(bgr, ts)
                if out is not None:
                    bgr = out
            except Exception as exc:
                # Don't kill playback if a shader misbehaves — log to stderr.
                import sys
                print(f"[VideoPlayer] frame processor error: {exc}", file=sys.stderr)
        self._last_displayed_bgr = bgr

        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw <= 1 or ch <= 1:
            return

        fh, fw = bgr.shape[:2]
        if fw == 0 or fh == 0:
            return

        scale = min(cw / fw, ch / fh)
        disp_w = max(1, int(fw * scale))
        disp_h = max(1, int(fh * scale))
        off_x = (cw - disp_w) // 2
        off_y = (ch - disp_h) // 2

        # The displayed frame has the same aspect ratio as the source. But when
        # the processor renders onto its own canvas (e.g. minimap_hud mode),
        # the output size may differ from the input. We still honour the
        # output's own aspect ratio here.
        self._display_offset = (off_x, off_y)
        self._display_scale = scale

        resized = cv2.resize(bgr, (disp_w, disp_h), interpolation=cv2.INTER_AREA)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)
        self._photo = ImageTk.PhotoImage(pil)

        if self._photo_id is None:
            self._photo_id = self.canvas.create_image(
                off_x, off_y, anchor=tk.NW, image=self._photo
            )
        else:
            self.canvas.itemconfig(self._photo_id, image=self._photo)
            self.canvas.coords(self._photo_id, off_x, off_y)

        self.canvas.tag_raise("overlay")

        for fn in self._on_frame_listeners:
            try:
                fn(self._last_bgr, ts)
            except Exception:
                pass

    def _redraw(self):
        if self._last_displayed_bgr is not None:
            # Re-render at the new canvas size without re-running the processor
            # (so interactive resizing stays snappy).
            src = self._last_displayed_bgr
            cw = self.canvas.winfo_width()
            ch = self.canvas.winfo_height()
            if cw <= 1 or ch <= 1:
                return
            fh, fw = src.shape[:2]
            scale = min(cw / fw, ch / fh)
            disp_w = max(1, int(fw * scale))
            disp_h = max(1, int(fh * scale))
            off_x = (cw - disp_w) // 2
            off_y = (ch - disp_h) // 2
            self._display_offset = (off_x, off_y)
            self._display_scale = scale
            resized = cv2.resize(src, (disp_w, disp_h), interpolation=cv2.INTER_AREA)
            rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            self._photo = ImageTk.PhotoImage(Image.fromarray(rgb))
            if self._photo_id is None:
                self._photo_id = self.canvas.create_image(
                    off_x, off_y, anchor=tk.NW, image=self._photo
                )
            else:
                self.canvas.itemconfig(self._photo_id, image=self._photo)
                self.canvas.coords(self._photo_id, off_x, off_y)
            self.canvas.tag_raise("overlay")

    # ------------------------------------------------------------------
    # Controls
    # ------------------------------------------------------------------

    def _update_time_ui(self):
        if not hasattr(self, "_slider"):
            return
        span = max(1e-3, self._range_end - self._range_start)
        rel = (self._last_ts - self._range_start) / span
        rel = max(0.0, min(1.0, rel))
        self._suppress_slider_cb = True
        try:
            self._slider_var.set(rel)
        finally:
            self._suppress_slider_cb = False

        self._time_label.config(
            text=(
                f"{_format_time(self._last_ts - self._range_start)} / "
                f"{_format_time(self._range_end - self._range_start)}"
            )
        )

    def _on_slider_drag(self, _value: str):
        if self._suppress_slider_cb or self._cap is None:
            return
        rel = float(self._slider_var.get())
        span = self._range_end - self._range_start
        target = self._range_start + rel * span
        was_playing = self._playing
        self.pause()
        self.seek(target)
        if was_playing:
            self.play()
