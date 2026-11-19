import re
import socket
import threading
from contextlib import contextmanager
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from vision_core.features.monitor.infrastructure.http.server import make_server
from vision_core.infrastructure.monitor.state import MonitorState

_CSP_BASE = (
    "default-src 'self'; frame-ancestors 'none'; base-uri 'none'; "
    "object-src 'none'; form-action 'none'; connect-src 'self'; "
    "img-src 'self' blob:;"
)

_EXPECTED = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": (
        "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
        "magnetometer=(), microphone=(), payment=(), usb=()"
    ),
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
}


@contextmanager
def _running_server(state, page_path=None):
    server = make_server("127.0.0.1", 0, state, page_path=page_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.fixture
def monitor_server():
    state = MonitorState()
    with _running_server(state) as server:
        state.publish(b"jpeg", [], 4)
        yield server, state


@pytest.fixture
def empty_monitor_server():
    state = MonitorState()
    with _running_server(state) as server:
        yield server, state


def _url(server, path):
    return f"http://127.0.0.1:{server.server_port}{path}"


def _assert_security_headers(headers):
    for name, value in _EXPECTED.items():
        assert headers[name] == value
    csp = headers["Content-Security-Policy"]
    assert _CSP_BASE in csp
    assert "unsafe-inline" not in csp
    assert "unsafe-eval" not in csp


def test_no_server_fingerprint(monitor_server):
    server, _ = monitor_server

    with urlopen(_url(server, "/")) as response:
        assert "Server" not in response.headers

    request = (f"GET / HTTP/1.1\r\nHost: 127.0.0.1:{server.server_port}\r\n" "Connection: close\r\n\r\n").encode()
    with socket.create_connection(("127.0.0.1", server.server_port)) as connection:
        connection.sendall(request)
        raw = b"".join(iter(lambda: connection.recv(4096), b""))

    assert b"Python" not in raw
    assert b"BaseHTTP" not in raw
    assert b"Server:" not in raw


def test_security_headers_on_success(monitor_server):
    server, _ = monitor_server

    with urlopen(_url(server, "/")) as response:
        assert response.status == 200
        _assert_security_headers(response.headers)


@pytest.mark.parametrize("path", ["/api/state", "/api/frame"])
def test_security_headers_on_api_success(monitor_server, path):
    server, _ = monitor_server

    with urlopen(_url(server, path)) as response:
        assert response.status == 200
        _assert_security_headers(response.headers)


def test_security_headers_on_not_found(monitor_server):
    server, _ = monitor_server

    with pytest.raises(HTTPError) as error:
        urlopen(_url(server, "/ruta_invalida"))
    assert error.value.code == 404
    assert "Server" not in error.value.headers
    _assert_security_headers(error.value.headers)


def test_security_headers_on_method_not_allowed(monitor_server):
    server, _ = monitor_server
    request = Request(_url(server, "/"), data=b"", method="POST")

    with pytest.raises(HTTPError) as error:
        urlopen(request)
    assert error.value.code == 405
    assert error.value.headers["Allow"] == "GET"
    assert "Server" not in error.value.headers
    _assert_security_headers(error.value.headers)


def test_security_headers_on_bad_query(monitor_server):
    server, _ = monitor_server

    with pytest.raises(HTTPError) as error:
        urlopen(_url(server, "/api/state?foo=bar"))
    assert error.value.code == 400
    _assert_security_headers(error.value.headers)


def test_security_headers_on_request_uri_too_long(monitor_server):
    """414 is emitted by BaseHTTPRequestHandler before routing; headers still apply."""
    server, _ = monitor_server
    request = (
        f"GET /{'x' * 70_000} HTTP/1.1\r\n" f"Host: 127.0.0.1:{server.server_port}\r\n" "Connection: close\r\n\r\n"
    ).encode()

    with socket.create_connection(("127.0.0.1", server.server_port)) as connection:
        connection.sendall(request)
        chunks = []
        try:
            while True:
                chunk = connection.recv(4096)
                if not chunk:
                    break
                chunks.append(chunk)
        except ConnectionResetError:
            # The server closes immediately after the early 414 while the
            # client may still be writing the oversized URI.
            pass
        raw = b"".join(chunks)

    assert b"414" in raw.split(b"\r\n", 1)[0]
    headers = raw.split(b"\r\n\r\n", 1)[0].decode("latin-1")
    for name, value in _EXPECTED.items():
        assert f"{name}: {value}" in headers
    assert "Content-Security-Policy:" in headers
    assert "unsafe-inline" not in headers
    assert "unsafe-eval" not in headers
    assert "Server:" not in headers
    assert "Python" not in headers
    assert "BaseHTTP" not in headers


def test_security_headers_on_no_frame_available(empty_monitor_server):
    """503 is the monitor's 'waiting for video' response."""
    server, _ = empty_monitor_server

    with pytest.raises(HTTPError) as error:
        urlopen(_url(server, "/api/frame"))
    assert error.value.code == 503
    assert error.value.headers["Content-Type"] == "application/json"
    assert error.value.headers["Retry-After"] == "1"
    assert error.value.read() == b'{"error": "Esperando video"}'
    _assert_security_headers(error.value.headers)


def test_204_has_security_headers_but_no_entity_headers(monitor_server):
    server, state = monitor_server

    with urlopen(_url(server, f"/api/frame?after={state.sequence}")) as response:
        assert response.status == 204
        assert response.read() == b""
        assert "Content-Type" not in response.headers
        assert "Content-Length" not in response.headers
        _assert_security_headers(response.headers)


def test_custom_page_must_contain_both_nonce_placeholders(tmp_path):
    state = MonitorState()
    good = tmp_path / "good.html"
    good.write_text('<style nonce="__CSP_NONCE__"></style><script nonce="__CSP_NONCE__"></script>')
    bad = tmp_path / "bad.html"
    bad.write_text("<style></style><script></script>")

    with _running_server(state, page_path=good):
        pass
    with pytest.raises(ValueError, match="exactamente 2"):
        make_server("127.0.0.1", 0, state, page_path=bad)


def test_nonce_matches_html_and_csp(monitor_server):
    server, _ = monitor_server

    with urlopen(_url(server, "/")) as response:
        html = response.read().decode()
        csp = response.headers["Content-Security-Policy"]

    html_nonces = re.findall(r'nonce="([A-Za-z0-9_-]+)"', html)
    csp_nonces = re.findall(r"'nonce-([A-Za-z0-9_-]+)'", csp)
    assert len(html_nonces) == 2  # <style> and <script>
    assert html_nonces[0] == html_nonces[1]
    assert csp_nonces == [html_nonces[0], html_nonces[0]]
    assert "__CSP_NONCE__" not in html


def test_nonce_is_regenerated_per_request(monitor_server):
    server, _ = monitor_server

    def fetch_nonce():
        with urlopen(_url(server, "/")) as response:
            return response.headers["Content-Security-Policy"]

    assert "'nonce-" in fetch_nonce()
    assert fetch_nonce() != fetch_nonce()
