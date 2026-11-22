"""Pydantic models shared by the whole server (DESIGN.md section 3.8)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

Position = Literal["front", "left", "right", "back"]
Level = Literal["none", "caution", "danger", "info"]  # white, yellow, orange, blue

POSITIONS: tuple[Position, ...] = ("front", "left", "right", "back")


class CameraRates(BaseModel):
    front: float = 20
    back: float = 10
    left: float = 8
    right: float = 8


class ObjectAlert(BaseModel):
    """One row of the 'Detection & alerts' screen (slide 35). Stored in `object_settings`."""

    title: str = ""
    is_safety: bool = False  # "Safety" badge on the slide
    detect: bool = True
    announce: bool = True
    alert_at_m: float
    recommended_m: float = 0  # "Reset to recommended" restores this
    min_m: float = 1  # the minus button stops here
    max_m: float = 50  # the plus button stops here
    show_text: bool = False
    phase: int = 1  # 1 = works now, 3 = later (signs, potholes...)

    @model_validator(mode="after")
    def _check_range(self) -> "ObjectAlert":
        if not self.recommended_m:
            self.recommended_m = self.alert_at_m
        if not (0 < self.min_m <= self.alert_at_m <= self.max_m):
            raise ValueError(f"alert distance {self.alert_at_m} m must be between {self.min_m} and {self.max_m} m")
        return self


class VisionType(BaseModel):
    peripheral_vision: bool = False
    night_blindness: bool = False
    night_vision: bool = False


class Zone(BaseModel):
    """Warning zone in normalised 0..1 coordinates, tested with an object's bottom-centre point.

    If `polygon` is set (list of [x, y] corners) the point must be inside it; this is used
    for the lane trapezoid, which narrows towards the horizon. Otherwise the point must be
    inside the x/y band.
    """

    x_min: float = 0.0
    x_max: float = 1.0
    y_min: float = 0.0
    y_max: float = 1.0
    polygon: list[tuple[float, float]] | None = None


def lane(bottom_left: float, bottom_right: float, top_left: float, top_right: float, top_y: float) -> Zone:
    """Trapezoid from the bottom edge of the frame up to `top_y` (about the horizon)."""
    return Zone(polygon=[(bottom_left, 1.0), (bottom_right, 1.0), (top_right, top_y), (top_left, top_y)])


def _default_alerts() -> dict[str, ObjectAlert]:
    # Recommended values from slide 35. Min/max: the slide shows "+" turned off at 20 m for
    # vehicles and potholes; the other limits are our choice.
    return {
        "vehicles": ObjectAlert(title="Vehicles", is_safety=True, alert_at_m=20, min_m=5, max_m=20),
        "people": ObjectAlert(title="People", is_safety=True, alert_at_m=6, min_m=2, max_m=15),
        "traffic_lights": ObjectAlert(title="Traffic lights", is_safety=True, alert_at_m=15, min_m=5, max_m=30, phase=3),
        "traffic_signs": ObjectAlert(title="Traffic signs", alert_at_m=17, show_text=True, min_m=5, max_m=30, phase=3),
        "speed_breakers": ObjectAlert(title="Speed breakers", alert_at_m=14, min_m=5, max_m=30, phase=3),
        "potholes": ObjectAlert(title="Potholes", alert_at_m=20, min_m=5, max_m=20, phase=3),
        "sign_boards": ObjectAlert(title="Sign boards", alert_at_m=6, announce=False, show_text=True, min_m=2, max_m=15, phase=3),
    }


def _default_zones() -> dict[str, Zone]:
    # Keys: "<camera>_<group>" where group is "people" or "vehicles" (section 3.6).
    return {
        # Own lane: wide at the bottom of the frame, narrow near the horizon, so cars
        # parked at the roadside fall outside it. People get a wider band (crossing).
        "front_people": lane(0.05, 0.95, 0.38, 0.62, 0.45),
        "front_vehicles": lane(0.18, 0.82, 0.45, 0.55, 0.45),
        "left_people": Zone(y_min=0.30),
        "left_vehicles": Zone(y_min=0.30),
        "right_people": Zone(y_min=0.30),
        "right_vehicles": Zone(y_min=0.30),
        "back_people": lane(0.05, 0.95, 0.38, 0.62, 0.45),
        "back_vehicles": lane(0.18, 0.82, 0.45, 0.55, 0.45),
    }


class Settings(BaseModel):
    model: str = "yolov8n.pt"
    device: str = "cuda:0"
    imgsz: int = 640
    conf: float = 0.35
    iou: float = 0.5
    det_fps: CameraRates = Field(default_factory=CameraRates)
    camera_on: dict[str, bool] = Field(default_factory=lambda: {p: True for p in POSITIONS})
    include_other_vehicles: bool = True  # bus, truck, motorcycle, bicycle -> vehicle
    hfov_deg: float = 70
    hold_seconds: float = 1.0
    caution_factor: float = 1.5
    confirm_detections: int = 2  # seen in N consecutive detections before warning
    track_low_conf: float = 0.15  # second-stage (low score) association, ByteTrack style
    track_iou: float = 0.3  # min IoU to match a detection to a track
    min_box_height_px: float = 4.0  # smaller boxes get no distance estimate
    voice_gap_s: float = 4.0  # viewers speak at most one sentence per this many seconds
    voice_repeat_s: float = 15.0  # the same warning (code) is not spoken again within this time
    # Vehicles ahead / behind (front and back cameras), so a car simply driving in front of us
    # in city traffic is not orange all the time:
    vehicle_close_m: float = 7.0  # closer than this is orange even if it is not coming closer
    closing_speed_mps: float = 2.0  # within the alert distance, orange only if it comes closer at least this fast
    ttc_danger_s: float = 3.0  # orange if it would reach us in less than this (time to collision)
    # Our path: the middle part of the lane our car drives in (share of the lane width). The
    # coming-closer rules apply only there, so parked cars at the lane edge we drive past stay yellow.
    path_width: float = 0.6
    path_min_overlap: float = 0.3  # a car must cover at least this share of our path to be orange
    # Left/right cameras: a parked car passes the side camera in well under a second while
    # we drive; an overtaking car stays longer. Warn only after this long in view.
    side_min_track_s: float = 0.8
    # Only objects on the road are shown: the own lane widened this many times (front/back),
    # from the bottom of the picture up to a little above the horizon.
    road_width_factor: float = 2.0
    road_above_horizon: float = 0.04
    # Incident recorder (slides 45-47): keep the last record_seconds of every camera.
    record_seconds: float = 90
    record_fps: float = 10
    incident_cooldown_s: float = 10  # a second save within this time is ignored
    # Vision type "peripheral vision": side cameras warn this many times earlier (slide 36).
    peripheral_side_factor: float = 1.5
    approach_max_m: float = 20.0  # time-to-collision rule only closer than this (farther, oncoming cars near the horizon looked "in our path")
    approach_window_s: float = 1.0  # longer window = steadier approach speed (distance estimates are noisy)
    smoother_alpha: float = 0.5
    smoother_max_predict_s: float = 0.3
    smoother_drop_s: float = 0.7
    zones: dict[str, Zone] = Field(default_factory=_default_zones)
    real_heights_m: dict[str, float] = Field(
        default_factory=lambda: {
            "person": 1.7,
            "car": 1.5,
            "bus": 3.0,
            "truck": 3.0,
            "motorcycle": 1.4,
            "bicycle": 1.4,
        }
    )
    alerts: dict[str, ObjectAlert] = Field(default_factory=_default_alerts)
    vision: VisionType = Field(default_factory=VisionType)
    voice: bool = True  # "Voice assistance" (slide 34)
    beep: bool = True  # "Beep" (slide 34)
    volume: float = Field(0.85, ge=0, le=1)  # "Voice volume" 85% (slide 34)
    speech_speed: float = Field(1.0, ge=0.5, le=2.0)  # "Speech speed" 1.0x (slide 34)
    ar_mirror: bool = False
    jpeg_quality: float = 0.7
    stream_fps: int = 30
    stream_width: int = 640
    stream_height: int = 360


IncidentCause = Literal["sudden_brake", "hard_jolt", "saved_by_driver"]  # slide 46


class IncidentWarning(BaseModel):
    """One line of "Warnings before it" (slide 47)."""

    camera: Position
    time_in_video_s: int
    message: str
    distance_m: int | None = None
    colour: Literal["orange", "yellow"]
    was_spoken: bool = False


class Incident(BaseModel):
    id: int
    cause: IncidentCause
    happened_at: datetime
    length_s: int = 90
    front_picture: str | None = None
    videos: dict[Position, str] = Field(default_factory=dict)
    warnings: list[IncidentWarning] = Field(default_factory=list)
