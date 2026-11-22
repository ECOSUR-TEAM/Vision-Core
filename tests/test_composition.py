import ast
import threading
from pathlib import Path

import numpy as np
import pytest

import main as composition_root
from tests.fakes.fake_detector import FakeDetector
from tests.fakes.fake_door import FakeDoor
from tests.fakes.fake_reid import FakeReID
from tests.fakes.fake_video_source import FakeVideoSource
from vision_core.core.domain.event import Event
from vision_core.core.errors import ConfigurationError, VisionCoreError
from vision_core.features.pipeline.application.use_cases.run_pipeline import RunPipeline


def test_infrastructure_does_not_import_application():
    project_root = Path(__file__).resolve().parents[1]
    roots = (
        project_root / "src/vision_core/features",
        project_root / "src/vision_core/core/infrastructure/persistence",
    )
    legacy_application = ("application", "vision_core.application")
    for root in roots:
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.level == 0:
                    assert not (node.module or "").startswith(legacy_application), path
                elif isinstance(node, ast.Import):
                    assert all(not alias.name.startswith(legacy_application) for alias in node.names), path


def test_build_pipeline_accepts_injected_adapters():
    app = composition_root.build_pipeline(
        FakeVideoSource([]),
        FakeDetector(),
        FakeReID(),
        FakeDoor(),
        lambda crop: np.ones(4),
        lambda event: None,
    )
    assert isinstance(app, RunPipeline)


def test_build_monitor_state_uses_the_pipeline_serializer():
    state = composition_root.build_monitor_state()
    state.event(Event("PERSON_ENTERED", "person-1", metadata={"vec": np.zeros(2)}))
    assert state.snapshot()["events"][0]["metadata"] == {"vec": [0.0, 0.0]}


def test_expected_errors_keep_python_exception_compatibility():
    error = ConfigurationError("config inválida")

    assert str(error) == "config inválida"
    assert error.args == ("config inválida",)
    assert isinstance(error, ValueError)
    with pytest.raises(TypeError, match="at most one positional message"):
        VisionCoreError("primero", "segundo")


def test_monitor_main_uses_injected_state_and_runtime(monkeypatch):
    from vision_core.features.monitor.infrastructure import __main__ as monitor

    calls = {}

    class Server:
        def serve_forever(self, **kwargs):
            pass

        def server_close(self):
            calls["closed"] = True

        def shutdown(self):
            calls["shutdown"] = True

    class Runtime:
        failed = threading.Event()

        def start(self):
            calls["started"] = True

        def stop(self):
            calls["stopped"] = True

        def join(self, timeout=None):
            calls["joined"] = timeout

    def build_runtime(state, **kwargs):
        calls["state"] = state
        calls["kwargs"] = kwargs
        return Runtime()

    state = object()
    monkeypatch.setattr(monitor, "make_server", lambda *args: Server())
    monkeypatch.setattr(monitor.signal, "signal", lambda *args: None)
    monkeypatch.setattr("sys.argv", ["monitor", "--uncalibrated"])

    monitor.main(state=state, build_runtime=build_runtime)

    assert calls["state"] is state
    assert calls["kwargs"]["zones_file"] is None
    assert calls["started"] and calls["stopped"] and calls["closed"]


def test_monitor_main_no_render_forces_override(monkeypatch):
    from vision_core.features.monitor.infrastructure import __main__ as monitor

    calls = {}

    class Server:
        def serve_forever(self, **kwargs):
            pass

        def server_close(self):
            pass

        def shutdown(self):
            pass

    class Runtime:
        failed = threading.Event()

        def start(self):
            pass

        def stop(self):
            pass

        def join(self, timeout=None):
            pass

    def build_runtime(state, **kwargs):
        calls["kwargs"] = kwargs
        return Runtime()

    monkeypatch.setattr(monitor, "make_server", lambda *args: Server())
    monkeypatch.setattr(monitor.signal, "signal", lambda *args: None)
    monkeypatch.setattr("sys.argv", ["monitor", "--demo-zones", "--no-render"])

    monitor.main(state=object(), build_runtime=build_runtime)

    assert calls["kwargs"]["render_enabled"] is False
    assert Path(calls["kwargs"]["zones_file"]).as_posix().endswith("config/zones.example.json")
