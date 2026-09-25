from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QSplitter,
)

from cctv_intrusion.ui.widget.file_tree import FileTree
from cctv_intrusion.ui.widget.video_widget import VideoWidget
from cctv_intrusion.ui.widget.zone_panel import ZonePanel


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
    """

    zone_edit_started = Signal()
    zone_edit_applied = Signal()
    zone_edit_canceled = Signal()

    def __init__(self):
        super().__init__()

        self.setWindowTitle("CCTV Viewer")
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

        self.file_tree.file_selected.connect(self.video_widget.set_video)
        self.zone_panel.zone_button.clicked.connect(self.start_zone_edit)
        self.zone_panel.apply_button.clicked.connect(self.apply_zone_edit)
        self.zone_panel.cancel_button.clicked.connect(self.cancel_zone_edit)

        # 위험구역이 추가/삭제되거나 선택이 바뀌면 영상 위 표시를 다시 그림
        self.zone_panel.zones_changed.connect(self.update_zone_overlay)
        self.zone_panel.selection_changed.connect(self.update_zone_overlay)

        # 영상이 열리면 [위험지역 설정] 버튼 활성화
        self.video_widget.source_opened.connect(
            lambda source: self.zone_panel.zone_button.setEnabled(True)
        )

        self.setCentralWidget(splitter)

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

    def update_zone_overlay(self):
        self.video_widget.set_zones(self.zone_panel.zones, self.zone_panel.selected_index())

    def set_edit_mode(self, editing):
        self.zone_panel.set_edit_mode(editing)
        # 편집 중에는 재생 컨트롤(버튼, 슬라이더, 단축키) 비활성화
        self.video_widget.set_controls_enabled(not editing)
        # 편집 중에 다른 영상으로 바뀌지 않도록 파일 트리도 잠금
        self.file_tree.setEnabled(not editing)

    def closeEvent(self, event):
        # 창을 닫을 때 열려 있는 영상 자원 정리
        self.video_widget.close_video()
        super().closeEvent(event)
