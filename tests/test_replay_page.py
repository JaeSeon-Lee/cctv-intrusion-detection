from pathlib import Path

from cctv_intrusion.ui.widget.replay_page import list_intrusion_clips


def test_list_intrusion_clips(tmp_path: Path):
    (tmp_path / "live_1.mp4").write_bytes(b"a")
    (tmp_path / "test_2.mp4").write_bytes(b"b")
    (tmp_path / "notes.csv").write_text("x")
    (tmp_path / "subdir").mkdir()

    clips = list_intrusion_clips(output_dir=tmp_path)
    assert [path.name for path in clips] == ["live_1.mp4", "test_2.mp4"]


def test_list_intrusion_clips_missing(tmp_path: Path):
    assert list_intrusion_clips(output_dir=tmp_path / "none") == []
