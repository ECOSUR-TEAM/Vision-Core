import ast
import threading
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import main as composition_root
from tests.fakes.fake_detector import FakeDetector
from tests.fakes.fake_door import FakeDoor
from tests.fakes.fake_monitor_source import FakeMonitorSource
from tests.fakes.fake_reid import FakeReID
from tests.fakes.fake_runtime_app import FakeRuntimeApp
from tests.fakes.fake_video_source import FakeVideoSource
from vision_core.core.config import Settings
from vision_core.core.config.persistence import PersistenceSettings
from vision_core.core.domain.event import Event
from vision_core.core.errors import ConfigurationError, VisionCoreError
from vision_core.core.telemetry.metrics import ObservabilityMetrics
from vision_core.features.monitor.infrastructure.state import MonitorState
from vision_core.features.pipeline.application.use_cases.run_pipeline import RunPipeline

PACKAGE_NAME = "vision_core"


def test_infrastructure_does_not_import_application():
    project_root = Path(__file__).resolve().parents[1]
    roots = (
        project_root / "src/vision_core/features",
        project_root / "src/vision_core/core/infrastructure/persistence",
    )
    legacy_application = ("application", f"{PACKAGE_NAME}.application")
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


def _camera_quality_settings(tmp_path, sample_every_n_frames=3, camera_id="default"):
    return Settings.from_env(
        {
            "VISION_CORE_DB_PATH": str(tmp_path / "camera-quality.sqlite3"),
            "VISION_CORE_CAMERA_ID": camera_id,
            "VISION_CORE_CAMERA_QUALITY_ENABLED": "1",
            "VISION_CORE_CAMERA_QUALITY_SAMPLE_EVERY_N_FRAMES": str(sample_every_n_frames),
        },
        validate_startup=False,
    )


def _patch_pipeline_dependencies(monkeypatch, tmp_path):
    persistence = composition_root.build_persistence(
        PersistenceSettings.from_env({"VISION_CORE_DB_PATH": str(tmp_path / "camera-quality.sqlite3")})
    )
    models = SimpleNamespace(as_health_metadata=lambda: {}, detection=None, embedding=None)
    monkeypatch.setattr(composition_root, "build_persistence", lambda *args, **kwargs: persistence)
    monkeypatch.setattr(composition_root, "resolve_active_models", lambda settings: models)
    monkeypatch.setattr(composition_root, "build_video", lambda **kwargs: FakeMonitorSource(object()))
    monkeypatch.setattr(composition_root, "build_door", lambda **kwargs: SimpleNamespace(analytics=FakeDoor()))
    monkeypatch.setattr(composition_root, "build_detection", lambda **kwargs: SimpleNamespace(detector=FakeDetector()))
    monkeypatch.setattr(
        composition_root,
        "build_reid",
        lambda **kwargs: SimpleNamespace(
            memory=kwargs.get("memory") or FakeReID(),
            embedder=kwargs.get("embedder") or (lambda crop: np.ones(4)),
        ),
    )
    monkeypatch.setattr(composition_root, "build_pipeline", lambda **kwargs: FakeRuntimeApp(**kwargs))
    return persistence


def test_build_monitor_pipeline_wires_sampled_quality_thread(monkeypatch, tmp_path):
    persistence = _patch_pipeline_dependencies(monkeypatch, tmp_path)
    threads = []
    sampled_flags = []

    class QualityMonitor:
        def __init__(self, *args, **kwargs):
            return None

        def observe(self, _frame, *, sampled=False):
            sampled_flags.append(sampled)

    class QualityThread:
        def __init__(self, analyze, *, sample_every_n_frames=1, on_error=None):
            self.analyze = analyze
            self.sample_every_n_frames = sample_every_n_frames
            self.on_error = on_error
            self.started = False
            self.closed = False
            self.submitted = []
            threads.append(self)

        def start(self):
            self.started = True

        def submit(self, frame):
            self.submitted.append(frame.copy())

        def close(self, timeout=2):
            self.closed = True
            return True

    monkeypatch.setattr(composition_root, "CameraQualityMonitor", QualityMonitor)
    monkeypatch.setattr(composition_root, "QualityThread", QualityThread)
    state = MonitorState(metrics=ObservabilityMetrics())
    pipeline = composition_root.build_monitor_pipeline(
        state,
        settings=_camera_quality_settings(tmp_path),
        persistence=persistence,
        start_retention=False,
        render_enabled=False,
    )

    try:
        pipeline(lambda: False)
    finally:
        persistence.close()

    assert len(threads) == 1
    thread = threads[0]
    assert thread.started and thread.closed
    assert thread.sample_every_n_frames == 3
    assert len(thread.submitted) == 1
    thread.analyze(np.zeros((2, 2, 3), dtype=np.uint8))
    assert sampled_flags == [True]


def test_build_monitor_pipeline_records_quality_analysis_errors(monkeypatch, tmp_path):
    persistence = _patch_pipeline_dependencies(monkeypatch, tmp_path)

    class FailingQualityMonitor:
        def __init__(self, *args, **kwargs):
            return None

        def observe(self, _frame, *, sampled=False):
            raise RuntimeError("fallo de análisis")

    class ImmediateQualityThread:
        def __init__(self, analyze, *, sample_every_n_frames=1, on_error=None):
            self.analyze = analyze
            self.on_error = on_error
            self.started = False
            self.closed = False

        def start(self):
            self.started = True

        def submit(self, frame):
            try:
                self.analyze(frame)
            except Exception as error:
                if self.on_error is not None:
                    self.on_error(error)

        def close(self, timeout=2):
            self.closed = True
            return True

    monkeypatch.setattr(composition_root, "CameraQualityMonitor", FailingQualityMonitor)
    monkeypatch.setattr(composition_root, "QualityThread", ImmediateQualityThread)
    metrics = ObservabilityMetrics()
    state = MonitorState(camera_id="camera-1", metrics=metrics)
    pipeline = composition_root.build_monitor_pipeline(
        state,
        settings=_camera_quality_settings(tmp_path, camera_id="camera-1"),
        persistence=persistence,
        start_retention=False,
        render_enabled=False,
    )

    try:
        pipeline(lambda: False)
    finally:
        persistence.close()

    key = f"vision_core_camera_quality_errors_total{{camera_id={state.camera_id}}}"
    assert metrics.snapshot()["counters"][key] == 1
