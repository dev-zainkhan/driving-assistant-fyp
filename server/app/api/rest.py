"""REST API: /api/* (docs/protocol.md section 2)."""
from __future__ import annotations

from typing import Any

import shutil
import time
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import ValidationError

from app.config import INCIDENTS_DIR, REPO_DIR, VIDEOS_DIR
from app.models.schemas import IncidentWarning, Settings
from app.core import protocol
from app.core.protocol import POSITIONS

VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}

router = APIRouter(prefix="/api")


def _rt(request: Request):
    return request.app.state.runtime


@router.get("/health")
def health(request: Request) -> dict:
    rt = _rt(request)
    return {
        "status": "ok",
        "device": rt.device_name(),
        "model": rt.settings.model,
        "detector": rt.detector_state(),
        "protocol": protocol.PROTOCOL_VERSION,
    }


@router.get("/meta")
def meta() -> dict:
    return protocol.meta()


@router.get("/status")
def status(request: Request) -> dict:
    return _rt(request).status_json()


@router.get("/settings")
def get_settings(request: Request) -> dict:
    return _rt(request).settings.model_dump()


# Values that belong to the laptop setup, not to the app screens.
NOT_EDITABLE = {"model", "device"}


def deep_merge(base: dict, patch: dict) -> dict:
    out = dict(base)
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _bad(code: str, message: str, status: int = 400) -> HTTPException:
    return HTTPException(status, detail={"code": code, "message": message})


@router.patch("/settings")
def patch_settings(request: Request, body: dict[str, Any]) -> dict:
    """Change some settings, e.g. {"volume": 0.6} or {"alerts": {"people": {"alert_at_m": 8}}}.
    The new values are checked, saved in the database and sent to every connected app."""
    rt = _rt(request)
    unknown = sorted(set(body) - set(Settings.model_fields))
    if unknown:
        raise _bad("UNKNOWN_SETTING", f"unknown settings: {unknown}")
    locked = sorted(set(body) & NOT_EDITABLE)
    if locked:
        raise _bad("NOT_EDITABLE", f"these settings can't be changed from the app: {locked}")
    from app.storage.db import ADVANCED_UI

    for name, value in body.items():
        if name in ADVANCED_UI and isinstance(value, (int, float)) and not isinstance(value, bool):
            lo, hi = ADVANCED_UI[name][2], ADVANCED_UI[name][3]
            if not lo <= value <= hi:
                raise _bad("INVALID_SETTING", f"{name} must be between {lo} and {hi}")
    current = rt.settings.model_dump()
    for name, a in (body.get("alerts") or {}).items():
        if name not in current["alerts"]:
            raise _bad("UNKNOWN_OBJECT", f"unknown object: {name}")
    try:
        new = Settings.model_validate(deep_merge(current, body))
    except ValidationError as e:
        first = e.errors()[0]
        where = ".".join(str(x) for x in first.get("loc", ()))
        raise _bad("INVALID_SETTING", f"{where}: {first.get('msg')}".strip(": "))
    rt.db.save_settings(new)
    rt.apply_settings(new)
    return rt.settings.model_dump()


@router.post("/settings/alerts/reset")
def reset_alerts(request: Request) -> dict:
    """'Reset to recommended' on the Detection and alerts screen (slide 35)."""
    rt = _rt(request)
    rt.db.reset_alerts()
    rt.apply_settings(rt.db.load_settings(base=rt.settings))
    return rt.settings.model_dump()


@router.get("/settings/advanced")
def advanced_settings(request: Request) -> list[dict]:
    """The fine-tuning numbers for the Advanced settings screen: value, default, range, unit,
    group and a plain-English description."""
    from app.storage.db import ADVANCED, ADVANCED_UI

    s = _rt(request).settings
    d = Settings()
    out = []
    for name, (group, title, lo, hi, step) in ADVANCED_UI.items():
        unit, desc = ADVANCED[name]
        out.append({"name": name, "group": group, "title": title, "value": getattr(s, name), "default": getattr(d, name),
                    "min": lo, "max": hi, "step": step, "unit": unit, "description": desc})
    return out


