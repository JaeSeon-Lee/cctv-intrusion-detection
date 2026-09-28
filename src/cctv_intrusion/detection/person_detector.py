# YOLO로 프레임 한 장에서 사람을 찾는다. (UI와 무관한 순수 추론 코드, 스레드 처리는 person_detection.py)
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from ultralytics import YOLO

from cctv_intrusion.paths import MODELS_DIR

# ultralytics 공식 모델 이름. MODELS_DIR 에 없으면 최초 1회 자동으로 내려받는다 (약 19MB)
MODEL_NAME = "yolo11s.pt"
PERSON_CLASS = 0  # COCO: person

# --- 담 넘는 자세(가림·가로 자세) 대응 ---
# test_trespass 약 24~25초: 서 있을 때 conf≈0.9 → 담 위에서는 최고점이 ≈0.19까지 떨어짐.
# 기존 0.30으로는 그 구간이 전부 탈락해서, 임계값을 그 아래로 내린다.
DEFAULT_CONFIDENCE = 0.15
# 입력 해상도. 클수록 부분만 보이는 몸도 특징이 살아남기 쉽다.
DEFAULT_IMGSZ = 1280
# NMS IoU. 담에 잘린 후보 박스가 서로 겹쳐도 너무 일찍 지우지 않게 한다.
DEFAULT_IOU = 0.45
# Test-Time Augmentation(좌우 반전 등 여러 번 추론 후 합침).
# 담 넘는 프레임에서 conf가 0.19→0.65 수준으로 회복되는 경우가 많아 켠다.
# 대가로 추론이 대략 2~3배 느려지지만, MPS면 실사용 가능한 수준이다.
DEFAULT_AUGMENT = True


@dataclass(slots=True, frozen=True)
class Detection:
    """탐지된 사람 한 명. 좌표는 원본 프레임 픽셀 기준 (x1, y1: 왼쪽 위 / x2, y2: 오른쪽 아래)"""

    x1: int
    y1: int
    x2: int
    y2: int
    confidence: float


def select_device() -> str:
    """가능하면 GPU/Apple Silicon, 아니면 CPU."""
    if torch.cuda.is_available():
        return "cuda:0"
    if getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


class PersonDetector:
    """YOLO 모델을 한 번 불러와서 프레임마다 사람 박스를 돌려준다.

    모델을 불러오는 데 시간이 걸리고 추론도 프레임당 수십 ms 걸리므로
    UI 스레드가 아니라 워커 스레드에서 만들고 사용한다 (PersonDetection 참고).
    """

    def __init__(
        self,
        model_path: Path = MODELS_DIR / MODEL_NAME,
        confidence: float = DEFAULT_CONFIDENCE,
        imgsz: int = DEFAULT_IMGSZ,
        iou: float = DEFAULT_IOU,
        augment: bool = DEFAULT_AUGMENT,
    ) -> None:
        self.device = select_device()
        self.confidence = confidence
        self.imgsz = imgsz
        self.iou = iou
        self.augment = augment
        # 파일이 없으면 ultralytics가 model_path 위치로 내려받는다 (cwd에 받지 않도록 전체 경로로 넘김)
        self.model = YOLO(str(model_path))

    def detect(self, frame: np.ndarray) -> list[Detection]:
        # frame: OpenCV BGR 프레임
        results = self.model(
            frame,
            classes=[PERSON_CLASS],
            conf=self.confidence,
            iou=self.iou,
            imgsz=self.imgsz,
            augment=self.augment,
            device=self.device,
            verbose=False,
        )
        boxes = results[0].boxes
        if boxes is None or len(boxes) == 0:
            return []
        return [
            Detection(round(x1), round(y1), round(x2), round(y2), confidence)
            for (x1, y1, x2, y2), confidence in zip(
                boxes.xyxy.tolist(), boxes.conf.tolist(), strict=True
            )
        ]
