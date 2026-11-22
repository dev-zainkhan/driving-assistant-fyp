# Driving Assistant FYP: Design Document

Nov 19, 2026 · @Alishba

## 1. Introduction

The Driving Assistant is a laptop-hosted system that watches four camera feeds (front, left, right, back), detects cars and people with YOLOv8n, and shows a fixed dashboard that warns the driver where something is. Four phones act as the cameras: each plays a road video in a browser and streams frames to the laptop over Wi-Fi.

### 1.1 Problem statement

Drivers have blind spots on the sides and behind the car, and attention on the road ahead drops over long drives. Commercial ADAS (Advanced Driver Assistance Systems) with surround cameras are expensive and mostly found in high-end cars. A low-cost assistant that combines several camera views and warns only when something matters can reduce missed hazards. The presentation frames it as AR guidance for drivers with low vision (peripheral vision loss, night blindness), so warnings are large, colour-coded and spoken.

### 1.2 Objectives

1. Receive four live video streams from four "camera nodes" (phones in a browser) over a local Wi-Fi network.
2. Run real-time object detection (cars and people in version 1) on all four streams on one laptop GPU.
3. Show a constant-layout dashboard: front feed always large in the centre with all warnings; left, back and right slots always reserved, black when nothing is detected, showing the feed with a warning when something is.
4. Keep the backend client-agnostic so four different frontends (React, Next.js, Flutter, React Native) can use the same API.
5. Extend in later phases to potholes, traffic lights, road signs, speed limits, night vision, incident saving, a windscreen (AR-style) view and settings.

### 1.3 Scope

**In scope for the basic version:** phone camera-node web page, FastAPI server, YOLOv8n (COCO pretrained) detection of `car` and `person` (plus `bus`, `truck`, `motorcycle`, `bicycle` mapped to vehicle if cheap to include), per-camera warnings, constant dashboard in React and Next.js, and a backup mode where the server reads video files directly.

**Out of scope:** real car-mounted cameras, road testing, control of the vehicle (no braking or steering), cloud hosting, training custom models in phase 1.

### 1.4 Constraints and assumptions

| Item | Value |
| --- | --- |
| Server laptop | MSI GS65 Stealth Thin 8RF, Intel i7-8750H, 16 GB RAM |
| GPU | NVIDIA GTX 1070 Max-Q, 8 GB VRAM |
| OS and runtime | Windows 11, Python 3.12 |
| Known issue | Installed PyTorch is CPU-only; a CUDA build must be installed (section 5.2) |
| Model | YOLOv8n pretrained on COCO, FP32 |
| Network | All phones and laptop on one Wi-Fi (router or phone hotspot) |
| Camera input | Road videos from each phone's gallery, played in the browser |
| Stream rate | 30 fps, about 640x360 JPEG per frame, per camera |
| Detection rate | Front 20 fps, back 10 fps, left 8 fps, right 8 fps |
| Latency | Some delay is acceptable (supervisor); target under 300 ms end to end |
| Team | Alishba (React JS), Zain (Next.js), Bilawal (Flutter), Bilal (React Native) |

### 1.5 Glossary

- **Camera node**: a phone browser page that plays a video and sends its frames to the server.
- **Viewer / dashboard**: a frontend app (React, Next.js, Flutter or RN) that shows the four slots and warnings.
- **Detection fps**: how many frames per second go through YOLO for a camera. Display fps stays at 30.
- **Track**: an object followed across frames with a stable id, used to smooth boxes between detections.
- **Warning**: a message raised when a tracked object is in a danger zone of a camera (for example a person close ahead).

## 2. Software Requirements Specification (SRS)

The system has three parts: camera nodes (phones), one server (laptop), and viewer apps (dashboards). Requirements below use ids so tests and code comments can refer to them.

### 2.1 Actors

| Actor | Description |
| --- | --- |
| Driver (demo user) | Watches the dashboard and hears warnings. |
| Camera operator | Opens the camera page on a phone, picks position and video, presses Play. In the demo this is a team member. |
| Admin / developer | Starts the server, changes settings, reviews incidents. |

### 2.2 Feature list by phase

| Phase | Feature |
| --- | --- |
| 1 (basic, for supervisor demo) | 4 camera nodes, live streaming, car and person detection, tracking, warnings, constant dashboard in React and Next.js, file-source backup mode |
| 2 | Settings screens (Detection and alerts, voice, vision type), spoken alerts, system check and system status screens, incident saving with list and playback |
| 3 | Traffic lights (COCO class 9) and stop signs (COCO class 11), then pothole model, road signs and speed limits (custom models) |
| 4 | Night vision enhancement, windscreen AR mirror view, top-down "Tesla view" (car in the middle, detected objects around it), Flutter and React Native clients |

### 2.3 Functional requirements

**Camera node (phone web page)**

- **FR-C1** The page lets the user choose a position: front, left, right or back.
- **FR-C2** The page lets the user pick a video file from the phone gallery (`<input type="file" accept="video/*">`).
- **FR-C3** On Play, the page plays the video (muted, looping) and sends frames to the server at 30 fps as JPEG, about 640x360, over a WebSocket.
- **FR-C4** The page shows connection state (connecting, live, reconnecting), sent fps and the server's position acknowledgement.
- **FR-C5** If the connection drops, the page reconnects automatically with backoff (1, 2, 4, max 5 seconds).
- **FR-C6** Only one node per position is active. A second node for the same position replaces the first (server sends `replaced` to the old one).

**Server**

- **FR-S1** Accept camera WebSocket connections at `/ws/camera/{position}`.
- **FR-S2** Keep only the latest frame per camera; older unprocessed frames are dropped (no queue build-up).
- **FR-S3** Run YOLOv8n on the GPU with per-camera detection rates: front 20 fps, back 10 fps, left 8 fps, right 8 fps (configurable).
- **FR-S4** Detect `person` and `car` in phase 1. `bus`, `truck`, `motorcycle`, `bicycle` are reported as class `vehicle` subtypes if enabled in settings.
- **FR-S5** Track objects per camera with stable ids, and smooth or predict boxes for frames between detections so the display stays at 30 fps.
- **FR-S6** Compute a warning level per camera (`none`, `caution`, `danger`) using zones and object size rules (section 3.6).
- **FR-S7** Broadcast to every connected viewer: front frames always, side and back frames only while that camera has an active warning, plus detections and warnings as JSON.
- **FR-S8** Expose REST endpoints for health, status, settings and incidents (section 3.5).
- **FR-S9** Backup mode: read up to four local video files as fake camera streams at 30 fps, with the same downstream pipeline.
- **FR-S10** Serve the camera node page as static files so phones only need a browser.
- **FR-S11 (phase 2)** Keep the last 90 s from all four cameras and save them as an incident (front snapshot, one clip per camera, the warnings given just before, JSON metadata) when the driver presses Save or, optionally, when a danger warning starts (60 s cooldown). Hard-brake detection needs a phone accelerometer and is optional.

