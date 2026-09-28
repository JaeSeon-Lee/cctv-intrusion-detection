"""위험구역 데이터 모델."""

from __future__ import annotations

from dataclasses import dataclass, field

from .levels import DEFAULT_LEVEL_ID, normalize_level_id

type Point = tuple[int, int]

# 다각형이 되려면 필요한 최소 꼭짓점 수
MIN_POINTS = 3


@dataclass(slots=True)
class Zone:
    """영상 위 위험구역 하나.

    points: 원본 프레임 픽셀 좌표
    level: caution | danger | detect

    """

    name: str
    points: list[Point] = field(default_factory=list)
    level: str = DEFAULT_LEVEL_ID

    def __post_init__(self) -> None:
        self.level = normalize_level_id(self.level)
        self.points = [(int(x), int(y)) for x, y in self.points]

    @classmethod
    def from_dict(cls, data: dict, *, default_name: str = "1") -> Zone:
        return cls(
            name=str(data.get("name", default_name)),
            points=[(int(x), int(y)) for x, y in data["points"]],
            level=data.get("level", DEFAULT_LEVEL_ID),
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "points": [[int(x), int(y)] for x, y in self.points],
            "level": normalize_level_id(self.level),
        }
