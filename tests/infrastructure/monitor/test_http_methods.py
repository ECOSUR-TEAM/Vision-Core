"""ECM-90: solo GET, 405 con Allow y validación estricta de query."""

import json
import threading
from http.client import HTTPConnection
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from vision_core.core.errors import codes
from vision_core.features.monitor.infrastructure.http.server import make_server
from vision_core.infrastructure.monitor.state import MonitorState


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


@pytest.mark.parametrize("method", ["HEAD", "POST", "PUT", "DELETE", "PATCH"])
def test_only_get_is_allowed(monitor_server, method):
    _, _, _, address = monitor_server

    connection = HTTPConnection(*address, timeout=5)
    connection.request(method, "/api/v1/state")
    response = connection.getresponse()
    body = response.read()
    headers = dict(response.getheaders())
    connection.close()

    assert response.status == 405
    assert headers["Allow"] == "GET"
    assert headers["Content-Type"] == "application/json"
    assert headers["X-Request-ID"]
    if method == "HEAD":
        assert body == b""
    else:
        payload = json.loads(body)
        assert payload["error"]["code"] == codes.VALIDATION_FAILED
        assert payload["error"]["request_id"] == headers["X-Request-ID"]


@pytest.mark.parametrize("path", ["/?x=1", "/api/v1/state?x=1", "/health?x=1", "/ready?x=1", "/metrics?x=1"])
def test_non_frame_routes_reject_query_parameters(monitor_server, path):
    _, _, base_url, _ = monitor_server

    response, body = _get(base_url, path)

    assert response.code == 400
    assert json.loads(body)["error"]["code"] == codes.VALIDATION_FAILED


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/frame?after=1&after=2",
        "/api/v1/frame?unknown=1",
        "/api/v1/frame?after=-1",
        "/api/v1/frame?after=abc",
        "/api/v1/frame?after=",
        "/api/v1/frame?after=" + "9" * 31,
    ],
)
def test_frame_query_is_strict(monitor_server, path):
    _, _, base_url, _ = monitor_server

    response, body = _get(base_url, path)

    assert response.code == 400
    assert json.loads(body)["error"]["code"] == codes.VALIDATION_FAILED


def test_large_sequence_is_not_capped_like_a_c_int(monitor_server):
    _, _, base_url, _ = monitor_server

    response, _ = _get(base_url, "/api/v1/frame?after=" + "9" * 30)

    assert response.status == 204


def test_existing_contract_is_preserved(monitor_server):
    _, state, base_url, _ = monitor_server
    state.publish(b"jpeg", [], 7)

    response, body = _get(base_url, "/api/v1/state")
    assert response.status == 200 and json.loads(body)["frame"] == state.sequence

    response, _ = _get(base_url, "/api/state")
    assert response.status == 200 and response.headers["Deprecation"] == "true"

    response, body = _get(base_url, "/api/v1/frame")
    assert response.status == 200 and body == b"jpeg"
    assert response.headers["X-Frame-Sequence"] == str(state.sequence)

    response, body = _get(base_url, "/api/v1/unknown")
    assert response.code == 404
    assert json.loads(body)["error"]["code"] == codes.REQUEST_NOT_FOUND
