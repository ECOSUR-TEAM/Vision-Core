import json
import socket
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from vision_core.features.monitor.infrastructure.http.handler import MAX_SEQUENCE_DIGITS
from vision_core.infrastructure.monitor.http_server import make_server
from vision_core.infrastructure.monitor.state import MonitorState


@pytest.fixture
def monitor_server():
    state = MonitorState()
    server = make_server("127.0.0.1", 0, state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        state.publish(b"jpeg", [], 4)
        yield server, state
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def _url(server, path):
    return f"http://127.0.0.1:{server.server_port}{path}"


def _request_error(url, method="GET", data=None):
    with pytest.raises(HTTPError) as error:
        urlopen(Request(url, data=data, method=method))
    return error.value


def _payload(error):
    return json.loads(error.read())


def test_valid_routes_return_200(monitor_server):
    server, _ = monitor_server

    with urlopen(_url(server, "/")) as response:
        assert response.status == 200
        assert response.headers["Content-Type"] == "text/html; charset=utf-8"

    with urlopen(_url(server, "/api/state")) as response:
        assert response.status == 200
        body = json.load(response)
        assert body["status"] == "running"
        assert body["frame"] == 1

    with urlopen(_url(server, "/api/frame")) as response:
        assert response.status == 200
        assert response.read() == b"jpeg"
        assert response.headers["X-Frame-Sequence"] == "1"


def test_unknown_route_returns_404_with_json_error(monitor_server):
    server, _ = monitor_server

    error = _request_error(_url(server, "/api/unknown"))
    assert error.code == 404
    assert _payload(error) == {"error": "Not found"}


@pytest.mark.parametrize("path", ["/api/state/", "/api/frame/", "/index.html", "/api"])
def test_routes_are_exact(monitor_server, path):
    server, _ = monitor_server

    error = _request_error(_url(server, path))
    assert error.code == 404
    assert _payload(error) == {"error": "Not found"}


@pytest.mark.parametrize("method", ["POST", "PUT", "HEAD", "DELETE", "PATCH", "OPTIONS", "TRACE"])
@pytest.mark.parametrize("path", ["/", "/api/state", "/api/frame"])
def test_disallowed_methods_return_405_with_allow_get(monitor_server, method, path):
    server, _ = monitor_server
    data = b"" if method in {"POST", "PUT", "PATCH"} else None

    error = _request_error(_url(server, path), method=method, data=data)
    assert error.code == 405
    assert error.headers["Allow"] == "GET"
    if method != "HEAD":
        assert _payload(error) == {"error": "Method not allowed"}


def test_head_405_has_no_body(monitor_server):
    """RFC 9110: HEAD answers with status/headers only, never content."""
    server, _ = monitor_server
    request = (
        f"HEAD /api/state HTTP/1.1\r\n" f"Host: 127.0.0.1:{server.server_port}\r\n" "Connection: close\r\n\r\n"
    ).encode()

    with socket.create_connection(("127.0.0.1", server.server_port)) as connection:
        connection.sendall(request)
        chunks = []
        while True:
            chunk = connection.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)

    raw = b"".join(chunks)
    headers, separator, body = raw.partition(b"\r\n\r\n")
    assert separator
    assert b"405 Method Not Allowed" in headers.split(b"\r\n", 1)[0]
    assert b"Allow: GET" in headers
    assert b"Content-Type: application/json" in headers
    assert body == b""
    assert b'{"error"' not in raw


@pytest.mark.parametrize("path", ["/", "/api/state"])
@pytest.mark.parametrize("query", ["foo=bar", "after=1", "foo="])
def test_root_and_state_reject_any_query_parameter(monitor_server, path, query):
    server, _ = monitor_server

    error = _request_error(_url(server, f"{path}?{query}"))
    assert error.code == 400
    assert _payload(error) == {"error": "Query parameters are not allowed"}


def test_frame_accepts_valid_after(monitor_server):
    server, state = monitor_server
    for _ in range(100):
        state.publish(b"jpeg", [], 4)

    with urlopen(_url(server, "/api/frame?after=100")) as response:
        assert response.status == 200
        assert response.read() == b"jpeg"
        assert response.headers["X-Frame-Sequence"] == "101"


@pytest.mark.parametrize(
    "raw_after",
    [
        "-1",
        "+5",
        "%2B5",
        "%2010%20",
        "abc",
        "",
        "1.5",
        "0" * (MAX_SEQUENCE_DIGITS + 1) + "1",
        "9" * (MAX_SEQUENCE_DIGITS + 1),
        "9" * 100,
    ],
)
def test_frame_rejects_invalid_after_values(monitor_server, raw_after):
    server, _ = monitor_server

    error = _request_error(_url(server, f"/api/frame?after={raw_after}"))
    assert error.code == 400
    assert "error" in _payload(error)


def test_frame_rejects_duplicate_after(monitor_server):
    server, _ = monitor_server

    error = _request_error(_url(server, "/api/frame?after=1&after=2"))
    assert error.code == 400
    assert _payload(error) == {"error": "Duplicate 'after' parameter"}


@pytest.mark.parametrize("query", ["foo=bar", "after=1&foo=bar", "foo=bar&after=1"])
def test_frame_rejects_unknown_query_parameters(monitor_server, query):
    server, _ = monitor_server

    error = _request_error(_url(server, f"/api/frame?{query}"))
    assert error.code == 400
    assert _payload(error) == {"error": "Unknown query parameter"}


def test_error_responses_do_not_leak_server_details(monitor_server):
    server, _ = monitor_server

    error = _request_error(_url(server, "/api/frame?after=%2B5"))
    body = error.read().decode()
    assert error.code == 400
    assert "Server" not in error.headers
    assert "Traceback" not in body
    assert "BaseHTTP" not in body
    assert "handler.py" not in body


def test_204_has_no_body_or_entity_headers(monitor_server):
    server, state = monitor_server
    sequence = state.sequence

    with urlopen(_url(server, f"/api/frame?after={sequence}")) as response:
        assert response.status == 204
        assert response.read() == b""
        assert "Content-Type" not in response.headers
        assert "Content-Length" not in response.headers
        assert response.headers["X-Frame-Sequence"] == str(sequence)


def test_waiting_for_video_returns_json_503(monitor_server):
    server, state = monitor_server
    # Recrear el estado vacío sin reiniciar el server no es posible; usar un
    # servidor dedicado con un MonitorState que nunca publicó un frame.
    empty_state = type(state)()
    empty_server = make_server("127.0.0.1", 0, empty_state)
    thread = threading.Thread(target=empty_server.serve_forever, daemon=True)
    thread.start()
    try:
        error = _request_error(_url(empty_server, "/api/frame"))
        assert error.code == 503
        assert error.headers["Content-Type"] == "application/json"
        assert error.headers["Retry-After"] == "1"
        assert _payload(error) == {"error": "Esperando video"}
    finally:
        empty_server.shutdown()
        empty_server.server_close()
        thread.join()
