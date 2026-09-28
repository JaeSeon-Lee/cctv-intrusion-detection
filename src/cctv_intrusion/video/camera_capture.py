from __future__ import annotations

import threading
import time

import cv2
import numpy as np

# 연속으로 이만큼 읽기에 실패하면 카메라 연결이 끊긴 것으로 본다 (약 3초)
MAX_READ_FAILURES = 100
RETRY_INTERVAL_SEC = 0.03


class CameraCapture:
    """웹캠 입력. VideoRender 와 같은 모양으로 쓸 수 있게 맞춘 래퍼.

    cv2.VideoCapture.read() 는 다음 프레임이 올 때까지 기다리므로 UI 스레드에서 부르면 화면이 끊긴다.
    그래서 별도 스레드가 계속 읽으며 가장 최근 프레임 하나만 들고 있고,
    read() 는 기다리지 않고 새 프레임이 있으면 돌려준다. (카메라 버퍼에 옛 프레임이 쌓이지도 않는다)
    """

    def __init__(self, index: int) -> None:
        self.index = index
        self.capture = cv2.VideoCapture(index)
        self.lock = threading.Lock()
        self.latest: np.ndarray | None = None
        self.lost = False  # 카메라 연결이 끊겼는지
        self.running = False
        self.thread: threading.Thread | None = None

    def is_opened(self) -> bool:
        return self.capture.isOpened()

    def start(self) -> None:
        self.running = True
        self.thread = threading.Thread(target=self._run, name="camera-capture", daemon=True)
        self.thread.start()

    def _run(self) -> None:
        failures = 0
        while self.running:
            ok, frame = self.capture.read()
            if not ok or frame is None:
                failures += 1
                if failures >= MAX_READ_FAILURES:
                    self.lost = True
                    return
                time.sleep(RETRY_INTERVAL_SEC)
                continue
            failures = 0
            with self.lock:
                self.latest = frame

    def read(self) -> tuple[bool, np.ndarray | None]:
        """새 프레임이 있으면 (True, frame), 아직 없으면 (False, None). 기다리지 않는다."""
        with self.lock:
            frame = self.latest
            self.latest = None
        return frame is not None, frame

    def get_fps(self) -> float:
        return float(self.capture.get(cv2.CAP_PROP_FPS) or 0)

    def get_frame_size(self) -> tuple[int, int]:
        return (
            int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        )

    def get_frame_count(self) -> int:
        return 0

    def release(self) -> None:
        self.running = False
        if self.thread is not None:
            self.thread.join()
            self.thread = None
        self.capture.release()
