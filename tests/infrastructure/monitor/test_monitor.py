import threading
import time

import cv2
import numpy as np
import pytest

from application.vision_core_app import VisionCoreApp
from domain.entities import BBox, Event, ResolvedTrack
from infrastructure.door.polygon_door_analytics import PolygonDoorAnalytics
from infrastructure.door.zone_config import load_zones
from infrastructure.monitor.server import MonitorState
from infrastructure.video.latest_frame_source import LatestFrameSource
from tests.application.test_vision_core_app import FakeVideoSource, FakeDetector, FakeReID, FakeDoor


def test_observer_receives_current_resolved_detections_and_empty_frames():
    snapshots = []
    detector = FakeDetector(lost_ids_per_call=[[], []])
    frame = np.zeros((20, 20, 3), dtype=np.uint8)
    app = VisionCoreApp(FakeVideoSource([]), detector, FakeReID(), FakeDoor(),
        lambda crop: np.ones(4), lambda event: None,
        on_frame=lambda image, tracks, ms: snapshots.append((image, tracks, ms)))
    app._process_frame(frame)
    detector._detections_per_frame = [[]]
    app._process_frame(frame)
    assert snapshots[0][0] is frame
    assert snapshots[0][1][0].person_id == 'person-1'
    assert snapshots[0][1][0].track_id == 1
    assert snapshots[0][2] >= 0
    # Retained tracker IDs must not appear as people visible in this frame.
    assert snapshots[1][1] == ()


def test_monitor_annotates_without_mutating_input_and_flags_stale(monkeypatch):
    state = MonitorState(demo=True)
    zones = load_zones('config/zones.example.json')
    analytics = PolygonDoorAnalytics(zones.exterior, zones.interior, zones.door)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    person = ResolvedTrack('person-a', BBox(10, 30, 110, 200), .9, 1)
    analytics.update(person.person_id, person.bbox.center)
    state.publish(frame, [person], 22, zones, analytics, dropped=7)
    assert not frame.any()
    assert cv2.imdecode(np.frombuffer(state.jpeg, np.uint8), cv2.IMREAD_COLOR).any()
    report = state.snapshot()
    assert report['people'][0]['zone'] == 'exterior'
    assert report['people'][0]['track_id'] == 1
    assert report['dropped_frames'] == 7
    monkeypatch.setattr(time, 'time', lambda: state.updated + 6)
    assert state.snapshot()['status'] == 'stale'
    assert state.snapshot()['people'] == []
    state.set_status('error', 'ConnectionError')
    assert state.snapshot()['status'] == 'error'


def test_event_buffer_bounded_but_counters_preserved():
    state = MonitorState()
    for i in range(150):
        state.event(Event('PERSON_ENTERED', str(i)))
    report = state.snapshot()
    assert len(report['events']) == 100
    assert report['events'][0]['person_id'] == '149'
    assert report['counts']['PERSON_ENTERED'] == 150


def test_capture_keeps_latest_frame_and_closes_on_owner_thread():
    closed = threading.Event()
    owner = []
    class Source(FakeVideoSource):
        def close(self):
            owner.append(threading.get_ident())
            closed.set()
    source = LatestFrameSource(Source([np.full((2, 2, 3), i, np.uint8) for i in range(5)]))
    source.open()
    assert closed.wait(2)
    assert np.all(source.read_frame() == 4)
    assert source.dropped_frames == 4
    assert source.read_frame() is None
    source.close()
    assert owner == [source._thread.ident]


def test_capture_failure_propagates_and_releases_source():
    closed = threading.Event()
    class Source:
        def open(self):
            raise ConnectionError('private URL')
        def close(self):
            closed.set()
    source = LatestFrameSource(Source())
    source.open()
    with pytest.raises(ConnectionError):
        source.read_frame()
    source.close()
    assert closed.is_set()
