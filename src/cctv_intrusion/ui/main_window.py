from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from cctv_intrusion.ui.widget.file_tree import FileTree
from cctv_intrusion.ui.widget.tool_bar import ToolBar
from cctv_intrusion.ui.widget.video_widget import VideoWidget
from cctv_intrusion.ui.widget.zone_panel import ZonePanel


class MainWindow(QMainWindow):
    """메인 창

    팀원 연동용 Signal (팀원 코드에서 .connect(함수)로 연결해서 사용)
      - window.video_widget.source_opened(str)        : 영상/스트림을 열었을 때
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

        self.tool_bar = ToolBar()
        self.file_tree = FileTree()
        self.video_widget = VideoWidget()
        self.zone_panel = ZonePanel()

        # 파일 트리 | 영상 | 위험구역 패널
        splitter.addWidget(self.file_tree)
        splitter.addWidget(self.video_widget)
        splitter.addWidget(self.zone_panel)
        splitter.setSizes([280, 860, 260])

        self.file_tree.file_selected.connect(self.video_widget.set_video)
        self.tool_bar.stream_button.clicked.connect(self.on_stream_clicked)
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

        # 상단 툴바 + 아래 (파일 트리 | 영상) 를 세로로 배치
        central = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.tool_bar)
        layout.addWidget(splitter, 1)
        central.setLayout(layout)

        self.setCentralWidget(central)

    def on_stream_clicked(self):
        # QInputDialog.getText: 한 줄 입력 다이얼로그. (입력 문자열, 확인 여부)를 돌려준다.
        text, ok = QInputDialog.getText(
            self,
            "스트림 연결",
            "RTSP URL 또는 웹캠 번호를 입력하세요.\n예) rtsp://192.168.0.10:554/stream , 0",
        )
        text = text.strip()
        if not ok or not text:
            return

        if text.isdigit():
            source = int(text)  # 웹캠 번호 (0, 1, ...)
        elif "://" in text:
            source = text  # rtsp://, http:// 등 URL
        else:
            QMessageBox.warning(
                self, "입력 오류", "RTSP URL(rtsp://...) 또는 웹캠 번호(0, 1 ...)를 입력하세요."
            )
            return

        if self.video_widget.open_source(source, is_stream=True):
            # 파일 트리의 선택 표시는 지워서 지금 보고 있는 게 스트림임을 알 수 있게 함
            self.file_tree.tree.clearSelection()

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
        self.tool_bar.set_edit_mode(editing)
        self.zone_panel.set_edit_mode(editing)
        # 편집 중에는 재생 컨트롤(버튼, 슬라이더, 단축키) 비활성화
        self.video_widget.set_controls_enabled(not editing)
        # 편집 중에 다른 영상으로 바뀌지 않도록 파일 트리도 잠금
        self.file_tree.setEnabled(not editing)

    def closeEvent(self, event):
        # 창을 닫을 때 열려 있는 영상 자원 정리
        self.video_widget.close_video()
        super().closeEvent(event)
