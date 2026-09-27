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
    """워커 스레드 안에서 모델을 불러오고 추론만 하는 객체. PersonDetection 이 만들어서 쓴다."""

    loaded = Signal(str)  # 모델 로딩 완료: 사용하는 장치 ("cpu" / "cuda:0")
    load_failed = Signal(str)  # 모델 로딩 실패: 오류 메시지
    # 추론 완료: (세대 번호, 프레임 번호, list[Detection])
    detected = Signal(int, int, object)

    def __init__(self, detector_factory: DetectorFactory) -> None:
        super().__init__()
        self.detector_factory = detector_factory
        self.detector = None

    @Slot()
    def load(self) -> None:
        # 모델 파일이 없으면 여기서 내려받기까지 하므로 오래 걸릴 수 있다
        try:
            self.detector = self.detector_factory()
        except (OSError, RuntimeError, ValueError) as error:
            logger.exception("YOLO 모델을 불러오지 못했습니다.")
            self.load_failed.emit(str(error))
            return
        self.loaded.emit(self.detector.device)

    @Slot(int, int, object)
    def detect(self, generation: int, frame_index: int, frame: np.ndarray) -> None:
        detections = []
        if self.detector is not None:
            try:
                detections = self.detector.detect(frame)
            except RuntimeError:
                # 한 프레임 추론이 실패해도 다음 프레임은 계속 처리하도록 빈 결과로 넘긴다
                logger.exception("%d번 프레임 사람 탐지 실패", frame_index)
        # 실패해도 반드시 detected 를 보낸다. PersonDetection 이 이걸 받아야 다음 프레임을 보낸다
        self.detected.emit(generation, frame_index, detections)


class PersonDetection(QObject):
    """UI 스레드 쪽 창구. 프레임을 넘기면 워커 스레드에서 사람을 찾아 결과를 Signal로 알려준다.

    사용법:
      detection = PersonDetection()
      detection.start()                                  # 워커 스레드 시작 + 모델 로딩
      video_widget.frame_ready.connect(detection.submit) # 프레임마다 탐지 요청
      detection.detected.connect(...)                    # 결과 받기
      detection.stop()                                   # 앱 종료 시

    Signals:
      ready(str)             : 모델 로딩 완료 (사용 장치 "cpu" / "cuda:0")
      failed(str)            : 모델 로딩 실패 (오류 메시지). 이후 submit 은 무시된다
      detected(int, list)    : (프레임 번호, list[Detection]) 좌표는 원본 프레임 픽셀
    """

    ready = Signal(str)
    failed = Signal(str)
    detected = Signal(int, object)  # object: list[Detection]

    # 워커에게 추론 요청 (내부용): (세대 번호, 프레임 번호, BGR 프레임)
    request = Signal(int, int, object)

    def __init__(self, detector_factory: DetectorFactory = PersonDetector) -> None:
        super().__init__()
        self.available = True  # 모델 로딩에 실패하면 False
        self.busy = False  # 워커가 추론(또는 모델 로딩) 중인지
        self.pending = None  # 추론 중에 들어온 가장 최근 프레임 (frame, frame_index)
        # 영상을 바꿀 때마다 1씩 올린다. 이전 영상 프레임의 결과가 늦게 도착하면 세대가 달라서 버린다
        self.generation = 0

        # QThread: 이벤트 루프를 가진 별도 스레드. moveToThread 한 객체의 Slot은 그 스레드에서 실행된다.
        # 다른 스레드 객체로의 Signal 연결은 자동으로 queued(이벤트 큐로 전달) 방식이 된다.
        self.thread = QThread()
        self.worker = DetectionWorker(detector_factory)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.load)
        self.request.connect(self.worker.detect)
        self.worker.loaded.connect(self.on_loaded)
        self.worker.load_failed.connect(self.on_load_failed)
        self.worker.detected.connect(self.on_worker_detected)

    def start(self) -> None:
        # 모델 로딩이 끝날 때까지 들어오는 프레임은 pending 에 최신 것만 남겨뒀다가 로딩 후 바로 처리한다
        self.busy = True
        self.thread.start()

    def stop(self) -> None:
        # 진행 중인 추론(또는 모델 내려받기)이 끝날 때까지 기다린 뒤 스레드를 종료한다
        self.thread.quit()
        self.thread.wait()

    def reset(self) -> None:
        # 새 영상을 열 때 호출: 기다리던 프레임과 진행 중인 이전 영상의 결과를 버린다
        self.generation += 1
        self.pending = None

    @Slot(object, int)
    def submit(self, frame: np.ndarray, frame_index: int) -> None:
        # 탐지 요청. VideoWidget.frame_ready 에 연결한다
        if not self.available:
            return
        # frame 은 다른 모듈이 그 위에 그릴 수도 있으므로 복사본을 워커에게 넘긴다
        if self.busy:
            self.pending = (frame.copy(), frame_index)
            return
        self.send(frame.copy(), frame_index)

    def send(self, frame: np.ndarray, frame_index: int) -> None:
        self.busy = True
        self.request.emit(self.generation, frame_index, frame)

    def send_pending(self) -> None:
        # 기다리던 프레임이 있으면 보내고, 없으면 쉬는 상태로
        if self.pending is None:
            self.busy = False
            return
        frame, frame_index = self.pending
        self.pending = None
        self.send(frame, frame_index)

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

    @Slot(int, int, object)
    def on_worker_detected(
        self, generation: int, frame_index: int, detections: list[Detection]
    ) -> None:
        self.send_pending()
        if generation == self.generation:
            self.detected.emit(frame_index, detections)
