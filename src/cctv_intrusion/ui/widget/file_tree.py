from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileSystemModel,
    QLabel,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from cctv_intrusion.paths import CCTV_DIR
from cctv_intrusion.ui.styles import load_qss


class FileTree(QWidget):
    """CCTV 영상 폴더(data/cctv) 파인더."""

    file_selected = Signal(str)

    def __init__(self):
        super().__init__()

        CCTV_DIR.mkdir(parents=True, exist_ok=True)
        root = str(CCTV_DIR)

        self.model = QFileSystemModel()
        self.model.setRootPath(root)
        self.model.setNameFilters(["*.mp4", "*.avi", "*.mov", "*.mkv"])
        self.model.setNameFilterDisables(False)

        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setRootIndex(self.model.index(root))
        self.tree.setColumnHidden(1, True)
        self.tree.setColumnHidden(2, True)
        self.tree.setColumnHidden(3, True)
        self.tree.setHeaderHidden(True)

        title = QLabel("영상 목록")
        title.setObjectName("panelTitle")
        subtitle = QLabel("화면을 고른 뒤 파일을 선택하세요")
        subtitle.setObjectName("panelSubtitle")

        self.setStyleSheet(load_qss("file_tree"))

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self.tree, 1)
        self.setLayout(layout)

        self.tree.clicked.connect(self.on_clicked)

    def on_clicked(self, index):
        path = self.model.filePath(index)
        if path.lower().endswith((".mp4", ".avi", ".mov", ".mkv")):
            self.file_selected.emit(path)
