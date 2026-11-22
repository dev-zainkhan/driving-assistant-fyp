"""One slot per camera: the newest frame wins, older ones are dropped (never queued)."""
from __future__ import annotations

import threading
from dataclasses import dataclass

from app.core.protocol import POSITIONS


@dataclass(slots=True)
class StoredFrame:
    seq: int
    capture_ts_ms: float
    server_ts_ms: float
    jpeg: bytes


class FrameStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._slots: dict[str, StoredFrame | None] = {p: None for p in POSITIONS}
        self._version: dict[str, int] = {p: 0 for p in POSITIONS}  # bumps on every put

    def put(self, position: str, frame: StoredFrame) -> None:
        with self._lock:
            self._slots[position] = frame
            self._version[position] += 1

    def get(self, position: str) -> tuple[StoredFrame | None, int]:
        with self._lock:
            return self._slots[position], self._version[position]

    def clear(self, position: str) -> None:
        with self._lock:
            self._slots[position] = None
