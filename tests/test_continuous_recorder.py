from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

from cctv_intrusion.video.continuous_recorder import (
    ContinuousRecorder,
    find_ffmpeg,
    recording_path,
)

STARTED_AT = datetime(2026, 9, 28, 20, 0, 0)


def test_recording_path_uses_cam_dir_and_datetime(tmp_path: Path):
    cam_dir = tmp_path / "cam1"
    first = recording_path(1, STARTED_AT, recordings_dir=cam_dir)
    assert first == cam_dir / "20260928_200000.ts"
    first.write_bytes(b"x")
    assert recording_path(1, STARTED_AT, recordings_dir=cam_dir).name == "20260928_200000_2.ts"


@pytest.mark.skipif(find_ffmpeg() is None, reason="ffmpeg 필요")
def test_continuous_recorder_writes_mpegts(tmp_path: Path):
    recorder = ContinuousRecorder(
        2,
        64,
        48,
        10.0,
        recordings_dir=tmp_path,
        clock=lambda: STARTED_AT,
    )
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    for i in range(20):
        frame[:] = i * 10
        recorder.write(frame)
    path = recorder.close()
    assert path is not None
    assert path.suffix == ".ts"
    assert path.exists()
    assert path.stat().st_size > 0
    # MPEG-TS sync byte
    assert path.read_bytes()[0] == 0x47


@pytest.mark.skipif(find_ffmpeg() is None, reason="ffmpeg 필요")
def test_continuous_recorder_readable_while_writing(tmp_path: Path):
    """쓰기 중에 OpenCV 로 열어 프레임을 읽을 수 있어야 한다."""
    import cv2

    recorder = ContinuousRecorder(
        1,
        64,
        48,
        10.0,
        recordings_dir=tmp_path,
        clock=lambda: STARTED_AT,
    )
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    for i in range(30):
        frame[:] = (i * 7) % 255
        recorder.write(frame)

    capture = cv2.VideoCapture(str(recorder.path))
    assert capture.isOpened()
    ok, loaded = capture.read()
    capture.release()
    assert ok
    assert loaded is not None

    path = recorder.close()
    assert path is not None


@pytest.mark.skipif(find_ffmpeg() is None, reason="ffmpeg 필요")
def test_continuous_recorder_no_frames_deletes_file(tmp_path: Path):
    recorder = ContinuousRecorder(
        1,
        64,
        48,
        10.0,
        recordings_dir=tmp_path,
        clock=lambda: STARTED_AT,
    )
    path = recorder.path
    assert recorder.close() is None
    assert not path.exists()
