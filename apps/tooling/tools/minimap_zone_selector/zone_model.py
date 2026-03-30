"""Zone data model and fire-detection logic."""

from dataclasses import dataclass, field

import cv2
import numpy as np

from utils.image import extract_roi, scale_roi

# HSV scale conversions (user-space -> OpenCV)
_H_USER_TO_CV = 179 / 360
_SV_USER_TO_CV = 255 / 100


@dataclass
class Zone:
    zone_id: str
    x: int
    y: int
    width: int
    height: int
    h_center: int  # 0-360
    h_tol: int
    s_center: int  # 0-100
    s_tol: int
    v_center: int  # 0-100
    v_tol: int
    min_ratio: float
    weight: float
    weight_override: bool


@dataclass
class MinimapConfig:
    id: str
    roi: dict  # {name, x, y, width, height} at reference resolution
    identification_threshold: float
    maps: dict = field(default_factory=dict)  # map_label -> list[Zone]


def zone_fires(zone: Zone, bgr_frame: np.ndarray, ref_w: int = 1920, ref_h: int = 1080) -> bool:
    """Test whether a zone's HSV criteria are met in the given frame.

    Args:
        zone: Zone with full-frame reference coordinates and HSV params.
        bgr_frame: Full-frame BGR numpy array.
        ref_w: Reference width for zone coordinates.
        ref_h: Reference height for zone coordinates.

    Returns:
        True if the ratio of in-range pixels meets zone.min_ratio.
    """
    frame_h, frame_w = bgr_frame.shape[:2]
    scale = frame_w / ref_w

    roi_dict = {
        "name": zone.zone_id,
        "x": zone.x,
        "y": zone.y,
        "width": zone.width,
        "height": zone.height,
    }
    scaled_roi = scale_roi(roi_dict, scale)
    region = extract_roi(bgr_frame, scaled_roi)

    hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)

    # Convert user-space HSV to OpenCV scale
    h_lo = round((zone.h_center - zone.h_tol) * _H_USER_TO_CV)
    h_hi = round((zone.h_center + zone.h_tol) * _H_USER_TO_CV)
    s_lo = max(0, round((zone.s_center - zone.s_tol) * _SV_USER_TO_CV))
    s_hi = min(255, round((zone.s_center + zone.s_tol) * _SV_USER_TO_CV))
    v_lo = max(0, round((zone.v_center - zone.v_tol) * _SV_USER_TO_CV))
    v_hi = min(255, round((zone.v_center + zone.v_tol) * _SV_USER_TO_CV))

    # Handle hue wraparound
    if h_lo < 0 or h_hi > 179:
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

    return np.count_nonzero(mask) / mask.size >= zone.min_ratio
