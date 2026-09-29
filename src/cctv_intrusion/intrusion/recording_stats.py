"""상시 녹화 대시보드용 통계.

녹화 파일(recordings/camN/{YYYYmmdd_HHMMSS}.ts)과 같은 폴더의 events.csv 에서
source_file 이 그 녹화인 행만 모아
녹화 길이 대비 침입 비율 · 침입 횟수 · 침입 당 지속 시간을 계산한다.
시각은 CSV 의 source_alarm_at / source_cleared_at (녹화 파일 기준)을 쓴다.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import cv2

from cctv_intrusion.intrusion.events import CAM_EVENTS_CSV_NAME


def parse_video_timestamp(text: str) -> float:
    """'MM:SS.mmm' 또는 'H:MM:SS.mmm' → 초. format_video_timestamp 의 역."""
    parts = text.strip().split(":")
    if not 2 <= len(parts) <= 3:
        raise ValueError(f"영상 시각 형식이 아닙니다: {text!r}")
    seconds = float(parts[-1])
    minutes = int(parts[-2])
    hours = int(parts[0]) if len(parts) == 3 else 0
    return hours * 3600 + minutes * 60 + seconds


@dataclass(slots=True, frozen=True)
class RecordingEvent:
    """CSV 한 줄 = 침입 한 건 (녹화 파일 기준 초)."""

    alarm_sec: float
    cleared_sec: float
    zone_name: str
    zone_level: str
    clip_file: str = ""

    @property
    def duration_sec(self) -> float:
        return max(0.0, self.cleared_sec - self.alarm_sec)


@dataclass(slots=True, frozen=True)
class RecordingStats:
    video_sec: float
    events: tuple[RecordingEvent, ...]
    # 같은 캠 CSV 에서 녹화 위치(source_*)가 없어 어느 녹화인지 알 수 없는 이전 기록 수
    unplaced_count: int = 0

    @property
    def count(self) -> int:
        return len(self.events)

    @property
    def durations(self) -> list[float]:
        return [event.duration_sec for event in self.events]

    @property
    def intrusion_sec(self) -> float:
        """겹치는 구간은 한 번만 센 침입 총 시간 (녹화 길이 안으로 자름)."""
        spans = sorted(
            (max(0.0, e.alarm_sec), min(self.video_sec, e.cleared_sec)) for e in self.events
        )
        total = 0.0
        cur_start = cur_end = None
        for start, end in spans:
            if end <= start:
                continue
            if cur_end is None or start > cur_end:
                if cur_end is not None:
                    total += cur_end - cur_start
                cur_start, cur_end = start, end
            else:
                cur_end = max(cur_end, end)
        if cur_end is not None:
            total += cur_end - cur_start
        return total

    @property
    def ratio_pct(self) -> float:
        if self.video_sec <= 0:
            return 0.0
        return min(100.0, self.intrusion_sec / self.video_sec * 100.0)

    @property
    def avg_sec(self) -> float:
        return sum(self.durations) / self.count if self.events else 0.0

    @property
    def max_sec(self) -> float:
        return max(self.durations, default=0.0)

    @property
    def min_sec(self) -> float:
        return min(self.durations, default=0.0)


def load_recording_events(recording_path: str | Path) -> tuple[list[RecordingEvent], int]:
    """녹화 폴더의 events.csv 에서 이 녹화의 사건을 읽는다.

    (사건 목록, 녹화 위치가 없어 제외한 이전 기록 수) 를 반환한다. CSV 가 없으면 ([], 0).
    """
    recording = Path(recording_path)
    csv_path = recording.parent / CAM_EVENTS_CSV_NAME
    if not csv_path.is_file():
        return [], 0

    events: list[RecordingEvent] = []
    unplaced = 0
    with csv_path.open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            source = (row.get("source_file") or "").strip()
            if not source:
                unplaced += 1
                continue
            if source != recording.name:
                continue
            try:
                alarm = parse_video_timestamp(row["source_alarm_at"])
                cleared = parse_video_timestamp(row["source_cleared_at"])
            except (KeyError, TypeError, ValueError):
                unplaced += 1
                continue
            events.append(
                RecordingEvent(
                    alarm_sec=alarm,
                    cleared_sec=max(alarm, cleared),
                    zone_name=(row.get("zone_name") or "").strip(),
                    zone_level=(row.get("zone_level") or "").strip(),
                    clip_file=(row.get("clip_file") or "").strip(),
                )
            )
    events.sort(key=lambda e: e.alarm_sec)
    return events, unplaced


def probe_video_duration(path: str | Path) -> float:
    """영상 길이(초). 읽지 못하면 0."""
    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            return 0.0
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        frames = float(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
        if fps <= 0 or frames <= 0:
            return 0.0
        return frames / fps
    finally:
        capture.release()


def recording_stats(
    recording_path: str | Path,
    *,
    video_path: str | Path | None = None,
) -> RecordingStats:
    """녹화 한 개의 대시보드 통계.

    video_path: 길이를 잴 파일 (녹화 중인 .ts 는 스냅샷을 넘긴다). 없으면 recording_path.
    길이를 못 읽으면 마지막 해제 시각으로 대신한다.
    """
    events, unplaced = load_recording_events(recording_path)
    video_sec = probe_video_duration(video_path or recording_path)
    if video_sec <= 0:
        video_sec = max((e.cleared_sec for e in events), default=0.0)
    return RecordingStats(video_sec=video_sec, events=tuple(events), unplaced_count=unplaced)
