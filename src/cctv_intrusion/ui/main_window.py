from pathlib import Path

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import QMainWindow, QMessageBox, QSplitter, QTabWidget

from cctv_intrusion.detection import Detection, PersonDetection
from cctv_intrusion.intrusion import (
    IntrusionMonitor,
    LiveRecorder,
    MonitorState,
    save_event_records,
)
from cctv_intrusion.paths import INPUT_DIR
from cctv_intrusion.ui.widget.camera_panel import CameraPanel
from cctv_intrusion.ui.widget.file_tree import FileTree
from cctv_intrusion.ui.widget.video_widget import VideoWidget
from cctv_intrusion.ui.widget.zone_panel import ZonePanel
from cctv_intrusion.zone import (
    MIN_POINTS,
    Zone,
    ZoneFileError,
    load_zones,
    save_zones,
    zone_file_path,
)

MAX_SCREEN_RATIO = 0.9
MIN_VIDEO_WIDTH = 800

LIVE_TAB = 0
FILE_TAB = 1
PLACEHOLDERS = {
    LIVE_TAB: "왼쪽에서 카메라를 연결하세요",
    FILE_TAB: "왼쪽 목록에서 영상을 선택하세요",
}


def camera_zone_source(index: str | int) -> Path:
    # 웹캠 위험구역은 data/input/camera_0.json 처럼 카메라 번호별로 저장한다
    return INPUT_DIR / f"camera_{index}"


