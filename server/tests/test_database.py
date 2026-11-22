"""SQLite database (docs/database.md) and the settings / incidents API."""
import json
import sqlite3
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.models.schemas import IncidentWarning, Settings
from app.storage.db import Database

TABLES = {
    "general_settings": 1,
    "vision_types": 3,
    "object_settings": 7,
    "yolo_classes": 6,
    "cameras": 4,
    "warning_areas": 8,
    "incidents": 0,
    "incident_videos": 0,
    "incident_warnings": 0,
}


@pytest.fixture
def db(temp_database):
    d = Database(temp_database)
    d.init()
    return d


# ---------------- tables and first fill ----------------
def test_first_start_fills_recommended_values(db):
    counts = db.table_counts()
    for table, n in TABLES.items():
        assert counts[table] == n, table
    assert counts["advanced_settings"] >= 20
    with sqlite3.connect(db.path) as con:
        row = con.execute("SELECT alert_distance_m, max_distance_m, is_safety FROM object_settings WHERE name = 'vehicles'").fetchone()
        assert row == (20, 20, 1)
        assert con.execute("SELECT voice_volume, speech_speed, beep_on FROM general_settings").fetchone() == (85, 1.0, 1)
        assert con.execute("SELECT object FROM yolo_classes WHERE name = 'bus'").fetchone() == ("vehicles",)


def test_settings_round_trip(db):
    assert db.load_settings() == Settings().model_copy(update={"zones": db.load_settings().zones})
    s = db.load_settings()
    s.volume = 0.5
    s.speech_speed = 1.4
    s.beep = False
    s.vision.night_blindness = True
    s.alerts["people"].alert_at_m = 9
    s.det_fps.left = 5
    s.camera_on["back"] = False
    s.side_min_track_s = 1.2
    db.save_settings(s)
    back = db.load_settings()
    assert (back.volume, back.speech_speed, back.beep) == (0.5, 1.4, False)
    assert back.vision.night_blindness is True
    assert back.alerts["people"].alert_at_m == 9
    assert back.det_fps.left == 5 and back.camera_on["back"] is False
    assert back.side_min_track_s == 1.2


def test_restart_keeps_saved_values(db):
    s = db.load_settings()
    s.alerts["vehicles"].alert_at_m = 12
    db.save_settings(s)
    db.init()  # server starts again: must not overwrite
    assert db.load_settings().alerts["vehicles"].alert_at_m == 12


def test_lane_corners_survive(db):
    lane = db.load_settings().zones["front_vehicles"].polygon
    assert lane == Settings().zones["front_vehicles"].polygon
    side = db.load_settings().zones["left_vehicles"].polygon
    assert side == [(0.0, 0.3), (1.0, 0.3), (1.0, 1.0), (0.0, 1.0)]  # band stored as a rectangle


def test_reset_to_recommended(db):
    s = db.load_settings()
    s.alerts["people"].alert_at_m = 12
    s.alerts["vehicles"].alert_at_m = 8
    db.save_settings(s)
    db.reset_alerts()
    back = db.load_settings()
    assert back.alerts["people"].alert_at_m == 6 and back.alerts["vehicles"].alert_at_m == 20


def test_database_refuses_bad_values(db):
    with sqlite3.connect(db.path) as con:
        with pytest.raises(sqlite3.IntegrityError):
            con.execute("UPDATE object_settings SET alert_distance_m = 25 WHERE name = 'vehicles'")  # above max 20
        with pytest.raises(sqlite3.IntegrityError):
            con.execute("UPDATE general_settings SET voice_volume = 150")
        with pytest.raises(sqlite3.IntegrityError):
            con.execute("INSERT INTO cameras VALUES ('top', 5, 1)")


# ---------------- incidents ----------------
def test_incidents_add_list_get_delete(db, tmp_path):
    warns = [
        IncidentWarning(camera="front", time_in_video_s=85, message="Person crossing", distance_m=6, colour="orange", was_spoken=True),
        IncidentWarning(camera="back", time_in_video_s=87, message="Motorbike behind", distance_m=7, colour="yellow"),
    ]
    videos = {p: f"1/{p}.mp4" for p in ("front", "left", "right", "back")}
    a = db.add_incident("sudden_brake", datetime(2026, 10, 14, 18, 42), videos=videos, warnings=warns, front_picture="1/front.jpg")
    b = db.add_incident("saved_by_driver", datetime(2026, 10, 12, 9, 15))
    items = db.list_incidents()
    assert [i.id for i in items] == [a, b]  # newest first
    full = db.get_incident(a)
    assert full.cause == "sudden_brake" and len(full.videos) == 4
    assert [w.message for w in full.warnings] == ["Person crossing", "Motorbike behind"]
    (tmp_path / str(a)).mkdir()
    assert db.delete_incident(a, files_root=tmp_path) is True
    assert not (tmp_path / str(a)).exists()
    counts = db.table_counts()
    assert counts["incidents"] == 1 and counts["incident_videos"] == 0 and counts["incident_warnings"] == 0  # cascade
    assert db.delete_incident(999) is False