**Viewer (dashboard)**

- **FR-V1** Show the constant layout (section 4): big front slot, and left, back, right slots that never move.
- **FR-V2** Draw boxes, labels and warnings over the front feed at all times.
- **FR-V3** Show a side or back slot fully black when that camera has no warning; show its feed with a coloured border and label while it has one.
- **FR-V4** Tapping the screen shows only two buttons, Settings and Windscreen, which hide again after 3 s.
- **FR-V5** Show a small status indicator per camera (offline, live) without changing the layout.
- **FR-V6** Play an alert sound on a new `danger` warning (phase 2, settings toggle).

### 2.4 Non-functional requirements

| Id | Requirement | Target |
| --- | --- | --- |
| NFR-1 Performance | Display rate on dashboard | 30 fps for front, 30 fps for active side slots |
| NFR-2 Performance | Detection rate | Front 20, back 10, left 8, right 8 fps on GTX 1070 Max-Q |
| NFR-3 Latency | Phone send to box on screen | Under 300 ms on a 5 GHz router (some delay accepted) |
| NFR-4 Accuracy | Car and person detection | YOLOv8n COCO baseline, confidence 0.35 default; report mAP on a small labelled set of 100 frames |
| NFR-5 Reliability | Camera disconnect | Server and other cameras keep running; slot shows offline |
| NFR-6 Portability | Client independence | Any client that speaks WebSocket + JSON + JPEG works with no server change |
| NFR-7 Usability | Fixed layout | No camera picker, no slot shifting; warnings readable from 1 m |
| NFR-8 Maintainability | Code | Typed Python (pydantic models), one module per pipeline stage, unit tests for warnings logic |
| NFR-9 Resource use | GPU memory | Under 2 GB VRAM; CPU under 70% on i7-8750H |
| NFR-10 Security | Local network only | Server binds to LAN; no internet needed; no personal data stored except incident clips |

## 3. Software Design Specification (SDS)

The server is one FastAPI process with two paths: a fast display path that forwards every phone JPEG to viewers unchanged, and a slower detection path that runs YOLO on the newest frame of each camera at its own rate. Boxes are drawn by the viewer, so the server never re-encodes video.

### 3.1 Architecture overview

```text
 CAMERA NODES (phones)        LAPTOP SERVER (FastAPI + YOLOv8n, GTX 1070)                 VIEWERS
 +-------------+           +---------------------------------------------------+     +-----------------+
 | Front phone |--+        |  +------------------+        +-----------------+  |     | React (Alishba) |
 +-------------+  |        |  | Ingest           |------->| Broadcaster     |--+---->+-----------------+
 | Left phone  |--+------->|  | /ws/camera/{pos} | display| /ws/viewer      |  |     | Next.js (Zain)  |
 +-------------+  | JPEG   |  +------------------+  path  | front always,   |  +---->+-----------------+
 | Right phone |--+ 30 fps |           |                  | others only on  |  |     | Flutter / RN    |
 +-------------+  | WS     |           v                  | warning         |  +---->| (later)         |
 | Back phone  |--+ Wi-Fi  |  +------------------+        +-----------------+        +-----------------+
 +-------------+           |  | Frame store      |                 ^                         ^
                           |  | newest only      |                 |                         |
                           |  +------------------+                 |                         |
                           |           |                           |                         |
                           |           v                           |                         |
                           |  +------------------------------------------------+             |
                           |  | Inference thread (GPU): YOLOv8n batch at       |             |
                           |  | 20/10/8/8 fps, ByteTrack, smoother, distance,  |             |
                           |  | warning rules                                  |             |
                           |  +------------------------------------------------+             |
                           |  +------------------+   +--------------------+                  |
                           |  | Storage (phase 2)|<--| REST API /api/*    |------------------+ REST JSON
                           |  +------------------+   +--------------------+
                           +---------------------------------------------------+
```

Phone frames enter through Ingest and are forwarded to viewers right away (display path); the inference thread reads only the newest frame per camera and adds boxes and warnings (detection path).

| Component | Runs on | Technology | Responsibility |
| --- | --- | --- | --- |
| Camera node | 4 phones (browser) | Plain HTML + JS, served by the server | Play gallery video, grab frames with canvas, send JPEG over WebSocket |
| Ingest | Laptop | FastAPI WebSocket `/ws/camera/{position}` | Receive frames, store latest per camera, hand frame to broadcaster |
| Frame store | Laptop | Python dict + lock, 1 slot per camera | Keep only the newest frame (drop stale) |
| Detection scheduler | Laptop, 1 thread | Python thread + Ultralytics YOLOv8n on CUDA | Pick cameras that are due, batch frames, run model |
| Tracker | Laptop | ByteTrack (Ultralytics built-in or `trackers` package), one per camera | Stable track ids |
| Smoother | Laptop | Small Python class | Predict box positions for frames between detections |
| Warning engine | Laptop | Pure Python rules | Turn tracks into `none` / `caution` / `danger` per camera |
| Broadcaster | Laptop | FastAPI WebSocket `/ws/viewer` | Send frames + overlay JSON + warning state to all viewers |
| REST API | Laptop | FastAPI routes `/api/*` | Health, status, settings, incidents, file sources |
| Storage (phase 2) | Laptop | SQLite + files in `data/` | Settings JSON, incidents (snapshot, clip, metadata) |
| Viewers | Laptop browser, tablet, phone | React (Vite), Next.js; later Flutter, React Native | Constant dashboard |

### 3.2 Data flow for one frame

1. The phone draws the current video frame onto a hidden 640x360 canvas and calls `canvas.toBlob(cb, "image/jpeg", 0.7)`.
2. It prepends a 16-byte header (sequence number, capture time) and sends the bytes over the camera WebSocket.
3. The server writes the frame into that camera's single slot in the frame store, replacing any older frame.
4. Display path: the broadcaster immediately forwards the JPEG to viewers that should see this camera, together with an `overlay` message holding the smoothed boxes for that frame's time.
5. Detection path: the scheduler thread wakes every 5 ms, finds cameras whose next detection time has passed and whose slot holds a frame newer than the last one detected, decodes those JPEGs with OpenCV, and runs one batched `model.predict` call.
6. Results go to that camera's tracker, then the smoother (stores box and velocity per track), then the warning engine.
7. If a camera's warning level changes, the broadcaster sends `warning_state` to all viewers; side and back video starts or stops flowing accordingly.

