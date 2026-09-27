import csv

from cctv_intrusion.detection import Detection
from cctv_intrusion.intrusion import (
    EVENT_CSV_FIELDS,
    IntrusionEvent,
    IntrusionMonitor,
    MonitorState,
    append_events,
    events_csv_path,
)
from cctv_intrusion.intrusion.events import format_video_timestamp
from cctv_intrusion.zone import Zone


def test_format_video_timestamp():
    assert format_video_timestamp(0) == "00:00.000"
    assert format_video_timestamp(83.5) == "01:23.500"
    assert format_video_timestamp(3723.25) == "1:02:03.250"


def test_events_csv_path_uses_video_stem(tmp_path):
    assert events_csv_path(tmp_path / "cam1.mp4", output_dir=tmp_path) == tmp_path / "cam1.csv"
    assert (
        events_csv_path("/data/input/test_trespass.mp4", output_dir=tmp_path)
        == tmp_path / "test_trespass.csv"
    )


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
    assert event.clip_start == "00:07.000"  # 10 - 3
    assert event.clip_end == "00:15.000"  # 10 + 5


def test_append_events_writes_header_and_rows(tmp_path):
    video = tmp_path / "cam1.mp4"
    event = IntrusionEvent.create(
        alarm_sec=10.0,
        cleared_sec=12.0,
        zone_name="구역1",
        zone_level="danger",
    )
    path = append_events([event], video, output_dir=tmp_path)
    assert path == tmp_path / "cam1.csv"

    with path.open(encoding="utf-8") as file:
        rows = list(csv.DictReader(file))

    assert list(rows[0].keys()) == list(EVENT_CSV_FIELDS)
    assert rows[0]["alarm_at"] == "00:10.000"
    assert rows[0]["cleared_at"] == "00:12.000"
    assert rows[0]["duration_sec"] == "2.0"
    assert rows[0]["clip_start"] == "00:07.000"
    assert rows[0]["clip_end"] == "00:15.000"
    assert rows[0]["zone_name"] == "구역1"
    assert rows[0]["zone_level"] == "danger"


def test_monitor_emits_event_on_clear_not_on_alarm():
    zone = Zone(name="A", points=[(0, 0), (100, 0), (100, 100), (0, 100)], level="danger")
    monitor = IntrusionMonitor()
    monitor.set_zones([zone])
    person = Detection(x1=40, y1=10, x2=60, y2=90, confidence=0.9)

    assert monitor.update([person], frame_index=0, fps=10) == MonitorState.ARMED
    assert monitor.new_events == []

    # +1.0s → alarm starts, but CSV row waits until clear
    assert monitor.update([person], frame_index=10, fps=10) == MonitorState.ALARM
    assert monitor.new_events == []

    # still inside
    monitor.update([person], frame_index=20, fps=10)
    assert monitor.new_events == []

    # leave zone → cleared, event recorded
    state = monitor.update([], frame_index=25, fps=10)
    assert state == MonitorState.CLEARED
    assert len(monitor.new_events) == 1
    event = monitor.new_events[0]
    assert event.zone_name == "A"
    assert event.alarm_at == "00:01.000"
    assert event.cleared_at == "00:02.500"
    assert event.duration_sec == 1.5
    assert event.clip_start == "00:00.000"
    assert event.clip_end == "00:06.000"
