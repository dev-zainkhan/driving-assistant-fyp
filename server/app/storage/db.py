"""SQLite database: settings and saved incidents (docs/database.md).

One file on the laptop, next to the server. Only the server uses it; the apps go through the
REST API. Table and column names are the simple names from docs/database.md; the rest of the
server keeps using the `Settings` model, and this module converts between the two.

Each call opens its own short connection, so it is safe from any thread. Writes are rare
(only when someone changes a setting or an incident is saved), so this is fast enough.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from app.core.protocol import COCO_IDS, POSITIONS, VEHICLE_CLASSES
from app.models.schemas import Incident, IncidentWarning, Settings, Zone

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);

-- Slide 34, Voice and audio. Always exactly one row (id = 1).
CREATE TABLE IF NOT EXISTS general_settings (
    id           INTEGER PRIMARY KEY CHECK (id = 1),
    voice_on     INTEGER NOT NULL CHECK (voice_on IN (0, 1)),
    beep_on      INTEGER NOT NULL CHECK (beep_on IN (0, 1)),
    voice_volume INTEGER NOT NULL CHECK (voice_volume BETWEEN 0 AND 100),
    speech_speed REAL    NOT NULL CHECK (speech_speed BETWEEN 0.5 AND 2.0),
    mirror_on    INTEGER NOT NULL CHECK (mirror_on IN (0, 1)),
    updated_at   TEXT    NOT NULL
);

-- Slides 6-13 and 36-43, Vision type.
CREATE TABLE IF NOT EXISTS vision_types (
    name        TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    description TEXT NOT NULL,
    is_chosen   INTEGER NOT NULL CHECK (is_chosen IN (0, 1))
);

-- Slide 35, Detection and alerts. One row per object.
CREATE TABLE IF NOT EXISTS object_settings (
    name                   TEXT PRIMARY KEY,
    title                  TEXT NOT NULL,
    is_safety              INTEGER NOT NULL CHECK (is_safety IN (0, 1)),
    detect                 INTEGER NOT NULL CHECK (detect IN (0, 1)),
    announce               INTEGER NOT NULL CHECK (announce IN (0, 1)),
    alert_distance_m       REAL NOT NULL,
    recommended_distance_m REAL NOT NULL,
    min_distance_m         REAL NOT NULL,
    max_distance_m         REAL NOT NULL,
    show_text              INTEGER NOT NULL CHECK (show_text IN (0, 1)),
    phase                  INTEGER NOT NULL,
    CHECK (min_distance_m > 0 AND min_distance_m <= alert_distance_m AND alert_distance_m <= max_distance_m)
);

-- What YOLO detects -> which row of object_settings, and its usual height (for distance).
CREATE TABLE IF NOT EXISTS yolo_classes (
    name           TEXT PRIMARY KEY,
    object         TEXT NOT NULL REFERENCES object_settings(name),
    yolo_id        INTEGER NOT NULL UNIQUE,
    usual_height_m REAL NOT NULL CHECK (usual_height_m > 0)
);

-- Slide 44, the four cameras.
CREATE TABLE IF NOT EXISTS cameras (
    name              TEXT PRIMARY KEY CHECK (name IN ('front', 'left', 'right', 'back')),
    checks_per_second REAL NOT NULL CHECK (checks_per_second >= 0),
    is_on             INTEGER NOT NULL CHECK (is_on IN (0, 1))
);

-- Where in the picture something counts as a danger (e.g. our own lane). corners = [[x, y], ...]
CREATE TABLE IF NOT EXISTS warning_areas (
    id      INTEGER PRIMARY KEY,
    camera  TEXT NOT NULL REFERENCES cameras(name),
    object  TEXT NOT NULL REFERENCES object_settings(name),
    corners TEXT NOT NULL,
    UNIQUE (camera, object)
);

-- Fine-tuning numbers for the team, one per row.
CREATE TABLE IF NOT EXISTS advanced_settings (
    name        TEXT PRIMARY KEY,
    value       REAL NOT NULL,
    unit        TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT ''
);

-- Slides 45-47, saved incidents.
CREATE TABLE IF NOT EXISTS incidents (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    cause         TEXT NOT NULL CHECK (cause IN ('sudden_brake', 'hard_jolt', 'saved_by_driver')),
    happened_at   TEXT NOT NULL,
    length_s      INTEGER NOT NULL DEFAULT 90,
    front_picture TEXT
);

CREATE TABLE IF NOT EXISTS incident_videos (
    id         INTEGER PRIMARY KEY,
    incident   INTEGER NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    camera     TEXT NOT NULL REFERENCES cameras(name),
    video_file TEXT NOT NULL,
    UNIQUE (incident, camera)
);

CREATE TABLE IF NOT EXISTS incident_warnings (
    id              INTEGER PRIMARY KEY,
    incident        INTEGER NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    camera          TEXT NOT NULL REFERENCES cameras(name),
    time_in_video_s INTEGER NOT NULL,
    message         TEXT NOT NULL,
    distance_m      INTEGER,
    colour          TEXT NOT NULL CHECK (colour IN ('orange', 'yellow')),
    was_spoken      INTEGER NOT NULL DEFAULT 0 CHECK (was_spoken IN (0, 1))
);
"""

