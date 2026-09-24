# 파이썬이 기본으로 제공하는 모듈은 import로 불러오기
import sys

# PySide6.QtWidgets 모듈에서 QApplication 클래스 불러오기
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
from ui import MainWindow

def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Noto Sans CJK KR", 10))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()