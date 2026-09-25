# 파이썬이 기본으로 제공하는 모듈은 import로 불러오기
import sys

from PySide6.QtGui import QFont

# PySide6.QtWidgets 모듈에서 QApplication 클래스 불러오기
from PySide6.QtWidgets import QApplication

from cctv_intrusion.ui import MainWindow
from cctv_intrusion.ui.styles import load_qss


def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Noto Sans CJK KR", 10))
    # 앱 전체 공통 스타일 (위젯별 스타일은 각 위젯에서 적용)
    app.setStyleSheet(load_qss("app"))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
