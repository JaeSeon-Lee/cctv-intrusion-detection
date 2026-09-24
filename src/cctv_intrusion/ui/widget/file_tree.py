from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileSystemModel,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from cctv_intrusion.paths import DATA_DIR, OUTPUT_DIR
from cctv_intrusion.ui.styles import load_qss


class FileTree(QWidget):
    file_selected = Signal(str)

    def __init__(self):
        super().__init__()

        # Qt 함수에는 문자열 경로를 넘긴다
        data_path = str(DATA_DIR)
        output_path = str(OUTPUT_DIR)

        # 침입 클립이 저장될 output 폴더가 없으면 미리 만들어둔다 (git clone 직후에는 빈 폴더가 없음)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        # QFileSystemModel은 폴더를 감시하다가 파일이 추가/삭제되면 트리를 자동으로 갱신해준다.
        # 따라서 팀원 모듈이 output 폴더에 클립을 저장하면 별도 코드 없이 트리에 나타난다.
        self.model = QFileSystemModel()
        self.model.setRootPath(data_path)
        self.model.setNameFilters(["*.mp4", "*.avi", "*.mov", "*.mkv"])
        self.model.setNameFilterDisables(False)

        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setRootIndex(self.model.index(data_path))

        # 파일 이름 이외 컬럼 보이지 않게 설정.
        self.tree.setColumnHidden(1, True)  # Size
        self.tree.setColumnHidden(2, True)  # Type
        self.tree.setColumnHidden(3, True)  # Date Modified
        self.tree.setHeaderHidden(True)

        # output 폴더는 처음부터 펼쳐서 새 클립이 바로 보이게 함
        self.tree.expand(self.model.index(output_path))

        self.tree.setStyleSheet(load_qss("file_tree"))

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tree)

        self.setLayout(layout)

        self.tree.clicked.connect(self.on_clicked)

    def on_clicked(self, index):
        path = self.model.filePath(index)

        if path.lower().endswith((".mp4", ".avi", ".mov", ".mkv")):
            self.file_selected.emit(path)
