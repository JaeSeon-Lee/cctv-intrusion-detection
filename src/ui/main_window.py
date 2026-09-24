from PySide6.QtWidgets import QMainWindow, QSplitter, QWidget, QVBoxLayout, QInputDialog, QMessageBox
from PySide6.QtCore import Qt
from ui.widget.file_tree import FileTree
from ui.widget.video_widget import VideoWidget
from ui.widget.tool_bar import ToolBar

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("CCTV Viewer")
        self.resize(1400, 1000)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.tool_bar = ToolBar()
        self.file_tree = FileTree()
        self.video_widget = VideoWidget()

        splitter.addWidget(self.file_tree)
        splitter.addWidget(self.video_widget)
        splitter.setSizes([300, 900])

        self.file_tree.file_selected.connect(
            self.video_widget.set_video
        )
        self.tool_bar.stream_button.clicked.connect(self.on_stream_clicked)

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
            source = text       # rtsp://, http:// 등 URL
        else:
            QMessageBox.warning(self, "입력 오류", "RTSP URL(rtsp://...) 또는 웹캠 번호(0, 1 ...)를 입력하세요.")
            return

        if self.video_widget.open_source(source, is_stream=True):
            # 파일 트리의 선택 표시는 지워서 지금 보고 있는 게 스트림임을 알 수 있게 함
            self.file_tree.tree.clearSelection()

    def closeEvent(self, event):
        # 창을 닫을 때 열려 있는 영상 자원 정리
        self.video_widget.close_video()
        super().closeEvent(event)
