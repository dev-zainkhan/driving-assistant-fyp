from fastapi.testclient import TestClient

from app.main import create_app


def make_client():
    return TestClient(create_app(enable_detector=False))


def test_health():
    with make_client() as c:
        r = c.get("/api/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["model"] == "yolov8n.pt"
        assert body["detector"] == "disabled"


def test_meta():
    with make_client() as c:
        body = c.get("/api/meta").json()
        assert body["positions"] == ["front", "left", "right", "back"]
        assert "person" in body["classes"] and "car" in body["classes"]
        assert body["protocol"] == 1
        assert "PERSON_AHEAD" in body["warning_codes"]


def test_settings_defaults():
    with make_client() as c:
        s = c.get("/api/settings").json()
        assert s["det_fps"] == {"front": 20, "back": 10, "left": 8, "right": 8}
        assert s["alerts"]["vehicles"]["alert_at_m"] == 20
        assert s["alerts"]["people"]["alert_at_m"] == 6


def test_openapi_lists_routes():
    with make_client() as c:
        paths = c.get("/openapi.json").json()["paths"]
        assert "/api/health" in paths and "/api/meta" in paths


def test_pages_are_not_cached_but_api_is_untouched():
    with make_client() as c:
        assert c.get("/camera/").headers.get("cache-control") == "no-cache"
        assert c.get("/camera/camera.js").headers.get("cache-control") == "no-cache"
        assert "cache-control" not in c.get("/api/health").headers