### 3.3 Concurrency model

- Uvicorn runs the asyncio event loop for all WebSockets and REST calls. Network handlers never call the model.
- One dedicated inference thread owns the YOLO model and the GPU. A single thread avoids GPU contention and keeps VRAM low; batching up to 4 frames per call uses the GPU well.
- The frame store, tracks and warning state are shared through small objects guarded by `threading.Lock`. The inference thread hands results back to the event loop with `loop.call_soon_threadsafe`.
- Scheduling rule per camera: `due = now >= last_detect_time + 1 / det_fps[camera]` and `frame.seq > last_detected_seq`. Order due cameras by priority front, back, left, right.
- Expected load: 20 + 10 + 8 + 8 = 46 inferences per second. YOLOv8n at 640 px usually takes roughly 8 to 15 ms per image on a GTX 1070-class GPU in FP32 (estimate; measure on the laptop in milestone M2), so the GPU is about half busy.

### 3.4 Message formats (WebSocket protocol v1)

All JSON messages have a `type` field. All box coordinates are normalised to 0..1 relative to the frame width and height, so any client size works. Camera positions are the strings `front`, `left`, `right`, `back`; in binary headers they use index 0, 1, 2, 3 in that order. Integers are little-endian.

**Camera node to server** (`ws://<laptop-ip>:8000/ws/camera/{position}`)

First message, text:

```json
{"type": "hello", "position": "front", "client": "camera-web/1.0", "width": 640, "height": 360, "fps": 30, "video_name": "road_front.mp4"}
```

Then one binary message per frame:

| Bytes | Field | Type | Notes |
| --- | --- | --- | --- |
| 0 | version | uint8 | 1 |
| 1 | msg\_type | uint8 | 1 = frame |
| 2-5 | seq | uint32 | Starts at 0, +1 per frame |
| 6-13 | capture\_ts\_ms | float64 | `performance.timeOrigin + performance.now()` on the phone |
| 14-15 | reserved | uint16 | 0 |
| 16-end | jpeg | bytes | The JPEG file |

Optional text message every 2 s: `{"type": "stats", "sent_fps": 29.8, "dropped": 3}`.

**Server to camera node**

```json
{"type": "ack", "position": "front", "session_id": "c1f3", "server_time_ms": 1763540000000}
{"type": "config", "fps": 30, "jpeg_quality": 0.7, "width": 640, "height": 360}
{"type": "replaced", "reason": "another node took this position"}
{"type": "error", "code": "BAD_POSITION", "message": "position must be front, left, right or back"}
```

**Viewer to server** (`ws://<laptop-ip>:8000/ws/viewer`)

```json
{"type": "subscribe", "video": "auto"}
```

`video` is `auto` (default: front always, other cameras only while they have a warning), `all` (debug: every camera always) or `none` (data only).

**Server to viewer, binary frame**

| Bytes | Field | Type | Notes |
| --- | --- | --- | --- |
| 0 | version | uint8 | 1 |
| 1 | msg\_type | uint8 | 1 = frame |
| 2 | camera | uint8 | 0 front, 1 left, 2 right, 3 back |
| 3 | reserved | uint8 | 0 |
| 4-7 | seq | uint32 | Same seq as the phone sent |
| 8-15 | capture\_ts\_ms | float64 | From the phone |
| 16-23 | server\_ts\_ms | float64 | When the server received it |
| 24-end | jpeg | bytes | Forwarded unchanged |

**Server to viewer, text messages**

`welcome`, sent once on connect:

```json
{"type": "welcome", "protocol": 1, "server_version": "0.1.0",
 "cameras": [{"position": "front", "status": "online"}, {"position": "left", "status": "offline"}],
 "settings": {"...": "same object as GET /api/settings"}}
```

`overlay`, sent right after each forwarded frame, with the same `camera` and `seq`:

```json
{"type": "overlay", "camera": "front", "seq": 1234, "det_seq": 1230,
 "objects": [
   {"track_id": 7, "cls": "person", "conf": 0.82, "box": [0.41, 0.38, 0.49, 0.80], "predicted": true, "zone": "center", "distance_m": 5.4, "level": "danger"},
   {"track_id": 3, "cls": "car", "conf": 0.91, "box": [0.10, 0.45, 0.30, 0.70], "predicted": false, "zone": "left", "distance_m": 31.0, "level": "none"}
 ],
 "warning": {"level": "danger", "codes": ["PERSON_AHEAD"], "text": "Person ahead"}}
```

`box` is `[x1, y1, x2, y2]`. `predicted` is true when the box was extrapolated by the smoother rather than detected on this frame. `det_seq` is the frame the last real detection used.

`warning_state`, sent whenever any camera's level or codes change:

```json
{"type": "warning_state", "ts": 1763540001234,
 "cameras": {
   "front": {"level": "danger", "codes": ["PERSON_AHEAD"], "text": "Person ahead", "since": 1763540001100},
   "left":  {"level": "none", "codes": [], "text": "", "since": 1763539990000},
   "right": {"level": "caution", "codes": ["VEHICLE_RIGHT"], "text": "Car on right", "since": 1763540000800},
   "back":  {"level": "none", "codes": [], "text": "", "since": 1763539990000}}}
```

`camera_status`, on connect or disconnect of a node:

```json
{"type": "camera_status", "position": "left", "status": "offline"}
```

`stats`, once per second:

```json
{"type": "stats", "cameras": {"front": {"in_fps": 29.7, "det_fps": 19.8, "latency_ms": 140, "infer_ms": 11.2}}, "gpu": "cuda:0"}
```

`incident` (phase 2): `{"type": "incident", "id": "inc_0007", "camera": "front", "codes": ["PERSON_AHEAD"], "ts": 1763540001100}`.

### 3.5 REST API (JSON, base `http://<laptop-ip>:8000`)

