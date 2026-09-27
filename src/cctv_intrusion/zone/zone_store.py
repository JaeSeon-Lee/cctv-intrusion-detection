# 위험구역을 동영상 옆 json 파일로 저장하고 불러온다.
# 동영상과 같은 폴더, 같은 파일 이름에 확장자만 .json (예: data/input/a.mp4 → data/input/a.json)
#
# 파일 형식은 팀원 DangerZoneStore(feature/danger)와 같게 맞춰서 서로 만든 파일을 그대로 읽을 수 있다.
#   {
#     "video": "a.mp4",
#     "zones": [{"name": "구역 1", "points": [[x, y], ...], "level": "danger"}, ...]
#   }
#   points: 원본 프레임 픽셀 좌표
import json
import re
from pathlib import Path

type Point = tuple[int, int]
type Zone = dict  # {"name": str, "points": list[Point], "level": str(파일에서 읽은 경우)}

ZONE_FILE_SUFFIX = ".json"
# 파일에 level이 없을 때 쓰는 기본 위험 등급 (팀원 DangerZone 기본값과 같음)
DEFAULT_LEVEL = "danger"
# 다각형이 되려면 필요한 최소 꼭짓점 수
MIN_POINTS = 3
# 구역 이름 끝에 붙은 번호 ("구역 3" → 3, 팀원 형식 "3" → 3)
NAME_NUMBER = re.compile(r"(\d+)\s*$")


class ZoneFileError(Exception):
    """json 파일 내용이 위험구역 형식이 아닐 때"""


def zone_file_path(video_path: str | Path) -> Path:
    return Path(video_path).with_suffix(ZONE_FILE_SUFFIX)


def load_zones(video_path: str | Path) -> list[Zone]:
    # 동영상에 딸린 위험구역 파일을 읽는다. 파일이 없으면 빈 목록.
    # 파일은 있는데 읽을 수 없으면 OSError, 형식이 틀리면 ZoneFileError
    path = zone_file_path(video_path)
    if not path.exists():
        return []

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ZoneFileError(f"json 형식이 아닙니다: {error}") from error

    # 팀원 코드처럼 최상위가 구역 목록 그 자체인 파일도 받아준다
    items = raw if isinstance(raw, list) else raw.get("zones") if isinstance(raw, dict) else None
    if not isinstance(items, list):
        raise ZoneFileError('"zones" 목록이 없습니다.')

    zones = []
    for i, item in enumerate(items):
        try:
            points = [(int(x), int(y)) for x, y in item["points"]]
            name = str(item.get("name", i + 1))
            level = str(item.get("level", DEFAULT_LEVEL))
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            raise ZoneFileError(f"{i + 1}번째 구역 형식이 잘못되었습니다.") from error
        if len(points) < MIN_POINTS:
            raise ZoneFileError(f"{i + 1}번째 구역의 꼭짓점이 {MIN_POINTS}개 미만입니다.")
        zones.append({"name": name, "points": points, "level": level})
    return zones


def save_zones(video_path: str | Path, zones: list[Zone]) -> None:
    # 위험구역 목록 전체로 파일을 덮어쓴다. 구역이 0개여도 빈 목록으로 저장한다.
    path = zone_file_path(video_path)
    payload = {
        "video": Path(video_path).name,
        "zones": [
            {
                "name": zone["name"],
                "points": [[int(x), int(y)] for x, y in zone["points"]],
                "level": zone.get("level", DEFAULT_LEVEL),
            }
            for zone in zones
        ],
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)

    # 임시 파일에 다 쓴 다음 바꿔치기한다. 쓰는 도중 앱이 꺼져도 기존 파일이 반쯤 잘린 채로 남지 않는다.
    temp_path = path.with_name(f"{path.name}.tmp")
    try:
        temp_path.write_text(text, encoding="utf-8")
        temp_path.replace(path)
    except OSError:
        temp_path.unlink(missing_ok=True)
        raise


def next_zone_number(zones: list[Zone]) -> int:
    # 새로 만들 구역에 붙일 번호: 이름 끝 번호 중 가장 큰 값 + 1 (이름에 번호가 없으면 구역 수 + 1)
    numbers = [int(match.group(1)) for zone in zones if (match := NAME_NUMBER.search(zone["name"]))]
    return max(numbers, default=len(zones)) + 1
