"""WebSocket protocol v1 (docs/protocol.md is the contract).

Binary headers are little-endian. Camera index: 0 front, 1 left, 2 right, 3 back.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

PROTOCOL_VERSION = 1
SERVER_VERSION = "0.1.0"

MSG_FRAME = 1

POSITIONS = ("front", "left", "right", "back")
POSITION_INDEX = {p: i for i, p in enumerate(POSITIONS)}

# Classes reported to clients in phase 1.
CLASSES = ("person", "car", "bus", "truck", "motorcycle", "bicycle")
# COCO ids for the classes above.
COCO_IDS = {"person": 0, "bicycle": 1, "car": 2, "motorcycle": 3, "bus": 5, "truck": 7}
VEHICLE_CLASSES = frozenset({"car", "bus", "truck", "motorcycle", "bicycle"})

WARNING_CODES = {
    "PERSON_AHEAD": "Person ahead",
    "VEHICLE_AHEAD": "Car ahead",
    "PERSON_LEFT": "Person on left",
    "VEHICLE_LEFT": "Car on left",
    "PERSON_RIGHT": "Person on right",
    "VEHICLE_RIGHT": "Car on right",
    "PERSON_BEHIND": "Person behind",
    "VEHICLE_BEHIND": "Car behind",
}

# Camera -> server frame header: version u8, msg_type u8, seq u32, capture_ts f64, reserved u16
CAMERA_HEADER = struct.Struct("<BBIdH")
CAMERA_HEADER_SIZE = CAMERA_HEADER.size  # 16
# Server -> viewer frame header: version u8, msg_type u8, camera u8, reserved u8,
# seq u32, capture_ts f64, server_ts f64
VIEWER_HEADER = struct.Struct("<BBBBIdd")
VIEWER_HEADER_SIZE = VIEWER_HEADER.size  # 24

assert CAMERA_HEADER_SIZE == 16
assert VIEWER_HEADER_SIZE == 24


class ProtocolError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class CameraFrame:
    seq: int
    capture_ts_ms: float
    jpeg: bytes


def pack_camera_frame(seq: int, capture_ts_ms: float, jpeg: bytes) -> bytes:
    return CAMERA_HEADER.pack(PROTOCOL_VERSION, MSG_FRAME, seq & 0xFFFFFFFF, capture_ts_ms, 0) + jpeg


def unpack_camera_frame(data: bytes) -> CameraFrame:
    if len(data) < CAMERA_HEADER_SIZE:
        raise ProtocolError("frame shorter than header")
    version, msg_type, seq, ts, _ = CAMERA_HEADER.unpack_from(data, 0)
    if version != PROTOCOL_VERSION:
        raise ProtocolError(f"unsupported version {version}")
    if msg_type != MSG_FRAME:
        raise ProtocolError(f"unknown msg_type {msg_type}")
    return CameraFrame(seq=seq, capture_ts_ms=ts, jpeg=bytes(data[CAMERA_HEADER_SIZE:]))


def pack_viewer_frame(position: str, seq: int, capture_ts_ms: float, server_ts_ms: float, jpeg: bytes) -> bytes:
    return (
        VIEWER_HEADER.pack(
            PROTOCOL_VERSION, MSG_FRAME, POSITION_INDEX[position], 0, seq & 0xFFFFFFFF, capture_ts_ms, server_ts_ms
        )
        + jpeg
    )


def unpack_viewer_frame(data: bytes) -> tuple[str, int, float, float, bytes]:
    if len(data) < VIEWER_HEADER_SIZE:
        raise ProtocolError("frame shorter than header")
    version, msg_type, cam, _, seq, cts, sts = VIEWER_HEADER.unpack_from(data, 0)
    if version != PROTOCOL_VERSION or msg_type != MSG_FRAME:
        raise ProtocolError("bad viewer frame header")
    return POSITIONS[cam], seq, cts, sts, bytes(data[VIEWER_HEADER_SIZE:])


# ---- JSON message builders -------------------------------------------------

def msg_ack(position: str, session_id: str, server_time_ms: float) -> dict:
    return {"type": "ack", "position": position, "session_id": session_id, "server_time_ms": server_time_ms}


def msg_config(fps: int, jpeg_quality: float, width: int, height: int) -> dict:
    return {"type": "config", "fps": fps, "jpeg_quality": jpeg_quality, "width": width, "height": height}


def msg_replaced() -> dict:
    return {"type": "replaced", "reason": "another node took this position"}


def msg_error(code: str, message: str) -> dict:
    return {"type": "error", "code": code, "message": message}


def msg_camera_status(position: str, status: str) -> dict:
    return {"type": "camera_status", "position": position, "status": status}


def meta() -> dict:
    return {
        "positions": list(POSITIONS),
        "classes": list(CLASSES),
        "warning_codes": dict(WARNING_CODES),
        "levels": ["none", "caution", "danger", "info"],
        "protocol": PROTOCOL_VERSION,
        "server_version": SERVER_VERSION,
    }
