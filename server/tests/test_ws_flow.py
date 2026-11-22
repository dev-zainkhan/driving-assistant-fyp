"""Integration: fake camera -> server -> fake viewer, with a fake detector (no GPU needed)."""
import json
import time

from fastapi.testclient import TestClient

from app.core import protocol as p
from app.core.detector import Detection
from app.main import create_app
from app.models.schemas import Settings

import cv2  # noqa: E402
import numpy as np  # noqa: E402

JPEG = cv2.imencode(".jpg", np.full((360, 640, 3), 128, np.uint8))[1].tobytes()


class FakeDetector:
    device = "fake"
    last_infer_ms = 1.0

    def warmup(self):
        pass

    def predict(self, images):
        # A big person in the centre: 1.7 m * 457 px / (0.9 * 360 px) = 2.4 m -> danger
        return [[Detection("person", 0.9, (0.4, 0.05, 0.6, 0.95))] for _ in images]


def hello(pos):
    return json.dumps({"type": "hello", "position": pos, "client": "test", "video_name": "t.mp4"})


def test_bad_position():
    with TestClient(create_app(enable_detector=False)) as c:
        with c.websocket_connect("/ws/camera/top") as ws:
            assert ws.receive_json()["code"] == "BAD_POSITION"


def test_camera_ack_status_and_offline():
    with TestClient(create_app(enable_detector=False)) as c:
        with c.websocket_connect("/ws/camera/left") as ws:
            ws.send_text(hello("left"))
            ack = ws.receive_json()
            assert ack["type"] == "ack" and ack["position"] == "left"
            assert ws.receive_json()["type"] == "config"
            for i in range(5):
                ws.send_bytes(p.pack_camera_frame(i, time.time() * 1000, JPEG))
            ws.send_text(json.dumps({"type": "ping", "t": 1}))
            assert ws.receive_json()["type"] == "pong"  # all frames before it were processed
            st = c.get("/api/status").json()["cameras"]
            assert st["left"]["status"] == "online" and st["left"]["video_name"] == "t.mp4"
            assert st["front"]["status"] == "offline"
        assert c.get("/api/status").json()["cameras"]["left"]["status"] == "offline"


def test_second_node_replaces_first():
    with TestClient(create_app(enable_detector=False)) as c:
        with c.websocket_connect("/ws/camera/back") as ws1:
            ws1.send_text(hello("back"))
            ws1.receive_json(), ws1.receive_json()
            with c.websocket_connect("/ws/camera/back") as ws2:
                ws2.send_text(hello("back"))
                assert ws2.receive_json()["type"] == "ack"
                assert ws1.receive_json()["type"] == "replaced"
                assert c.get("/api/status").json()["cameras"]["back"]["status"] == "online"


def _recv_until(ws, pred, limit=500):
    for _ in range(limit):
        m = ws.receive()
        if m.get("text"):
            j = json.loads(m["text"])
            if pred(j):
                return j
    raise AssertionError("message not received")


def test_viewer_gets_frame_overlay_and_warning():
    settings = Settings(det_fps={"front": 50, "back": 10, "left": 8, "right": 8})
    app = create_app(settings=settings, enable_detector=True, detector_factory=lambda s: FakeDetector())
    with TestClient(app) as c:
        with c.websocket_connect("/ws/viewer") as viewer:
            welcome = viewer.receive_json()
            assert welcome["type"] == "welcome" and welcome["protocol"] == 1
            assert viewer.receive_json()["type"] == "warning_state"
            viewer.send_text(json.dumps({"type": "subscribe", "video": "auto"}))
            with c.websocket_connect("/ws/camera/front") as cam:
                cam.send_text(hello("front"))
                cam.receive_json(), cam.receive_json()
                got_frame = False
                warned = None
                for i in range(200):
                    cam.send_bytes(p.pack_camera_frame(i, time.time() * 1000, JPEG))
                    time.sleep(0.01)
                    m = viewer.receive()
                    if m.get("bytes"):
                        pos, seq, _, _, jpeg = p.unpack_viewer_frame(m["bytes"])
                        assert pos == "front" and jpeg == JPEG
                        got_frame = True
                        continue
                    j = json.loads(m["text"])
                    if j["type"] == "overlay":
                        assert j["camera"] == "front"
                        for o in j["objects"]:
                            assert all(0 <= v <= 1 for v in o["box"])
                    if j["type"] == "warning_state" and j["cameras"]["front"]["level"] == "danger":
                        warned = j
                        break
                assert got_frame
                assert warned is not None
                assert warned["cameras"]["front"]["codes"] == ["PERSON_AHEAD"]


def test_file_source_missing_file():
    with TestClient(create_app(enable_detector=False)) as c:
        r = c.post("/api/sources/files", json={"front": "videos/does_not_exist.mp4"})
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "NOT_FOUND"


def test_backup_mode_plays_a_video_file(tmp_path):
    video = tmp_path / "clip.mp4"
    vw = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 30, (640, 360))
    for i in range(30):
        vw.write(np.full((360, 640, 3), i * 8 % 255, np.uint8))
    vw.release()
    with TestClient(create_app(enable_detector=False)) as c:
        r = c.post("/api/sources/files", json={"left": str(video)})
        assert r.status_code == 200 and r.json() == {"started": ["left"]}
        deadline = time.time() + 5
        st = {}
        while time.time() < deadline:
            st = c.get("/api/status").json()["cameras"]["left"]
            if st["in_fps"] > 5:
                break
            time.sleep(0.2)
        assert st["status"] == "online" and st["source"] == "file" and st["in_fps"] > 5
        assert c.get("/api/sources/files").json() == {"running": {"left": "clip.mp4"}}
        assert c.delete("/api/sources/files").json()["stopped"] is True
        assert c.get("/api/status").json()["cameras"]["left"]["status"] == "offline"


