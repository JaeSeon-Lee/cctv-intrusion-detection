from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PySide6.QtCore import Qt

class VideoWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.label = QLabel("동영상을 선택하세요.")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.label.setStyleSheet("""
            QLabel {
                font-size: 24px;
            }
        """)

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        self.setLayout(layout)

    def set_video(self, path):
        self.label.setText(path)