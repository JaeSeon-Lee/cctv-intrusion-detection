import pytest

from cctv_intrusion.ui.styles import STYLE_DIR, load_qss


@pytest.mark.parametrize("path", sorted(STYLE_DIR.glob("*.qss")), ids=lambda p: p.stem)
def test_load_qss(path):
    assert load_qss(path.stem) == path.read_text(encoding="utf-8")


def test_main_window_starts(qtbot):
    from cctv_intrusion.ui import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    assert window.zone_panel.zones == []
    # 창을 닫아야 closeEvent 에서 사람 탐지 스레드가 종료된다.
    # (닫지 않고 window 가 해제되면 실행 중인 QThread 가 파괴되어 프로세스가 강제 종료됨)
    window.close()
