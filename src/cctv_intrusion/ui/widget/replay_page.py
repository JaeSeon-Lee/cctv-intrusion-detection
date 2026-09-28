"""다시보기 탭 UI.

상단: data/recordings 상시 녹화본
하단: 선택한 녹화본과 같은 이름 폴더의 침입 클립
예) cam1.mp4 선택 → recordings/cam1/*.mp4 목록
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QFileSystemModel,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from cctv_intrusion.paths import RECORDINGS_DIR
from cctv_intrusion.ui.styles import load_qss
from cctv_intrusion.ui.widget.video_widget import VideoWidget

VIDEO_SUFFIXES = (".mp4", ".avi", ".mov", ".mkv")


def clips_dir_for(video_path: str | Path) -> Path:
    """녹화본 foo.mp4 → 같은 위치의 foo/ 폴더."""
    return Path(video_path).with_suffix("")


def list_related_clips(video_path: str | Path) -> list[Path]:
    folder = clips_dir_for(video_path)
    if not folder.is_dir():
        return []
    return sorted(
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in VIDEO_SUFFIXES
    )


class ReplayPage(QWidget):
    """다시보기: 좌측(녹화 + 침입 클립) · 중앙 재생기 · 배속."""

    file_selected = Signal(str)

    def __init__(self) -> None:
        super().__init__()

        RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
        root = str(RECORDINGS_DIR)
        self.current_recording: Path | None = None

        self.model = QFileSystemModel()
        self.model.setRootPath(root)
        self.model.setNameFilters([f"*{suffix}" for suffix in VIDEO_SUFFIXES])
        self.model.setNameFilterDisables(False)

        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setRootIndex(self.model.index(root))
        self.tree.setColumnHidden(1, True)
        self.tree.setColumnHidden(2, True)
        self.tree.setColumnHidden(3, True)
        self.tree.setHeaderHidden(True)
        self.tree.clicked.connect(self._on_recording_clicked)

        rec_title = QLabel("녹화 목록")
        rec_title.setObjectName("panelTitle")
        rec_subtitle = QLabel("상시 녹화본 · 클릭하면 아래 침입 클립이 열립니다")
        rec_subtitle.setObjectName("panelSubtitle")

        self.clips_title = QLabel("침입 클립")
        self.clips_title.setObjectName("panelTitle")
        self.clips_subtitle = QLabel("녹화본과 같은 이름 폴더")
        self.clips_subtitle.setObjectName("panelSubtitle")

        self.clips_list = QListWidget()
        self.clips_list.setObjectName("clipsList")
        self.clips_list.itemClicked.connect(self._on_clip_clicked)

        top = QWidget()
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(0)
        top_layout.addWidget(rec_title)
        top_layout.addWidget(rec_subtitle)
        top_layout.addWidget(self.tree, 1)

        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(0)
        bottom_layout.addWidget(self.clips_title)
        bottom_layout.addWidget(self.clips_subtitle)
        bottom_layout.addWidget(self.clips_list, 1)

        side_split = QSplitter(Qt.Orientation.Vertical)
        side_split.setHandleWidth(2)
        side_split.setChildrenCollapsible(False)
        side_split.addWidget(top)
        side_split.addWidget(bottom)
        side_split.setSizes([420, 280])
        side_split.setStretchFactor(0, 2)
        side_split.setStretchFactor(1, 1)

        side = QWidget()
        side.setObjectName("replaySide")
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.addWidget(side_split)

        self.player = VideoWidget(compact=False)
        self.player.label.setText("왼쪽에서 녹화본을 선택하세요")

        hint = QLabel(
            "배속은 하단 컨트롤에서 바꿀 수 있습니다.\n"
            "침입 클립은 녹화본과 같은 이름 폴더에 저장됩니다. "
            "(예: cam1.mp4 → cam1/)"
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
        splitter.setSizes([300, 1000])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

        self.setStyleSheet(load_qss("replay_page"))
        self._show_clips([])

    @Slot(object)
    def _on_recording_clicked(self, index) -> None:
        path = Path(self.model.filePath(index))
        if path.suffix.lower() not in VIDEO_SUFFIXES:
            return
        # 침입 클립 폴더(이름만 같은 디렉터리)는 녹화본이 아님
        if path.is_dir():
            return
        self.current_recording = path
        self.file_selected.emit(str(path))
        self.player.set_video(str(path))
        clips = list_related_clips(path)
        self._show_clips(clips)
        folder = clips_dir_for(path)
        self.clips_subtitle.setText(
            f"{folder.name}/  ·  {len(clips)}개"
            if clips
            else f"{folder.name}/  ·  클립 없음 (침입 시 여기에 저장)"
        )

    @Slot(object)
    def _on_clip_clicked(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self.file_selected.emit(str(path))
            self.player.set_video(str(path))

    def _show_clips(self, clips: list[Path]) -> None:
        self.clips_list.clear()
        for clip in clips:
            item = QListWidgetItem(clip.name)
            item.setData(Qt.ItemDataRole.UserRole, str(clip))
            self.clips_list.addItem(item)
