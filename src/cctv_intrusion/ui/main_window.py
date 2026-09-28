from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QSplitter,
    QTabWidget,
)

from cctv_intrusion.detection import Detection, PersonDetection
from cctv_intrusion.intrusion import (
    IntrusionMonitor,
    LiveRecorder,
    MonitorState,
)
from cctv_intrusion.paths import OUTPUT_DIR, RECORDINGS_DIR, SCREEN_COUNT, screen_recordings_dir
from cctv_intrusion.ui.widget.camera_grid import CameraGrid
from cctv_intrusion.ui.widget.file_tree import FileTree
from cctv_intrusion.ui.widget.replay_page import ReplayPage
from cctv_intrusion.ui.widget.zone_panel import ZonePanel
from cctv_intrusion.video import ContinuousRecorder, compose_overlay_frame
from cctv_intrusion.zone import (
    MIN_POINTS,
    Zone,
    ZoneFileError,
    load_zones,
    save_zones,
    screen_zone_path,
)

WINDOW_SCREEN_RATIO = 0.92
SPLITTER_SIZES = (220, 1100, 260)


class MainWindow(QMainWindow):
    """공장형 CCTV 모니터.

    탭: CCTV(4분할) / 다시보기
    CCTV 탭을 벗어나도 4분할 재생·탐지는 계속 돈다.
    """

    zone_edit_started = Signal()
    zone_edit_applied = Signal()
    zone_edit_canceled = Signal()

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("침입 감지 모니터")
        self.loading_zones = False
        self.editing = False

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)

        self.monitors = {i: IntrusionMonitor() for i in range(1, SCREEN_COUNT + 1)}
        self.live_recorders: dict[int, LiveRecorder] = {}
        # 상시 녹화: 탭 전환과 무관하게 frame_ready 에서 계속 기록
        self.continuous_recorders: dict[int, ContinuousRecorder] = {}

        self.file_tree = FileTree()
        self.camera_grid = CameraGrid()
        self.zone_panel = ZonePanel()

        cctv_splitter = QSplitter(Qt.Orientation.Horizontal)
        cctv_splitter.setHandleWidth(2)
        cctv_splitter.setChildrenCollapsible(False)
        cctv_splitter.addWidget(self.file_tree)
        cctv_splitter.addWidget(self.camera_grid)
        cctv_splitter.addWidget(self.zone_panel)
        cctv_splitter.setSizes(list(SPLITTER_SIZES))
        cctv_splitter.setStretchFactor(0, 0)
        cctv_splitter.setStretchFactor(1, 1)
        cctv_splitter.setStretchFactor(2, 0)
        self.cctv_splitter = cctv_splitter

        self.replay_page = ReplayPage()

        self.main_tabs = QTabWidget()
        self.main_tabs.setObjectName("mainTabs")
        self.main_tabs.addTab(cctv_splitter, "CCTV")
        self.main_tabs.addTab(self.replay_page, "다시보기")

        self.setCentralWidget(self.main_tabs)
        self._fit_to_screen()

        self.file_tree.file_selected.connect(self.on_file_selected)
        self.camera_grid.selection_changed.connect(self.on_screen_selected)
        self.camera_grid.frame_ready.connect(self.on_frame_ready)
        self.camera_grid.source_opened.connect(self.on_source_opened)
        self.camera_grid.source_lost.connect(self.on_source_lost)

        self.zone_panel.zone_button.clicked.connect(self.start_zone_edit)
        self.zone_panel.apply_button.clicked.connect(self.apply_zone_edit)
        self.zone_panel.cancel_button.clicked.connect(self.cancel_zone_edit)
        self.zone_panel.zones_changed.connect(self.update_zone_overlay)
        self.zone_panel.selection_changed.connect(self.update_zone_overlay)
        self.zone_panel.zones_changed.connect(self.save_zone_file)

        self.person_detection = PersonDetection()
        self.person_detection.detected.connect(self.on_detections)
        self.person_detection.failed.connect(self.on_detection_failed)
        self.person_detection.start()

        QShortcut(QKeySequence(Qt.Key.Key_Escape), self).activated.connect(self.on_escape)

        self.load_screen_zones(self.camera_grid.selected_index)
        self.camera_grid.start_webcam()

    def _fit_to_screen(self) -> None:
        """가용 화면의 약 92% 크기로 맞추고 가운데 배치한다."""
        screen = self.screen().availableGeometry()
        width = max(1280, int(screen.width() * WINDOW_SCREEN_RATIO))
        height = max(800, int(screen.height() * WINDOW_SCREEN_RATIO))
        width = min(width, screen.width())
        height = min(height, screen.height())
        self.resize(width, height)
        self.move(
            screen.x() + (screen.width() - width) // 2,
            screen.y() + (screen.height() - height) // 2,
        )

    @Slot()
    def on_escape(self) -> None:
        if self.editing:
            self.cancel_zone_edit()
            return
        if self.camera_grid.focused_index is not None:
            self.camera_grid.clear_focus()

    def selected_video(self):
        return self.camera_grid.video(self.camera_grid.selected_index)

    @Slot(str)
    def on_file_selected(self, path: str) -> None:
        if self.editing:
            return
        self.camera_grid.assign_video(path)

    @Slot(int)
    def on_screen_selected(self, screen_index: int) -> None:
        if self.editing:
            return
        self.load_screen_zones(screen_index)

    @Slot(int, str)
    def on_source_opened(self, screen_index: int, source: str) -> None:
        del source
        self.finish_live_recording(screen_index)
        self.stop_continuous_recording(screen_index)
        video = self.camera_grid.video(screen_index)
        monitor = self.monitors[screen_index]

        # 화면별 구역은 유지 — 체류/경보만 리셋 후 구역 다시 적용
        zones = load_zones(screen_zone_path(screen_index))
        monitor.reset()
        state = monitor.set_zones(zones)
        video.set_zones(
            zones,
            self.zone_panel.selected_index()
            if screen_index == self.camera_grid.selected_index
            else -1,
        )
        video.set_monitor_state(state)

        # 파일 캠도 CCTV(웹캠)와 동일: 실시간 버퍼 방식 침입 클립 (해제 후 5초 안 재경보면 이어쓰기)
        self.live_recorders[screen_index] = LiveRecorder(
            output_dir=screen_recordings_dir(screen_index)
        )

        self.start_continuous_recording(screen_index)

        if screen_index == self.camera_grid.selected_index:
            self.loading_zones = True
            try:
                self.zone_panel.set_zones(zones)
            finally:
                self.loading_zones = False
            self.zone_panel.zone_button.setEnabled(True)

    @Slot(int)
    def on_source_lost(self, screen_index: int) -> None:
        self.finish_live_recording(screen_index)
        self.stop_continuous_recording(screen_index)
        self.camera_grid.video(screen_index).close_video()
        self.monitors[screen_index].reset()
        if screen_index == 1:
            QMessageBox.warning(
                self,
                "카메라 연결 끊김",
                "웹캠에서 영상을 받을 수 없어 연결을 해제했습니다.",
            )

    @Slot(int, object, int)
    def on_frame_ready(self, screen_index: int, frame, frame_index: int) -> None:
        self.person_detection.submit(frame, frame_index, screen_index)
        video = self.camera_grid.video(screen_index)

        continuous = self.continuous_recorders.get(screen_index)
        if continuous is not None:
            try:
                overlaid = compose_overlay_frame(
                    frame,
                    video.zones,
                    video.detections,
                    video.monitor_state,
                    selected_index=video.selected_zone,
                )
                continuous.write(overlaid)
            except OSError as error:
                self.on_continuous_record_failed(screen_index, error)

        recorder = self.live_recorders.get(screen_index)
        if recorder is None:
            return
        try:
            recorder.add_frame(frame, frame_index / video.fps)
        except OSError as error:
            self.on_live_record_failed(screen_index, error)

    def load_screen_zones(self, screen_index: int) -> None:
        path = screen_zone_path(screen_index)
        try:
            zones = load_zones(path)
        except (OSError, ZoneFileError) as error:
            zones = []
            QMessageBox.warning(
                self,
                "위험구역 불러오기 실패",
                f"화면 {screen_index} 위험구역을 읽을 수 없어 빈 목록으로 시작합니다.\n\n"
                f"{path}\n{error}",
            )

        self.loading_zones = True
        try:
            self.zone_panel.set_zones(zones)
        finally:
            self.loading_zones = False

        state = self.monitors[screen_index].set_zones(zones)
        video = self.camera_grid.video(screen_index)
        video.set_zones(zones, self.zone_panel.selected_index())
        video.set_monitor_state(state)
        self.zone_panel.zone_button.setEnabled(True)

    @Slot(list)
    def save_zone_file(self, zones: list[Zone]) -> None:
        if self.loading_zones:
            return
        screen_index = self.camera_grid.selected_index
        path = screen_zone_path(screen_index)
        try:
            save_zones(path, zones)
        except OSError as error:
            QMessageBox.warning(
                self,
                "위험구역 저장 실패",
                f"위험구역을 저장할 수 없습니다.\n\n{path}\n{error}",
            )

    def update_zone_overlay(self) -> None:
        screen_index = self.camera_grid.selected_index
        zones = self.zone_panel.zones
        self.camera_grid.video(screen_index).set_zones(zones, self.zone_panel.selected_index())
        state = self.monitors[screen_index].set_zones(zones)
        self.camera_grid.video(screen_index).set_monitor_state(state)

    def start_zone_edit(self) -> None:
        video = self.selected_video()
        if video.render is None:
            QMessageBox.information(
                self,
                "위험지역 설정",
                "먼저 화면에 영상(또는 웹캠)이 재생 중이어야 합니다.",
            )
            return
        # 구역 편집 중에도 CCTV 재생은 계속한다 (일시정지하지 않음)
        self.set_edit_mode(True)
        video.start_drawing()
        if not video.is_playing():
            video.play()
        self.zone_edit_started.emit()

    def apply_zone_edit(self) -> None:
        video = self.selected_video()
        if len(video.drawing_points) < MIN_POINTS:
            QMessageBox.warning(
                self,
                "위험지역 설정",
                f"영상을 클릭해 꼭짓점을 {MIN_POINTS}개 이상 찍어주세요.",
            )
            return
        points = video.finish_drawing()
        self.set_edit_mode(False)
        self.zone_panel.add_zone(points)
        self.zone_edit_applied.emit()

    def cancel_zone_edit(self) -> None:
        self.selected_video().finish_drawing()
        self.set_edit_mode(False)
        self.zone_edit_canceled.emit()

    def set_edit_mode(self, editing: bool) -> None:
        self.editing = editing
        self.zone_panel.set_edit_mode(editing)
        self.file_tree.setEnabled(not editing)
        self.main_tabs.setTabEnabled(1, not editing)

    @Slot(int, int, object)
    def on_detections(
        self, screen_index: int, frame_index: int, detections: list[Detection]
    ) -> None:
        if screen_index not in self.monitors:
            return
        video = self.camera_grid.video(screen_index)
        monitor = self.monitors[screen_index]
        state = monitor.update(detections, frame_index, video.fps)

        recorder = self.live_recorders.get(screen_index)
        if recorder is not None:
            try:
                recorder.update(
                    state == MonitorState.ALARM,
                    frame_index / video.fps,
                    monitor.new_events,
                )
            except OSError as error:
                self.on_live_record_failed(screen_index, error)

        video.set_detections(frame_index, detections)
        video.set_monitor_state(state)

    def start_continuous_recording(self, screen_index: int) -> None:
        video = self.camera_grid.video(screen_index)
        width, height = video.frame_size()
        if width <= 0 or height <= 0:
            return
        try:
            self.continuous_recorders[screen_index] = ContinuousRecorder(
                screen_index,
                width,
                height,
                video.fps,
                recordings_dir=screen_recordings_dir(screen_index),
            )
        except OSError as error:
            QMessageBox.warning(
                self,
                "상시 녹화 실패",
                f"CAM{screen_index} 상시 녹화를 시작하지 못했습니다.\n\n{error}",
            )

    def stop_continuous_recording(self, screen_index: int) -> None:
        recorder = self.continuous_recorders.pop(screen_index, None)
        if recorder is None:
            return
        try:
            recorder.close()
        except OSError as error:
            QMessageBox.warning(
                self,
                "상시 녹화 종료 오류",
                f"CAM{screen_index} 상시 녹화 파일을 닫는 중 오류가 났습니다.\n\n{error}",
            )

    def on_continuous_record_failed(self, screen_index: int, error: OSError) -> None:
        recorder = self.continuous_recorders.pop(screen_index, None)
        if recorder is not None:
            try:
                recorder.close()
            except OSError:
                pass
        QMessageBox.warning(
            self,
            "상시 녹화 중단",
            f"CAM{screen_index} 상시 녹화를 멈춥니다.\n\n{error}",
        )

    def finish_live_recording(self, screen_index: int) -> None:
        recorder = self.live_recorders.pop(screen_index, None)
        if recorder is None:
            return
        try:
            recorder.finish(self.monitors[screen_index].close_alarms())
        except OSError as error:
            QMessageBox.warning(
                self,
                "사건 저장 실패",
                f"침입 사건 클립/CSV를 저장할 수 없습니다.\n\n{error}",
            )

    def on_live_record_failed(self, screen_index: int, error: OSError) -> None:
        self.live_recorders.pop(screen_index, None)
        QMessageBox.warning(
            self,
            "사건 저장 실패",
            f"실시간 사건 저장을 멈춰습니다.\n\n{error}",
        )

    @Slot(str)
    def on_detection_failed(self, message: str) -> None:
        QMessageBox.warning(
            self,
            "사람 탐지 불가",
            f"YOLO 모델을 불러오지 못해 사람 탐지 없이 영상만 재생합니다.\n\n{message}",
        )

    def closeEvent(self, event) -> None:
        for screen_index in list(self.live_recorders):
            self.finish_live_recording(screen_index)
        for screen_index in list(self.continuous_recorders):
            self.stop_continuous_recording(screen_index)
        self.camera_grid.close_all()
        self.person_detection.stop()
        super().closeEvent(event)
