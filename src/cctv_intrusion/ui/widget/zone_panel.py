from typing import override

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QMouseEvent, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
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
        self._drawing = False
        self._syncing_edit = False

        self.zone_button = QPushButton("위험지역 설정")
        self.apply_button = QPushButton("완료")
        self.cancel_button = QPushButton("취소")
        self.edit_label = QLabel(
            "영상을 클릭해 꼭짓점을 3개 이상 찍은 뒤 [완료]를 누르세요.\n"
            "꼭짓점 드래그로 위치를 수정하고, 우클릭하면 마지막 점을 취소합니다."
        )
        self.edit_label.setWordWrap(True)

        default_caption = QLabel("새 구역 기본 등급")
        default_caption.setObjectName("title")
        self.default_level_combo = QComboBox()
        self._fill_level_combo(self.default_level_combo)
        self.set_combo_level(self.default_level_combo, DEFAULT_LEVEL_ID)

        title = QLabel("위험구역")
        self.list = ZoneList()

        edit_caption = QLabel("선택 구역 수정")
        edit_caption.setObjectName("title")
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("구역 이름")
        self.name_edit.setClearButtonEnabled(True)

        self.edit_level_combo = QComboBox()
        self._fill_level_combo(self.edit_level_combo)

        self.apply_edit_button = QPushButton("수정 적용")
        self.apply_edit_button.setObjectName("apply")

        self.edit_hint = QLabel("목록에서 구역을 선택한 뒤 이름·등급을 바꾸고 [수정 적용]을 누르세요")
        self.edit_hint.setObjectName("hint")
        self.edit_hint.setWordWrap(True)

        hint = QLabel("Delete로 선택 구역 삭제 · Esc 또는 빈 곳 클릭으로 선택 해제")
        hint.setWordWrap(True)
        hint.setObjectName("hint")

        for widget in (
            self.zone_button,
            self.apply_button,
            self.cancel_button,
            self.list,
            self.default_level_combo,
            self.edit_level_combo,
            self.apply_edit_button,
        ):
            widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.zone_button.setEnabled(False)
        self.zone_button.setObjectName("primaryAction")
        self.apply_button.setObjectName("apply")
        self.cancel_button.setObjectName("cancel")
        self.edit_label.setObjectName("editLabel")
        self.default_level_combo.setObjectName("levelCombo")
        self.edit_level_combo.setObjectName("levelCombo")
        self.name_edit.setObjectName("nameEdit")
        default_caption.setObjectName("title")
        title.setObjectName("title")

        self.setStyleSheet(load_qss("zone_panel"))

        draw_buttons = QHBoxLayout()
        draw_buttons.setSpacing(8)
        draw_buttons.addWidget(self.apply_button)
        draw_buttons.addWidget(self.cancel_button)

        layout = QVBoxLayout()
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        layout.addWidget(self.zone_button)
        layout.addWidget(self.edit_label)
        layout.addLayout(draw_buttons)
        layout.addWidget(default_caption)
        layout.addWidget(self.default_level_combo)
        layout.addSpacing(4)
        layout.addWidget(title)
        layout.addWidget(self.list, 1)
        layout.addWidget(edit_caption)
        layout.addWidget(self.name_edit)
        layout.addWidget(self.edit_level_combo)
        layout.addWidget(self.apply_edit_button)
        layout.addWidget(self.edit_hint)
        layout.addWidget(hint)
        self.setLayout(layout)

        self.list.itemSelectionChanged.connect(self.on_selection_changed)
        self.apply_edit_button.clicked.connect(self.apply_selected_edit)
        self.name_edit.returnPressed.connect(self.apply_selected_edit)
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self).activated.connect(self.on_delete_key)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self).activated.connect(self.list.clearSelection)

        self.set_edit_mode(False)
        self.update_edit_form()

    @staticmethod
    def _fill_level_combo(combo: QComboBox) -> None:
        for level in ZONE_LEVELS:
            combo.addItem(f"{level.rank}  {level.label}", level.id)

    def set_edit_mode(self, editing: bool) -> None:
        """다각형 그리기 모드 on/off (영상 위 꼭짓점 편집)."""
        self._drawing = editing
        self.zone_button.setVisible(not editing)
        self.edit_label.setVisible(editing)
        self.apply_button.setVisible(editing)
        self.cancel_button.setVisible(editing)
        self.list.setEnabled(not editing)
        self.default_level_combo.setEnabled(not editing)
        self.update_edit_form()

    def current_default_level_id(self) -> str:
        data = self.default_level_combo.currentData()
        return normalize_level_id(data if data is not None else DEFAULT_LEVEL_ID)

    def set_combo_level(self, combo: QComboBox, level_id: str | int | None) -> None:
        target = normalize_level_id(level_id)
        index = combo.findData(target)
        if index < 0:
            index = combo.findData(DEFAULT_LEVEL_ID)
        self._syncing_edit = True
        try:
            combo.setCurrentIndex(max(0, index))
        finally:
            self._syncing_edit = False

    def on_selection_changed(self) -> None:
        self.update_edit_form()
        self.selection_changed.emit(self.selected_index())

    def update_edit_form(self) -> None:
        index = self.selected_index()
        can_edit = (not self._drawing) and index >= 0 and self.list.isEnabled()
        self.name_edit.setEnabled(can_edit)
        self.edit_level_combo.setEnabled(can_edit)
        self.apply_edit_button.setEnabled(can_edit)

        if not can_edit:
            if index < 0:
                self._syncing_edit = True
                try:
                    self.name_edit.clear()
                    self.set_combo_level(self.edit_level_combo, DEFAULT_LEVEL_ID)
                finally:
                    self._syncing_edit = False
            return

        zone = self.zones[index]
        self._syncing_edit = True
        try:
            self.name_edit.setText(zone.name)
            self.set_combo_level(self.edit_level_combo, zone.level)
        finally:
            self._syncing_edit = False

    def apply_selected_edit(self) -> None:
        if self._syncing_edit or self._drawing:
            return
        index = self.selected_index()
        if index < 0 or not self.list.isEnabled():
            return

        name = self.name_edit.text().strip()
        if not name:
            self.name_edit.setFocus()
            self.name_edit.selectAll()
            return

        level_id = normalize_level_id(self.edit_level_combo.currentData())
        zone = self.zones[index]
        if zone.name == name and zone.level == level_id:
            return

        zone.name = name
        zone.level = level_id
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
        zone = Zone(name=name, points=list(points), level=self.current_default_level_id())
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
        self.update_edit_form()

    def remove_zone(self, index: int) -> None:
        if not 0 <= index < len(self.zones):
            return
        del self.zones[index]
        self.list.takeItem(index)
        self.list.clearSelection()
        self.zones_changed.emit(self.zones)
        self.selection_changed.emit(self.selected_index())
        self.update_edit_form()

    def selected_index(self) -> int:
        rows = [index.row() for index in self.list.selectedIndexes()]
        return rows[0] if rows else -1

    def on_delete_key(self) -> None:
        # 이름 입력 중이면 글자 삭제가 우선이므로 포커스가 리스트/패널에 있을 때만 구역 삭제
        if self.name_edit.hasFocus():
            return
        if self.list.isEnabled() and self.selected_index() >= 0:
            self.remove_zone(self.selected_index())
