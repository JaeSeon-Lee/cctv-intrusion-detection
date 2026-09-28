from cctv_intrusion.detection.person_detector import select_device


def test_select_device_returns_known_backend():
    assert select_device() in {"cpu", "mps", "cuda:0"}
