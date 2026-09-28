import json

import pytest

from cctv_intrusion.paths import SCREENS_DIR
from cctv_intrusion.zone import (
    Zone,
    ZoneFileError,
    format_level,
    get_level,
    load_zones,
    next_zone_number,
    normalize_level_id,
    save_zones,
    screen_zone_path,
    zone_file_path,
)

TRIANGLE = [(0, 0), (10, 0), (5, 8)]


def test_zone_file_next_to_video(tmp_path):
    assert zone_file_path(tmp_path / "cam1.mp4") == tmp_path / "cam1.json"


def test_screen_zone_path():
    assert screen_zone_path(1) == SCREENS_DIR / "screen_1.json"
    assert screen_zone_path(4).name == "screen_4.json"


def test_save_screen_zones(tmp_path, monkeypatch):
    monkeypatch.setattr("cctv_intrusion.zone.zone_store.SCREENS_DIR", tmp_path)
    path = screen_zone_path(2)
    save_zones(path, [Zone(name="구역 1", points=TRIANGLE)])
    assert load_zones(path) == [Zone(name="구역 1", points=TRIANGLE, level="danger")]


def test_no_file_means_no_zones(tmp_path):
    assert load_zones(tmp_path / "cam1.mp4") == []


def test_save_then_load_round_trip(tmp_path):
    video = tmp_path / "cam1.mp4"
    save_zones(video, [Zone(name="구역 1", points=TRIANGLE)])

    assert load_zones(video) == [Zone(name="구역 1", points=TRIANGLE, level="danger")]
    saved = json.loads(zone_file_path(video).read_text(encoding="utf-8"))
    assert saved["video"] == "cam1.mp4"
    assert not (tmp_path / "cam1.json.tmp").exists()


def test_save_level_normalized(tmp_path):
    video = tmp_path / "cam1.mp4"
    save_zones(
        video,
        [
            {"name": "구역 1", "points": TRIANGLE, "level": "주의"},
            {"name": "구역 2", "points": TRIANGLE, "level": 4},
        ],
    )
    zones = load_zones(video)
    assert zones[0].level == "caution"
    assert zones[1].level == "danger"  # rank 4 → 최대 등급(위험)


def test_save_empty_list_overwrites(tmp_path):
    video = tmp_path / "cam1.mp4"
    save_zones(video, [Zone(name="구역 1", points=TRIANGLE)])
    save_zones(video, [])
    assert load_zones(video) == []


def test_load_teammate_format(tmp_path):
    video = tmp_path / "cam1.mp4"
    zones = [{"name": "2", "points": [[1, 2], [3, 4], [5, 6]], "level": "warning"}]
    zone_file_path(video).write_text(json.dumps(zones), encoding="utf-8")

    assert load_zones(video) == [Zone(name="2", points=[(1, 2), (3, 4), (5, 6)], level="danger")]


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        json.dumps({"other": 1}),
        json.dumps({"zones": [{"name": "a"}]}),
        json.dumps({"zones": [{"name": "a", "points": [[0, 0], [1, 1]]}]}),
        json.dumps({"zones": [{"name": "a", "points": [[0, "x"], [1, 1], [2, 2]]}]}),
    ],
)
def test_invalid_file_raises(tmp_path, content):
    video = tmp_path / "cam1.mp4"
    zone_file_path(video).write_text(content, encoding="utf-8")
    with pytest.raises(ZoneFileError):
        load_zones(video)


def test_next_zone_number():
    assert next_zone_number([]) == 1
    assert (
        next_zone_number(
            [Zone(name="구역 1", points=TRIANGLE), Zone(name="구역 5", points=TRIANGLE)]
        )
        == 6
    )
    assert next_zone_number([Zone(name="3", points=TRIANGLE)]) == 4
    assert (
        next_zone_number([Zone(name="입구", points=TRIANGLE), Zone(name="창고", points=TRIANGLE)])
        == 3
    )


def test_level_helpers():
    assert normalize_level_id("금지") == "detect"
    assert normalize_level_id("감지") == "detect"
    assert normalize_level_id(1) == "detect"
    assert normalize_level_id(2) == "caution"
    assert normalize_level_id(3) == "danger"
    assert get_level("critical").rank == 3
    assert get_level("detect").alert_seconds == 3.0
    assert get_level("caution").alert_seconds == 2.0
    assert get_level("danger").alert_seconds == 1.0
    assert format_level("danger") == "3 위험"
    assert format_level("detect") == "1 감지"
