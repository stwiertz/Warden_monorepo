"""Image processing utilities for the Warden pipeline.

Stateless helper functions using OpenCV. Designed for reuse across
Tool 1 (black screen detector), Tool 3 (pixel finder), and Tool 4 (validation).
"""

import sys

import cv2
import numpy as np


def downscale(frame, target_height):
    """Resize a frame proportionally to target height.

    If the frame is already at or below target_height, returns it unchanged
    with the appropriate scale factor.

    Args:
        frame: BGR numpy array (height, width, 3).
        target_height: Desired output height in pixels.

    Returns:
        tuple: (resized_frame, scale_factor) where scale_factor is
               target_height / original_height.
    """
    h, w = frame.shape[:2]
    scale_factor = target_height / h
    # F7: don't upscale — return original frame if already at or below target
    if target_height >= h:
        return frame, scale_factor
    target_width = int(w * scale_factor)
    resized = cv2.resize(frame, (target_width, target_height), interpolation=cv2.INTER_AREA)
    return resized, scale_factor


def to_grayscale(frame):
    """Convert a BGR frame to single-channel grayscale.

    Args:
        frame: BGR numpy array (height, width, 3).

    Returns:
        numpy array (height, width) — single channel grayscale.
    """
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


def scale_roi(roi, scale_factor):
    """Scale an ROI dict from reference resolution to processing resolution.

    Args:
        roi: Dict with keys 'name', 'x', 'y', 'width', 'height' at reference resolution.
        scale_factor: Ratio of processing resolution to reference resolution.

    Returns:
        dict: New ROI with integer coordinates scaled to processing resolution.
    """
    return {
        "name": roi["name"],
        "x": int(roi["x"] * scale_factor),
        "y": int(roi["y"] * scale_factor),
        "width": max(1, int(roi["width"] * scale_factor)),
        "height": max(1, int(roi["height"] * scale_factor)),
    }


def extract_roi(frame, roi):
    """Crop an ROI region from a frame.

    Args:
        frame: numpy array (2D grayscale or 3D color).
        roi: Dict with 'x', 'y', 'width', 'height' keys.

    Returns:
        numpy array: The cropped region.

    Raises:
        ValueError: If the ROI is entirely outside the frame bounds.
    """
    fh, fw = frame.shape[:2]
    x, y, w, h = roi["x"], roi["y"], roi["width"], roi["height"]

    # F3: validate ROI is within frame bounds
    if x >= fw or y >= fh:
        raise ValueError(
            f"ROI '{roi.get('name', '?')}' starts outside frame bounds: "
            f"roi=({x},{y},{w},{h}), frame=({fw},{fh})"
        )

    # Clamp to frame edges and warn if truncated
    x2 = min(x + w, fw)
    y2 = min(y + h, fh)
    if (x2 - x) < w or (y2 - y) < h:
        print(
            f"Warning: ROI '{roi.get('name', '?')}' truncated to fit frame: "
            f"requested ({x},{y},{w},{h}), actual ({x},{y},{x2-x},{y2-y})",
            file=sys.stderr,
        )

    return frame[y:y2, x:x2]


def is_black(region, threshold):
    """Check if a grayscale region's mean brightness is at or below a threshold.

    Args:
        region: Single-channel (grayscale) numpy array.
        threshold: Maximum mean pixel value (0-255) to be considered black.
            A region with mean brightness <= threshold is considered black.

    Returns:
        bool: True if the region's mean pixel value is at or below the threshold.
    """
    # F10: use <= for intuitive "at or below threshold" semantics
    return float(np.mean(region)) <= threshold
