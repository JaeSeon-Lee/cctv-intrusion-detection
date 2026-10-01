# QPainter 등 코드에서 직접 그릴 때 쓰는 색 (QSS로 지정할 수 없는 색)
from PySide6.QtGui import QColor

from cctv_intrusion.zone.levels import get_level

_ZONE_LEVEL_COLORS = {
    # 1 감지 → 2 주의 → 3 위험 (등급↑ = 색↑)
    "detect": QColor(234, 179, 8),
    "caution": QColor(245, 158, 11),
    "danger": QColor(220, 38, 38),
    # 레거시 id (json에 남아 있을 수 있음)
    "warning": QColor(245, 158, 11),
    "restricted": QColor(234, 179, 8),
    "critical": QColor(185, 28, 28),
}

ZONE_SELECTED = QColor(251, 191, 36)
ZONE_DRAWING = QColor(14, 165, 233)
ZONE_NAME_TEXT = QColor(255, 255, 255)
PERSON_BOX = QColor(16, 185, 129)
ALARM_FRAME = QColor(239, 68, 68)  # 경보 테두리·덮개 (조금 더 밝은 빨강)
ALARM_BADGE = QColor(185, 28, 28)  # 경보 상태 배지

# 영상 우측 상단 경보 상태 배지
MONITOR_STATE_COLORS = {
    "idle": QColor(100, 116, 139),  # 대기
    "armed": QColor(15, 118, 110),  # 감지
    "alarm": QColor(239, 68, 68),  # 경보
    "cleared": QColor(217, 119, 6),  # 해제
}
MONITOR_STATE_TEXT = QColor(255, 255, 255)


def zone_color(level_id: str | int | None) -> QColor:
    level = get_level(level_id)
    return QColor(_ZONE_LEVEL_COLORS.get(level.id, _ZONE_LEVEL_COLORS["danger"]))


# 대시보드 차트 (어두운 배경 기준)
CHART_INTRUSION = QColor(239, 68, 68)  # 침입 구간·막대
CHART_INTRUSION_HOVER = QColor(252, 165, 165)
CHART_TRACK = QColor(30, 41, 59)  # 타임라인 바탕 (침입 없는 구간)
CHART_GRID = QColor(30, 41, 59)
CHART_AXIS_TEXT = QColor(148, 163, 184)
CHART_LABEL_BG = QColor(18, 25, 32)  # 섹션 바탕(#121920) — 막대 위 라벨 뒤
