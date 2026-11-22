"""Incident recorder (slides 45-47): always keep the last 90 s of every camera; on an incident
save them as one video per camera, plus the warnings given in that time.

- add() runs on the event loop for every incoming frame. It only keeps a reference to the
  phone's JPEG bytes (no copy, no decoding), at record_fps, and drops frames older than
  record_seconds. Memory: 4 cameras x 90 s x 10 fps x ~40 KB = about 150 MB.
- save() takes a snapshot of the buffers on the event loop (fast) and writes the files in
  its own thread, so live video is never slowed down. Writing a video needs decoded pictures,
  so that thread decodes the saved JPEGs; this is the only decoding outside the inference
  thread and it happens only when an incident is saved.
- Videos are WebM (VP8): browsers can play them, and OpenCV writes VP8 without extra libraries.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from app.core.protocol import POSITIONS
from app.models.schemas import IncidentWarning

if TYPE_CHECKING:
    from app.core.runtime import Runtime

log = logging.getLogger("da.recorder")


class IncidentRecorder:
    def __init__(self, rt: "Runtime", folder: Path) -> None:
        self.rt = rt
        self.folder = folder
        self._frames: dict[str, deque] = {p: deque() for p in POSITIONS}  # (time s, jpeg bytes)
        self._last_kept: dict[str, float] = {p: 0.0 for p in POSITIONS}
        self._warnings: deque = deque()  # (time s, camera, code, level, text, distance_m)
        self._last_codes: dict[str, set] = {p: set() for p in POSITIONS}
        self._saving = threading.Lock()
        self._last_save = 0.0

    # ---------------- collecting (event loop) ----------------
    def add(self, position: str, jpeg: bytes, now: float | None = None) -> None:
        now = time.time() if now is None else now
        s = self.rt.settings
        if now - self._last_kept[position] < 1.0 / max(1.0, s.record_fps) - 1e-3:
            return
        self._last_kept[position] = now
        buf = self._frames[position]
        buf.append((now, jpeg))
        while buf and now - buf[0][0] > s.record_seconds:
            buf.popleft()

    def note_warnings(self, cameras: dict, now: float | None = None) -> None:
        """Remember each new warning (camera, code) as it starts, for "Warnings before it"."""
        now = time.time() if now is None else now
        for cam, w in cameras.items():
            codes = set(w["codes"]) if w["level"] in ("caution", "danger") else set()
            for code in codes - self._last_codes[cam]:
                dist = None
                text = w["text"]
                if "," in text and text.rstrip().endswith("m"):
                    try:
                        dist = int(round(float(text.rsplit(",", 1)[1].strip().rstrip("m").strip())))
                    except ValueError:
                        dist = None
                self._warnings.append((now, cam, code, w["level"], text.split(",")[0], dist))
            self._last_codes[cam] = codes
        limit = self.rt.settings.record_seconds
        while self._warnings and now - self._warnings[0][0] > limit:
            self._warnings.popleft()

    # ---------------- saving ----------------
    def save(self, cause: str, now: float | None = None) -> bool:
        """Start saving the buffered seconds as an incident. False if one was saved just before
        (cooldown) or one is still being written."""
        now = time.time() if now is None else now
        s = self.rt.settings
        if now - self._last_save < s.incident_cooldown_s or self._saving.locked():
            return False
        if not any(self._frames.values()):
            return False
        self._last_save = now
        frames = {p: list(buf) for p, buf in self._frames.items() if buf}
        warnings = list(self._warnings)
        threading.Thread(target=self._write, args=(cause, now, frames, warnings), name="incident-writer", daemon=True).start()
        return True

    @staticmethod
    def _write_video(out: Path, cam: str, buf: list, start: float, now: float, fps: float) -> bool:
        """One camera's frames as a WebM file, each frame placed at its real time."""
        import cv2
        import numpy as np

        first = cv2.imdecode(np.frombuffer(buf[0][1], np.uint8), cv2.IMREAD_COLOR)
        if first is None:
            return False
        h, w = first.shape[:2]
        vw = cv2.VideoWriter(str(out / f"{cam}.webm"), cv2.VideoWriter_fourcc(*"VP80"), fps, (w, h))
        k, last_k, img = 0, -1, first
        for i in range(int((now - start) * fps)):
            t = start + i / fps
            while k + 1 < len(buf) and buf[k + 1][0] <= t:
                k += 1
            if k != last_k:  # decode each saved JPEG only once
                dec = cv2.imdecode(np.frombuffer(buf[k][1], np.uint8), cv2.IMREAD_COLOR)
                if dec is not None and dec.shape[:2] == (h, w):
                    img = dec
                last_k = k
            vw.write(img)
        vw.release()
        return True

    def _write(self, cause: str, now: float, frames: dict, warnings: list) -> None:
        with self._saving:
            try:
                start = min(buf[0][0] for buf in frames.values())
                length = max(1, round(now - start))
                warn_rows = [
                    IncidentWarning(camera=cam, time_in_video_s=max(0, round(t - start)), message=msg, distance_m=dist,
                                    colour="orange" if level == "danger" else "yellow", was_spoken=level == "danger")
                    for t, cam, code, level, msg, dist in warnings
                    if t >= start
                ]
                iid = self.rt.db.add_incident(cause, datetime.fromtimestamp(now), length_s=length, warnings=warn_rows)
                out = self.folder / str(iid)
                out.mkdir(parents=True, exist_ok=True)
                fps = self.rt.settings.record_fps
                # the four videos are written at the same time (OpenCV encodes outside the GIL)
                with ThreadPoolExecutor(max_workers=len(frames)) as pool:
                    done = pool.map(lambda kv: (kv[0], self._write_video(out, kv[0], kv[1], start, now, fps)), frames.items())
                    videos = {cam: f"{iid}/{cam}.webm" for cam, ok in done if ok}
                picture = None
                if "front" in frames:
                    (out / "front.jpg").write_bytes(frames["front"][-1][1])  # the phone's own JPEG
                    picture = f"{iid}/front.jpg"
                with self.rt.db.connect() as con:
                    for cam, rel in videos.items():
                        con.execute("INSERT INTO incident_videos (incident, camera, video_file) VALUES (?, ?, ?)", (iid, cam, rel))
                    con.execute("UPDATE incidents SET front_picture = ? WHERE id = ?", (picture, iid))
                log.info("incident %s saved (%s, %d s, %d cameras)", iid, cause, length, len(videos))
                msg = {"type": "incident", "id": iid, "cause": cause, "camera": None, "codes": [], "ts": int(now * 1000)}
                if self.rt.loop is not None:
                    self.rt.loop.call_soon_threadsafe(self.rt.broadcaster.publish_json, msg)
            except Exception:
                log.exception("saving the incident failed")
