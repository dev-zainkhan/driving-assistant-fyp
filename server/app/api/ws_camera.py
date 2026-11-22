"""/ws/camera/{position}: phones (camera nodes) send hello, then binary JPEG frames."""
from __future__ import annotations

import asyncio
import json
import logging
import time

from fastapi import APIRouter, WebSocket

from app.core import protocol
from app.core.protocol import POSITIONS, ProtocolError
from app.core.runtime import CameraConn

router = APIRouter()
log = logging.getLogger("da.ws_camera")

HELLO_TIMEOUT_S = 5.0


@router.websocket("/ws/camera/{position}")
async def camera_ws(ws: WebSocket, position: str) -> None:
    rt = ws.app.state.runtime
    await ws.accept()
    if position not in POSITIONS:
        await ws.send_json(protocol.msg_error("BAD_POSITION", "position must be front, left, right or back"))
        await ws.close(code=1008)
        return

    try:
        first = await asyncio.wait_for(ws.receive(), HELLO_TIMEOUT_S)
        hello = json.loads(first.get("text") or "{}")
        if hello.get("type") != "hello":
            raise ValueError("first message must be hello")
    except Exception as e:
        try:
            await ws.send_json(protocol.msg_error("BAD_HELLO", f"expected hello message: {e}"))
            await ws.close(code=1008)
        except Exception:
            pass
        return

    session = rt.new_session_id()

    async def close_replaced(msg: dict) -> None:
        await ws.send_json(msg)
        await ws.close(code=4000)

    conn = CameraConn(
        session_id=session,
        source="phone",
        client=str(hello.get("client", "")),
        video_name=str(hello.get("video_name", "")),
        close=close_replaced,
    )
    await rt.register_camera(position, conn)
    s = rt.settings
    await ws.send_json(protocol.msg_ack(position, session, time.time() * 1000))
    await ws.send_json(protocol.msg_config(s.stream_fps, s.jpeg_quality, s.stream_width, s.stream_height))

    try:
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                break
            if rt.cameras[position] is not conn:
                break  # replaced by another node
            data = msg.get("bytes")
            if data is not None:
                try:
                    f = protocol.unpack_camera_frame(data)
                except ProtocolError as e:
                    log.debug("bad frame from %s: %s", position, e)
                    continue
                rt.ingest(position, f.seq, f.capture_ts_ms, f.jpeg)
                continue
            text = msg.get("text")
            if text:
                try:
                    m = json.loads(text)
                except ValueError:
                    continue
                if m.get("type") == "stats":
                    conn.client_stats = m
                elif m.get("type") == "hello":
                    conn.video_name = str(m.get("video_name", conn.video_name))
                elif m.get("type") == "ping":
                    await ws.send_json({"type": "pong", "t": m.get("t"), "server_time_ms": time.time() * 1000})
    except Exception as e:
        log.debug("camera %s socket ended: %s", position, e)
    finally:
        rt.unregister_camera(position, session)
