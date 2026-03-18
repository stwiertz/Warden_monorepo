"""Frame Labeler — GUI tool for manually labeling extracted score frames by map name.

Scans the output directory for PNG files with 'score' in the filename,
displays them one by one, and lets the user assign a map label via buttons.
Labeled images are copied into per-map subdirectories under a configurable
labeled-data folder.
"""

import argparse
import glob
import os
import shutil
import sys
import tkinter as tk
from tkinter import filedialog, messagebox

from PIL import Image, ImageTk

MAP_LABELS = [
    "horizon",
    "engine",
    "outlaw",
    "ceres",
    "artefact",
    "silva",
    "bastion",
    "polaris",
    "coliseum",
    "the_cliff",
    "helios",
    "atlantis",
    "the_rock",
    "lunar_outpost",
]

# Display names for buttons (title-cased, spaces preserved)
LABEL_DISPLAY = {
    "horizon": "Horizon",
    "engine": "Engine",
    "outlaw": "Outlaw",
    "ceres": "Ceres",
    "artefact": "Artefact",
    "silva": "Silva",
    "bastion": "Bastion",
    "polaris": "Polaris",
    "coliseum": "Coliseum",
    "the_cliff": "The Cliff",
    "helios": "Helios",
    "atlantis": "Atlantis",
    "the_rock": "The Rock",
    "lunar_outpost": "Lunar Outpost",
}


def find_score_images(source_dir):
    """Return sorted list of PNG paths containing 'score' in the filename."""
    pattern = os.path.join(source_dir, "**", "*score*.png")
    paths = glob.glob(pattern, recursive=True)
    paths.sort()
    return paths


