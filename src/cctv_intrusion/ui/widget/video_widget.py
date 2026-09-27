from typing import override

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal, Slot
from PySide6.QtGui import (
    QColor,
    QImage,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
    QShortcut,
)
from PySide6.QtWidgets import QLabel, QMessageBox, QSizePolicy, QVBoxLayout, QWidget

from cctv_intrusion.detection import Detection
from cctv_intrusion.ui.styles import colors, load_qss
from cctv_intrusion.ui.widget.control_bar import ControlBar
from cctv_intrusion.video import VideoRender

# FPS 정보를 못 읽었을 때 사용할 기본값
DEFAULT_FPS = 30
# [◀ 5초] / [5초 ▶] 버튼, ← / → 키로 이동하는 시간 (초)
SEEK_SECONDS = 5
# 편집 중 꼭짓점을 그리는 점의 반지름 (화면 픽셀)
POINT_RADIUS = 5
# 꼭짓점에서 이 거리(화면 픽셀) 안을 누르면 그 점을 잡은 것으로 본다 (점보다 조금 넓게 잡아야 잡기 쉬움)
POINT_HIT_RADIUS = 10


class VideoLabel(QLabel):
    """영상을 표시하는 QLabel. 마우스 누름 / 이동 / 뗌을 신호로 알려준다.

    QLabel은 원래 마우스 신호가 없어서, mousePressEvent 등(마우스 동작 시 Qt가 자동으로
    호출하는 함수)을 덮어써서(override) 직접 신호를 보낸다. 위치는 모두 라벨 기준 좌표.

    Signals:
      mouse_pressed(x, y, button) : 마우스 버튼을 눌렀을 때 (button: Qt.MouseButton)
      mouse_moved(x, y)           : 마우스를 움직일 때 (setMouseTracking(True)면 버튼을 안 눌러도 발생)
      mouse_released()            : 마우스 버튼을 뗐을 때
    """

    mouse_pressed = Signal(float, float, object)  # object: Qt.MouseButton
    mouse_moved = Signal(float, float)
    mouse_released = Signal()

    @override
    def mousePressEvent(self, event: QMouseEvent) -> None:
        pos = event.position()
        self.mouse_pressed.emit(pos.x(), pos.y(), event.button())

    @override
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position()
        self.mouse_moved.emit(pos.x(), pos.y())

    @override
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self.mouse_released.emit()


