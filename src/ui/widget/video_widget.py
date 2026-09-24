from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QSizePolicy, QMessageBox
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap, QKeySequence, QShortcut
from video import VideoRender
from ui.widget.control_bar import ControlBar

# FPS 정보를 못 읽었을 때 사용할 기본값
DEFAULT_FPS = 30

class VideoWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.render = None          # 현재 열린 VideoRender (없으면 None)
        self.fps = DEFAULT_FPS
        self.frame_count = 0        # 전체 프레임 수 (파일일 때만 의미 있음)
        self.frame_index = -1       # 현재 화면에 표시 중인 프레임 번호
        self.is_stream = False      # 실시간 스트림이면 True (탐색 불가)
        self.at_end = False         # 영상 끝까지 재생했는지
        self.controls_enabled = True  # False면 재생 컨트롤 전체 비활성화 (위험지역 편집 모드 등)
        self.was_playing = False    # 슬라이더를 잡기 전에 재생 중이었는지
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

        self.controls = ControlBar()
        self.controls.play_button.clicked.connect(self.toggle_play)
        self.controls.prev_button.clicked.connect(self.prev_frame)
        self.controls.next_button.clicked.connect(self.step_frame)

        # 슬라이더를 잡고 있는 동안은 재생을 멈추고, 놓으면 원래 상태로 되돌린다.
        self.controls.slider.sliderPressed.connect(self.on_slider_pressed)
        self.controls.slider.sliderReleased.connect(self.on_slider_released)
        # valueChanged: 드래그, 클릭 등으로 슬라이더 값이 바뀔 때마다 발생
        self.controls.slider.valueChanged.connect(self.go_to_frame)

        # QTimer: 지정한 간격(ms)마다 timeout 신호를 보내는 타이머.
        # timeout에 next_frame을 연결해서 FPS 간격으로 다음 프레임을 읽는다.
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.next_frame)

        # QShortcut: 키보드 단축키. 창 안 어디에 포커스가 있어도 동작한다.
        QShortcut(QKeySequence("Space"), self).activated.connect(self.on_space_key)
        QShortcut(QKeySequence("Left"), self).activated.connect(self.on_left_key)
        QShortcut(QKeySequence("Right"), self).activated.connect(self.on_right_key)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.label, 1)  # 1: 남는 세로 공간을 영상이 차지
        layout.addWidget(self.controls)
        self.setLayout(layout)

        self.update_control_state()

    # ------------------------------------------------------------
    # 영상 열기 / 닫기
    # ------------------------------------------------------------
    def set_video(self, path):
        # 파일 트리에서 파일을 선택했을 때 호출됨
        self.open_source(path)

    def open_source(self, source, is_stream=False):
        # 기존 영상이 있으면 먼저 정리
        self.close_video()

        render = VideoRender(source)
        if not render.is_opened():
            render.release()
            self.label.setText("동영상을 선택하세요.")
            QMessageBox.critical(self, "열기 실패", f"영상을 열 수 없습니다.\n{source}")
            return False

        self.render = render
        self.is_stream = is_stream
        self.fps = render.get_fps()
        if self.fps <= 0:
            self.fps = DEFAULT_FPS
        self.frame_count = 0 if is_stream else render.get_frame_count()

        # 슬라이더 범위를 0 ~ 마지막 프레임 번호로 설정
        # blockSignals: 코드로 값을 바꿀 때 valueChanged가 발생해 go_to_frame이 불리지 않도록 잠시 막음
        self.controls.slider.blockSignals(True)
        self.controls.slider.setRange(0, max(0, self.frame_count - 1))
        self.controls.slider.setValue(0)
        self.controls.slider.blockSignals(False)

        self.update_control_state()

        # 첫 프레임을 바로 보여주고 재생 시작
        self.next_frame()
        self.play()
        return True

    def close_video(self):
        self.pause()
        if self.render is not None:
            self.render.release()
            self.render = None
        self.frame_index = -1
        self.frame_count = 0
        self.is_stream = False
        self.at_end = False
        self.current_pixmap = None
        self.label.clear()
        self.update_control_state()

    # ------------------------------------------------------------
    # 재생 / 일시정지
    # ------------------------------------------------------------
    def is_playing(self):
        return self.timer.isActive()

    def play(self):
        if self.render is None:
            return
        # 끝까지 본 영상을 다시 재생하면 처음부터
        if self.at_end and not self.is_stream:
            self.render.seek_frame(0)
            self.frame_index = -1
            self.at_end = False
        # 1000ms / fps = 프레임 하나당 표시 시간
        self.timer.start(int(1000 / self.fps))
        self.controls.set_playing(True)

    def pause(self):
        self.timer.stop()
        self.controls.set_playing(False)

    def toggle_play(self):
        if self.is_playing():
            self.pause()
        else:
            self.play()

    # ------------------------------------------------------------
    # 프레임 이동
    # ------------------------------------------------------------
    def next_frame(self):
        # 다음 프레임을 읽어서 표시 (타이머가 주기적으로 호출)
        if self.render is None:
            return

        ret, frame = self.render.read()
        if not ret:
            # 영상 끝 (또는 읽기 실패) → 재생 멈춤
            self.at_end = True
            self.pause()
            return

        self.frame_index += 1
        self.handle_frame(frame)

    def step_frame(self):
        # [다음] 버튼: 멈춘 상태에서 한 프레임 앞으로
        self.pause()
        self.next_frame()

    def prev_frame(self):
        # [이전] 버튼: 멈춘 상태에서 한 프레임 뒤로
        self.pause()
        if self.frame_index > 0:
            self.go_to_frame(self.frame_index - 1)

    def go_to_frame(self, frame_number):
        # 원하는 프레임 번호로 이동해서 표시 (슬라이더, 이전 버튼에서 사용)
        if self.render is None or self.is_stream:
            return

        self.render.seek_frame(frame_number)
        ret, frame = self.render.read()
        if not ret:
            return

        self.frame_index = frame_number
        self.at_end = False
        self.handle_frame(frame)

    def on_slider_pressed(self):
        self.was_playing = self.is_playing()
        self.pause()

    def on_slider_released(self):
        if self.was_playing:
            self.play()

    # ------------------------------------------------------------
    # 화면 표시
    # ------------------------------------------------------------
    def handle_frame(self, frame):
        # 새 프레임을 읽을 때마다 호출: 화면 표시 + 슬라이더/시간 갱신
        self.show_frame(frame)
        self.update_position()

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

    def update_position(self):
        # 현재 프레임 번호에 맞춰 슬라이더와 시간 표시 갱신
        current_sec = self.frame_index / self.fps

        if self.is_stream:
            self.controls.set_live_time(current_sec)
            return

        self.controls.slider.blockSignals(True)
        self.controls.slider.setValue(self.frame_index)
        self.controls.slider.blockSignals(False)
        self.controls.set_time(current_sec, self.frame_count / self.fps)

    def resizeEvent(self, event):
        # 위젯 크기가 바뀔 때마다 Qt가 자동으로 호출하는 함수 (이벤트 핸들러)
        super().resizeEvent(event)
        self.update_label()

    # ------------------------------------------------------------
    # 컨트롤 활성화 상태
    # ------------------------------------------------------------
    def set_controls_enabled(self, enabled):
        # 외부(예: 위험지역 편집 모드)에서 재생 컨트롤 전체를 켜고 끌 때 사용
        self.controls_enabled = enabled
        self.update_control_state()

    def update_control_state(self):
        has_video = self.render is not None and self.controls_enabled
        # 실시간 스트림은 탐색이 안 되므로 재생/정지만 가능
        can_seek = has_video and not self.is_stream

        self.controls.play_button.setEnabled(has_video)
        self.controls.prev_button.setEnabled(can_seek)
        self.controls.next_button.setEnabled(can_seek)
        self.controls.slider.setEnabled(can_seek)

        if self.render is None:
            self.controls.set_time(0, 0)

    # 단축키는 해당 버튼이 활성화되어 있을 때만 동작
    def on_space_key(self):
        if self.controls.play_button.isEnabled():
            self.toggle_play()

    def on_left_key(self):
        if self.controls.prev_button.isEnabled():
            self.prev_frame()

    def on_right_key(self):
        if self.controls.next_button.isEnabled():
            self.step_frame()
