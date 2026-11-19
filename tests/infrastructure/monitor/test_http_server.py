import json
import logging
import threading
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from vision_core.features.monitor.infrastructure.http import handler as handler_module
from vision_core.infrastructure.monitor.http_server import make_server
from vision_core.infrastructure.monitor.state import MonitorState
from vision_core.shared.domain.event import Event
from vision_core.shared.errors import (
    ConfigurationError,
    PipelineError,
    ReIDModelUnavailableError,
    VideoSourceError,
    codes,
)
from vision_core.shared.events import EVENT_SCHEMA_VERSION


@pytest.fixture
def monitor_server():
    state = MonitorState()
    server = make_server("127.0.0.1", 0, state)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        yield server, state, f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def _error_response(url):
    with pytest.raises(HTTPError) as error:
        urlopen(url)
    return error.value, json.load(error.value)


def test_versioned_http_routes_keep_monitor_contract(monitor_server):
    server, state, base_url = monitor_server
    state.publish(b"jpeg", [], 4)

    with urlopen(f"{base_url}/") as response:
        assert response.status == 200
        assert response.headers["Content-Type"] == "text/html; charset=utf-8"
        assert response.headers["X-Request-ID"]

    with urlopen(f"{base_url}/api/v1/state") as response:
        body = json.load(response)
        assert body["status"] == "running"
        assert body["frame"] == 1
        assert response.headers["X-Request-ID"]

    with urlopen(f"{base_url}/api/v1/frame") as response:
        assert response.status == 200
        assert response.read() == b"jpeg"
        assert response.headers["X-Frame-Sequence"] == "1"


def test_error_envelope_has_stable_shape_and_no_internal_details(monitor_server):
    _, _, base_url = monitor_server

    response, body = _error_response(f"{base_url}/api/v1/frame?after=-1")

    assert response.code == 400
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "request_id"}
    assert body["error"]["code"] == codes.VALIDATION_FAILED
    assert body["error"]["request_id"] == response.headers["X-Request-ID"]
    assert "Traceback" not in body["error"]["message"]

    response, body = _error_response(f"{base_url}/api/v1/unknown")

    assert response.code == 404
    assert body["error"]["code"] == codes.REQUEST_NOT_FOUND


def test_no_frame_uses_retryable_envelope(monitor_server):
    _, _, base_url = monitor_server

    response, body = _error_response(f"{base_url}/api/v1/frame")

    assert response.code == 503
    assert body["error"]["code"] == codes.VIDEO_FRAME_PENDING
    assert response.headers["Content-Type"] == "application/json"


def test_legacy_api_paths_are_deprecated_aliases(monitor_server):
    _, state, base_url = monitor_server
    state.publish(b"jpeg", [], 4)

    with urlopen(f"{base_url}/api/state") as response:
        assert response.status == 200
        assert response.headers["Deprecation"] == "true"
        assert json.load(response)["status"] == "running"


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (VideoSourceError("sin stream"), 503, codes.VIDEO_SOURCE_UNAVAILABLE),
        (ConfigurationError("config inválida"), 500, codes.CONFIGURATION_INVALID),
        (ReIDModelUnavailableError("sin CUDA"), 500, codes.REID_MODEL_UNAVAILABLE),
        (
            PipelineError("resolución distinta", code=codes.PIPELINE_CALIBRATION_MISMATCH),
            409,
            codes.PIPELINE_CALIBRATION_MISMATCH,
        ),
    ],
)
def test_application_errors_are_translated_at_the_http_boundary(error, status, code):
    class FailingState:
        def snapshot(self):
            raise error

    server = make_server("127.0.0.1", 0, FailingState())
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        response, body = _error_response(f"http://127.0.0.1:{server.server_port}/api/v1/state")
        assert response.code == status
        assert body["error"]["code"] == code
        assert body["error"]["message"] == error.message
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_http_errors_log_structured_details_and_traceback(caplog):
    error = ConfigurationError(
        "config inválida",
        context={"variable": "VISION_CORE_RTSP_URL", "password": "secreto"},
    )

    class FailingState:
        def snapshot(self):
            raise error

    server = make_server("127.0.0.1", 0, FailingState())
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        with caplog.at_level(logging.ERROR, logger=handler_module.__name__):
            _, body = _error_response(f"http://127.0.0.1:{server.server_port}/api/v1/state")
    finally:
        server.shutdown()
        server.server_close()
        thread.join()

    records = [record for record in caplog.records if record.name == handler_module.__name__]
    assert records
    record = records[-1]
    assert error.code in record.getMessage()
    assert error.message in record.getMessage()
    assert "secreto" not in record.getMessage()
    assert record.exc_info
    assert body["error"]["code"] == error.code
    assert "secreto" not in body["error"]["message"]


def test_serialized_events_declare_schema_version(monitor_server):
    _, state, base_url = monitor_server
    state.event(Event("PERSON_ENTERED", "p1", timestamp=1.0))

    with urlopen(f"{base_url}/api/v1/state") as response:
        events = json.load(response)["events"]

    assert events[0]["schema_version"] == EVENT_SCHEMA_VERSION
