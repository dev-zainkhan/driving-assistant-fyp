"""Warning engine (DESIGN.md 3.6). Pure Python; every number comes from Settings.

Per object: level none (white) / caution (yellow) / danger (orange).
Per camera: the highest active level, held for `hold_seconds` after the last
qualifying object so slots do not flicker.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.core.tracker import Track
from app.models.schemas import Settings

LEVEL_RANK = {"none": 0, "info": 1, "caution": 2, "danger": 3}

CODES = {
    ("front", "people"): "PERSON_AHEAD",
    ("front", "vehicles"): "VEHICLE_AHEAD",
    ("left", "people"): "PERSON_LEFT",
    ("left", "vehicles"): "VEHICLE_LEFT",
    ("right", "people"): "PERSON_RIGHT",
    ("right", "vehicles"): "VEHICLE_RIGHT",
    ("back", "people"): "PERSON_BEHIND",
    ("back", "vehicles"): "VEHICLE_BEHIND",
}

SIDE_CAMERAS = frozenset({"left", "right"})

# Cameras where vehicles use the closing-speed rule (see WarningEngine.vehicle_level).
CLOSING_CAMERAS = frozenset({"front", "back"})


def warning_text(camera: str, cls: str, distance_m: float | None) -> str:
    name = cls.capitalize()
    if camera == "front":
        base = f"{name} ahead"
        return f"{base}, {round(distance_m)} m" if distance_m is not None else base
    if camera == "back":
        return f"{name} behind"
    return f"{name} on {camera}"


def bottom_centre(box) -> tuple[float, float]:
    return (box[0] + box[2]) / 2, box[3]


def point_in_polygon(x: float, y: float, poly) -> bool:
    """Ray casting; points exactly on the bottom edge (y = 1) count as inside."""
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xc = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < xc:
                inside = not inside
    return inside


def in_zone(settings: Settings, camera: str, group: str, box) -> bool:
    z = settings.zones.get(f"{camera}_{group}")
    if z is None:
        return True
    x, y = bottom_centre(box)
    if z.polygon:
        return point_in_polygon(x, min(y, 0.9999), z.polygon)
    return z.x_min <= x <= z.x_max and z.y_min <= y <= z.y_max


def _lane_at(settings: Settings, camera: str, y: float) -> tuple[float, float] | None:
    """Middle and half-width of the lane at picture height y. None without a lane trapezoid."""
    z = settings.zones.get(f"{camera}_vehicles")
    if z is None or not z.polygon or len(z.polygon) != 4:
        return None
    (blx, by), (brx, _), (trx, ty), (tlx, _) = z.polygon
    t = min(1.0, max(0.0, (by - y) / (by - ty))) if by != ty else 0.0
    left, right = blx + t * (tlx - blx), brx + t * (trx - brx)
    half = (right - left) / 2
    return ((left + right) / 2, half) if half > 0 else None


def lane_position(settings: Settings, camera: str, box) -> float | None:
    """Where the object's bottom-centre sits across the lane: 0 = middle, -1 / +1 = edges."""
    x, y = bottom_centre(box)
    lane = _lane_at(settings, camera, y)
    return None if lane is None else (x - lane[0]) / lane[1]


def path_overlap(settings: Settings, camera: str, box) -> float | None:
    """How much the box and our path (the middle path_width of the lane) overlap, 0..1,
    measured at the box's bottom, as a share of the narrower of the two: a far car (narrow
    box) in the middle gives 1.0, a parked car at the lane edge gives almost 0.
    None without a lane trapezoid."""
    lane = _lane_at(settings, camera, box[3])
    if lane is None:
        return None
    mid, half = lane
    p_half = half * settings.path_width
    covered = max(0.0, min(box[2], mid + p_half) - max(box[0], mid - p_half))
    narrower = min(box[2] - box[0], 2 * p_half)
    return covered / narrower if narrower > 0 else 0.0


