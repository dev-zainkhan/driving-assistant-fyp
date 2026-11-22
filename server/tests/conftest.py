import os
import sys
import tempfile
from pathlib import Path

import pytest

os.environ.setdefault("DA_DISABLE_DETECTOR", "1")
# app.main builds one app at import time; point it at a throwaway database too.
os.environ["DA_DB_PATH"] = str(Path(tempfile.mkdtemp(prefix="da-test-")) / "import.db")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def temp_database(tmp_path, monkeypatch):
    """Every test gets its own empty SQLite file, never the real server/data database."""
    monkeypatch.setenv("DA_DB_PATH", str(tmp_path / "test.db"))
    yield tmp_path / "test.db"
