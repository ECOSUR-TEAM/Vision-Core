import time

import numpy as np

import main as composition_root
from tests.fakes.fake_detector import FakeDetector
from tests.fakes.fake_door import FakeDoor
from tests.fakes.fake_monitor_source import FakeMonitorSource
from tests.fakes.fake_reid import FakeReID
from tests.fakes.fake_runtime_app import FakeRuntimeApp
from tests.fakes.fake_video_source import FakeVideoSource
from vision_core.infrastructure.reid.memory_reid import InMemoryReID
from vision_core.settings.persistence import PersistenceSettings
from vision_core.shared.domain.bbox import BBox


def test_monitor_runtime_persists_events_tracks_and_health(monkeypatch, tmp_path):
    settings = PersistenceSettings.from_env({"VISION_CORE_DB_PATH": str(tmp_path / "runtime.sqlite3")})
    persistence = composition_root.build_persistence(settings)
    state = composition_root.build_monitor_state()
    sources = []

    def build_video(**kwargs):
        source = FakeMonitorSource(object())
        sources.append(source)
        return source

    monkeypatch.setattr(composition_root, "build_video", build_video)
    monkeypatch.setattr(composition_root, "build_pipeline", lambda **kwargs: FakeRuntimeApp(**kwargs))
    monkeypatch.setattr(composition_root, "render_frame", lambda *args, **kwargs: (b"jpeg", []))

    runtime = composition_root.build_monitor_runtime(state, persistence=persistence, start_retention=False)
    runtime.start()
    runtime.join(timeout=2)
    runtime.stop()

    assert state.snapshot()["persistence"]["enabled"] is True
    monkeypatch.setattr(persistence, "health", lambda: {"enabled": True, "failures": 7})
    assert state.snapshot()["persistence"]["failures"] == 7
    assert sources and sources[0].closed
    assert len(persistence.events.list()) == 1
    assert len(persistence.tracks.list()) == 1
    sessions = persistence.sessions.list()
    assert len(sessions) == 1 and sessions[0][2] is not None
    assert len(persistence.metrics.list()) == 1

    persistence.close()
    reopened = composition_root.build_persistence(settings)
    assert len(reopened.events.list()) == 1
    assert len(reopened.tracks.list()) == 1
    reopened.close()


def test_build_reid_with_persistence_restores_gallery(tmp_path):
    settings = PersistenceSettings.from_env({"VISION_CORE_DB_PATH": str(tmp_path / "reid.sqlite3")})
    persistence = composition_root.build_persistence(settings)
    now = time.time()
    assert persistence.save_identity("person-restored", [1.0, 0.0, 0.0, 0.0], now) is True

    memory = composition_root.build_reid_with_persistence(InMemoryReID(), persistence)
    assert memory.resolve(1, [1.0, 0.0, 0.0, 0.0], BBox(0, 0, 1, 1)) == "person-restored"
    assert len(persistence.identities.list_active(since=0.0)) == 1
    persistence.close()


def test_build_pipeline_uses_persisting_reid_memory(tmp_path):
    settings = PersistenceSettings.from_env({"VISION_CORE_DB_PATH": str(tmp_path / "pipeline.sqlite3")})
    persistence = composition_root.build_persistence(settings)
    memory = composition_root.build_reid_with_persistence(FakeReID(), persistence)
    app = composition_root.build_pipeline(
        FakeVideoSource([]),
        FakeDetector(),
        memory,
        FakeDoor(),
        lambda crop: np.ones(4),
        lambda event: None,
    )
    assert app._reid is memory
    persistence.close()


def test_monitor_runtime_can_disable_persistence(monkeypatch):
    state = composition_root.build_monitor_state()
    settings = PersistenceSettings.from_env({})
    persistence = composition_root.build_persistence(settings)

    monkeypatch.setattr(composition_root, "build_video", lambda **kwargs: FakeMonitorSource(object()))
    monkeypatch.setattr(composition_root, "build_pipeline", lambda **kwargs: FakeRuntimeApp(**kwargs))
    monkeypatch.setattr(composition_root, "render_frame", lambda *args, **kwargs: (b"jpeg", []))

    runtime = composition_root.build_monitor_runtime(state, persistence=persistence)
    runtime.start()
    runtime.join(timeout=2)
    runtime.stop()

    assert state.snapshot()["persistence"]["enabled"] is False
    assert persistence.health()["failures"] == 0
