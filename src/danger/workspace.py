from pathlib import Path

import cv2
import numpy as np

from .editor import DangerZoneEditor
from .overlay import DangerZoneOverlay
from .store import DangerZoneStore
from .zone import DangerZone
from .zone_list import DangerZoneList

DELETE_KEYS = {8, 127}


class DangerWorkspace:
    """영상 영역과 리스트를 한 창에서 같은 높이로 붙이고 입력을 라우팅한다."""

    def __init__(self, window_name: str, video_path: str | Path):
        self.window_name = window_name
        self.store = DangerZoneStore(video_path)
        self.zones: list[DangerZone] = self.store.load()
        self.editor = DangerZoneEditor()
        self.zone_list = DangerZoneList()
        self.overlay = DangerZoneOverlay()
        self.selected_index: int | None = None
        self._video_w = 0

        cv2.namedWindow(self.window_name)
        cv2.setMouseCallback(self.window_name, self._on_mouse)

    def render(self, frame: np.ndarray) -> np.ndarray:
        video = frame.copy()
        self._video_w = video.shape[1]
        self.overlay.draw(video, self.zones, self.selected_index)
        self.editor.draw_preview(video)
        self.editor.draw_buttons(video)
        sidebar = self.zone_list.draw(video.shape[0], self.zones, self.selected_index)
        return np.hstack([video, sidebar])

    def handle_key(self, key: int) -> None:
        if key in DELETE_KEYS:
            self._delete_selected()

    def _on_mouse(self, event, x, y, flags, param) -> None:
        if event != cv2.EVENT_LBUTTONDOWN or self._video_w == 0:
            return

        if x >= self._video_w:
            self._on_list_click(y)
            return

        button = self.editor.hit_button(x, y)
        if button == "start":
            self.editor.toggle_start()
            return
        if button == "complete":
            self._complete_zone()
            return
        self.editor.add_point(x, y)

    def _on_list_click(self, y: int) -> None:
        index = self.zone_list.index_at(y, len(self.zones))
        self.selected_index = index

    def _complete_zone(self) -> None:
        points = self.editor.try_complete()
        if points is None:
            return
        name = self.zone_list.next_name(self.zones)
        self.zones.append(DangerZone(name=name, points=points, level="danger"))
        self.store.save(self.zones)
        self.selected_index = len(self.zones) - 1

    def _delete_selected(self) -> None:
        if self.selected_index is None:
            return
        if not (0 <= self.selected_index < len(self.zones)):
            self.selected_index = None
            return
        del self.zones[self.selected_index]
        self.store.save(self.zones)
        if not self.zones:
            self.selected_index = None
        elif self.selected_index >= len(self.zones):
            self.selected_index = len(self.zones) - 1
