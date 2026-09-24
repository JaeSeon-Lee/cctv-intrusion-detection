from PySide6.QtWidgets import QWidget, QPushButton, QHBoxLayout
from PySide6.QtCore import Qt

class ToolBar(QWidget):
    """창 상단 버튼 모음 (스트림 연결 등)

    버튼 클릭 시 동작은 MainWindow에서 clicked 신호에 연결해서 처리한다.
    """

    def __init__(self):
        super().__init__()

        self.stream_button = QPushButton("스트림 연결")
        self.stream_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.setStyleSheet("""
            QPushButton {
                font-size: 18px;
                padding: 6px 16px;
            }
        """)

        layout = QHBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self.stream_button)
        layout.addStretch()  # 버튼들을 왼쪽으로 붙이고 남는 공간은 비워둠
        self.setLayout(layout)
