import json
import logging
import threading
from unittest.mock import Mock
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from vision_core.core.telemetry.health import HealthStatus
from vision_core.core.telemetry.metrics import ObservabilityMetrics
from vision_core.core.telemetry.redacted_text_formatter import RedactedTextFormatter
from vision_core.core.telemetry.structured_logging import StructuredJsonFormatter, configure_structured_logging
from vision_core.features.monitor.infrastructure.http.server import make_server
from vision_core.features.monitor.infrastructure.runtime import MonitorRuntime
from vision_core.features.monitor.infrastructure.state import MonitorState
from vision_core.features.pipeline.application.use_cases.run_pipeline import RunPipeline


def test_json_log_schema_and_secret_redaction():
    formatter = StructuredJsonFormatter("camera-a")
    record = logging.LogRecord(
        "vision_core",
        logging.ERROR,
        __file__,
        1,
        "Camera failed rtsp://user:password@camera.local/live",
        (),
        None,
    )
    record.event_id = "camera-a-123"
    record.person_id = "person-9"
    record.duration_ms = 42.5
    record.error_code = "ConnectionError"

    payload = json.loads(formatter.format(record))
    assert set(
        {
            "timestamp",
            "level",
            "service",
            "camera_id",
            "event_id",
            "person_id",
            "duration_ms",
            "error_code",
        }
    ).issubset(payload)
    assert payload["level"] == "ERROR"
    assert payload["camera_id"] == "camera-a"
    assert "password" not in payload["message"]


def test_metrics_counter_gauge_and_histogram():
    metrics = ObservabilityMetrics()
    metrics.increment("vision_core_frames_processed_total", 3)
    metrics.set_gauge("vision_core_fps", 24.5)
    metrics.observe("vision_core_frame_processing_duration_ms", 12)
    metrics.observe("vision_core_frame_processing_duration_ms", 18)

    payload = metrics.snapshot()
    assert payload["counters"]["vision_core_frames_processed_total"] == 3
    assert payload["gauges"]["vision_core_fps"] == 24.5
    assert payload["histograms"]["vision_core_frame_processing_duration_ms"]["count"] == 2
    assert payload["histograms"]["vision_core_frame_processing_duration_ms"]["avg"] == 15


def test_metrics_keep_legacy_keys_and_add_camera_labels():
    metrics = ObservabilityMetrics()
    metrics.increment("vision_core_frames_processed_total", 2, camera_id="camera-g0")
    metrics.set_gauge("vision_core_fps", 12.5, camera_id="camera-g0")
    metrics.observe("vision_core_inference_latency_ms", 8, camera_id="camera-g0")
    metrics.increment("vision_core_errors_total", camera_id="default")

    payload = metrics.snapshot()
    assert payload["counters"]["vision_core_frames_processed_total"] == 2
    assert payload["counters"]["vision_core_frames_processed_total{camera_id=camera-g0}"] == 2
    assert payload["gauges"]["vision_core_fps"] == 12.5
    assert payload["gauges"]["vision_core_fps{camera_id=camera-g0}"] == 12.5
    assert payload["histograms"]["vision_core_inference_latency_ms"]["count"] == 1
    assert payload["histograms"]["vision_core_inference_latency_ms{camera_id=camera-g0}"]["avg"] == 8
    assert "vision_core_errors_total{camera_id=default}" not in payload["counters"]


def test_metrics_camera_label_is_sanitized():
    metrics = ObservabilityMetrics()
    metrics.increment("vision_core_frames_processed_total", camera_id="camera/1\nregion")

    payload = metrics.snapshot()
    assert "vision_core_frames_processed_total{camera_id=camera_1_region}" in payload["counters"]


def test_monitor_state_publishes_camera_labelled_metrics():
    metrics = ObservabilityMetrics()
    state = MonitorState(metrics=metrics, camera_id="camera-g0")
    state.publish(b"jpeg", [], 2, dropped=5, queue_size=1)

    payload = metrics.snapshot()
    assert payload["counters"]["vision_core_frames_discarded_total{camera_id=camera-g0}"] == 5
    assert payload["gauges"]["vision_core_queue_size{camera_id=camera-g0}"] == 1
    assert "vision_core_frames_discarded_total{camera_id=camera-g0}" in payload["counters"]
    assert "vision_core_frames_discarded_total" in payload["counters"]


def test_readiness_reports_individual_checks():
    health = HealthStatus(minimum_free_disk_mb=0)
    health.set_ready(config_valid=True, model_loaded=True, source_connected=False)
    payload = health.snapshot()
    assert payload["ready"] is False
    assert payload["checks"]["configuration"] is True
    assert payload["checks"]["model"] is True
    assert payload["checks"]["video_source"] is False
    assert payload["checks"]["disk"] is True


