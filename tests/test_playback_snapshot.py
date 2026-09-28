"""녹화 중 .ts 재생용 스냅샷 테스트."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from cctv_intrusion.video.continuous_recorder import ContinuousRecorder, find_ffmpeg
from cctv_intrusion.video.playback_snapshot import cleanup_snapshot, snapshot_for_playback
from cctv_intrusion.video.video_render import VideoRender


@pytest.mark.skipif(find_ffmpeg() is None, reason="ffmpeg 필요")
def test_snapshot_plays_while_recording(tmp_path: Path):
    recorder = ContinuousRecorder(
        1,
        64,
        48,
        10.0,
        recordings_dir=tmp_path,
    )
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    for i in range(40):
        frame[:] = i
        recorder.write(frame, video_time_sec=i / 10.0)
    recorder.flush()

    snap = snapshot_for_playback(recorder.path)
    try:
        assert snap.exists()
        assert snap != recorder.path
        render = VideoRender(snap)
        assert render.is_opened()
        ok, loaded = render.read()
        render.release()
        assert ok
        assert loaded is not None
    finally:
        cleanup_snapshot(snap)
        recorder.close()
