from typing import override

from PySide6.QtCore import Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QLabel


class VideoLabel(QLabel):
    """영상을 표시하는 QLabel. 마우스 누름 / 이동 / 뗌을 신호로 알려준다."""

    mouse_pressed = Signal(float, float, object)  # object: Qt.MouseButton
    mouse_moved = Signal(float, float)
    mouse_released = Signal()

    @override
    def mousePressEvent(self, event: QMouseEvent) -> None:
        pos = event.position()
        self.mouse_pressed.emit(pos.x(), pos.y(), event.button())

    @override
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position()
        self.mouse_moved.emit(pos.x(), pos.y())

    @override
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self.mouse_released.emit()
