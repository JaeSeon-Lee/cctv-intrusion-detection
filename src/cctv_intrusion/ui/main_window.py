from pathlib import Path

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QSplitter,
)

from cctv_intrusion.detection import PersonDetection
from cctv_intrusion.ui.widget.file_tree import FileTree
from cctv_intrusion.ui.widget.video_widget import VideoWidget
from cctv_intrusion.ui.widget.zone_panel import ZonePanel
from cctv_intrusion.zone import ZoneFileError, load_zones, save_zones, zone_file_path

# 영상을 열 때 창 크기를 영상에 맞추는 기준
# 창이 화면(작업표시줄 제외)에서 차지할 수 있는 최대 비율
MAX_SCREEN_RATIO = 0.9
# 영상은 원본보다 크게 늘리지 않지만, 작은 영상은 화면에서 이 너비(px)까지는 키워서 보여준다
MIN_VIDEO_WIDTH = 800


class MainWindow(QMainWindow):
    """메인 창

    팀원 연동용 Signal (팀원 코드에서 .connect(함수)로 연결해서 사용)
      - window.video_widget.source_opened(str)        : 영상을 열었을 때
      - window.video_widget.frame_ready(ndarray, int) : 프레임을 표시할 때마다
      - window.zone_edit_started()                    : [위험지역 설정] 클릭
      - window.zone_edit_applied()                    : [완료] 클릭
      - window.zone_edit_canceled()                   : [취소] 클릭
      - window.zone_panel.zones_changed(list)         : 위험구역이 추가/삭제될 때 (전체 구역 목록)
          [{"name": "구역 1", "points": [(x, y), ...]}, ...]  # points: 원본 프레임 픽셀 좌표
          영상을 열 때 그 영상의 구역 파일을 불러온 직후에도 발생한다.
      - window.person_detection.detected(int, list)   : 사람 탐지 결과가 나올 때마다
          (프레임 번호, [Detection(x1, y1, x2, y2, confidence), ...])  # 원본 프레임 픽셀 좌표
          추론이 재생보다 느리면 중간 프레임은 건너뛰므로 모든 프레임 번호가 오지는 않는다.

    위험구역은 동영상과 같은 폴더의 같은 이름 .json 파일에 저장된다 (cctv_intrusion.zone 참고).
    """

    zone_edit_started = Signal()
    zone_edit_applied = Signal()
    zone_edit_canceled = Signal()

    def __init__(self):
        super().__init__()

        self.setWindowTitle("CCTV Viewer")

        self.video_path = None  # 지금 열려 있는 영상 경로 (위험구역 파일 위치를 정하는 데 사용)
        self.loading_zones = False  # True면 파일에서 불러오는 중이라 저장하지 않음
        self.resize(1400, 1000)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.file_tree = FileTree()
        self.video_widget = VideoWidget()
        self.zone_panel = ZonePanel()

        # 파일 트리 | 영상 | 위험구역 패널
        splitter.addWidget(self.file_tree)
        splitter.addWidget(self.video_widget)
        splitter.addWidget(self.zone_panel)
        splitter.setSizes([280, 860, 260])
        # 창 크기가 바뀌면 늘어나거나 줄어든 만큼 영상만 커지거나 작아지고, 양옆 패널은 너비를 유지한다
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)

        self.file_tree.file_selected.connect(self.video_widget.set_video)
        self.zone_panel.zone_button.clicked.connect(self.start_zone_edit)
        self.zone_panel.apply_button.clicked.connect(self.apply_zone_edit)
        self.zone_panel.cancel_button.clicked.connect(self.cancel_zone_edit)

        # 위험구역이 추가/삭제되거나 선택이 바뀌면 영상 위 표시를 다시 그림
        self.zone_panel.zones_changed.connect(self.update_zone_overlay)
        self.zone_panel.selection_changed.connect(self.update_zone_overlay)
        # 위험구역이 추가/삭제될 때마다 영상 옆 json 파일에 저장
        self.zone_panel.zones_changed.connect(self.save_zone_file)

        self.video_widget.source_opened.connect(self.on_source_opened)

        # 사람 탐지: 표시하는 프레임마다 워커 스레드로 보내고, 결과 박스를 영상 위에 그린다
        self.person_detection = PersonDetection()
        self.video_widget.frame_ready.connect(self.person_detection.submit)
        self.person_detection.detected.connect(self.video_widget.set_detections)
        self.person_detection.failed.connect(self.on_detection_failed)
        self.person_detection.start()

        self.setCentralWidget(splitter)

    def on_source_opened(self, source):
        # 이전 영상에서 탐지 중이던 결과가 새 영상 위에 그려지지 않도록 버린다
        self.person_detection.reset()
        # 영상이 열리면 [위험지역 설정] 버튼 활성화
        self.zone_panel.zone_button.setEnabled(True)
        self.video_path = Path(source)
        self.load_zone_file()
        self.fit_to_video()

    def fit_to_video(self):
        # 영상 표시 영역이 영상 비율과 딱 맞도록(검은 여백 없이) 창 크기를 바꾸고 화면 가운데로 옮긴다.
        # 사용자가 최대화/전체화면으로 둔 창은 건드리지 않는다.
        if self.isMaximized() or self.isFullScreen():
            return
        video_width, video_height = self.video_widget.frame_size()
        if video_width <= 0 or video_height <= 0:
            return

        label = self.video_widget.label
        # 창 전체(테두리 포함)에서 영상 라벨을 뺀 나머지 크기: 파일 트리, 위험구역 패널, 재생 컨트롤, 창 테두리
        extra_width = self.frameGeometry().width() - label.width()
        extra_height = self.frameGeometry().height() - label.height()

        screen = self.screen().availableGeometry()
        max_width = screen.width() * MAX_SCREEN_RATIO - extra_width
        max_height = screen.height() * MAX_SCREEN_RATIO - extra_height

        # 화면에 들어가는 가장 큰 배율. 단, 원본(1배)보다 키우지 않고 작은 영상만 MIN_VIDEO_WIDTH 까지 키운다
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
        # move는 창 테두리를 포함한 왼쪽 위 위치를 정한다
        self.move(
            screen.x() + (screen.width() - (label_width + extra_width)) // 2,
            screen.y() + (screen.height() - (label_height + extra_height)) // 2,
        )

    # ------------------------------------------------------------
    # 위험지역 편집 모드
    # (UI는 영상 클릭으로 꼭짓점 좌표만 모아서 구역으로 등록한다.
    #  침입 판단은 팀원 담당: zone_panel.zones_changed 로 구역 좌표를 받아서 사용)
    # ------------------------------------------------------------
    def start_zone_edit(self):
        self.video_widget.pause()
        self.set_edit_mode(True)
        self.video_widget.start_drawing()
        self.zone_edit_started.emit()

    def apply_zone_edit(self):
        # 다각형은 꼭짓점이 3개 이상 있어야 하므로, 부족하면 편집 모드를 유지한다
        if len(self.video_widget.drawing_points) < 3:
            QMessageBox.warning(
                self, "위험지역 설정", "영상을 클릭해 꼭짓점을 3개 이상 찍어주세요."
            )
            return

        points = self.video_widget.finish_drawing()
        self.set_edit_mode(False)
        self.zone_panel.add_zone(points)
        self.zone_edit_applied.emit()

    def cancel_zone_edit(self):
        self.video_widget.finish_drawing()  # 찍은 점은 버림
        self.set_edit_mode(False)
        self.zone_edit_canceled.emit()

    # ------------------------------------------------------------
    # 위험구역 파일 (동영상 옆 같은 이름 .json)
    # ------------------------------------------------------------
    def load_zone_file(self) -> None:
        # 영상에 딸린 위험구역 파일이 있으면 불러와 바로 적용하고, 없으면 구역 목록을 비운다
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

        # 불러온 내용을 그대로 다시 저장하지 않도록 막아둔다
        # (특히 파일이 없을 때 빈 json이 생기거나, 읽기 실패한 파일을 바로 덮어쓰는 것을 방지)
        self.loading_zones = True
        try:
            self.zone_panel.set_zones(zones)
        finally:
            self.loading_zones = False

    @Slot(list)
    def save_zone_file(self, zones: list[dict]) -> None:
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

    def update_zone_overlay(self):
        self.video_widget.set_zones(self.zone_panel.zones, self.zone_panel.selected_index())

    def set_edit_mode(self, editing):
        self.zone_panel.set_edit_mode(editing)
        # 편집 중에는 재생 컨트롤(버튼, 슬라이더, 단축키) 비활성화
        self.video_widget.set_controls_enabled(not editing)
        # 편집 중에 다른 영상으로 바뀌지 않도록 파일 트리도 잠금
        self.file_tree.setEnabled(not editing)

    @Slot(str)
    def on_detection_failed(self, message: str) -> None:
        QMessageBox.warning(
            self,
            "사람 탐지 불가",
            f"YOLO 모델을 불러오지 못해 사람 탐지 없이 영상만 재생합니다.\n"
            f"처음 실행이라면 모델을 내려받을 수 있도록 인터넷 연결을 확인하세요.\n\n{message}",
        )

    def closeEvent(self, event):
        # 창을 닫을 때 열려 있는 영상 자원 정리, 탐지 스레드 종료
        self.video_widget.close_video()
        self.person_detection.stop()
        super().closeEvent(event)
