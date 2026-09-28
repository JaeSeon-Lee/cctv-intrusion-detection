import csv
from datetime import datetime

import cv2
import numpy as np

from cctv_intrusion.intrusion import IntrusionEvent, LiveRecorder, live_clip_path
from cctv_intrusion.intrusion.live_recorder import estimate_fps

FPS = 10
STARTED_AT = datetime(2026, 9, 27, 18, 9, 11)


def _frame(index: int) -> np.ndarray:
    return np.full((48, 64, 3), index % 255, dtype=np.uint8)


def _recorder(tmp_path) -> LiveRecorder:
    return LiveRecorder(output_dir=tmp_path, clock=lambda: STARTED_AT)


def _feed(recorder: LiveRecorder, start: int, stop: int):
    """start~stop-1 번 프레임을 FPS 간격 시각으로 넣고, 클립이 끝나면 CSV 경로를 돌려준다."""
    for index in range(start, stop):
        csv_path = recorder.add_frame(_frame(index), index / FPS)
        if csv_path is not None:
            return csv_path
    return None


def _frame_count(path) -> int:
    capture = cv2.VideoCapture(str(path))
    count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    capture.release()
    return count


def _event(alarm_sec: float, cleared_sec: float) -> IntrusionEvent:
    return IntrusionEvent.create(
        alarm_sec=alarm_sec, cleared_sec=cleared_sec, zone_name="구역 1", zone_level="danger"
    )


def test_live_clip_path_uses_datetime_and_avoids_duplicates(tmp_path):
    first = live_clip_path(STARTED_AT, output_dir=tmp_path)
    assert first.name == "live_20260927_180911.mp4"
    first.write_bytes(b"x")
    assert live_clip_path(STARTED_AT, output_dir=tmp_path).name == "live_20260927_180911_2.mp4"


def test_estimate_fps():
    assert estimate_fps([0.0, 0.1, 0.2, 0.3]) == 10
    assert estimate_fps([1.0]) == 30


def test_no_clip_without_alarm(tmp_path):
    recorder = _recorder(tmp_path)
    _feed(recorder, 0, 100)
    recorder.update(False, 9.9, [])
    assert not recorder.recording
    assert recorder.finish() is None
    assert list(tmp_path.iterdir()) == []
    # 버퍼는 경보 전 3초 + 여유 2초만 들고 있는다
    assert recorder.buffer[0][0] >= 9.9 - 5.0


def test_clip_covers_before_alarm_to_after_clear(tmp_path):
    recorder = _recorder(tmp_path)
    _feed(recorder, 0, 51)
    recorder.update(True, 5.0, [])  # 5초에 경보
    assert recorder.recording
    _feed(recorder, 51, 81)
    recorder.update(False, 8.0, [_event(5.0, 8.0)])  # 8초에 해제

    csv_path = _feed(recorder, 81, 200)
    clip_path = tmp_path / "live_20260927_180911.mp4"
    assert csv_path == tmp_path / "live_20260927_180911.csv"
    assert not recorder.recording
    # 2초(경보 3초 전) ~ 13초(해제 5초 후) 프레임
    assert _frame_count(clip_path) == 111

    with csv_path.open(encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    assert len(rows) == 1
    # CSV 시각은 클립 영상 안의 시각
    assert rows[0]["alarm_at"] == "00:03.000"
    assert rows[0]["cleared_at"] == "00:06.000"
    assert rows[0]["clip_start"] == "00:00.000"
    assert rows[0]["clip_file"] == "live_20260927_180911.mp4"
    assert rows[0]["zone_level"] == "danger"


def test_new_alarm_during_after_clear_extends_same_clip(tmp_path):
    recorder = _recorder(tmp_path)
    _feed(recorder, 0, 51)
    recorder.update(True, 5.0, [])
    _feed(recorder, 51, 61)
    recorder.update(False, 6.0, [_event(5.0, 6.0)])
    _feed(recorder, 61, 81)
    recorder.update(True, 8.0, [])  # 해제 후 5초가 지나기 전에 다시 경보
    _feed(recorder, 81, 101)
    recorder.update(False, 10.0, [_event(8.0, 10.0)])

    csv_path = _feed(recorder, 101, 200)
    assert csv_path is not None
    assert [path.name for path in tmp_path.glob("*.mp4")] == ["live_20260927_180911.mp4"]
    with csv_path.open(encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    assert [row["alarm_at"] for row in rows] == ["00:03.000", "00:06.000"]


def test_finish_while_recording_saves_clip(tmp_path):
    recorder = _recorder(tmp_path)
    _feed(recorder, 0, 51)
    recorder.update(True, 5.0, [])
    _feed(recorder, 51, 61)

    # 카메라 연결 해제: 아직 경보 중인 사건은 끊은 시각에 해제된 것으로 기록
    csv_path = recorder.finish([_event(5.0, 6.0)])
    assert _frame_count(tmp_path / "live_20260927_180911.mp4") == 41
    with csv_path.open(encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    assert rows[0]["cleared_at"] == "00:04.000"
