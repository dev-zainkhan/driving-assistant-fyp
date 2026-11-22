"""/ws/viewer: dashboards receive frames (binary), overlays and state (JSON)."""
from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket

from app.core import protocol
from app.core.broadcaster import VIDEO_MODES

router = APIRouter()
log = logging.getLogger("da.ws_viewer")


@router.websocket("/ws/viewer")
async def viewer_ws(ws: WebSocket) -> None:
    rt = ws.app.state.runtime
    await ws.accept()
    b = rt.broadcaster
    v = b.add(ws)
    b.send_to(v, rt.welcome_json())
    b.send_to(v, rt.warning_state_json())
    try:
        while True:
            msg = await ws.receive_json()
            if msg.get("type") == "subscribe":
                mode = msg.get("video", "auto")
                if mode in VIDEO_MODES:
                    v.mode = mode
                else:
                    b.send_to(v, protocol.msg_error("BAD_VIDEO_MODE", "video must be auto, all or none"))
    except Exception as e:
        log.debug("viewer socket ended: %s", e)
    finally:
        await b.remove(v)
