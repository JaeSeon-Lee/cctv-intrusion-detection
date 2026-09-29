from pathlib import Path

import pytest

from cctv_intrusion.intrusion.events import format_video_timestamp
from cctv_intrusion.intrusion.recording_stats import (
    RecordingEvent,
    RecordingStats,
    load_recording_events,
    parse_video_timestamp,
    recording_stats,
)

CSV_HEADER = (
    "alarm_at,cleared_at,duration_sec,clip_start,clip_end,clip_file,zone_name,zone_level,"
    "source_file,source_alarm_at,source_cleared_at\n"
)


@pytest.mark.parametrize("seconds", [0.0, 3.0, 5.333, 65.5, 3725.25])
def test_parse_video_timestamp_roundtrip(seconds):
    assert parse_video_timestamp(format_video_timestamp(seconds)) == pytest.approx(seconds)


def test_parse_video_timestamp_invalid():
    with pytest.raises(ValueError):
        parse_video_timestamp("abc")


def test_load_recording_events_filters_by_source(tmp_path: Path):
    (tmp_path / "events.csv").write_text(
        CSV_HEADER + "00:03.000,00:05.333,2.33,00:00.000,00:10.333,live_a.mp4,구역 1,danger,"
        "rec_a.ts,01:03.000,01:05.333\n"
        + "00:01.000,00:02.000,1.00,00:00.000,00:07.000,live_b.mp4,구역 2,detect,"
        "rec_b.ts,00:11.000,00:12.000\n"
        + "00:03.000,00:04.500,1.50,00:00.000,00:09.500,live_c.mp4,구역 2,caution,"
        "rec_a.ts,00:20.000,00:21.500\n"
        # 예전 기록: 녹화 위치 없음
         + "00:03.000,00:04.000,1.00,00:00.000,00:09.000,live_old.mp4,구역 1,danger,,,\n",
        encoding="utf-8",
    )
    events, unplaced = load_recording_events(tmp_path / "rec_a.ts")
    assert [e.alarm_sec for e in events] == [20.0, 63.0]
    assert events[1].duration_sec == pytest.approx(2.333)
    assert events[0].clip_file == "live_c.mp4"
    assert unplaced == 1


def test_load_recording_events_old_header(tmp_path: Path):
    (tmp_path / "events.csv").write_text(
        "alarm_at,cleared_at,duration_sec,clip_start,clip_end,clip_file,zone_name,zone_level\n"
        "00:03.000,00:05.333,2.33,00:00.000,00:10.333,live_a.mp4,구역 1,danger\n",
        encoding="utf-8",
    )
    assert load_recording_events(tmp_path / "rec_a.ts") == ([], 1)


def test_load_recording_events_missing_csv(tmp_path: Path):
    assert load_recording_events(tmp_path / "rec_a.ts") == ([], 0)


def test_stats_merges_overlap_and_clamps():
    stats = RecordingStats(
        video_sec=10.0,
        events=(
            RecordingEvent(1.0, 3.0, "a", "danger"),
            RecordingEvent(2.0, 4.0, "b", "danger"),  # 1~4 로 합쳐짐
            RecordingEvent(9.0, 12.0, "c", "danger"),  # 녹화 끝(10)에서 자름
        ),
    )
    assert stats.count == 3
    assert stats.intrusion_sec == pytest.approx(4.0)
    assert stats.ratio_pct == pytest.approx(40.0)
    assert stats.avg_sec == pytest.approx(7.0 / 3)
    assert stats.max_sec == pytest.approx(3.0)
    assert stats.min_sec == pytest.approx(2.0)


def test_stats_empty():
    stats = RecordingStats(video_sec=0.0, events=())
    assert stats.count == 0
    assert stats.ratio_pct == 0.0
    assert stats.avg_sec == 0.0


def test_recording_stats_falls_back_to_last_cleared(tmp_path: Path):
    (tmp_path / "events.csv").write_text(
        CSV_HEADER + "00:03.000,00:05.000,2.00,00:00.000,00:10.000,live_a.mp4,구역 1,danger,"
        "rec_a.ts,00:30.000,00:32.000\n",
        encoding="utf-8",
    )
    (tmp_path / "rec_a.ts").write_bytes(b"not a video")
    stats = recording_stats(tmp_path / "rec_a.ts")
    assert stats.video_sec == pytest.approx(32.0)
    assert stats.count == 1
