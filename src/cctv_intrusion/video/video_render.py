from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


class VideoRender:
    """OpenCV VideoCapture 래퍼."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self.capture = cv2.VideoCapture(self.path)

    def is_opened(self) -> bool:
        return self.capture.isOpened()

    def read(self) -> tuple[bool, np.ndarray | None]:
        return self.capture.read()

    def seek_frame(self, frame_number: int) -> None:
        self.capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number)

    def get_current_frame(self) -> int:
        return int(self.capture.get(cv2.CAP_PROP_POS_FRAMES))

    def get_fps(self) -> float:
        return float(self.capture.get(cv2.CAP_PROP_FPS) or 0)

    def get_frame_size(self) -> tuple[int, int]:
        return (
            int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        )

    def get_frame_count(self) -> int:
        return int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT))

    def release(self) -> None:
        self.capture.release()