@router.post("/settings/advanced/reset")
def reset_advanced(request: Request) -> dict:
    """Put every fine-tuning number back to its default."""
    from app.storage.db import ADVANCED_UI

    rt = _rt(request)
    d = Settings()
    new = rt.settings.model_copy(update={name: getattr(d, name) for name in ADVANCED_UI})
    rt.db.save_settings(new)
    rt.apply_settings(new)
    return rt.settings.model_dump()


# ---------------- saved incidents (slides 45-47) ----------------
@router.get("/incidents")
def list_incidents(request: Request, limit: int = 100) -> dict:
    db = _rt(request).db
    items = db.list_incidents(limit=max(1, min(limit, 1000)))
    return {"count": db.count_incidents(), "incidents": [i.model_dump(mode="json") for i in items]}


@router.post("/incidents", status_code=202)
def save_incident(request: Request, body: dict[str, Any] | None = None) -> dict:
    """Save the last record_seconds of every camera as an incident (slide 45), e.g. when the
    driver holds the screen. The videos are written in the background; an `incident` message
    is sent to all viewers when it is ready."""
    cause = (body or {}).get("cause", "saved_by_driver")
    if cause not in ("sudden_brake", "hard_jolt", "saved_by_driver"):
        raise _bad("INVALID_CAUSE", "cause must be sudden_brake, hard_jolt or saved_by_driver")
    if not _rt(request).recorder.save(cause):
        raise _bad("NOT_SAVED", "nothing recorded yet, or an incident was saved a moment ago", 409)
    return {"saving": True, "cause": cause}


@router.get("/incidents/{incident_id}")
def get_incident(request: Request, incident_id: int) -> dict:
    inc = _rt(request).db.get_incident(incident_id)
    if inc is None:
        raise _bad("NOT_FOUND", f"incident {incident_id} not found", 404)
    return inc.model_dump(mode="json")


@router.delete("/incidents/{incident_id}", status_code=204)
def delete_incident(request: Request, incident_id: int) -> Response:
    if not _rt(request).db.delete_incident(incident_id, files_root=INCIDENTS_DIR):
        raise _bad("NOT_FOUND", f"incident {incident_id} not found", 404)
    return Response(status_code=204)


def _incident_file(request: Request, incident_id: int, rel: str | None):
    if not rel:
        raise _bad("NOT_FOUND", "file not found", 404)
    path = (INCIDENTS_DIR / rel).resolve()
    if INCIDENTS_DIR.resolve() not in path.parents or not path.is_file():
        raise _bad("NOT_FOUND", "file not found", 404)
    return FileResponse(path)


@router.get("/incidents/{incident_id}/video/{camera}")
def incident_video(request: Request, incident_id: int, camera: str):
    """One camera's video of an incident (slide 47 plays all four together)."""
    inc = _rt(request).db.get_incident(incident_id)
    if inc is None:
        raise _bad("NOT_FOUND", f"incident {incident_id} not found", 404)
    return _incident_file(request, incident_id, inc.videos.get(camera))


@router.get("/incidents/{incident_id}/picture")
def incident_picture(request: Request, incident_id: int):
    """Front camera picture shown in the incident list (slide 46)."""
    inc = _rt(request).db.get_incident(incident_id)
    if inc is None:
        raise _bad("NOT_FOUND", f"incident {incident_id} not found", 404)
    return _incident_file(request, incident_id, inc.front_picture)


SAMPLE_WARNINGS = [
    IncidentWarning(camera="front", time_in_video_s=-9, message="Person crossing", distance_m=9, colour="yellow"),
    IncidentWarning(camera="front", time_in_video_s=-5, message="Person crossing", distance_m=6, colour="orange", was_spoken=True),
    IncidentWarning(camera="back", time_in_video_s=-3, message="Motorbike behind", distance_m=7, colour="yellow"),
]


