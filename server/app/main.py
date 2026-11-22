"""FastAPI entry point.  Run from server/:  uvicorn app.main:app --host 0.0.0.0 --port 8000"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api import rest, ws_camera, ws_viewer
from app.config import DB_FILE, REACT_DIST, STATIC_DIR
from app.core.protocol import SERVER_VERSION
from app.core.runtime import Runtime
from app.models.schemas import Settings
from app.storage.db import Database

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def create_app(
    settings: Settings | None = None,
    enable_detector: bool | None = None,
    detector_factory: Callable[[Settings], Any] | None = None,
) -> FastAPI:
    if enable_detector is None:
        enable_detector = os.environ.get("DA_DISABLE_DETECTOR", "0") != "1"
    # SQLite database (docs/database.md). DA_DB_PATH lets tests use a temporary file.
    db = Database(os.environ.get("DA_DB_PATH") or DB_FILE)
    db.init(settings)  # creates tables and fills missing rows; existing values are kept
    if settings is None:
        settings = db.load_settings()
    runtime = Runtime(settings, enable_detector=enable_detector, detector_factory=detector_factory, db=db)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await runtime.start()
        try:
            yield
        finally:
            await runtime.stop()

    app = FastAPI(title="Driving Assistant server", version=SERVER_VERSION, lifespan=lifespan)
    app.state.runtime = runtime
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    @app.middleware("http")
    async def no_stale_pages(request: Request, call_next):
        """Pages (HTML) must always be checked again, or a browser keeps showing an old dashboard
        after a rebuild. JS/CSS files have a new name on every build, so they can stay cached."""
        response = await call_next(request)
        path = request.url.path
        if path.endswith("/") or path.endswith(".html") or path.endswith(".js") and path.startswith("/camera/"):
            response.headers["Cache-Control"] = "no-cache"
        return response

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException):
        detail = exc.detail if isinstance(exc.detail, dict) else {"code": "HTTP_ERROR", "message": str(exc.detail)}
        return JSONResponse({"error": detail}, status_code=exc.status_code)

    app.include_router(rest.router)
    app.include_router(ws_camera.router)
    app.include_router(ws_viewer.router)

    @app.get("/camera", include_in_schema=False)
    async def camera_redirect():
        return RedirectResponse("/camera/")

    @app.get("/debug", include_in_schema=False)
    async def debug_redirect():
        return RedirectResponse("/debug/")

    @app.get("/", include_in_schema=False)
    async def root_redirect():
        return RedirectResponse("/app/" if (REACT_DIST / "index.html").exists() else "/docs")

    if (REACT_DIST / "index.html").exists():  # built with run_demo.bat / npm run build:react

        @app.get("/app", include_in_schema=False)
        async def app_redirect():
            return RedirectResponse("/app/")

        app.mount("/app/", StaticFiles(directory=REACT_DIST, html=True), name="react")

    app.mount("/camera/", StaticFiles(directory=STATIC_DIR / "camera", html=True), name="camera")
    app.mount("/debug/", StaticFiles(directory=STATIC_DIR / "debug", html=True), name="debug")
    return app


app = create_app()
