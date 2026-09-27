"""위험구역 경보 등급 정의.

숫자가 클수록 민감(경보까지 필요한 체류 시간이 짧다).
  1 주의(3초) → 2 위험(2초) → 3 감지(1초)
"""

from __future__ import annotations

from dataclasses import dataclass

# 예전 파일 / 팀원 코드에서 쓰이던 문자열 → 현재 id
_LEGACY_ALIASES = {
    "주의": "caution",
    "경고": "danger",
    "위험": "danger",
    "감지": "detect",
    "금지": "detect",
    "긴급": "detect",
    "격리": "detect",
    "금지구역": "detect",
    "주의구역": "caution",
    "warning": "danger",
    "restricted": "detect",
    "critical": "detect",
}


@dataclass(frozen=True, slots=True)
class ZoneLevel:
    id: str
    rank: int
    label: str
    alert_seconds: float  # 이 시간 이상 구역에 있으면 경보


ZONE_LEVELS: tuple[ZoneLevel, ...] = (
    ZoneLevel("caution", 1, "주의", alert_seconds=3.0),
    ZoneLevel("danger", 2, "위험", alert_seconds=2.0),
    ZoneLevel("detect", 3, "감지", alert_seconds=1.0),
)

DEFAULT_LEVEL_ID = "danger"
_BY_ID = {level.id: level for level in ZONE_LEVELS}
_BY_RANK = {level.rank: level for level in ZONE_LEVELS}
_MAX_RANK = max(_BY_RANK)


def get_level(level_id: str | int | None) -> ZoneLevel:
    """id·숫자·한글 별칭을 ZoneLevel로 정규화. 모르면 기본(위험)."""
    if level_id is None:
        return _BY_ID[DEFAULT_LEVEL_ID]
    if isinstance(level_id, int) or str(level_id).strip().isdigit():
        rank = int(level_id)
        if rank in _BY_RANK:
            return _BY_RANK[rank]
        if rank > _MAX_RANK:
            return _BY_RANK[_MAX_RANK]
        return _BY_ID[DEFAULT_LEVEL_ID]

    key = str(level_id).strip().lower()
    if key in _BY_ID:
        return _BY_ID[key]
    legacy = _LEGACY_ALIASES.get(str(level_id).strip()) or _LEGACY_ALIASES.get(key)
    if legacy and legacy in _BY_ID:
        return _BY_ID[legacy]
    return _BY_ID[DEFAULT_LEVEL_ID]


def normalize_level_id(level_id: str | int | None) -> str:
    return get_level(level_id).id


def alert_seconds_for(level_id: str | int | None) -> float:
    """해당 등급이 경보로 바뀌는 데 필요한 구역 내 체류 시간(초)."""
    return get_level(level_id).alert_seconds


def format_level(level_id: str | int | None) -> str:
    """목록·라벨용: '2 위험'."""
    level = get_level(level_id)
    return f"{level.rank} {level.label}"


def format_zone_item(name: str, level_id: str | int | None) -> str:
    """리스트 한 줄: '구역 1  ·  Lv.2 위험'."""
    level = get_level(level_id)
    return f"{name}  ·  Lv.{level.rank} {level.label}"
