"""Make 4 short synthetic test videos (no download) from the Ultralytics sample picture.

They are NOT road videos: they only prove that backup mode and the pipeline work.
Written as WebM (VP8) so browsers can also play them (incident playback); OpenCV writes
VP8 without extra libraries, while browsers cannot play OpenCV's default "mp4v".
Usage (from server/):  ..\.venv\Scripts\python.exe tools\make_test_videos.py [--out ..\videos\test] [--seconds 10]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np


def main() -> None:
    import ultralytics

    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[2] / "videos" / "test"))
    ap.add_argument("--seconds", type=float, default=10)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    img = cv2.imread(str(Path(ultralytics.__file__).parent / "assets" / "bus.jpg"))
    W, H, fps = 640, 360, 30
    base = cv2.resize(img, (W * 2, int(img.shape[0] * W * 2 / img.shape[1])))
    for pos, speed in (("front", 1.0), ("left", 2.0), ("right", -2.0), ("back", 0.5)):
        path = out / f"{pos}.webm"
        vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"VP80"), fps, (W, H))
        n = int(a.seconds * fps)
        for i in range(n):
            # slow zoom + pan so boxes move and grow (object approaching)
            z = 1.0 + 0.6 * (i / n)
            cw, ch = int(base.shape[1] / 2 / z), int(base.shape[0] / z)
            cx = int(base.shape[1] / 2 + speed * 80 * np.sin(i / n * np.pi))
            x0 = max(0, min(base.shape[1] - cw, cx - cw // 2))
            y0 = max(0, (base.shape[0] - ch) // 2)
            frame = cv2.resize(base[y0 : y0 + ch, x0 : x0 + cw], (W, H))
            vw.write(frame)
        vw.release()
        print("wrote", path)


if __name__ == "__main__":
    main()
