from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget


class ToolBar(QWidget):
    """창 상단 버튼 모음 (스트림 연결)

    위험지역 설정 버튼은 화면 우측 위험구역 패널(ZonePanel)에 있다.
    버튼 클릭 시 동작은 MainWindow에서 clicked 신호에 연결해서 처리한다.
    """

    def __init__(self):
        super().__init__()

        self.stream_button = QPushButton("스트림 연결")
        self.stream_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        layout = QHBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self.stream_button)
        layout.addStretch()  # 버튼들을 왼쪽으로 붙이고 남는 공간은 비워둠
        self.setLayout(layout)

    def set_edit_mode(self, editing):
        # 편집 중에는 다른 스트림으로 바꾸지 못하게 막음
        self.stream_button.setEnabled(not editing)
