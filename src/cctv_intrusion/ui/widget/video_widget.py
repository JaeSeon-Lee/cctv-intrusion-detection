import time

from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QImage, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import QMessageBox, QSizePolicy, QVBoxLayout, QWidget

from cctv_intrusion.detection import Detection
from cctv_intrusion.intrusion import MonitorState
from cctv_intrusion.ui.styles import load_qss
from cctv_intrusion.ui.widget.control_bar import ControlBar
from cctv_intrusion.ui.widget.video_label import VideoLabel
from cctv_intrusion.ui.widget.video_overlay import (
    draw_detections,
    draw_monitor_state,
    draw_zones,
)
from cctv_intrusion.video import CameraCapture, VideoRender
from cctv_intrusion.zone import Zone

DEFAULT_FPS = 30
MAX_LIVE_FPS = 60
SEEK_SECONDS = 5
POINT_HIT_RADIUS = 10


class VideoWidget(QWidget):
    """영상 재생 · 위험구역 편집 · 탐지 박스 표시를 담당하는 중앙 위젯.

    저장된 동영상(open_source)과 실시간 웹캠(open_camera)을 같은 화면에서 보여준다.
    실시간일 때 frame_index 는 연결 후 흐른 시간 × fps 이다 (frame_index / fps = 실제 경과 초).
    """

    source_opened = Signal(str)  # 동영상 경로, 또는 웹캠 번호
    source_lost = Signal()  # 웹캠 연결이 끊김
    frame_ready = Signal(object, int)  # (BGR frame, frame_index)

    def __init__(self, *, compact: bool = False) -> None:
        super().__init__()

        self.compact = compact
        self.render: VideoRender | CameraCapture | None = None
        self.live = False
        self.live_elapsed_sec = 0.0  # 일시정지 전까지 흐른 시간
        self.live_resumed_at = 0.0
        self.fps = DEFAULT_FPS
        self.frame_count = 0
        self.frame_index = -1
        self.at_end = False
        self.controls_enabled = True
        self.was_playing = False
        self.current_pixmap: QPixmap | None = None

        self.zones: list[Zone] = []
        self.selected_zone = -1
        self.drawing = False
        self.drawing_points: list[tuple[int, int]] = []
        self.dragging_point = -1
        self.detections: list[Detection] = []
        self.monitor_state = MonitorState.IDLE
        self.view_scale = 1.0
        self.view_offset_x = 0.0
        self.view_offset_y = 0.0
        self.source_path: str | None = None  # 파일 경로 (웹캠이면 None)

        self.label = VideoLabel("영상 없음")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.label.setStyleSheet(load_qss("video_widget"))

        self.controls = ControlBar()
        self.playback_speed = 1.0
        self.controls.play_button.clicked.connect(self.toggle_play)
        self.controls.prev_button.clicked.connect(self.seek_backward)
        self.controls.next_button.clicked.connect(self.seek_forward)
        self.label.mouse_pressed.connect(self.on_label_pressed)
        self.label.mouse_moved.connect(self.on_label_moved)
        self.label.mouse_released.connect(self.on_label_released)
        self.controls.slider.sliderPressed.connect(self.on_slider_pressed)
        self.controls.slider.sliderReleased.connect(self.on_slider_released)
        self.controls.slider.valueChanged.connect(self.go_to_frame)
        self.controls.speed_combo.currentIndexChanged.connect(self.on_speed_changed)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.next_frame)

        if not compact:
            QShortcut(QKeySequence("Space"), self).activated.connect(self.on_space_key)
            QShortcut(QKeySequence("Left"), self).activated.connect(self.on_left_key)
            QShortcut(QKeySequence("Right"), self).activated.connect(self.on_right_key)
            QShortcut(QKeySequence(","), self).activated.connect(self.on_comma_key)
            QShortcut(QKeySequence("."), self).activated.connect(self.on_period_key)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.label, 1)
        if not compact:
            layout.addWidget(self.controls)
        else:
            self.controls.hide()
        self.setLayout(layout)

        self.update_control_state()

    def set_video(self, path: str) -> bool:
        return self.open_source(path)

    def open_source(self, source: str) -> bool:
        render = VideoRender(source)
        if not render.is_opened():
            render.release()
            QMessageBox.critical(self, "열기 실패", f"영상을 열 수 없습니다.\n{source}")
            return False

        self.close_video()
        self.render = render
        self.live = False
        self.source_path = str(source)
        self.controls.set_live(False)
        self.fps = render.get_fps() or DEFAULT_FPS
        self.frame_count = render.get_frame_count()

        self.controls.slider.blockSignals(True)
        self.controls.slider.setRange(0, max(0, self.frame_count - 1))
        self.controls.slider.setValue(0)
        self.controls.slider.blockSignals(False)

        self.update_control_state()
        self.source_opened.emit(str(source))
        self.next_frame()
        self.play()
        return True

    @Slot(int)
    def open_camera(self, index: int, *, quiet: bool = False) -> bool:
        camera = CameraCapture(index)
        if not camera.is_opened():
            camera.release()
            if not quiet:
                QMessageBox.critical(
                    self,
                    "카메라 연결 실패",
                    f"카메라 {index}번을 열 수 없습니다.\n"
                    f"카메라가 꽂혀 있는지, 다른 프로그램이 쓰고 있지 않은지 확인하세요.",
                )
            self.label.setText(f"CAM 웹캠 {index} 연결 실패")
            return False

        self.close_video()
        self.render = camera
        self.live = True
        self.source_path = None
        self.live_elapsed_sec = 0.0
        self.controls.set_live(True)
        fps = camera.get_fps()
        self.fps = fps if 0 < fps <= MAX_LIVE_FPS else DEFAULT_FPS
        camera.start()

        self.update_control_state()
        self.source_opened.emit(str(index))
        self.play()
        return True

    def close_video(self) -> None:
        self.pause(force=True)
        if self.render is not None:
            self.render.release()
            self.render = None
        self.live = False
        self.source_path = None
        self.frame_index = -1
        self.frame_count = 0
        self.at_end = False
        self.current_pixmap = None
        self.detections = []
        self.label.clear()
        self.controls.set_live(False)
        self.update_control_state()

    def frame_size(self) -> tuple[int, int]:
        if self.render is None:
            return 0, 0
        return self.render.get_frame_size()

    def is_playing(self) -> bool:
        return self.timer.isActive()

    def play(self) -> None:
        if self.render is None:
            return
        if self.live:
            self.live_resumed_at = time.monotonic()
        if self.at_end:
            self.render.seek_frame(0)
            self.frame_index = -1
            self.at_end = False
        self.timer.start(self._frame_interval_ms())
        self.controls.set_playing(True)

    def _frame_interval_ms(self) -> int:
        rate = self.fps * (1.0 if self.live else self.playback_speed)
        return max(1, int(1000 / max(rate, 0.1)))

    def set_playback_speed(self, speed: float) -> None:
        self.playback_speed = max(0.25, min(float(speed), 4.0))
        if self.is_playing() and not self.live:
            self.timer.start(self._frame_interval_ms())

    def on_speed_changed(self) -> None:
        self.set_playback_speed(self.controls.playback_speed())

    def pause(self, *, force: bool = False) -> None:
        # 위험구역 꼭짓점을 찍는 동안에는 재생을 멈추지 않는다
        if self.drawing and not force:
            return
        if self.live and self.is_playing():
            self.live_elapsed_sec += time.monotonic() - self.live_resumed_at
        self.timer.stop()
        self.controls.set_playing(False)

    def toggle_play(self) -> None:
        if self.drawing:
            return
        if self.is_playing():
            self.pause()
        else:
            self.play()

    def next_frame(self) -> None:
        if self.render is None:
            return
        ret, frame = self.render.read()
        if self.live:
            if not ret:
                # 아직 새 프레임이 없으면 다음 타이머에서 다시 본다
                if self.render.lost:
                    self.pause(force=True)
                    self.source_lost.emit()
                return
            elapsed = self.live_elapsed_sec + time.monotonic() - self.live_resumed_at
            self.frame_index = round(elapsed * self.fps)
            self.handle_frame(frame)
            return
        if not ret:
            # 구역 편집 중이면 처음으로 돌려 계속 재생 (CCTV처럼)
            if self.drawing:
                self.render.seek_frame(0)
                self.frame_index = -1
                self.at_end = False
                return
            self.at_end = True
            self.pause()
            return
        self.frame_index += 1
        self.handle_frame(frame)

    def step_frame(self) -> None:
        if self.drawing:
            return
        self.pause()
        self.next_frame()

    def prev_frame(self) -> None:
        if self.drawing:
            return
        self.pause()
        if self.frame_index > 0:
            self.go_to_frame(self.frame_index - 1)

    def seek_backward(self) -> None:
        self.seek_seconds(-SEEK_SECONDS)

    def seek_forward(self) -> None:
        self.seek_seconds(SEEK_SECONDS)

    def seek_seconds(self, seconds: float) -> None:
        if self.render is None:
            return
        target = self.frame_index + round(seconds * self.fps)
        target = max(0, min(target, self.frame_count - 1))
        self.go_to_frame(target)

    def go_to_frame(self, frame_number: int) -> None:
        if self.render is None:
            return
        self.render.seek_frame(frame_number)
        ret, frame = self.render.read()
        if not ret:
            return
        self.frame_index = frame_number
        self.at_end = False
        self.handle_frame(frame)

    def on_slider_pressed(self) -> None:
        if self.drawing:
            return
        self.was_playing = self.is_playing()
        self.pause()

    def on_slider_released(self) -> None:
        if self.drawing:
            return
        if self.was_playing:
            self.play()

    def handle_frame(self, frame) -> None:
        self.show_frame(frame)
        self.update_position()
        self.frame_ready.emit(frame, self.frame_index)

    def show_frame(self, frame) -> None:
        height, width, channels = frame.shape
        bytes_per_line = channels * width
        image = QImage(
            frame.data, width, height, bytes_per_line, QImage.Format.Format_BGR888
        ).copy()
        self.current_pixmap = QPixmap.fromImage(image)
        self.update_label()

    def update_label(self) -> None:
        if self.current_pixmap is None:
            return
        scaled = self.current_pixmap.scaled(
            self.label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.view_scale = scaled.width() / self.current_pixmap.width()
        self.view_offset_x = (self.label.width() - scaled.width()) / 2
        self.view_offset_y = (self.label.height() - scaled.height()) / 2

        draw_zones(
            scaled,
            self.zones,
            selected_index=self.selected_zone,
            scale=self.view_scale,
            drawing=self.drawing,
            drawing_points=self.drawing_points,
        )
        draw_detections(scaled, self.detections, self.view_scale)
        draw_monitor_state(scaled, self.monitor_state)
        self.label.setPixmap(scaled)

    def update_position(self) -> None:
        current_sec = self.frame_index / self.fps
        self.controls.slider.blockSignals(True)
        self.controls.slider.setValue(self.frame_index)
        self.controls.slider.blockSignals(False)
        self.controls.set_time(current_sec, self.frame_count / self.fps)

    def set_zones(self, zones: list[Zone], selected_index: int) -> None:
        self.zones = zones
        self.selected_zone = selected_index
        self.update_label()

    def start_drawing(self) -> None:
        self.drawing = True
        self.drawing_points = []
        self.dragging_point = -1
        self.label.setMouseTracking(True)
        self.label.setCursor(Qt.CursorShape.CrossCursor)
        # 구역 편집 시작 시 재생 유지
        if self.render is not None and not self.is_playing():
            self.play()
        self.update_label()

    def finish_drawing(self) -> list[tuple[int, int]]:
        points = self.drawing_points
        self.drawing = False
        self.drawing_points = []
        self.dragging_point = -1
        self.label.setMouseTracking(False)
        self.label.unsetCursor()
        self.update_label()
        return points

    @Slot(float, float, object)
    def on_label_pressed(self, x: float, y: float, button: Qt.MouseButton) -> None:
        if not self.drawing or self.current_pixmap is None:
            return

        if button == Qt.MouseButton.RightButton:
            if self.drawing_points and self.dragging_point < 0:
                self.drawing_points.pop()
                self.update_label()
            return

        if button != Qt.MouseButton.LeftButton:
            return

        hit = self.find_point_at(x, y)
        if hit >= 0:
            self.dragging_point = hit
            self.label.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        frame_x, frame_y = self.to_frame_point(x, y)
        if not (
            0 <= frame_x < self.current_pixmap.width()
            and 0 <= frame_y < self.current_pixmap.height()
        ):
            return

        self.drawing_points.append((int(frame_x), int(frame_y)))
        self.update_label()

    @Slot(float, float)
    def on_label_moved(self, x: float, y: float) -> None:
        if not self.drawing or self.current_pixmap is None:
            return

        if self.dragging_point < 0:
            if self.find_point_at(x, y) >= 0:
                self.label.setCursor(Qt.CursorShape.OpenHandCursor)
            else:
                self.label.setCursor(Qt.CursorShape.CrossCursor)
            return

        frame_x, frame_y = self.to_frame_point(x, y)
        frame_x = max(0, min(frame_x, self.current_pixmap.width() - 1))
        frame_y = max(0, min(frame_y, self.current_pixmap.height() - 1))
        self.drawing_points[self.dragging_point] = (int(frame_x), int(frame_y))
        self.update_label()

    @Slot()
    def on_label_released(self) -> None:
        if self.dragging_point < 0:
            return
        self.dragging_point = -1
        self.label.setCursor(Qt.CursorShape.OpenHandCursor)

    def to_frame_point(self, x: float, y: float) -> tuple[float, float]:
        return (x - self.view_offset_x) / self.view_scale, (
            y - self.view_offset_y
        ) / self.view_scale

    def find_point_at(self, x: float, y: float) -> int:
        for i in range(len(self.drawing_points) - 1, -1, -1):
            px, py = self.drawing_points[i]
            view_x = px * self.view_scale + self.view_offset_x
            view_y = py * self.view_scale + self.view_offset_y
            if (view_x - x) ** 2 + (view_y - y) ** 2 <= POINT_HIT_RADIUS**2:
                return i
        return -1

    @Slot(int, object)
    def set_detections(self, frame_index: int, detections: list[Detection]) -> None:
        self.detections = detections
        self.update_label()

    def set_monitor_state(self, state: MonitorState) -> None:
        if self.monitor_state == state:
            return
        self.monitor_state = state
        self.update_label()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.update_label()

    def set_controls_enabled(self, enabled: bool) -> None:
        self.controls_enabled = enabled
        self.update_control_state()

    def update_control_state(self) -> None:
        has_video = self.render is not None and self.controls_enabled
        seekable = has_video and not self.live
        self.controls.play_button.setEnabled(has_video)
        self.controls.prev_button.setEnabled(seekable)
        self.controls.next_button.setEnabled(seekable)
        self.controls.slider.setEnabled(seekable)
        if self.render is None:
            self.controls.set_time(0, 0)

    def on_space_key(self) -> None:
        if self.drawing:
            return
        if self.controls.play_button.isEnabled():
            self.toggle_play()

    def on_left_key(self) -> None:
        if self.controls.prev_button.isEnabled():
            self.seek_backward()

    def on_right_key(self) -> None:
        if self.controls.next_button.isEnabled():
            self.seek_forward()

    def on_comma_key(self) -> None:
        if self.controls.prev_button.isEnabled():
            self.prev_frame()

    def on_period_key(self) -> None:
        if self.controls.next_button.isEnabled():
            self.step_frame()
