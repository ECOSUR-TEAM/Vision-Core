import numpy as np

from tests.fakes.fake_detector import FakeDetector
from tests.fakes.fake_door import FakeDoor
from tests.fakes.fake_monitor_source import FakeMonitorSource
from tests.fakes.fake_reid import FakeReID
from tests.fakes.fake_runtime_app import FakeRuntimeApp
from tests.fakes.fake_video_source import FakeVideoSource
from vision_core import composition
from vision_core.composition import (
    build_monitor_runtime,
    build_monitor_state,
    build_persistence,
    build_vision_core_app,
)
from vision_core.infrastructure.persistence.persisting_reid_memory import PersistingReIDMemory
from vision_core.settings.persistence import PersistenceSettings
from vision_core.shared.domain.bbox import BBox


def test_monitor_runtime_persists_events_tracks_and_health(monkeypatch, tmp_path):
    settings = PersistenceSettings.from_env({"VISION_CORE_DB_PATH": str(tmp_path / "runtime.sqlite3")})
    persistence = build_persistence(settings)
    state = build_monitor_state()
    sources = []

    monkeypatch.setattr(composition, "build_video_source", lambda: object())
    monkeypatch.setattr(composition, "build_door_analytics", lambda zones: object())
    monkeypatch.setattr(composition, "build_vision_core_app", lambda **kwargs: FakeRuntimeApp(**kwargs))
    monkeypatch.setattr(
        "vision_core.infrastructure.monitor.renderer.render_frame",
        lambda *args, **kwargs: (b"jpeg", []),
    )

    def build_source(inner):
        source = FakeMonitorSource(inner)
        sources.append(source)
        return source

    monkeypatch.setattr("vision_core.infrastructure.video.latest_frame_source.LatestFrameSource", build_source)

    runtime = build_monitor_runtime(state, persistence=persistence, start_retention=False)
    runtime.start()
    runtime.join(timeout=2)
    runtime.stop()

    assert state.snapshot()["persistence"]["enabled"] is True
    assert sources and sources[0].closed
    assert len(persistence.events.list()) == 1
    assert len(persistence.tracks.list()) == 1
    sessions = persistence.sessions.list()
    assert len(sessions) == 1 and sessions[0][2] is not None
    assert len(persistence.metrics.list()) == 1

    persistence.close()
    reopened = build_persistence(settings)
    assert len(reopened.events.list()) == 1
    assert len(reopened.tracks.list()) == 1
    reopened.close()


def test_build_vision_core_app_persists_reid_identities(tmp_path):
    settings = PersistenceSettings.from_env({"VISION_CORE_DB_PATH": str(tmp_path / "reid.sqlite3")})
    persistence = build_persistence(settings)

    app = build_vision_core_app(
        video_source=FakeVideoSource([]),
        door_analytics=FakeDoor(),
        on_event=lambda event: None,
        detector=FakeDetector(),
        reid_memory=FakeReID(),
        embedder=lambda crop: np.ones(4),
        persistence=persistence,
    )

    assert isinstance(app._reid, PersistingReIDMemory)
    app._reid.resolve(1, [0.1, 0.2, 0.3, 0.4], BBox(0, 0, 1, 1))
    assert len(persistence.identities.list_active(since=0.0)) == 1
    persistence.close()


def test_monitor_runtime_can_disable_persistence(monkeypatch):
    state = build_monitor_state()
    settings = PersistenceSettings.from_env({})
    persistence = build_persistence(settings)

    monkeypatch.setattr(composition, "build_video_source", lambda: object())
    monkeypatch.setattr(composition, "build_door_analytics", lambda zones: object())
    monkeypatch.setattr(composition, "build_vision_core_app", lambda **kwargs: FakeRuntimeApp(**kwargs))
    monkeypatch.setattr(
        "vision_core.infrastructure.monitor.renderer.render_frame",
        lambda *args, **kwargs: (b"jpeg", []),
    )
    monkeypatch.setattr(
        "vision_core.infrastructure.video.latest_frame_source.LatestFrameSource",
        lambda inner: FakeMonitorSource(inner),
    )

    runtime = build_monitor_runtime(state, persistence=persistence)
    runtime.start()
    runtime.join(timeout=2)
    runtime.stop()

    assert state.snapshot()["persistence"]["enabled"] is False
    assert persistence.health()["failures"] == 0
