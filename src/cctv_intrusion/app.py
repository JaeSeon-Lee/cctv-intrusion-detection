# 파이썬이 기본으로 제공하는 모듈은 import로 불러오기
import logging
import sys

from PySide6.QtGui import QFont

# PySide6.QtWidgets 모듈에서 QApplication 클래스 불러오기
from PySide6.QtWidgets import QApplication

from cctv_intrusion.ui import MainWindow
from cctv_intrusion.ui.styles import load_qss


def main():
    # logger.info 이상을 터미널에 출력 (예: 사람 탐지 모델 로딩 완료, 사용 장치)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    app = QApplication(sys.argv)
    app.setFont(QFont("Noto Sans CJK KR", 10))
    # 앱 전체 공통 스타일 (위젯별 스타일은 각 위젯에서 적용)
    app.setStyleSheet(load_qss("app"))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
