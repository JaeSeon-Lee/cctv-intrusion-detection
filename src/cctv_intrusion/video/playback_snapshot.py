"""다시보기용 상시 녹화 스냅샷.

녹화 중인 `.ts` 를 OpenCV 로 그대로 열면, 연 순간의 길이만 읽고 바로 끝난다.
(MPEG-TS 는 스트림이라 쓰기와 읽기가 동시에 되긴 하지만, OpenCV 는 파일 끝을 따라가지 않는다.)

해결: 재생 직전에 현재까지 쓰인 내용의 스냅샷을 만들어 그 파일을 연다.
- macOS/APFS: `cp -c` (copy-on-write) → 용량·시간 거의 없음
- 그 외: 바이트 복사
닫힌 `.ts` 는 스냅샷 없이 원본을 그대로 연다.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_TEMP_PREFIX = "cctv_replay_"


def snapshot_for_playback(source: Path) -> Path:
    """현재 파일 내용의 재생용 스냅샷 경로를 만든다. 호출측이 삭제한다."""
    source = Path(source)
    if not source.is_file():
        raise OSError(f"녹화 파일이 없습니다: {source}")

    suffix = source.suffix or ".ts"
    fd, name = tempfile.mkstemp(prefix=_TEMP_PREFIX, suffix=suffix)
    os.close(fd)  # Windows 는 열린 파일을 지울 수 없다 (WinError 32)
    dest = Path(name)
    dest.unlink(missing_ok=True)

    if sys.platform == "darwin":
        # APFS copy-on-write — 대용량도 거의 즉시
        result = subprocess.run(
            ["cp", "-c", str(source), str(dest)],
            check=False,
            capture_output=True,
        )
        if result.returncode == 0 and dest.exists() and dest.stat().st_size > 0:
            return dest

    shutil.copyfile(source, dest)
    if not dest.exists() or dest.stat().st_size == 0:
        dest.unlink(missing_ok=True)
        raise OSError(f"재생용 스냅샷을 만들 수 없습니다: {source}")
    return dest


def cleanup_snapshot(path: Path | None) -> None:
    if path is None:
        return
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        pass
