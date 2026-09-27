"""침입·경보 판정에 쓰는 상수와 스펙 (구현 전 계약).

발 위치 기준, 등급별 체류 시간, 시스템 상태, 사건 클립/CSV 정책을 한곳에 둔다.
"""

from __future__ import annotations

from enum import StrEnum

from cctv_intrusion.zone.levels import ZONE_LEVELS, alert_seconds_for

# 사람 박스 하단 중앙(발 위치) → 침입 후보 점
# point = ((x1 + x2) / 2, y2)


class MonitorState(StrEnum):
    """감지 시스템 상태."""

    IDLE = "idle"  # 대기: 위험구역 미설정
    ARMED = "armed"  # 감지: 위험구역이 설정된 상태
    ALARM = "alarm"  # 경보: 체류 시간 충족으로 경보 울림
    CLEARED = "cleared"  # 해제: 경보가 풀린 상태


# 등급 id → 경보까지 필요한 구역 내 체류 시간(초)
ALERT_HOLD_SECONDS: dict[str, float] = {level.id: level.alert_seconds for level in ZONE_LEVELS}

# 사건 영상: 침입(경보) 시점 기준 이전/이후
EVENT_CLIP_BEFORE_SEC = 3.0
EVENT_CLIP_AFTER_SEC = 5.0

# 사건 CSV에 남길 필드(구현 시 컬럼명)
EVENT_CSV_FIELDS = ("timestamp", "duration_sec", "zone_name", "zone_level")


def foot_point(x1: float, y1: float, x2: float, y2: float) -> tuple[float, float]:
    """YOLO 박스 → 발 위치(하단 중앙). y1은 시그니처 대칭용으로 받되 사용하지 않는다."""
    del y1
    return (x1 + x2) / 2.0, float(y2)


__all__ = [
    "ALERT_HOLD_SECONDS",
    "EVENT_CLIP_AFTER_SEC",
    "EVENT_CLIP_BEFORE_SEC",
    "EVENT_CSV_FIELDS",
    "MonitorState",
    "alert_seconds_for",
    "foot_point",
]
