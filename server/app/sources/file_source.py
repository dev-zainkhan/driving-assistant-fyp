"""Backup mode: the server reads local video files as fake cameras (FR-S9).

Each file plays in its own thread at stream_fps, is fitted into the stream size (black bars,
never stretched, like the phone page) and JPEG-encoded (the job a phone does), then enters
the same pipeline as phone frames.

HD videos are expensive to decode (four 1280x720 videos used about 3 CPU cores). So during the
first round the small frames are also written to a cached copy in data/video_cache/, and
later rounds play that copy instead.
"""
from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import cv2

import numpy as np

from app.config import DATA_DIR, REPO_DIR
from app.core.runtime import CameraConn

if TYPE_CHECKING:
    from app.core.runtime import Runtime

log = logging.getLogger("da.file_source")


def resolve_video(path: str) -> Path:
    p = Path(path)
    if not p.is_absolute():
        p = REPO_DIR / p
    return p.resolve()


CACHE_DIR = DATA_DIR / "video_cache"
BIG_FACTOR = 1.25  # videos larger than the stream size by this much get a cached small copy


def fit(img: np.ndarray, w: int, h: int) -> np.ndarray:
    """Scale the picture to fit inside w x h without stretching; fill the rest with black."""
    ih, iw = img.shape[:2]
    if (iw, ih) == (w, h):
        return img
    k = min(w / iw, h / ih)
    nw, nh = max(1, round(iw * k)), max(1, round(ih * k))
    small = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
    if (nw, nh) == (w, h):
        return small
    out = np.zeros((h, w, 3), dtype=img.dtype)
    x, y = (w - nw) // 2, (h - nh) // 2
    out[y : y + nh, x : x + nw] = small
    return out


def cache_path(src: Path, w: int, h: int) -> Path:
    st = src.stat()
    return CACHE_DIR / f"{src.stem}-{st.st_size}-{int(st.st_mtime)}-{w}x{h}.mp4"


class FileSource(threading.Thread):
    def __init__(self, rt: "Runtime", position: str, path: Path) -> None:
        super().__init__(name=f"file-{position}", daemon=True)
        self.rt, self.position, self.path = rt, position, path
        self._halt = threading.Event()

    def stop(self) -> None:
        self._halt.set()

    def run(self) -> None:
        s = self.rt.settings
        w, h = s.stream_width, s.stream_height
        cached = cache_path(self.path, w, h)
        source = cached if cached.exists() else self.path
        cap = cv2.VideoCapture(str(source))
        if not cap.isOpened():
            log.error("cannot open %s", source)
            return
        big = source == self.path and (
            cap.get(cv2.CAP_PROP_FRAME_WIDTH) > w * BIG_FACTOR or cap.get(cv2.CAP_PROP_FRAME_HEIGHT) > h * BIG_FACTOR
        )
        writer, tmp = None, None
        if big:  # write the small copy while playing the first round
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            tmp = CACHE_DIR / f"{cached.stem}.{uuid.uuid4().hex[:6]}.part.mp4"
            writer = cv2.VideoWriter(str(tmp), cv2.VideoWriter_fourcc(*"mp4v"), s.stream_fps, (w, h))
            log.info("making a small copy of %s for later rounds", self.path.name)

        interval = 1.0 / max(1, s.stream_fps)
        quality = int(s.jpeg_quality * 100)
        seq, next_t, fails = 0, time.monotonic(), 0
        try:
            while not self._halt.is_set():
                ok, img = cap.read()
                if not ok:
                    fails += 1
                    if fails > 3:
                        log.error("video %s unreadable", source)
                        break
                    if writer is not None and fails == 1:  # first round done: switch to the small copy
                        writer.release()
                        writer = None
                        try:
                            os.replace(tmp, cached)
                        except OSError:
                            # another camera playing the same file finished its copy first (and
                            # Windows will not replace a file that is open): use that one
                            tmp.unlink(missing_ok=True)
                        source = cached if cached.exists() else self.path
                        cap.release()
                        cap = cv2.VideoCapture(str(source))
                        log.info("now playing the small copy of %s", self.path.name)
                        continue
                    # loop: seek back to the start; some formats cannot seek, so open the file again
                    if fails > 1 or not cap.set(cv2.CAP_PROP_POS_FRAMES, 0):
                        cap.release()
                        cap = cv2.VideoCapture(str(source))
                    continue
                fails = 0
                frame = fit(img, w, h)
                if writer is not None:
                    writer.write(frame)
                ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
                if ok and self.rt.loop is not None:
                    self.rt.loop.call_soon_threadsafe(self.rt.ingest, self.position, seq, time.time() * 1000, buf.tobytes())
                    seq += 1
                next_t += interval
                delay = next_t - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
                else:
                    next_t = time.monotonic()  # fell behind: don't try to catch up
        finally:
            cap.release()
            if writer is not None:  # stopped in the middle of the first round: drop the half copy
                writer.release()
                if tmp is not None:
                    tmp.unlink(missing_ok=True)


class FileSourceManager:
    def __init__(self, rt: "Runtime") -> None:
        self.rt = rt
        self.sources: dict[str, tuple[FileSource, str]] = {}

    async def start(self, mapping: dict[str, str]) -> list[str]:
        started = []
        for pos, path in mapping.items():
            p = resolve_video(path)
            if not p.is_file():
                raise FileNotFoundError(f"{pos}: video not found: {p}")
        for pos, path in mapping.items():
            p = resolve_video(path)
            self.stop(pos, notify=False)
            session = self.rt.new_session_id()
            await self.rt.register_camera(pos, CameraConn(session_id=session, source="file", video_name=p.name))
            src = FileSource(self.rt, pos, p)
            self.sources[pos] = (src, session)
            src.start()
            started.append(pos)
        return started

    def stop(self, pos: str, notify: bool = True) -> None:
        item = self.sources.pop(pos, None)
        if item is None:
            return
        src, session = item
        src.stop()
        if notify:
            self.rt.unregister_camera(pos, session)

    def stop_all(self) -> list[str]:
        stopped = list(self.sources)
        for pos in stopped:
            self.stop(pos)
        return stopped
