from dataclasses import dataclass, field


@dataclass
class DangerZone:
    name: str
    points: list[list[int]] = field(default_factory=list)
    level: str = "danger"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "points": self.points,
            "level": self.level,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DangerZone":
        return cls(
            name=str(data.get("name", "1")),
            points=[[int(x), int(y)] for x, y in data.get("points", [])],
            level=str(data.get("level", "danger")),
        )
