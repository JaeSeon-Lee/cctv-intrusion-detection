"""다시보기 탭 UI.

상시 녹화본을 골라 재생하는 화면. 녹화 파이프라인은 별도 작업.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileSystemModel,
    QLabel,
    QSplitter,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from cctv_intrusion.paths import RECORDINGS_DIR
from cctv_intrusion.ui.styles import load_qss
from cctv_intrusion.ui.widget.video_widget import VideoWidget


class ReplayPage(QWidget):
    """다시보기: 좌측 녹화 목록 + 중앙 재생기."""

    file_selected = Signal(str)

    def __init__(self) -> None:
        super().__init__()

        RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
        root = str(RECORDINGS_DIR)

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
        self.tree.clicked.connect(self._on_clicked)

        title = QLabel("녹화 목록")
        title.setObjectName("panelTitle")
        subtitle = QLabel("CAM별 상시 녹화본이 여기에 쌓입니다")
        subtitle.setObjectName("panelSubtitle")

        side = QWidget()
        side.setObjectName("replaySide")
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(0)
        side_layout.addWidget(title)
        side_layout.addWidget(subtitle)
        side_layout.addWidget(self.tree, 1)

        self.player = VideoWidget(compact=False)
        self.player.label.setText("왼쪽에서 녹화본을 선택하세요")

        hint = QLabel(
            "CCTV 탭은 탭을 바꿔도 계속 동작합니다.\n"
            "상시 녹화(화면 그대로 저장)는 다음 작업에서 연결됩니다."
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

        player_wrap = QWidget()
        player_layout = QVBoxLayout(player_wrap)
        player_layout.setContentsMargins(0, 0, 0, 0)
        player_layout.setSpacing(0)
        player_layout.addWidget(self.player, 1)
        player_layout.addWidget(hint)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(side)
        splitter.addWidget(player_wrap)
        splitter.setSizes([280, 1000])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

        self.setStyleSheet(load_qss("replay_page"))

    def _on_clicked(self, index) -> None:
        path = self.model.filePath(index)
        if path.lower().endswith((".mp4", ".avi", ".mov", ".mkv")):
            self.file_selected.emit(path)
            self.player.set_video(path)
