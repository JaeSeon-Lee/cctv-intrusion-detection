"""CAM 화면 상시 녹화 (MPEG-TS).

ffmpeg 에 raw BGR 프레임을 stdin 으로 넘겨 `.ts` 로 저장한다.
MPEG-TS 는 스트림형이라 쓰기 중에도 다시보기에서 재생하기 쉽다.

파일: RECORDINGS_DIR / 'cam{N}_{YYYYmmdd_HHMMSS}.ts'
침입 사건 클립(OUTPUT_DIR 의 mp4)과 역할이 다르다.
오버레이(박스·구역·경보)는 호출 측에서 프레임에 그린 뒤 write 한다.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from cctv_intrusion.paths import RECORDINGS_DIR

CLIP_SUFFIX = ".ts"
DEFAULT_FPS = 30.0
MAX_FPS = 60.0


def recording_path(
    screen_index: int,
    started_at: datetime,
    *,
    recordings_dir: Path | None = None,
) -> Path:
    """'cam{N}_{YYYYmmdd_HHMMSS}.ts'. 같은 초에 있으면 '_2', '_3'."""
    directory = recordings_dir or RECORDINGS_DIR
    directory.mkdir(parents=True, exist_ok=True)
    stem = f"cam{screen_index}_{started_at:%Y%m%d_%H%M%S}"
    path = directory / f"{stem}{CLIP_SUFFIX}"
    index = 2
    while path.exists():
        path = directory / f"{stem}_{index}{CLIP_SUFFIX}"
        index += 1
    return path


def find_ffmpeg() -> str | None:
    return shutil.which("ffmpeg")


class ContinuousRecorder:
    """오버레이가 입혀진 BGR 프레임을 MPEG-TS 로 계속 쓴다."""

    def __init__(
        self,
        screen_index: int,
        width: int,
        height: int,
        fps: float,
        *,
        recordings_dir: Path | None = None,
        clock: Callable[[], datetime] = datetime.now,
        ffmpeg_bin: str | None = None,
    ) -> None:
        if width < 2 or height < 2:
            raise OSError(f"녹화할 수 없는 해상도입니다: {width}x{height}")

        # yuv420p 는 짝수 해상도 필요
        self.width = width - (width % 2)
        self.height = height - (height % 2)
        if self.width < 2 or self.height < 2:
            raise OSError(f"녹화할 수 없는 해상도입니다: {width}x{height}")

        self.fps = min(max(float(fps) if fps and fps > 0 else DEFAULT_FPS, 1.0), MAX_FPS)
        self.screen_index = screen_index
        self.path = recording_path(screen_index, clock(), recordings_dir=recordings_dir)
        self.written = 0
        self._proc: subprocess.Popen[bytes] | None = None

        ffmpeg = ffmpeg_bin or find_ffmpeg()
        if not ffmpeg:
            raise OSError("ffmpeg 을 찾을 수 없습니다. 상시 녹화에는 ffmpeg 이 필요합니다.")

        command = [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "-s",
            f"{self.width}x{self.height}",
            "-r",
            f"{self.fps:.3f}",
            "-i",
            "pipe:0",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-tune",
            "zerolatency",
            "-crf",
            "28",
            "-pix_fmt",
            "yuv420p",
            "-g",
            "30",
            "-flush_packets",
            "1",
            "-f",
            "mpegts",
            str(self.path),
        ]
        try:
            self._proc = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        except OSError as error:
            raise OSError(f"ffmpeg 을 시작할 수 없습니다: {error}") from error

        if self._proc.stdin is None:
            self._cleanup_failed_start()
            raise OSError(f"녹화 파이프를 열 수 없습니다: {self.path}")

    @property
    def recording(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def write(self, frame: np.ndarray) -> None:
        if self._proc is None or self._proc.stdin is None:
            return
        if self._proc.poll() is not None:
            err = self._read_stderr()
            self._proc = None
            raise OSError(f"상시 녹화가 중단되었습니다: {self.path}\n{err}".strip())

        if frame.ndim != 3 or frame.shape[2] != 3:
            raise OSError(f"BGR 프레임이 아닙니다: shape={frame.shape}")

        height, width = frame.shape[:2]
        if width != self.width or height != self.height:
            frame = cv2.resize(frame, (self.width, self.height), interpolation=cv2.INTER_AREA)
        if not frame.flags["C_CONTIGUOUS"]:
            frame = np.ascontiguousarray(frame)

        try:
            self._proc.stdin.write(frame.tobytes())
            # 디스크에 빨리 보이도록 파이프를 자주 비운다 (쓰기 중 재생)
            if self.written % 5 == 0:
                self._proc.stdin.flush()
        except BrokenPipeError as error:
            err = self._read_stderr()
            self.close()
            raise OSError(f"상시 녹화 쓰기에 실패했습니다: {self.path}\n{err}".strip()) from error
        self.written += 1

    def close(self) -> Path | None:
        """녹화를 끝내고 파일 경로를 반환한다. 프레임이 없으면 파일을 지운다."""
        proc = self._proc
        self._proc = None
        if proc is None:
            return None

        stderr = b""
        try:
            if proc.stdin is not None:
                try:
                    proc.stdin.flush()
                except Exception:
                    pass
                proc.stdin.close()
            stderr = proc.stderr.read() if proc.stderr is not None else b""
            proc.wait(timeout=30)
        except Exception:
            proc.kill()
            try:
                proc.wait(timeout=5)
            except Exception:
                pass

        if self.written == 0:
            self.path.unlink(missing_ok=True)
            return None

        if proc.returncode not in (0, None) and self.written > 0:
            message = stderr.decode("utf-8", errors="replace").strip()
            if message:
                raise OSError(f"상시 녹화 종료 오류 (프레임 {self.written}): {message}")

        return self.path if self.path.exists() else None

    def _read_stderr(self) -> str:
        if self._proc is None or self._proc.stderr is None:
            return ""
        try:
            return self._proc.stderr.read().decode("utf-8", errors="replace").strip()
        except Exception:
            return ""

    def _cleanup_failed_start(self) -> None:
        if self._proc is not None:
            try:
                self._proc.kill()
                self._proc.wait(timeout=5)
            except Exception:
                pass
            self._proc = None
        self.path.unlink(missing_ok=True)
