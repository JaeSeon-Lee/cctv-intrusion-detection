from typing import override

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QMouseEvent, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QPushButton, QVBoxLayout, QWidget

from cctv_intrusion.ui.styles import load_qss
from cctv_intrusion.zone import next_zone_number


class ZoneList(QListWidget):
    """선택을 풀 수 있는 위험구역 리스트

    QListWidget은 한 번 선택하면 마우스로 선택을 풀 방법이 없어서,
    빈 공간을 누르거나 이미 선택된 항목을 다시 누르면 선택을 해제하도록 덮어쓴다.
    """

    @override
    def mousePressEvent(self, event: QMouseEvent) -> None:
        item = self.itemAt(event.position().toPoint())
        if item is None or item.isSelected():
            self.clearSelection()
            return
        super().mousePressEvent(event)


class ZonePanel(QWidget):
    """화면 우측 위험구역 패널 ([위험지역 설정] / [완료] / [취소] 버튼 + 위험구역 리스트)

    위험구역 데이터는 self.zones 에 보관한다.
      [{"name": "구역 1", "points": [(x, y), ...]}, ...]   # points: 원본 프레임 픽셀 좌표

    버튼 클릭 시 동작은 MainWindow에서 clicked 신호에 연결해서 처리한다.
    """

    # 구역이 추가/삭제될 때마다: 전체 구역 목록 (팀원 탐지 모듈에서 연결해서 사용)
    zones_changed = Signal(list)
    # 리스트에서 선택한 구역이 바뀔 때마다: 선택한 구역 번호 (선택 없으면 -1)
    selection_changed = Signal(int)

    def __init__(self):
        super().__init__()

        self.zones = []
        self.next_number = 1  # 다음에 만들 구역 이름에 붙일 번호 (삭제해도 번호를 재사용하지 않아 이름이 겹치지 않음)

        self.zone_button = QPushButton("위험지역 설정")
        self.apply_button = QPushButton("완료")
        self.cancel_button = QPushButton("취소")
        self.edit_label = QLabel(
            "영상을 클릭해 꼭짓점을 3개 이상 찍고 [완료]를 누르세요.\n꼭짓점 드래그: 위치 수정\n우클릭: 마지막 점 취소"
        )
        self.edit_label.setWordWrap(True)  # 패널 폭이 좁으므로 자동 줄바꿈

        title = QLabel("위험구역 목록")
        hint = QLabel("Del: 선택한 구역 삭제\nEsc / 빈 곳 클릭: 선택 해제")

        self.list = ZoneList()

        # 키보드 포커스를 가져가지 않게 해서 Space, ←/→ 같은 재생 단축키와 겹치지 않게 한다.
        # (리스트는 포커스가 없어도 마우스 클릭으로 선택할 수 있다)
        for widget in (self.zone_button, self.apply_button, self.cancel_button, self.list):
            widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # 영상이 열리기 전에는 위험지역 설정 불가
        self.zone_button.setEnabled(False)

        # objectName을 지정하면 스타일시트에서 #이름 으로 특정 위젯만 꾸밀 수 있다
        self.apply_button.setObjectName("apply")
        self.edit_label.setObjectName("editLabel")
        title.setObjectName("title")
        hint.setObjectName("hint")

        self.setStyleSheet(load_qss("zone_panel"))

        # [완료] [취소] 는 가로로 나란히
        edit_buttons = QHBoxLayout()
        edit_buttons.addWidget(self.apply_button)
        edit_buttons.addWidget(self.cancel_button)

        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self.zone_button)
        layout.addWidget(self.edit_label)
        layout.addLayout(edit_buttons)
        layout.addSpacing(8)
        layout.addWidget(title)
        layout.addWidget(self.list, 1)  # 1: 남는 세로 공간을 리스트가 차지
        layout.addWidget(hint)
        self.setLayout(layout)

        # itemSelectionChanged: 리스트에서 선택한 항목이 바뀔 때마다 발생
        self.list.itemSelectionChanged.connect(
            lambda: self.selection_changed.emit(self.selected_index())
        )

        # Del 키: 창 안 어디에 포커스가 있어도 동작
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self).activated.connect(self.on_delete_key)
        # Esc 키: 선택 해제
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self).activated.connect(self.list.clearSelection)

        self.set_edit_mode(False)

    def set_edit_mode(self, editing):
        # 편집 모드: [위험지역 설정] 대신 안내 문구와 [완료] / [취소] 표시
        self.zone_button.setVisible(not editing)
        self.edit_label.setVisible(editing)
        self.apply_button.setVisible(editing)
        self.cancel_button.setVisible(editing)
        # 편집 중에는 리스트 선택/삭제를 막음
        self.list.setEnabled(not editing)

    # ------------------------------------------------------------
    # 위험구역 추가 / 삭제
    # ------------------------------------------------------------
    def add_zone(self, points):
        # 새 구역을 "구역 N" 이름으로 추가하고, 붙인 이름을 돌려준다
        name = f"구역 {self.next_number}"
        self.next_number += 1

        self.zones.append({"name": name, "points": list(points)})
        self.list.addItem(name)
        self.zones_changed.emit(self.zones)
        return name

    def set_zones(self, zones: list[dict]) -> None:
        # 영상을 새로 열 때 그 영상의 구역 목록(파일에서 읽은 것)으로 통째로 바꾼다
        self.zones = [dict(zone) for zone in zones]
        self.next_number = next_zone_number(self.zones)
        self.list.clear()
        self.list.addItems([zone["name"] for zone in self.zones])
        self.zones_changed.emit(self.zones)
        self.selection_changed.emit(self.selected_index())

    def remove_zone(self, index):
        if not 0 <= index < len(self.zones):
            return
        del self.zones[index]
        # takeItem: 리스트에서 항목을 빼낸다 (리스트 순서 = self.zones 순서)
        self.list.takeItem(index)
        # 삭제 후 옆 항목이 자동으로 선택되지 않게 선택 해제 (Del 연타로 여러 개가 지워지는 것 방지)
        self.list.clearSelection()
        self.zones_changed.emit(self.zones)
        self.selection_changed.emit(self.selected_index())

    def selected_index(self):
        # 선택한 구역 번호 (선택 없으면 -1)
        rows = [index.row() for index in self.list.selectedIndexes()]
        return rows[0] if rows else -1

    def on_delete_key(self):
        # 편집 중이 아니고, 선택된 구역이 있을 때만 삭제
        if self.list.isEnabled() and self.selected_index() >= 0:
            self.remove_zone(self.selected_index())
