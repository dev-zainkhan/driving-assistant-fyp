"""Send a local video (or a still image) to the server exactly like a phone camera node.

Examples (from server/):
  ..\\.venv\\Scripts\\python.exe tools\\fake_camera.py --position front --video ..\\videos\\front.mp4
  ..\\.venv\\Scripts\\python.exe tools\\fake_camera.py --position left --image sample      (Ultralytics bus.jpg)
  ..\\.venv\\Scripts\\python.exe tools\\fake_camera.py --all --image sample                 (4 cameras at once)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import struct
import time
from pathlib import Path

import cv2
import numpy as np
import websockets

HEADER = struct.Struct("<BBIdH")
POSITIONS = ("front", "left", "right", "back")


def sample_path() -> Path:
    import ultralytics

    return Path(ultralytics.__file__).parent / "assets" / "bus.jpg"


class Source:
    def __init__(self, video: str | None, image: str | None, w: int, h: int) -> None:
        self.w, self.h = w, h
        self.cap = None
        self.still = None
        self.frame_i = 0
        if video:
            self.cap = cv2.VideoCapture(video)
            if not self.cap.isOpened():
                raise SystemExit(f"cannot open video {video}")
        else:
            p = sample_path() if image in (None, "sample") else Path(image)
            img = cv2.imread(str(p))
            if img is None:
                raise SystemExit(f"cannot read image {p}")
            self.still = cv2.resize(img, (w, h))

    def next(self) -> np.ndarray:
        if self.cap is not None:
            ok, img = self.cap.read()
            if not ok:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, img = self.cap.read()
            return cv2.resize(img, (self.w, self.h))
        # still image: slide it a little so boxes move
        self.frame_i += 1
        shift = int(20 * np.sin(self.frame_i / 15))
        return np.roll(self.still, shift, axis=1)


async def run(url: str, position: str, src: Source, fps: float, quality: int, seconds: float | None) -> None:
    uri = f"{url}/ws/camera/{position}"
    backoff = 1.0
    start = time.monotonic()
    while True:
        try:
            async with websockets.connect(uri, max_size=None) as ws:
                await ws.send(json.dumps({"type": "hello", "position": position, "client": "fake_camera/1.0",
                                          "width": src.w, "height": src.h, "fps": fps, "video_name": "fake"}))
                print(f"[{position}] connected:", await ws.recv())
                backoff = 1.0
                seq, sent, t_report = 0, 0, time.monotonic()
                next_t = time.monotonic()
                while seconds is None or time.monotonic() - start < seconds:
                    ok, buf = cv2.imencode(".jpg", src.next(), [cv2.IMWRITE_JPEG_QUALITY, quality])
                    ts = time.time() * 1000
                    await ws.send(HEADER.pack(1, 1, seq & 0xFFFFFFFF, ts, 0) + buf.tobytes())
                    seq += 1
                    sent += 1
                    now = time.monotonic()
                    if now - t_report >= 2:
                        rate = sent / (now - t_report)
                        await ws.send(json.dumps({"type": "stats", "sent_fps": round(rate, 1), "dropped": 0}))
                        print(f"[{position}] sent {rate:.1f} fps")
                        sent, t_report = 0, now
                    next_t += 1 / fps
                    await asyncio.sleep(max(0, next_t - time.monotonic()))
                    if next_t < time.monotonic() - 0.5:
                        next_t = time.monotonic()
                return
        except (OSError, websockets.ConnectionClosed) as e:
            print(f"[{position}] disconnected ({e}); retry in {backoff:.0f}s")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 5)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="ws://127.0.0.1:8000")
    ap.add_argument("--position", choices=POSITIONS, default="front")
    ap.add_argument("--all", action="store_true", help="run all four positions")
    ap.add_argument("--video")
    ap.add_argument("--image", help="image path, or 'sample' for Ultralytics bus.jpg")
    ap.add_argument("--fps", type=float, default=30)
    ap.add_argument("--quality", type=int, default=70)
    ap.add_argument("--seconds", type=float)
    a = ap.parse_args()
    positions = POSITIONS if a.all else (a.position,)
    await asyncio.gather(*(run(a.url, p, Source(a.video, a.image, 640, 360), a.fps, a.quality, a.seconds) for p in positions))


if __name__ == "__main__":
    asyncio.run(main())
