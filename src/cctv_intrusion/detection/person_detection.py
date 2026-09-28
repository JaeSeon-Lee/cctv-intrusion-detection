# 사람 탐지를 워커 스레드에서 돌린다.
#
# 추론(CPU 기준 프레임당 약 40ms)을 UI 스레드에서 하면 재생·버튼이 멈추므로 QThread로 분리한다.
# 재생 속도가 추론보다 빠르면 프레임이 쌓이는데, 밀린 프레임을 다 처리하면 박스가 점점 늦게 나오므로
# "추론 중에 들어온 프레임은 가장 최근 것 하나만" 남기고 나머지는 건너뛴다.
import logging
from collections.abc import Callable

import numpy as np
from PySide6.QtCore import QObject, QThread, Signal, Slot

from cctv_intrusion.detection.person_detector import Detection, PersonDetector

logger = logging.getLogger(__name__)

type DetectorFactory = Callable[[], PersonDetector]


class DetectionWorker(QObject):
    """워커 스레드 안에서 모델을 불러오고 추론만 하는 객체."""

    loaded = Signal(str)
    load_failed = Signal(str)
    # (세대, screen_id, frame_index, detections)
    detected = Signal(int, int, int, object)

    def __init__(self, detector_factory: DetectorFactory) -> None:
        super().__init__()
        self.detector_factory = detector_factory
        self.detector = None

    @Slot()
    def load(self) -> None:
        try:
            self.detector = self.detector_factory()
        except (OSError, RuntimeError, ValueError) as error:
            logger.exception("YOLO 모델을 불러오지 못했습니다.")
            self.load_failed.emit(str(error))
            return
        self.loaded.emit(self.detector.device)

    @Slot(int, int, int, object)
    def detect(
        self, generation: int, screen_id: int, frame_index: int, frame: np.ndarray
    ) -> None:
        detections = []
        if self.detector is not None:
            try:
                detections = self.detector.detect(frame)
            except RuntimeError:
                logger.exception("%d번 프레임 사람 탐지 실패", frame_index)
        self.detected.emit(generation, screen_id, frame_index, detections)


class PersonDetection(QObject):
    """UI 스레드 쪽 창구. screen_id 로 어느 CCTV 칸인지 구분한다.

    Signals:
      ready(str)
      failed(str)
      detected(int, int, list) : (screen_id, frame_index, detections)
    """

    ready = Signal(str)
    failed = Signal(str)
    detected = Signal(int, int, object)

    request = Signal(int, int, int, object)  # generation, screen_id, frame_index, frame

    def __init__(self, detector_factory: DetectorFactory = PersonDetector) -> None:
        super().__init__()
        self.available = True
        self.busy = False
        self.pending = None  # (frame, frame_index, screen_id)
        self.generation = 0

        self.thread = QThread()
        self.worker = DetectionWorker(detector_factory)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.load)
        self.request.connect(self.worker.detect)
        self.worker.loaded.connect(self.on_loaded)
        self.worker.load_failed.connect(self.on_load_failed)
        self.worker.detected.connect(self.on_worker_detected)

    def start(self) -> None:
        self.busy = True
        self.thread.start()

    def stop(self) -> None:
        self.thread.quit()
        self.thread.wait()

    def reset(self) -> None:
        self.generation += 1
        self.pending = None

    def submit(self, frame: np.ndarray, frame_index: int, screen_id: int = 0) -> None:
        if not self.available:
            return
        if self.busy:
            self.pending = (frame.copy(), frame_index, screen_id)
            return
        self.send(frame.copy(), frame_index, screen_id)

    def send(self, frame: np.ndarray, frame_index: int, screen_id: int) -> None:
        self.busy = True
        self.request.emit(self.generation, screen_id, frame_index, frame)

    def send_pending(self) -> None:
        if self.pending is None:
            self.busy = False
            return
        frame, frame_index, screen_id = self.pending
        self.pending = None
        self.send(frame, frame_index, screen_id)

    @Slot(str)
    def on_loaded(self, device: str) -> None:
        logger.info("사람 탐지 모델 로딩 완료 (장치: %s)", device)
        self.ready.emit(device)
        self.send_pending()

    @Slot(str)
    def on_load_failed(self, message: str) -> None:
        self.available = False
        self.busy = False
        self.pending = None
        self.failed.emit(message)

    @Slot(int, int, int, object)
    def on_worker_detected(
        self,
        generation: int,
        screen_id: int,
        frame_index: int,
        detections: list[Detection],
    ) -> None:
        self.send_pending()
        if generation == self.generation:
            self.detected.emit(screen_id, frame_index, detections)
