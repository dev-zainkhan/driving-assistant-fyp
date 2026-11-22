# Driving Assistant protocol v1 (the contract for every client)

Copied from DESIGN.md sections 3.4 and 3.5. If a message format changes, update this file,
`server/app/core/protocol.py`, `clients/shared` and their tests in the same change.

Byte fixtures used by both the Python and the JavaScript tests:

| Case | Hex |
| --- | --- |
| Camera frame: seq 42, capture_ts 1763540000000.0, jpeg `ffd8ffd9` | `01012a0000000000d0cdb2a979420000ffd8ffd9` |
| Viewer frame: camera right (2), seq 7, capture 1000.25, server 1001.5, payload `JPEG` | `01010200070000000000000000428f4000000000004c8f404a504547` |

Notes added during implementation:

- `GET /api/health` also returns `"detector": "ready" | "loading" | "disabled" | "error" | "stalled"` and `"protocol": 1`. `stalled` = the inference loop has not run for 5 s.
- `GET /api/meta` also returns `"levels"` and `"server_version"`.
- `GET /api/status` returns `{"cameras": {"front": {"status": "online", "in_fps": 29.7, "det_fps": 19.8, "latency_ms": 140, "infer_ms": 11.2, "source": "phone" | "file", "video_name": "..."}, ...}, "gpu": "cuda:0"}`. All four positions are always present.
- Settings has extra tuning fields (zones, real heights, smoother and approach values) so no threshold is hard-coded.
- `settings.zones["<camera>_<people|vehicles>"]` is `{x_min, x_max, y_min, y_max, polygon}`. When `polygon` (a list of `[x, y]` corners, normalised) is set, an object is in the zone when its bottom-centre point is inside the polygon. Front and back use a lane trapezoid (wide at the bottom of the frame, narrow at the horizon) so cars parked at the roadside do not warn. Left and right use the y band (lower 70%).
- Left and right cameras warn only after an object has been in view for `side_min_track_s` (default 0.8 s). A parked car passes a side camera in well under a second while we drive; an overtaking car stays longer.
- Extra REST routes for backup mode: `GET /api/sources/videos` returns `{"folder": "videos", "videos": [{"path": "videos/test/front.mp4", "name": "front.mp4", "size_mb": 7.2}]}` (paths can be passed to `POST /api/sources/files`); `GET /api/sources/files` returns `{"running": {"front": "front.mp4"}}`. `DELETE /api/sources/files` also returns `"positions"` (the ones stopped).
- `GET /` redirects to `/app/` (the built React dashboard, served by the server when `clients/react-web/dist` exists), otherwise to `/docs`.
- Voice settings for viewers: `voice_gap_s` (min seconds between two sentences, default 4) and `voice_repeat_s` (the same warning code is not spoken again within this time, default 15). Viewers never cut a sentence off; a warning that arrives while speaking is skipped, not queued.
- In `overlay`, `distance_m` may be `null` when the box is too small to estimate.
- `stats.latency_ms` is measured on the server only: frame received → detection result ready. Phone and laptop clocks are not synced, so `capture_ts_ms` is not used for latency.
- Camera nodes may send `{"type": "ping", "t": <number>}`; the server answers `{"type": "pong", "t": <same>, "server_time_ms": ...}` so the phone can show round-trip time.
- `warning_state` text examples: front `"Person ahead, 5 m"`, side `"Car on left"`, back `"Car behind"`. Narrow side slots may show only the object name.
- `stats` also has `"detector"` (same values as in `/api/health`) and `"errors"` (inference steps that failed and were skipped; detection keeps running), and every camera entry has `status`, `source` and `video_name`.

## 1. Message formats (WebSocket protocol v1)

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

`incident` (sent when an incident is saved; today only by the demo route): `{"type": "incident", "id": 7, "cause": "sudden_brake", "camera": null, "codes": [], "ts": 1763540001100}`.

## 2. REST API (JSON, base `http://<laptop-ip>:8000`)

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

## 3. Settings and incidents (Phase 2, database in `docs/database.md`)

Settings are stored in SQLite on the laptop. Every client sees the same values.

| Method | Path | Body | Response |
| --- | --- | --- | --- |
| GET | `/api/settings` | | `Settings` |
| PATCH | `/api/settings` | Part of `Settings`, nested, e.g. `{"volume": 0.6}` or `{"alerts": {"people": {"alert_at_m": 8}}}` | the full new `Settings` |
| POST | `/api/settings/alerts/reset` | | `Settings` after "Reset to recommended" (slide 35) |
| GET | `/api/settings/advanced` | | `[{"name", "group", "title", "value", "default", "min", "max", "step", "unit", "description"}]` fine-tuning numbers; PATCH refuses values outside min..max |
| GET | `/api/incidents?limit=100` | | `{"count": 3, "incidents": [Incident]}` newest first, `warnings` left empty |
| GET | `/api/incidents/{id}` | | `Incident` with `warnings` |
| DELETE | `/api/incidents/{id}` | | `204`, also deletes its videos folder |
| GET | `/api/database` | | `{"file": "driving_assistant.db", "tables": {"object_settings": 7, ...}}` rows per table |
| GET | `/api/incidents/{id}/video/{camera}` | | the camera's video file (WebM VP8, plays in browsers) |
| GET | `/api/incidents/{id}/picture` | | front picture (JPEG) for the incident list |
| POST | `/api/incidents` | `{"cause": "saved_by_driver"}` | `202 {"saving": true}`: saves the last `record_seconds` of every camera; an `incident` message follows when the videos are written. `409 NOT_SAVED` if nothing is recorded yet or one was saved within `incident_cooldown_s` |
| POST | `/api/settings/advanced/reset` | | `Settings` with every fine-tuning number back to its default |
| POST | `/api/incidents/sample` | `{"cause": "sudden_brake"}` | DEMO ONLY: saves a sample incident from `videos/test/*.webm` and sends the `incident` message |

