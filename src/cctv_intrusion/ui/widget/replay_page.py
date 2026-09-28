"""다시보기 탭 UI.

recordings/camN/ · 상시 .ts · 침입 .mp4 · events.csv
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

CONTINUOUS_SUFFIXES = (".ts",)
INTRUSION_SUFFIXES = (".mp4",)
VIDEO_SUFFIXES = CONTINUOUS_SUFFIXES + INTRUSION_SUFFIXES + (".avi", ".mov", ".mkv")


def list_intrusion_clips(*, recordings_dir: Path | None = None) -> list[Path]:
    """recordings/cam*/ 아래 침입 클립 .mp4."""
    root = recordings_dir or RECORDINGS_DIR
    if not root.is_dir():
        return []
    clips: list[Path] = []
    for cam_dir in sorted(root.glob("cam*")):
        if not cam_dir.is_dir():
            continue
        clips.extend(
            path
            for path in cam_dir.iterdir()
            if path.is_file() and path.suffix.lower() in INTRUSION_SUFFIXES
        )
    return sorted(clips, key=lambda p: (p.parent.name, p.name))


class ReplayPage(QWidget):
    """다시보기: 좌측(상시 녹화 + 침입 클립) · 중앙 재생기 · 배속."""

    file_selected = Signal(str)

    def __init__(self) -> None:
        super().__init__()

        RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
        root = str(RECORDINGS_DIR)

        self.model = QFileSystemModel()
        self.model.setRootPath(root)
        self.model.setNameFilters([f"*{suffix}" for suffix in CONTINUOUS_SUFFIXES])
        self.model.setNameFilterDisables(False)

        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setRootIndex(self.model.index(root))
        self.tree.setColumnHidden(1, True)
        self.tree.setColumnHidden(2, True)
        self.tree.setColumnHidden(3, True)
        self.tree.setHeaderHidden(True)
        self.tree.clicked.connect(self._on_recording_clicked)

        rec_title = QLabel("상시 녹화")
        rec_title.setObjectName("panelTitle")
        rec_subtitle = QLabel("recordings/camN/ · .ts (캠별 폴더)")
        rec_subtitle.setObjectName("panelSubtitle")

        self.clips_title = QLabel("침입 클립")
        self.clips_title.setObjectName("panelTitle")
        self.clips_subtitle = QLabel("recordings/camN/ · .mp4 · events.csv")
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
        self.player.label.setText("왼쪽에서 녹화본 또는 침입 클립을 선택하세요")

        hint = QLabel(
            "상시 녹화·침입 클립·사건 CSV 는 캠별 폴더(recordings/cam1 … cam4)에 저장됩니다."
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
        self.refresh_intrusion_clips()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.refresh_intrusion_clips()

    def refresh_intrusion_clips(self) -> None:
        clips = list_intrusion_clips()
        self.clips_list.clear()
        for clip in clips:
            label = f"{clip.parent.name}/{clip.name}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, str(clip))
            self.clips_list.addItem(item)
        self.clips_subtitle.setText(
            f"recordings/camN/ · {len(clips)}개"
            if clips
            else "recordings/camN/ · 침입 클립 없음"
        )

    @Slot(object)
    def _on_recording_clicked(self, index) -> None:
        path = Path(self.model.filePath(index))
        if path.suffix.lower() not in CONTINUOUS_SUFFIXES:
            return
        if path.is_dir():
            return
        self.file_selected.emit(str(path))
        self.player.set_video(str(path))
        self.refresh_intrusion_clips()

    @Slot(object)
    def _on_clip_clicked(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self.file_selected.emit(str(path))
            self.player.set_video(str(path))
