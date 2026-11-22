"""Endurecimiento HTTP sin romper el contrato versionado de develop."""

import json
import re
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

_NONCE_RE = re.compile(r"'nonce-([^']+)'")


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


def _payload(body):
    return json.loads(body)


def test_security_headers_are_present_without_native_server_banner(monitor_server):
    _, _, base_url, _ = monitor_server

    response, _ = _get(base_url, "/api/v1/state")

    assert response.status == 200
    assert response.headers["X-Request-ID"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Cache-Control"] == "no-store, no-cache, must-revalidate, max-age=0"
    assert "img-src 'self' blob:" in response.headers["Content-Security-Policy"]
    assert response.headers.get("Server") is None


def test_csp_nonce_is_per_request_and_replaces_both_placeholders(monitor_server):
    _, _, base_url, _ = monitor_server

    first, first_body = _get(base_url, "/")
    second, second_body = _get(base_url, "/")

    first_nonce = _NONCE_RE.search(first.headers["Content-Security-Policy"]).group(1)
    second_nonce = _NONCE_RE.search(second.headers["Content-Security-Policy"]).group(1)
    assert first_nonce != second_nonce
    for body, nonce in ((first_body, first_nonce), (second_body, second_nonce)):
        page = body.decode()
        assert "__CSP_NONCE__" not in page
        assert f'<style nonce="{nonce}">' in page
        assert f'<script nonce="{nonce}">' in page


def test_versioned_contract_and_observability_routes_are_preserved(monitor_server):
    _, state, base_url, _ = monitor_server
    state.publish(b"jpeg", [], 1)

    response, body = _get(base_url, "/api/v1/state")
    assert response.status == 200 and _payload(body)["frame"] == 1
    assert response.headers["X-Request-ID"]

    response, body = _get(base_url, "/api/v1/frame")
    assert response.status == 200 and body == b"jpeg"
    assert response.headers["X-Frame-Sequence"] == "1"

    response, _ = _get(base_url, "/api/state")
    assert response.status == 200 and response.headers["Deprecation"] == "true"

    response, body = _get(base_url, "/health")
    assert response.status == 200 and _payload(body) == {"status": "alive", "live": True}

    response, body = _get(base_url, "/metrics")
    assert response.status == 200
    assert {"counters", "gauges", "histograms"} <= set(_payload(body))

    response, body = _get(base_url, "/ready")
    assert response.status == 200 and _payload(body)["ready"] is True


def test_error_envelope_keeps_request_id_and_stable_codes(monitor_server):
    _, _, base_url, _ = monitor_server

    response, body = _get(base_url, "/api/v1/unknown")

    assert response.code == 404
    payload = _payload(body)
    assert set(payload) == {"error"}
    assert set(payload["error"]) == {"code", "message", "request_id"}
    assert payload["error"]["code"] == codes.REQUEST_NOT_FOUND
    assert payload["error"]["request_id"] == response.headers["X-Request-ID"]


def test_no_frame_uses_retryable_envelope(monitor_server):
    _, _, base_url, _ = monitor_server

    response, body = _get(base_url, "/api/v1/frame")

    assert response.code == 503
    assert _payload(body)["error"]["code"] == codes.VIDEO_FRAME_PENDING
    assert response.headers["Retry-After"] == "1"
    assert response.headers["Content-Type"] == "application/json"


def test_204_has_no_entity_headers_but_keeps_sequence(monitor_server):
    _, state, base_url, _ = monitor_server
    state.publish(b"jpeg", [], 1)

    response, body = _get(base_url, "/api/v1/frame?after=1")

    assert response.status == 204 and body == b""
    assert "Content-Type" not in response.headers
    assert "Content-Length" not in response.headers
    assert response.headers["X-Frame-Sequence"] == "1"
    assert response.headers["X-Request-ID"]


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/frame?after=1&after=2",
        "/api/v1/frame?unknown=1",
        "/api/v1/frame?after=-1",
        "/api/v1/frame?after=abc",
        "/api/v1/frame?after=",
        "/api/v1/frame?after=" + "9" * 31,
        "/api/v1/state?extra=1",
        "/health?extra=1",
        "/?extra=1",
    ],
)
def test_strict_query_validation_uses_validation_failed(monitor_server, path):
    _, _, base_url, _ = monitor_server

    response, body = _get(base_url, path)

    assert response.code == 400
    assert _payload(body)["error"]["code"] == codes.VALIDATION_FAILED


