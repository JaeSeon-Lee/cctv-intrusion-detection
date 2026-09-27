# QPainter 등 코드에서 직접 그릴 때 쓰는 색 (QSS로 지정할 수 없는 색)
from PySide6.QtGui import QColor

from cctv_intrusion.zone.levels import get_level

_ZONE_LEVEL_COLORS = {
    "caution": QColor(234, 179, 8),
    "danger": QColor(220, 38, 38),
    "detect": QColor(185, 28, 28),
    # 레거시 id (json에 남아 있을 수 있음)
    "warning": QColor(245, 158, 11),
    "restricted": QColor(185, 28, 28),
    "critical": QColor(127, 29, 29),
}

ZONE_SELECTED = QColor(251, 191, 36)
ZONE_DRAWING = QColor(14, 165, 233)
ZONE_NAME_TEXT = QColor(255, 255, 255)
PERSON_BOX = QColor(16, 185, 129)

# 영상 우측 상단 경보 상태 배지
MONITOR_STATE_COLORS = {
    "idle": QColor(100, 116, 139),  # 대기
    "armed": QColor(15, 118, 110),  # 감지
    "alarm": QColor(220, 38, 38),  # 경보
    "cleared": QColor(217, 119, 6),  # 해제
}
MONITOR_STATE_TEXT = QColor(255, 255, 255)


def zone_color(level_id: str | int | None) -> QColor:
    level = get_level(level_id)
    return QColor(_ZONE_LEVEL_COLORS.get(level.id, _ZONE_LEVEL_COLORS["danger"]))
