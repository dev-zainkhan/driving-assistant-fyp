"""Runtime: every long-lived object of the server (one per app).

Threads:
- asyncio event loop: WebSockets, REST, forwarding frames to viewers (display path).
- inference thread (scheduler.py): decode + YOLO + tracking + warnings (detection path).
Shared per-camera pipeline state is guarded by one lock per camera.
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from app.core import protocol
from app.core.broadcaster import Broadcaster
from app.core.frame_store import FrameStore, StoredFrame
from app.core.protocol import POSITIONS
from app.core.stats import CameraStats
from app.core.tracker import CameraTracker
from app.core.warnings import WarningEngine, on_road
from app.models.schemas import Settings

log = logging.getLogger("da.runtime")

STATS_EVERY_S = 1.0


def default_detector_factory(settings: Settings):
    from app.core.detector import Detector

    return Detector(settings)


@dataclass
class CameraConn:
    session_id: str
    source: str  # "phone" | "file"
    client: str = ""
    video_name: str = ""
    connected_at: float = field(default_factory=time.time)
    close: Callable[[dict], Any] | None = None  # async callable(msg) that tells the old node and closes it
    client_stats: dict = field(default_factory=dict)


class CameraPipeline:
    def __init__(self, position: str, settings: Settings) -> None:
        self.lock = threading.Lock()
        self.tracker = CameraTracker(settings)
        self.engine = WarningEngine(position, settings)
        self.levels: dict[int, str] = {}
        self.det_seq: int | None = None

    def reset(self) -> bool:
        """Forget tracks and warnings (camera went away or was replaced). Returns True if a
        warning was showing, so viewers must be told."""
        with self.lock:
            self.tracker.reset()
            self.levels.clear()
            self.det_seq = None
            was_warning = self.engine.state.level != "none"
            self.engine = WarningEngine(self.engine.camera, self.engine.settings)
            return was_warning


def zone_name(box) -> str:
    x = (box[0] + box[2]) / 2
    return "left" if x < 1 / 3 else "right" if x > 2 / 3 else "center"


class Runtime:
    def __init__(
        self,
        settings: Settings,
        enable_detector: bool = True,
        detector_factory: Callable[[Settings], Any] | None = None,
        db=None,
    ) -> None:
        self.settings = settings
        self.db = db  # app.storage.db.Database
        self.enable_detector = enable_detector
        self.detector_factory = detector_factory or default_detector_factory
        self.detector = None
        self.detector_error = False
        self.infer_heartbeat = 0.0  # time.monotonic() of the inference loop's last round
        self.infer_errors = 0
        self.frame_store = FrameStore()
        self.cameras: dict[str, CameraConn | None] = {p: None for p in POSITIONS}
        self.stats = {p: CameraStats() for p in POSITIONS}
        self.pipelines = {p: CameraPipeline(p, settings) for p in POSITIONS}
        self.broadcaster = Broadcaster(self.camera_active)
        self.loop: asyncio.AbstractEventLoop | None = None
        self._infer = None
        self._stats_task: asyncio.Task | None = None
        self.file_sources = None  # set in start()
        from app.config import INCIDENTS_DIR
        from app.core.recorder import IncidentRecorder

        self.recorder = IncidentRecorder(self, INCIDENTS_DIR)

    # ---------------- lifecycle ----------------
    async def start(self) -> None:
        self.loop = asyncio.get_running_loop()
        from app.sources.file_source import FileSourceManager

        self.file_sources = FileSourceManager(self)
        if self.enable_detector:
            from app.core.scheduler import InferenceThread

            self._infer = InferenceThread(self)
            self._infer.start()
        self._stats_task = asyncio.create_task(self._stats_loop())
        log.info("runtime started (detector=%s)", self.enable_detector)

    async def stop(self) -> None:
        if self.file_sources:
            self.file_sources.stop_all()
        if self._infer:
            self._infer.stop()
            self._infer.join(timeout=3)
        if self._stats_task:
            self._stats_task.cancel()
        log.info("runtime stopped")

    # ---------------- info ----------------
    def device_name(self) -> str:
        if self.detector is not None:
            return self.detector.device
        return self.settings.device

    def detector_state(self) -> str:
        if not self.enable_detector:
            return "disabled"
        if self.detector_error:
            return "error"
        if self.detector is None:
            return "loading"
        if time.monotonic() - self.infer_heartbeat > 5:
            return "stalled"  # the inference loop stopped running
        return "ready"

    def camera_status(self, position: str) -> str:
        return "online" if self.cameras[position] is not None else "offline"

    def camera_active(self, position: str) -> bool:
        return self.pipelines[position].engine.state.level in ("caution", "danger")

    def status_json(self) -> dict:
        cams = {}
        for p in POSITIONS:
            c = self.cameras[p]
            d = {"status": self.camera_status(p), **self.stats[p].to_json()}
            d["source"] = c.source if c else None
            d["video_name"] = c.video_name if c else None
            cams[p] = d
        return {
            "type": "stats",
            "cameras": cams,
            "gpu": self.device_name(),
            "detector": self.detector_state(),
            "errors": self.infer_errors,
        }

    def warning_state_json(self) -> dict:
        return {
            "type": "warning_state",
            "ts": int(time.time() * 1000),
            "cameras": {p: self.pipelines[p].engine.state.to_json() for p in POSITIONS},
        }

    def welcome_json(self) -> dict:
        return {
            "type": "welcome",
            "protocol": protocol.PROTOCOL_VERSION,
            "server_version": protocol.SERVER_VERSION,
            "cameras": [{"position": p, "status": self.camera_status(p)} for p in POSITIONS],
            "settings": self.settings.model_dump(),
        }

    # ---------------- settings (event loop) ----------------
    def apply_settings(self, new: Settings) -> None:
        """Copy new values into the shared Settings object, so every part of the server
        (tracker, warnings, detector) sees them at once, then tell all viewers."""
        smoother_changed = any(
            getattr(new, f) != getattr(self.settings, f) for f in ("smoother_alpha", "smoother_max_predict_s", "smoother_drop_s")
        )
        for name in Settings.model_fields:
            setattr(self.settings, name, getattr(new, name))
        if smoother_changed:
            for pl in self.pipelines.values():
                pl.reset()
        self.broadcaster.publish_json({"type": "settings", "settings": self.settings.model_dump()})

    # ---------------- camera registry (event loop) ----------------
    async def register_camera(self, position: str, conn: CameraConn) -> None:
        old = self.cameras[position]
        self.cameras[position] = conn
        if old is not None and old.close is not None:
            try:
                await old.close(protocol.msg_replaced())
            except Exception:
                pass
        if old is not None and old.source == "file" and self.file_sources:
            self.file_sources.stop(position, notify=False)
        if self.pipelines[position].reset():
            self.broadcaster.publish_json(self.warning_state_json())
        self.broadcaster.publish_json(protocol.msg_camera_status(position, "online"))
        log.info("camera %s online (%s, %s)", position, conn.source, conn.video_name)

    def unregister_camera(self, position: str, session_id: str) -> None:
        cur = self.cameras[position]
        if cur is None or cur.session_id != session_id:
            return  # already replaced
        self.cameras[position] = None
        self.frame_store.clear(position)
        had_warning = self.pipelines[position].reset()
        self.broadcaster.publish_json(protocol.msg_camera_status(position, "offline"))
        if had_warning:
            self.broadcaster.publish_json(self.warning_state_json())
        log.info("camera %s offline", position)

    @staticmethod
    def new_session_id() -> str:
        return uuid.uuid4().hex[:8]

    # ---------------- display path (event loop) ----------------
    def ingest(self, position: str, seq: int, capture_ts_ms: float, jpeg: bytes) -> None:
        server_ts_ms = time.time() * 1000
        self.frame_store.put(position, StoredFrame(seq, capture_ts_ms, server_ts_ms, jpeg))
        self.stats[position].in_fps.tick()
        self.recorder.add(position, jpeg, server_ts_ms / 1000)  # last 90 s for incidents
        if self.broadcaster.viewers:
            frame = protocol.pack_viewer_frame(position, seq, capture_ts_ms, server_ts_ms, jpeg)
            try:
                overlay = self.overlay(position, seq, server_ts_ms / 1000)
            except Exception:
                # Never drop the camera because of a bad track: send the picture without boxes.
                log.exception("overlay for %s failed; sending the frame without boxes", position)
                overlay = {"type": "overlay", "camera": position, "seq": seq, "det_seq": None, "objects": [],
                           "warning": {"level": "none", "codes": [], "text": ""}}
            self.broadcaster.publish_frame(position, frame, overlay)

    def overlay(self, position: str, seq: int, T: float) -> dict:
        pl = self.pipelines[position]
        objects = []
        with pl.lock:
            tr = pl.tracker
            s = self.settings
            for t in tr.tracks.values():
                box = tr.smoother.predict(t.track_id, T) or t.box
                # Show only confident objects on the road: no boxes on buildings, fences or
                # things far off to the side (they never warn anyway).
                if t.conf < s.conf or not on_road(s, position, box):
                    continue
                objects.append(
                    {
                        "track_id": t.track_id,
                        "cls": t.cls,
                        "conf": round(t.conf, 2),
                        "box": [round(v, 4) for v in box],
                        "predicted": not (seq == pl.det_seq and tr.detected_now(t)),
                        "zone": zone_name(box),
                        "distance_m": round(t.distance_m, 1) if t.distance_m is not None else None,
                        "level": pl.levels.get(t.track_id, "none"),
                    }
                )
            st = pl.engine.state
            warning = {"level": st.level, "codes": list(st.codes), "text": st.text}
            det_seq = pl.det_seq
        return {"type": "overlay", "camera": position, "seq": seq, "det_seq": det_seq, "objects": objects, "warning": warning}

    # ---------------- detection path (inference thread) ----------------
    def process_detections(self, position: str, frame: StoredFrame, dets, w: int, h: int, infer_ms: float) -> None:
        t = frame.server_ts_ms / 1000
        pl = self.pipelines[position]
        with pl.lock:
            tracks = pl.tracker.update(dets, t, w, h)
            levels, changed = pl.engine.update(tracks, time.time())
            pl.levels = levels
            pl.det_seq = frame.seq
        st = self.stats[position]
        st.det_fps.tick()
        st.latency_ms.add(time.time() * 1000 - frame.server_ts_ms)
        st.infer_ms.add(infer_ms)
        if changed:
            self._notify_warning_change()

    def tick_warnings(self) -> None:
        now = time.time()
        changed = False
        for pl in self.pipelines.values():
            with pl.lock:
                changed |= pl.engine.tick(now)
        if changed:
            self._notify_warning_change()

    def _notify_warning_change(self) -> None:
        if self.loop is not None:
            self.loop.call_soon_threadsafe(self._publish_warning_state)

    def _publish_warning_state(self) -> None:
        msg = self.warning_state_json()
        self.recorder.note_warnings(msg["cameras"])  # for "Warnings before it" (slide 47)
        self.broadcaster.publish_json(msg)

    # ---------------- periodic ----------------
    async def _stats_loop(self) -> None:
        while True:
            await asyncio.sleep(STATS_EVERY_S)
            self.broadcaster.publish_json(self.status_json())
