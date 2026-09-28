from pathlib import Path

from cctv_intrusion.ui.widget.replay_page import clips_dir_for, list_related_clips


def test_clips_dir_for_uses_stem_folder(tmp_path: Path):
    video = tmp_path / "cam1.mp4"
    assert clips_dir_for(video) == tmp_path / "cam1"


def test_list_related_clips(tmp_path: Path):
    video = tmp_path / "cam1.mp4"
    video.write_bytes(b"x")
    folder = tmp_path / "cam1"
    folder.mkdir()
    (folder / "event_1.mp4").write_bytes(b"a")
    (folder / "event_2.mp4").write_bytes(b"b")
    (folder / "notes.txt").write_text("no")

    clips = list_related_clips(video)
    assert [path.name for path in clips] == ["event_1.mp4", "event_2.mp4"]


def test_list_related_clips_missing_folder(tmp_path: Path):
    assert list_related_clips(tmp_path / "none.mp4") == []