def test_sequence_digits_are_not_capped_like_a_c_int(monitor_server):
    _, _, base_url, _ = monitor_server

    response, _ = _get(base_url, "/api/v1/frame?after=" + "9" * 30)

    assert response.status == 204


@pytest.mark.parametrize("method", ["HEAD", "POST", "PUT", "DELETE", "PATCH"])
def test_only_get_is_allowed_and_head_has_no_body(monitor_server, method):
    _, _, _, address = monitor_server

    connection = HTTPConnection(*address, timeout=5)
    connection.request(method, "/api/v1/state")
    response = connection.getresponse()
    body = response.read()
    connection.close()

    assert response.status == 405
    assert response.getheader("Allow") == "GET"
    assert response.getheader("Content-Type") == "application/json"
    assert response.getheader("X-Request-ID")
    if method == "HEAD":
        assert body == b""
    else:
        assert _payload(body)["error"]["code"] == codes.VALIDATION_FAILED


def test_oversized_request_line_is_rejected_with_envelope(monitor_server):
    _, _, _, address = monitor_server

    connection = HTTPConnection(*address, timeout=5)
    connection.putrequest("GET", "/" + "a" * MAX_REQUEST_LINE)
    connection.endheaders()
    response = connection.getresponse()
    payload = _payload(response.read())
    connection.close()

    assert response.status == 414
    assert payload["error"]["code"] == codes.VALIDATION_FAILED


def test_too_many_headers_are_rejected_with_envelope(monitor_server):
    _, _, _, address = monitor_server

    with socket.create_connection(address, timeout=5) as sock:
        headers = b"".join(f"X-Test-{index}: 1\r\n".encode() for index in range(MAX_HEADER_COUNT + 5))
        sock.sendall(b"GET / HTTP/1.0\r\n" + headers + b"\r\n")
        raw = b""
        while chunk := sock.recv(65535):
            raw += chunk

    assert raw.startswith(b"HTTP/1.0 431") or raw.startswith(b"HTTP/1.1 431")
    assert b'"code": "VALIDATION_FAILED"' in raw


def test_request_body_is_rejected(monitor_server):
    _, _, _, address = monitor_server

    connection = HTTPConnection(*address, timeout=5)
    connection.request("GET", "/api/v1/state", body=b"not-allowed")
    response = connection.getresponse()
    payload = _payload(response.read())
    connection.close()

    assert response.status == 413
    assert payload["error"]["code"] == codes.VALIDATION_FAILED


def test_connection_budget_returns_json_503_with_retry_after(monitor_server):
    server, _, base_url, _ = monitor_server
    server._connections = threading.BoundedSemaphore(0)

    response, body = _get(base_url, "/api/v1/state")

    assert response.code == 503
    assert _payload(body)["error"]["code"] == codes.INTERNAL_ERROR
    assert response.headers["Retry-After"] == "1"
    assert response.headers["X-Request-ID"]
    assert server.limits_metrics.snapshot()["concurrency"] >= 1


def test_long_poll_budget_returns_json_503_with_retry_after(monitor_server):
    server, _, base_url, _ = monitor_server
    server.long_poll_slots = threading.BoundedSemaphore(0)

    response, body = _get(base_url, "/api/v1/frame?after=0")

    assert response.code == 503
    assert _payload(body)["error"]["code"] == codes.INTERNAL_ERROR
    assert response.headers["Retry-After"] == "1"
    assert server.limits_metrics.snapshot()["long_poll_concurrency"] >= 1


def test_rejection_counters_do_not_replace_observability_metrics(monitor_server):
    server, state, _, _ = monitor_server

    assert server.metrics is state.metrics
    assert "concurrency" in server.limits_metrics.snapshot()
