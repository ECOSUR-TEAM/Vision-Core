from unittest.mock import Mock
import cv2
import numpy as np
import pytest
from infrastructure.video.frame_validation import validate_frame
from infrastructure.video.rtsp_video_source import RtspVideoSource
from infrastructure.video.check_stream import measure

FRAME = np.zeros((48, 64, 3), dtype=np.uint8)


@pytest.mark.parametrize('frame', [None, np.zeros((2, 2)), np.zeros((2, 2, 4), dtype=np.uint8), np.zeros((0, 2, 3), dtype=np.uint8), FRAME.astype(float)])
def test_bad_formats(frame):
    with pytest.raises(ValueError):
        validate_frame(frame)


def test_resolution_change():
    with pytest.raises(ValueError):
        validate_frame(FRAME, (100, 100))


def test_temporary_outage(monkeypatch):
    first, offline, recovered = Mock(), Mock(), Mock()
    first.read.return_value = (False, None)
    offline.open.return_value = False
    recovered.read.return_value = (True, FRAME)
    monkeypatch.setattr(cv2, 'VideoCapture', Mock(side_effect=[first, offline, recovered]))
    source = RtspVideoSource('rtsp://frigate:8554/entrada', delay=0)
    source.open()
    assert source.read_frame() is FRAME
    assert source.reconnections == 1
    source.close()
    source.close()
    for cap in (first, offline, recovered):
        cap.release.assert_called_once()


def test_permanent_outage(monkeypatch):
    cap = Mock()
    cap.open.return_value = False
    monkeypatch.setattr(cv2, 'VideoCapture', lambda: cap)
    source = RtspVideoSource('rtsp://frigate:8554/entrada', attempts=2, delay=0)
    with pytest.raises(ConnectionError):
        source.open()
    assert cap.release.call_count == 3


def test_frames_consumed_by_detector_contract():
    source = Mock(reconnections=0)
    source.read_frame.return_value = FRAME
    detector = Mock()
    detector.process.side_effect = lambda frame: validate_frame(frame)
    result = measure(source, 3, detector)
    assert detector.process.call_count == 3
    assert result['width'] == 64
    assert result['consumption_fps'] > 0
    assert result['end_to_end_latency_ms'] is None
    source.close.assert_called_once()


def test_detector_error_releases():
    source, detector = Mock(), Mock()
    source.read_frame.return_value = FRAME
    detector.process.side_effect = NotImplementedError
    with pytest.raises(NotImplementedError):
        measure(source, 1, detector)
    source.close.assert_called_once()
