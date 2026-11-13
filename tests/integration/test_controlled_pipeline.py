"""Recorded synthetic frames, scripted YOLO outputs, real tracker/ReID/zones."""
from types import SimpleNamespace
from unittest.mock import Mock
import sys
import cv2
import numpy as np
import pytest

from application.vision_core_app import VisionCoreApp
from domain.entities import Polygon
from infrastructure.detection.yolo_detector_manager import YoloDetectorManager
from infrastructure.reid.memory_reid import InMemoryReID
from infrastructure.door.polygon_door_analytics import PolygonDoorAnalytics
from infrastructure.video.file_video_source import FileVideoSource
from infrastructure.video.rtsp_video_source import RtspVideoSource
from scripts.pipeline_tools.limited_source import LimitedSource


def scene(monkeypatch, count):
    # Three stable observations at each endpoint; short full occlusion in the middle.
    positions = [10]*3 + list(range(12, 64, 2)) + [62]*3 + [None]*3 + [62]*3 + list(range(60, 8, -2)) + [10]*3
    outputs = []
    for x in positions:
        boxes = [] if x is None else [SimpleNamespace(
            cls=np.array([0]), conf=np.array([.9]),
            xyxy=np.array([[x, 5+35*i, x+20, 30+35*i]])) for i in range(count)]
        outputs.append(SimpleNamespace(boxes=boxes))
    model = Mock()
    model.predict.side_effect = [[output] for output in outputs]
    monkeypatch.setitem(sys.modules, 'ultralytics', SimpleNamespace(YOLO=lambda path: model))
    return len(outputs), YoloDetectorManager()


def analytics():
    return PolygonDoorAnalytics(
        Polygon('out', ((0,0),(50,0),(50,80),(0,80))),
        Polygon('in', ((50,0),(100,0),(100,80),(50,80))))


@pytest.mark.parametrize('people', [1, 2])
def test_recorded_controlled_entries_exits_and_occlusion(tmp_path, monkeypatch, people):
    frames, detector = scene(monkeypatch, people)
    path = tmp_path / 'controlled.avi'
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'MJPG'), 10, (100,80))
    assert writer.isOpened()
    for _ in range(frames):
        writer.write(np.zeros((80,100,3), dtype=np.uint8))
    writer.release()
    source = FileVideoSource(path)
    events = []
    app = VisionCoreApp(source, detector, InMemoryReID(), analytics(),
                        lambda crop: np.array([1.,0.]), events.append)
    app.run()
    assert source._cap is None
    assert [e.event for e in events].count('PERSON_ENTERED') == people
    assert [e.event for e in events].count('PERSON_EXITED') == people
    entered = {e.person_id for e in events if e.event == 'PERSON_ENTERED'}
    exited = {e.person_id for e in events if e.event == 'PERSON_EXITED'}
    assert entered == exited and len(entered) == people


@pytest.mark.parametrize('recover', [True, False])
def test_pipeline_rtsp_outage(monkeypatch, recover):
    frames, detector = scene(monkeypatch, 1)
    frame = np.zeros((80,100,3), dtype=np.uint8)
    first, second = Mock(), Mock()
    first.read.side_effect = [(True,frame)]*3 + [(False,None)]
    second.open.return_value = recover
    second.read.return_value = (True,frame)
    monkeypatch.setattr(cv2, 'VideoCapture', Mock(side_effect=[first,second]))
    rtsp = RtspVideoSource('rtsp://test:8554/room', reconnect_attempts=1, reconnect_delay_seconds=0)
    source = LimitedSource(rtsp, frames)
    events = []
    app = VisionCoreApp(source, detector, InMemoryReID(), analytics(),
                        lambda crop: np.array([1.,0.]), events.append)
    if recover:
        app.run()
        assert rtsp.reconnections == 1
        assert [e.event for e in events] == ['PERSON_ENTERED','PERSON_EXITED']
    else:
        with pytest.raises(ConnectionError):
            app.run()
    first.release.assert_called_once()
    second.release.assert_called_once()
