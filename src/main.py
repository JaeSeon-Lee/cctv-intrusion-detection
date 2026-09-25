import os
import sys
from pathlib import Path

# conda OpenCV와 PyTorch가 libomp를 이중 로드함. torch를 cv2보다 먼저 붙여야 함
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["OMP_NUM_THREADS"] = "1"

import torch  # noqa: F401  # cv2보다 먼저
import cv2

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from danger import DangerWorkspace
from video import PersonDetector, VideoRender

WINDOW_NAME = "CCTV"
VIDEO_PATH = SRC_DIR.parent / "data" / "input" / "test_trespass.mp4"


def main() -> None:
    video = VideoRender(VIDEO_PATH)
    if not video.is_opened():
        raise FileNotFoundError(f"영상을 열 수 없습니다: {VIDEO_PATH}")

    person_detector = PersonDetector("yolov8n.pt", classes=[0, 1], conf=0.5)
    workspace = DangerWorkspace(WINDOW_NAME, VIDEO_PATH)

    while True:
        ret, frame = video.read()
        if not ret:
            video.rewind()
            continue

        boxes = person_detector.detect(frame)
        person_detector.draw(frame, boxes)
        canvas = workspace.render(frame)

        cv2.imshow(WINDOW_NAME, canvas)
        key = cv2.waitKey(1) & 0xFF
        if key == 27:
            break
        workspace.handle_key(key)

    video.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
