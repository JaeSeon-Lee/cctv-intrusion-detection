import cv2
import numpy as np

from .text import put_text


class DangerZoneEditor:
    """시작 토글과 꼭짓점 입력, 3점 이상일 때 완료 버튼 활성화."""

    START_RECT = (10, 10, 110, 50)
    COMPLETE_RECT = (120, 10, 230, 50)

    def __init__(self) -> None:
        self.editing = False
        self.current_points: list[list[int]] = []

    def can_complete(self) -> bool:
        return self.editing and len(self.current_points) >= 3

    def toggle_start(self) -> None:
        self.editing = not self.editing
        if not self.editing:
            self.current_points = []

    def add_point(self, x: int, y: int) -> None:
        if self.editing:
            self.current_points.append([int(x), int(y)])

    def try_complete(self) -> list[list[int]] | None:
        if not self.can_complete():
            return None
        points = self.current_points
        self.current_points = []
        return points

    def hit_button(self, x: int, y: int) -> str | None:
        if self._inside(x, y, self.START_RECT):
            return "start"
        if self._inside(x, y, self.COMPLETE_RECT):
            return "complete"
        return None

    def draw_preview(self, frame: np.ndarray) -> np.ndarray:
        """그리는 중인 다각형을 프레임에 그린다. in-place."""
        if not self.current_points:
            return frame
        pts = np.array(self.current_points, np.int32)
        cv2.polylines(frame, [pts], False, (0, 0, 255), 2)
        for x, y in self.current_points:
            cv2.circle(frame, (x, y), 4, (0, 0, 255), -1)
        return frame

    def draw_buttons(self, frame: np.ndarray) -> np.ndarray:
        """시작/완료 버튼을 프레임에 그린다. in-place."""
        start_color = (40, 140, 40) if self.editing else (50, 50, 50)
        complete_color = (40, 140, 40) if self.can_complete() else (40, 40, 40)
        self._draw_button(frame, self.START_RECT, start_color, "시작")
        self._draw_button(frame, self.COMPLETE_RECT, complete_color, "완료")
        return frame

    def _draw_button(
        self,
        frame: np.ndarray,
        rect: tuple[int, int, int, int],
        color: tuple[int, int, int],
        label: str,
    ) -> None:
        x1, y1, x2, y2 = rect
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, -1)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (200, 200, 200), 1)
        put_text(frame, label, (x1 + 22, y1 + 10), font_size=20)

    @staticmethod
    def _inside(x: int, y: int, rect: tuple[int, int, int, int]) -> bool:
        x1, y1, x2, y2 = rect
        return x1 <= x <= x2 and y1 <= y <= y2
