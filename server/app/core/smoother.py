"""Box prediction between detections (DESIGN.md 3.7).

Per track: last detected box b at time t and a velocity v (per-second change of each
coordinate, EMA). Predicted box at time T = b + v * min(T - t, max_predict_s).
"""
from __future__ import annotations

from dataclasses import dataclass

Box = tuple[float, float, float, float]


@dataclass(slots=True)
class _State:
    box: Box
    t: float
    v: Box = (0.0, 0.0, 0.0, 0.0)


class Smoother:
    def __init__(self, alpha: float = 0.5, max_predict_s: float = 0.3, drop_s: float = 0.7) -> None:
        self.alpha = alpha
        self.max_predict_s = max_predict_s
        self.drop_s = drop_s
        self._s: dict[int, _State] = {}

    def update(self, track_id: int, box: Box, t: float) -> None:
        st = self._s.get(track_id)
        if st is None:
            self._s[track_id] = _State(box=box, t=t)
            return
        dt = t - st.t
        if dt > 1e-6:
            inst = tuple((n - o) / dt for n, o in zip(box, st.box))
            a = self.alpha
            st.v = tuple(a * i + (1 - a) * ov for i, ov in zip(inst, st.v))  # type: ignore[assignment]
        st.box, st.t = box, t

    def predict(self, track_id: int, T: float) -> Box | None:
        st = self._s.get(track_id)
        if st is None:
            return None
        dt = max(0.0, min(T - st.t, self.max_predict_s))
        return tuple(min(1.0, max(0.0, b + v * dt)) for b, v in zip(st.box, st.v))  # type: ignore[return-value]

    def last_time(self, track_id: int) -> float | None:
        st = self._s.get(track_id)
        return st.t if st else None

    def prune(self, now: float) -> list[int]:
        dead = [tid for tid, st in self._s.items() if now - st.t > self.drop_s]
        for tid in dead:
            del self._s[tid]
        return dead

    def remove(self, track_id: int) -> None:
        self._s.pop(track_id, None)

    def ids(self) -> list[int]:
        return list(self._s)
