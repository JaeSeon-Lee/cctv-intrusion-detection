"""위험구역 침입·경보 상태 추적.

발 위치가 구역 안에 있는 시간을 누적해 MonitorState 를 갱신한다.
"""

from __future__ import annotations

import cv2
import numpy as np

from cctv_intrusion.detection import Detection
from cctv_intrusion.intrusion.criteria import MonitorState, alert_seconds_for, foot_point
from cctv_intrusion.zone import Zone

STATE_LABELS: dict[MonitorState, str] = {
    MonitorState.IDLE: "대기",
    MonitorState.ARMED: "감지",
    MonitorState.ALARM: "경보",
    MonitorState.CLEARED: "해제",
}


def point_in_zone(point: tuple[float, float], zone: Zone) -> bool:
    if len(zone.points) < 3:
        return False
    contour = np.array(zone.points, dtype=np.float32)
    return cv2.pointPolygonTest(contour, point, False) >= 0


class IntrusionMonitor:
    """구역 설정·사람 탐지 결과를 받아 경보 상태를 만든다."""

    def __init__(self) -> None:
        self.zones: list[Zone] = []
        self.state = MonitorState.IDLE
        self._dwell_sec: dict[str, float] = {}
        self._last_frame_index: int | None = None

    def reset(self) -> None:
        self.zones = []
        self.state = MonitorState.IDLE
        self._dwell_sec.clear()
        self._last_frame_index = None

    def set_zones(self, zones: list[Zone]) -> MonitorState:
        self.zones = list(zones)
        self._dwell_sec = {zone.name: self._dwell_sec.get(zone.name, 0.0) for zone in self.zones}
        if not self.zones:
            self.state = MonitorState.IDLE
            self._dwell_sec.clear()
        elif self.state in (MonitorState.IDLE, MonitorState.CLEARED):
            self.state = MonitorState.ARMED
        return self.state

    def update(
        self,
        detections: list[Detection],
        frame_index: int,
        fps: float,
    ) -> MonitorState:
        if not self.zones:
            self.state = MonitorState.IDLE
            self._dwell_sec.clear()
            self._last_frame_index = frame_index
            return self.state

        dt = 0.0
        if self._last_frame_index is not None and fps > 0:
            gap = max(0, frame_index - self._last_frame_index)
            dt = gap / fps
        self._last_frame_index = frame_index

        inside_names: set[str] = set()
        for detection in detections:
            foot = foot_point(detection.x1, detection.y1, detection.x2, detection.y2)
            for zone in self.zones:
                if point_in_zone(foot, zone):
                    inside_names.add(zone.name)

        alarmed = False
        for zone in self.zones:
            if zone.name in inside_names:
                self._dwell_sec[zone.name] = self._dwell_sec.get(zone.name, 0.0) + dt
                if self._dwell_sec[zone.name] >= alert_seconds_for(zone.level):
                    alarmed = True
            else:
                self._dwell_sec[zone.name] = 0.0

        if alarmed:
            self.state = MonitorState.ALARM
        elif self.state == MonitorState.ALARM:
            self.state = MonitorState.CLEARED
        elif self.state == MonitorState.CLEARED and not inside_names:
            self.state = MonitorState.ARMED
        elif self.state != MonitorState.CLEARED:
            self.state = MonitorState.ARMED

        return self.state
