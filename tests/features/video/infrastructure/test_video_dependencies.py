import numpy as np
import pytest

from tests.fakes.fake_video_source import FakeVideoSource
from vision_core.composition import build_video_with


def test_build_video_wires_use_cases_with_injected_source():
    frame = np.zeros((2, 2, 3), dtype=np.uint8)
    source = FakeVideoSource([frame])

    video = build_video_with(source=source)

    video.open()
    assert np.array_equal(video.read_frame(), frame)
    assert video.read_frame() is None
    video.close()
    assert video.dropped_frames == 0


def test_build_video_can_expose_latest_frame_adapter():
    video = build_video_with(source=FakeVideoSource([]), latest=True)

    assert video.dropped_frames == 0


def test_build_video_rejects_unknown_configuration(monkeypatch):
    monkeypatch.setenv("VISION_CORE_VIDEO_SOURCE", "bogus")

    with pytest.raises(ValueError):
        build_video_with()


def test_build_video_file_requires_path(monkeypatch):
    monkeypatch.setenv("VISION_CORE_VIDEO_SOURCE", "file")
    monkeypatch.delenv("VISION_CORE_VIDEO_PATH", raising=False)

    with pytest.raises(ValueError):
        build_video_with()
