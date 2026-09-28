from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QWidget,
)

from cctv_intrusion.ui.styles import load_qss

SPEED_OPTIONS = (
    (0.5, "0.5×"),
    (1.0, "1×"),
    (1.5, "1.5×"),
    (2.0, "2×"),
    (4.0, "4×"),
)


class ControlBar(QWidget):
    """재생 컨트롤 (뒤로 / 재생 / 앞으로 / 배속 / 슬라이더 / 시간)"""

    def __init__(self):
        super().__init__()

        self.live = False

        self.prev_button = QPushButton("−5초")
        self.play_button = QPushButton("재생")
        self.next_button = QPushButton("+5초")

        self.speed_combo = QComboBox()
        self.speed_combo.setObjectName("speedCombo")
        for value, label in SPEED_OPTIONS:
            self.speed_combo.addItem(label, value)
        self.speed_combo.setCurrentIndex(1)  # 1×

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)

        self.time_label = QLabel("00:00 / 00:00")
        self.play_button.setObjectName("playButton")
        self.time_label.setObjectName("timeLabel")

        for widget in (
            self.prev_button,
            self.play_button,
            self.next_button,
            self.speed_combo,
            self.slider,
        ):
            widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.setStyleSheet(load_qss("control_bar"))

        layout = QHBoxLayout()
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        layout.addWidget(self.prev_button)
        layout.addWidget(self.play_button)
        layout.addWidget(self.next_button)
        layout.addWidget(self.speed_combo)
        layout.addWidget(self.slider, 1)
        layout.addStretch(0)
        layout.addWidget(self.time_label)
        self.setLayout(layout)

    def set_playing(self, playing):
        self.play_button.setText("일시정지" if playing else "재생")

    def set_live(self, live):
        self.live = live
        for widget in (self.prev_button, self.next_button, self.slider, self.speed_combo):
            widget.setVisible(not live)

    def set_time(self, current_sec, total_sec):
        if self.live:
            self.time_label.setText(f"● LIVE  {format_time(current_sec)}")
            return
        self.time_label.setText(f"{format_time(current_sec)} / {format_time(total_sec)}")

    def playback_speed(self) -> float:
        data = self.speed_combo.currentData()
        return float(data) if data is not None else 1.0


def format_time(seconds):
    # 초 → "mm:ss" (1시간 이상이면 "h:mm:ss")
    minutes, sec = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{sec:02d}"
    return f"{minutes:02d}:{sec:02d}"
