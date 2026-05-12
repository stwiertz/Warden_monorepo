"""Video Timeline Labeler — Tool 6: scrub a video and snap-to-keyframe label PNGs.

Opens a video, scrubs along its timeline, and on a hotkey snaps the cursor to the
nearest keyframe and writes a labeled full-resolution PNG into a HUD-version-aware
directory tree (``labeled/v<ver>/<class>/<seq>_<ts>.png``). The output dataset feeds
Tool 7 (overlay stack analyzer) for ROI mining of the redesigned EVA HUD.

Usage:
    python tools/video_timeline_labeler.py <video.mp4> [-o OUTPUT_DIR] [--snap nearest|prior|after]
"""

import argparse
import glob
import math
import os
import re
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

# Use absolute path to avoid shadowing stdlib modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cv2
from PIL import Image, ImageTk

from utils.video import (
    check_ffmpeg,
    extract_frame_at_timestamp,
    extract_frame_at_timestamp_scaled,
    get_keyframe_timestamps,
    get_video_duration,
    get_video_info,
)
from tools.frame_labeler import LABEL_DISPLAY, MAP_LABELS

# Filesystem-safe HUD version: letters, digits, '.', '-', '_'. No '..' / no path seps.
_HUD_VERSION_RE = re.compile(r"^[A-Za-z0-9._-]+$")

# Non-map classes that this tool labels in addition to the 14 maps.
NON_MAP_CLASSES = ("lobby", "transition", "score")

# Hotkey -> map class. Positional, matches frame_labeler.py to avoid muscle-memory conflict.
MAP_HOTKEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "q", "w", "e", "r"]


# ---------------------------------------------------------------------------
# Pure helpers (top-level so they're unit-testable without Tk).
# ---------------------------------------------------------------------------


def _snap_to_keyframe(cursor: float, pts_list: list[float], policy: str) -> float | None:
    """Snap a cursor PTS (seconds) to a keyframe timestamp per the chosen policy.

    ``nearest`` returns the closest PTS in absolute-time terms, breaking ties by
    selecting the prior (lower) PTS. ``prior`` returns the largest PTS <= cursor or
    ``None`` if cursor < pts_list[0]. ``after`` returns the smallest PTS >= cursor or
    ``None`` if cursor > pts_list[-1]. An empty pts_list always returns ``None``.

    pts_list is assumed to be sorted ascending (as get_keyframe_timestamps emits).
    """
    if not pts_list:
        return None
    if policy == "nearest":
        best = None
        best_dist = float("inf")
        for pts in pts_list:
            dist = abs(pts - cursor)
            if dist < best_dist:
                best = pts
                best_dist = dist
        return best
    if policy == "prior":
        candidates = [p for p in pts_list if p <= cursor]
        return max(candidates) if candidates else None
    if policy == "after":
        candidates = [p for p in pts_list if p >= cursor]
        return min(candidates) if candidates else None
    return None


