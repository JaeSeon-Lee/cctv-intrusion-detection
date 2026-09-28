"""실시간(웹캠) 침입 사건 클립 녹화.

실시간 영상은 원본 파일이 없어 나중에 구간을 잘라낼 수 없다.
그래서 최근 프레임을 버퍼(JPEG 압축)에 들고 있다가 경보가 울리면 그때부터 파일로 쓴다.

- 경보 이전 3초: 버퍼에서 꺼내 쓴다
- 경보 해제 이후 5초: 계속 쓰다가 닫는다 (그 사이 다시 경보가 울리면 같은 클립에 이어 쓴다)
- 클립: OUTPUT_DIR / 'live_YYYYmmdd_HHMMSS.mp4' (녹화 시작 시각)
- CSV: 클립과 같은 이름의 .csv. 시각은 클립 영상 안의 시각이다 (저장된 동영상 CSV 와 같은 방식)
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from cctv_intrusion.intrusion.clip_export import CLIP_SUFFIX
from cctv_intrusion.intrusion.criteria import EVENT_CLIP_AFTER_SEC, EVENT_CLIP_BEFORE_SEC
from cctv_intrusion.intrusion.events import IntrusionEvent, append_events, events_csv_path
from cctv_intrusion.paths import OUTPUT_DIR

LIVE_CLIP_PREFIX = "live"
# 경보 판정은 사람 탐지가 끝난 뒤에 오므로(CPU 에서 수백 ms), 그만큼 버퍼를 더 들고 있는다
BUFFER_MARGIN_SEC = 2.0
DEFAULT_FPS = 30.0
MAX_FPS = 60.0
JPEG_QUALITY = 90
_FOURCC = cv2.VideoWriter_fourcc(*"mp4v")


def live_clip_path(
    started_at: datetime,
    *,
    output_dir: Path | None = None,
) -> Path:
    """'live_YYYYmmdd_HHMMSS.mp4' 경로. 같은 초에 이미 있으면 '_2', '_3' 을 붙인다."""
    directory = output_dir or OUTPUT_DIR
    directory.mkdir(parents=True, exist_ok=True)
    stem = f"{LIVE_CLIP_PREFIX}_{started_at:%Y%m%d_%H%M%S}"
    path = directory / f"{stem}{CLIP_SUFFIX}"
    index = 2
    while path.exists() or events_csv_path(path, output_dir=directory).exists():
        path = directory / f"{stem}_{index}{CLIP_SUFFIX}"
        index += 1
    return path


class LiveRecorder:
    """실시간 프레임과 경보 상태를 받아 사건 클립 + CSV 를 만든다.

    사용법 (time_sec: 실시간 영상을 연결한 뒤 흐른 시각(초)):
      recorder.add_frame(frame, time_sec)             # 화면에 나오는 모든 프레임
      recorder.update(alarm_active, time_sec, events) # 사람 탐지 결과가 나올 때마다
      recorder.finish(monitor.close_alarms())         # 연결을 끊을 때
    """

    def __init__(
        self,
        *,
        output_dir: Path | None = None,
        clock: Callable[[], datetime] = datetime.now,
    ) -> None:
        self.output_dir = output_dir
        self.clock = clock
        self.buffer: deque[tuple[float, np.ndarray]] = deque()  # (시각, JPEG 바이트)
        self.clip_path: Path | None = None
        self.clip_start_sec = 0.0
        self.clip_fps = DEFAULT_FPS
        self.stop_at_sec: float | None = None
        self.events: list[IntrusionEvent] = []
        self.writer: cv2.VideoWriter | None = None
        self.written = 0

    @property
    def recording(self) -> bool:
        return self.clip_path is not None

    def add_frame(self, frame: np.ndarray, time_sec: float) -> Path | None:
        """프레임을 버퍼나 클립에 넣는다. 이 프레임으로 클립이 끝나면 CSV 경로를 반환한다."""
        if self.recording:
            self._write(frame)
            if self.stop_at_sec is not None and time_sec >= self.stop_at_sec:
                return self.finish()
            return None

        ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        if ok:
            self.buffer.append((time_sec, encoded))
        keep_from = time_sec - EVENT_CLIP_BEFORE_SEC - BUFFER_MARGIN_SEC
        while self.buffer and self.buffer[0][0] < keep_from:
            self.buffer.popleft()
        return None

    def update(
        self,
        alarm_active: bool,
        time_sec: float,
        events: list[IntrusionEvent],
    ) -> None:
        """사람 탐지 결과마다 호출한다. time_sec 은 탐지한 프레임의 시각."""
        if alarm_active:
            if not self.recording:
                self._start(time_sec)
            self.stop_at_sec = None
        elif self.recording and self.stop_at_sec is None:
            self.stop_at_sec = time_sec + EVENT_CLIP_AFTER_SEC

        if self.recording:
            self.events.extend(events)

    def finish(self, events: list[IntrusionEvent] | None = None) -> Path | None:
        """녹화 중인 클립을 닫고 사건을 CSV 에 기록한다. 기록한 CSV 경로를 반환한다.

        events: 아직 해제되지 않았지만 여기서 끝난 것으로 기록할 사건 (연결을 끊을 때)
        """
        if not self.recording:
            return None

        clip_path = self.clip_path
        clip_start_sec = self.clip_start_sec
        events = self.events + list(events or [])
        written = self.written
        if self.writer is not None:
            self.writer.release()
        self.clip_path = None
        self.writer = None
        self.written = 0
        self.stop_at_sec = None
        self.events = []

        if written == 0:
            return None

        rows = []
        for event in events:
            row = IntrusionEvent.create(
                alarm_sec=event.alarm_sec - clip_start_sec,
                cleared_sec=event.cleared_sec - clip_start_sec,
                zone_name=event.zone_name,
                zone_level=event.zone_level,
            )
            row.clip_file = clip_path.name
            rows.append(row)
        return append_events(rows, clip_path, output_dir=clip_path.parent)

    def _start(self, alarm_sec: float) -> None:
        start_from = alarm_sec - EVENT_CLIP_BEFORE_SEC
        frames = [(sec, data) for sec, data in self.buffer if sec >= start_from]
        self.buffer.clear()

        self.clip_path = live_clip_path(self.clock(), output_dir=self.output_dir)
        self.clip_start_sec = frames[0][0] if frames else alarm_sec
        self.clip_fps = estimate_fps([sec for sec, _ in frames])
        for _, data in frames:
            self._write(cv2.imdecode(data, cv2.IMREAD_COLOR))

    def _write(self, frame: np.ndarray) -> None:
        if self.writer is None:
            height, width = frame.shape[:2]
            writer = cv2.VideoWriter(str(self.clip_path), _FOURCC, self.clip_fps, (width, height))
            if not writer.isOpened():
                writer.release()
                path = self.clip_path
                self.clip_path = None
                self.events = []
                raise OSError(f"클립 파일을 만들 수 없습니다: {path}")
            self.writer = writer
        self.writer.write(frame)
        self.written += 1


def estimate_fps(times: list[float]) -> float:
    """버퍼 프레임 시각으로 실제 초당 프레임 수를 구한다. 웹캠이 알려주는 fps 는 틀릴 때가 많다."""
    if len(times) < 2 or times[-1] <= times[0]:
        return DEFAULT_FPS
    fps = (len(times) - 1) / (times[-1] - times[0])
    return min(max(fps, 1.0), MAX_FPS)
