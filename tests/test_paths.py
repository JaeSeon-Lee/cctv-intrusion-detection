from cctv_intrusion.paths import DATA_DIR, INPUT_DIR, MODELS_DIR, OUTPUT_DIR, PROJECT_ROOT


def test_project_root_has_pyproject():
    assert (PROJECT_ROOT / "pyproject.toml").is_file()


def test_data_dirs_under_project_root():
    assert INPUT_DIR.parent == DATA_DIR
    assert OUTPUT_DIR.parent == DATA_DIR
    assert DATA_DIR.parent == PROJECT_ROOT
    assert MODELS_DIR.parent == PROJECT_ROOT