PATCH errors (status 400): `UNKNOWN_SETTING`, `UNKNOWN_OBJECT`, `NOT_EDITABLE` (`model`, `device`), `INVALID_SETTING` (e.g. volume above 1, or an alert distance outside `min_m`..`max_m`).

After every successful change the server sends all viewers:

```json
{"type": "settings", "settings": {"...": "same object as GET /api/settings"}}
```

New `Settings` fields (slides 34 and 35):

| Field | Default | Meaning |
| --- | --- | --- |
| `volume` | 0.85 | Voice volume 0..1 (the database stores 0..100) |
| `speech_speed` | 1.0 | Speech rate, 0.5..2.0 |
| `beep` | true | Short beep before a spoken orange warning |
| `camera_on.{camera}` | true | false = no detection on that camera |
| `alerts.{object}.title` | "Vehicles" | Name shown on screen |
| `alerts.{object}.is_safety` | true for vehicles, people, traffic lights | "Safety" badge |
| `alerts.{object}.recommended_m` | | Value restored by "Reset to recommended" |
| `alerts.{object}.min_m`, `max_m` | | Limits for the minus and plus buttons |
| `alerts.{object}.phase` | 1 or 3 | 3 = not detected yet (signs, potholes...) |

`Incident`:

```json
{"id": 7, "cause": "sudden_brake", "happened_at": "2026-10-14T18:42:00", "length_s": 90,
 "front_picture": "7/front.jpg",
 "videos": {"front": "7/front.mp4", "left": "7/left.mp4", "right": "7/right.mp4", "back": "7/back.mp4"},
 "warnings": [{"camera": "front", "time_in_video_s": 85, "message": "Person crossing", "distance_m": 6, "colour": "orange", "was_spoken": true}]}
```

`cause` is `sudden_brake`, `hard_jolt` or `saved_by_driver` (slide 46). This replaces the earlier `manual` / `danger_warning` / `hard_brake` in DESIGN.md 3.8. Saving incidents (the rolling 90 s recorder) is not built yet; the tables and these routes are. Videos are WebM (VP8) because browsers cannot play OpenCV's default MPEG-4 (`mp4v`).

New setting: `peripheral_side_factor` (1.5). With the vision type "peripheral vision" the left and right cameras warn this many times earlier, and the scheduler checks the side cameras first.

## 4. Transport notes

- Run the server with WebSocket compression off (`--ws-per-message-deflate false`, already in `run_server.bat` and `run_demo.bat`). JPEG frames do not get smaller, and compressing them for every viewer used a whole CPU core: viewers got about 17 fps instead of 30 with 4 cameras.
- Camera pages close their WebSocket when the phone screen turns off or the page is hidden, so viewers see the camera as offline instead of a frozen picture, and reconnect as soon as the page is visible again.

## 5. Warning rule details (changed after testing on a real dashcam video, 2026-11-20)

- Approach speed is the slope of a straight line fitted through the distances of the last `approach_window_s` (now 1.0 s, at least 4 points). Using only the first and last point turned box-size noise into fake "approaching fast" warnings.
- Once a warning code is orange it stays orange for `hold_seconds` after its last orange detection, so the colour does not flicker between orange and yellow.
- Lane zones are set per camera in the dashboard (Settings > Lane setup) and saved with `PATCH /api/settings` as `zones.<camera>_vehicles.polygon` and `zones.<camera>_people.polygon`. The default lane assumes the horizon at 45% of the picture height; a phone tilted down needs it lower.
- Backup mode fits frames into the stream size with black bars (never stretched) and keeps a small cached copy of HD videos in `server/data/video_cache/`.

### Closing-speed rule for vehicles ahead and behind (2026-11-20)

Front and back cameras, vehicles only (people still use distance alone). A car must cover at least `path_min_overlap` (0.3) of our path, the middle `path_width` (0.6) of the lane, measured against the narrower of the car and the path; beside our path it is at most yellow. In our path it is orange when:

- closer than `vehicle_close_m` (7 m), or
- within the object's alert distance (vehicles 20 m) and coming closer at `closing_speed_mps` (2 m/s) or faster, or
- it would reach us in under `ttc_danger_s` (3 s), within `approach_max_m` (20 m).

Otherwise yellow within `caution_factor` x alert distance (30 m). Only tracks seen in the current detection round can keep a warning alive. Measured on a 60 s city dashcam clip: orange went from 84% of the time to 38%, yellow from 9% to 46%.

## 6. Incident recorder (2026-11-20)

The server always keeps the last `record_seconds` (90) of every camera at `record_fps` (10), as references to the phones' JPEGs (about 150 MB for 4 cameras). `POST /api/incidents` (the dashboard sends it on a 1-second long-press or the `S` key, cause `saved_by_driver`) snapshots that buffer and a background thread writes one WebM (VP8) per camera, the front picture (the phone's own JPEG) and the warnings that started in that time (`time_in_video_s`, message, distance, orange or yellow, orange counted as spoken). Writing uses one thread per camera; a 90 s incident took about 70 s with four HD backup videos running. This thread decodes the saved JPEGs to write video: the only JPEG decoding outside the inference thread, and only while an incident is being saved. Sudden-brake and hard-jolt detection are not built yet.
