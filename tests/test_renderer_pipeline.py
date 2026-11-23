"""Buffer de tamaño 1, renderer desacoplado y profiling del pipeline."""

import json
import threading
import time
from time import perf_counter

import numpy as np
import pytest

from vision_core.core.config.pipeline_config import PipelineConfig
from vision_core.core.telemetry.frame_profiler import STAGES, FrameProfiler
from vision_core.features.monitor.infrastructure.latest_frame_buffer import LatestFrameBuffer
from vision_core.features.monitor.infrastructure.renderer_thread import RendererThread


def test_latest_frame_buffer_discards_older_frames():
    buffer = LatestFrameBuffer()
    for index in range(3):
        buffer.publish(np.full((2, 2, 3), index, dtype=np.uint8))

    latest = buffer.take()
    assert np.all(latest == 2)
    # El consumidor solo lee el último: los dos primeros se descartaron.
    assert buffer.take() is None
    stats = buffer.stats()
    assert stats == {"published": 3, "dropped": 2, "queued": 0}


@pytest.mark.parametrize("maxsize", [0, 2, 3])
def test_latest_frame_buffer_only_allows_size_one(maxsize):
    with pytest.raises(ValueError, match="maxsize"):
        LatestFrameBuffer(maxsize=maxsize)


def test_slow_renderer_never_blocks_the_inference_producer():
    buffer = LatestFrameBuffer()
    rendering = threading.Event()
    rendered = []

    def slow_render(job):
        rendering.set()
        time.sleep(0.05)
        rendered.append(job)

    renderer = RendererThread(buffer, slow_render)
    warmup = np.full((2, 2, 3), 0, dtype=np.uint8)
    renderer.start()
    try:
        renderer.submit(warmup, (), label_for=lambda person_id: person_id)
        assert rendering.wait(1), "El renderer no consumió el primer frame"
        warmup[:] = 255  # el renderer debe conservar la copia, no esta referencia

        started = perf_counter()
        for index in range(100):
            frame = np.full((2, 2, 3), index, dtype=np.uint8)
            renderer.submit(frame, (), label_for=lambda person_id: person_id)
            frame[:] = 255
        elapsed = perf_counter() - started
        # Un renderer que bloqueara tardaría >= 5 s; el productor debe seguir
        # por encima de 100 FPS aunque el render esté dormido.
        assert elapsed < 1.0, f"El productor se bloqueó: {100 / elapsed:.1f} FPS"

        deadline = perf_counter() + 2
        while buffer.stats()["queued"] and perf_counter() < deadline:
            time.sleep(0.005)
        assert buffer.stats()["queued"] == 0
    finally:
        renderer.stop()
        renderer.join(timeout=2)

    assert not renderer.is_alive()
    assert buffer.stats()["published"] == 101
    assert buffer.stats()["dropped"] >= 99
    assert rendered[-1].frame[0, 0, 0] == 99
    assert rendered[0].frame[0, 0, 0] == 0  # copia: la mutación a 255 no se propagó


def test_renderer_stops_cleanly_and_propagates_errors():
    renderer = RendererThread(LatestFrameBuffer(), lambda job: None)
    assert not renderer.is_alive()
    renderer.start()
    assert renderer.is_alive()
    renderer.stop()
    renderer.join(timeout=2)
    assert not renderer.is_alive()
    assert renderer.ident not in {thread.ident for thread in threading.enumerate()}
    assert renderer.error is None

    flushing = RendererThread(LatestFrameBuffer(), lambda job: None)
    flushing.start()
    flushing.submit(np.zeros((2, 2, 3), dtype=np.uint8), ())
    assert flushing.drain(timeout=1)
    flushing.close(timeout=2)
    assert not flushing.is_alive()

    errors = []

    def failing_render(job):
        raise RuntimeError("fallo de JPEG")

    failing = RendererThread(
        LatestFrameBuffer(),
        failing_render,
        on_error=lambda error: errors.append(error),
    )
    failing.start()
    failing.submit(np.zeros((2, 2, 3), dtype=np.uint8), ())
    failing.join(timeout=2)
    assert not failing.is_alive()
    assert failing.failed.is_set()
    assert isinstance(failing.error, RuntimeError)
    assert errors == [failing.error]
    failing.stop()
    failing.join(timeout=2)
    assert failing.ident not in {thread.ident for thread in threading.enumerate()}


def test_renderer_failure_clears_pending_jobs():
    started = threading.Event()
    release = threading.Event()
    errors = []

    def failing_render(job):
        started.set()
        assert release.wait(1)
        raise RuntimeError("fallo de JPEG")

    buffer = LatestFrameBuffer()
    failing = RendererThread(buffer, failing_render, on_error=errors.append)
    failing.start()
    try:
        failing.submit(np.zeros((2, 2, 3), dtype=np.uint8), ())
        assert started.wait(1)
        failing.submit(np.ones((2, 2, 3), dtype=np.uint8), ())
        assert buffer.stats()["queued"] == 1
        release.set()
        failing.join(timeout=2)
        assert not failing.is_alive()
        assert buffer.stats()["queued"] == 0
        assert failing.drain(timeout=0.1)
        assert len(errors) == 1
    finally:
        release.set()
        failing.close(timeout=2)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("false", False), ("0", False), ("yes", True), ("on", True), ("TRUE", True)],
)
def test_pipeline_config_uses_the_shared_boolean_parser(monkeypatch, raw, expected):
    monkeypatch.setenv("VISION_CORE_RENDER_ENABLED", raw)
    config = PipelineConfig.from_env()
    assert config.render_enabled is expected


@pytest.mark.parametrize(
    "name",
    [
        "VISION_CORE_RENDER_ENABLED",
        "VISION_CORE_PROFILING_ENABLED",
        "VISION_CORE_EMBEDDING_BATCH_SIZE",
        "VISION_CORE_EMBEDDING_STRIDE",
    ],
)
def test_pipeline_config_rejects_invalid_environment_values(monkeypatch, name):
    monkeypatch.setenv(name, "quizas")
    with pytest.raises(ValueError, match=name):
        PipelineConfig.from_env()


def test_telemetry_exports_frame_profiler():
    from vision_core.core.telemetry import STAGES as PUBLIC_STAGES
    from vision_core.core.telemetry import FrameProfiler as PublicFrameProfiler

    assert PublicFrameProfiler is FrameProfiler
    assert PUBLIC_STAGES == STAGES


def test_frame_profiler_writes_percentiles_and_fps(tmp_path):
    profiler = FrameProfiler()
    for seconds in (0.01, 0.02, 0.03):
        profiler.record("detection", seconds)
    profiler.record_frame()

    summary = profiler.summary()
    assert summary["camera_id"] == "default"
    assert summary["frames"] == 1
    assert summary["fps"] > 0
    assert summary["stages"]["detection"]["p50_ms"] == pytest.approx(20.0)
    assert summary["stages"]["detection"]["p95_ms"] == pytest.approx(30.0)

    path = profiler.save(tmp_path / "profiling_results.json")
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["camera_id"] == "default"
    assert saved["frames"] == 1
    assert saved["stages"] == summary["stages"]


def test_frame_profiler_labels_results_with_camera_id(tmp_path):
    profiler = FrameProfiler(camera_id="camera-g0")
    profiler.record("detection", 0.01)
    profiler.record_frame()

    saved = json.loads(profiler.save(tmp_path / "profiling_results.json").read_text(encoding="utf-8"))
    assert saved["camera_id"] == "camera-g0"
    assert set(saved["stages"]) == set(STAGES)
