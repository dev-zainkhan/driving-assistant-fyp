"""Each rule row of DESIGN.md 3.6 gives the expected level."""
import pytest

from app.core.detector import Detection
from app.core.distance import estimate_distance_m, focal_px
from app.core.tracker import CameraTracker, iou
from app.core.warnings import WarningEngine, warning_text
from app.models.schemas import Settings

W, H = 640, 360
F = focal_px(W, 70)  # ~457 px


def box_for(distance_m: float, real_h: float, cx: float = 0.5, bottom: float = 0.9) -> tuple:
    """Box whose pinhole distance is `distance_m`, bottom-centre at (cx, bottom)."""
    h = real_h * F / distance_m / H
    w = h * 0.5
    return (cx - w / 2, bottom - h, cx + w / 2, bottom)


def run(camera, cls, distance, cx=0.5, bottom=0.9, cycles=3, settings=None, t0=0.0, dt=0.05):
    s = settings or Settings()
    tracker, engine = CameraTracker(s), WarningEngine(camera, s)
    real_h = s.real_heights_m[cls]
    levels = {}
    for i in range(cycles):
        t = t0 + i * dt
        tracks = tracker.update([Detection(cls, 0.9, box_for(distance, real_h, cx, bottom))], t, W, H)
        levels, _ = engine.update(tracks, t)
    return list(levels.values())[0], engine


def test_focal_length():
    assert F == pytest.approx(457, abs=1)


def test_distance_estimate():
    d = estimate_distance_m(box_for(10, 1.7), "person", W, H, 70, Settings().real_heights_m, 4)
    assert d == pytest.approx(10, rel=1e-6)


def test_tiny_box_has_no_distance():
    assert estimate_distance_m((0.5, 0.5, 0.51, 0.505), "person", W, H, 70, Settings().real_heights_m, 4) is None


@pytest.mark.parametrize(
    "camera,cls,distance,expected",
    [
        ("front", "person", 5, "danger"),     # <= 6 m
        ("front", "person", 8, "caution"),    # <= 9 m
        ("front", "person", 12, "none"),
        ("front", "car", 18, "caution"),      # within 20 m but not coming closer: yellow
        ("front", "car", 6, "danger"),        # closer than vehicle_close_m (7 m): orange
        ("front", "car", 28, "caution"),      # <= 30 m
        ("front", "car", 40, "none"),
        ("left", "car", 15, "danger"),
        ("right", "person", 7, "caution"),
        ("back", "truck", 25, "caution"),
        ("back", "person", 4, "danger"),
    ],
)
def test_rule_levels(camera, cls, distance, expected):
    level, engine = run(camera, cls, distance, cycles=12, dt=0.1)
    assert level == expected
    assert engine.state.level == expected


def test_outside_zone_is_white():
    level, _ = run("front", "person", 3, cx=0.1)  # front people zone is x 0.25..0.75
    assert level == "none"


def test_parked_car_at_roadside_is_not_a_warning():
    # 12 m away, bottom of box at y 0.62, at the side of the road (x 0.30): outside the lane
    level, engine = run("front", "car", 12, cx=0.30, bottom=0.62)
    assert level == "none" and engine.state.level == "none"


def test_car_in_own_lane_far_up_is_a_warning():
    level, _ = run("front", "car", 12, cx=0.50, bottom=0.62)
    assert level == "caution"  # in our lane, 12 m, not coming closer: yellow


def test_parked_car_passing_fast_is_not_danger():
    # We drive past a parked car: it "approaches" fast, but it is outside our lane.
    s = Settings()
    tracker, engine = CameraTracker(s), WarningEngine("front", s)
    level = None
    for i in range(11):
        t = i * 0.05
        d = 29 - 10 * t
        tracks = tracker.update([Detection("car", 0.9, box_for(d, 1.5, cx=0.12, bottom=0.8))], t, W, H)
        levels, _ = engine.update(tracks, t)
        level = list(levels.values())[0]
    assert level == "none"


def test_lane_polygon_shape():
    from app.core.warnings import point_in_polygon
    from app.models.schemas import lane

    poly = lane(0.18, 0.82, 0.45, 0.55, 0.45).polygon
    assert point_in_polygon(0.5, 0.99, poly)
    assert point_in_polygon(0.2, 0.98, poly)  # wide near the car
    assert not point_in_polygon(0.3, 0.55, poly)  # narrow further away
    assert not point_in_polygon(0.5, 0.40, poly)  # above the horizon