def test_text_log_redacts_credentials():
    formatter = RedactedTextFormatter("%(levelname)s %(message)s")
    record = logging.LogRecord(
        "vision_core",
        logging.ERROR,
        __file__,
        1,
        "Camera failed rtsp://user:password@camera.local/live",
        (),
        None,
    )
    output = formatter.format(record)
    assert "password" not in output
    assert "rtsp://user:***@camera.local/live" in output


def test_configure_logging_closes_previous_handlers():
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    stale = Mock(spec=logging.StreamHandler)
    try:
        root.handlers = [stale]
        configure_structured_logging("INFO", False, "camera-a")
        assert root.handlers and stale not in root.handlers
        stale.close.assert_called_once_with()
    finally:
        for handler in list(root.handlers):
            root.removeHandler(handler)
            handler.close()
        root.handlers = original_handlers
        root.setLevel(original_level)


def test_pipeline_failure_is_counted_once():
    video = Mock()
    video.open.side_effect = ConnectionError("camera down")
    metrics = ObservabilityMetrics()
    state = MonitorState(metrics=metrics)
    pipeline = RunPipeline(video, Mock(), Mock(), Mock(), Mock(), Mock())
    pipeline.set_observability(metrics)

    runtime = MonitorRuntime(pipeline.run, state)
    runtime.start()
    runtime.join(timeout=2)

    assert state.status == "error"
    assert metrics.snapshot()["counters"]["vision_core_errors_total"] == 1


def test_discarded_frames_are_counted_as_delta_and_queue_size_is_reported():
    metrics = ObservabilityMetrics()
    state = MonitorState(metrics=metrics)
    state.publish(b"jpeg", [], 1, dropped=3000, queue_size=1)
    state.publish(b"jpeg", [], 1, dropped=3000, queue_size=1)
    payload = metrics.snapshot()
    assert payload["counters"]["vision_core_frames_discarded_total"] == 3000
    assert payload["gauges"]["vision_core_queue_size"] == 1


def test_histogram_summary_keeps_cumulative_count_and_sum():
    metrics = ObservabilityMetrics()
    for _ in range(1200):
        metrics.observe("vision_core_inference_latency_ms", 2)
    histogram = metrics.snapshot()["histograms"]["vision_core_inference_latency_ms"]
    assert histogram["count"] == 1200
    assert histogram["sum"] == 2400
    assert histogram["avg"] == 2


def test_stale_stream_marks_video_source_not_ready(tmp_path):
    health = HealthStatus(minimum_free_disk_mb=0, disk_path=str(tmp_path))
    health.set_ready(config_valid=True, model_loaded=True, source_connected=True)
    state = MonitorState(health=health)
    state.publish(b"jpeg", [], 1)
    assert health.snapshot()["ready"] is True

    with state.lock:
        state._updated_monotonic -= 6
    assert state.snapshot()["status"] == "stale"
    readiness = health.snapshot()
    assert readiness["ready"] is False
    assert readiness["checks"]["video_source"] is False


def test_ready_endpoint_follows_actual_stream_state(tmp_path):
    health = HealthStatus(minimum_free_disk_mb=0, disk_path=str(tmp_path))
    health.set_ready(config_valid=True, model_loaded=True)
    state = MonitorState(health=health)
    server = make_server("127.0.0.1", 0, state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    try:
        with pytest.raises(HTTPError) as error:
            urlopen(f"{base_url}/ready")
        assert error.value.code == 503

        state.publish(b"jpeg", [], 1)
        with urlopen(f"{base_url}/ready") as response:
            assert response.status == 200

        with state.lock:
            state._updated_monotonic -= 6
        with pytest.raises(HTTPError) as error:
            urlopen(f"{base_url}/ready")
        assert error.value.code == 503
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_metrics_endpoint_exposes_camera_labelled_and_legacy_keys():
    state = MonitorState(camera_id="camera-http")
    state.publish(b"jpeg", [], 1, dropped=1, queue_size=0)
    server = make_server("127.0.0.1", 0, state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    try:
        with urlopen(f"{base_url}/metrics") as response:
            payload = json.load(response)
        assert payload["counters"]["vision_core_frames_processed_total"] == 1
        assert payload["counters"]["vision_core_frames_processed_total{camera_id=camera-http}"] == 1
        assert payload["gauges"]["vision_core_queue_size{camera_id=camera-http}"] == 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
