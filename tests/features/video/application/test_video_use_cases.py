import numpy as np

from tests.fakes.fake_video_source import FakeVideoSource
from vision_core.features.video.application.dto.request.request_close_video import (
    RequestCloseVideo,
)
from vision_core.features.video.application.dto.request.request_open_video import (
    RequestOpenVideo,
)
from vision_core.features.video.application.dto.request.request_read_frame import (
    RequestReadFrame,
)
from vision_core.features.video.application.mappers.video_mapper import dto_to_frame
from vision_core.features.video.application.use_cases.close_video import CloseVideo
from vision_core.features.video.application.use_cases.open_video import OpenVideo
from vision_core.features.video.application.use_cases.read_frame import ReadFrame


def test_open_read_and_close_with_fake_source():
    frame = np.zeros((4, 6, 3), dtype=np.uint8)
    frame[:, :, 0] = 12
    source = FakeVideoSource([frame])

    opened = OpenVideo(source).execute(RequestOpenVideo())
    response = ReadFrame(source).execute(RequestReadFrame())
    closed = CloseVideo(source).execute(RequestCloseVideo())

    assert opened.opened is True
    assert closed.closed is True
    assert response.frame_png is not None
    assert (response.width, response.height) == (6, 4)
    assert np.array_equal(dto_to_frame(response), frame)
    assert ReadFrame(source).execute(RequestReadFrame()).frame_png is None