| Method | Path | Phase | Purpose | Response |
| --- | --- | --- | --- | --- |
| GET | `/api/health` | 1 | Liveness and GPU check | `{"status":"ok","device":"cuda:0","model":"yolov8n.pt"}` |
| GET | `/api/meta` | 1 | Positions, classes, warning codes, protocol version, so clients do not hard-code them | `{"positions":[...],"classes":[...],"warning_codes":{...},"protocol":1}` |
| GET | `/api/status` | 1 | Per-camera online state, fps, latency | same shape as `stats` |
| GET | `/api/settings` | 1 | Current settings | `Settings` object |
| PATCH | `/api/settings` | 2 | Partial update, validated | updated `Settings` |
| POST | `/api/sources/files` | 1 | Start backup mode: `{"front":"videos/front.mp4","left":"videos/left.mp4",...}` | `{"started":["front","left"]}` |
| DELETE | `/api/sources/files` | 1 | Stop backup mode | `{"stopped":true}` |
| GET | `/api/incidents?camera=&limit=50` | 2 | List incidents, newest first | `[Incident]` |
| GET | `/api/incidents/{id}` | 2 | One incident | `Incident` |
| GET | `/api/incidents/{id}/snapshot.jpg` | 2 | Snapshot image | JPEG |
| GET | `/api/incidents/{id}/clip.mp4` | 2 | Short clip | MP4 |
| DELETE | `/api/incidents/{id}` | 2 | Delete incident | `204` |
| GET | `/camera` | 1 | Camera node web page (static) | HTML |

Errors use one shape: `{"error": {"code": "NOT_FOUND", "message": "incident inc_0099 not found"}}`. CORS allows all origins because everything runs on a private LAN.

### 3.6 Warning engine rules (phase 1)

The presentation sets warnings by distance in metres (Settings, "Alert at": vehicles 20 m, people 6 m, traffic lights 15 m) and by colour: orange = near, warn now; yellow = a little near; white = far, just tracked; blue = traffic signs and sign boards. The server therefore estimates a rough distance for every tracked object with the pinhole formula `distance_m = real_height_m * focal_px / box_height_px`, using typical heights (person 1.7 m, car 1.5 m, bus or truck 3.0 m, motorcycle or bicycle 1.4 m) and a focal length from an assumed 70 degree horizontal field of view (`focal_px = (frame_width / 2) / tan(35 deg)`, about 457 px at 640 px wide). This is an approximation for demo videos whose real camera is unknown; it is good enough to rank near and far, and the field of view is a setting. An object is in a camera's zone when its bottom-centre point is inside that zone (normalised coordinates).

| Camera | Code | Object and zone | Orange (danger) | Yellow (caution) |
| --- | --- | --- | --- | --- |
| front | `PERSON_AHEAD` | person, centre zone x 0.25 to 0.75 | distance <= people alert\_at (6 m) | <= 1.5 x alert\_at |
| front | `VEHICLE_AHEAD` | car or other vehicle in our lane (Lane setup) and in our path | closer than 7 m, or within alert\_at (20 m) and coming closer at 2 m/s or more, or time to collision under 3 s (within 20 m); see docs/protocol.md section 5 | <= 1.5 x alert\_at |
| left | `VEHICLE_LEFT` / `PERSON_LEFT` | vehicle or person, lower 70% of frame | distance <= alert\_at | <= 1.5 x alert\_at |
| right | `VEHICLE_RIGHT` / `PERSON_RIGHT` | vehicle or person, lower 70% of frame | distance <= alert\_at | <= 1.5 x alert\_at |
| back | `VEHICLE_BEHIND` / `PERSON_BEHIND` | vehicle or person in the back camera's lane | vehicles: same closing-speed rule as front; people: distance <= alert\_at | <= 1.5 x alert\_at |

Everything else that is detected and enabled is drawn white (far, tracked). For side and back cameras, only orange and yellow switch the slot from black to video (FR-V3); white objects alone keep the slot black.

Rules for stability: a track must be seen in 2 consecutive detections before it can raise a warning; approach speed is the change in estimated distance over the last 0.5 s; a camera's level stays active for 1.0 s after the last qualifying object (hold time) so slots do not flicker; the camera level is the highest level of its objects; the warning text names the class and side, for example "Car", "Car behind", "Person ahead, 5 m". Viewers speak each new orange warning with the browser speech API when "announce" is on for that class. All numbers live in `Settings` so they can be tuned during testing. Phase 3 adds `RED_LIGHT`, `STOP_SIGN`, `POTHOLE`, `SPEED_BREAKER`, `ROAD_SIGN` and `SPEED_LIMIT` (with a `value` field), shown blue as banners at the top left of the front view.

### 3.7 Smoother (box prediction between detections)

For each track the smoother keeps the last detected box `b`, its time `t`, and a velocity `v` (per-second change of each coordinate, exponential moving average with alpha 0.5). For a display frame at time `T`, the predicted box is `b + v * min(T - t, 0.3)`. A track not detected for 0.7 s is removed. This keeps boxes moving smoothly on 30 fps video while left and right cameras are only detected 8 times a second.

### 3.8 Data models (pydantic, server `app/models/schemas.py`)

```python
Position = Literal["front", "left", "right", "back"]
Level = Literal["none", "caution", "danger", "info"]   # white, yellow, orange, blue

class CameraRates(BaseModel):
    front: float = 20
    back: float = 10
    left: float = 8
    right: float = 8

class ObjectAlert(BaseModel):          # one row of the "Detection & alerts" screen
    detect: bool = True
    announce: bool = True
    alert_at_m: float                    # orange threshold in metres
    show_text: bool = False

class VisionType(BaseModel):            # from the setup screens in the presentation
    peripheral_vision: bool = False
    night_blindness: bool = False        # turns night vision on automatically (phase 4)
    night_vision: bool = False

class Settings(BaseModel):
    model: str = "yolov8n.pt"
    device: str = "cuda:0"
    imgsz: int = 640
    conf: float = 0.35
    iou: float = 0.5
    det_fps: CameraRates = CameraRates()
    hfov_deg: float = 70                 # assumed camera field of view for distance
    hold_seconds: float = 1.0
    caution_factor: float = 1.5          # yellow = within 1.5 x alert_at
    alerts: dict[str, ObjectAlert] = {
        "vehicles":       ObjectAlert(alert_at_m=20),
        "people":         ObjectAlert(alert_at_m=6),
        "traffic_lights": ObjectAlert(alert_at_m=15),            # phase 3
        "traffic_signs":  ObjectAlert(alert_at_m=17, show_text=True),
        "speed_breakers": ObjectAlert(alert_at_m=14),
        "potholes":       ObjectAlert(alert_at_m=20),
        "sign_boards":    ObjectAlert(alert_at_m=6, announce=False, show_text=True),
    }
    vision: VisionType = VisionType()
    voice: bool = True
    volume: float = 0.8
    ar_mirror: bool = False              # windscreen view flips left-right
    jpeg_quality: float = 0.7
    stream_fps: int = 30

class Incident(BaseModel):
    id: str                              # "inc_0007"
    cause: Literal["manual", "danger_warning", "hard_brake"]
    camera: Position | None
    codes: list[str]
    started_at: datetime
    warnings_before: list[dict]          # warnings given in the 30 s before
    snapshot_path: str                   # front camera picture
    clips: dict[Position, str]           # one MP4 per camera
```