def test_side_car_passing_quickly_is_ignored():
    # Parked car sweeping past the left camera: in view for only 0.4 s
    level, engine = run("left", "car", 5, cycles=4, dt=0.1)
    assert level == "none" and engine.state.level == "none"


def test_side_car_staying_beside_us_warns():
    # Overtaking car stays in view: after 0.8 s it warns
    level, engine = run("left", "car", 5, cycles=10, dt=0.1)
    assert level == "danger" and engine.state.codes == ["VEHICLE_LEFT"]


def test_side_upper_part_ignored():
    level, _ = run("left", "car", 10, bottom=0.2)  # side zone is lower 70% (y >= 0.3)
    assert level == "none"


def test_needs_two_detections():
    level, engine = run("front", "person", 3, cycles=1)
    assert level == "none" and engine.state.level == "none"


def test_codes_and_text():
    _, engine = run("front", "person", 5)
    assert engine.state.codes == ["PERSON_AHEAD"]
    assert engine.state.text == "Person ahead, 5 m"
    _, engine = run("back", "car", 10)
    assert engine.state.codes == ["VEHICLE_BEHIND"] and engine.state.text == "Car behind"
    assert warning_text("left", "car", 3) == "Car on left"


def test_hold_time_then_clear():
    s = Settings()
    _, engine = run("back", "car", 5, settings=s)  # very close behind: orange
    assert engine.state.level == "danger"
    assert engine.tick(0.1 + 0.9) is False  # still held (hold 1.0 s after last at t=0.1)
    assert engine.state.level == "danger"
    assert engine.tick(0.1 + 1.01) is True
    assert engine.state.level == "none" and engine.state.codes == []


def test_fast_approaching_car_turns_orange_once_within_20_m():
    # A car closing at 10 m/s from 29 m: yellow while it is still beyond 20 m (lanes are hard to
    # tell apart that far away), orange as soon as it is within 20 m and coming closer.
    s = Settings()
    tracker, engine = CameraTracker(s), WarningEngine("front", s)
    seen = []
    for i in range(16):
        t = i * 0.05
        d = 29 - 10 * t  # 29 m down to 21.5 m
        levels, _ = engine.update(tracker.update([Detection("car", 0.9, box_for(d, 1.5))], t, W, H), t)
        seen.append((round(d, 1), list(levels.values())[0]))
    assert all(lvl != "danger" for d, lvl in seen if d > 20.5), seen
    for i in range(16, 24):
        t = i * 0.05
        d = 29 - 10 * t  # now 21 m -> 17.5 m
        levels, _ = engine.update(tracker.update([Detection("car", 0.9, box_for(d, 1.5))], t, W, H), t)
    assert list(levels.values())[0] == "danger"

def test_alert_distance_comes_from_settings():
    s = Settings()
    s.alerts["people"].alert_at_m = 3
    assert run("front", "person", 4, settings=s)[0] == "caution"  # 3 < 4 <= 1.5 x 3
    assert run("front", "person", 5, settings=s)[0] == "none"  # beyond 4.5 m


def test_tracker_keeps_id_and_iou():
    s = Settings()
    tr = CameraTracker(s)
    a = tr.update([Detection("car", 0.9, (0.1, 0.4, 0.3, 0.7))], 0.0, W, H)
    b = tr.update([Detection("car", 0.9, (0.12, 0.4, 0.32, 0.7))], 0.1, W, H)
    assert a[0].track_id == b[0].track_id and b[0].hits == 2
    assert iou((0, 0, 1, 1), (0, 0, 1, 1)) == 1.0 and iou((0, 0, 0.1, 0.1), (0.5, 0.5, 1, 1)) == 0.0


def test_tracker_low_score_keeps_track_alive():
    s = Settings()
    tr = CameraTracker(s)
    tr.update([Detection("person", 0.9, (0.4, 0.2, 0.5, 0.8))], 0.0, W, H)
    out = tr.update([Detection("person", 0.2, (0.41, 0.2, 0.51, 0.8))], 0.1, W, H)  # below conf 0.35
    assert len(out) == 1 and out[0].track_id == 1 and out[0].hits == 2
    out = tr.update([Detection("person", 0.2, (0.8, 0.2, 0.9, 0.8))], 0.2, W, H)  # low + unmatched -> no new track
    assert [t.track_id for t in out] == [1]


