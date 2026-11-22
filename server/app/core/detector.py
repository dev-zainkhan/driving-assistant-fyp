"""YOLOv8n wrapper. Used ONLY from the inference thread."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import numpy as np

from app.config import model_path
from app.core.protocol import COCO_IDS
from app.models.schemas import Settings

log = logging.getLogger("da.detector")

COCO_NAMES = {v: k for k, v in COCO_IDS.items()}


@dataclass(slots=True)
class Detection:
    cls: str
    conf: float
    box: tuple[float, float, float, float]  # normalised x1, y1, x2, y2


def wanted_classes(settings: Settings) -> list[str]:
    out: list[str] = []
    if settings.alerts.get("people") is None or settings.alerts["people"].detect:
        out.append("person")
    if settings.alerts.get("vehicles") is None or settings.alerts["vehicles"].detect:
        out.append("car")
        if settings.include_other_vehicles:
            out += ["bus", "truck", "motorcycle", "bicycle"]
    return out


class Detector:
    def __init__(self, settings: Settings) -> None:
        import torch
        from ultralytics import YOLO

        self.settings = settings
        device = settings.device
        if device.startswith("cuda") and not torch.cuda.is_available():
            log.warning("CUDA not available, falling back to CPU (slow). Install torch 2.14.0+cu126.")
            device = "cpu"
        self.device = device
        self.gpu_name = torch.cuda.get_device_name(0) if device.startswith("cuda") else "cpu"
        self.model = YOLO(str(model_path(settings.model)))
        self.last_infer_ms = 0.0
        log.info("loaded %s on %s (%s)", settings.model, device, self.gpu_name)

    def warmup(self, n: int = 3) -> None:
        img = np.zeros((360, 640, 3), dtype=np.uint8)
        for _ in range(n):
            self.predict([img])

    def predict(self, images: list[np.ndarray], classes: list[str] | None = None) -> list[list[Detection]]:
        """Run one batched call. Returns detections per image (normalised boxes)."""
        if not images:
            return []
        s = self.settings
        class_ids = [COCO_IDS[c] for c in (classes if classes is not None else wanted_classes(s))]
        t0 = time.perf_counter()
        results = self.model.predict(
            images,
            imgsz=s.imgsz,
            conf=min(s.conf, s.track_low_conf),
            iou=s.iou,
            classes=class_ids,
            device=self.device,
            half=False,
            verbose=False,
        )
        self.last_infer_ms = (time.perf_counter() - t0) * 1000 / len(images)
        out: list[list[Detection]] = []
        for r in results:
            dets: list[Detection] = []
            b = r.boxes
            if b is not None and len(b):
                xyxyn = b.xyxyn.cpu().numpy()
                cls = b.cls.cpu().numpy().astype(int)
                conf = b.conf.cpu().numpy()
                for (x1, y1, x2, y2), c, p in zip(xyxyn, cls, conf):
                    name = COCO_NAMES.get(int(c))
                    if name is None:
                        continue
                    dets.append(Detection(name, float(p), (float(x1), float(y1), float(x2), float(y2))))
            out.append(dets)
        return out
