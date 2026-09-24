import cv2

# 스트림 연결/읽기 대기 시간 (ms). 너무 길면 연결 실패 시 화면이 오래 멈춘다.
STREAM_TIMEOUT_MS = 5000


class VideoRender:
    def __init__(self, path):
        # path: 파일 경로, 스트림 URL(rtsp://...), 또는 웹캠 번호(int)
        self.path = path

        if isinstance(path, str) and "://" in path:
            # 네트워크 스트림은 타임아웃을 지정해서 연다
            self.capture = cv2.VideoCapture(
                path,
                cv2.CAP_FFMPEG,
                [
                    cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,
                    STREAM_TIMEOUT_MS,
                    cv2.CAP_PROP_READ_TIMEOUT_MSEC,
                    STREAM_TIMEOUT_MS,
                ],
            )
        else:
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

    def get_frame_count(self):
        # 전체 프레임 수 (실시간 스트림은 0 또는 음수가 나올 수 있음)
        return int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT))

    def release(self):
        self.capture.release()
