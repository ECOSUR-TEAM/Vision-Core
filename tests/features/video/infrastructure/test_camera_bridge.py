import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from scripts.camera_bridge import camera_target, relay_url, forward


def test_relay_preserves_credentials_path_and_query():
    url = 'rtsp://user:p%40ss@[2001:db8::1]:8554/live.sdp?channel=2'
    assert camera_target(url) == ('2001:db8::1', 8554)
    assert relay_url(url) == 'rtsp://user:p%40ss@host.docker.internal:15554/live.sdp?channel=2'
    assert camera_target('rtsp://camera/live.sdp') == ('camera', 554)


@pytest.mark.parametrize('url', ['http://camera/video', 'rtsp:///live.sdp', 'rtsp://camera:bad/live'])
def test_invalid_target_fails_before_startup(url):
    with pytest.raises(ValueError):
        relay_url(url)


def test_forward_preserves_binary_payload_and_applies_backpressure():
    reader = Mock(read=AsyncMock(side_effect=[b'RTSP/1.0\r\n', b'\x24\x00\x00\x02\x00\xff', b'']))
    writer = Mock(drain=AsyncMock())
    asyncio.run(forward(reader, writer))
    assert b''.join(call.args[0] for call in writer.write.call_args_list) == b'RTSP/1.0\r\n\x24\x00\x00\x02\x00\xff'
    assert writer.drain.await_count == 2