def _format_hhmmss(pts: float) -> str:
    """Format seconds as ``HHhMMmSSs`` (zero-padded; no compatible helper exists in utils.format).

    Non-finite inputs (NaN, +/-inf) clamp to 0 — `int(NaN)` would otherwise raise.
    """
    pts = float(pts)
    if not math.isfinite(pts):
        pts = 0.0
    pts = max(0.0, pts)
    hours = int(pts // 3600)
    minutes = int((pts % 3600) // 60)
    secs = int(pts % 60)
    return f"{hours:02d}h{minutes:02d}m{secs:02d}s"


def _output_path(
    output_root: str, version: str, class_: str, seq: int, pts: float
) -> str:
    """Build ``<root>/v<version>/<class>/<seq:03d>_<HHmMSs>.png``."""
    return os.path.join(
        output_root,
        f"v{version}",
        class_,
        f"{seq:03d}_{_format_hhmmss(pts)}.png",
    )


def _next_seq(dest_dir: str) -> int:
    """Return ``max(seq) + 1`` for files matching ``^\\d+_`` in dest_dir, or 1 if empty.

    Non-conforming filenames are silently skipped. Missing directory returns 1.
    """
    pattern = re.compile(r"^(\d+)_")
    seqs: list[int] = []
    for path in glob.glob(os.path.join(dest_dir, "*.png")):
        match = pattern.match(os.path.basename(path))
        if match:
            seqs.append(int(match.group(1)))
    return max(seqs) + 1 if seqs else 1


def _undo(last_written_path: str | None) -> bool:
    """Remove the most recently written file. Return True on success, False otherwise.

    OSError (permission denied, Windows file-lock, race with external delete) is
    caught and turned into False — the caller treats this as "nothing to undo".
    """
    if last_written_path is None or not os.path.exists(last_written_path):
        return False
    try:
        os.remove(last_written_path)
    except OSError:
        return False
    return True


def _is_valid_hud_version(value: str) -> bool:
    """Return True if value is safe to use as a `v<value>/` directory name.

    Reject leading '.' (POSIX-hidden dir) and leading '-' (downstream CLI flag confusable).
    """
    if not value or value in (".", ".."):
        return False
    if value[0] in (".", "-"):
        return False
    return bool(_HUD_VERSION_RE.match(value))


def _backfill_between(
    last_class: str | None,
    last_pts: float | None,
    current_class: str,
    current_pts: float,
    keyframes: list[float],
    skip_classes: tuple[str, ...] = ("transition",),
) -> list[float]:
    """Return the list of keyframe PTS values to backfill between two same-class labels.

    Backfill fires when:
      * The previous label exists (``last_class`` and ``last_pts`` are both non-None).
      * Previous and current labels share a class.
      * That class is NOT in ``skip_classes`` (default: ``("transition",)`` — transitions
        are short, never assume they extend across a gap).
      * The current label is strictly forward in time of the previous one
        (``last_pts < current_pts``).

    Returns the keyframe PTS values strictly between the two endpoints (exclusive).
    Returns an empty list if any condition fails.
    """
    if last_class is None or last_pts is None:
        return []
    if last_class != current_class:
        return []
    if current_class in skip_classes:
        return []
    if last_pts >= current_pts:
        return []
    return [p for p in keyframes if last_pts < p < current_pts]


# ---------------------------------------------------------------------------
# HUD version prompt
# ---------------------------------------------------------------------------


def _prompt_hud_version(video_path: str | None = None) -> str | None:
    """Modal: pick HUD version. Returns "1.0", "2.0", a custom string, or None on cancel.

    If video_path is provided, the first frame is extracted (scaled to 360px tall)
    and shown as a thumbnail so the user can visually confirm which HUD to label.
    Custom versions are validated via `_is_valid_hud_version` (filesystem-safe).

    Implemented as a standalone, visible `tk.Tk()` (NOT a Toplevel of a withdrawn
    root + `transient(...)` — that combination renders invisible/behind on Windows;
    cf. 2026-05-09 and 2026-05-12 smoke regressions). Multiple sequential `tk.Tk()`
    instances per process (picker → prompt → player) are fine as long as each is
    destroyed before the next is created.
    """
    selection: dict[str, str | None] = {"value": None}

    root = tk.Tk()
    root.title("Warden — Select HUD Version")
    root.resizable(False, False)
    root.attributes("-topmost", True)
    root.after(200, lambda: root.attributes("-topmost", False))

    def _set_choice(value: str | None) -> None:
        selection["value"] = value
        root.destroy()

    def _ask_custom() -> None:
        v = simpledialog.askstring(
            "Custom HUD version",
            "Enter HUD version (letters, digits, '.', '-', '_'):",
            parent=root,
        )
        if v is None:
            return
        v = v.strip()
        if _is_valid_hud_version(v):
            _set_choice(v)
        else:
            messagebox.showerror(
                "Invalid version",
                f"'{v}' is not a valid HUD version.\n"
                "Allowed: letters, digits, '.', '-', '_'. Not '.' or '..'.",
                parent=root,
            )

    root.protocol("WM_DELETE_WINDOW", lambda: _set_choice(None))

    tk.Label(
        root,
        text="Which HUD version is this video?",
        font=("sans-serif", 12, "bold"),
        padx=24,
        pady=12,
    ).pack()

    # First-frame preview (best-effort). If decode fails the prompt still
    # shows, but we log the cause to stderr — silent swallow used to let
    # users blow past a broken video and discover the failure inside the
    # player init, with no breadcrumb.
    if video_path is not None:
        try:
            preview_bgr = extract_frame_at_timestamp_scaled(video_path, 0.0, 360)
            preview_rgb = cv2.cvtColor(preview_bgr, cv2.COLOR_BGR2RGB)
            preview_pil = Image.fromarray(preview_rgb)
            preview_tk = ImageTk.PhotoImage(preview_pil)
            preview_holder = tk.Label(root, image=preview_tk, bd=1, relief=tk.SUNKEN)
            preview_holder._tk_image = preview_tk  # GC ref
            preview_holder.pack(padx=24, pady=8)
        except Exception as exc:
            print(
                f"⚠ HUD-prompt preview decode failed for {video_path}: "
                f"{type(exc).__name__}: {exc}",
                file=sys.stderr,
                flush=True,
            )
            tk.Label(
                root,
                text=f"(preview unavailable: {exc})",
                font=("sans-serif", 9),
                fg="gray",
                padx=24,
            ).pack()

    tk.Label(
        root,
        text="Output PNGs route to <output>/v<version>/<class>/. "
        "Cannot be changed mid-session.",
        font=("sans-serif", 9),
        fg="gray",
        padx=24,
        wraplength=520,
        justify="center",
    ).pack()

    btn_frame = tk.Frame(root)
    btn_frame.pack(padx=24, pady=14)
    tk.Button(
        btn_frame, text="HUD 1.0", width=14, command=lambda: _set_choice("1.0")
    ).pack(side=tk.LEFT, padx=6)
    tk.Button(
        btn_frame, text="HUD 2.0", width=14, command=lambda: _set_choice("2.0")
    ).pack(side=tk.LEFT, padx=6)
    tk.Button(
        btn_frame, text="Custom…", width=14, command=_ask_custom
    ).pack(side=tk.LEFT, padx=6)

    root.update_idletasks()
    w = root.winfo_width()
    h = root.winfo_height()
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    root.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")

    root.mainloop()
    return selection["value"]


# ---------------------------------------------------------------------------
# Tk app
# ---------------------------------------------------------------------------


class VideoTimelineLabelerApp(tk.Tk):
    """Main player window — scrub, snap-to-keyframe, label PNGs."""

    def __init__(
        self,
        video_path: str,
        output_dir: str,
        hud_version: str,
        snap_policy: str,
        keyframe_pts: list[float],
    ):
        super().__init__()

        self._video_path = video_path
        self._output_dir = output_dir
        self._hud_version = hud_version
        self._snap_policy = snap_policy
        self._keyframe_pts = keyframe_pts

        self._cap = cv2.VideoCapture(video_path)
        if not self._cap.isOpened():
            raise RuntimeError(f"Could not open video: {video_path}")
        try:
            raw_fps = self._cap.get(cv2.CAP_PROP_FPS) or 0.0
            if raw_fps <= 0 or not math.isfinite(raw_fps):
                print(
                    f"⚠ FPS metadata missing/invalid ({raw_fps!r}); defaulting to 30.0",
                    file=sys.stderr,
                    flush=True,
                )
                raw_fps = 30.0
            self._fps = raw_fps
            self._frame_count = max(0, int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT)))
            if self._frame_count <= 0:
                self._cap.release()
                raise RuntimeError(
                    f"Video has zero frames or unreadable frame-count metadata: {video_path}"
                )
            self._duration_s = self._frame_count / self._fps
            try:
                self._src_w, self._src_h = get_video_info(video_path)
            except Exception as exc:
                self._cap.release()
                raise RuntimeError(
                    f"Could not read video info for {video_path}: {exc}"
                ) from exc
        except Exception:
            # Ensure cap is released on any init failure before re-raising.
            try:
                self._cap.release()
            except Exception:
                pass
            raise

        self._cursor_s: float = 0.0
        self._playing: bool = False
        # Most-recent write batch (single PNG for normal labels; many PNGs after backfill).
        # Backspace removes the entire batch.
        self._last_written_batch: list[str] = []
        self._last_label_class: str | None = None
        self._last_label_pts: float | None = None
        self._session_counts: dict[str, int] = {}
        self._slider_after_id: str | None = None
        # Cursor advance step in seconds after each label. Snap to nearest keyframe.
        # Default 60s per Stephane: minute-sampling; same-class consecutive triggers backfill.
        self._advance_step_s: float = 60.0

        self.title("Warden Video Timeline Labeler")
        self.geometry("1400x900")
        self.minsize(900, 600)

        self._tk_image = None  # prevent GC
        self._build_ui()
        self._render_current_frame()
        self._update_status_bar()

    # ------------------------------------------------------------------
    # UI build
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # Top: HUD-version + snap-policy labels
        top = tk.Frame(self, relief=tk.RAISED, bd=1)
        top.pack(side=tk.TOP, fill=tk.X, padx=4, pady=4)
        tk.Label(
            top,
            text=f"HUD: {self._hud_version}",
            font=("sans-serif", 10, "bold"),
        ).pack(side=tk.LEFT, padx=(8, 16))
        tk.Label(
            top,
            text=f"Snap: {self._snap_policy}",
            font=("sans-serif", 10, "bold"),
        ).pack(side=tk.LEFT)
        tk.Label(
            top,
            text=f"keyframes: {len(self._keyframe_pts)}",
            font=("sans-serif", 9),
            fg="gray",
        ).pack(side=tk.RIGHT, padx=8)
        tk.Label(
            top,
            text=f"Advance: +{self._advance_step_s:.0f}s + same-class backfill (skip transition)",
            font=("sans-serif", 9),
            fg="gray",
        ).pack(side=tk.RIGHT, padx=8)

        # Label buttons — special classes (lobby/transition/score)
        special_row = tk.Frame(self, relief=tk.GROOVE, bd=1)
        special_row.pack(side=tk.TOP, fill=tk.X, padx=4, pady=(0, 2))
        tk.Label(
            special_row,
            text="Special:",
            font=("sans-serif", 9, "bold"),
            width=8,
            anchor="w",
        ).pack(side=tk.LEFT, padx=(8, 4))
        for class_name, key in (("lobby", "L"), ("transition", "T"), ("score", "S")):
            tk.Button(
                special_row,
                text=f"{class_name.capitalize()} ({key})",
                command=lambda c=class_name: self._label_current(c),
            ).pack(side=tk.LEFT, padx=2, pady=2)
        tk.Button(
            special_row,
            text="Undo (Backspace)",
            command=self._on_backspace,
        ).pack(side=tk.RIGHT, padx=(4, 8), pady=2)

        # Label buttons — 14 maps with their numeric/alpha hotkeys
        maps_row = tk.Frame(self, relief=tk.GROOVE, bd=1)
        maps_row.pack(side=tk.TOP, fill=tk.X, padx=4, pady=(0, 4))
        tk.Label(
            maps_row,
            text="Maps:",
            font=("sans-serif", 9, "bold"),
            width=8,
            anchor="w",
        ).pack(side=tk.LEFT, padx=(8, 4))
        for idx, key in enumerate(MAP_HOTKEYS):
            label = MAP_LABELS[idx]
            tk.Button(
                maps_row,
                text=f"{LABEL_DISPLAY[label]} ({key})",
                command=lambda c=label: self._label_current(c),
            ).pack(side=tk.LEFT, padx=1, pady=2)

        # Center: canvas
        self._canvas = tk.Canvas(self, bg="#1e1e1e")
        self._canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self._canvas.bind("<Configure>", lambda e: self._render_current_frame())

        # Bottom: scrubber + status
        bottom = tk.Frame(self)
        bottom.pack(side=tk.BOTTOM, fill=tk.X, padx=4, pady=4)

        self._scale = tk.Scale(
            bottom,
            orient=tk.HORIZONTAL,
            from_=0.0,
            to=max(self._duration_s, 0.001),
            resolution=0.001,
            showvalue=False,
            command=self._on_slider,
        )
        self._scale.pack(side=tk.TOP, fill=tk.X)

        self._status_label = tk.Label(
            bottom, text="", font=("sans-serif", 9), anchor="w"
        )
        self._status_label.pack(side=tk.TOP, fill=tk.X, padx=4)

        # Key bindings.
        # CRITICAL: use the explicit `<KeyPress-X>` form for single-character keys.
        # Tk interprets bare `<1>`..`<5>` as mouse Button-1..Button-5 (not digits!),
        # which silently routes every left-click to the digit's handler. See
        # `tk(n)` Bind manual; the bug shipped once already (cf. artefact-folder
        # pollution in 2026-05-09 smoke logs).
        self.bind("<KeyPress-space>", lambda e: self._toggle_play())
        self.bind("<KeyPress-Left>", lambda e: self._step_frames(-1))
        self.bind("<KeyPress-Right>", lambda e: self._step_frames(+1))
        self.bind("<Shift-KeyPress-Left>", lambda e: self._step_frames(-10))
        self.bind("<Shift-KeyPress-Right>", lambda e: self._step_frames(+10))
        self.bind("<KeyPress-j>", lambda e: self._step_seconds(-1))
        self.bind("<KeyPress-k>", lambda e: self._step_seconds(+1))
        self.bind("<KeyPress-J>", lambda e: self._step_seconds(-1))
        self.bind("<KeyPress-K>", lambda e: self._step_seconds(+1))
        self.bind("<KeyPress-l>", lambda e: self._label_current("lobby"))
        self.bind("<KeyPress-L>", lambda e: self._label_current("lobby"))
        self.bind("<KeyPress-t>", lambda e: self._label_current("transition"))
        self.bind("<KeyPress-T>", lambda e: self._label_current("transition"))
        self.bind("<KeyPress-s>", lambda e: self._label_current("score"))
        self.bind("<KeyPress-S>", lambda e: self._label_current("score"))
        for idx, key in enumerate(MAP_HOTKEYS):
            self.bind(
                f"<KeyPress-{key}>",
                lambda e, label=MAP_LABELS[idx]: self._label_current(label),
            )
            # Also bind the uppercase letter so CapsLock / Shift-held keystrokes
            # don't silently no-op (lobby/transition/score already bind both cases).
            if key.isalpha():
                self.bind(
                    f"<KeyPress-{key.upper()}>",
                    lambda e, label=MAP_LABELS[idx]: self._label_current(label),
                )
        self.bind("<KeyPress-BackSpace>", lambda e: self._on_backspace())

    # ------------------------------------------------------------------
    # Rendering + scrubbing
    # ------------------------------------------------------------------

    def _paint_frame(self, frame) -> None:
        """Render a decoded BGR frame onto the canvas, scaled to fit. Held PhotoImage ref prevents GC."""
        cw = self._canvas.winfo_width()
        ch = self._canvas.winfo_height()
        if cw < 2 or ch < 2:
            return
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)
        scale = min(cw / pil.width, ch / pil.height)
        new_w = max(1, int(pil.width * scale))
        new_h = max(1, int(pil.height * scale))
        resized = pil.resize((new_w, new_h), Image.LANCZOS)
        self._tk_image = ImageTk.PhotoImage(resized)
        self._canvas.delete("all")
        self._canvas.create_image(
            cw // 2, ch // 2, anchor=tk.CENTER, image=self._tk_image
        )

    def _render_current_frame(self) -> None:
        # Always re-seek to cursor before reading so the capture position
        # stays in sync with _cursor_s. Without this seek, a <Configure>
        # event or a canvas-too-small early return silently consumes the
        # next sequential frame and the player drifts off the cursor.
        self._cap.set(cv2.CAP_PROP_POS_MSEC, self._cursor_s * 1000)
        ret, frame = self._cap.read()
        if not ret:
            return
        self._paint_frame(frame)

    def _on_slider(self, value_str: str) -> None:
        try:
            value = float(value_str)
        except (TypeError, ValueError):
            return
        self._cursor_s = value
        # Debounce: only redraw 50 ms after the last slider event.
        if self._slider_after_id is not None:
            self.after_cancel(self._slider_after_id)
        self._slider_after_id = self.after(50, self._seek_and_render)

    def _seek_and_render(self) -> None:
        self._slider_after_id = None
        self._cap.set(cv2.CAP_PROP_POS_MSEC, self._cursor_s * 1000)
        ret, frame = self._cap.read()
        if ret:
            self._paint_frame(frame)
        self._update_status_bar()

    def _toggle_play(self) -> None:
        self._playing = not self._playing
        if self._playing:
            self._tick()

    def _tick(self) -> None:
        if not self._playing or not self.winfo_exists():
            return
        ret, frame = self._cap.read()
        if not ret:
            self._playing = False
            return
        self._paint_frame(frame)
        pos_msec = self._cap.get(cv2.CAP_PROP_POS_MSEC)
        self._cursor_s = pos_msec / 1000.0
        # Update slider without re-firing _on_slider seek
        self._scale.set(self._cursor_s)
        self._update_status_bar()
        delay = max(1, int(1000 / self._fps)) if self._fps else 33
        self.after(delay, self._tick)

    def _step_frames(self, delta: int) -> None:
        if not self._fps:
            return
        new_s = max(0.0, min(self._duration_s, self._cursor_s + delta / self._fps))
        self._cursor_s = new_s
        # Update slider display, then render immediately (bypass debounce so
        # each press lands a visible frame — frame-by-frame inspection is
        # the entire reason for these keys).
        self._scale.set(new_s)
        if self._slider_after_id is not None:
            self.after_cancel(self._slider_after_id)
            self._slider_after_id = None
        self._seek_and_render()

    def _step_seconds(self, delta: int) -> None:
        new_s = max(0.0, min(self._duration_s, self._cursor_s + delta))
        self._cursor_s = new_s
        self._scale.set(new_s)
        if self._slider_after_id is not None:
            self.after_cancel(self._slider_after_id)
            self._slider_after_id = None
        self._seek_and_render()

    # ------------------------------------------------------------------
    # Labeling
    # ------------------------------------------------------------------

    def _label_current(self, class_name: str) -> None:
        # Restore root focus so hotkeys still fire after a button click.
        self.focus_set()

        if not self._keyframe_pts:
            self.bell()
            self._status_label.config(
                text="⚠ no keyframes loaded — cannot label (check ffprobe output)"
            )
            return

        snapped = _snap_to_keyframe(
            self._cursor_s, self._keyframe_pts, self._snap_policy
        )
        if snapped is None:
            self.bell()
            self._status_label.config(
                text=f"⚠ no keyframe for cursor {self._cursor_s:.3f}s "
                f"under policy '{self._snap_policy}' — refused"
            )
            return

        # Pre-compute the base sequence number once per batch so backfill
        # writes don't each rescan the directory — that pattern would race
        # against itself if a future change ever moved writes off-thread,
        # and the rescan-per-call overhead is wasted work anyway.
        dest_dir = os.path.join(
            self._output_dir, f"v{self._hud_version}", class_name
        )
        os.makedirs(dest_dir, exist_ok=True)
        base_seq = _next_seq(dest_dir)

        primary_path = self._write_label_png(
            class_name, snapped, seq=base_seq
        )
        if primary_path is None:
            return

        # Defensive — if folder routing is ever wrong, this surfaces loudly.
        if class_name not in primary_path:
            print(
                f"⚠ ROUTING BUG: class_name={class_name!r} but path={primary_path!r}",
                flush=True,
            )

        # Backfill keyframes between the previous and current label.
        between = _backfill_between(
            self._last_label_class,
            self._last_label_pts,
            class_name,
            snapped,
            self._keyframe_pts,
        )
        print(
            f"[backfill-check] last_class={self._last_label_class!r} "
            f"current_class={class_name!r} last_pts={self._last_label_pts} "
            f"snapped={snapped:.3f} -> {len(between)} keyframe(s) to backfill",
            flush=True,
        )
        new_batch = [primary_path]
        backfilled = 0
        for offset, pts in enumerate(between, start=1):
            fill_path = self._write_label_png(
                class_name, pts, seq=base_seq + offset, log_prefix="backfill"
            )
            if fill_path is not None:
                new_batch.append(fill_path)
                backfilled += 1

        self._last_written_batch = new_batch
        self._last_label_class = class_name
        self._last_label_pts = snapped

        if backfilled:
            extra = (
                f"snapped {self._cursor_s:.3f} → {snapped:.3f}; "
                f"backfilled {backfilled} keyframes as {class_name}"
            )
        else:
            extra = f"snapped {self._cursor_s:.3f} → {snapped:.3f}"
        self._update_status_bar(extra=extra)

        # Advance cursor by self._advance_step_s and snap to the nearest keyframe.
        target = snapped + self._advance_step_s
        next_step = _snap_to_keyframe(target, self._keyframe_pts, "nearest")
        # If snap landed back on `snapped` (target past end of video or no later
        # keyframe is closer than `snapped` itself), pick the first keyframe > snapped.
        if next_step is None or next_step <= snapped:
            next_step = next(
                (p for p in self._keyframe_pts if p > snapped), None
            )
        if next_step is not None and next_step > snapped:
            self._scale.set(next_step)  # triggers _on_slider → seek + render

    def _write_label_png(
        self,
        class_name: str,
        snapped_pts: float,
        seq: int | None = None,
        log_prefix: str = "",
    ) -> str | None:
        """Decode + write a single labeled PNG. Returns the path on success, else None.

        If ``seq`` is None, scan the destination directory for the next sequence
        number. Callers writing a batch should pass explicit sequential ``seq``
        values (see ``_label_current``) so backfill writes don't all collide on
        the same rescan-based number.
        """
        dest_dir = os.path.join(
            self._output_dir, f"v{self._hud_version}", class_name
        )
        try:
            os.makedirs(dest_dir, exist_ok=True)
        except OSError as exc:
            self.bell()
            self._status_label.config(text=f"⚠ mkdir failed: {dest_dir} ({exc})")
            return None
        if seq is None:
            seq = _next_seq(dest_dir)
        dest_path = _output_path(
            self._output_dir, self._hud_version, class_name, seq, snapped_pts
        )
        try:
            frame = extract_frame_at_timestamp(
                self._video_path, snapped_pts, self._src_w, self._src_h
            )
        except Exception as exc:
            self.bell()
            self._status_label.config(text=f"⚠ extract failed at {snapped_pts:.3f}: {exc}")
            return None
        # Use cv2.imencode + open()+write for Windows non-ASCII path safety.
        # cv2.imwrite uses the ANSI codepage internally and silently returns
        # False for paths containing non-ASCII characters (e.g. accented
        # usernames in C:\Users\…). imencode bypasses that codepath.
        try:
            ok, buf = cv2.imencode(".png", frame)
            if not ok:
                raise RuntimeError("cv2.imencode returned False")
            with open(dest_path, "wb") as f:
                f.write(buf.tobytes())
        except (OSError, RuntimeError, cv2.error) as exc:
            self.bell()
            self._status_label.config(text=f"⚠ write failed: {dest_path} ({exc})")
            return None
        self._session_counts[class_name] = (
            self._session_counts.get(class_name, 0) + 1
        )
        tag = f"({log_prefix}) " if log_prefix else ""
        print(
            f"[v{self._hud_version}/{class_name}] {tag}{os.path.basename(dest_path)} "
            f"@ pts={snapped_pts:.3f}",
            flush=True,
        )
        return dest_path

    def _on_backspace(self) -> None:
        # Restore root focus so hotkeys still fire after a button click.
        self.focus_set()
        if not self._last_written_batch:
            self.bell()
            return
        removed = 0
        for path in self._last_written_batch:
            if _undo(path):
                removed += 1
                class_dir = os.path.dirname(path)
                cls = os.path.basename(class_dir)
                if cls in self._session_counts and self._session_counts[cls] > 0:
                    self._session_counts[cls] -= 1
        print(f"[undo] removed {removed} file(s) from last action", flush=True)
        # Roll back the cursor to the pts of the just-undone primary label —
        # so the user can re-label the same frame in one click instead of
        # having to scrub back from the +60s auto-advance position.
        rollback_pts = self._last_label_pts
        self._last_written_batch = []
        # Roll back the "last label" tracker so a re-label at this cursor counts as fresh.
        self._last_label_class = None
        self._last_label_pts = None
        if rollback_pts is not None:
            self._cursor_s = rollback_pts
            self._scale.set(rollback_pts)
            if self._slider_after_id is not None:
                self.after_cancel(self._slider_after_id)
                self._slider_after_id = None
            self._seek_and_render()
        self._update_status_bar(extra=f"undid {removed} label(s)")

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------

    def _update_status_bar(self, extra: str = "") -> None:
        mm = int(self._cursor_s // 60)
        ss = int(self._cursor_s % 60)
        ms = int((self._cursor_s - int(self._cursor_s)) * 1000)
        idx = int(self._cursor_s * self._fps) if self._fps else 0
        if self._last_written_batch:
            head = self._last_written_batch[0]
            last_class = os.path.basename(os.path.dirname(head))
            last_basename = os.path.basename(head)
            tail = (
                f" (+{len(self._last_written_batch) - 1} backfill)"
                if len(self._last_written_batch) > 1
                else ""
            )
            last_field = f"{last_class}/{last_basename}{tail}"
        else:
            last_field = "—"
        nonzero = [
            f"{cls}={n}" for cls, n in sorted(self._session_counts.items()) if n > 0
        ]
        session_field = ", ".join(nonzero) if nonzero else "—"
        msg = (
            f"{mm:02d}:{ss:02d}.{ms:03d} | frame {idx}/{self._frame_count} | "
            f"last: {last_field} | session: {session_field}"
        )
        if extra:
            msg = f"{msg}    [{extra}]"
        self._status_label.config(text=msg)

    def destroy(self) -> None:  # noqa: D401 - tk override
        try:
            if self._cap is not None:
                self._cap.release()
        except Exception as exc:
            print(f"⚠ cap.release failed during destroy: {exc}", file=sys.stderr, flush=True)
        super().destroy()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _default_output_dir() -> str:
    return os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")),
        "output",
        "labeled",
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Tool 6 — Label frames from a video timeline (HUD-version-aware)."
    )
    parser.add_argument(
        "video",
        nargs="?",
        default=None,
        help="Path to a video file (default: open file picker).",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output root directory (default: <project_root>/output/labeled).",
    )
    parser.add_argument(
        "--snap",
        choices=["nearest", "prior", "after"],
        default="nearest",
        help="Snap policy for label hotkeys (default: nearest).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    video_path = args.video
    if video_path is None:
        # Standalone withdrawn root just for the file picker; destroyed
        # before the HUD prompt creates its own root. Sequential, never
        # overlapping — fine for Tk.
        picker_root = tk.Tk()
        picker_root.withdraw()
        video_path = filedialog.askopenfilename(
            title="Select video file",
            filetypes=[("MP4", "*.mp4"), ("All files", "*.*")],
        )
        picker_root.destroy()
        if not video_path:
            print("No video selected. Exiting.", file=sys.stderr)
            return 1

    video_path = os.path.abspath(video_path)
    output_dir = os.path.abspath(args.output or _default_output_dir())

    print(f"Video:  {video_path}", flush=True)
    print(f"Output: {output_dir}", flush=True)
    print(f"Snap:   {args.snap}", flush=True)

    check_ffmpeg()
    print("Probing video duration...", flush=True)
    duration = get_video_duration(video_path)
    if duration is None or not math.isfinite(duration) or duration <= 0:
        print(
            f"⚠ Could not determine video duration ({duration!r}). "
            "Exiting — the file may be corrupt or empty.",
            file=sys.stderr,
            flush=True,
        )
        return 1
    # math.ceil so a 3599.9s video still scans all 3600s of keyframes
    # instead of truncating to 3599 via int().
    scan_seconds = math.ceil(duration) + 1
    print(
        f"Duration: {duration:.1f}s ({duration/60:.1f} min) — "
        f"scanning keyframes (packet-level, usually <5s)...",
        flush=True,
    )
    keyframe_pts = get_keyframe_timestamps(video_path, scan_duration=scan_seconds)
    print(
        f"Found {len(keyframe_pts)} keyframes spanning {duration:.1f}s",
        flush=True,
    )

    print("Opening HUD-version prompt...", flush=True)
    hud_version = _prompt_hud_version(video_path=video_path)
    if hud_version is None:
        print("HUD version not selected. Exiting.", file=sys.stderr, flush=True)
        return 1
    print(
        f"HUD version: {hud_version} — output root: {output_dir}/v{hud_version}/",
        flush=True,
    )

    app = VideoTimelineLabelerApp(
        video_path=video_path,
        output_dir=output_dir,
        hud_version=hud_version,
        snap_policy=args.snap,
        keyframe_pts=keyframe_pts,
    )
    app.mainloop()
    return 0


# Re-export for tests
__all__ = [
    "_snap_to_keyframe",
    "_output_path",
    "_format_hhmmss",
    "_next_seq",
    "_undo",
    "_is_valid_hud_version",
    "_backfill_between",
    "_prompt_hud_version",
    "VideoTimelineLabelerApp",
    "MAP_LABELS",
    "LABEL_DISPLAY",
    "MAP_HOTKEYS",
    "NON_MAP_CLASSES",
    "main",
]


if __name__ == "__main__":
    sys.exit(main())