def test_list_videos():
    with TestClient(create_app(enable_detector=False)) as c:
        body = c.get("/api/sources/videos").json()
        assert body["folder"] == "videos" and isinstance(body["videos"], list)


class FlakyDetector(FakeDetector):
    """First result is broken (box is None): processing it raises. Later results are fine."""

    calls = 0

    def predict(self, images):
        FlakyDetector.calls += 1
        if FlakyDetector.calls == 1:
            return [[Detection("person", 0.9, None)] for _ in images]
        return super().predict(images)


def _wait_for(ws, pred, limit=400):
    for _ in range(limit):
        m = ws.receive()
        if m.get("text"):
            j = json.loads(m["text"])
            if pred(j):
                return j
    raise AssertionError("message not received")


def test_bad_detection_does_not_stop_detection_and_offline_clears_warning():
    FlakyDetector.calls = 0
    settings = Settings(det_fps={"front": 50, "back": 10, "left": 8, "right": 8})
    app = create_app(settings=settings, enable_detector=True, detector_factory=lambda s: FlakyDetector())
    with TestClient(app) as c:
        with c.websocket_connect("/ws/viewer") as viewer:
            viewer.receive_json(), viewer.receive_json()
            with c.websocket_connect("/ws/camera/front") as cam:
                cam.send_text(hello("front"))
                cam.receive_json(), cam.receive_json()
                warned = False
                for i in range(300):
                    cam.send_bytes(p.pack_camera_frame(i, time.time() * 1000, JPEG))
                    time.sleep(0.01)
                    m = viewer.receive()
                    if m.get("text"):
                        j = json.loads(m["text"])
                        if j["type"] == "warning_state" and j["cameras"]["front"]["level"] == "danger":
                            warned = True
                            break
                assert warned, "detection stopped after one bad result"
                assert app.state.runtime.infer_errors >= 1
                assert c.get("/api/health").json()["detector"] == "ready"
            # camera gone: its warning must not stay on screen
            cleared = _wait_for(viewer, lambda j: j["type"] == "warning_state" and j["cameras"]["front"]["level"] == "none")
            assert cleared["cameras"]["front"]["codes"] == []


def test_fit_keeps_shape_with_black_bars():
    from app.sources.file_source import fit

    img = np.full((960, 1280, 3), 200, np.uint8)  # 4:3
    out = fit(img, 640, 360)
    assert out.shape == (360, 640, 3)
    assert out[:, :10].max() == 0 and out[:, -10:].max() == 0  # black bars left and right
    assert out[180, 320, 0] == 200  # picture in the middle


def test_hd_video_gets_a_small_cached_copy(tmp_path, monkeypatch):
    import app.sources.file_source as fs

    monkeypatch.setattr(fs, "CACHE_DIR", tmp_path / "cache")
    video = tmp_path / "hd.mp4"
    vw = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 30, (1280, 720))
    for i in range(20):
        vw.write(np.full((720, 1280, 3), i * 10, np.uint8))
    vw.release()
    with TestClient(create_app(enable_detector=False)) as c:
        # two cameras play the same HD file: both write a copy, only one can win
        c.post("/api/sources/files", json={"front": str(video), "back": str(video)})
        time.sleep(2.5)  # 20 frames = 0.7 s per round: a few rounds
        st = c.get("/api/status").json()["cameras"]
        assert st["front"]["in_fps"] > 10 and st["back"]["in_fps"] > 10, st  # both still playing
        c.delete("/api/sources/files")
    time.sleep(0.3)
    copies = list((tmp_path / "cache").glob("hd-*-640x360.mp4"))
    assert len(copies) == 1
    assert not list((tmp_path / "cache").glob("*.part.mp4"))  # no half copies left
    cap = cv2.VideoCapture(str(copies[0]))
    assert (cap.get(cv2.CAP_PROP_FRAME_WIDTH), cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) == (640, 360)


def test_incident_recorder_saves_last_seconds(tmp_path):
    app = create_app(enable_detector=False)
    with TestClient(app) as c:
        rt = app.state.runtime
        rt.recorder.folder = tmp_path / "incidents"
        assert c.post("/api/incidents", json={"cause": "saved_by_driver"}).status_code == 409  # nothing yet
        with c.websocket_connect("/ws/viewer") as viewer:
            viewer.receive_json(), viewer.receive_json()
            with c.websocket_connect("/ws/camera/front") as cam:
                cam.send_text(hello("front"))
                cam.receive_json(), cam.receive_json()
                for i in range(40):
                    cam.send_bytes(p.pack_camera_frame(i, time.time() * 1000, JPEG))
                    time.sleep(0.03)
                cam.send_text(json.dumps({"type": "ping", "t": 1}))
                cam.receive_json()
                rt.recorder.note_warnings({"front": {"level": "danger", "codes": ["PERSON_AHEAD"], "text": "Person ahead, 5 m"}})
                r = c.post("/api/incidents", json={"cause": "saved_by_driver"})
                assert r.status_code == 202
                assert c.post("/api/incidents", json={"cause": "saved_by_driver"}).status_code == 409  # cooldown
                msg = _wait_for(viewer, lambda j: j["type"] == "incident")
        inc = c.get(f"/api/incidents/{msg['id']}").json()
        assert inc["cause"] == "saved_by_driver" and "front" in inc["videos"]
        assert inc["warnings"][0]["message"] == "Person ahead" and inc["warnings"][0]["distance_m"] == 5
        video = tmp_path / "incidents" / str(msg["id"]) / "front.webm"
        assert video.exists() and video.stat().st_size > 1000
        cap = cv2.VideoCapture(str(video))
        assert cap.get(cv2.CAP_PROP_FRAME_COUNT) >= 5 or cap.read()[0]
