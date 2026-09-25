from pathlib import Path

import cv2


class VideoRender:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.capture = cv2.VideoCapture(str(self.path))

    def is_opened(self) -> bool:
        return self.capture.isOpened()

    def read(self):
        return self.capture.read()

    def rewind(self) -> None:
        self.capture.set(cv2.CAP_PROP_POS_FRAMES, 0)

    def seek_frame(self, frame_number: int) -> None:
        self.capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number)

    def get_current_frame(self) -> int:
        return int(self.capture.get(cv2.CAP_PROP_POS_FRAMES))

    def get_fps(self) -> float:
        return float(self.capture.get(cv2.CAP_PROP_FPS) or 0)

    def release(self) -> None:
        self.capture.release()
