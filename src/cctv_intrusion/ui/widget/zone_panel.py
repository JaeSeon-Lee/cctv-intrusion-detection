from typing import override

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QMouseEvent, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from cctv_intrusion.ui.styles import load_qss
from cctv_intrusion.zone import (
    DEFAULT_LEVEL_ID,
    ZONE_LEVELS,
    Zone,
    format_zone_item,
    next_zone_number,
    normalize_level_id,
)


class ZoneList(QListWidget):
    """선택을 풀 수 있는 위험구역 리스트.

    빈 공간 클릭 또는 이미 선택된 항목을 다시 누르면 선택을 해제한다.
    """

    @override
    def mousePressEvent(self, event: QMouseEvent) -> None:
        item = self.itemAt(event.position().toPoint())
        if item is None or item.isSelected():
            self.clearSelection()
            return
        super().mousePressEvent(event)


class ZonePanel(QWidget):
    """우측 위험구역 패널.

    self.zones: list[Zone]
    버튼 동작은 MainWindow에서 clicked 신호에 연결한다.
    """

    zones_changed = Signal(list)
    selection_changed = Signal(int)

    def __init__(self) -> None:
        super().__init__()

        self.zones: list[Zone] = []
        self.next_number = 1
        self._syncing_level = False

        self.zone_button = QPushButton("위험지역 설정")
        self.apply_button = QPushButton("완료")
        self.cancel_button = QPushButton("취소")
        self.edit_label = QLabel(
            "영상을 클릭해 꼭짓점을 3개 이상 찍은 뒤 [완료]를 누르세요.\n"
            "꼭짓점 드래그로 위치를 수정하고, 우클릭하면 마지막 점을 취소합니다."
        )
        self.edit_label.setWordWrap(True)

        level_caption = QLabel("구역 등급")
        level_caption.setObjectName("title")
        self.level_hint = QLabel("새 구역에 적용 · 목록에서 고른 구역의 등급도 여기서 바꿉니다")
        self.level_hint.setObjectName("hint")
        self.level_hint.setWordWrap(True)

        self.level_combo = QComboBox()
        for level in ZONE_LEVELS:
            self.level_combo.addItem(f"{level.rank}  {level.label}", level.id)
        self.set_combo_level(DEFAULT_LEVEL_ID)

        title = QLabel("위험구역")
        hint = QLabel("Delete로 선택 구역 삭제 · Esc 또는 빈 곳 클릭으로 선택 해제")
        hint.setWordWrap(True)

        self.list = ZoneList()

        for widget in (
            self.zone_button,
            self.apply_button,
            self.cancel_button,
            self.list,
            self.level_combo,
        ):
            widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.zone_button.setEnabled(False)
        self.zone_button.setObjectName("primaryAction")
        self.apply_button.setObjectName("apply")
        self.cancel_button.setObjectName("cancel")
        self.edit_label.setObjectName("editLabel")
        self.level_combo.setObjectName("levelCombo")
        title.setObjectName("title")
        hint.setObjectName("hint")

        self.setStyleSheet(load_qss("zone_panel"))

        edit_buttons = QHBoxLayout()
        edit_buttons.setSpacing(8)
        edit_buttons.addWidget(self.apply_button)
        edit_buttons.addWidget(self.cancel_button)

        layout = QVBoxLayout()
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        layout.addWidget(self.zone_button)
        layout.addWidget(self.edit_label)
        layout.addLayout(edit_buttons)
        layout.addWidget(level_caption)
        layout.addWidget(self.level_combo)
        layout.addWidget(self.level_hint)
        layout.addSpacing(4)
        layout.addWidget(title)
        layout.addWidget(self.list, 1)
        layout.addWidget(hint)
        self.setLayout(layout)

        self.list.itemSelectionChanged.connect(self.on_selection_changed)
        self.level_combo.currentIndexChanged.connect(self.on_level_changed)
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self).activated.connect(self.on_delete_key)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self).activated.connect(self.list.clearSelection)

        self.set_edit_mode(False)

    def set_edit_mode(self, editing: bool) -> None:
        self.zone_button.setVisible(not editing)
        self.edit_label.setVisible(editing)
        self.apply_button.setVisible(editing)
        self.cancel_button.setVisible(editing)
        self.list.setEnabled(not editing)

    def current_level_id(self) -> str:
        data = self.level_combo.currentData()
        return normalize_level_id(data if data is not None else DEFAULT_LEVEL_ID)

    def set_combo_level(self, level_id: str | int | None) -> None:
        target = normalize_level_id(level_id)
        index = self.level_combo.findData(target)
        if index < 0:
            index = self.level_combo.findData(DEFAULT_LEVEL_ID)
        self._syncing_level = True
        try:
            self.level_combo.setCurrentIndex(max(0, index))
        finally:
            self._syncing_level = False

    def on_selection_changed(self) -> None:
        index = self.selected_index()
        if index >= 0:
            self.set_combo_level(self.zones[index].level)
        self.selection_changed.emit(index)

    def on_level_changed(self) -> None:
        if self._syncing_level:
            return
        index = self.selected_index()
        if index < 0 or not self.list.isEnabled():
            return
        level_id = self.current_level_id()
        if self.zones[index].level == level_id:
            return
        self.zones[index].level = level_id
        self.refresh_list_item(index)
        self.zones_changed.emit(self.zones)

    def refresh_list_item(self, index: int) -> None:
        item = self.list.item(index)
        if item is None:
            return
        zone = self.zones[index]
        item.setText(format_zone_item(zone.name, zone.level))

    def rebuild_list(self) -> None:
        self.list.clear()
        for zone in self.zones:
            self.list.addItem(format_zone_item(zone.name, zone.level))

    def add_zone(self, points: list[tuple[int, int]]) -> str:
        name = f"구역 {self.next_number}"
        self.next_number += 1
        zone = Zone(name=name, points=list(points), level=self.current_level_id())
        self.zones.append(zone)
        self.list.addItem(format_zone_item(zone.name, zone.level))
        self.zones_changed.emit(self.zones)
        return name

    def set_zones(self, zones: list[Zone]) -> None:
        self.zones = [
            zone if isinstance(zone, Zone) else Zone.from_dict(zone)  # type: ignore[arg-type]
            for zone in zones
        ]
        self.next_number = next_zone_number(self.zones)
        self.rebuild_list()
        self.zones_changed.emit(self.zones)
        self.selection_changed.emit(self.selected_index())

    def remove_zone(self, index: int) -> None:
        if not 0 <= index < len(self.zones):
            return
        del self.zones[index]
        self.list.takeItem(index)
        self.list.clearSelection()
        self.zones_changed.emit(self.zones)
        self.selection_changed.emit(self.selected_index())

    def selected_index(self) -> int:
        rows = [index.row() for index in self.list.selectedIndexes()]
        return rows[0] if rows else -1

    def on_delete_key(self) -> None:
        if self.list.isEnabled() and self.selected_index() >= 0:
            self.remove_zone(self.selected_index())