class VideoWidget(QWidget):
    # Signal: "이런 일이 일어났다"고 알리는 신호. 다른 객체가 .connect(함수)로 연결해두면
    # .emit(...) 할 때마다 연결된 함수가 호출된다. (FileTree.file_selected와 같은 방식)
    # 클래스 변수로 선언해야 동작한다.

    # 영상을 열었을 때: 파일 경로
    source_opened = Signal(str)
    # 프레임을 하나 표시할 때마다: (BGR 원본 프레임 numpy 배열, 프레임 번호)
    # numpy 배열은 Qt가 모르는 타입이라 object로 선언한다.
    frame_ready = Signal(object, int)

    def __init__(self):
        super().__init__()

        self.render = None  # 현재 열린 VideoRender (없으면 None)
        self.fps = DEFAULT_FPS
        self.frame_count = 0  # 전체 프레임 수
        self.frame_index = -1  # 현재 화면에 표시 중인 프레임 번호
        self.at_end = False  # 영상 끝까지 재생했는지
        self.controls_enabled = True  # False면 재생 컨트롤 전체 비활성화 (위험지역 편집 모드 등)
        self.was_playing = False  # 슬라이더를 잡기 전에 재생 중이었는지
        self.current_pixmap = None  # 원본 크기 이미지 (창 크기가 바뀔 때 다시 축소하기 위해 보관)

        # 위험구역 표시용
        self.zones = []  # [{"name": "구역 1", "points": [(x, y), ...]}, ...] (원본 프레임 좌표)
        self.selected_zone = -1  # 리스트에서 선택한 구역 번호 (없으면 -1)
        self.drawing = False  # True면 영상 클릭으로 꼭짓점을 찍는 중 (위험지역 편집 모드)
        self.drawing_points = []  # 편집 중에 찍은 꼭짓점들 (원본 프레임 좌표)
        self.dragging_point = -1  # 드래그로 옮기는 중인 꼭짓점 번호 (없으면 -1)
        # 사람 탐지 결과 (원본 프레임 좌표). 추론이 끝날 때마다 바뀌고, 다음 결과가 올 때까지 계속 그린다
        self.detections: list[Detection] = []
        # 화면에 그린 이미지의 배율과 위치. 클릭 위치 → 원본 프레임 좌표 변환에 사용
        self.view_scale = 1.0
        self.view_offset_x = 0.0
        self.view_offset_y = 0.0

        self.label = VideoLabel("동영상을 선택하세요.")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # QLabel은 기본적으로 이미지 크기만큼 커지려고 해서 창이 늘어나 버린다.
        # Ignored로 두면 레이아웃이 정해준 크기를 그대로 따르므로 이미지를 자유롭게 줄일 수 있다.
        self.label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)

        self.label.setStyleSheet(load_qss("video_widget"))

        self.controls = ControlBar()
        self.controls.play_button.clicked.connect(self.toggle_play)
        self.controls.prev_button.clicked.connect(self.seek_backward)
        self.controls.next_button.clicked.connect(self.seek_forward)
        self.label.mouse_pressed.connect(self.on_label_pressed)
        self.label.mouse_moved.connect(self.on_label_moved)
        self.label.mouse_released.connect(self.on_label_released)

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
        #   Space : 재생/일시정지
        #   ← / → : 5초 뒤로 / 앞으로
        #   , / . : 한 프레임 뒤로 / 앞으로 (일시정지 상태로)
        QShortcut(QKeySequence("Space"), self).activated.connect(self.on_space_key)
        QShortcut(QKeySequence("Left"), self).activated.connect(self.on_left_key)
        QShortcut(QKeySequence("Right"), self).activated.connect(self.on_right_key)
        QShortcut(QKeySequence(","), self).activated.connect(self.on_comma_key)
        QShortcut(QKeySequence("."), self).activated.connect(self.on_period_key)

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

    def open_source(self, source):
        # source: 영상 파일 경로
        render = VideoRender(source)

        # 열기에 실패하면 지금 보고 있던 영상은 그대로 둔다
        if not render.is_opened():
            render.release()
            QMessageBox.critical(self, "열기 실패", f"영상을 열 수 없습니다.\n{source}")
            return False

        # 새 영상이 열린 게 확인되면 기존 영상 정리 후 교체
        self.close_video()
        self.render = render
        self.fps = render.get_fps()
        if self.fps <= 0:
            self.fps = DEFAULT_FPS
        self.frame_count = render.get_frame_count()

        # 슬라이더 범위를 0 ~ 마지막 프레임 번호로 설정
        # blockSignals: 코드로 값을 바꿀 때 valueChanged가 발생해 go_to_frame이 불리지 않도록 잠시 막음
        self.controls.slider.blockSignals(True)
        self.controls.slider.setRange(0, max(0, self.frame_count - 1))
        self.controls.slider.setValue(0)
        self.controls.slider.blockSignals(False)

        self.update_control_state()

        # 팀원 모듈이 초기화할 수 있도록 첫 frame_ready보다 먼저 알림
        self.source_opened.emit(str(source))

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
        self.at_end = False
        self.current_pixmap = None
        self.detections = []
        self.label.clear()
        self.update_control_state()

    def frame_size(self):
        # 열린 영상의 원본 프레임 크기 (너비, 높이). 영상이 없으면 (0, 0)
        if self.render is None:
            return 0, 0
        return self.render.get_frame_size()

    # ------------------------------------------------------------
    # 재생 / 일시정지
    # ------------------------------------------------------------
    def is_playing(self):
        return self.timer.isActive()

    def play(self):
        if self.render is None:
            return
        # 끝까지 본 영상을 다시 재생하면 처음부터
        if self.at_end:
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
        # [.] 키: 멈춘 상태에서 한 프레임 앞으로
        self.pause()
        self.next_frame()

    def prev_frame(self):
        # [,] 키: 멈춘 상태에서 한 프레임 뒤로
        self.pause()
        if self.frame_index > 0:
            self.go_to_frame(self.frame_index - 1)

    def seek_backward(self):
        # [◀ 5초] 버튼, ← 키
        self.seek_seconds(-SEEK_SECONDS)

    def seek_forward(self):
        # [5초 ▶] 버튼, → 키
        self.seek_seconds(SEEK_SECONDS)

    def seek_seconds(self, seconds):
        # 현재 위치에서 seconds초 만큼 이동 (음수면 뒤로). 재생 중이면 이동한 위치부터 계속 재생된다.
        if self.render is None:
            return
        target = self.frame_index + round(seconds * self.fps)
        # 영상 처음(0) ~ 마지막 프레임 사이로 제한
        target = max(0, min(target, self.frame_count - 1))
        self.go_to_frame(target)

    def go_to_frame(self, frame_number):
        # 원하는 프레임 번호로 이동해서 표시 (슬라이더, 5초 이동, 이전 프레임에서 사용)
        if self.render is None:
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
        # 새 프레임을 읽을 때마다 호출: 화면 표시 + 슬라이더/시간 갱신 + 팀원 모듈에 전달
        self.show_frame(frame)
        self.update_position()
        # 원본 프레임을 먼저 표시한 뒤 emit 하므로,
        # 연결된 함수 안에서 show_frame(오버레이 그린 프레임)을 호출하면 그 화면으로 덮어써진다.
        self.frame_ready.emit(frame, self.frame_index)

    def show_frame(self, frame):
        # OpenCV 프레임(BGR 순서 numpy 배열)을 QLabel에 표시
        # 팀원 모듈이 바운딩 박스 등을 그린 프레임을 넘겨서 화면을 바꿀 때도 사용 가능
        height, width, channels = frame.shape
        bytes_per_line = channels * width

        # numpy 배열 → QImage. Format_BGR888을 쓰면 BGR→RGB 변환 없이 바로 만들 수 있다.
        # .copy()로 복사해두지 않으면 frame 메모리가 사라졌을 때 이미지가 깨질 수 있다.
        image = QImage(
            frame.data, width, height, bytes_per_line, QImage.Format.Format_BGR888
        ).copy()

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

        # 원본 → 화면 배율, 그리고 라벨 가운데 정렬로 생긴 여백(검은 띠)의 크기
        self.view_scale = scaled.width() / self.current_pixmap.width()
        self.view_offset_x = (self.label.width() - scaled.width()) / 2
        self.view_offset_y = (self.label.height() - scaled.height()) / 2

        # 위험구역·사람 박스는 축소된 화면 이미지 위에 그린다 (원본에 그리면 작은 창에서 선·글자가 뭉개짐)
        self.draw_zones(scaled)
        self.draw_detections(scaled)
        self.label.setPixmap(scaled)

    def update_position(self):
        # 현재 프레임 번호에 맞춰 슬라이더와 시간 표시 갱신
        current_sec = self.frame_index / self.fps

        self.controls.slider.blockSignals(True)
        self.controls.slider.setValue(self.frame_index)
        self.controls.slider.blockSignals(False)
        self.controls.set_time(current_sec, self.frame_count / self.fps)

    # ------------------------------------------------------------
    # 위험구역 표시 / 편집 중 꼭짓점 찍기
    # ------------------------------------------------------------
    def set_zones(self, zones, selected_index):
        # 위험구역 목록이나 선택이 바뀌었을 때 MainWindow가 호출. 일시정지 중이어도 바로 다시 그린다.
        self.zones = zones
        self.selected_zone = selected_index
        self.update_label()

    def start_drawing(self) -> None:
        self.drawing = True
        self.drawing_points = []
        self.dragging_point = -1
        # 마우스 트래킹: 버튼을 누르지 않고 움직여도 mouseMoveEvent가 오게 한다 (꼭짓점 위 커서 변경용)
        self.label.setMouseTracking(True)
        self.label.setCursor(Qt.CursorShape.CrossCursor)
        self.update_label()

    def finish_drawing(self) -> list[tuple[int, int]]:
        # 편집 종료. 찍은 꼭짓점 목록을 돌려준다.
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
            # 우클릭: 마지막으로 찍은 점 취소 (드래그 중에는 무시)
            if self.drawing_points and self.dragging_point < 0:
                self.drawing_points.pop()
                self.update_label()
            return

        if button != Qt.MouseButton.LeftButton:
            return

        # 이미 찍은 꼭짓점을 눌렀으면 새 점을 찍지 않고 그 점을 잡는다 (드래그로 이동)
        hit = self.find_point_at(x, y)
        if hit >= 0:
            self.dragging_point = hit
            self.label.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        frame_x, frame_y = self.to_frame_point(x, y)
        # 영상 바깥(위아래/좌우 검은 여백)을 클릭하면 무시
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
            # 드래그 중이 아니면: 꼭짓점 위에서는 손 모양, 나머지는 십자 커서로 잡을 수 있는 점을 알려줌
            if self.find_point_at(x, y) >= 0:
                self.label.setCursor(Qt.CursorShape.OpenHandCursor)
            else:
                self.label.setCursor(Qt.CursorShape.CrossCursor)
            return

        # 잡은 꼭짓점을 마우스 위치로 이동. 영상 밖으로 끌고 나가도 영상 가장자리에 붙어 있게 한다.
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
        self.label.setCursor(Qt.CursorShape.OpenHandCursor)  # 마우스는 아직 그 점 위에 있음

    def to_frame_point(self, x: float, y: float) -> tuple[float, float]:
        # 화면(라벨) 좌표 → 원본 프레임 좌표
        return (x - self.view_offset_x) / self.view_scale, (
            y - self.view_offset_y
        ) / self.view_scale

    def find_point_at(self, x: float, y: float) -> int:
        # 화면 좌표 (x, y) 근처에 있는 꼭짓점 번호 (없으면 -1).
        # 거리는 화면 픽셀로 재야 창 크기와 상관없이 잡히는 범위가 같다.
        # 점이 겹쳐 있으면 나중에 찍은(위에 그려진) 점을 먼저 잡도록 뒤에서부터 찾는다.
        for i in range(len(self.drawing_points) - 1, -1, -1):
            px, py = self.drawing_points[i]
            view_x = px * self.view_scale + self.view_offset_x
            view_y = py * self.view_scale + self.view_offset_y
            if (view_x - x) ** 2 + (view_y - y) ** 2 <= POINT_HIT_RADIUS**2:
                return i
        return -1

    def draw_zones(self, pixmap):
        # QPainter: QPixmap/위젯 위에 선, 도형, 글자를 그리는 도구. begin(대상) ~ end() 사이에서 그린다.
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)  # 선을 부드럽게

        for i, zone in enumerate(self.zones):
            selected = i == self.selected_zone
            color = colors.ZONE_SELECTED if selected else colors.ZONE
            polygon = self.to_view_polygon(zone["points"])

            # 선택된 구역은 선을 두껍게, 안쪽을 더 진하게 칠해서 눈에 띄게 한다
            painter.setPen(QPen(color, 4 if selected else 2))
            fill = QColor(color)
            fill.setAlpha(110 if selected else 50)  # 투명도(0~255)
            painter.setBrush(fill)
            painter.drawPolygon(polygon)

            self.draw_zone_name(painter, zone["name"], polygon, color)

        if self.drawing and self.drawing_points:
            # 편집 중인 꼭짓점: 점과 점 사이를 선으로 잇고, 마지막 점 → 첫 점은 점선으로 표시
            points = self.to_view_polygon(self.drawing_points)
            painter.setPen(QPen(colors.ZONE_DRAWING, 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPolyline(points)
            if len(points) >= 3:
                painter.setPen(QPen(colors.ZONE_DRAWING, 2, Qt.PenStyle.DashLine))
                painter.drawLine(points[len(points) - 1], points[0])
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(colors.ZONE_DRAWING)
            for point in points:
                painter.drawEllipse(point, POINT_RADIUS, POINT_RADIUS)

        painter.end()

    def draw_zone_name(self, painter, name, polygon, color):
        # 구역 이름을 색 배경 상자 안에 적어서 구역 가운데에 표시
        font = painter.font()
        font.setPixelSize(16)
        font.setBold(True)
        painter.setFont(font)

        text_rect = painter.fontMetrics().boundingRect(name).adjusted(-6, -3, 6, 3)
        text_rect.moveCenter(polygon.boundingRect().center().toPoint())

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawRect(text_rect)
        painter.setPen(colors.ZONE_NAME_TEXT)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, name)

    # ------------------------------------------------------------
    # 사람 탐지 박스 표시
    # ------------------------------------------------------------
    @Slot(int, object)
    def set_detections(self, frame_index: int, detections: list[Detection]) -> None:
        # 탐지 결과가 도착했을 때 호출. 일시정지 중이어도 바로 다시 그린다.
        # 추론이 끝나는 사이 영상이 조금 더 진행되므로 결과는 현재 화면보다 1~2프레임 늦을 수 있다.
        self.detections = detections
        self.update_label()

    def draw_detections(self, pixmap: QPixmap) -> None:
        if not self.detections:
            return
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(colors.PERSON_BOX, 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for detection in self.detections:
            painter.drawRect(
                QRectF(
                    detection.x1 * self.view_scale,
                    detection.y1 * self.view_scale,
                    (detection.x2 - detection.x1) * self.view_scale,
                    (detection.y2 - detection.y1) * self.view_scale,
                )
            )
        painter.end()

    def to_view_polygon(self, points):
        # 원본 프레임 좌표 목록 → 축소된 화면 이미지 좌표의 QPolygonF
        return QPolygonF([QPointF(x * self.view_scale, y * self.view_scale) for x, y in points])

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

        self.controls.play_button.setEnabled(has_video)
        self.controls.prev_button.setEnabled(has_video)
        self.controls.next_button.setEnabled(has_video)
        self.controls.slider.setEnabled(has_video)

        if self.render is None:
            self.controls.set_time(0, 0)

    # 단축키는 해당 버튼이 활성화되어 있을 때만 동작
    def on_space_key(self):
        if self.controls.play_button.isEnabled():
            self.toggle_play()

    def on_left_key(self):
        if self.controls.prev_button.isEnabled():
            self.seek_backward()

    def on_right_key(self):
        if self.controls.next_button.isEnabled():
            self.seek_forward()

    def on_comma_key(self):
        if self.controls.prev_button.isEnabled():
            self.prev_frame()

    def on_period_key(self):
        if self.controls.next_button.isEnabled():
            self.step_frame()
