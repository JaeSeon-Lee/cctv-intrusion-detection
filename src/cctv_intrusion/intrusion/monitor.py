"""위험구역 침입·경보 상태 추적.

발 위치가 구역 안에 있는 시간을 누적해 MonitorState 를 갱신한다.
경보가 난 뒤 구역에서 벗어나 해제되면 IntrusionEvent 를 남긴다.
"""

from __future__ import annotations

import cv2
import numpy as np

from cctv_intrusion.detection import Detection
from cctv_intrusion.intrusion.criteria import MonitorState, alert_seconds_for, foot_point
from cctv_intrusion.intrusion.events import IntrusionEvent
from cctv_intrusion.zone import Zone

STATE_LABELS: dict[MonitorState, str] = {
    MonitorState.IDLE: "대기",
    MonitorState.ARMED: "감지 중",
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
        self.new_events: list[IntrusionEvent] = []
        self._dwell_sec: dict[str, float] = {}
        # 경보 중인 구역 → (경보 확정 시각(초), level)
        self._active_alarms: dict[str, tuple[float, str]] = {}
        self._last_frame_index: int | None = None
        self._last_fps = 0.0

    def reset(self) -> None:
        self.zones = []
        self.state = MonitorState.IDLE
        self.new_events = []
        self._dwell_sec.clear()
        self._active_alarms.clear()
        self._last_frame_index = None
        self._last_fps = 0.0

    def set_zones(self, zones: list[Zone]) -> MonitorState:
        self.zones = list(zones)
        names = {zone.name for zone in self.zones}
        self._dwell_sec = {name: self._dwell_sec.get(name, 0.0) for name in names}
        self._active_alarms = {
            name: value for name, value in self._active_alarms.items() if name in names
        }
        if not self.zones:
            self.state = MonitorState.IDLE
            self._dwell_sec.clear()
            self._active_alarms.clear()
        elif self.state in (MonitorState.IDLE, MonitorState.CLEARED):
            self.state = MonitorState.ARMED
        return self.state

    def update(
        self,
        detections: list[Detection],
        frame_index: int,
        fps: float,
    ) -> MonitorState:
        self.new_events = []
        self._last_fps = fps

        if not self.zones:
            self.state = MonitorState.IDLE
            self._dwell_sec.clear()
            self._active_alarms.clear()
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
        video_sec = frame_index / fps if fps > 0 else 0.0
        for zone in self.zones:
            if zone.name in inside_names:
                self._dwell_sec[zone.name] = self._dwell_sec.get(zone.name, 0.0) + dt
                dwell = self._dwell_sec[zone.name]
                if dwell >= alert_seconds_for(zone.level):
                    alarmed = True
                    if zone.name not in self._active_alarms:
                        self._active_alarms[zone.name] = (video_sec, str(zone.level))
            else:
                self._dwell_sec[zone.name] = 0.0
                active = self._active_alarms.pop(zone.name, None)
                if active is not None:
                    alarm_sec, zone_level = active
                    self.new_events.append(
                        IntrusionEvent.create(
                            alarm_sec=alarm_sec,
                            cleared_sec=video_sec,
                            zone_name=zone.name,
                            zone_level=zone_level,
                        )
                    )

        if alarmed:
            self.state = MonitorState.ALARM
        elif self.state == MonitorState.ALARM:
            self.state = MonitorState.CLEARED
        elif self.state == MonitorState.CLEARED and not inside_names:
            self.state = MonitorState.ARMED
        elif self.state != MonitorState.CLEARED:
            self.state = MonitorState.ARMED

        return self.state

    def close_alarms(self) -> list[IntrusionEvent]:
        """아직 경보 중인 구역을 마지막 탐지 시각에 해제된 사건으로 만들어 돌려준다.

        실시간 영상 연결을 끊을 때처럼 해제를 기다릴 수 없을 때 쓴다.
        """
        if self._last_frame_index is None or self._last_fps <= 0:
            return []
        cleared_sec = self._last_frame_index / self._last_fps
        events = [
            IntrusionEvent.create(
                alarm_sec=alarm_sec,
                cleared_sec=cleared_sec,
                zone_name=zone_name,
                zone_level=zone_level,
            )
            for zone_name, (alarm_sec, zone_level) in self._active_alarms.items()
        ]
        self._active_alarms.clear()
        for name in self._dwell_sec:
            self._dwell_sec[name] = 0.0
        if self.state == MonitorState.ALARM:
            self.state = MonitorState.CLEARED
        return events
