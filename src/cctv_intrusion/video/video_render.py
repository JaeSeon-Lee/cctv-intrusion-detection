import cv2


class VideoRender:
    def __init__(self, path):
        self.path = path
        self.capture = cv2.VideoCapture(path)

    def is_opened(self):
        # 파일이 없거나 코덱을 못 읽으면 False
        return self.capture.isOpened()

    def read(self):
        return self.capture.read()

    def seek_frame(self, frame_number):
        self.capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number)

    def get_current_frame(self):
        return int(self.capture.get(cv2.CAP_PROP_POS_FRAMES))

    def get_fps(self):
        return self.capture.get(cv2.CAP_PROP_FPS)

    def get_frame_size(self):
        # 원본 프레임 크기 (너비, 높이)
        return (
            int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        )

    def get_frame_count(self):
        # 전체 프레임 수
        return int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT))

    def release(self):
        self.capture.release()
