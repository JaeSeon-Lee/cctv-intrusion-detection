"""상시 녹화(.ts)에서 침입 구간을 잘라 MP4 + CSV 로 남긴다.

프레임 JPEG 버퍼·별도 VideoWriter 없이 ContinuousRecorder 파일만 사용한다.
- 경보 전 3초 ~ 해제 후 5초
- 해제 후 5초 안에 다시 경보가 나면 같은 클립 구간을 늘린다
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from cctv_intrusion.intrusion.criteria import EVENT_CLIP_AFTER_SEC, EVENT_CLIP_BEFORE_SEC
from cctv_intrusion.intrusion.events import IntrusionEvent, append_events
from cctv_intrusion.paths import RECORDINGS_DIR
from cctv_intrusion.video.playback_snapshot import cleanup_snapshot, snapshot_for_playback

CLIP_SUFFIX = ".mp4"
LIVE_CLIP_PREFIX = "live"

logger = logging.getLogger(__name__)


def find_ffmpeg() -> str | None:
    return shutil.which("ffmpeg")


def live_clip_path(
    started_at: datetime,
    *,
    output_dir: Path | None = None,
) -> Path:
    """live_YYYYmmdd_HHMMSS.mp4 경로. 같은 초 파일이 있으면 _2, _3 …

    camN/ 의 events.csv 는 캠 공유 파일이라 존재 여부로 루프하면 안 된다.
    (예전에 events.csv 가 있으면 while 이 무한 반복되어 UI/클립 스레드가 멈췄다)
    """
    directory = output_dir or RECORDINGS_DIR
    directory.mkdir(parents=True, exist_ok=True)
    stem = f"{LIVE_CLIP_PREFIX}_{started_at:%Y%m%d_%H%M%S}"
    path = directory / f"{stem}{CLIP_SUFFIX}"
    index = 2
    while path.exists():
        path = directory / f"{stem}_{index}{CLIP_SUFFIX}"
        index += 1
        if index > 10_000:
            raise OSError(f"클립 파일명을 만들 수 없습니다: {directory}")
    return path


def cut_clip_from_recording(
    source: Path,
    *,
    start_sec: float,
    duration_sec: float,
    output: Path,
    ffmpeg_bin: str | None = None,
) -> Path:
    """상시 녹화 파일에서 [start_sec, start_sec+duration) 를 MP4 로 저장.

    `-ss` 를 입력 앞에 둬 긴 .ts 전체를 디코드하지 않는다.
    (입력 뒤 `-ss` 는 긴 녹화에서 수십 초~수 분 걸릴 수 있음)
    """
    ffmpeg = ffmpeg_bin or find_ffmpeg()
    if not ffmpeg:
        raise OSError("ffmpeg 을 찾을 수 없습니다. 침입 클립 저장에 필요합니다.")
    if not source.exists():
        raise OSError(f"상시 녹화 파일이 없습니다: {source}")
    if duration_sec <= 0:
        raise OSError("클립 길이가 0 이하입니다.")

    output.parent.mkdir(parents=True, exist_ok=True)
    start_sec = max(0.0, start_sec)
    output.unlink(missing_ok=True)
    command = [
        ffmpeg,
        "-y",
        "-loglevel",
        "error",
        "-ss",
        f"{start_sec:.3f}",
        "-i",
        str(source),
        "-t",
        f"{duration_sec:.3f}",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "28",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output),
    ]
    logger.info(
        "ffmpeg 클립 자르기 시작 source=%s start=%.2fs dur=%.2fs out=%s size=%s",
        source.name,
        start_sec,
        duration_sec,
        output.name,
        source.stat().st_size if source.exists() else 0,
    )
    t0 = time.perf_counter()
    try:
        result = subprocess.run(command, check=False, capture_output=True, timeout=180)
    except subprocess.TimeoutExpired as error:
        output.unlink(missing_ok=True)
        raise OSError(f"침입 클립 생성 시간 초과(180s): {source}") from error
    except OSError as error:
        raise OSError(f"침입 클립을 만들 수 없습니다: {error}") from error
    elapsed = time.perf_counter() - t0
    if result.returncode != 0 or not output.exists() or output.stat().st_size == 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        output.unlink(missing_ok=True)
        logger.error("ffmpeg 클립 실패 %.1fs: %s", elapsed, message)
        raise OSError(f"침입 클립 생성 실패: {source} → {output}\n{message}".strip())
    logger.info(
        "ffmpeg 클립 완료 %.1fs out=%s bytes=%d",
        elapsed,
        output.name,
        output.stat().st_size,
    )
    return output


@dataclass(slots=True)
class ClipExportJob:
    """백그라운드에서 돌릴 클립 저장 작업."""

    source: Path
    origin_video_sec: float
    events: list[IntrusionEvent]
    last_time_sec: float
    output_dir: Path
    started_at: datetime
    ffmpeg_bin: str | None = None


def run_clip_export(job: ClipExportJob) -> Path | None:
    """스냅샷 → 구간 자르기 → CSV. UI 스레드에서 호출하지 말 것."""
    if not job.events:
        return None

    clip_start = min(event.clip_start_sec for event in job.events)
    clip_end = max(event.clip_end_sec for event in job.events)
    available_end = max(job.last_time_sec, max(event.cleared_sec for event in job.events))
    clip_end = min(clip_end, available_end)
    file_start = max(0.0, clip_start - job.origin_video_sec)
    duration = max(0.1, clip_end - clip_start)

    clip_path = live_clip_path(job.started_at, output_dir=job.output_dir)
    logger.info(
        "클립 export 시작 events=%d file_start=%.2f dur=%.2f source=%s",
        len(job.events),
        file_start,
        duration,
        job.source,
    )
    t0 = time.perf_counter()
    snap = snapshot_for_playback(job.source)
    try:
        logger.info(
            "스냅샷 완료 %.2fs bytes=%d",
            time.perf_counter() - t0,
            snap.stat().st_size,
        )
        cut_clip_from_recording(
            snap,
            start_sec=file_start,
            duration_sec=duration,
            output=clip_path,
            ffmpeg_bin=job.ffmpeg_bin,
        )
    finally:
        cleanup_snapshot(snap)

    rows = []
    for event in job.events:
        row = IntrusionEvent.create(
            alarm_sec=event.alarm_sec - clip_start,
            cleared_sec=event.cleared_sec - clip_start,
            zone_name=event.zone_name,
            zone_level=event.zone_level,
        )
        row.clip_file = clip_path.name
        rows.append(row)
    csv_path = append_events(rows, clip_path, output_dir=clip_path.parent)
    logger.info(
        "클립 export 전체 %.1fs clip=%s csv=%s",
        time.perf_counter() - t0,
        clip_path.name,
        csv_path,
    )
    return csv_path


class IntrusionClipper:
    """경보 상태를 받아 상시 녹화에서 클립을 자른다. 프레임을 받지 않는다."""

    def __init__(
        self,
        *,
        output_dir: Path,
        get_recording: Callable[[], object | None],
        clock: Callable[[], datetime] = datetime.now,
        ffmpeg_bin: str | None = None,
    ) -> None:
        self.output_dir = output_dir
        self.get_recording = get_recording
        self.clock = clock
        self.ffmpeg_bin = ffmpeg_bin
        self.stop_at_sec: float | None = None
        self.events: list[IntrusionEvent] = []
        self._last_time_sec = 0.0
        self._clip_open = False
        self._exporting = False

    @property
    def pending(self) -> bool:
        return self._clip_open or self._exporting

    def update(
        self,
        alarm_active: bool,
        time_sec: float,
        events: list[IntrusionEvent],
    ) -> None:
        self._last_time_sec = max(self._last_time_sec, float(time_sec))
        if alarm_active:
            self._clip_open = True
            self.stop_at_sec = None
        elif self._clip_open and self.stop_at_sec is None:
            self.stop_at_sec = time_sec + EVENT_CLIP_AFTER_SEC
            logger.info(
                "클립 종료 예약 stop_at=%.2fs (해제+%.0fs)",
                self.stop_at_sec,
                EVENT_CLIP_AFTER_SEC,
            )

        if self._clip_open:
            self.events.extend(events)

    def tick(self, time_sec: float) -> ClipExportJob | None:
        """종료 시각이 지나면 export 작업을 반환한다 (실제 자르기는 호출측 백그라운드)."""
        self._last_time_sec = max(self._last_time_sec, float(time_sec))
        if not self._clip_open or self.stop_at_sec is None:
            return None
        if time_sec < self.stop_at_sec:
            return None
        if self._exporting:
            # 이전 export 끝날 때까지 매 프레임 재시도/로그하지 않음
            return None
        logger.info("클립 저장 시점 도달 time=%.2fs (해제+%.0fs 후)", time_sec, EVENT_CLIP_AFTER_SEC)
        return self.take_export_job()

    def take_export_job(self, events: list[IntrusionEvent] | None = None) -> ClipExportJob | None:
        """상태를 비우고 백그라운드용 작업을 만든다."""
        if self._exporting:
            return None
        if not self._clip_open and not events:
            return None

        job_events = self.events + list(events or [])
        self._clip_open = False
        self.stop_at_sec = None
        self.events = []

        if not job_events:
            return None

        recording = self.get_recording()
        if recording is None:
            raise OSError("상시 녹화가 없어 침입 클립을 자를 수 없습니다.")

        flush = getattr(recording, "flush", None)
        if callable(flush):
            flush()

        self._exporting = True
        return ClipExportJob(
            source=Path(recording.path),
            origin_video_sec=float(getattr(recording, "origin_video_sec", 0.0) or 0.0),
            events=job_events,
            last_time_sec=self._last_time_sec,
            output_dir=self.output_dir,
            started_at=self.clock(),
            ffmpeg_bin=self.ffmpeg_bin,
        )

    def mark_export_done(self) -> None:
        self._exporting = False

    def finish(self, events: list[IntrusionEvent] | None = None) -> Path | None:
        """동기 저장 (연결 해제·앱 종료용)."""
        job = self.take_export_job(events)
        if job is None:
            return None
        try:
            return run_clip_export(job)
        finally:
            self.mark_export_done()


__all__ = [
    "EVENT_CLIP_AFTER_SEC",
    "EVENT_CLIP_BEFORE_SEC",
    "ClipExportJob",
    "IntrusionClipper",
    "LIVE_CLIP_PREFIX",
    "cut_clip_from_recording",
    "find_ffmpeg",
    "live_clip_path",
    "run_clip_export",
]
