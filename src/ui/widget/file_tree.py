from PySide6.QtWidgets import (
    QWidget,
    QTreeView,
    QVBoxLayout,
    QFileSystemModel,
)
from PySide6.QtCore import QDir, Signal

class FileTree(QWidget):
    file_selected = Signal(str)

    def __init__(self):
        super().__init__()

        data_path = QDir.current().filePath("./data")

        self.model = QFileSystemModel()
        self.model.setRootPath(data_path)
        self.model.setNameFilters(
            ["*.mp4", "*.avi", "*.mov", "*.mkv"]
        )
        self.model.setNameFilterDisables(False)

        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setRootIndex(
            self.model.index(data_path)
        )

        # 파일 이름 이외 컬럼 보이지 않게 설정.
        self.tree.setColumnHidden(1, True) # Size
        self.tree.setColumnHidden(2, True) # Type
        self.tree.setColumnHidden(3, True) # Date Modified
        self.tree.setHeaderHidden(True)

        self.tree.setStyleSheet("""
            QTreeView {
                background-color: #dfdfdf;
                font-size: 24px;
                color: #000;
                border: none;
            }
            QTreeView::item {
                padding: 12px 24px;
            }
            QTreeView::item:selected {
                background-color: #3a6ea5;
                color: white;
            }
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tree)

        self.setLayout(layout)

        self.tree.clicked.connect(self.on_clicked)

    def on_clicked(self, index):
        path = self.model.filePath(index)

        if path.lower().endswith((".mp4", ".avi", ".mov", ".mkv")):
            self.file_selected.emit(path)