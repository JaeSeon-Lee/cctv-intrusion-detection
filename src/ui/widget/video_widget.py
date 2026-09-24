from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QSizePolicy, QMessageBox
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from video import VideoRender

# FPS 정보를 못 읽었을 때 사용할 기본값
DEFAULT_FPS = 30

class VideoWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.render = None          # 현재 열린 VideoRender (없으면 None)
        self.fps = DEFAULT_FPS
        self.frame_index = -1       # 현재 화면에 표시 중인 프레임 번호
        self.current_pixmap = None  # 원본 크기 이미지 (창 크기가 바뀔 때 다시 축소하기 위해 보관)

        self.label = QLabel("동영상을 선택하세요.")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # QLabel은 기본적으로 이미지 크기만큼 커지려고 해서 창이 늘어나 버린다.
        # Ignored로 두면 레이아웃이 정해준 크기를 그대로 따르므로 이미지를 자유롭게 줄일 수 있다.
        self.label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)

        self.label.setStyleSheet("""
            QLabel {
                background-color: #000;
                color: #fff;
                font-size: 24px;
            }
        """)

        # QTimer: 지정한 간격(ms)마다 timeout 신호를 보내는 타이머.
        # timeout에 next_frame을 연결해서 FPS 간격으로 다음 프레임을 읽는다.
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.next_frame)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label)
        self.setLayout(layout)

    def set_video(self, path):
        # 파일 트리에서 파일을 선택했을 때 호출됨
        self.open_source(path)

    def open_source(self, source):
        # 기존 영상이 있으면 먼저 정리
        self.close_video()

        render = VideoRender(source)
        if not render.is_opened():
            render.release()
            self.label.setText("동영상을 선택하세요.")
            QMessageBox.critical(self, "열기 실패", f"영상을 열 수 없습니다.\n{source}")
            return False

        self.render = render
        self.fps = render.get_fps()
        if self.fps <= 0:
            self.fps = DEFAULT_FPS

        # 첫 프레임을 바로 보여주고 재생 시작
        self.next_frame()
        self.play()
        return True

    def close_video(self):
        self.timer.stop()
        if self.render is not None:
            self.render.release()
            self.render = None
        self.frame_index = -1
        self.current_pixmap = None
        self.label.clear()

    def play(self):
        if self.render is None:
            return
        # 1000ms / fps = 프레임 하나당 표시 시간
        self.timer.start(int(1000 / self.fps))

    def pause(self):
        self.timer.stop()

    def next_frame(self):
        if self.render is None:
            return

        ret, frame = self.render.read()
        if not ret:
            # 영상 끝 (또는 읽기 실패) → 재생 멈춤
            self.pause()
            return

        self.frame_index += 1
        self.show_frame(frame)

    def show_frame(self, frame):
        # OpenCV 프레임(BGR 순서 numpy 배열)을 QLabel에 표시
        height, width, channels = frame.shape
        bytes_per_line = channels * width

        # numpy 배열 → QImage. Format_BGR888을 쓰면 BGR→RGB 변환 없이 바로 만들 수 있다.
        # .copy()로 복사해두지 않으면 frame 메모리가 사라졌을 때 이미지가 깨질 수 있다.
        image = QImage(frame.data, width, height, bytes_per_line, QImage.Format.Format_BGR888).copy()

        self.current_pixmap = QPixmap.fromImage(image)
        self.update_label()

    def update_label(self):
        if self.current_pixmap is None:
            return
        # 라벨 크기에 맞춰 비율을 유지하며 확대/축소
        scaled = self.current_pixmap.scaled(
            self.label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.label.setPixmap(scaled)

    def resizeEvent(self, event):
        # 위젯 크기가 바뀔 때마다 Qt가 자동으로 호출하는 함수 (이벤트 핸들러)
        super().resizeEvent(event)
        self.update_label()
