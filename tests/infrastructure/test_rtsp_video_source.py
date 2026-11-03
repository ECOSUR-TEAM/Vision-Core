from unittest.mock import Mock

import cv2
import numpy as np
import pytest

from infrastructure.video.rtsp_video_source import RtspVideoSource


URL = "rtsp://user:secret@frigate:8554/entrada"


def capture(opened=True, frames=()):
    cap = Mock()
    cap.open.return_value = opened
    cap.isOpened.return_value = opened
    cap.read.side_effect = frames
    return cap


def source(monkeypatch, caps, **kwargs):
    factory = Mock(side_effect=caps)
    monkeypatch.setattr(cv2, "VideoCapture", factory)
    return RtspVideoSource(URL, reconnect_delay_seconds=0, **kwargs)


def test_reconnect_returns_bgr_and_releases(monkeypatch):
    frame = np.zeros((2, 3, 3), dtype=np.uint8)
    first = capture(frames=[(False, None)])
    second = capture(frames=[(True, frame)])
    video = source(monkeypatch, [first, second])
    video.open()
    assert video.read_frame() is frame
    first.release.assert_called_once()
    video.close()
    video.close()
    second.release.assert_called_once()
    assert first.open.call_args.args[1] == cv2.CAP_FFMPEG
    assert cv2.CAP_PROP_READ_TIMEOUT_MSEC in first.open.call_args.args[2]


def test_initial_retry_and_idempotent_open(monkeypatch):
    bad, good = capture(False), capture()
    video = source(monkeypatch, [bad, good])
    video.open()
    video.open()
    bad.release.assert_called_once()
    good.open.assert_called_once()
    video.close()


@pytest.mark.parametrize('during_read', [False, True])
def test_exhaustion_releases_and_hides_credentials(monkeypatch, during_read):
    caps = [capture(during_read, [(False, None)]), capture(False), capture(False)]
    video = source(monkeypatch, caps, reconnect_attempts=2)
    with pytest.raises(ConnectionError) as error:
        video.open()
        if during_read:
            video.read_frame()
    assert 'secret' not in str(error.value)
    for cap in caps:
        cap.release.assert_called_once()


def test_native_read_error_recovers(monkeypatch):
    frame = np.ones((2, 2, 3), dtype=np.uint8)
    bad, good = capture(), capture(frames=[(True, frame)])
    bad.read.side_effect = cv2.error('native failure')
    video = source(monkeypatch, [bad, good])
    video.open()
    assert video.read_frame() is frame
    video.close()


def test_env(monkeypatch):
    monkeypatch.setenv('VISION_CORE_RTSP_URL', URL)
    monkeypatch.setenv('VISION_CORE_RECONNECT_ATTEMPTS', '0')
    assert RtspVideoSource.from_env()._attempts == 0
    monkeypatch.setenv('VISION_CORE_READ_TIMEOUT_MS', '-1')
    with pytest.raises(ValueError):
        RtspVideoSource.from_env()
    monkeypatch.delenv('VISION_CORE_RTSP_URL')
    with pytest.raises(ValueError):
        RtspVideoSource.from_env()


def test_read_requires_open():
    with pytest.raises(RuntimeError):
        RtspVideoSource(URL).read_frame()
