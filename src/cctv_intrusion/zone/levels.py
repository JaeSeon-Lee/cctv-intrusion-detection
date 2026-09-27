"""위험구역 등급 정의.

숫자가 클수록 더 심각하다.
  1 주의 → 2 경고 → 3 위험 → 4 금지 → 5 긴급
"""

from __future__ import annotations

from dataclasses import dataclass

# 예전 파일 / 팀원 코드에서 쓰이던 문자열 → 현재 id
_LEGACY_ALIASES = {
    "주의": "caution",
    "경고": "warning",
    "위험": "danger",
    "금지": "restricted",
    "긴급": "critical",
    "격리": "critical",
    "금지구역": "restricted",
    "주의구역": "caution",
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


def get_level(level_id: str | int | None) -> ZoneLevel:
    """id·숫자·한글 별칭을 ZoneLevel로 정규화. 모르면 기본(위험)."""
    if level_id is None:
        return _BY_ID[DEFAULT_LEVEL_ID]
    if isinstance(level_id, int):
        return _BY_RANK.get(level_id, _BY_ID[DEFAULT_LEVEL_ID])

    key = str(level_id).strip().lower()
    if key.isdigit():
        return _BY_RANK.get(int(key), _BY_ID[DEFAULT_LEVEL_ID])
    if key in _BY_ID:
        return _BY_ID[key]
    legacy = _LEGACY_ALIASES.get(str(level_id).strip()) or _LEGACY_ALIASES.get(key)
    if legacy:
        return _BY_ID[legacy]
    return _BY_ID[DEFAULT_LEVEL_ID]


def normalize_level_id(level_id: str | int | None) -> str:
    return get_level(level_id).id


def format_level(level_id: str | int | None) -> str:
    """목록·라벨용: '3 위험'."""
    level = get_level(level_id)
    return f"{level.rank} {level.label}"


def format_zone_item(name: str, level_id: str | int | None) -> str:
    """리스트 한 줄: '구역 1  ·  Lv.3 위험'."""
    level = get_level(level_id)
    return f"{name}  ·  Lv.{level.rank} {level.label}"
