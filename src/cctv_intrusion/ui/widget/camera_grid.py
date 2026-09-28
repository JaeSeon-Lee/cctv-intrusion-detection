"""CCTV 4분할 화면 셀 · 그리드."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from cctv_intrusion.paths import SCREEN_COUNT
from cctv_intrusion.ui.styles import load_qss
from cctv_intrusion.ui.widget.video_widget import VideoWidget

WEBCAM_INDEX = 0
_CELL_POSITIONS = ((0, 0), (0, 1), (1, 0), (1, 1))


class CameraCell(QFrame):
    """CAM N 한 칸. 클릭하면 선택, VideoWidget 으로 재생."""

    cell_selected = Signal(int)  # 1-based screen index
    focus_requested = Signal(int)  # 크게 보기 토글 요청
    frame_ready = Signal(int, object, int)  # screen, frame, frame_index
    source_opened = Signal(int, str)
    source_lost = Signal(int)

    def __init__(self, screen_index: int, *, webcam: bool = False) -> None:
        super().__init__()
        self.screen_index = screen_index
        self.webcam = webcam
        self._selected = False
        self._focused = False

        self.setObjectName("cameraCell")
        self.setProperty("selected", False)
        self.setProperty("focused", False)

        title_text = f"CAM {screen_index}"
        if webcam:
            title_text += "  ·  웹캠"
        self.title = QLabel(title_text)
        self.title.setObjectName("cameraCellTitle")

        self.expand_button = QPushButton("크게")
        self.expand_button.setObjectName("expandButton")
        self.expand_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.expand_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.expand_button.clicked.connect(self._on_expand_clicked)

        header = QWidget()
        header.setObjectName("cameraCellHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)
        header_layout.addWidget(self.title, 1)
        header_layout.addWidget(self.expand_button)

        self.video = VideoWidget(compact=True)
        self.video.frame_ready.connect(self._on_frame)
        self.video.source_opened.connect(self._on_source_opened)
        self.video.source_lost.connect(self._on_source_lost)
        self.video.label.mouse_pressed.connect(self._on_label_pressed)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(header)
        layout.addWidget(self.video, 1)
        self.setLayout(layout)

        self.title.mousePressEvent = self._on_title_pressed  # type: ignore[method-assign]
        self.title.mouseDoubleClickEvent = self._on_title_double  # type: ignore[method-assign]

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)

    def set_focused(self, focused: bool) -> None:
        self._focused = focused
        self.setProperty("focused", focused)
        self.expand_button.setText("분할" if focused else "크게")
        self.style().unpolish(self)
        self.style().polish(self)

    def _on_expand_clicked(self) -> None:
        self.cell_selected.emit(self.screen_index)
        self.focus_requested.emit(self.screen_index)

    def _on_title_pressed(self, event) -> None:
        self.cell_selected.emit(self.screen_index)
        QLabel.mousePressEvent(self.title, event)

    def _on_title_double(self, event) -> None:
        self.cell_selected.emit(self.screen_index)
        self.focus_requested.emit(self.screen_index)
        QLabel.mouseDoubleClickEvent(self.title, event)

    @Slot(float, float, object)
    def _on_label_pressed(self, _x: float, _y: float, _button) -> None:
        if not self.video.drawing:
            self.cell_selected.emit(self.screen_index)

    @Slot(object, int)
    def _on_frame(self, frame, frame_index: int) -> None:
        self.frame_ready.emit(self.screen_index, frame, frame_index)

    @Slot(str)
    def _on_source_opened(self, source: str) -> None:
        self.source_opened.emit(self.screen_index, source)

    @Slot()
    def _on_source_lost(self) -> None:
        self.source_lost.emit(self.screen_index)


class CameraGrid(QWidget):
    """2×2 CCTV 그리드. CAM1=웹캠, CAM2~4=파일 할당. 한 화면 크게 보기 지원."""

    selection_changed = Signal(int)  # 1-based
    focus_changed = Signal(object)  # int | None
    frame_ready = Signal(int, object, int)
    source_opened = Signal(int, str)
    source_lost = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self.selected_index = 1
        self.focused_index: int | None = None
        self.cells: list[CameraCell] = []

        self.grid = QGridLayout()
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(6)
        self.grid.setRowStretch(0, 1)
        self.grid.setRowStretch(1, 1)
        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(1, 1)

        for i, (row, col) in enumerate(_CELL_POSITIONS, start=1):
            cell = CameraCell(i, webcam=(i == 1))
            cell.cell_selected.connect(self.select)
            cell.focus_requested.connect(self.toggle_focus)
            cell.frame_ready.connect(self.frame_ready)
            cell.source_opened.connect(self.source_opened)
            cell.source_lost.connect(self.source_lost)
            self.cells.append(cell)
            self.grid.addWidget(cell, row, col)

        self.setLayout(self.grid)
        self.setStyleSheet(load_qss("camera_grid"))
        self.select(1)

    def cell(self, screen_index: int) -> CameraCell:
        return self.cells[screen_index - 1]

    def video(self, screen_index: int) -> VideoWidget:
        return self.cell(screen_index).video

    @Slot(int)
    def select(self, screen_index: int) -> None:
        if not 1 <= screen_index <= SCREEN_COUNT:
            return
        self.selected_index = screen_index
        for cell in self.cells:
            cell.set_selected(cell.screen_index == screen_index)
        self.selection_changed.emit(screen_index)

    @Slot(int)
    def toggle_focus(self, screen_index: int) -> None:
        if self.focused_index == screen_index:
            self.clear_focus()
        else:
            self.set_focus(screen_index)

    def set_focus(self, screen_index: int) -> None:
        if not 1 <= screen_index <= SCREEN_COUNT:
            return
        self.select(screen_index)
        self.focused_index = screen_index
        for cell in self.cells:
            self.grid.removeWidget(cell)
            if cell.screen_index == screen_index:
                cell.show()
                cell.set_focused(True)
                self.grid.addWidget(cell, 0, 0, 2, 2)
            else:
                cell.hide()
                cell.set_focused(False)
        self.focus_changed.emit(screen_index)

    def clear_focus(self) -> None:
        self.focused_index = None
        for cell in self.cells:
            self.grid.removeWidget(cell)
            cell.show()
            cell.set_focused(False)
        for cell, (row, col) in zip(self.cells, _CELL_POSITIONS, strict=True):
            self.grid.addWidget(cell, row, col)
        self.focus_changed.emit(None)

    def start_webcam(self) -> None:
        self.video(1).open_camera(WEBCAM_INDEX, quiet=True)

    def assign_video(self, path: str) -> bool:
        """선택된 화면에 파일 재생. CAM1(웹캠)이면 거부."""
        if self.selected_index == 1:
            QMessageBox.information(
                self,
                "웹캠 전용",
                "CAM 1은 웹캠 전용입니다.\nCAM 2~4를 선택한 뒤 영상을 지정하세요.",
            )
            return False
        return self.video(self.selected_index).set_video(path)

    def close_all(self) -> None:
        for cell in self.cells:
            cell.video.close_video()