def test_bad_incident_cause_refused(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.add_incident("crash", datetime(2026, 1, 1))


# ---------------- API ----------------
def client():
    return TestClient(create_app(enable_detector=False))


def test_patch_saves_and_broadcasts():
    with client() as c:
        with c.websocket_connect("/ws/viewer") as viewer:
            viewer.receive_json(), viewer.receive_json()  # welcome, warning_state
            r = c.patch("/api/settings", json={"volume": 0.6, "alerts": {"people": {"alert_at_m": 8}}})
            assert r.status_code == 200
            assert r.json()["volume"] == 0.6 and r.json()["alerts"]["people"]["alert_at_m"] == 8
            assert r.json()["alerts"]["people"]["announce"] is True  # untouched values stay
            for _ in range(10):
                m = viewer.receive_json()
                if m["type"] == "settings":
                    assert m["settings"]["volume"] == 0.6
                    break
            else:
                raise AssertionError("no settings message")
    with client() as c:  # "restart": values come back from the database
        assert c.get("/api/settings").json()["alerts"]["people"]["alert_at_m"] == 8


def test_patch_changes_the_running_rules():
    app = create_app(enable_detector=False)
    with TestClient(app) as c:
        c.patch("/api/settings", json={"side_min_track_s": 1.5})
        rt = app.state.runtime
        assert rt.pipelines["left"].engine.settings.side_min_track_s == 1.5


@pytest.mark.parametrize(
    "body,code",
    [
        ({"volume": 3}, "INVALID_SETTING"),
        ({"alerts": {"vehicles": {"alert_at_m": 50}}}, "INVALID_SETTING"),  # above max 20 m
        ({"alerts": {"cats": {"alert_at_m": 5}}}, "UNKNOWN_OBJECT"),
        ({"colour_theme": "pink"}, "UNKNOWN_SETTING"),
        ({"device": "cpu"}, "NOT_EDITABLE"),
    ],
)
def test_patch_rejects_bad_input(body, code):
    with client() as c:
        r = c.patch("/api/settings", json=body)
        assert r.status_code == 400 and r.json()["error"]["code"] == code


def test_reset_alerts_endpoint():
    with client() as c:
        c.patch("/api/settings", json={"alerts": {"people": {"alert_at_m": 10}}})
        body = c.post("/api/settings/alerts/reset").json()
        assert body["alerts"]["people"]["alert_at_m"] == 6


def test_incidents_api(temp_database):
    with client() as c:
        assert c.get("/api/incidents").json() == {"count": 0, "incidents": []}
        iid = Database(temp_database).add_incident("hard_jolt", datetime(2026, 10, 9, 17, 3))
        listed = c.get("/api/incidents").json()
        assert listed["count"] == 1 and listed["incidents"][0]["cause"] == "hard_jolt"
        assert c.get(f"/api/incidents/{iid}").json()["length_s"] == 90
        assert c.delete(f"/api/incidents/{iid}").status_code == 204
        assert c.get(f"/api/incidents/{iid}").status_code == 404


def test_database_summary_and_advanced():
    with client() as c:
        tables = c.get("/api/database").json()["tables"]
        assert tables["object_settings"] == 7
        adv = c.get("/api/settings/advanced").json()
        hold = next(a for a in adv if a["name"] == "hold_seconds")
        assert hold["unit"] == "s" and "flicker" in hold["description"]
        json.dumps(adv)


def test_sample_incident_flow(tmp_path, monkeypatch):
    import app.api.rest as rest

    monkeypatch.setattr(rest, "INCIDENTS_DIR", tmp_path / "incidents")
    with client() as c:
        with c.websocket_connect("/ws/viewer") as viewer:
            viewer.receive_json(), viewer.receive_json()
            inc = c.post("/api/incidents/sample", json={"cause": "hard_jolt"}).json()
            assert inc["cause"] == "hard_jolt" and len(inc["warnings"]) == 3
            for _ in range(10):
                m = viewer.receive_json()
                if m["type"] == "incident":
                    assert m["id"] == inc["id"]
                    break
            else:
                raise AssertionError("no incident message")
        for cam in inc["videos"]:
            r = c.get(f"/api/incidents/{inc['id']}/video/{cam}")
            assert r.status_code == 200 and len(r.content) > 1000
        assert c.get(f"/api/incidents/{inc['id']}/video/top").status_code == 404
        assert c.post("/api/incidents/sample", json={"cause": "crash"}).status_code == 400


def test_peripheral_vision_warns_earlier_on_the_sides():
    from app.core.detector import Detection
    from app.core.tracker import CameraTracker
    from app.core.warnings import WarningEngine
    from tests.test_warnings import box_for

    def level(peripheral):
        s = Settings()
        s.vision.peripheral_vision = peripheral
        tr, en = CameraTracker(s), WarningEngine("left", s)
        for i in range(12):
            t = i * 0.1
            levels, _ = en.update(tr.update([Detection("car", 0.9, box_for(25, 1.5))], t, 640, 360), t)
        return list(levels.values())[0]

    assert level(False) == "caution"  # 25 m: within 1.5 x 20 m
    assert level(True) == "danger"  # 25 m: within 1.5 x 20 m = 30 m alert distance


def test_advanced_screen_data_and_reset():
    from app.storage.db import ADVANCED, ADVANCED_UI

    assert set(ADVANCED_UI) == set(ADVANCED)  # every tuning number is on the screen
    with client() as c:
        rows = c.get("/api/settings/advanced").json()
        ttc = next(r for r in rows if r["name"] == "ttc_danger_s")
        assert ttc["group"] == "Cars ahead and behind" and ttc["default"] == 3.0 and ttc["min"] == 1
        assert c.patch("/api/settings", json={"ttc_danger_s": 99}).status_code == 400  # outside 1..8
        assert c.patch("/api/settings", json={"ttc_danger_s": 4.5}).json()["ttc_danger_s"] == 4.5
        assert c.post("/api/settings/advanced/reset").json()["ttc_danger_s"] == 3.0