class FrameLabelerApp(tk.Tk):
    """Main labeling window."""

    def __init__(self, source_dir, output_dir):
        super().__init__()

        self.source_dir = source_dir
        self.output_dir = output_dir
        self.images = find_score_images(source_dir)
        self.current_index = 0

        if not self.images:
            messagebox.showinfo(
                "No images",
                f"No PNG files with 'score' in name found in:\n{source_dir}",
            )
            self.destroy()
            sys.exit(0)

        # Create label subdirectories
        for label in MAP_LABELS:
            os.makedirs(os.path.join(output_dir, label), exist_ok=True)

        self.title("Warden Frame Labeler")
        self.geometry("1300x900")
        self.minsize(800, 600)

        self._build_ui()
        self._show_current()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        # --- Top: label buttons ---
        btn_frame = tk.Frame(self, relief=tk.RAISED, bd=1)
        btn_frame.pack(side=tk.TOP, fill=tk.X, padx=4, pady=4)

        tk.Label(btn_frame, text="Label as:", font=("sans-serif", 10, "bold")).pack(
            side=tk.LEFT, padx=(8, 4)
        )

        for label in MAP_LABELS:
            btn = tk.Button(
                btn_frame,
                text=LABEL_DISPLAY[label],
                width=10,
                command=lambda l=label: self._label_current(l),
            )
            btn.pack(side=tk.LEFT, padx=2, pady=4)

        # --- Navigation bar ---
        nav_frame = tk.Frame(self)
        nav_frame.pack(side=tk.TOP, fill=tk.X, padx=4)

        self._btn_prev = tk.Button(nav_frame, text="< Prev", command=self._prev)
        self._btn_prev.pack(side=tk.LEFT, padx=4)

        self._btn_skip = tk.Button(nav_frame, text="Skip >", command=self._next)
        self._btn_skip.pack(side=tk.LEFT, padx=4)

        self._btn_undo = tk.Button(
            nav_frame, text="Undo last", command=self._undo, state=tk.DISABLED
        )
        self._btn_undo.pack(side=tk.LEFT, padx=4)

        self._counter_label = tk.Label(nav_frame, text="", font=("sans-serif", 10))
        self._counter_label.pack(side=tk.LEFT, padx=12)

        self._status_label = tk.Label(
            nav_frame, text="", font=("sans-serif", 9), fg="gray"
        )
        self._status_label.pack(side=tk.RIGHT, padx=8)

        # --- Image display ---
        self._canvas = tk.Canvas(self, bg="#1e1e1e")
        self._canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self._canvas.bind("<Configure>", lambda e: self._render_image())

        self._tk_image = None  # prevent GC
        self._pil_image = None
        self._last_action = None  # (src_path, dest_path) for undo

        # Keyboard shortcuts: 1-9, 0, q, w, e, r for the 14 maps
        keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "q", "w", "e", "r"]
        for i, key in enumerate(keys):
            self.bind(key, lambda event, l=MAP_LABELS[i]: self._label_current(l))

        self.bind("<Left>", lambda e: self._prev())
        self.bind("<Right>", lambda e: self._next())
        self.bind("<BackSpace>", lambda e: self._undo())

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _show_current(self):
        if self.current_index >= len(self.images):
            messagebox.showinfo("Done", "All images have been reviewed!")
            self.destroy()
            return

        path = self.images[self.current_index]
        self._counter_label.config(
            text=f"{self.current_index + 1} / {len(self.images)}"
        )
        self._status_label.config(text=os.path.basename(path))

        try:
            self._pil_image = Image.open(path).convert("RGB")
        except Exception as exc:
            messagebox.showerror("Error", f"Cannot open image:\n{exc}")
            self._next()
            return

        self._render_image()

    def _render_image(self):
        if self._pil_image is None:
            return
        cw = self._canvas.winfo_width()
        ch = self._canvas.winfo_height()
        if cw < 2 or ch < 2:
            return

        img = self._pil_image
        scale = min(cw / img.width, ch / img.height)
        new_w = max(1, int(img.width * scale))
        new_h = max(1, int(img.height * scale))
        resized = img.resize((new_w, new_h), Image.LANCZOS)

        self._tk_image = ImageTk.PhotoImage(resized)
        self._canvas.delete("all")
        self._canvas.create_image(cw // 2, ch // 2, anchor=tk.CENTER, image=self._tk_image)

    def _next(self):
        self.current_index += 1
        self._show_current()

    def _prev(self):
        if self.current_index > 0:
            self.current_index -= 1
            self._show_current()

    # ------------------------------------------------------------------
    # Labeling
    # ------------------------------------------------------------------

    def _label_current(self, label):
        if self.current_index >= len(self.images):
            return

        src = self.images[self.current_index]
        dest_dir = os.path.join(self.output_dir, label)
        dest = os.path.join(dest_dir, os.path.basename(src))

        shutil.copy2(src, dest)
        self._last_action = (src, dest)
        self._btn_undo.config(state=tk.NORMAL)

        print(f"  [{label}] {os.path.basename(src)}")
        self._next()

    def _undo(self):
        if self._last_action is None:
            return
        _, dest = self._last_action
        if os.path.exists(dest):
            os.remove(dest)
            print(f"  [undo] removed {dest}")
        self._last_action = None
        self._btn_undo.config(state=tk.DISABLED)
        if self.current_index > 0:
            self.current_index -= 1
            self._show_current()


def main():
    parser = argparse.ArgumentParser(
        description="Label extracted score frames by map name."
    )
    parser.add_argument(
        "source",
        nargs="?",
        default=None,
        help="Directory containing extracted frames (default: open folder picker).",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Directory for labeled output (default: <source>/labeled).",
    )
    args = parser.parse_args()

    source_dir = args.source
    if source_dir is None:
        root = tk.Tk()
        root.withdraw()
        source_dir = filedialog.askdirectory(title="Select frames directory")
        root.destroy()
        if not source_dir:
            print("No directory selected. Exiting.", file=sys.stderr)
            sys.exit(1)

    source_dir = os.path.abspath(source_dir)
    output_dir = args.output or os.path.join(source_dir, "labeled")

    print(f"Source:  {source_dir}")
    print(f"Output:  {output_dir}")
    print(f"Found {len(find_score_images(source_dir))} score images.\n")
    print("Keyboard shortcuts: 1-9, 0, q, w, e, r  |  Left/Right = nav  |  Backspace = undo\n")

    app = FrameLabelerApp(source_dir, output_dir)
    app.mainloop()


if __name__ == "__main__":
    main()
