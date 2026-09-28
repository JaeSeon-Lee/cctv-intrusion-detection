# 위험구역 JSON 저장/로드.
#
# 화면(슬롯) 단위: data/cctv/screens/screen_1.json ...
# 또는 레거시: 동영상과 같은 stem 의 .json
#
# 파일 형식:
#   {
#     "video": "screen_1" | "a.mp4",
#     "zones": [{"name": "구역 1", "points": [[x, y], ...], "level": "danger"}, ...]
#   }
from __future__ import annotations

import json
import re
from pathlib import Path

from cctv_intrusion.paths import SCREENS_DIR

from .models import MIN_POINTS, Zone

ZONE_FILE_SUFFIX = ".json"
NAME_NUMBER = re.compile(r"(\d+)\s*$")


class ZoneFileError(Exception):
    """json 파일 내용이 위험구역 형식이 아닐 때"""


def zone_file_path(source: str | Path) -> Path:
    """동영상 경로 또는 screen stem → .json 경로."""
    return Path(source).with_suffix(ZONE_FILE_SUFFIX)


def screen_zone_path(screen_index: int) -> Path:
    """1-based 화면 번호 → data/cctv/screens/screen_N.json."""
    SCREENS_DIR.mkdir(parents=True, exist_ok=True)
    return SCREENS_DIR / f"screen_{screen_index}{ZONE_FILE_SUFFIX}"


def load_zones(source: str | Path) -> list[Zone]:
    """위험구역 파일을 읽는다. 파일이 없으면 빈 목록.

    source: 동영상 경로, screen stem, 또는 .json 경로.
    """
    path = Path(source)
    if path.suffix.lower() != ZONE_FILE_SUFFIX:
        path = zone_file_path(path)
    if not path.exists():
        return []

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ZoneFileError(f"json 형식이 아닙니다: {error}") from error

    items = raw if isinstance(raw, list) else raw.get("zones") if isinstance(raw, dict) else None
    if not isinstance(items, list):
        raise ZoneFileError('"zones" 목록이 없습니다.')

    zones: list[Zone] = []
    for i, item in enumerate(items):
        try:
            zone = Zone.from_dict(item, default_name=str(i + 1))
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            raise ZoneFileError(f"{i + 1}번째 구역 형식이 잘못되었습니다.") from error
        if len(zone.points) < MIN_POINTS:
            raise ZoneFileError(f"{i + 1}번째 구역의 꼭짓점이 {MIN_POINTS}개 미만입니다.")
        zones.append(zone)
    return zones


def save_zones(source: str | Path, zones: list[Zone] | list[dict]) -> None:
    """위험구역 목록 전체로 파일을 덮어쓴다."""
    path = Path(source)
    if path.suffix.lower() != ZONE_FILE_SUFFIX:
        path = zone_file_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    normalized = [zone if isinstance(zone, Zone) else Zone.from_dict(zone) for zone in zones]
    label = path.stem if path.name.startswith("screen_") else Path(source).name
    payload = {
        "video": label,
        "zones": [zone.to_dict() for zone in normalized],
    }

    text = json.dumps(payload, ensure_ascii=False, indent=2)
    temp_path = path.with_name(f"{path.name}.tmp")
    try:
        temp_path.write_text(text, encoding="utf-8")
        temp_path.replace(path)
    except OSError:
        temp_path.unlink(missing_ok=True)
        raise


def next_zone_number(zones: list[Zone] | list[dict]) -> int:
    names = [zone.name if isinstance(zone, Zone) else str(zone.get("name", "")) for zone in zones]
    numbers = [int(match.group(1)) for name in names if (match := NAME_NUMBER.search(name))]
    return max(numbers, default=len(zones)) + 1
