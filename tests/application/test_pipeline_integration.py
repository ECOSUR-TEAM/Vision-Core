from unittest.mock import Mock
import ast
from pathlib import Path

import numpy as np
import pytest

from application.vision_core_app import VisionCoreApp
from domain.entities import BBox, Detection, Polygon
from infrastructure.reid.memory_reid import InMemoryReID
from infrastructure.door.polygon_door_analytics import PolygonDoorAnalytics


FRAME = np.zeros((40, 40, 3), dtype=np.uint8)


def components():
    source, detector, reid, door, embedder, sink = [Mock() for _ in range(6)]
    source.read_frame.side_effect = [FRAME, None]
    detector.process.return_value = [Detection(BBox(1, 1, 5, 5), 0, .9, 1)]
    detector.pop_lost_track_ids.return_value = []
    embedder.return_value = np.array([1., 0.])
    reid.resolve.return_value = 'person'
    return source, detector, reid, door, embedder, sink


@pytest.mark.parametrize('stage', ['open', 'read', 'detect', 'lost', 'embed', 'reid', 'door', 'event'])
def test_stage_failure_closes_and_propagates(stage):
    args = components()
    source, detector, reid, door, embedder, sink = args
    target = dict(open=source.open, read=source.read_frame, detect=detector.process,
                  lost=detector.pop_lost_track_ids, embed=embedder,
                  reid=reid.resolve, door=door.update, event=sink)[stage]
    error = RuntimeError('stage failure')
    target.side_effect = error
    with pytest.raises(RuntimeError) as caught:
        VisionCoreApp(*args).run()
    assert caught.value is error
    source.close.assert_called_once()


def test_cleanup_failure_preserves_original_error():
    args = components()
    error = ConnectionError('read failure')
    args[0].read_frame.side_effect = error
    args[0].close.side_effect = RuntimeError('close failure')
    with pytest.raises(ConnectionError) as caught:
        VisionCoreApp(*args).run()
    assert caught.value is error


def test_interrupt_closes():
    args = components()
    args[0].read_frame.side_effect = KeyboardInterrupt
    with pytest.raises(KeyboardInterrupt):
        VisionCoreApp(*args).run()
    args[0].close.assert_called_once()


def test_eof_closes_without_detection():
    args = components()
    args[0].read_frame.side_effect = [None]
    VisionCoreApp(*args).run()
    args[0].close.assert_called_once()
    args[1].process.assert_not_called()


def test_fractional_crop_has_pixels():
    args = components()
    args[1].process.return_value = [Detection(BBox(1.1, 2.1, 1.9, 2.9), 0, .9, 1)]
    VisionCoreApp(*args).run()
    assert args[4].call_args.args[0].shape == (1, 1, 3)
    args[3].update.assert_called_once_with('person', (1.5, 2.5))


def test_video_to_real_reid_and_zones_with_reappearance():
    source, detector, _, _, embedder, _ = components()
    source.read_frame.side_effect = [FRAME, FRAME, FRAME, None]
    detector.process.side_effect = [
        [Detection(BBox(2, 2, 8, 8), 0, .9, 1)], [],
        [Detection(BBox(22, 2, 28, 8), 0, .9, 2)],
    ]
    detector.pop_lost_track_ids.side_effect = [[], [], [1]]
    reid = InMemoryReID()
    door = PolygonDoorAnalytics(
        Polygon('out', ((0, 0), (20, 0), (20, 40), (0, 40))),
        Polygon('in', ((20, 0), (40, 0), (40, 40), (20, 40))),
    )
    events = []
    app = VisionCoreApp(source, detector, reid, door, embedder, events.append)
    app.run()
    assert len(events) == 1
    assert events[0].event == 'PERSON_ENTERED'
    assert events[0].person_id == reid._active[2]
    assert set(app._person_by_track) == set(app._last_embedding_by_track) == {2}
    assert set(reid._active) == {2}
    source.close.assert_called_once()


def test_application_has_no_infrastructure_imports():
    tree = ast.parse(Path('application/vision_core_app.py').read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert not (node.module or '').startswith('infrastructure')
        elif isinstance(node, ast.Import):
            assert all(not item.name.startswith('infrastructure') for item in node.names)


def test_close_failure_on_normal_completion_is_reported():
    args = components()
    args[0].close.side_effect = RuntimeError('close failure')
    with pytest.raises(RuntimeError, match='close failure'):
        VisionCoreApp(*args).run()
    args[0].close.assert_called_once()


@pytest.mark.parametrize('bbox', [BBox(2, 2, 1, 3), BBox(50, 50, 60, 60),
                                  BBox(float('nan'), 1, 3, 4)])
def test_invalid_detector_box_stops_before_embedding(bbox):
    args = components()
    args[1].process.return_value = [Detection(bbox, 0, .9, 1)]
    with pytest.raises(ValueError):
        VisionCoreApp(*args).run()
    args[4].assert_not_called()
    args[0].close.assert_called_once()
