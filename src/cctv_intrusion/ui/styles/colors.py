# QPainter 등 코드에서 직접 그릴 때 쓰는 색 (QSS로 지정할 수 없는 색)
from PySide6.QtGui import QColor

from cctv_intrusion.zone.levels import get_level

_ZONE_LEVEL_COLORS = {
    "caution": QColor(234, 179, 8),
    "warning": QColor(245, 158, 11),
    "danger": QColor(220, 38, 38),
    "restricted": QColor(185, 28, 28),
    "critical": QColor(127, 29, 29),
}

ZONE_SELECTED = QColor(251, 191, 36)
ZONE_DRAWING = QColor(14, 165, 233)
ZONE_NAME_TEXT = QColor(255, 255, 255)
PERSON_BOX = QColor(16, 185, 129)


def zone_color(level_id: str | int | None) -> QColor:
    level = get_level(level_id)
    return QColor(_ZONE_LEVEL_COLORS.get(level.id, _ZONE_LEVEL_COLORS["danger"]))
