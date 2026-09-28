from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import QComboBox, QLabel, QPushButton, QVBoxLayout, QWidget

from cctv_intrusion.ui.styles import load_qss

# 목록에 보여줄 카메라 번호 (OpenCV 장치 번호. 노트북 내장 카메라는 보통 0번)
CAMERA_COUNT = 4


class CameraPanel(QWidget):
    """실시간 영상 탭의 왼쪽 패널: 카메라 번호 선택 + 연결/연결 해제 버튼.

    Signals:
      connect_requested(int) : [연결]을 누름 (카메라 번호)
      disconnect_requested() : [연결 해제]를 누름
    """

    connect_requested = Signal(int)
    disconnect_requested = Signal()

    def __init__(self) -> None:
        super().__init__()

        self.connected = False

        title = QLabel("카메라")
        title.setObjectName("panelTitle")
        subtitle = QLabel("연결할 카메라를 선택하세요")
        subtitle.setObjectName("panelSubtitle")

        self.camera_combo = QComboBox()
        self.camera_combo.setObjectName("cameraCombo")
        for index in range(CAMERA_COUNT):
            self.camera_combo.addItem(f"카메라 {index}", index)
        self.connect_button = QPushButton("연결")
        self.connect_button.setObjectName("primaryAction")

        hint = QLabel(
            "침입이 감지되면 경보 3초 전부터 해제 5초 후까지\n"
            "output 폴더에 live_날짜_시각.mp4 / .csv 로 저장합니다."
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)

        for widget in (self.camera_combo, self.connect_button):
            widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.setStyleSheet(load_qss("camera_panel"))

        body = QVBoxLayout()
        body.setContentsMargins(16, 0, 16, 16)
        body.setSpacing(10)
        body.addWidget(self.camera_combo)
        body.addWidget(self.connect_button)
        body.addWidget(hint)
        body.addStretch(1)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(body, 1)
        self.setLayout(layout)

        self.connect_button.clicked.connect(self.on_button_clicked)

    @Slot()
    def on_button_clicked(self) -> None:
        if self.connected:
            self.disconnect_requested.emit()
        else:
            self.connect_requested.emit(self.camera_combo.currentData())

    def set_connected(self, connected: bool) -> None:
        self.connected = connected
        self.connect_button.setText("연결 해제" if connected else "연결")
        self.camera_combo.setEnabled(not connected)
