from unittest.mock import Mock

import numpy as np
import pytest

from tests.fakes.fake_video_source import FakeVideoSource
from vision_core.core.errors import ConfigurationError, VideoSourceError, codes
from vision_core.features.video.domain.ports.video_source import VideoSource
from vision_core.features.video.infrastructure.adapters.latest_frame_source import LatestFrameSource
from vision_core.features.video.infrastructure.adapters.rtsp_video_source import RtspVideoSource

FRAME = np.zeros((2, 3, 3), dtype=np.uint8)


def _cached_source():
    return FakeVideoSource([FRAME])


def _latest_source():
    return LatestFrameSource(FakeVideoSource([FRAME]))


@pytest.mark.parametrize("factory", [_cached_source, _latest_source])
def test_video_port_contract_with_fake_and_real_adapter(factory):
    source = factory()
    assert isinstance(source, VideoSource)
    source.open()
    assert np.array_equal(source.read_frame(), FRAME)
    assert source.read_frame() is None
    source.close()


def test_rtsp_configuration_error_has_stable_code_and_no_credentials():
    with pytest.raises(ConfigurationError) as error:
        RtspVideoSource("rtsp://user:secret@host/stream", open_timeout_ms=0)
    assert error.value.code == codes.CONFIGURATION_INVALID
    assert "secret" not in str(error.value)
    assert "secret" not in str(error.value.context)


def test_latest_frame_adapter_propagates_typed_video_error():
    failing = Mock()
    failing.open.side_effect = VideoSourceError("sin stream")
    source = LatestFrameSource(failing)
    source.open()
    with pytest.raises(VideoSourceError) as error:
        source.read_frame()
    assert error.value.retryable is True
    source.close()
