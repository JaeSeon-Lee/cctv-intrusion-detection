from PySide6.QtWidgets import QWidget, QPushButton, QLabel, QHBoxLayout
from PySide6.QtCore import Qt

class ToolBar(QWidget):
    """창 상단 버튼 모음 (스트림 연결, 위험지역 설정 / 완료 / 취소)

    버튼 클릭 시 동작은 MainWindow에서 clicked 신호에 연결해서 처리한다.
    """

    def __init__(self):
        super().__init__()

        self.stream_button = QPushButton("스트림 연결")
        self.zone_button = QPushButton("위험지역 설정")
        self.apply_button = QPushButton("완료")
        self.cancel_button = QPushButton("취소")
        self.edit_label = QLabel("위험지역 편집 중 · 영상 위에 구역을 지정한 뒤 [완료]를 누르세요.")

        for button in (self.stream_button, self.zone_button, self.apply_button, self.cancel_button):
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # 영상이 열리기 전에는 위험지역 설정 불가
        self.zone_button.setEnabled(False)

        # objectName을 지정하면 스타일시트에서 #이름 으로 특정 위젯만 꾸밀 수 있다
        self.apply_button.setObjectName("apply")
        self.edit_label.setObjectName("editLabel")

        self.setStyleSheet("""
            QPushButton {
                font-size: 18px;
                padding: 6px 16px;
            }
            QPushButton#apply {
                background-color: #3a6ea5;
                color: white;
            }
            QLabel#editLabel {
                font-size: 18px;
                color: #c0392b;
            }
        """)

        layout = QHBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self.stream_button)
        layout.addWidget(self.zone_button)
        layout.addWidget(self.edit_label)
        layout.addWidget(self.apply_button)
        layout.addWidget(self.cancel_button)
        layout.addStretch()  # 버튼들을 왼쪽으로 붙이고 남는 공간은 비워둠
        self.setLayout(layout)

        self.set_edit_mode(False)

    def set_edit_mode(self, editing):
        # 편집 모드: [위험지역 설정] 대신 안내 문구와 [완료] / [취소] 표시
        self.zone_button.setVisible(not editing)
        self.edit_label.setVisible(editing)
        self.apply_button.setVisible(editing)
        self.cancel_button.setVisible(editing)
        # 편집 중에는 다른 스트림으로 바꾸지 못하게 막음
        self.stream_button.setEnabled(not editing)
