"""BGR 프레임에 구역·탐지 박스·경보 상태를 그린다 (상시 녹화용).

UI(QPainter)와 같은 정보를 OpenCV로 그려, 녹화 파이프라인이 Qt 표시 스케일에
묶이지 않게 한다. Hershey 폰트는 한글 미지원이라 상태 배지는 ASCII 라벨을 쓴다.
"""

from __future__ import annotations

import cv2
import numpy as np

from cctv_intrusion.detection import Detection
from cctv_intrusion.intrusion.criteria import MonitorState
from cctv_intrusion.zone import Zone
from cctv_intrusion.zone.levels import get_level

ALARM_FRAME_WIDTH = 8
STATUS_MARGIN = 12
STATUS_PAD_X = 10
STATUS_PAD_Y = 8
ZONE_FILL_ALPHA = 0.25

# BGR — ui.styles.colors 와 맞춤 (video→ui 순환 import 방지)
_ZONE_LEVEL_BGR = {
    "detect": (8, 179, 234),
    "caution": (11, 158, 245),
    "danger": (38, 38, 220),
    "warning": (11, 158, 245),
    "restricted": (8, 179, 234),
    "critical": (28, 28, 185),
}
_ZONE_SELECTED_BGR = (36, 191, 251)
_PERSON_BOX_BGR = (129, 185, 16)
_ALARM_FRAME_BGR = (38, 38, 220)
_MONITOR_STATE_BGR = {
    "idle": (139, 116, 100),
    "armed": (110, 118, 15),
    "alarm": (38, 38, 220),
    "cleared": (6, 119, 217),
}

_STATE_ASCII: dict[MonitorState, str] = {
    MonitorState.IDLE: "IDLE",
    MonitorState.ARMED: "ARMED",
    MonitorState.ALARM: "ALARM",
    MonitorState.CLEARED: "CLEARED",
}


def _zone_bgr(level_id: str | int | None) -> tuple[int, int, int]:
    level = get_level(level_id)
    return _ZONE_LEVEL_BGR.get(level.id, _ZONE_LEVEL_BGR["danger"])


def compose_overlay_frame(
    frame: np.ndarray,
    zones: list[Zone],
    detections: list[Detection],
    state: MonitorState,
    *,
    selected_index: int = -1,
) -> np.ndarray:
    """원본 BGR 복사본에 오버레이를 그려 반환한다."""
    out = frame.copy()
    _draw_zones(out, zones, selected_index=selected_index)
    _draw_detections(out, detections)
    _draw_monitor_state(out, state)
    return out


def _draw_zones(frame: np.ndarray, zones: list[Zone], *, selected_index: int) -> None:
    if not zones:
        return
    overlay = frame.copy()
    for zone in zones:
        if len(zone.points) < 3:
            continue
        pts = np.array(zone.points, dtype=np.int32)
        cv2.fillPoly(overlay, [pts], _zone_bgr(zone.level))
    cv2.addWeighted(overlay, ZONE_FILL_ALPHA, frame, 1.0 - ZONE_FILL_ALPHA, 0, frame)

    for i, zone in enumerate(zones):
        if len(zone.points) < 3:
            continue
        selected = i == selected_index
        bgr = _zone_bgr(zone.level)
        pts = np.array(zone.points, dtype=np.int32)
        edge = _ZONE_SELECTED_BGR if selected else bgr
        cv2.polylines(frame, [pts], True, edge, 4 if selected else 2, cv2.LINE_AA)


def _draw_detections(frame: np.ndarray, detections: list[Detection]) -> None:
    if not detections:
        return
    for detection in detections:
        cv2.rectangle(
            frame,
            (int(detection.x1), int(detection.y1)),
            (int(detection.x2), int(detection.y2)),
            _PERSON_BOX_BGR,
            2,
            cv2.LINE_AA,
        )


def _draw_monitor_state(frame: np.ndarray, state: MonitorState) -> None:
    height, width = frame.shape[:2]
    if state == MonitorState.ALARM:
        inset = ALARM_FRAME_WIDTH // 2
        cv2.rectangle(
            frame,
            (inset, inset),
            (width - 1 - inset, height - 1 - inset),
            _ALARM_FRAME_BGR,
            ALARM_FRAME_WIDTH,
            cv2.LINE_AA,
        )

    label = _STATE_ASCII.get(state, str(state))
    text = f"STATUS  {label}"
    bg_bgr = _MONITOR_STATE_BGR.get(state.value, _MONITOR_STATE_BGR["idle"])
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.6
    thickness = 2
    (tw, th), baseline = cv2.getTextSize(text, font, scale, thickness)
    box_w = tw + STATUS_PAD_X * 2
    box_h = th + baseline + STATUS_PAD_Y * 2
    x1 = width - box_w - STATUS_MARGIN
    y1 = STATUS_MARGIN
    x2 = x1 + box_w
    y2 = y1 + box_h
    cv2.rectangle(frame, (x1, y1), (x2, y2), bg_bgr, -1)
    cv2.putText(
        frame,
        text,
        (x1 + STATUS_PAD_X, y1 + STATUS_PAD_Y + th),
        font,
        scale,
        (255, 255, 255),
        thickness,
        cv2.LINE_AA,
    )
