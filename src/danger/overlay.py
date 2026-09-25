import cv2
import numpy as np

from .text import put_text
from .zone import DangerZone


class DangerZoneOverlay:
    """영상 위 위험구역 다각형과 이름 라벨."""

    def draw(
        self,
        frame: np.ndarray,
        zones: list[DangerZone],
        selected_index: int | None = None,
    ) -> np.ndarray:
        """구역을 프레임에 그린다. in-place."""
        for i, zone in enumerate(zones):
            if len(zone.points) < 2:
                continue
            pts = np.array(zone.points, np.int32)
            selected = i == selected_index
            color = (0, 220, 255) if selected else (0, 255, 255)
            if selected:
                overlay = frame.copy()
                cv2.fillPoly(overlay, [pts], (0, 0, 180))
                cv2.addWeighted(overlay, 0.35, frame, 0.65, 0, frame)
            cv2.polylines(frame, [pts], True, color, 3 if selected else 2)
            x, y = zone.points[0]
            put_text(frame, str(zone.name), (x + 4, max(y - 22, 0)), font_size=18, color=color)
        return frame