VISION_TYPES = {
    "peripheral_vision": ("Peripheral vision", "Hard to see things at the sides"),
    "night_blindness": ("Night blindness", "Hard to see in low light or at night"),
    "night_vision": ("Night vision", "Use the night camera view all the time"),
}

# Settings field -> (unit, description). These go to the advanced_settings table.
ADVANCED: dict[str, tuple[str, str]] = {
    "conf": ("", "Minimum confidence (0 to 1) for YOLO to count a detection"),
    "iou": ("", "Overlap above which YOLO merges two boxes"),
    "imgsz": ("px", "Image size given to YOLO"),
    "include_other_vehicles": ("yes/no", "Also treat bus, truck, motorcycle and bicycle as vehicles"),
    "hfov_deg": ("deg", "Assumed camera field of view, used to guess distance"),
    "hold_seconds": ("s", "A warning stays on this long after the object is gone (stops flicker)"),
    "caution_factor": ("x", "Yellow when closer than this many times the alert distance"),
    "confirm_detections": ("checks", "An object must be seen this many times in a row before it warns"),
    "side_min_track_s": ("s", "Left/right cameras: object must be in view this long (ignores parked cars)"),
    "peripheral_side_factor": ("x", "With peripheral vision, side cameras warn this many times earlier"),
    "road_width_factor": ("x", "Road area shown = own lane this many times wider; things outside are hidden"),
    "road_above_horizon": ("", "Road area reaches this far above the horizon (0 to 1 of picture height)"),
    "vehicle_close_m": ("m", "A car ahead or behind closer than this is orange, even if it is not coming closer"),
    "closing_speed_mps": ("m/s", "Within the alert distance, a car is orange only if it comes closer at least this fast"),
    "ttc_danger_s": ("s", "Orange if a car would reach us in less than this (time to collision)"),
    "path_width": ("", "Middle share of the lane our car drives in"),
    "path_min_overlap": ("", "A car ahead or behind must cover at least this share of our path to be orange"),
    "approach_max_m": ("m", "The time-to-collision rule only applies closer than this"),
    "approach_window_s": ("s", "Time window used to measure approach speed"),
    "track_low_conf": ("", "Low-confidence detections down to this still keep a track alive"),
    "track_iou": ("", "Minimum overlap to match a detection to an existing track"),
    "min_box_height_px": ("px", "Boxes smaller than this get no distance"),
    "smoother_alpha": ("", "How quickly box movement prediction reacts (0 to 1)"),
    "smoother_max_predict_s": ("s", "Boxes are moved forward at most this far between detections"),
    "smoother_drop_s": ("s", "A track not seen for this long is removed"),
    "voice_gap_s": ("s", "At least this long between two spoken warnings"),
    "voice_repeat_s": ("s", "The same warning is not spoken again within this time"),
    "record_seconds": ("s", "Incidents save this many seconds from every camera"),
    "record_fps": ("fps", "Frames per second kept for incident videos"),
    "incident_cooldown_s": ("s", "A second incident within this time is not saved"),
    "jpeg_quality": ("", "JPEG quality the phones send (0 to 1)"),
    "stream_fps": ("fps", "Frames per second the phones send"),
    "stream_width": ("px", "Width of the frames the phones send"),
    "stream_height": ("px", "Height of the frames the phones send"),
}

