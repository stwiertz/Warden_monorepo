"""Data loader for labeled minimap images."""

import os
import sys

import cv2
import numpy as np
from PIL import Image

from tools.frame_labeler import MAP_LABELS


class MinimapDataLoader:
    """Loads and serves labeled map images for zone validation.

    Args:
        labeled_dir: Root directory containing per-map subdirectories of PNGs.
        minimap_roi_ref: ROI dict with x, y, width, height at reference resolution.
        ref_w: Reference frame width (default 1920).
        ref_h: Reference frame height (default 1080).
    """

    def __init__(self, labeled_dir, minimap_roi_ref, ref_w=1920, ref_h=1080):
        self._labeled_dir = labeled_dir
        self._minimap_roi_ref = minimap_roi_ref
        self._ref_w = ref_w
        self._ref_h = ref_h
        self._frames: dict[str, list[np.ndarray]] = {}

        for map_name in MAP_LABELS:
            map_dir = os.path.join(labeled_dir, map_name)
            if not os.path.isdir(map_dir):
                print(
                    f"[WARN] Missing labeled directory for '{map_name}': {map_dir}",
                    file=sys.stderr,
                )
                self._frames[map_name] = []
                continue

            frames = []
            for fname in sorted(os.listdir(map_dir)):
                if not fname.lower().endswith(".png"):
                    continue
                if fname.lower().endswith("_score.png"):
                    continue
                path = os.path.join(map_dir, fname)
                frame = cv2.imread(path)
                if frame is None:
                    print(
                        f"[WARN] Could not read image: {path}",
                        file=sys.stderr,
                    )
                    continue
                fh, fw = frame.shape[:2]
                if fw != ref_w or fh != ref_h:
                    print(
                        f"[WARN] {path}: frame is {fw}\u00d7{fh}, expected "
                        f"{ref_w}\u00d7{ref_h} \u2014 zone coords may be inaccurate",
                        file=sys.stderr,
                    )
                frames.append(frame)

            self._frames[map_name] = frames

    def get_frames(self, map_name: str) -> list[np.ndarray]:
        """All full-frame BGR arrays for a map."""
        return self._frames.get(map_name, [])

    def get_all_frames(self) -> dict[str, list[np.ndarray]]:
        """All maps -> frame lists."""
        return dict(self._frames)

    def get_reference_image(self, map_name: str, index: int = 0):
        """Return frame at index as PIL RGB Image, or None."""
        frames = self._frames.get(map_name, [])
        if not frames or index < 0 or index >= len(frames):
            return None
        bgr = frames[index]
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb)

    def frame_count(self, map_name: str) -> int:
        return len(self._frames.get(map_name, []))

    def all_map_names(self) -> list[str]:
        """Maps with at least one image loaded."""
        return [m for m in MAP_LABELS if self._frames.get(m)]
