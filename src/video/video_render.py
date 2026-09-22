import cv2

class VideoRender:
    def __init__(self, path):
        self.path = path
        self.capture = cv2.VideoCapture(path)

    def read(self):
        return self.capture.read()

    def seek_frame(self, frame_number):
        self.capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number)

    def get_current_frame(self):
        return int(self.capture.get(cv2.CAP_PROP_POS_FRAMES))

    def get_fps(self):
        return self.capture.get(cv2.CAP_PROP_FPS)

    def release(self):
        self.capture.release()

    