# How the Advanced settings screen shows each number: group, short title, min, max, step.
# The same ranges are checked by PATCH /api/settings.
ADVANCED_UI: dict[str, tuple[str, str, float, float, float]] = {
    "vehicle_close_m": ("Cars ahead and behind", "Very close", 2, 20, 0.5),
    "closing_speed_mps": ("Cars ahead and behind", "Coming-closer speed", 0.5, 10, 0.5),
    "ttc_danger_s": ("Cars ahead and behind", "Time to collision", 1, 8, 0.5),
    "approach_max_m": ("Cars ahead and behind", "Time-to-collision range", 5, 50, 1),
    "approach_window_s": ("Cars ahead and behind", "Speed measuring window", 0.3, 3, 0.1),
    "path_width": ("Cars ahead and behind", "Our path width (share of lane)", 0.2, 1, 0.05),
    "path_min_overlap": ("Cars ahead and behind", "Must cover our path at least", 0.05, 1, 0.05),
    "hold_seconds": ("Warnings", "Hold time", 0, 5, 0.1),
    "caution_factor": ("Warnings", "Yellow zone (x alert distance)", 1, 3, 0.1),
    "confirm_detections": ("Warnings", "Seen in a row before warning", 1, 10, 1),
    "side_min_track_s": ("Warnings", "Side cameras: time in view", 0, 5, 0.1),
    "peripheral_side_factor": ("Warnings", "Peripheral vision: earlier on sides", 1, 3, 0.1),
    "road_width_factor": ("Road area", "Road area width (x lane)", 1, 4, 0.1),
    "road_above_horizon": ("Road area", "Road area above horizon", 0, 0.3, 0.01),
    "conf": ("Detection", "Minimum confidence", 0.05, 0.95, 0.05),
    "iou": ("Detection", "Box overlap merge", 0.1, 0.95, 0.05),
    "imgsz": ("Detection", "YOLO image size", 320, 1280, 32),
    "include_other_vehicles": ("Detection", "Bus, truck, bike count as vehicles", 0, 1, 1),
    "hfov_deg": ("Detection", "Camera field of view", 40, 120, 1),
    "min_box_height_px": ("Detection", "Smallest box with a distance", 1, 50, 1),
    "track_low_conf": ("Tracking", "Low confidence that keeps a track", 0.05, 0.9, 0.05),
    "track_iou": ("Tracking", "Overlap to match a track", 0.05, 0.9, 0.05),
    "smoother_alpha": ("Tracking", "Movement prediction speed", 0.05, 1, 0.05),
    "smoother_max_predict_s": ("Tracking", "Predict boxes up to", 0, 1, 0.05),
    "smoother_drop_s": ("Tracking", "Forget a track after", 0.2, 5, 0.1),
    "record_seconds": ("Incidents", "Seconds saved per incident", 10, 120, 5),
    "record_fps": ("Incidents", "Frames per second in incident videos", 2, 30, 1),
    "incident_cooldown_s": ("Incidents", "Ignore another save for", 0, 120, 1),
    "voice_gap_s": ("Voice", "Gap between spoken warnings", 0, 15, 0.5),
    "voice_repeat_s": ("Voice", "Do not repeat the same warning for", 0, 120, 1),
    "jpeg_quality": ("Phone stream", "JPEG quality", 0.3, 0.95, 0.05),
    "stream_fps": ("Phone stream", "Frames per second", 5, 30, 1),
    "stream_width": ("Phone stream", "Frame width", 320, 1280, 16),
    "stream_height": ("Phone stream", "Frame height", 180, 720, 9),
}

DEFAULT_DB = Path(__file__).resolve().parents[2] / "data" / "driving_assistant.db"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def zone_to_corners(z: Zone) -> list[list[float]]:
    if z.polygon:
        return [[x, y] for x, y in z.polygon]
    return [[z.x_min, z.y_min], [z.x_max, z.y_min], [z.x_max, z.y_max], [z.x_min, z.y_max]]


def object_of_class(cls: str) -> str:
    return "vehicles" if cls in VEHICLE_CLASSES else "people"