def road_polygon(settings: Settings, camera: str) -> list[tuple[float, float]] | None:
    """Road area of a front/back camera: its lane trapezoid widened by road_width_factor and
    raised a little above the horizon. None if the camera has no lane trapezoid."""
    z = settings.zones.get(f"{camera}_vehicles")
    if z is None or not z.polygon or len(z.polygon) != 4:
        return None
    (blx, by), (brx, _), (trx, ty), (tlx, _) = z.polygon
    k = settings.road_width_factor
    cb, wb = (blx + brx) / 2, (brx - blx) * k / 2
    ct, wt = (tlx + trx) / 2, (trx - tlx) * k / 2
    top = max(0.0, ty - settings.road_above_horizon)
    return [(cb - wb, by), (cb + wb, by), (ct + wt, top), (ct - wt, top)]


def on_road(settings: Settings, camera: str, box) -> bool:
    """Is the object on the road (shown), or off to the side / up in buildings (hidden)?"""
    if camera in SIDE_CAMERAS:
        return in_zone(settings, camera, "vehicles", box)  # side cameras: lower part of the picture
    poly = road_polygon(settings, camera)
    if poly is None:
        return True
    x, y = bottom_centre(box)
    return point_in_polygon(x, min(y, 0.9999), poly)


MIN_APPROACH_POINTS = 4


def approach_speed(tr: Track, now: float, window_s: float) -> float:
    """Metres per second the object is getting closer (positive = approaching).

    The distance comes from the box height, which jumps a little from frame to frame (a car
    27 m away is only ~25 px tall, so 1 px is about 1 m). Using only the first and last point
    turned that noise into fake "approaching fast" warnings, so this fits a straight line
    (least squares) through all points in the window and uses its slope.
    """
    pts = [(t, d) for t, d in tr.dist_hist if now - t <= window_s]
    if len(pts) < MIN_APPROACH_POINTS or pts[-1][0] - pts[0][0] < window_s * 0.4:
        return 0.0
    n = len(pts)
    mt = sum(t for t, _ in pts) / n
    md = sum(d for _, d in pts) / n
    var = sum((t - mt) ** 2 for t, _ in pts)
    if var <= 0:
        return 0.0
    slope = sum((t - mt) * (d - md) for t, d in pts) / var  # metres per second, negative = closer
    return -slope


@dataclass(slots=True)
class _Active:
    level: str  # latest level seen for this warning code
    until: float  # the code stays active until then (hold time after the last sighting)
    text: str
    distance_m: float | None
    danger_until: float = 0.0  # orange is kept until then, so the colour does not flicker

    def effective(self, now: float) -> str:
        return "danger" if now <= self.danger_until else self.level


@dataclass
class CameraWarning:
    level: str = "none"
    codes: list[str] = field(default_factory=list)
    text: str = ""
    since: float = 0.0  # seconds (time.time)

    def to_json(self) -> dict:
        return {"level": self.level, "codes": list(self.codes), "text": self.text, "since": int(self.since * 1000)}


