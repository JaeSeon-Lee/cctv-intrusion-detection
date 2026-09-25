import cv2
import numpy as np

from .text import put_text
from .zone import DangerZone


class DangerZoneList:
    """영상과 같은 높이에 붙는 위험구역 목록. 숫자 이름, 선택, 삭제."""

    WIDTH = 240
    TITLE_H = 44
    ITEM_H = 40

    def next_name(self, zones: list[DangerZone]) -> str:
        numbers: list[int] = []
        for zone in zones:
            try:
                numbers.append(int(zone.name))
            except ValueError:
                continue
        return str(max(numbers, default=0) + 1)

    def index_at(self, y: int, zone_count: int) -> int | None:
        if y < self.TITLE_H:
            return None
        index = (y - self.TITLE_H) // self.ITEM_H
        if 0 <= index < zone_count:
            return index
        return None

    def draw(
        self,
        height: int,
        zones: list[DangerZone],
        selected_index: int | None,
    ) -> np.ndarray:
        panel = np.full((height, self.WIDTH, 3), (36, 36, 36), dtype=np.uint8)
        cv2.rectangle(panel, (0, 0), (self.WIDTH - 1, height - 1), (80, 80, 80), 1)
        put_text(panel, "위험구역 리스트", (12, 10), font_size=18)

        for i, zone in enumerate(zones):
            y1 = self.TITLE_H + i * self.ITEM_H
            y2 = y1 + self.ITEM_H
            if y2 >= height:
                break
            bg = (70, 90, 40) if i == selected_index else (48, 48, 48)
            cv2.rectangle(panel, (8, y1 + 4), (self.WIDTH - 8, y2 - 4), bg, -1)
            put_text(panel, str(zone.name), (20, y1 + 10), font_size=18)
        return panel
