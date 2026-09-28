import csv

import cv2
import numpy as np

from cctv_intrusion.detection import Detection
from cctv_intrusion.intrusion import (
    EVENT_CSV_FIELDS,
    IntrusionEvent,
    IntrusionMonitor,
    MonitorState,
    events_csv_path,
    export_event_clip,
    next_clip_path,
    save_event_records,
)
from cctv_intrusion.intrusion.events import CAM_EVENTS_CSV_NAME, format_video_timestamp
from cctv_intrusion.zone import Zone


def _write_dummy_video(path, *, frames: int = 30, fps: float = 10.0) -> None:
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (64, 48),
    )
    assert writer.isOpened()
    for index in range(frames):
        frame = np.full((48, 64, 3), index % 255, dtype=np.uint8)
        writer.write(frame)
    writer.release()


def test_format_video_timestamp():
    assert format_video_timestamp(0) == "00:00.000"
    assert format_video_timestamp(83.5) == "01:23.500"
    assert format_video_timestamp(3723.25) == "1:02:03.250"


def test_events_csv_path_uses_video_stem(tmp_path):
    assert events_csv_path(tmp_path / "cam1.mp4", output_dir=tmp_path) == tmp_path / "cam1.csv"


def test_events_csv_path_uses_events_in_cam_folder(tmp_path, monkeypatch):
    monkeypatch.setattr("cctv_intrusion.intrusion.events.RECORDINGS_DIR", tmp_path)
    cam_dir = tmp_path / "cam3"
    cam_dir.mkdir()
    assert (
        events_csv_path(tmp_path / "test.mp4", output_dir=cam_dir)
        == cam_dir / CAM_EVENTS_CSV_NAME
    )


def test_save_event_records_writes_cam_events_csv(tmp_path, monkeypatch):
    monkeypatch.setattr("cctv_intrusion.intrusion.events.RECORDINGS_DIR", tmp_path)
    cam_dir = tmp_path / "cam2"
    cam_dir.mkdir()
    video = tmp_path / "cctv" / "test_2.mp4"
    video.parent.mkdir()
    _write_dummy_video(video, frames=40, fps=10.0)

    event = IntrusionEvent.create(
        alarm_sec=2.0,
        cleared_sec=3.0,
        zone_name="구역1",
        zone_level="danger",
    )
    csv_path = save_event_records([event], video, output_dir=cam_dir)
    assert csv_path == cam_dir / CAM_EVENTS_CSV_NAME
    assert (cam_dir / "test_2_1.mp4").exists()


def test_next_clip_path_increments(tmp_path):
    video = tmp_path / "cam1.mp4"
    first = next_clip_path(video, output_dir=tmp_path)
    assert first == tmp_path / "cam1_1.mp4"
    first.write_bytes(b"x")
    assert next_clip_path(video, output_dir=tmp_path) == tmp_path / "cam1_2.mp4"


def test_intrusion_event_includes_clip_window():
    event = IntrusionEvent.create(
        alarm_sec=10.0,
        cleared_sec=13.5,
        zone_name="구역1",
        zone_level="danger",
    )
    assert event.alarm_at == "00:10.000"
    assert event.cleared_at == "00:13.500"
    assert event.duration_sec == 3.5
    assert event.clip_start == "00:07.000"
    assert event.clip_end == "00:18.500"  # cleared 13.5 + 5
    assert event.clip_start_sec == 7.0
    assert event.clip_end_sec == 18.5


def test_export_and_save_event_records(tmp_path):
    video = tmp_path / "cam1.mp4"
    _write_dummy_video(video, frames=40, fps=10.0)

    event = IntrusionEvent.create(
        alarm_sec=2.0,
        cleared_sec=3.0,
        zone_name="구역1",
        zone_level="danger",
    )
    # clip: max(0, 2-3)=0 .. 2+5=7 → 0~7s at 10fps = frames 0..70 but only 40 exist
    csv_path = save_event_records([event], video, output_dir=tmp_path)
    assert csv_path == tmp_path / "cam1.csv"
    assert event.clip_file == "cam1_1.mp4"
    clip = tmp_path / "cam1_1.mp4"
    assert clip.exists() and clip.stat().st_size > 0

    with csv_path.open(encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    assert list(rows[0].keys()) == list(EVENT_CSV_FIELDS)
    assert rows[0]["clip_file"] == "cam1_1.mp4"
    assert rows[0]["zone_name"] == "구역1"

    # second event gets _2
    event2 = IntrusionEvent.create(
        alarm_sec=1.0,
        cleared_sec=1.5,
        zone_name="구역2",
        zone_level="caution",
    )
    export_event_clip(video, event2, output_dir=tmp_path)
    assert (tmp_path / "cam1_2.mp4").exists()


def test_monitor_emits_event_on_clear_not_on_alarm():
    zone = Zone(name="A", points=[(0, 0), (100, 0), (100, 100), (0, 100)], level="danger")
    monitor = IntrusionMonitor()
    monitor.set_zones([zone])
    person = Detection(x1=40, y1=10, x2=60, y2=90, confidence=0.9)

    assert monitor.update([person], frame_index=0, fps=10) == MonitorState.ARMED
    assert monitor.new_events == []

    assert monitor.update([person], frame_index=10, fps=10) == MonitorState.ALARM
    assert monitor.new_events == []

    monitor.update([person], frame_index=20, fps=10)
    assert monitor.new_events == []

    state = monitor.update([], frame_index=25, fps=10)
    assert state == MonitorState.CLEARED
    assert len(monitor.new_events) == 1
    event = monitor.new_events[0]
    assert event.zone_name == "A"
    assert event.alarm_at == "00:01.000"
    assert event.cleared_at == "00:02.500"
    assert event.duration_sec == 1.5
    assert event.clip_start_sec == 0.0
    assert event.clip_end_sec == 7.5  # cleared 2.5 + 5


def test_monitor_close_alarms_returns_active_alarm_as_event():
    zone = Zone(name="구역1", points=[(0, 0), (100, 0), (100, 100), (0, 100)], level="danger")
    monitor = IntrusionMonitor()
    monitor.set_zones([zone])
    inside = [Detection(x1=40, y1=10, x2=60, y2=50, confidence=0.9)]
    for frame_index in range(0, 21):  # 10fps 로 2초 동안 구역 안
        monitor.update(inside, frame_index, 10.0)
    assert monitor.state == MonitorState.ALARM

    events = monitor.close_alarms()
    assert len(events) == 1
    assert events[0].zone_name == "구역1"
    assert events[0].cleared_at == "00:02.000"
    assert monitor.state == MonitorState.CLEARED
    assert monitor.close_alarms() == []
