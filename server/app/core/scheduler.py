"""The one inference thread: owns the model and the GPU.

Every few ms it finds cameras that are due (their det_fps interval passed and their
slot holds a frame newer than the last one detected), decodes those JPEGs, runs one
batched predict call and hands results to the runtime. JPEG decoding and the model
run ONLY here, never on the event loop.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING

import cv2
import numpy as np

if TYPE_CHECKING:
    from app.core.runtime import Runtime

log = logging.getLogger("da.scheduler")

PRIORITY = ("front", "back", "left", "right")
PERIPHERAL_PRIORITY = ("left", "right", "front", "back")  # slide 36: side cameras get top priority
IDLE_SLEEP_S = 0.005
TICK_EVERY_S = 0.1


class InferenceThread(threading.Thread):
    def __init__(self, runtime: "Runtime") -> None:
        super().__init__(name="inference", daemon=True)
        self.rt = runtime
        self._halt = threading.Event()
        self._last_version = {p: 0 for p in PRIORITY}
        self._next_due = {p: 0.0 for p in PRIORITY}

    def stop(self) -> None:
        self._halt.set()

    def run(self) -> None:
        try:
            det = self.rt.detector_factory(self.rt.settings)
            det.warmup()
            self.rt.detector = det
            log.info("detector ready on %s", det.device)
        except Exception:
            log.exception("detector failed to load")
            self.rt.detector_error = True
            return

        self._last_tick = 0.0
        while not self._halt.is_set():
            self.rt.infer_heartbeat = time.monotonic()
            try:
                self._step()
            except Exception:
                # Never let one bad frame or bug stop detection for the rest of the drive.
                self.rt.infer_errors += 1
                log.exception("inference step failed (%d so far); continuing", self.rt.infer_errors)
                time.sleep(0.05)

    def _step(self) -> None:
        now = time.monotonic()
        if now - self._last_tick >= TICK_EVERY_S:
            self.rt.tick_warnings()
            self._last_tick = now
        rates = self.rt.settings.det_fps
        due = []
        order = PERIPHERAL_PRIORITY if self.rt.settings.vision.peripheral_vision else PRIORITY
        for pos in order:
            fps = getattr(rates, pos)
            if fps <= 0 or not self.rt.settings.camera_on.get(pos, True) or now < self._next_due[pos]:
                continue
            frame, version = self.rt.frame_store.get(pos)
            if frame is None or version == self._last_version[pos]:
                continue
            due.append((pos, frame, version))
            # Keep a fixed schedule (next = previous due + interval) so waiting for a
            # 30 fps frame does not lower the average rate; never schedule in the past.
            self._next_due[pos] = max(self._next_due[pos] + 1.0 / fps, now)
        if not due:
            time.sleep(IDLE_SLEEP_S)
            return

        batch_pos, batch_frames, images = [], [], []
        for pos, frame, version in due:
            self._last_version[pos] = version
            img = cv2.imdecode(np.frombuffer(frame.jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                log.warning("bad JPEG from %s seq %s", pos, frame.seq)
                continue
            batch_pos.append(pos)
            batch_frames.append(frame)
            images.append(img)
        if not images:
            return
        try:
            results = self.rt.detector.predict(images)
        except Exception:
            log.exception("predict failed")
            time.sleep(0.1)
            return
        infer_ms = getattr(self.rt.detector, "last_infer_ms", 0.0)
        for pos, frame, img, dets in zip(batch_pos, batch_frames, images, results):
            h, w = img.shape[:2]
            try:
                self.rt.process_detections(pos, frame, dets, w, h, infer_ms)
            except Exception:
                self.rt.infer_errors += 1
                log.exception("processing %s failed; its tracks are reset, other cameras continue", pos)
                self.rt.pipelines[pos].reset()  # drop any half-updated (broken) track
