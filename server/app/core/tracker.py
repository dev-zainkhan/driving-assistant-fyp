"""Per-camera tracker, ByteTrack style, in pure Python.

Why not Ultralytics' built-in tracker: frames from four cameras share one batched
predict call, and the batch content changes every cycle, so `model.track(persist=True)`
would mix cameras. This small tracker keeps one instance per camera:

1. Predict every track's box at the detection time (Smoother).
2. Match high-score detections to tracks by IoU (greedy, same class group).
3. Match remaining tracks to low-score detections (the ByteTrack idea: keeps
   tracks alive through brief low-confidence frames).
4. Unmatched high-score detections start new tracks.
5. Tracks not detected for `smoother_drop_s` are removed.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from app.core.detector import Detection
from app.core.distance import estimate_distance_m
from app.core.protocol import VEHICLE_CLASSES
from app.core.smoother import Box, Smoother
from app.models.schemas import Settings


def group_of(cls: str) -> str:
    return "vehicles" if cls in VEHICLE_CLASSES else "people"


def iou(a: Box, b: Box) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


@dataclass(slots=True)
class Track:
    track_id: int
    cls: str
    conf: float
    box: Box
    last_det_t: float
    first_t: float = 0.0  # when the track was first seen
    hits: int = 1  # consecutive detection cycles in which this track was matched
    last_cycle: int = 0
    distance_m: float | None = None
    dist_hist: deque = field(default_factory=lambda: deque(maxlen=64))  # (t, distance)

    @property
    def group(self) -> str:
        return group_of(self.cls)


class CameraTracker:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.smoother = Smoother(settings.smoother_alpha, settings.smoother_max_predict_s, settings.smoother_drop_s)
        self.tracks: dict[int, Track] = {}
        self._next_id = 1
        self._cycle = 0

    def _match(self, track_ids: list[int], dets: list[Detection], t: float) -> tuple[list[tuple[int, int]], list[int], list[int]]:
        pairs: list[tuple[float, int, int]] = []
        for ti in track_ids:
            tr = self.tracks[ti]
            pbox = self.smoother.predict(ti, t) or tr.box
            for di, d in enumerate(dets):
                if group_of(d.cls) != tr.group:
                    continue
                v = iou(pbox, d.box)
                if v >= self.settings.track_iou:
                    pairs.append((v, ti, di))
        pairs.sort(reverse=True)
        used_t: set[int] = set()
        used_d: set[int] = set()
        matches: list[tuple[int, int]] = []
        for _, ti, di in pairs:
            if ti in used_t or di in used_d:
                continue
            used_t.add(ti)
            used_d.add(di)
            matches.append((ti, di))
        return matches, [t_ for t_ in track_ids if t_ not in used_t], [i for i in range(len(dets)) if i not in used_d]

    def _apply(self, tr: Track, d: Detection, t: float, frame_w: int, frame_h: int) -> None:
        s = self.settings
        tr.cls, tr.conf, tr.box = d.cls, d.conf, d.box
        tr.hits = tr.hits + 1 if tr.last_cycle == self._cycle - 1 else 1
        tr.last_cycle = self._cycle
        tr.last_det_t = t
        self.smoother.update(tr.track_id, d.box, t)
        tr.distance_m = estimate_distance_m(d.box, d.cls, frame_w, frame_h, s.hfov_deg, s.real_heights_m, s.min_box_height_px)
        if tr.distance_m is not None:
            tr.dist_hist.append((t, tr.distance_m))

    def update(self, dets: list[Detection], t: float, frame_w: int, frame_h: int) -> list[Track]:
        s = self.settings
        self._cycle += 1
        high = [d for d in dets if d.conf >= s.conf]
        low = [d for d in dets if s.track_low_conf <= d.conf < s.conf]

        m1, rest_tracks, new_high = self._match(list(self.tracks), high, t)
        for ti, di in m1:
            self._apply(self.tracks[ti], high[di], t, frame_w, frame_h)
        m2, _, _ = self._match(rest_tracks, low, t)
        for ti, di in m2:
            self._apply(self.tracks[ti], low[di], t, frame_w, frame_h)
        for di in new_high:
            d = high[di]
            tr = Track(track_id=self._next_id, cls=d.cls, conf=d.conf, box=d.box, last_det_t=t, first_t=t, last_cycle=self._cycle - 1, hits=0)
            self._next_id += 1
            self.tracks[tr.track_id] = tr
            self._apply(tr, d, t, frame_w, frame_h)

        for tid in self.smoother.prune(t):
            self.tracks.pop(tid, None)
        for tid in [k for k, tr in self.tracks.items() if t - tr.last_det_t > s.smoother_drop_s]:
            self.tracks.pop(tid, None)
            self.smoother.remove(tid)
        return list(self.tracks.values())

    def detected_now(self, tr: Track) -> bool:
        return tr.last_cycle == self._cycle

    def reset(self) -> None:
        self.tracks.clear()
        self.smoother = Smoother(self.settings.smoother_alpha, self.settings.smoother_max_predict_s, self.settings.smoother_drop_s)
