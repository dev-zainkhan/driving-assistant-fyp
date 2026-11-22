"""Pinhole distance estimate (DESIGN.md 3.6): distance = real_height * focal_px / box_height_px."""
from __future__ import annotations

import math


def focal_px(frame_width_px: float, hfov_deg: float) -> float:
    return (frame_width_px / 2) / math.tan(math.radians(hfov_deg) / 2)


def estimate_distance_m(
    box: tuple[float, float, float, float],
    cls: str,
    frame_w: int,
    frame_h: int,
    hfov_deg: float,
    real_heights_m: dict[str, float],
    min_box_height_px: float,
) -> float | None:
    real_h = real_heights_m.get(cls)
    if real_h is None:
        return None
    h_px = (box[3] - box[1]) * frame_h
    if h_px < min_box_height_px:
        return None
    return real_h * focal_px(frame_w, hfov_deg) / h_px
