from __future__ import annotations

import json
from pathlib import Path

from .zone import DangerZone


class DangerZoneStore:
    """동영상과 같은 디렉터리, 같은 파일명의 json을 읽고 덮어쓴다."""

    def __init__(self, video_path: str | Path):
        self.video_path = Path(video_path)
        self.json_path = self.video_path.with_suffix(".json")

    def load(self) -> list[DangerZone]:
        if not self.json_path.exists():
            return []
        with self.json_path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        items = raw if isinstance(raw, list) else raw.get("zones", [])
        return [DangerZone.from_dict(item) for item in items]

    def save(self, zones: list[DangerZone]) -> None:
        payload = {
            "video": self.video_path.name,
            "zones": [zone.to_dict() for zone in zones],
        }
        self.json_path.parent.mkdir(parents=True, exist_ok=True)
        with self.json_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
