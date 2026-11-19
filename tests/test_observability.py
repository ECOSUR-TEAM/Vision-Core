import json
import logging

from vision_core.shared.observability.health import HealthStatus
from vision_core.shared.observability.metrics import ObservabilityMetrics
from vision_core.shared.observability.structured_logging import StructuredJsonFormatter


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


def test_readiness_reports_individual_checks():
    health = HealthStatus(minimum_free_disk_mb=0)
    health.set_ready(config_valid=True, model_loaded=True, source_connected=False)
    payload = health.snapshot()
    assert payload["ready"] is False
    assert payload["checks"]["configuration"] is True
    assert payload["checks"]["model"] is True
    assert payload["checks"]["video_source"] is False
    assert payload["checks"]["disk"] is True