class MainWindow(QMainWindow):
    """메인 창.

    팀원 연동용 Signal:
      - video_widget.source_opened(str)   동영상 경로 또는 웹캠 번호
      - video_widget.frame_ready(ndarray, int)
      - zone_edit_started / zone_edit_applied / zone_edit_canceled
      - zone_panel.zones_changed(list[Zone])
      - person_detection.detected(int, list[Detection])
    """

    zone_edit_started = Signal()
    zone_edit_applied = Signal()
    zone_edit_canceled = Signal()

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("침입 감지 모니터")
        # 위험구역 json 의 기준 경로 (저장된 동영상 경로, 웹캠이면 camera_zone_source)
        self.video_path: Path | None = None
        self.live_recorder: LiveRecorder | None = None
        self.loading_zones = False
        self.resize(1440, 920)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setChildrenCollapsible(False)

        self.camera_panel = CameraPanel()
        self.file_tree = FileTree()
        self.source_tabs = QTabWidget()
        self.source_tabs.setObjectName("sourceTabs")
        self.source_tabs.addTab(self.camera_panel, "실시간 영상")
        self.source_tabs.addTab(self.file_tree, "저장된 동영상")
        self.video_widget = VideoWidget()
        self.zone_panel = ZonePanel()

        splitter.addWidget(self.source_tabs)
        splitter.addWidget(self.video_widget)
        splitter.addWidget(self.zone_panel)
        splitter.setSizes([260, 900, 280])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)

        self.file_tree.file_selected.connect(self.video_widget.set_video)
        self.camera_panel.connect_requested.connect(self.video_widget.open_camera)
        self.camera_panel.disconnect_requested.connect(self.close_source)
        self.source_tabs.currentChanged.connect(self.on_tab_changed)
        self.zone_panel.zone_button.clicked.connect(self.start_zone_edit)
        self.zone_panel.apply_button.clicked.connect(self.apply_zone_edit)
        self.zone_panel.cancel_button.clicked.connect(self.cancel_zone_edit)
        self.zone_panel.zones_changed.connect(self.update_zone_overlay)
        self.zone_panel.selection_changed.connect(self.update_zone_overlay)
        self.zone_panel.zones_changed.connect(self.save_zone_file)
        self.video_widget.source_opened.connect(self.on_source_opened)
        self.video_widget.source_lost.connect(self.on_source_lost)

        self.person_detection = PersonDetection()
        self.intrusion_monitor = IntrusionMonitor()
        self.video_widget.frame_ready.connect(self.person_detection.submit)
        self.video_widget.frame_ready.connect(self.record_live_frame)
        self.person_detection.detected.connect(self.on_detections)
        self.person_detection.failed.connect(self.on_detection_failed)
        self.person_detection.start()

        self.setCentralWidget(splitter)
        self.show_placeholder()

    def on_source_opened(self, source: str) -> None:
        self.finish_live_recording()
        self.person_detection.reset()
        self.intrusion_monitor.reset()
        self.video_widget.set_monitor_state(self.intrusion_monitor.state)
        self.zone_panel.zone_button.setEnabled(True)
        if self.video_widget.live:
            self.video_path = camera_zone_source(source)
            self.live_recorder = LiveRecorder()
            self.camera_panel.set_connected(True)
        else:
            self.video_path = Path(source)
        self.load_zone_file()
        self.fit_to_video()

    @Slot(int)
    def on_tab_changed(self, index: int) -> None:
        # 탭을 바꾸면 보던 영상(웹캠)을 닫고 빈 화면에서 시작한다
        self.close_source()

    @Slot()
    def close_source(self) -> None:
        self.finish_live_recording()
        self.video_widget.close_video()
        self.person_detection.reset()
        self.intrusion_monitor.reset()
        self.video_widget.set_monitor_state(self.intrusion_monitor.state)
        self.video_path = None
        self.loading_zones = True
        try:
            self.zone_panel.set_zones([])
        finally:
            self.loading_zones = False
        self.zone_panel.zone_button.setEnabled(False)
        self.camera_panel.set_connected(False)
        self.show_placeholder()

    @Slot()
    def on_source_lost(self) -> None:
        self.close_source()
        QMessageBox.warning(
            self,
            "카메라 연결 끊김",
            "카메라에서 영상을 받을 수 없어 연결을 해제했습니다.\n"
            "녹화 중이던 사건 클립은 끊기기 전까지 저장했습니다.",
        )

    def show_placeholder(self) -> None:
        self.video_widget.label.setText(PLACEHOLDERS[self.source_tabs.currentIndex()])

    def fit_to_video(self) -> None:
        if self.isMaximized() or self.isFullScreen():
            return
        video_width, video_height = self.video_widget.frame_size()
        if video_width <= 0 or video_height <= 0:
            return

        label = self.video_widget.label
        extra_width = self.frameGeometry().width() - label.width()
        extra_height = self.frameGeometry().height() - label.height()

        screen = self.screen().availableGeometry()
        max_width = screen.width() * MAX_SCREEN_RATIO - extra_width
        max_height = screen.height() * MAX_SCREEN_RATIO - extra_height

        scale = min(
            max_width / video_width,
            max_height / video_height,
            max(1.0, MIN_VIDEO_WIDTH / video_width),
        )
        if scale <= 0:
            return
        label_width = round(video_width * scale)
        label_height = round(video_height * scale)

        self.resize(
            self.width() + label_width - label.width(),
            self.height() + label_height - label.height(),
        )
        self.move(
            screen.x() + (screen.width() - (label_width + extra_width)) // 2,
            screen.y() + (screen.height() - (label_height + extra_height)) // 2,
        )

    def start_zone_edit(self) -> None:
        self.video_widget.pause()
        self.set_edit_mode(True)
        self.video_widget.start_drawing()
        self.zone_edit_started.emit()

    def apply_zone_edit(self) -> None:
        if len(self.video_widget.drawing_points) < MIN_POINTS:
            QMessageBox.warning(
                self,
                "위험지역 설정",
                f"영상을 클릭해 꼭짓점을 {MIN_POINTS}개 이상 찍어주세요.",
            )
            return

        points = self.video_widget.finish_drawing()
        self.set_edit_mode(False)
        self.zone_panel.add_zone(points)
        self.zone_edit_applied.emit()

    def cancel_zone_edit(self) -> None:
        self.video_widget.finish_drawing()
        self.set_edit_mode(False)
        self.zone_edit_canceled.emit()

    def load_zone_file(self) -> None:
        try:
            zones = load_zones(self.video_path)
        except (OSError, ZoneFileError) as error:
            zones = []
            QMessageBox.warning(
                self,
                "위험구역 불러오기 실패",
                f"위험구역 파일을 읽을 수 없어 빈 목록으로 시작합니다.\n"
                f"구역을 추가하거나 삭제하면 이 파일을 덮어씁니다.\n\n"
                f"{zone_file_path(self.video_path)}\n{error}",
            )

        self.loading_zones = True
        try:
            self.zone_panel.set_zones(zones)
        finally:
            self.loading_zones = False

    @Slot(list)
    def save_zone_file(self, zones: list[Zone]) -> None:
        if self.loading_zones or self.video_path is None:
            return
        try:
            save_zones(self.video_path, zones)
        except OSError as error:
            QMessageBox.warning(
                self,
                "위험구역 저장 실패",
                f"위험구역 파일을 저장할 수 없습니다.\n\n{zone_file_path(self.video_path)}\n{error}",
            )

    def update_zone_overlay(self) -> None:
        zones = self.zone_panel.zones
        self.video_widget.set_zones(zones, self.zone_panel.selected_index())
        state = self.intrusion_monitor.set_zones(zones)
        self.video_widget.set_monitor_state(state)

    @Slot(object, int)
    def record_live_frame(self, frame, frame_index: int) -> None:
        if self.live_recorder is None:
            return
        try:
            self.live_recorder.add_frame(frame, frame_index / self.video_widget.fps)
        except OSError as error:
            self.on_live_record_failed(error)

    def finish_live_recording(self) -> None:
        recorder, self.live_recorder = self.live_recorder, None
        if recorder is None:
            return
        try:
            # 경보 중에 연결을 끊으면 끊은 시각을 해제 시각으로 CSV 에 남긴다
            recorder.finish(self.intrusion_monitor.close_alarms())
        except OSError as error:
            QMessageBox.warning(
                self, "사건 저장 실패", f"침입 사건 클립/CSV를 저장할 수 없습니다.\n\n{error}"
            )

    def on_live_record_failed(self, error: OSError) -> None:
        # 같은 오류 창이 프레임마다 뜨지 않도록 이번 연결에서는 녹화를 멈춘다
        self.live_recorder = None
        QMessageBox.warning(
            self,
            "사건 저장 실패",
            f"실시간 침입 사건 클립/CSV를 저장할 수 없어 이번 연결에서는 녹화를 멈춥니다.\n\n{error}",
        )

    @Slot(int, object)
    def on_detections(self, frame_index: int, detections: list[Detection]) -> None:
        state = self.intrusion_monitor.update(detections, frame_index, self.video_widget.fps)
        if self.live_recorder is not None:
            try:
                self.live_recorder.update(
                    state == MonitorState.ALARM,
                    frame_index / self.video_widget.fps,
                    self.intrusion_monitor.new_events,
                )
            except OSError as error:
                self.on_live_record_failed(error)
        elif self.intrusion_monitor.new_events and self.video_path is not None:
            try:
                save_event_records(self.intrusion_monitor.new_events, self.video_path)
            except OSError as error:
                QMessageBox.warning(
                    self,
                    "사건 저장 실패",
                    f"침입 사건 클립/CSV를 저장할 수 없습니다.\n\n{error}",
                )
        self.video_widget.set_detections(frame_index, detections)
        self.video_widget.set_monitor_state(state)

    def set_edit_mode(self, editing: bool) -> None:
        self.zone_panel.set_edit_mode(editing)
        self.video_widget.set_controls_enabled(not editing)
        self.source_tabs.setEnabled(not editing)

    @Slot(str)
    def on_detection_failed(self, message: str) -> None:
        QMessageBox.warning(
            self,
            "사람 탐지 불가",
            f"YOLO 모델을 불러오지 못해 사람 탐지 없이 영상만 재생합니다.\n"
            f"처음 실행이라면 모델을 내려받을 수 있도록 인터넷 연결을 확인하세요.\n\n{message}",
        )

    def closeEvent(self, event) -> None:
        self.finish_live_recording()
        self.video_widget.close_video()
        self.person_detection.stop()
        super().closeEvent(event)
