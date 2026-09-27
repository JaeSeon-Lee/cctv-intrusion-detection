"""침입 사건 클립 영상 저장.

경보 이전 3초 ~ 해제 이후 5초를 원본에서 잘라
OUTPUT_DIR / '{stem}_{n}.mp4' 로 저장한다.
"""

from __future__ import annotations

import math
from pathlib import Path

import cv2

from cctv_intrusion.intrusion.events import IntrusionEvent, append_events
from cctv_intrusion.paths import OUTPUT_DIR

CLIP_SUFFIX = ".mp4"
_FOURCC = cv2.VideoWriter_fourcc(*"mp4v")


def next_clip_path(
    video_path: str | Path,
    *,
    output_dir: Path | None = None,
) -> Path:
    """아직 없는 '{stem}_N.mp4' 경로를 반환한다."""
    stem = Path(video_path).stem
    directory = output_dir or OUTPUT_DIR
    directory.mkdir(parents=True, exist_ok=True)
    index = 1
    while True:
        path = directory / f"{stem}_{index}{CLIP_SUFFIX}"
        if not path.exists():
            return path
        index += 1


def export_event_clip(
    video_path: str | Path,
    event: IntrusionEvent,
    *,
    output_dir: Path | None = None,
) -> Path:
    """사건 클립 구간을 새 mp4 로 저장하고 경로를 반환한다."""
    source = Path(video_path)
    output = next_clip_path(source, output_dir=output_dir)

    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        capture.release()
        raise OSError(f"원본 영상을 열 수 없습니다: {source}")

    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        if fps <= 0:
            fps = 30.0
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

        start_frame = max(0, int(event.clip_start_sec * fps))
        end_frame = int(math.ceil(event.clip_end_sec * fps))
        if frame_count > 0:
            end_frame = min(end_frame, frame_count)
        if end_frame <= start_frame:
            end_frame = start_frame + 1
            if frame_count > 0:
                end_frame = min(end_frame, frame_count)

        writer = cv2.VideoWriter(str(output), _FOURCC, fps, (width, height))
        if not writer.isOpened():
            writer.release()
            raise OSError(f"클립 파일을 만들 수 없습니다: {output}")

        try:
            capture.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
            written = 0
            for _ in range(start_frame, end_frame):
                ok, frame = capture.read()
                if not ok or frame is None:
                    break
                writer.write(frame)
                written += 1
            if written == 0:
                raise OSError(f"클립에 쓸 프레임이 없습니다: {source}")
        finally:
            writer.release()
    finally:
        capture.release()

    return output


def save_event_records(
    events: list[IntrusionEvent],
    video_path: str | Path,
    *,
    output_dir: Path | None = None,
) -> Path | None:
    """클립을 만든 뒤 CSV 에 사건(클립 파일명 포함)을 기록한다."""
    if not events:
        return None

    for event in events:
        clip_path = export_event_clip(video_path, event, output_dir=output_dir)
        event.clip_file = clip_path.name

    return append_events(events, video_path, output_dir=output_dir)
