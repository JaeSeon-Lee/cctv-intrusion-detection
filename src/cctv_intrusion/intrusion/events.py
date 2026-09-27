"""침입 사건 CSV 기록.

동영상 stem 과 같은 이름으로 OUTPUT_DIR 에 저장한다.
예: data/input/cam1.mp4 → data/output/cam1.csv

경보가 해제될 때 한 줄 기록:
  경보 시각 · 해제 시각 · 지속 · 클립 구간(−3s/+5s) · 구역
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
from cctv_intrusion.paths import OUTPUT_DIR

EVENTS_CSV_SUFFIX = ".csv"


def format_video_timestamp(seconds: float) -> str:
    """영상 내 시각을 MM:SS.mmm 또는 H:MM:SS.mmm 문자열로 만든다."""
    total_ms = int(round(max(0.0, seconds) * 1000))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}.{ms:03d}"
    return f"{minutes:02d}:{secs:02d}.{ms:03d}"


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
        clip_start = max(0.0, alarm_sec - EVENT_CLIP_BEFORE_SEC)
        clip_end = alarm_sec + EVENT_CLIP_AFTER_SEC
        return cls(
            alarm_at=format_video_timestamp(alarm_sec),
            cleared_at=format_video_timestamp(cleared_sec),
            duration_sec=round(cleared_sec - alarm_sec, 2),
            clip_start=format_video_timestamp(clip_start),
            clip_end=format_video_timestamp(clip_end),
            zone_name=zone_name,
            zone_level=zone_level,
        )

    def as_row(self) -> dict[str, str | float]:
        return {
            "alarm_at": self.alarm_at,
            "cleared_at": self.cleared_at,
            "duration_sec": self.duration_sec,
            "clip_start": self.clip_start,
            "clip_end": self.clip_end,
            "zone_name": self.zone_name,
            "zone_level": self.zone_level,
        }


def events_csv_path(
    video_path: str | Path,
    *,
    output_dir: Path | None = None,
) -> Path:
    """동영상과 같은 stem 의 CSV 경로 (OUTPUT_DIR / '{stem}.csv')."""
    stem = Path(video_path).stem
    return (output_dir or OUTPUT_DIR) / f"{stem}{EVENTS_CSV_SUFFIX}"


def append_events(
    events: list[IntrusionEvent],
    video_path: str | Path,
    *,
    output_dir: Path | None = None,
) -> Path | None:
    """사건을 해당 동영상 CSV 에 이어 쓴다. 파일이 없으면 헤더를 만든다."""
    if not events:
        return None

    path = events_csv_path(video_path, output_dir=output_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0

    with path.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(EVENT_CSV_FIELDS))
        if write_header:
            writer.writeheader()
        for event in events:
            writer.writerow(event.as_row())

    return path