class Database:
    def __init__(self, path: Path | str = DEFAULT_DB) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    # ---------------- connection ----------------
    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        with closing(sqlite3.connect(self.path, timeout=5)) as con:
            con.row_factory = sqlite3.Row
            con.execute("PRAGMA foreign_keys = ON")
            with con:  # one transaction: commit on success, roll back on error
                yield con

    def init(self, defaults: Settings | None = None) -> None:
        """Create the tables and fill in any missing rows with the recommended values.

        Safe to run on every start: rows that already exist are never overwritten.
        """
        d = defaults or Settings()
        with self.connect() as con:
            con.execute("PRAGMA journal_mode = WAL")
            con.executescript(SCHEMA)
            if con.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0] == 0:
                con.execute("INSERT INTO schema_version VALUES (?)", (SCHEMA_VERSION,))
            self._write(con, d, overwrite=False)

    # ---------------- settings: Settings -> rows ----------------
    def _write(self, con: sqlite3.Connection, s: Settings, overwrite: bool) -> None:
        verb = "INSERT OR REPLACE" if overwrite else "INSERT OR IGNORE"
        con.execute(
            f"{verb} INTO general_settings VALUES (1, ?, ?, ?, ?, ?, ?)",
            (int(s.voice), int(s.beep), round(s.volume * 100), s.speech_speed, int(s.ar_mirror), _now()),
        )
        for name, (title, desc) in VISION_TYPES.items():
            con.execute(f"{verb} INTO vision_types VALUES (?, ?, ?, ?)", (name, title, desc, int(getattr(s.vision, name))))
        for name, a in s.alerts.items():
            con.execute(
                f"{verb} INTO object_settings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (name, a.title or name, int(a.is_safety), int(a.detect), int(a.announce), a.alert_at_m,
                 a.recommended_m, a.min_m, a.max_m, int(a.show_text), a.phase),
            )
        for cls, h in s.real_heights_m.items():
            if cls in COCO_IDS:
                con.execute(f"{verb} INTO yolo_classes VALUES (?, ?, ?, ?)", (cls, object_of_class(cls), COCO_IDS[cls], h))
        for cam in POSITIONS:
            con.execute(
                f"{verb} INTO cameras VALUES (?, ?, ?)",
                (cam, getattr(s.det_fps, cam), int(s.camera_on.get(cam, True))),
            )
        for key, z in s.zones.items():
            cam, obj = key.split("_", 1)
            corners = json.dumps(zone_to_corners(z))
            if overwrite:
                con.execute(
                    "INSERT INTO warning_areas (camera, object, corners) VALUES (?, ?, ?) "
                    "ON CONFLICT (camera, object) DO UPDATE SET corners = excluded.corners",
                    (cam, obj, corners),
                )
            else:
                con.execute("INSERT OR IGNORE INTO warning_areas (camera, object, corners) VALUES (?, ?, ?)", (cam, obj, corners))
        for field, (unit, desc) in ADVANCED.items():
            value = float(getattr(s, field))
            if overwrite:
                con.execute(
                    "INSERT INTO advanced_settings VALUES (?, ?, ?, ?) "
                    "ON CONFLICT (name) DO UPDATE SET value = excluded.value",
                    (field, value, unit, desc),
                )
            else:
                con.execute("INSERT OR IGNORE INTO advanced_settings VALUES (?, ?, ?, ?)", (field, value, unit, desc))

    def save_settings(self, s: Settings) -> None:
        with self.connect() as con:
            self._write(con, s, overwrite=True)

    # ---------------- settings: rows -> Settings ----------------
    def load_settings(self, base: Settings | None = None) -> Settings:
        """Build a Settings object from the tables. Values not stored (model, device) come from `base`."""
        data: dict[str, Any] = (base or Settings()).model_dump()
        with self.connect() as con:
            g = con.execute("SELECT * FROM general_settings WHERE id = 1").fetchone()
            if g:
                data.update(voice=bool(g["voice_on"]), beep=bool(g["beep_on"]), volume=g["voice_volume"] / 100,
                            speech_speed=g["speech_speed"], ar_mirror=bool(g["mirror_on"]))
            for r in con.execute("SELECT * FROM vision_types"):
                data["vision"][r["name"]] = bool(r["is_chosen"])
            alerts = {}
            for r in con.execute("SELECT * FROM object_settings"):
                alerts[r["name"]] = {
                    "title": r["title"], "is_safety": bool(r["is_safety"]), "detect": bool(r["detect"]),
                    "announce": bool(r["announce"]), "alert_at_m": r["alert_distance_m"],
                    "recommended_m": r["recommended_distance_m"], "min_m": r["min_distance_m"],
                    "max_m": r["max_distance_m"], "show_text": bool(r["show_text"]), "phase": r["phase"],
                }
            if alerts:
                data["alerts"] = alerts
            heights = {r["name"]: r["usual_height_m"] for r in con.execute("SELECT * FROM yolo_classes")}
            if heights:
                data["real_heights_m"] = heights
            for r in con.execute("SELECT * FROM cameras"):
                data["det_fps"][r["name"]] = r["checks_per_second"]
                data["camera_on"][r["name"]] = bool(r["is_on"])
            zones = {}
            for r in con.execute("SELECT * FROM warning_areas"):
                zones[f"{r['camera']}_{r['object']}"] = {"polygon": json.loads(r["corners"])}
            if zones:
                data["zones"] = zones
            fields = Settings.model_fields
            for r in con.execute("SELECT name, value FROM advanced_settings"):
                f = fields.get(r["name"])
                if f is None:
                    continue  # old row for a setting that no longer exists
                typ = f.annotation
                v = r["value"]
                data[r["name"]] = bool(v) if typ is bool else int(v) if typ is int else v
        return Settings.model_validate(data)

    def reset_alerts(self) -> None:
        """'Reset to recommended' (slide 35)."""
        with self.connect() as con:
            con.execute("UPDATE object_settings SET alert_distance_m = recommended_distance_m")

    # ---------------- incidents ----------------
    def add_incident(self, cause: str, happened_at: datetime, length_s: int = 90, front_picture: str | None = None,
                     videos: dict[str, str] | None = None, warnings: list[IncidentWarning] | None = None) -> int:
        with self.connect() as con:
            cur = con.execute(
                "INSERT INTO incidents (cause, happened_at, length_s, front_picture) VALUES (?, ?, ?, ?)",
                (cause, happened_at.isoformat(timespec="seconds"), length_s, front_picture),
            )
            iid = int(cur.lastrowid)
            for cam, path in (videos or {}).items():
                con.execute("INSERT INTO incident_videos (incident, camera, video_file) VALUES (?, ?, ?)", (iid, cam, path))
            for w in warnings or []:
                con.execute(
                    "INSERT INTO incident_warnings (incident, camera, time_in_video_s, message, distance_m, colour, was_spoken) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (iid, w.camera, w.time_in_video_s, w.message, w.distance_m, w.colour, int(w.was_spoken)),
                )
        return iid

    def _incident(self, con: sqlite3.Connection, row: sqlite3.Row, full: bool) -> Incident:
        videos = {r["camera"]: r["video_file"] for r in con.execute(
            "SELECT camera, video_file FROM incident_videos WHERE incident = ?", (row["id"],))}
        warnings = []
        if full:
            warnings = [
                IncidentWarning(camera=r["camera"], time_in_video_s=r["time_in_video_s"], message=r["message"],
                                distance_m=r["distance_m"], colour=r["colour"], was_spoken=bool(r["was_spoken"]))
                for r in con.execute("SELECT * FROM incident_warnings WHERE incident = ? ORDER BY time_in_video_s", (row["id"],))
            ]
        return Incident(id=row["id"], cause=row["cause"], happened_at=datetime.fromisoformat(row["happened_at"]),
                        length_s=row["length_s"], front_picture=row["front_picture"], videos=videos, warnings=warnings)

    def list_incidents(self, limit: int = 100) -> list[Incident]:
        with self.connect() as con:
            rows = con.execute("SELECT * FROM incidents ORDER BY happened_at DESC, id DESC LIMIT ?", (limit,)).fetchall()
            return [self._incident(con, r, full=False) for r in rows]

    def count_incidents(self) -> int:
        with self.connect() as con:
            return con.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]

    def get_incident(self, iid: int) -> Incident | None:
        with self.connect() as con:
            row = con.execute("SELECT * FROM incidents WHERE id = ?", (iid,)).fetchone()
            return self._incident(con, row, full=True) if row else None

    def delete_incident(self, iid: int, files_root: Path | None = None) -> bool:
        """Delete the incident, its video and warning rows (cascade) and its folder."""
        with self.connect() as con:
            n = con.execute("DELETE FROM incidents WHERE id = ?", (iid,)).rowcount
        if n and files_root is not None:
            shutil.rmtree(files_root / str(iid), ignore_errors=True)
        return bool(n)

    # ---------------- for reports and debugging ----------------
    def table_counts(self) -> dict[str, int]:
        with self.connect() as con:
            names = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")]
            return {n: con.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0] for n in names}
