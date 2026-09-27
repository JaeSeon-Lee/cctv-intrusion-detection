# 파이썬이 기본으로 제공하는 모듈은 import로 불러오기
import logging
import sys

from PySide6.QtGui import QFont, QFontDatabase

# PySide6.QtWidgets 모듈에서 QApplication 클래스 불러오기
from PySide6.QtWidgets import QApplication

from cctv_intrusion.ui import MainWindow
from cctv_intrusion.ui.styles import load_qss

# macOS / Linux 에서 쓸 수 있는 한글 가독성 좋은 폰트 후보
_FONT_CANDIDATES = (
    "Apple SD Gothic Neo",
    "Noto Sans CJK KR",
    "Noto Sans KR",
    "Malgun Gothic",
    "NanumGothic",
)


def _app_font() -> QFont:
    available = set(QFontDatabase.families())
    for name in _FONT_CANDIDATES:
        if name in available:
            return QFont(name, 10)
    return QFont(QFont().defaultFamily(), 10)


def main():
    # logger.info 이상을 터미널에 출력 (예: 사람 탐지 모델 로딩 완료, 사용 장치)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    app = QApplication(sys.argv)
    app.setApplicationName("침입 감지 모니터")
    app.setFont(_app_font())
    # 앱 전체 공통 스타일 (위젯별 스타일은 각 위젯에서 적용)
    app.setStyleSheet(load_qss("app"))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
