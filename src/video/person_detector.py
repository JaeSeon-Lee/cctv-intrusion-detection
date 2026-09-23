import cv2
import numpy as np
from ultralytics import YOLO


class PersonDetector:
    def __init__(self, model_path: str = "yolov8n.pt", classes: list[int] = None, conf: float = 0.5):
        self.model = YOLO(model_path)
        self.classes = classes if classes is not None else [0]
        self.conf = conf

    def detect(self, frame: np.ndarray) -> np.ndarray:
        """프레임을 받아서 박스 좌표 배열(xyxy)을 반환"""
        results = self.model(frame, classes=self.classes, conf=self.conf, verbose=False)
        return results[0].boxes.xyxy.cpu().numpy()

    def draw(self, frame: np.ndarray, boxes: np.ndarray, color=(0, 0, 255), thickness: int = 2) -> np.ndarray:
        """박스를 프레임에 그려서 반환"""
        for box in boxes:
            x1, y1, x2, y2 = map(int, box)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
        return frame