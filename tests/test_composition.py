import ast
import threading
from pathlib import Path

import numpy as np

from application.vision_core_app import VisionCoreApp
from composition import build_monitor_state, build_vision_core_app
from domain.entities import Event
from tests.fakes.fake_detector import FakeDetector
from tests.fakes.fake_door import FakeDoor
from tests.fakes.fake_reid import FakeReID
from tests.fakes.fake_video_source import FakeVideoSource


def test_infrastructure_does_not_import_application():
    root = Path(__file__).resolve().parents[1] / 'infrastructure'
    for path in root.rglob('*.py'):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or '').startswith('application'), path
            elif isinstance(node, ast.Import):
                assert all(not alias.name.startswith('application') for alias in node.names), path


def test_build_vision_core_app_accepts_injected_adapters():
    app = build_vision_core_app(
        video_source=FakeVideoSource([]),
        door_analytics=FakeDoor(),
        on_event=lambda event: None,
        detector=FakeDetector(),
        reid_memory=FakeReID(),
        embedder=lambda crop: np.ones(4),
    )
    assert isinstance(app, VisionCoreApp)


def test_build_monitor_state_uses_the_application_serializer():
    state = build_monitor_state()
    state.event(Event('PERSON_ENTERED', 'person-1', metadata={'vec': np.zeros(2)}))
    assert state.snapshot()['events'][0]['metadata'] == {'vec': [0.0, 0.0]}


def test_monitor_main_uses_injected_state_and_runtime(monkeypatch):
    from infrastructure.monitor import __main__ as monitor

    calls = {}

    class Server:
        def serve_forever(self, **kwargs):
            pass

        def server_close(self):
            calls['closed'] = True

        def shutdown(self):
            calls['shutdown'] = True

    class Runtime:
        failed = threading.Event()

        def start(self):
            calls['started'] = True

        def stop(self):
            calls['stopped'] = True

        def join(self, timeout=None):
            calls['joined'] = timeout

    def build_runtime(state, **kwargs):
        calls['state'] = state
        calls['kwargs'] = kwargs
        return Runtime()

    state = object()
    monkeypatch.setattr(monitor, 'make_server', lambda *args: Server())
    monkeypatch.setattr(monitor.signal, 'signal', lambda *args: None)
    monkeypatch.setattr('sys.argv', ['monitor', '--uncalibrated'])

    monitor.main(state=state, build_runtime=build_runtime)

    assert calls['state'] is state
    assert calls['kwargs']['zones_file'] is None
    assert calls['started'] and calls['stopped'] and calls['closed']
