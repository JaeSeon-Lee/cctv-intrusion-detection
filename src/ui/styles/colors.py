# QPainter 등 코드에서 직접 그릴 때 쓰는 색 (QSS로 지정할 수 없는 색)
from PySide6.QtGui import QColor

# 위험구역 표시 색
ZONE = QColor(231, 76, 60)            # 빨강: 일반 구역
ZONE_SELECTED = QColor(241, 196, 15)  # 노랑: 리스트에서 선택한 구역
ZONE_DRAWING = QColor(52, 152, 219)   # 파랑: 편집 중인(아직 완료 안 한) 꼭짓점
ZONE_NAME_TEXT = QColor(0, 0, 0)      # 구역 이름 글자색
