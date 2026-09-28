from pathlib import Path

from cctv_intrusion.ui.widget.replay_page import list_intrusion_clips


def test_list_intrusion_clips_per_cam_folder(tmp_path: Path):
    cam2 = tmp_path / "cam2"
    cam4 = tmp_path / "cam4"
    cam2.mkdir()
    cam4.mkdir()
    (cam2 / "test_2_1.mp4").write_bytes(b"a")
    (cam4 / "live_1.mp4").write_bytes(b"b")
    (cam2 / "20260928.ts").write_bytes(b"c")
    (cam2 / "events.csv").write_text("x")

    clips = list_intrusion_clips(recordings_dir=tmp_path)
    assert [path.name for path in clips] == ["test_2_1.mp4", "live_1.mp4"]


def test_list_intrusion_clips_missing(tmp_path: Path):
    assert list_intrusion_clips(recordings_dir=tmp_path / "none") == []
