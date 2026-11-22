"""Small thread-safe counters for fps, latency and inference time."""
from __future__ import annotations

import threading
import time
from collections import deque


class RateCounter:
    """Events per second over a sliding window."""

    def __init__(self, window_s: float = 2.0) -> None:
        self.window_s = window_s
        self._t: deque[float] = deque()
        self._lock = threading.Lock()

    def tick(self, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        with self._lock:
            self._t.append(now)
            self._trim(now)

    def _trim(self, now: float) -> None:
        while self._t and now - self._t[0] > self.window_s:
            self._t.popleft()

    def rate(self, now: float | None = None) -> float:
        now = time.monotonic() if now is None else now
        with self._lock:
            self._trim(now)
            return len(self._t) / self.window_s


class Average:
    """Exponential moving average."""

    def __init__(self, alpha: float = 0.2) -> None:
        self.alpha = alpha
        self.value: float | None = None
        self._lock = threading.Lock()

    def add(self, v: float) -> None:
        with self._lock:
            self.value = v if self.value is None else self.alpha * v + (1 - self.alpha) * self.value

    def get(self) -> float | None:
        with self._lock:
            return self.value


class CameraStats:
    def __init__(self) -> None:
        self.in_fps = RateCounter()
        self.det_fps = RateCounter()
        self.latency_ms = Average()  # server receive -> detection result ready
        self.infer_ms = Average()

    def to_json(self) -> dict:
        lat, inf = self.latency_ms.get(), self.infer_ms.get()
        return {
            "in_fps": round(self.in_fps.rate(), 1),
            "det_fps": round(self.det_fps.rate(), 1),
            "latency_ms": round(lat) if lat is not None else None,
            "infer_ms": round(inf, 1) if inf is not None else None,
        }
