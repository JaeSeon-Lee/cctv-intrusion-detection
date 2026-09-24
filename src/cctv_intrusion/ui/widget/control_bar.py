from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSlider, QWidget

from cctv_intrusion.ui.styles import load_qss


class ControlBar(QWidget):
    """재생 컨트롤 (5초 뒤로 / 재생·일시정지 / 5초 앞으로 / 탐색 슬라이더 / 시간)

    버튼과 슬라이더는 화면만 담당하고,
    실제 동작은 VideoWidget에서 clicked, valueChanged 등의 신호에 연결해서 처리한다.
    """

    def __init__(self):
        super().__init__()

        self.prev_button = QPushButton("◀ 5초")
        self.play_button = QPushButton("재생")
        self.next_button = QPushButton("5초 ▶")

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)

        self.time_label = QLabel("00:00 / 00:00")

        # NoFocus: 클릭해도 키보드 포커스를 가져가지 않게 한다.
        # 포커스가 버튼에 있으면 Space 키가 버튼 클릭으로 처리되어 단축키와 겹칠 수 있기 때문.
        for widget in (self.prev_button, self.play_button, self.next_button, self.slider):
            widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.setStyleSheet(load_qss("control_bar"))

        layout = QHBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self.prev_button)
        layout.addWidget(self.play_button)
        layout.addWidget(self.next_button)
        layout.addWidget(self.slider, 1)  # 1: 남는 가로 공간을 슬라이더가 차지
        layout.addWidget(self.time_label)
        self.setLayout(layout)

    def set_playing(self, playing):
        self.play_button.setText("일시정지" if playing else "재생")

    def set_time(self, current_sec, total_sec):
        self.time_label.setText(f"{format_time(current_sec)} / {format_time(total_sec)}")

    def set_live_time(self, elapsed_sec):
        # 실시간 스트림은 전체 길이가 없으므로 경과 시간만 표시
        self.time_label.setText(f"LIVE  {format_time(elapsed_sec)}")


def format_time(seconds):
    # 초 → "mm:ss" (1시간 이상이면 "h:mm:ss")
    minutes, sec = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{sec:02d}"
    return f"{minutes:02d}:{sec:02d}"
