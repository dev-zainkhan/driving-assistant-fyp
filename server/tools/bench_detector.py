"""M1 check: load YOLOv8n on the GPU and print inference time per image.

Usage (from server/):  ..\\.venv\\Scripts\\python.exe tools\\bench_detector.py [--image path] [--n 50]
"""
from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402

from app.core.detector import Detector  # noqa: E402
from app.models.schemas import Settings  # noqa: E402


def sample_image() -> np.ndarray:
    import ultralytics

    p = Path(ultralytics.__file__).parent / "assets" / "bus.jpg"
    img = cv2.imread(str(p))
    if img is None:
        print("bus.jpg not found, using random noise")
        return np.random.randint(0, 255, (360, 640, 3), dtype=np.uint8)
    return cv2.resize(img, (640, 360))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image")
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--device", default="cuda:0")
    args = ap.parse_args()

    print(f"torch {torch.__version__}  cuda available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print("gpu:", torch.cuda.get_device_name(0))

    img = cv2.resize(cv2.imread(args.image), (640, 360)) if args.image else sample_image()
    det = Detector(Settings(device=args.device))
    print("device used:", det.device)
    det.warmup(5)

    found = det.predict([img])[0]
    print(f"detections on sample: {len(found)}")
    for d in found:
        print(f"  {d.cls:<10} conf {d.conf:.2f} box {tuple(round(v, 3) for v in d.box)}")

    for batch in (1, 2, 4):
        times = []
        for _ in range(args.n):
            t0 = time.perf_counter()
            det.predict([img] * batch)
            times.append((time.perf_counter() - t0) * 1000)
        per_img = statistics.mean(times) / batch
        print(f"batch {batch}: {statistics.mean(times):6.1f} ms per call, {per_img:5.1f} ms per image, "
              f"~{1000 / per_img:4.0f} images/s")
    if torch.cuda.is_available():
        print(f"peak VRAM: {torch.cuda.max_memory_allocated() / 1e6:.0f} MB")


if __name__ == "__main__":
    main()
