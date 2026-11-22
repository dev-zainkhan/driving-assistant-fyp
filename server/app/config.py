"""Paths used by the server."""
from __future__ import annotations

from pathlib import Path


SERVER_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = SERVER_DIR.parent
DATA_DIR = SERVER_DIR / "data"
WEIGHTS_DIR = SERVER_DIR / "weights"
STATIC_DIR = Path(__file__).resolve().parent / "static"
VIDEOS_DIR = REPO_DIR / "videos"
DB_FILE = DATA_DIR / "driving_assistant.db"  # SQLite: settings + incidents
INCIDENTS_DIR = DATA_DIR / "incidents"  # one folder per incident (videos, front picture)
REACT_DIST = REPO_DIR / "clients" / "react-web" / "dist"  # built dashboard, served at /app


def model_path(name: str) -> Path | str:
    """Return weights/<name> if present, else the bare name (Ultralytics downloads it)."""
    p = WEIGHTS_DIR / name
    return p if p.exists() else name