Settings are saved to `data/settings.json`. Incidents are stored in `data/incidents.db` (SQLite, one table) with files in `data/incidents/{id}/`. The presentation keeps the last 90 seconds from all four cameras. Holding that as JPEGs in RAM at 30 fps would take about 430 MB, so the recorder writes rolling 10 s MP4 segments per camera to data/buffer/ and keeps the last 9; on an incident it copies them into the incident folder.

### 3.9 Models

| Phase | Model | Classes used | Source |
| --- | --- | --- | --- |
| 1 | YOLOv8n COCO, FP32 | person (0), car (2); optional bicycle (1), motorcycle (3), bus (5), truck (7) | Ultralytics pretrained `yolov8n.pt` |
| 3 | Same model | traffic light (9), stop sign (11) | COCO |
| 3 | YOLOv8n fine-tuned | pothole | Public Roboflow / Hugging Face pothole datasets (section 7) |
| 3 | YOLOv8n fine-tuned | road signs, speed limit values | Public traffic sign datasets; local signs need a small labelled set |
| 4 | Preprocessing, no model | night vision: CLAHE on the L channel, gamma correction | OpenCV |

A second model (pothole, signs) runs only on the front camera at 5 to 10 fps, in the same inference thread, so the GPU budget stays predictable.

## 4. User interface specification

The live screen never changes shape: front in the middle, left and right as tall strips on the edges, back as a wide strip under the front view. Only the contents of the side and back slots change (black or video). This matches the mockups in the team presentation (slides 16 to 23).

### 4.1 Live view layout (landscape)

| Slot | Position on screen | Size (share of screen) | Default content | When warning active |
| --- | --- | --- | --- | --- |
| Front (F) | Centre, top | about 64% wide, 66% tall | Always live video with all boxes, warning pills and sign banners | Orange or yellow boxes, pill such as "Person ahead" |
| Back (B) | Centre, bottom, under front | about 64% wide, 34% tall | Fully black | Back video, pill "Car behind", nearest object boxed orange |
| Left (L) | Left edge, full height | about 18% wide | Fully black | Left video, pill "Car" at top |
| Right (R) | Right edge, full height | about 18% wide | Fully black | Right video, pill "Car" at top |

```text
+--------+-------------------------------------------+--------+
|        |                                           |        |
|  LEFT  |   FRONT (F) - always live video           | RIGHT  |
|  (L)   |   all boxes, warning pills, sign banners  |  (R)   |
|        |   ~72% wide, ~70% tall                    |        |
| black  |                    [AR] [Settings] on tap | black  |
| until  +-------------------------------------------+ until  |
| warning|   BACK (B) - black until a warning        | warning|
| ~13%   |   ~72% wide, ~28% tall                    | ~13%   |
+--------+-------------------------------------------+--------+
```

A warning only swaps a black slot for that camera's video; no slot ever moves or resizes.

Implementation notes:

