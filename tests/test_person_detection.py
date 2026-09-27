import threading

import cv2
import numpy as np
import pytest

from cctv_intrusion.detection import Detection, PersonDetection, PersonDetector
from cctv_intrusion.detection.person_detector import MODEL_NAME
from cctv_intrusion.paths import INPUT_DIR, MODELS_DIR

SAMPLE_VIDEO = INPUT_DIR / "test_trespass.mp4"
FRAME = np.zeros((4, 4, 3), dtype=np.uint8)
TIMEOUT_MS = 5000


class FakeDetector:
    """모델 대신 쓰는 가짜 탐지기. gate 가 열릴 때까지 추론이 끝나지 않는다."""

    device = "cpu"

    def __init__(self):
        self.gate = threading.Event()
        self.seen = []  # 추론한 프레임의 첫 픽셀 값 (어떤 프레임을 처리했는지 확인용)

    def detect(self, frame):
        self.gate.wait(TIMEOUT_MS / 1000)
        self.seen.append(int(frame[0, 0, 0]))
        return [Detection(0, 0, 1, 1, 0.9)]


def frame_with(value):
    frame = FRAME.copy()
    frame[0, 0, 0] = value
    return frame


@pytest.fixture
def fake():
    return FakeDetector()


@pytest.fixture
def detection(qtbot, fake):
    detection = PersonDetection(lambda: fake)
    with qtbot.waitSignal(detection.ready, timeout=TIMEOUT_MS):
        detection.start()
    yield detection
    fake.gate.set()
    detection.stop()


def test_only_latest_frame_is_kept_while_busy(qtbot, detection, fake):
    # 1번 추론 중에 2, 3, 4번이 들어오면 4번만 남겨서 처리한다
    received = []
    detection.detected.connect(lambda index, _: received.append(index))

    for i in range(1, 5):
        detection.submit(frame_with(i), i)
    fake.gate.set()
    qtbot.waitUntil(lambda: len(received) == 2, timeout=TIMEOUT_MS)

    assert received == [1, 4]
    assert fake.seen == [1, 4]
    assert not detection.busy


def test_result_of_previous_video_is_dropped(qtbot, detection, fake):
    received = []
    detection.detected.connect(lambda index, _: received.append(index))

    detection.submit(frame_with(1), 1)
    detection.reset()  # 1번 추론 도중 새 영상을 연 상황
    detection.submit(frame_with(2), 0)
    fake.gate.set()
    qtbot.waitUntil(lambda: not detection.busy, timeout=TIMEOUT_MS)

    assert received == [0]
    assert fake.seen == [1, 2]


def test_submitted_frame_is_copied(qtbot, detection, fake):
    # 다른 모듈이 frame_ready 로 받은 프레임에 그림을 그려도 탐지에 영향이 없어야 한다
    frame = frame_with(7)
    detection.submit(frame, 0)
    frame[0, 0, 0] = 99
    fake.gate.set()
    qtbot.waitUntil(lambda: not detection.busy, timeout=TIMEOUT_MS)

    assert fake.seen == [7]


def test_load_failure_disables_detection(qtbot):
    def broken_factory():
        raise OSError("download failed")

    detection = PersonDetection(broken_factory)
    with qtbot.waitSignal(detection.failed, timeout=TIMEOUT_MS) as blocker:
        detection.start()
    detection.submit(FRAME, 0)
    detection.stop()

    assert blocker.args == ["download failed"]
    assert not detection.available
    assert not detection.busy


@pytest.mark.skipif(
    not (MODELS_DIR / MODEL_NAME).exists(),
    reason="YOLO 모델 파일이 없음 (앱을 한 번 실행하면 models/ 에 내려받아짐)",
)
def test_real_model_finds_person_in_sample_video():
    capture = cv2.VideoCapture(str(SAMPLE_VIDEO))
    ok, frame = capture.read()
    capture.release()
    assert ok

    detections = PersonDetector().detect(frame)

    # 샘플 영상 첫 프레임에는 화면 가운데 오른쪽에 사람이 한 명 있다
    assert len(detections) == 1
    person = detections[0]
    assert 700 < person.x1 < person.x2 < 900
    assert 250 < person.y1 < person.y2 < 450
    assert person.confidence >= 0.5