def test_tracker_drops_old_tracks():
    s = Settings()
    tr = CameraTracker(s)
    tr.update([Detection("car", 0.9, (0.1, 0.4, 0.3, 0.7))], 0.0, W, H)
    assert tr.update([], 1.0, W, H) == []


def test_noisy_distance_is_not_fake_approach():
    # A car staying ~27 m ahead, but its estimated distance jumps +-2 m (box height noise).
    import random

    random.seed(1)
    s = Settings()
    tracker, engine = CameraTracker(s), WarningEngine("front", s)
    level = None
    for i in range(30):
        t = i * 0.05
        d = 27 + random.uniform(-2, 2)
        tracks = tracker.update([Detection("car", 0.9, box_for(d, 1.5))], t, W, H)
        levels, _ = engine.update(tracks, t)
        level = list(levels.values())[0]
        assert level != "danger", f"fake approach at step {i}"
    assert level == "caution"  # 27 m: within 1.5 x 20 m


def test_orange_does_not_flicker_back_to_yellow():
    s = Settings()
    tracker, engine = CameraTracker(s), WarningEngine("front", s)
    for i, d in enumerate([6, 6, 6, 24, 24]):  # very close (orange), then 24 m (yellow)
        t = i * 0.05
        engine.update(tracker.update([Detection("car", 0.9, box_for(d, 1.5))], t, W, H), t)
    assert engine.state.level == "danger"  # still held: last orange was 0.15 s ago
    t = 0.1 + s.hold_seconds + 0.05
    engine.update(tracker.update([Detection("car", 0.9, box_for(24, 1.5))], t, W, H), t)
    assert engine.state.level == "caution"  # hold time over: back to yellow


def test_road_area_hides_things_off_the_road():
    from app.core.warnings import on_road

    s = Settings()
    assert on_road(s, "front", (0.45, 0.6, 0.55, 0.9))  # car in our lane
    assert on_road(s, "front", (0.0, 0.7, 0.12, 0.98))  # car in the next lane, close
    assert not on_road(s, "front", (0.02, 0.3, 0.1, 0.5))  # up on a building, off to the side
    assert not on_road(s, "front", (0.85, 0.35, 0.95, 0.5))  # far to the side, above the road
    assert not on_road(s, "left", (0.4, 0.0, 0.6, 0.2))  # side camera: top of the picture
    assert on_road(s, "left", (0.4, 0.5, 0.6, 0.9))


def test_following_a_car_at_same_speed_is_yellow_not_orange():
    # City traffic: the car ahead stays 12 m in front for a long time.
    s = Settings()
    tracker, engine = CameraTracker(s), WarningEngine("front", s)
    for i in range(40):
        t = i * 0.05
        engine.update(tracker.update([Detection("car", 0.9, box_for(12, 1.5))], t, W, H), t)
    assert engine.state.level == "caution"


def test_car_ahead_braking_turns_orange():
    # The car ahead slows down: the gap shrinks from 15 m at 4 m/s.
    s = Settings()
    tracker, engine = CameraTracker(s), WarningEngine("front", s)
    for i in range(30):
        t = i * 0.05
        d = 15 - 4 * t
        engine.update(tracker.update([Detection("car", 0.9, box_for(d, 1.5))], t, W, H), t)
    assert engine.state.level == "danger"
    assert engine.state.codes == ["VEHICLE_AHEAD"]


def test_people_still_use_distance_only():
    level, _ = run("front", "person", 5)  # a person 5 m ahead is orange even if standing still
    assert level == "danger"


def test_parked_car_at_lane_edge_we_drive_past_stays_yellow():
    # Stationary car at the left edge of our lane while we drive at 10 m/s.
    from app.core.warnings import lane_position, path_overlap

    s = Settings()
    tracker, engine = CameraTracker(s), WarningEngine("front", s)
    for i in range(20):
        t = i * 0.05
        d = 19 - 10 * t  # 19 m -> 9.5 m: fast closing, but beside our path
        box = box_for(d, 1.5, cx=0.30, bottom=0.9)
        assert abs(lane_position(s, "front", box)) > s.path_width
        assert path_overlap(s, "front", box) < s.path_min_overlap
        engine.update(tracker.update([Detection("car", 0.9, box)], t, W, H), t)
    assert engine.state.level == "caution"


def test_very_close_parked_car_beside_our_path_is_not_orange():
    s = Settings()
    level, _ = run("front", "car", 5, cx=0.12, bottom=0.99, settings=s)  # 5 m, at the left lane edge
    assert level != "danger"