- Use CSS grid: `grid-template-columns: 18fr 64fr 18fr; grid-template-rows: 66fr 34fr;` (changed on 2026-11-20 from 13/72/13 and 70/28 at Alishba's request: the side slots were too narrow) with left spanning both rows in column 1, front in row 1 column 2, back in row 2 column 2, right spanning both rows in column 3. Gap 1% on a near-black background (`#0d0f12`), rounded corners on every slot.
- Each slot is a `<canvas>`. The viewer decodes the JPEG (`createImageBitmap(blob)`), draws it with `object-fit: cover` maths (side slots crop the centre of a 16:9 frame), then draws the overlay boxes from the matching `overlay` message.
- A black slot still shows its small round badge (L, R or B) so the reserved place is visible. Every slot has a badge; the front badge shows a blue dot when live.
- Box styling: white 2 px for far objects, yellow 3 px for caution, orange 4 px with a soft glow for danger, blue for signs. No text on the boxes (2026-11-20): the warning pill says what and how far. Only objects on the road are boxed (the lane widened by `road_width_factor`, up to just above the horizon); buildings and things far off to the side are not shown.
- Wide, short slots (back) crop the picture around the road (between the lane's horizon and the bottom), not the centre, so they do not show only sky.
- Warning pill: orange rounded pill with a warning triangle icon and short text, top left of its slot. Sign banners (phase 3): blue for signs, red for red light, at top left of the front view.
- Tapping anywhere shows two round buttons near the bottom right of the front view: Windscreen (AR mirror) and Settings. They hide after 3 s. No camera picker, no slot swapping.
- AR mirror mode flips the whole live view left to right (`transform: scaleX(-1)` on the container) so it reads correctly when reflected on the windscreen.
- A camera that is offline shows its slot black with a small grey "offline" tag; the layout does not change.
- Voice: on each new orange warning, speak the text once with `speechSynthesis` (for example "Car on the left", "Person ahead, 5 metres"), at most one sentence every 2 s.

### 4.2 Screens (from the presentation app map)

| Screen | Phase | Purpose | Backend calls |
| --- | --- | --- | --- |
| Start | 1 | One big "Start Driving Assistant" button, server address field | `GET /api/health` |
| System check | 2 | Shows four cameras, server and speaker as OK or missing | `GET /api/status` |
| Camera not found | 2 | Says which camera is missing (also spoken), Try again | `GET /api/status` |
| Vision type setup | 2 | Pick any of peripheral vision, night blindness, night vision | `PATCH /api/settings` |
| Live view | 1 | Constant layout above | `WS /ws/viewer` |
| Tap menu | 1 | Windscreen and Settings buttons only | none |
| Windscreen (AR mirror) | 2 | Mirrored live view | none (client-side) |
| Settings | 2 | Cards: voice and audio, detection and alerts, system (with Saved incidents) | `GET/PATCH /api/settings` |
| Detection and alerts | 2 | Per object: detect, announce, alert distance (minus/plus), show text, Reset to recommended | `PATCH /api/settings` |
| System status | 2 | Cameras, server, audio, reload | `GET /api/status` |
| Incident saved notice | 2 | Short banner on the live view | WS `incident` |
| Saved incidents list | 2 | Front picture, cause, date, time; no limit | `GET /api/incidents` |
| Incident playback | 2 | Four clips together, incident mark on timeline, warnings given before | `GET /api/incidents/{id}` and clip URLs |
| Tesla view | 4 | Top-down road with own car in the middle and detected objects around it, day or night colours | `WS /ws/viewer` (`video: none`) |

### 4.3 Camera node page (phone)

A single page at `http://<laptop-ip>:8000/camera`, plain HTML and JavaScript (no build step), large touch targets:

1. Four big buttons: Front, Left, Right, Back (shows which positions are already taken, from `GET /api/status`).
2. "Choose video" button (`<input type="file" accept="video/*">`), then a preview.
3. Play / Stop button. While playing: position name, live dot, sent fps, server round-trip time.
4. Settings drawer: server address (pre-filled from the page URL), JPEG quality, fps.

The page needs no camera permission because it reads a local video file, so plain HTTP works on the LAN. Use `requestVideoFrameCallback` when available, otherwise a 33 ms timer. Keep the screen awake with the Wake Lock API, and send nothing when the tab is hidden.

## 5. Implementation plan

Build the server and the camera page first, prove the pipeline with a debug viewer, then build the React and Next.js dashboards on a shared JavaScript client library. Milestones M0 to M5 are the supervisor demo; M6 onwards are later phases.

### 5.1 Technology stack

| Layer | Choice | Why |
| --- | --- | --- |
| Server language | Python 3.12 | Already installed; Ultralytics and OpenCV are Python |
| Web framework | FastAPI + Uvicorn (`uvicorn[standard]` for fast WebSockets) | Async WebSockets and REST in one process, automatic OpenAPI docs at `/docs` |
| Detection | Ultralytics YOLOv8n (`yolov8n.pt`), PyTorch with CUDA | Pretrained COCO model covers car and person |
| Tracking | ByteTrack: Ultralytics built-in (`model.track(..., tracker="bytetrack.yaml", persist=True)`) or Roboflow `trackers` package | Proven, no training needed |
| Image handling | OpenCV (`cv2.imdecode`), NumPy | Fast JPEG decode |
| Validation | Pydantic v2 | Schemas for settings, messages, incidents |
| Storage (phase 2) | SQLite (`sqlite3` or `aiosqlite`), files | No database server to install |
| Camera node | Plain HTML + JavaScript | Opens on any phone browser, no app install |
| Shared client library | JavaScript package `@da/client` (`clients/shared`, JSDoc types) | One protocol parser for React and Next.js |
| Alishba's dashboard | React 18 + Vite, JavaScript (JSX) | Fast dev server; the team knows JavaScript, not TypeScript |
| Zain's dashboard | Next.js (App Router), JavaScript | Dashboard is a client component (`"use client"`) because it uses WebSocket and canvas |
| Later clients | Flutter (`web_socket_channel`), React Native (built-in `WebSocket`) | Same protocol |
| Tests | pytest, httpx, `websockets` client; Vitest for the JavaScript clients |  |

### 5.2 Environment setup on the laptop (Windows 11)

1. Update the NVIDIA driver (GeForce Experience or nvidia.com). Check with `nvidia-smi`.
2. Create a virtual environment: `py -3.12 -m venv .venv` then `.venv\Scripts\activate`.
3. Replace the CPU-only PyTorch. The GTX 1070 is a Pascal GPU (compute capability 6.1). PyTorch's CUDA 12.8+ wheels dropped Pascal, and PyTorch 2.14 is the last release with CUDA 12.6 wheels ([PyTorch notice](https://dev-discuss.pytorch.org/t/notice-cuda-12-6-wheels-will-no-longer-be-published-from-pytorch-2-15-drops-maxwell-pascal-volta/3432)), so install:

```
pip uninstall -y torch torchvision torchaudio
pip install torch==2.14.0 torchvision==0.29.0 --index-url https://download.pytorch.org/whl/cu126
pip install ultralytics fastapi "uvicorn[standard]" opencv-python numpy pydantic pytest httpx websockets
```

4. Verify: `python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"` must print `True NVIDIA GeForce GTX 1070 with Max-Q Design`.
5. Allow Python through Windows Firewall on private networks, and set the Wi-Fi network profile to Private, otherwise phones cannot reach port 8000.
6. Run with `uvicorn app.main:app --host 0.0.0.0 --port 8000 --ws-per-message-deflate false` (no WebSocket compression: JPEGs are already compressed, and compressing them per viewer used a whole CPU core) from `server/`. Find the laptop IP with `ipconfig` and open `http://<ip>:8000/camera` on each phone.
7. Network: prefer a 5 GHz router. Four streams at 640x360, quality 0.7, 30 fps are roughly 1 to 1.5 MB/s each, about 40 to 50 Mbit/s total (estimate; measure in M3). A phone hotspot may not sustain this; if frames drop, lower quality to 0.6 or fps to 24 from settings.
8. Plug the laptop into power and set Windows power mode to Best performance; the Max-Q GPU slows down on battery.

### 5.3 Repository layout (monorepo)

```
driving-assistant/
  README.md                    how to run everything
  CLAUDE.md                    rules for Claude Code (section 5.6)
  docs/
    design.md                  this document
    protocol.md                section 3.4 + 3.5, the contract for all clients
  server/
    requirements.txt
    app/
      main.py                  FastAPI app, startup/shutdown, mounts static camera page
      config.py                paths, defaults, loads data/settings.json
      api/
        rest.py                /api/* routes
        ws_camera.py           /ws/camera/{position}
        ws_viewer.py           /ws/viewer
      core/
        protocol.py            binary header pack/unpack, message builders
        frame_store.py         latest-frame slot per camera (thread safe)
        scheduler.py           inference thread: due cameras, batching
        detector.py            YOLO wrapper (load, warm-up, predict batch, class filter)
        tracker.py             one ByteTrack per camera
        smoother.py            box velocity + prediction (3.7)
        distance.py            pinhole distance estimate
        warnings.py            rule engine (3.6), hold time, codes and texts
        broadcaster.py         viewer registry, subscriptions, fan-out
        stats.py               fps, latency, inference time
      sources/
        file_source.py         backup mode: read video files as fake cameras
      storage/
        settings_store.py
        incidents.py           phase 2: rolling recorder + SQLite
      models/
        schemas.py             pydantic models (3.8)
      static/camera/
        index.html
        camera.js
        camera.css
    tests/
      test_protocol.py
      test_warnings.py
      test_smoother.py
      test_ws_flow.py          fake camera -> server -> fake viewer
    tools/
      fake_camera.py           send a local video over /ws/camera like a phone
      bench_detector.py        measure inference ms on the laptop GPU
    weights/yolov8n.pt
    data/                      settings.json, incidents.db, buffer/, incidents/ (git-ignored)
  clients/
    shared/                    @da/client (JavaScript): protocol, binary parser, WebSocket client with reconnect
    react-web/                 Alishba: Vite + React
    nextjs-web/                Zain: Next.js
    flutter_app/               Bilawal (later)
    rn_app/                    Bilal (later)
  videos/                      sample road videos: front.mp4, left.mp4, right.mp4, back.mp4 (git-ignored)
```

Inside both web clients use the same component split: `LiveView` (grid), `CameraSlot` (canvas + draw), `WarningPill`, `SignBanner`, `TapMenu`, `SettingsPage`, `StatusPage`, `IncidentsPage`, plus a `useDrivingAssistant()` hook that wraps `@da/client`.

### 5.4 Team roles

| Member | Owns | Also helps with |
| --- | --- | --- |
| Alishba | React dashboard (`clients/react-web`), shared TS client library | Server integration testing |
| Zain | Next.js dashboard (`clients/nextjs-web`) | Settings and incidents screens |
| Bilawal | Flutter client (later) | Camera node page testing on Android phones |
| Bilal | React Native client (later) | Warning rules tuning and test videos |
| Whole team | Server (Python) | Split by module: ingest/broadcast, detection/tracking, warnings, storage |

### 5.5 Build order for Claude Code

Each step ends with a check that must pass before the next step.

1. **M0 Skeleton.** Create the monorepo layout, `server/requirements.txt`, FastAPI app with `GET /api/health` and `GET /api/meta`, pydantic schemas, `CLAUDE.md`, `docs/protocol.md`. Check: `uvicorn` starts, `/docs` lists the routes, `pytest` runs.
2. **M1 GPU detector.** `detector.py` loads `yolov8n.pt` on `cuda:0`, warms up, predicts a batch of 1 to 4 images filtered to person and car; `tools/bench_detector.py` prints ms per image. Check: `torch.cuda.is_available()` is true and average inference is printed (expect roughly 8 to 15 ms).
3. **M2 Ingest + frame store + fake camera.** `/ws/camera/{position}` with `hello`, `ack`, binary header parsing, latest-frame slot, `replaced` logic; `tools/fake_camera.py --position front --video videos/front.mp4` streams at 30 fps. Check: `GET /api/status` shows 4 cameras online at about 30 in-fps when 4 fake cameras run.
4. **M3 Camera node page.** `static/camera/` page per section 4.3, served at `/camera`. Check: a real phone on the same Wi-Fi picks a video and the server shows it online at 25 to 30 fps.
5. **M4 Detection pipeline.** `scheduler.py` (per-camera rates, newest frame only, batching), `tracker.py`, `smoother.py`, `distance.py`, `warnings.py`, `broadcaster.py`, `/ws/viewer` with `welcome`, `subscribe`, binary frames, `overlay`, `warning_state`, `camera_status`, `stats`. Unit tests for warnings and smoother. Check: `stats` shows det\_fps close to 20/10/8/8 and a tiny HTML debug viewer at `/debug` draws boxes on all four feeds.
6. **M5 Dashboards.** `clients/shared` first (message shapes from `docs/protocol.md`, parser, reconnecting client, Vitest tests for the parser). Then `react-web` and `nextjs-web` live view with the constant layout, black slots, pills, tap menu, voice. Check: with 4 phones (or `POST /api/sources/files`) running, both dashboards show front always, and side/back slots switch from black to video only during warnings.
7. **M6 Backup mode + demo hardening.** `file_source.py` and `POST/DELETE /api/sources/files`; reconnect handling; offline tags. Check: unplug Wi-Fi on one phone, the slot shows offline and the rest keep working; backup mode runs the whole demo without phones.
8. **M7 Phase 2.** Settings (PATCH, Detection and alerts screen, vision type), system check and status screens, rolling recorder and incidents (list, playback), AR mirror.
9. **M8 Phase 3.** Traffic lights and stop signs from COCO; fine-tune YOLOv8n for potholes, speed breakers and road signs; blue banners; speed limit value.
10. **M9 Phase 4.** Night vision preprocessing (CLAHE + gamma, auto with night blindness), Tesla top-down view, Flutter and React Native clients.

For the supervisor check on Monday 2026-11-23, M0 to M4 plus the React live view (part of M5) is a realistic target; backup mode (M6) is the safety net if Wi-Fi misbehaves.

### 5.6 Rules to put in CLAUDE.md

- `docs/protocol.md` is the contract. Any change to messages updates that file, `server/app/core/protocol.py`, `clients/shared` and their tests in the same change.
- Never block the event loop: model calls only in the inference thread; JPEG decode only in that thread.
- Never queue frames: one slot per camera, newest wins.
- Never re-encode video on the server for viewers; forward the phone JPEG.
- All coordinates sent to clients are normalised 0..1.
- Every threshold is a setting, never a magic number inside rules.
- Windows first: use `pathlib`, no shell-specific scripts; provide `run_server.bat`.
- Run `pytest` and the TS tests before finishing a step.

## 6. Testing and demo plan

Testing proves three things: the pipeline keeps up (fps and latency), warnings fire at the right time, and the layout behaves exactly as the mockups. Everything can be tested on the laptop alone with `tools/fake_camera.py` before phones are involved.

### 6.1 Test levels

| Level | What | How | Pass criteria |
| --- | --- | --- | --- |
| Unit | Binary header pack/unpack | pytest + Vitest with the same byte fixtures | Round-trip identical on both sides |
| Unit | Warning rules, hold time, distance | pytest with synthetic tracks | Each rule row in 3.6 gives the expected level |
| Unit | Smoother | pytest | Predicted box moves linearly, track removed after 0.7 s |
| Integration | Camera to viewer flow | pytest starts app, fake camera sends frames, fake viewer receives frame + overlay with same seq | Under 100 ms on localhost |
| Performance | 4 cameras at 30 fps | 4 fake cameras for 5 minutes, read `stats` | In-fps >= 28 each, det-fps within 10% of 20/10/8/8, no memory growth |
| Network | 4 real phones on router, then hotspot | Same as above | In-fps >= 25 each; note results for the report |
| Accuracy | Car and person detection | Label 100 frames from your road videos (Roboflow or CVAT), run `model.val` | Report precision, recall, mAP50 |
| Warning timing | Clips with known events (car overtakes left, person crosses) | Mark the event frame by hand, compare to first warning | Warning within 0.5 s of the event |
| UI | Constant layout | Manual checklist on React and Next.js | Slots never move; black when no warning; tap shows only 2 buttons |
| Robustness | Disconnect a phone, restart server, two phones pick same position | Manual | Offline tag, auto reconnect, old phone gets `replaced` |

### 6.2 Demo script for the supervisor (about 5 minutes)

1. Start the server on the laptop (on power, best performance mode) and open the React dashboard full screen.
2. Four teammates open `http://<laptop-ip>:8000/camera`, pick front, left, right, back, choose prepared road videos and press Play.
3. Show the front view with boxes and the three black slots.
4. Point out a car overtaking on the right video: the right slot turns on with an orange "Car" pill and the voice speaks, then goes black again.
5. Show a person crossing in the front video (orange box, "Person ahead").
6. Open `/api/status` or the stats overlay to show fps per camera and latency.
7. Disconnect one phone to show the offline tag and auto reconnect.
8. Switch to backup mode (`POST /api/sources/files`) to show the same system without phones.
9. Show the Next.js dashboard connected to the same server at the same time, to prove the backend is client-agnostic.

Prepare four videos per position in advance (each 1 to 3 minutes, 16:9, with clear events) and keep them on both the phones and the laptop.

## 7. Open-source references and what to reuse

No open-source project found does exactly this (four phone browsers streaming to one YOLO server with a fixed four-slot dashboard), so the plan combines ideas from several. The most useful pieces are Ultralytics tracking, Roboflow's tracker and the JPEG-over-WebSocket pattern from Websocket CAM. Links were opened on 2026-11-19.

| Project | What it is | What to reuse or learn |
| --- | --- | --- |
| [Ultralytics YOLO track mode](https://huggingface.co/spaces/CloudAnts/mydemo1/blob/ec4f80f40901f92309e4b225624de5bdd8f14dbf/docs/en/modes/track.md) | Official docs (mirror) for `model.track()` with ByteTrack or BoT-SORT, including a multi-stream threading example | Use `persist=True` and `tracker="bytetrack.yaml"`; their example runs one model per thread, but this design uses one shared inference thread to save VRAM |
| [Roboflow Supervision trackers](https://supervision.roboflow.com/latest/trackers/) | `sv.ByteTrack` with tunable `lost_track_buffer`, `track_activation_threshold`, `frame_rate` | Alternative tracker per camera. Note: `sv.ByteTrack` is deprecated from supervision 0.28 in favour of the separate `trackers` package (`ByteTrackTracker.update()`) |
| [Websocket CAM (umercodez/websocketcam)](https://awesome.ecosyste.ms/projects/github.com%2Fumercodez%2Fwebsocketcam) | Android app that streams phone camera frames as binary JPEG over WebSocket to Python clients | Same idea as our camera node: binary JPEG per WebSocket message, decoded with OpenCV. Our version is a browser page instead of an app, and the phone is the client, not the server |
| [Mobile as Webcam (moshfeu)](https://awesome.ecosyste.ms/projects/github.com%2Fmoshfeu%2Fmobile-as-webcam) | Node.js project using WebSocket and WebRTC to use a phone camera on a LAN | Shows that live camera access needs HTTPS (it ships cert.pem); our design avoids this because phones play a local video file |
| [HomeVision (suinaowawa)](https://github.com/suinaowawa/homevision) | FastAPI + aiohttp + aiortc (WebRTC) framework running YOLOv8 on several RTSP cameras, with a video-file demo script | Structure for multi-source FastAPI + YOLO; WebRTC is a possible later upgrade if WebSocket JPEG latency is too high. Very small project (3 stars), use as reference only |
| [OpenADAS (vietanhdev/open-adas)](https://awesome.ecosyste.ms/projects/github.com%2Fvietanhdev%2Fopen-adas) | C++/Qt ADAS on Jetson Nano, MIT licence, about 445 stars: forward collision, lane departure, traffic sign, overspeed warnings | Feature ideas and warning UX for phases 3 and 4 (signs, speed limit). Not reusable code for a Python server |
| [Copilot (visualbuffer/copilot)](https://github.com/visualbuffer/copilot) | Python, MIT licence: YOLO obstacle tracking, time to collision, lane detection, top view | Time-to-collision and relative velocity ideas for the "approaching" rule; top view idea for the Tesla view |
| [Driver Assistant System (SnPreethi)](https://github.com/SnPreethi/Driver_Assistant_System) | YOLOv8 + Ultrafast Lane Detector v2 on Jetson Orin Nano, collision and lane warnings, drowsiness | Similar student project; good for the literature review and for lane detection later |
| [people-tracking-cv (yilverdeja)](https://github.com/yilverdeja/people-tracking-cv) | Next.js + TypeScript app drawing detection boxes on a canvas over video | Canvas overlay pattern for the React and Next.js `CameraSlot`; it notes aspect-ratio bugs on mobile, which our normalised coordinates avoid |
| [Pothole detection YOLOv8 (mounishvatti)](https://github.com/mounishvatti/pothole_detection_yolov8) | MIT notebooks training YOLOv8 on a Roboflow pothole dataset | Training recipe for phase 3 pothole model (no weights included) |
| [Pothole YOLOv8 weights (Hugging Face)](https://huggingface.co/ZiaPratama/Yolov8_Pothole) | Pretrained pothole model | Quick phase 3 prototype before training your own; check its licence |
| [Roboflow Universe pothole dataset](https://universe.roboflow.com/yoloteam/potholedetectionyolov8-11c1w/dataset/1) | Labelled pothole images in YOLOv8 format | Training data for phase 3 |
| [PyTorch CUDA 12.6 notice](https://dev-discuss.pytorch.org/t/notice-cuda-12-6-wheels-will-no-longer-be-published-from-pytorch-2-15-drops-maxwell-pascal-volta/3432) | Pascal GPUs (GTX 10-series) are dropped after PyTorch 2.14 | Pin torch 2.14.0 + cu126 on the GTX 1070 |

**Takeaways for the design.** Keep one inference thread and batch frames (Ultralytics' per-thread example would load four models). Send JPEG bytes over WebSocket rather than base64 JSON (Websocket CAM). Draw boxes on the client from normalised coordinates (people-tracking-cv's mobile bug). Use distance and time-to-collision ideas from Copilot and OpenADAS for warnings.
