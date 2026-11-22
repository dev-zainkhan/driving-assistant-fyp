"""Viewer registry and fan-out. Runs on the asyncio event loop only.

Each viewer has one slot per camera (newest frame + its overlay wins) and a short
deque of control messages. A slow viewer therefore skips frames instead of building
a backlog: frames are never queued.
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections import deque
from typing import Callable

from fastapi import WebSocket

log = logging.getLogger("da.broadcast")

VIDEO_MODES = ("auto", "all", "none")


class Viewer:
    def __init__(self, ws: WebSocket) -> None:
        self.ws = ws
        self.mode = "auto"
        self.pending: dict[str, tuple[bytes, str]] = {}
        self.control: deque[str] = deque(maxlen=200)
        self.event = asyncio.Event()
        self.task: asyncio.Task | None = None
        self.closed = False

    async def run_sender(self) -> None:
        try:
            while not self.closed:
                await self.event.wait()
                self.event.clear()
                while self.control:
                    await self.ws.send_text(self.control.popleft())
                while self.pending:
                    pos = next(iter(self.pending))
                    frame, overlay = self.pending.pop(pos)
                    await self.ws.send_bytes(frame)
                    await self.ws.send_text(overlay)
                    while self.control:  # keep control messages timely
                        await self.ws.send_text(self.control.popleft())
        except Exception as e:  # connection closed
            log.debug("viewer sender stopped: %s", e)
        finally:
            self.closed = True


class Broadcaster:
    def __init__(self, camera_active: Callable[[str], bool]) -> None:
        self.viewers: set[Viewer] = set()
        self._camera_active = camera_active

    def add(self, ws: WebSocket) -> Viewer:
        v = Viewer(ws)
        self.viewers.add(v)
        v.task = asyncio.create_task(v.run_sender())
        return v

    async def remove(self, v: Viewer) -> None:
        v.closed = True
        v.event.set()
        self.viewers.discard(v)
        if v.task:
            try:
                await asyncio.wait_for(v.task, 1.0)
            except Exception:
                v.task.cancel()

    def wants(self, v: Viewer, position: str) -> bool:
        if v.mode == "all":
            return True
        if v.mode == "none":
            return False
        return position == "front" or self._camera_active(position)

    def publish_frame(self, position: str, frame: bytes, overlay: dict) -> None:
        if not self.viewers:
            return
        overlay_txt = None
        for v in list(self.viewers):
            if v.closed:
                self.viewers.discard(v)
                continue
            if not self.wants(v, position):
                continue
            if overlay_txt is None:
                overlay_txt = json.dumps(overlay, separators=(",", ":"))
            v.pending[position] = (frame, overlay_txt)
            v.event.set()

    def publish_json(self, msg: dict) -> None:
        txt = json.dumps(msg, separators=(",", ":"))
        for v in list(self.viewers):
            if v.closed:
                self.viewers.discard(v)
                continue
            v.control.append(txt)
            v.event.set()

    def send_to(self, v: Viewer, msg: dict) -> None:
        v.control.append(json.dumps(msg, separators=(",", ":")))
        v.event.set()
