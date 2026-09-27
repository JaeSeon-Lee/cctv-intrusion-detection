from cctv_intrusion.intrusion import (
    ALERT_HOLD_SECONDS,
    EVENT_CLIP_AFTER_SEC,
    EVENT_CLIP_BEFORE_SEC,
    MonitorState,
    foot_point,
)
from cctv_intrusion.zone import alert_seconds_for


def test_foot_point_is_box_bottom_center():
    assert foot_point(10, 20, 30, 40) == (20.0, 40.0)


def test_alert_hold_seconds_by_level():
    assert ALERT_HOLD_SECONDS == {"caution": 3.0, "danger": 2.0, "detect": 1.0}
    assert alert_seconds_for("주의") == 3.0
    assert alert_seconds_for("detect") == 1.0


def test_event_clip_window():
    assert EVENT_CLIP_BEFORE_SEC == 3.0
    assert EVENT_CLIP_AFTER_SEC == 5.0


def test_monitor_states():
    assert set(MonitorState) == {
        MonitorState.IDLE,
        MonitorState.ARMED,
        MonitorState.ALARM,
        MonitorState.CLEARED,
    }
