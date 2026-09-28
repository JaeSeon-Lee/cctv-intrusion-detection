from cctv_intrusion.paths import (
    CCTV_DIR,
    DATA_DIR,
    MODELS_DIR,
    OUTPUT_DIR,
    PROJECT_ROOT,
    RECORDINGS_DIR,
    SCREENS_DIR,
)


def test_project_root_has_pyproject():
    assert (PROJECT_ROOT / "pyproject.toml").is_file()


def test_data_dirs_under_project_root():
    assert CCTV_DIR.parent == DATA_DIR
    assert SCREENS_DIR.parent == CCTV_DIR
    assert RECORDINGS_DIR.parent == DATA_DIR
    assert OUTPUT_DIR.parent == DATA_DIR
    assert DATA_DIR.parent == PROJECT_ROOT
    assert MODELS_DIR.parent == PROJECT_ROOT
