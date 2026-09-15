"""The AC8b frame-source seam — two corpora, one engine path.

The story's two deliverables consume DIFFERENT corpora:

* **Accuracy** (AC11/AC12/Task 8) runs on the 2666 labeled PNGs at
  ``output/labeled/v2/`` — the only corpus with ground truth, and the only one
  Tool 9's baseline covers.
* **ms/keyframe** (AC11/Task 7) runs on real video keyframes from ``videos/V2/``
  via the FFmpeg pipe.

Both feed the same ``(frame_bgr_at_ref) -> [bool; n_rules]`` shader path. This
seam sits in front of it so neither deliverable forks the engine.

No GL here. The video source shells out to FFmpeg, so tests mock it (AC16);
everything else in this module is pure enough to exercise directly.
"""

import glob
import os
import re
import sys
from dataclasses import dataclass
from typing import Iterator

import cv2
import numpy as np

from tools.roi_detection_tester import _resize_to_ref

# HUD-version directories under the labeled root are `v1`, `v2`, `v2.1`, ...
# A bare `startswith("v")` would also swallow any future sibling beginning with
# "v" (`videos/`, `validation/`, `v2_backup/`), silently ingesting it as a HUD
# version and polluting the HUD classifier's denominator.
_HUD_DIR_RE = re.compile(r"^v\d+(\.\d+)*$")


@dataclass(frozen=True)
class SourceFrame:
    """One frame on its way to the shader, at reference resolution."""

    frame_idx: int
    timestamp_ms: int
    frame_bgr: np.ndarray
    # Labeled-corpus provenance; None on the video path.
    path: str | None = None
    hud_dir: str | None = None
    folder: str | None = None


def _read_frame_bgr(path: str) -> np.ndarray | None:
    """Windows non-ASCII-path-safe PNG read — ``np.fromfile`` + ``cv2.imdecode``.

    NEVER ``cv2.imread``: it cannot open a non-ASCII path on Windows and returns
    None, which would present as a corrupt corpus. Hard convention in this
    package (``roi_detection_tester.py:485``).
    """
    try:
        buf = np.fromfile(path, dtype=np.uint8)
    except OSError:
        return None
    if buf.size == 0:
        return None
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


def iter_labeled_frames(
    labeled_root: str,
    ref_height: int,
    *,
    limit_per_class: int | None = None,
) -> Iterator[SourceFrame]:
    """Labeled PNGs -> :class:`SourceFrame`, at reference height.

    Mirrors Tool 9's ``iter_labeled_frames`` ordering — sorted
    ``(hud_dir, class, file)``, every ``v*`` HUD dir scanned so the HUD-version
    classifier sees cross-HUD negatives — WITHOUT importing it wholesale, because
    its signature yields a 4-tuple with no frame index and no timestamp. The
    ordering is the contract; reproduce it exactly or the per-frame comparison
    against Tool 9's frame_predictions.csv misaligns.

    Timestamps are meaningless for still frames and are reported as 0.
    """
    if not os.path.isdir(labeled_root):
        return
    try:
        hud_dirs = sorted(os.listdir(labeled_root))
    except OSError as exc:
        print(f"  WARN: cannot list {labeled_root} ({exc})", file=sys.stderr, flush=True)
        return

    idx = 0
    for hud_dir in hud_dirs:
        hud_path = os.path.join(labeled_root, hud_dir)
        if not _HUD_DIR_RE.match(hud_dir) or not os.path.isdir(hud_path):
            continue
        try:
            class_dirs = sorted(os.listdir(hud_path))
        except OSError as exc:
            print(f"  WARN: cannot list {hud_path} ({exc})", file=sys.stderr, flush=True)
            continue
        for class_name in class_dirs:
            class_dir = os.path.join(hud_path, class_name)
            if not os.path.isdir(class_dir):
                continue
            pngs = sorted(glob.glob(os.path.join(class_dir, "*.png")))
            if limit_per_class is not None:
                pngs = pngs[: int(limit_per_class)]
            for frame_path in pngs:
                img = _read_frame_bgr(frame_path)
                if img is None:
                    print(f"  WARN: cannot read {frame_path} - skipping", file=sys.stderr)
                    continue
                yield SourceFrame(
                    frame_idx=idx,
                    timestamp_ms=0,
                    frame_bgr=_resize_to_ref(img, ref_height),
                    path=frame_path,
                    hud_dir=hud_dir,
                    folder=class_name,
                )
                idx += 1


def iter_video_keyframes(
    video_path: str,
    ref_height: int,
    *,
    profile_stats: dict | None = None,
    extractor=None,
) -> Iterator[SourceFrame]:
    """Video keyframes -> :class:`SourceFrame`, streamed ONE AT A TIME (AC2).

    Never accumulates: 1061 keyframes x 6.2 MB would be 6.6 GB held.

    AC5 (reference-resolution parity) — the frames are decoded at NATIVE
    resolution and resized only if the source is not already at ``ref_height``.
    Do NOT scale twice: ``utils/video.py`` would scale inside FFmpeg (swscale
    bicubic, even-width rounding ``round(src_w*th/sh/2)*2``) while Tool 9's
    ``_resize_to_ref`` uses ``max(1, round(w*ref_h/h))`` with INTER_AREA. At
    1920x1080 -> 1080 both are no-ops and agree; at any other height they produce
    different widths and different pixels, which would confound the accuracy
    comparison. Our V2 captures are natively 1080, so in practice neither runs.

    ``extractor`` is injected for tests (AC16 forbids a real decode in the suite).
    """
    if extractor is None:
        from utils.video import extract_iframes_native
        extractor = extract_iframes_native

    for idx, (frame, ts) in enumerate(extractor(video_path, profile_stats=profile_stats)):
        yield SourceFrame(
            frame_idx=idx,
            timestamp_ms=int(round(float(ts) * 1000.0)),
            frame_bgr=_resize_to_ref(frame, ref_height),
        )
