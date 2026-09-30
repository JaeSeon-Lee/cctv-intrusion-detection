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


def test_dashboard_button_needs_selected_recording(qtbot, tmp_path: Path, monkeypatch):
    from cctv_intrusion.ui.widget import replay_page
    from cctv_intrusion.ui.widget.dashboard_dialog import DashboardDialog

    cam3 = tmp_path / "cam3"
    cam3.mkdir()
    recording = cam3 / "20260929_120000.ts"
    recording.write_bytes(b"x")
    (cam3 / "live_1.mp4").write_bytes(b"x")
    (cam3 / "events.csv").write_text(
        "alarm_at,cleared_at,duration_sec,clip_start,clip_end,clip_file,zone_name,zone_level,"
        "source_file,source_alarm_at,source_cleared_at\n"
        "00:03.000,00:05.000,2.00,00:00.000,00:10.000,live_1.mp4,구역 1,danger,"
        "20260929_120000.ts,00:40.000,00:42.000\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(replay_page, "RECORDINGS_DIR", tmp_path)
    monkeypatch.setattr(replay_page, "list_intrusion_clips", lambda: [cam3 / "live_1.mp4"])

    page = replay_page.ReplayPage()
    qtbot.addWidget(page)
    assert not page.dashboard_button.isEnabled()

    # 폴더를 고르면 비활성
    page.tree.setCurrentIndex(page.model.index(str(cam3)))
    assert not page.dashboard_button.isEnabled()

    page.tree.setCurrentIndex(page.model.index(str(recording)))
    assert page.dashboard_button.isEnabled()
    assert page.selected_recording() == recording

    dialog = page.open_dashboard()
    assert isinstance(dialog, DashboardDialog)
    assert dialog.stats.count == 1
    assert dialog.stats.events[0].alarm_sec == 40.0
    assert dialog.table.item(0, 6).text() == "live_1.mp4"
    dialog.close()

    # 선택이 풀리면 (예: 침입 클립 재생) 비활성
    page.tree.clearSelection()
    assert not page.dashboard_button.isEnabled()
    assert page.open_dashboard() is None