@router.post("/incidents/sample")
def create_sample_incident(request: Request, body: dict[str, Any] | None = None) -> dict:
    """DEMO ONLY: save a sample incident from the test videos (videos/test/*.webm), so the
    "Incident saved" notice, the list and the playback screen can be shown before the real
    90-second recorder exists. Not used by the real driving flow."""
    import cv2

    rt = _rt(request)
    cause = (body or {}).get("cause", "sudden_brake")
    if cause not in ("sudden_brake", "hard_jolt", "saved_by_driver"):
        raise _bad("INVALID_CAUSE", "cause must be sudden_brake, hard_jolt or saved_by_driver")
    # WebM (VP8): browsers can play it in the incident playback screen
    sources = {cam: VIDEOS_DIR / "test" / f"{cam}.webm" for cam in POSITIONS}
    sources = {cam: src for cam, src in sources.items() if src.is_file()}
    length_s = 90
    if "front" in sources:
        cap = cv2.VideoCapture(str(sources["front"]))
        frames, fps = cap.get(cv2.CAP_PROP_FRAME_COUNT), cap.get(cv2.CAP_PROP_FPS) or 30
        cap.release()
        if frames > 0:
            length_s = max(1, round(frames / fps))
    # warnings are given as seconds before the end of the video
    warnings = [w.model_copy(update={"time_in_video_s": max(0, length_s + w.time_in_video_s)}) for w in SAMPLE_WARNINGS]
    iid = rt.db.add_incident(cause, datetime.now(), length_s=length_s, warnings=warnings)
    folder = INCIDENTS_DIR / str(iid)
    folder.mkdir(parents=True, exist_ok=True)
    videos = {}
    for cam, src in sources.items():
        shutil.copyfile(src, folder / f"{cam}.webm")
        videos[cam] = f"{iid}/{cam}.webm"
    picture = None
    if "front" in sources:
        cap = cv2.VideoCapture(str(sources["front"]))
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, cap.get(cv2.CAP_PROP_FRAME_COUNT) - 1))
        ok, img = cap.read()
        cap.release()
        if ok:
            cv2.imwrite(str(folder / "front.jpg"), img)
            picture = f"{iid}/front.jpg"
    with rt.db.connect() as con:
        for cam, rel in videos.items():
            con.execute("INSERT INTO incident_videos (incident, camera, video_file) VALUES (?, ?, ?)", (iid, cam, rel))
        con.execute("UPDATE incidents SET front_picture = ? WHERE id = ?", (picture, iid))
    msg = {"type": "incident", "id": iid, "cause": cause, "camera": None, "codes": [], "ts": int(time.time() * 1000)}
    if rt.loop is not None:
        rt.loop.call_soon_threadsafe(rt.broadcaster.publish_json, msg)
    return rt.db.get_incident(iid).model_dump(mode="json")


@router.get("/database")
def database_summary(request: Request) -> dict:
    """Rows per table: handy to show in the demo that the database is real."""
    db = _rt(request).db
    return {"file": db.path.name, "tables": db.table_counts()}


@router.get("/sources/videos")
def list_videos() -> dict:
    """Video files in the repo's videos/ folder, for backup mode. Paths are relative to the repo."""
    files = []
    if VIDEOS_DIR.is_dir():
        for f in sorted(VIDEOS_DIR.rglob("*")):
            if f.is_file() and f.suffix.lower() in VIDEO_EXTS:
                files.append({"path": f.relative_to(REPO_DIR).as_posix(), "name": f.name, "size_mb": round(f.stat().st_size / 1e6, 1)})
    return {"folder": VIDEOS_DIR.relative_to(REPO_DIR).as_posix(), "videos": files}


@router.get("/sources/files")
def file_sources_status(request: Request) -> dict:
    fs = _rt(request).file_sources
    return {"running": {pos: src.path.name for pos, (src, _) in fs.sources.items()}}


@router.post("/sources/files")
async def start_file_sources(request: Request, body: dict[str, str]) -> dict:
    bad = [k for k in body if k not in POSITIONS]
    if bad:
        raise HTTPException(400, detail={"code": "BAD_POSITION", "message": f"unknown positions: {bad}"})
    if not body:
        raise HTTPException(400, detail={"code": "EMPTY", "message": "give at least one position: path"})
    try:
        started = await _rt(request).file_sources.start(body)
    except FileNotFoundError as e:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": str(e)})
    return {"started": started}


@router.delete("/sources/files")
def stop_file_sources(request: Request) -> dict:
    stopped = _rt(request).file_sources.stop_all()
    return {"stopped": True, "positions": stopped}
