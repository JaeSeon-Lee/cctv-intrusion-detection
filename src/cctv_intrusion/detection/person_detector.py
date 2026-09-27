# YOLO로 프레임 한 장에서 사람을 찾는다. (UI와 무관한 순수 추론 코드, 스레드 처리는 person_detection.py)
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from ultralytics import YOLO

from cctv_intrusion.paths import MODELS_DIR

# ultralytics 공식 모델 이름. MODELS_DIR 에 없으면 최초 1회 자동으로 내려받는다 (약 19MB)
# 샘플 영상 기준 yolo11n 은 CPU 33ms 지만 작은 사람을 자주 놓쳐서(탐지율 68%),
# 조금 느려도(약 70ms) 탐지율이 높은(91%) small 모델을 쓴다.
MODEL_NAME = "yolo11s.pt"
# COCO 데이터셋 클래스 번호: 0 = person
PERSON_CLASS = 0
# 이 신뢰도(0~1) 미만인 박스는 버린다.
# 0.5 는 담에 일부 가려진 사람을 많이 놓치고, 0.35 까지 낮춰도 샘플 영상에서 오탐이 없었다
DEFAULT_CONFIDENCE = 0.35


@dataclass(slots=True, frozen=True)
class Detection:
    """탐지된 사람 한 명. 좌표는 원본 프레임 픽셀 기준 (x1, y1: 왼쪽 위 / x2, y2: 오른쪽 아래)"""

    x1: int
    y1: int
    x2: int
    y2: int
    confidence: float


def select_device() -> str:
    # GPU(CUDA)를 쓸 수 있으면 GPU, 아니면 CPU. CPU 전용 torch를 설치했으면 항상 CPU
    return "cuda:0" if torch.cuda.is_available() else "cpu"


class PersonDetector:
    """YOLO 모델을 한 번 불러와서 프레임마다 사람 박스를 돌려준다.

    모델을 불러오는 데 시간이 걸리고 추론도 프레임당 수십 ms 걸리므로
    UI 스레드가 아니라 워커 스레드에서 만들고 사용한다 (PersonDetection 참고).
    """

    def __init__(
        self,
        model_path: Path = MODELS_DIR / MODEL_NAME,
        confidence: float = DEFAULT_CONFIDENCE,
    ) -> None:
        self.device = select_device()
        self.confidence = confidence
        # 파일이 없으면 ultralytics가 model_path 위치로 내려받는다 (실행 위치 cwd에 받지 않도록 전체 경로로 넘김)
        self.model = YOLO(str(model_path))

    def detect(self, frame: np.ndarray) -> list[Detection]:
        # frame: OpenCV BGR 프레임
        results = self.model(
            frame,
            classes=[PERSON_CLASS],
            conf=self.confidence,
            device=self.device,
            verbose=False,
        )
        boxes = results[0].boxes
        return [
            Detection(round(x1), round(y1), round(x2), round(y2), confidence)
            for (x1, y1, x2, y2), confidence in zip(
                boxes.xyxy.tolist(), boxes.conf.tolist(), strict=True
            )
        ]
