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


def _ts_frame_count(path: Path) -> int:
    import cv2

    capture = cv2.VideoCapture(str(path))
    count = 0
    while True:
        ok, _ = capture.read()
        if not ok:
            break
        count += 1
    capture.release()
    return count


@pytest.mark.skipif(find_ffmpeg() is None, reason="ffmpeg 필요")
def test_slow_source_is_filled_to_video_time(tmp_path: Path):
    """웹캠처럼 선언 fps(10)보다 느리게(4fps) 들어와도 .ts 길이는 실제 경과 시간과 같아야 한다."""
    recorder = ContinuousRecorder(
        1, 64, 48, 10.0, recordings_dir=tmp_path, clock=lambda: STARTED_AT
    )
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    # 0.25초 간격으로 17장 → 0~4초
    for i in range(17):
        recorder.write(frame, video_time_sec=100.0 + i * 0.25)
    assert recorder.written == 41  # 4초 × 10fps + 첫 프레임
    path = recorder.close()
    assert path is not None
    assert _ts_frame_count(path) == 41


@pytest.mark.skipif(find_ffmpeg() is None, reason="ffmpeg 필요")
def test_fast_source_skips_extra_frames(tmp_path: Path):
    """녹화 fps(10)보다 빠르게(20fps) 들어오면 남는 프레임은 건너뛴다."""
    recorder = ContinuousRecorder(
        1, 64, 48, 10.0, recordings_dir=tmp_path, clock=lambda: STARTED_AT
    )
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    for i in range(41):
        recorder.write(frame, video_time_sec=i * 0.05)
    assert recorder.written == 21
    recorder.close()


@pytest.mark.skipif(find_ffmpeg() is None, reason="ffmpeg 필요")
def test_long_gap_is_filled_over_following_frames(tmp_path: Path):
    """긴 공백은 한 번에 MAX_FILL_SEC 까지만 채우고, 다음 프레임에서 따라잡는다."""
    from cctv_intrusion.video.continuous_recorder import MAX_FILL_SEC

    recorder = ContinuousRecorder(
        1, 64, 48, 10.0, recordings_dir=tmp_path, clock=lambda: STARTED_AT
    )
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    recorder.write(frame, video_time_sec=0.0)
    recorder.write(frame, video_time_sec=5.0)
    assert recorder.written == 1 + int(MAX_FILL_SEC * 10)
    recorder.write(frame, video_time_sec=5.1)
    recorder.write(frame, video_time_sec=5.2)
    recorder.write(frame, video_time_sec=5.3)
    assert recorder.written == 54  # 5.3초 × 10fps + 첫 프레임 — 다시 영상 시각과 일치
    recorder.close()
