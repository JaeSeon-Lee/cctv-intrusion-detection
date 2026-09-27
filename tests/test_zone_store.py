import json

import pytest

from cctv_intrusion.zone import (
    ZoneFileError,
    load_zones,
    next_zone_number,
    save_zones,
    zone_file_path,
)

TRIANGLE = [(0, 0), (10, 0), (5, 8)]


def test_zone_file_next_to_video(tmp_path):
    assert zone_file_path(tmp_path / "cam1.mp4") == tmp_path / "cam1.json"


def test_no_file_means_no_zones(tmp_path):
    assert load_zones(tmp_path / "cam1.mp4") == []


def test_save_then_load_round_trip(tmp_path):
    video = tmp_path / "cam1.mp4"
    save_zones(video, [{"name": "구역 1", "points": TRIANGLE}])

    assert load_zones(video) == [{"name": "구역 1", "points": TRIANGLE, "level": "danger"}]
    saved = json.loads(zone_file_path(video).read_text(encoding="utf-8"))
    assert saved["video"] == "cam1.mp4"
    assert not (tmp_path / "cam1.json.tmp").exists()


def test_save_empty_list_overwrites(tmp_path):
    video = tmp_path / "cam1.mp4"
    save_zones(video, [{"name": "구역 1", "points": TRIANGLE}])
    save_zones(video, [])
    assert load_zones(video) == []


def test_load_teammate_format(tmp_path):
    # feature/danger 의 DangerZoneStore 가 만든 파일 (이름이 번호만, 최상위가 목록인 경우도 허용)
    video = tmp_path / "cam1.mp4"
    zones = [{"name": "2", "points": [[1, 2], [3, 4], [5, 6]], "level": "warning"}]
    zone_file_path(video).write_text(json.dumps(zones), encoding="utf-8")

    assert load_zones(video) == [
        {"name": "2", "points": [(1, 2), (3, 4), (5, 6)], "level": "warning"}
    ]


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
    assert next_zone_number([{"name": "구역 1"}, {"name": "구역 5"}]) == 6
    assert next_zone_number([{"name": "3"}]) == 4
    assert next_zone_number([{"name": "입구"}, {"name": "창고"}]) == 3
