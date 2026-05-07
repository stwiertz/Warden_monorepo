"""Frame Labeler — GUI tool for manually labeling extracted frames by map name.

Scans the output directory for PNG files with 'score' in the filename,
displays them one by one, and lets the user assign a map label via buttons.
When a score frame is labeled, the matching start and end frames from the same
game session are automatically co-exported. All three files are named
{counter:03d}_{type}.png and placed flat in labeled/<map>/. Labeled images are
copied (non-destructive) into per-map subdirectories under a configurable
labeled-data folder.
"""

import argparse
import glob
import os
import re
import shutil
import sys
import tkinter as tk
from tkinter import filedialog, messagebox

from PIL import Image, ImageTk

MAP_LABELS = [
    "artefact",
    "atlantis",
    "bastion",
    "ceres",
    "coliseum",
    "engine",
    "helios",
    "horizon",
    "lunar_outpost",
    "outlaw",
    "polaris",
    "silva",
    "the_cliff",
    "the_rock",
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


def find_frame_images(source_dir, frame_type="all"):
    """Return sorted list of PNG paths matching the given frame type.

    Args:
        source_dir: Directory to scan recursively.
        frame_type: One of 'score', 'start', 'end', 'all'.
    """
    type_patterns = {
        "score": ["*_score*.png"],
        "start": ["*_start*.png"],
        "end":   ["*_end*.png"],
        "all":   ["*_score*.png", "*_start*.png", "*_end*.png"],
    }
    patterns = type_patterns.get(frame_type, type_patterns["all"])
    seen = set()
    paths = []
    for pattern in patterns:
        for p in glob.glob(os.path.join(source_dir, "**", pattern), recursive=True):
            if p not in seen:
                seen.add(p)
                paths.append(p)
    paths.sort()
    return paths


def find_score_images(source_dir):
    """Backward-compatible alias for find_frame_images with frame_type='score'."""
    return find_frame_images(source_dir, frame_type="score")


def parse_seq_num(filename):
    """Return the trailing sequence integer from a filename like '00m14s_start_001.png', or None."""
    match = re.search(r'_(\d+)\.png$', filename)
    return int(match.group(1)) if match else None


def find_linked_frames(score_path):
    """Find the start and end frames that belong to the same game session as the given score frame.

    Scans the same directory as score_path. Uses the global sequence number
    embedded in filenames to identify the most recent start/end before the score.
    Returns (start_path, end_path); either may be None if not found.
    """
    score_seq = parse_seq_num(os.path.basename(score_path))
    if score_seq is None:
        return None, None

    scan_dir = os.path.dirname(score_path) or "."
    start_candidates = []  # (seq, full_path)
    end_candidates = []

    try:
        entries = os.listdir(scan_dir)
    except OSError:
        return None, None

    for fname in entries:
        if not fname.endswith('.png'):
            continue
        seq = parse_seq_num(fname)
        if seq is None or seq >= score_seq:
            continue
        full = os.path.join(scan_dir, fname)
        if re.search(r'_start_\d+\.png$', fname):
            start_candidates.append((seq, full))
        elif re.search(r'_end_\d+\.png$', fname):
            end_candidates.append((seq, full))

    start_path = max(start_candidates, key=lambda x: x[0])[1] if start_candidates else None
    start_seq = parse_seq_num(os.path.basename(start_path)) if start_path else -1

    valid_ends = [(s, p) for s, p in end_candidates if s > start_seq]
    end_path = max(valid_ends, key=lambda x: x[0])[1] if valid_ends else None

    return start_path, end_path


def next_game_counter(dest_dir):
    """Return the next sequential game counter for a labeled map directory.

    Counts existing *_score.png files to determine the next number.
    """
    existing = glob.glob(os.path.join(dest_dir, '*_score.png'))
    return len(existing) + 1


def next_frame_counter(dest_dir, frame_type):
    """Return the next counter for a non-score frame type in a labeled map directory."""
    existing = glob.glob(os.path.join(dest_dir, f'*_{frame_type}.png'))
    return len(existing) + 1


def detect_frame_type(basename):
    """Detect frame type ('score', 'start', 'end') from a filename, defaulting to 'score'."""
    if re.search(r'_start[_.]', basename):
        return 'start'
    if re.search(r'_end[_.]', basename):
        return 'end'
    return 'score'


class FrameLabelerApp(tk.Tk):
    """Main labeling window."""

    def __init__(self, source_dir, output_dir, frame_type="all"):
        super().__init__()

        self.source_dir = source_dir
        self.output_dir = output_dir
        self.frame_type = frame_type
        self.images = find_frame_images(source_dir, frame_type)
        self.current_index = 0

        if not self.images:
            messagebox.showinfo(
                "No images",
                f"No PNG files matching type '{frame_type}' found in:\n{source_dir}",
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
        self._last_action = None  # list of dest paths for undo

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
        ftype = detect_frame_type(os.path.basename(src))
        copied = []

        if ftype == 'score':
            # Score frame: auto-link and export start/end from the same session
            counter = next_game_counter(dest_dir)
            start_src, end_src = find_linked_frames(src)
            score_dest = os.path.join(dest_dir, f"{counter:03d}_score.png")
            try:
                shutil.copy2(src, score_dest)
                copied.append(score_dest)
                if start_src:
                    start_dest = os.path.join(dest_dir, f"{counter:03d}_start.png")
                    shutil.copy2(start_src, start_dest)
                    copied.append(start_dest)
                if end_src:
                    end_dest = os.path.join(dest_dir, f"{counter:03d}_end.png")
                    shutil.copy2(end_src, end_dest)
                    copied.append(end_dest)
            except Exception as exc:
                for path in copied:
                    if os.path.exists(path):
                        os.remove(path)
                messagebox.showerror("Error", f"Failed to copy frames:\n{exc}")
                return

            if not start_src or not end_src:
                missing = [t for t, p in [('start', start_src), ('end', end_src)] if not p]
                print(f"  [warn] no {'/'.join(missing)} found for {os.path.basename(src)}")

            linked = [t for t, p in [('start', start_src), ('end', end_src)] if p]
            extra = f"(+ {', '.join(linked)})" if linked else "(score only)"
            print(f"  [{label}] {counter:03d}_score.png {extra}")
        else:
            # Non-score frame (start/end): copy single frame
            counter = next_frame_counter(dest_dir, ftype)
            dest = os.path.join(dest_dir, f"{counter:03d}_{ftype}.png")
            try:
                shutil.copy2(src, dest)
                copied.append(dest)
            except Exception as exc:
                messagebox.showerror("Error", f"Failed to copy frame:\n{exc}")
                return
            print(f"  [{label}] {counter:03d}_{ftype}.png")

        self._last_action = copied
        self._btn_undo.config(state=tk.NORMAL)
        self._next()

    def _undo(self):
        if self._last_action is None:
            return
        for dest in self._last_action:
            if os.path.exists(dest):
                os.remove(dest)
                print(f"  [undo] removed {os.path.basename(dest)}")
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
    parser.add_argument(
        "--type",
        dest="frame_type",
        choices=["score", "start", "end", "all"],
        default="all",
        help="Frame type to scan for labeling (default: all).",
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
    found = find_frame_images(source_dir, args.frame_type)
    print(f"Found {len(found)} '{args.frame_type}' frame(s).\n")
    print("Keyboard shortcuts: 1-9, 0, q, w, e, r  |  Left/Right = nav  |  Backspace = undo\n")

    app = FrameLabelerApp(source_dir, output_dir, frame_type=args.frame_type)
    app.mainloop()


if __name__ == "__main__":
    main()