class WarningEngine:
    """One instance per camera."""

    def __init__(self, camera: str, settings: Settings) -> None:
        self.camera = camera
        self.settings = settings
        self.state = CameraWarning()
        self._active: dict[str, _Active] = {}
        self._levels: dict[int, str] = {}  # last level of each track

    def object_level(self, tr: Track, now: float) -> str:
        s = self.settings
        alert = s.alerts.get(tr.group)
        if alert is None or tr.hits < s.confirm_detections or tr.distance_m is None:
            return "none"
        if not in_zone(s, self.camera, tr.group, tr.box):
            return "none"
        if self.camera in SIDE_CAMERAS and now - tr.first_t < s.side_min_track_s:
            return "none"  # passing by quickly (e.g. parked car while we drive)
        d = tr.distance_m
        alert_at = alert.alert_at_m
        if self.camera in SIDE_CAMERAS and s.vision.peripheral_vision:
            alert_at *= s.peripheral_side_factor  # slide 36: warn earlier about things at your sides
        if tr.group == "vehicles" and self.camera in CLOSING_CAMERAS:
            return self.vehicle_level(tr, d, alert_at, now)
        if d <= alert_at:
            return "danger"
        if d <= alert_at * s.caution_factor:
            return "caution"
        return "none"

    def vehicle_level(self, tr: Track, d: float, alert_at: float, now: float) -> str:
        """Closing-speed rule for a vehicle in our lane ahead (front) or behind (back).

        In city traffic the car in front is often within the 20 m alert distance for minutes;
        it is only a danger if it is very close or the gap is shrinking:
          Only if the box covers at least path_min_overlap of our path (the middle path_width
          of the lane); beside our path it is at most yellow. Then orange when:
                  closer than vehicle_close_m, or
                  within alert_at and coming closer at >= closing_speed_mps, or
                  would reach us in under ttc_danger_s (time to collision), within approach_max_m
          yellow: within caution_factor x alert_at
        """
        s = self.settings
        closing = approach_speed(tr, now, s.approach_window_s)  # m/s, positive = gap shrinking
        overlap = path_overlap(s, self.camera, tr.box)
        if overlap is not None and overlap < s.path_min_overlap:
            # in the lane but beside our path (e.g. a parked car at the edge we drive past)
            return "caution" if d <= alert_at * s.caution_factor else "none"
        if d <= s.vehicle_close_m:
            return "danger"
        if d <= alert_at and closing >= s.closing_speed_mps:
            return "danger"
        if closing > 0 and d < s.approach_max_m and d / closing < s.ttc_danger_s:
            return "danger"
        if d <= alert_at * s.caution_factor:
            return "caution"
        return "none"

    def update(self, tracks: list[Track], now: float) -> tuple[dict[int, str], bool]:
        """Returns (level per track id, camera state changed)."""
        levels: dict[int, str] = {}
        best: dict[str, tuple[str, Track]] = {}
        latest = max((tr.last_det_t for tr in tracks), default=0.0)
        for tr in tracks:
            if tr.last_det_t < latest - 1e-6:
                # Not seen in this detection round (kept a moment by the tracker): keep its
                # colour on screen, but do not let its old distance keep the warning alive.
                levels[tr.track_id] = self._levels.get(tr.track_id, "none")
                continue
            lvl = self.object_level(tr, now)
            levels[tr.track_id] = lvl
            if lvl in ("caution", "danger"):
                code = CODES[(self.camera, tr.group)]
                prev = best.get(code)
                if (
                    prev is None
                    or LEVEL_RANK[lvl] > LEVEL_RANK[prev[0]]
                    or (lvl == prev[0] and (tr.distance_m or 1e9) < (prev[1].distance_m or 1e9))
                ):
                    best[code] = (lvl, tr)
        self._levels = levels
        hold = self.settings.hold_seconds
        for code, (lvl, tr) in best.items():
            prev = self._active.get(code)
            danger_until = now + hold if lvl == "danger" else (prev.danger_until if prev else 0.0)
            self._active[code] = _Active(
                lvl, now + hold, warning_text(self.camera, tr.cls, tr.distance_m), tr.distance_m, danger_until
            )
        return levels, self._refresh(now)

    def _refresh(self, now: float) -> bool:
        for code in [c for c, a in self._active.items() if a.until < now]:
            del self._active[code]
        if self._active:
            eff = {c: a.effective(now) for c, a in self._active.items()}
            top_code, top = max(
                self._active.items(), key=lambda kv: (LEVEL_RANK[eff[kv[0]]], -(kv[1].distance_m or 1e9))
            )
            level, text = eff[top_code], top.text
            codes = sorted(self._active, key=lambda c: -LEVEL_RANK[eff[c]])
        else:
            level, text, codes = "none", "", []
        changed = level != self.state.level or set(codes) != set(self.state.codes)
        if changed:
            self.state.since = now
        self.state.level, self.state.codes, self.state.text = level, codes, text
        return changed

    def tick(self, now: float) -> bool:
        """Expire held warnings when no detection runs (camera stalled)."""
        return self._refresh(now)
