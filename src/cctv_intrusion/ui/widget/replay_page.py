"""다시보기 탭 UI.

recordings/camN/ · 상시 .ts · 침입 .mp4 · events.csv
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QFileSystemModel,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from cctv_intrusion.intrusion.recording_stats import recording_stats
from cctv_intrusion.paths import RECORDINGS_DIR
from cctv_intrusion.ui.styles import load_qss
from cctv_intrusion.ui.widget.dashboard_dialog import DashboardDialog
from cctv_intrusion.ui.widget.video_widget import VideoWidget
from cctv_intrusion.video.playback_snapshot import cleanup_snapshot, snapshot_for_playback

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

        # 지금 쓰는 상시 녹화 경로들 — MainWindow 가 주입
        self._live_sources: Callable[[], set[str]] | None = None

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
        self.tree.selectionModel().selectionChanged.connect(self._update_dashboard_button)

        # 상시 녹화(.ts)를 선택했을 때만 활성화
        self.dashboard_button = QPushButton("대시보드")
        self.dashboard_button.setObjectName("dashboardButton")
        self.dashboard_button.setToolTip("선택한 상시 녹화의 침입 비율·횟수·지속 시간 보기")
        self.dashboard_button.setEnabled(False)
        self.dashboard_button.clicked.connect(self.open_dashboard)

        rec_title = QLabel("상시 녹화")
        rec_title.setObjectName("panelTitle")
        rec_subtitle = QLabel("recordings/camN/ · .ts (캠별 폴더)")
        rec_subtitle.setObjectName("panelSubtitle")

        self.clips_title = QLabel("침입 클립")
        self.clips_title.setObjectName("panelTitle")

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

        # 버튼 상하좌우 여백을 같게 두려고 QSS margin 대신 레이아웃 여백을 쓴다
        dashboard_bar = QWidget()
        dashboard_bar.setObjectName("dashboardBar")
        dashboard_layout = QVBoxLayout(dashboard_bar)
        dashboard_layout.setContentsMargins(12, 12, 12, 12)
        dashboard_layout.addWidget(self.dashboard_button)
        top_layout.addWidget(dashboard_bar)

        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(0)
        bottom_layout.addWidget(self.clips_title)
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

        self.player = VideoWidget(compact=False, paint_overlays=False)
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

        # 좌측 패널 제목·트리는 CCTV 탭 영상 목록과 같은 스타일을 쓴다
        self.setStyleSheet(load_qss("file_tree") + "\n" + load_qss("replay_page"))
        self.refresh_intrusion_clips()

    def set_live_sources(self, provider: Callable[[], set[str]]) -> None:
        """녹화 중인 상시 .ts 경로 집합을 돌려주는 콜백."""
        self._live_sources = provider

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

    def selected_recording(self) -> Path | None:
        """트리에서 고른 상시 녹화 .ts (폴더·선택 없음이면 None)."""
        indexes = self.tree.selectionModel().selectedIndexes()
        if not indexes:
            return None
        path = Path(self.model.filePath(indexes[0]))
        if path.suffix.lower() not in CONTINUOUS_SUFFIXES or not path.is_file():
            return None
        return path

    @Slot()
    def _update_dashboard_button(self) -> None:
        self.dashboard_button.setEnabled(self.selected_recording() is not None)

    @Slot()
    def open_dashboard(self) -> DashboardDialog | None:
        recording = self.selected_recording()
        if recording is None:
            return None
        live = str(recording.resolve()) in self._live_paths()
        # 녹화 중인 .ts 는 연 순간 길이만 보이므로 스냅샷으로 길이를 잰다
        snapshot = None
        if live:
            try:
                snapshot = snapshot_for_playback(recording)
            except OSError:
                snapshot = None
        try:
            stats = recording_stats(recording, video_path=snapshot)
        finally:
            if snapshot is not None:
                cleanup_snapshot(snapshot)
        dialog = DashboardDialog(recording, self, stats=stats, live=live)
        dialog.show()
        return dialog

    def _live_paths(self) -> set[str]:
        if self._live_sources is None:
            return set()
        return self._live_sources()

    def _play_path(self, path: Path) -> None:
        """닫힌 파일은 원본, 녹화 중 .ts 는 스냅샷으로 재생."""
        play = path
        owned_temp = None
        if path.suffix.lower() in CONTINUOUS_SUFFIXES and str(path.resolve()) in self._live_paths():
            try:
                owned_temp = snapshot_for_playback(path)
                play = owned_temp
            except OSError as error:
                QMessageBox.warning(
                    self,
                    "다시보기",
                    f"녹화 중인 파일을 재생용으로 준비하지 못했습니다.\n\n{error}",
                )
                return
        self.file_selected.emit(str(path))
        self.player.set_video(str(play), owned_temp=owned_temp)

    @Slot(object)
    def _on_recording_clicked(self, index) -> None:
        path = Path(self.model.filePath(index))
        if path.suffix.lower() not in CONTINUOUS_SUFFIXES:
            return
        if path.is_dir():
            return
        self._play_path(path)
        self.refresh_intrusion_clips()

    @Slot(object)
    def _on_clip_clicked(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            # 침입 클립을 재생하면 상시 녹화 선택(대시보드)은 풀린다
            self.tree.clearSelection()
            self._play_path(Path(path))
