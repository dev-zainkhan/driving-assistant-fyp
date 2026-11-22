"""Stress test the running server (start it first). Prints a short report.

Runs at the same time, for --seconds (default 60):
- 4 fake cameras at 30 fps (Ultralytics sample picture, moving a little)
- a healthy viewer that counts the frames it receives per camera
- a stuck viewer that never reads anything (like a frozen tablet)
- broken frames: every 50th frame of the front camera is not a valid JPEG
- a drop: the right camera disconnects at 1/3 of the run and comes back 5 s later

Usage (from server/):  ..\\.venv\\Scripts\\python.exe tools\\stress_test.py [--seconds 60]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import struct
import time
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
import websockets

HEADER = struct.Struct("<BBIdH")
POSITIONS = ("front", "left", "right", "back")


def sample_frames(n: int = 30) -> list[bytes]:
    import ultralytics

    img = cv2.imread(str(Path(ultralytics.__file__).parent / "assets" / "bus.jpg"))
    img = cv2.resize(img, (640, 360))
    out = []
    for i in range(n):
        shifted = np.roll(img, int(20 * np.sin(i / 5)), axis=1)
        out.append(cv2.imencode(".jpg", shifted, [cv2.IMWRITE_JPEG_QUALITY, 70])[1].tobytes())
    return out


async def camera(url: str, pos: str, frames: list[bytes], seconds: float, report: dict, drop: tuple | None) -> None:
    start = time.monotonic()
    seq = 0
    sent = 0
    broken = 0
    reconnects = 0
    while time.monotonic() - start < seconds:
        try:
            async with websockets.connect(f"{url}/ws/camera/{pos}", max_size=None) as ws:
                await ws.send(json.dumps({"type": "hello", "position": pos, "client": "stress", "video_name": "stress"}))
                await ws.recv()
                await ws.recv()
                next_t = time.monotonic()
                while (t := time.monotonic() - start) < seconds:
                    if drop and drop[0] <= t < drop[1]:
                        break  # simulate the phone losing Wi-Fi
                    payload = frames[seq % len(frames)]
                    if pos == "front" and seq % 50 == 49:
                        payload = os.urandom(2000)  # broken JPEG
                        broken += 1
                    await ws.send(HEADER.pack(1, 1, seq & 0xFFFFFFFF, time.time() * 1000, 0) + payload)
                    seq += 1
                    sent += 1
                    next_t += 1 / 30
                    await asyncio.sleep(max(0, next_t - time.monotonic()))
            if drop and drop[0] <= time.monotonic() - start < drop[1]:
                await asyncio.sleep(drop[1] - (time.monotonic() - start))
                reconnects += 1
        except (OSError, websockets.ConnectionClosed):
            reconnects += 1
            await asyncio.sleep(1)
    report[pos] = {"sent": sent, "broken": broken, "reconnects": reconnects}


async def good_viewer(url: str, seconds: float, report: dict) -> None:
    frames = Counter()
    overlays = 0
    texts = Counter()
    statuses = []
    async with websockets.connect(f"{url}/ws/viewer", max_size=None) as ws:
        await ws.send(json.dumps({"type": "subscribe", "video": "all"}))
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            try:
                m = await asyncio.wait_for(ws.recv(), timeout=2)
            except asyncio.TimeoutError:
                texts["(2 s silence)"] += 1
                continue
            if isinstance(m, bytes):
                frames[POSITIONS[m[2]]] += 1
            else:
                j = json.loads(m)
                texts[j["type"]] += 1
                if j["type"] == "overlay":
                    overlays += 1
                if j["type"] == "camera_status":
                    statuses.append(f"{j['position']}:{j['status']}")
    report["viewer"] = {
        "fps": {p: round(frames[p] / seconds, 1) for p in POSITIONS},
        "overlays": overlays,
        "messages": dict(texts),
        "camera_status": statuses,
    }


async def stuck_viewer(url: str, seconds: float) -> None:
    async with websockets.connect(f"{url}/ws/viewer", max_size=None) as ws:
        await ws.send(json.dumps({"type": "subscribe", "video": "all"}))
        await asyncio.sleep(seconds)  # never reads


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="ws://127.0.0.1:8000")
    ap.add_argument("--seconds", type=float, default=60)
    a = ap.parse_args()
    frames = sample_frames()
    report: dict = {}
    drop = (a.seconds / 3, a.seconds / 3 + 5)
    await asyncio.gather(
        *(camera(a.url, p, frames, a.seconds, report, drop if p == "right" else None) for p in POSITIONS),
        good_viewer(a.url, a.seconds, report),
        stuck_viewer(a.url, a.seconds),
    )
    http = a.url.replace("ws://", "http://")
    import urllib.request

    status = json.load(urllib.request.urlopen(f"{http}/api/status"))
    health = json.load(urllib.request.urlopen(f"{http}/api/health"))
    print(json.dumps({"cameras_sent": {p: report[p] for p in POSITIONS}, "healthy_viewer": report["viewer"],
                      "server_detector": health["detector"], "server_errors": status.get("errors")}, indent=1))


if __name__ == "__main__":
    asyncio.run(main())
