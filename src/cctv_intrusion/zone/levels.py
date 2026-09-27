"""위험구역 등급 정의.

숫자가 클수록 더 심각하다.
  1 주의 → 2 위험 → 3 금지
"""

from __future__ import annotations

from dataclasses import dataclass

# 예전 파일 / 팀원 코드에서 쓰이던 문자열 → 현재 id
_LEGACY_ALIASES = {
    "주의": "caution",
    "경고": "danger",
    "위험": "danger",
    "금지": "restricted",
    "긴급": "restricted",
    "격리": "restricted",
    "금지구역": "restricted",
    "주의구역": "caution",
    "warning": "danger",
    "critical": "restricted",
}


@dataclass(frozen=True, slots=True)
class ZoneLevel:
    id: str
    rank: int
    label: str


ZONE_LEVELS: tuple[ZoneLevel, ...] = (
    ZoneLevel("caution", 1, "주의"),
    ZoneLevel("danger", 2, "위험"),
    ZoneLevel("restricted", 3, "금지"),
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


def format_level(level_id: str | int | None) -> str:
    """목록·라벨용: '2 위험'."""
    level = get_level(level_id)
    return f"{level.label}"


def format_zone_item(name: str, level_id: str | int | None) -> str:
    """리스트 한 줄: '구역 1  ·  Lv.2 위험'."""
    level = get_level(level_id)
    return f"{name}  ·  Lv.{level.rank} {level.label}"
