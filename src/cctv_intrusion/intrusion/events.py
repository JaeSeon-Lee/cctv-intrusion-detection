"""침입 사건 CSV 기록.

캠별 폴더(recordings/camN/)에는 events.csv 한 파일에 사건을 누적한다.
클립: 같은 폴더의 {원본_stem}_N.mp4 또는 live_*.mp4
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from cctv_intrusion.intrusion.criteria import (
    EVENT_CLIP_AFTER_SEC,
    EVENT_CLIP_BEFORE_SEC,
    EVENT_CSV_FIELDS,
)
from cctv_intrusion.paths import OUTPUT_DIR, RECORDINGS_DIR

EVENTS_CSV_SUFFIX = ".csv"
CAM_EVENTS_CSV_NAME = "events.csv"


def format_video_timestamp(seconds: float) -> str:
    """영상 내 시각을 MM:SS.mmm 또는 H:MM:SS.mmm 문자열로 만든다."""
    total_ms = int(round(max(0.0, seconds) * 1000))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}.{ms:03d}"
    return f"{minutes:02d}:{secs:02d}.{ms:03d}"


def _optional_timestamp(seconds: float | None) -> str:
    return "" if seconds is None else format_video_timestamp(seconds)


def is_screen_recording_dir(directory: Path) -> bool:
    """recordings/camN/ 형태인지."""
    if directory.parent != RECORDINGS_DIR:
        return False
    name = directory.name
    return name.startswith("cam") and name[3:].isdigit()


@dataclass(slots=True)
class IntrusionEvent:
    """경보~해제까지 끝난 한 건의 침입 사건."""

    alarm_at: str
    cleared_at: str
    duration_sec: float
    clip_start: str
    clip_end: str
    zone_name: str
    zone_level: str
    alarm_sec: float
    cleared_sec: float
    clip_start_sec: float
    clip_end_sec: float
    clip_file: str = ""
    # 상시 녹화(.ts) 파일 기준 위치 — 대시보드에서 전체 녹화 대비 침입을 계산할 때 쓴다
    source_file: str = ""
    source_alarm_sec: float | None = None
    source_cleared_sec: float | None = None

    @classmethod
    def create(
        cls,
        *,
        alarm_sec: float,
        cleared_sec: float,
        zone_name: str,
        zone_level: str,
    ) -> IntrusionEvent:
        alarm_sec = max(0.0, alarm_sec)
        cleared_sec = max(alarm_sec, cleared_sec)
        clip_start_sec = max(0.0, alarm_sec - EVENT_CLIP_BEFORE_SEC)
        clip_end_sec = cleared_sec + EVENT_CLIP_AFTER_SEC
        return cls(
            alarm_at=format_video_timestamp(alarm_sec),
            cleared_at=format_video_timestamp(cleared_sec),
            duration_sec=round(cleared_sec - alarm_sec, 2),
            clip_start=format_video_timestamp(clip_start_sec),
            clip_end=format_video_timestamp(clip_end_sec),
            zone_name=zone_name,
            zone_level=zone_level,
            alarm_sec=alarm_sec,
            cleared_sec=cleared_sec,
            clip_start_sec=clip_start_sec,
            clip_end_sec=clip_end_sec,
        )

    def as_row(self) -> dict[str, str | float]:
        return {
            "alarm_at": self.alarm_at,
            "cleared_at": self.cleared_at,
            "duration_sec": self.duration_sec,
            "clip_start": self.clip_start,
            "clip_end": self.clip_end,
            "clip_file": self.clip_file,
            "zone_name": self.zone_name,
            "zone_level": self.zone_level,
            "source_file": self.source_file,
            "source_alarm_at": _optional_timestamp(self.source_alarm_sec),
            "source_cleared_at": _optional_timestamp(self.source_cleared_sec),
        }


def events_csv_path(
    video_path: str | Path,
    *,
    output_dir: Path | None = None,
) -> Path:
    """CSV 경로. recordings/camN/ 이면 events.csv, 그 외는 {stem}.csv."""
    directory = output_dir or OUTPUT_DIR
    if is_screen_recording_dir(directory):
        return directory / CAM_EVENTS_CSV_NAME
    stem = Path(video_path).stem
    return directory / f"{stem}{EVENTS_CSV_SUFFIX}"


def _upgrade_csv_header(path: Path) -> None:
    """예전 컬럼으로 만든 CSV 면 현재 컬럼으로 다시 쓴다 (없는 칸은 빈 값)."""
    if not path.exists() or path.stat().st_size == 0:
        return
    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        if tuple(reader.fieldnames or ()) == EVENT_CSV_FIELDS:
            return
        rows = list(reader)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(EVENT_CSV_FIELDS), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) or "" for field in EVENT_CSV_FIELDS})


def append_events(
    events: list[IntrusionEvent],
    video_path: str | Path,
    *,
    output_dir: Path | None = None,
) -> Path | None:
    """사건을 CSV 에 이어 쓴다. 파일이 없으면 헤더를 만든다."""
    if not events:
        return None

    path = events_csv_path(video_path, output_dir=output_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    _upgrade_csv_header(path)
    write_header = not path.exists() or path.stat().st_size == 0

    with path.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(EVENT_CSV_FIELDS))
        if write_header:
            writer.writeheader()
        for event in events:
            writer.writerow(event.as_row())

    return path
