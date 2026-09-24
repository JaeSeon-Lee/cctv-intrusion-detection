from PySide6.QtWidgets import QMainWindow, QSplitter, QWidget
from PySide6.QtCore import Qt
from ui.widget.file_tree import FileTree
from ui.widget.video_widget import VideoWidget

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("CCTV Viewer")
        self.resize(1400, 1000)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.file_tree = FileTree()
        self.video_widget = VideoWidget()

        splitter.addWidget(self.file_tree)
        splitter.addWidget(self.video_widget)
        splitter.setSizes([300, 900])

        self.file_tree.file_selected.connect(
            self.video_widget.set_video
        )

        self.setCentralWidget(splitter)

    def closeEvent(self, event):
        # 창을 닫을 때 열려 있는 영상 자원 정리
        self.video_widget.close_video()
        super().closeEvent(event)