"""상시 녹화에서 침입 구간을 자르는 IntrusionClipper 테스트."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from cctv_intrusion.intrusion.events import IntrusionEvent
from cctv_intrusion.intrusion.recording_clip import (
    IntrusionClipper,
    cut_clip_from_recording,
    find_ffmpeg,
    live_clip_path,
    run_clip_export,
)
from cctv_intrusion.video.continuous_recorder import ContinuousRecorder

FPS = 10.0
STARTED_AT = datetime(2026, 9, 27, 18, 9, 11)


def _event(alarm_sec: float, cleared_sec: float) -> IntrusionEvent:
    return IntrusionEvent.create(
        alarm_sec=alarm_sec,
        cleared_sec=cleared_sec,
        zone_name="구역 1",
        zone_level="danger",
    )


def test_live_clip_path_uses_datetime_and_avoids_duplicates(tmp_path: Path):
    first = live_clip_path(STARTED_AT, output_dir=tmp_path)
    assert first.name == "live_20260927_180911.mp4"
    first.write_bytes(b"x")
    assert live_clip_path(STARTED_AT, output_dir=tmp_path).name == "live_20260927_180911_2.mp4"


def test_live_clip_path_ignores_shared_events_csv(tmp_path: Path):
    """camN/events.csv 가 있어도 파일명 while 이 무한루프 되지 않아야 한다."""
    cam_dir = tmp_path / "cam9"
    cam_dir.mkdir()
    (cam_dir / "events.csv").write_text("alarm_at\n", encoding="utf-8")
    path = live_clip_path(STARTED_AT, output_dir=cam_dir)
    assert path.name == "live_20260927_180911.mp4"
    assert path.parent == cam_dir


@pytest.mark.skipif(find_ffmpeg() is None, reason="ffmpeg 필요")
def test_clipper_cuts_from_continuous_recording(tmp_path: Path):
    """상시 .ts 에 쓴 뒤, 경보 구간만 MP4 로 자른다 (프레임 JPEG 버퍼 없음)."""
    continuous = ContinuousRecorder(
        1,
        64,
        48,
        FPS,
        recordings_dir=tmp_path,
        clock=lambda: STARTED_AT,
    )
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    # 0~15초 분량 (150 프레임)
    for index in range(150):
        frame[:] = (index * 3) % 255
        continuous.write(frame, video_time_sec=index / FPS)

    clipper = IntrusionClipper(
        output_dir=tmp_path,
        get_recording=lambda: continuous,
        clock=lambda: STARTED_AT,
    )

    # 5초에 경보, 8초에 해제 → 클립 2초~13초
    clipper.update(True, 5.0, [])
    assert clipper.pending
    clipper.update(False, 8.0, [_event(5.0, 8.0)])

    assert clipper.tick(12.9) is None
    job = clipper.tick(13.0)
    assert job is not None
    csv_path = run_clip_export(job)
    clipper.mark_export_done()
    assert csv_path is not None
    assert not clipper.pending

    clip_path = tmp_path / "live_20260927_180911.mp4"
    assert clip_path.exists()
    assert clip_path.stat().st_size > 0

    with csv_path.open(encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    assert len(rows) == 1
    assert rows[0]["alarm_at"] == "00:03.000"
    assert rows[0]["cleared_at"] == "00:06.000"
    assert rows[0]["clip_file"] == "live_20260927_180911.mp4"
    assert rows[0]["zone_level"] == "danger"
    # 상시 녹화 파일 기준 위치 (대시보드용)
    assert rows[0]["source_file"] == continuous.path.name
    assert rows[0]["source_alarm_at"] == "00:05.000"
    assert rows[0]["source_cleared_at"] == "00:08.000"

    continuous.close()


@pytest.mark.skipif(find_ffmpeg() is None, reason="ffmpeg 필요")
def test_source_position_subtracts_recording_origin(tmp_path: Path):
    """녹화가 영상 20초부터 시작했으면 .ts 기준 위치는 20초를 뺀 값이다."""
    continuous = ContinuousRecorder(
        1, 64, 48, FPS, recordings_dir=tmp_path, clock=lambda: STARTED_AT
    )
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    for index in range(150):
        continuous.write(frame, video_time_sec=20.0 + index / FPS)

    clipper = IntrusionClipper(
        output_dir=tmp_path, get_recording=lambda: continuous, clock=lambda: STARTED_AT
    )
    clipper.update(True, 25.0, [])
    clipper.update(False, 28.0, [_event(25.0, 28.0)])
    job = clipper.tick(33.0)
    assert job is not None
    csv_path = run_clip_export(job)
    clipper.mark_export_done()
    assert csv_path is not None

    with csv_path.open(encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    assert rows[0]["alarm_at"] == "00:03.000"
    assert rows[0]["source_alarm_at"] == "00:05.000"
    assert rows[0]["source_cleared_at"] == "00:08.000"

    continuous.close()


@pytest.mark.skipif(find_ffmpeg() is None, reason="ffmpeg 필요")
def test_new_alarm_during_after_clear_extends_same_clip(tmp_path: Path):
    continuous = ContinuousRecorder(
        1,
        64,
        48,
        FPS,
        recordings_dir=tmp_path,
        clock=lambda: STARTED_AT,
    )
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    for index in range(200):
        continuous.write(frame, video_time_sec=index / FPS)

    clipper = IntrusionClipper(
        output_dir=tmp_path,
        get_recording=lambda: continuous,
        clock=lambda: STARTED_AT,
    )
    clipper.update(True, 5.0, [])
    clipper.update(False, 6.0, [_event(5.0, 6.0)])
    clipper.update(True, 8.0, [])  # 해제 후 5초 전 재경보
    clipper.update(False, 10.0, [_event(8.0, 10.0)])

    job = clipper.tick(15.0)
    assert job is not None
    csv_path = run_clip_export(job)
    clipper.mark_export_done()
    assert csv_path is not None
    assert [path.name for path in tmp_path.glob("*.mp4")] == ["live_20260927_180911.mp4"]
    with csv_path.open(encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    assert [row["alarm_at"] for row in rows] == ["00:03.000", "00:06.000"]

    continuous.close()


@pytest.mark.skipif(find_ffmpeg() is None, reason="ffmpeg 필요")
def test_finish_while_recording_saves_available_range(tmp_path: Path):
    continuous = ContinuousRecorder(
        1,
        64,
        48,
        FPS,
        recordings_dir=tmp_path,
        clock=lambda: STARTED_AT,
    )
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    for index in range(70):
        continuous.write(frame, video_time_sec=index / FPS)

    clipper = IntrusionClipper(
        output_dir=tmp_path,
        get_recording=lambda: continuous,
        clock=lambda: STARTED_AT,
    )
    clipper.update(True, 5.0, [])
    clipper.tick(6.0)

    csv_path = clipper.finish([_event(5.0, 6.0)])
    assert csv_path is not None
    clip_path = tmp_path / "live_20260927_180911.mp4"
    assert clip_path.exists()

    capture = cv2.VideoCapture(str(clip_path))
    assert capture.isOpened()
    capture.release()

    with csv_path.open(encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    assert rows[0]["cleared_at"] == "00:04.000"

    continuous.close()


def test_no_clip_without_alarm(tmp_path: Path):
    recording = SimpleNamespace(path=tmp_path / "missing.ts", origin_video_sec=0.0)
    clipper = IntrusionClipper(
        output_dir=tmp_path,
        get_recording=lambda: recording,
        clock=lambda: STARTED_AT,
    )
    clipper.update(False, 9.9, [])
    assert not clipper.pending
    assert clipper.finish() is None
    assert list(tmp_path.iterdir()) == []


@pytest.mark.skipif(find_ffmpeg() is None, reason="ffmpeg 필요")
def test_cut_past_recording_end_raises_and_leaves_no_file(tmp_path: Path):
    """녹화 길이를 넘는 구간을 자르면 빈 mp4 를 남기지 않고 오류를 낸다."""
    continuous = ContinuousRecorder(
        1, 64, 48, FPS, recordings_dir=tmp_path, clock=lambda: STARTED_AT
    )
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    for index in range(30):  # 3초
        continuous.write(frame, video_time_sec=index / FPS)
    source = continuous.close()
    assert source is not None

    output = tmp_path / "live_out.mp4"
    with pytest.raises(OSError, match="프레임이 없습니다"):
        cut_clip_from_recording(source, start_sec=20.0, duration_sec=5.0, output=output)
    assert not output.exists()
