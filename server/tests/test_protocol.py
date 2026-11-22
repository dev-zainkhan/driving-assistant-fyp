import pytest

from app.core import protocol as p

# Shared byte fixture: the TS tests in clients/shared-ts use the same bytes.
CAMERA_FIXTURE_HEX = "01012a0000000000d0cdb2a979420000ffd8ffd9"
VIEWER_FIXTURE_HEX = "01010200070000000000000000428f4000000000004c8f404a504547"


def test_camera_header_size():
    assert p.CAMERA_HEADER_SIZE == 16
    assert p.VIEWER_HEADER_SIZE == 24


def test_camera_roundtrip():
    jpeg = b"\xff\xd8hello\xff\xd9"
    data = p.pack_camera_frame(42, 1763540000000.5, jpeg)
    f = p.unpack_camera_frame(data)
    assert f.seq == 42 and f.capture_ts_ms == 1763540000000.5 and f.jpeg == jpeg


def test_camera_fixture_bytes():
    data = p.pack_camera_frame(42, 1763540000000.0, b"\xff\xd8\xff\xd9")
    assert data.hex() == CAMERA_FIXTURE_HEX


def test_viewer_fixture_bytes():
    assert p.pack_viewer_frame("right", 7, 1000.25, 1001.5, b"JPEG").hex() == VIEWER_FIXTURE_HEX


def test_viewer_roundtrip():
    data = p.pack_viewer_frame("right", 7, 1000.25, 1001.5, b"JPEG")
    assert data[2] == 2
    pos, seq, cts, sts, jpeg = p.unpack_viewer_frame(data)
    assert (pos, seq, cts, sts, jpeg) == ("right", 7, 1000.25, 1001.5, b"JPEG")


def test_bad_frames():
    with pytest.raises(p.ProtocolError):
        p.unpack_camera_frame(b"\x01\x01")
    with pytest.raises(p.ProtocolError):
        p.unpack_camera_frame(b"\x02" + b"\x00" * 20)
