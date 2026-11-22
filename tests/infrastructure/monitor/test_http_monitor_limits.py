"""ECM-91: límites de petición, concurrencia y respuestas 503 reintentables."""

import json
import socket
import threading
from http.client import HTTPConnection
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from vision_core.core.errors import codes
from vision_core.features.monitor.infrastructure.http.handler import MAX_HEADER_COUNT, MAX_REQUEST_LINE
from vision_core.features.monitor.infrastructure.http.server import make_server
from vision_core.features.monitor.infrastructure.state import MonitorState


@pytest.fixture
def monitor_server():
    state = MonitorState()
    server = make_server("127.0.0.1", 0, state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, state, f"http://127.0.0.1:{server.server_port}", ("127.0.0.1", server.server_port)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def _get(base_url, path):
    try:
        with urlopen(f"{base_url}{path}", timeout=5) as response:
            return response, response.read()
    except HTTPError as error:
        return error, error.read()


def _raw_request(address, request_bytes):
    with socket.create_connection(address, timeout=5) as sock:
        sock.sendall(request_bytes)
        raw = b""
        while chunk := sock.recv(65535):
            raw += chunk
    return raw


def test_oversized_request_line_returns_envelope(monitor_server):
    _, _, _, address = monitor_server

    raw = _raw_request(address, b"GET /" + b"a" * MAX_REQUEST_LINE + b" HTTP/1.0\r\n\r\n")

    assert raw.startswith(b"HTTP/1.0 414") or raw.startswith(b"HTTP/1.1 414")
    assert b'"code": "VALIDATION_FAILED"' in raw


def test_too_many_headers_return_envelope(monitor_server):
    _, _, _, address = monitor_server
    headers = b"".join(f"X-Test-{index}: 1\r\n".encode() for index in range(MAX_HEADER_COUNT + 5))

    raw = _raw_request(address, b"GET / HTTP/1.0\r\n" + headers + b"\r\n")

    assert raw.startswith(b"HTTP/1.0 431") or raw.startswith(b"HTTP/1.1 431")
    assert b'"code": "VALIDATION_FAILED"' in raw


def test_request_body_is_rejected(monitor_server):
    _, _, _, address = monitor_server

    connection = HTTPConnection(*address, timeout=5)
    connection.request("GET", "/api/v1/state", body=b"not-allowed")
    response = connection.getresponse()
    payload = json.loads(response.read())
    connection.close()

    assert response.status == 413
    assert payload["error"]["code"] == codes.VALIDATION_FAILED


@pytest.mark.parametrize(
    "header_lines",
    [
        b"Transfer-Encoding: chunked\r\n",
        b"Content-Length: 1\r\nContent-Length: 1\r\n",
        b"Content-Length: abc\r\n",
    ],
)
def test_invalid_body_headers_are_rejected(monitor_server, header_lines):
    _, _, _, address = monitor_server

    raw = _raw_request(address, b"GET /api/v1/state HTTP/1.0\r\n" + header_lines + b"\r\n")

    assert raw.startswith(b"HTTP/1.0 400") or raw.startswith(b"HTTP/1.1 400")
    assert b'"code": "VALIDATION_FAILED"' in raw


def test_connection_budget_returns_retryable_json_503(monitor_server):
    server, _, base_url, _ = monitor_server
    server._connections = threading.BoundedSemaphore(0)

    response, body = _get(base_url, "/api/v1/state")

    assert response.code == 503
    payload = json.loads(body)
    assert payload["error"]["code"] == codes.INTERNAL_ERROR
    assert payload["error"]["request_id"] == response.headers["X-Request-ID"]
    assert response.headers["Retry-After"] == "1"
    assert server.limits_metrics.snapshot()["concurrency"] >= 1


def test_long_poll_budget_returns_retryable_json_503(monitor_server):
    server, _, base_url, _ = monitor_server
    server.long_poll_slots = threading.BoundedSemaphore(0)

    response, body = _get(base_url, "/api/v1/frame?after=0")

    assert response.code == 503
    assert json.loads(body)["error"]["code"] == codes.INTERNAL_ERROR
    assert response.headers["Retry-After"] == "1"
    assert server.limits_metrics.snapshot()["long_poll_concurrency"] >= 1


def test_no_frame_uses_retryable_envelope(monitor_server):
    _, _, base_url, _ = monitor_server

    response, body = _get(base_url, "/api/v1/frame")

    assert response.code == 503
    assert json.loads(body)["error"]["code"] == codes.VIDEO_FRAME_PENDING
    assert response.headers["Retry-After"] == "1"


def test_204_still_works_and_keeps_sequence(monitor_server):
    _, state, base_url, _ = monitor_server
    state.publish(b"jpeg", [], 1)

    response, body = _get(base_url, "/api/v1/frame?after=1")

    assert response.status == 204 and body == b""
    assert response.headers["X-Frame-Sequence"] == "1"


def test_rejection_counters_do_not_replace_observability_metrics(monitor_server):
    server, state, _, _ = monitor_server

    assert server.metrics is state.metrics
    assert set(server.limits_metrics.snapshot()) == {"concurrency", "long_poll_concurrency", "timeout", "oversized"}
