import numpy as np

from cctv_intrusion.detection import Detection
from cctv_intrusion.intrusion import MonitorState
from cctv_intrusion.video.frame_overlay import compose_overlay_frame
from cctv_intrusion.zone import Zone


def test_compose_overlay_frame_draws_without_error():
    frame = np.zeros((120, 160, 3), dtype=np.uint8)
    zones = [
        Zone(
            name="구역 1",
            level="danger",
            points=[(10, 10), (80, 10), (80, 80), (10, 80)],
        )
    ]
    detections = [Detection(x1=20, y1=20, x2=40, y2=90, confidence=0.9)]
    out = compose_overlay_frame(
        frame,
        zones,
        detections,
        MonitorState.ALARM,
        selected_index=0,
    )
    assert out.shape == frame.shape
    assert not np.array_equal(out, frame)
