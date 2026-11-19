import socket
import threading
import time
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from vision_core.features.monitor.infrastructure.http.handler import (
    MAX_HEADER_COUNT,
    MAX_HEADERS_BYTES,
    MAX_REQUEST_LINE,
    REQUEST_DEADLINE_SECONDS,
)
from vision_core.features.monitor.infrastructure.http.server import (
    MAX_CONNECTIONS,
    MAX_LONG_POLLS,
)
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


def _base_url(server):
    return f"http://127.0.0.1:{server.server_port}"


def _raw_exchange(server, request, read_timeout=3.0):
    with socket.create_connection(("127.0.0.1", server.server_port)) as connection:
        connection.settimeout(read_timeout)
        connection.sendall(request)
        chunks = []
        while True:
            chunk = connection.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
    return b"".join(chunks)


def _status_line(response):
    return response.split(b"\r\n", 1)[0]


def _rejected_error(url):
    with pytest.raises(HTTPError) as error:
        urlopen(url)
    return error.value


def _wait_until(predicate, timeout=2.0, interval=0.01):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


def _header_bytes_request(total_bytes):
    """Build a GET whose header section (excluding the request line) has total_bytes."""
    request_line = b"GET /api/state HTTP/1.1\r\n"
    host = b"Host: 127.0.0.1\r\n"
    suffix = b"\r\n"
    pad = b"X-Pad: "
    filler = total_bytes - len(host) - len(suffix) - 2 - len(pad)
    assert filler >= 0
    return request_line + host + pad + b"a" * filler + b"\r\n" + suffix


def test_request_line_boundary(monitor_server):
    server, _ = monitor_server
    base = b"GET /"
    ending = b" HTTP/1.1\r\n"
    headers = b"Host: 127.0.0.1\r\n\r\n"

    def request_line(length):
        filler = length - len(base) - len(ending)
        assert filler >= 0
        return base + b"a" * filler + ending + headers

    assert b"414" not in _status_line(_raw_exchange(server, request_line(MAX_REQUEST_LINE)))
    assert b"414" in _status_line(_raw_exchange(server, request_line(MAX_REQUEST_LINE + 1)))
    assert server.metrics.snapshot()["oversized"] >= 1


def test_header_bytes_boundary(monitor_server):
    server, _ = monitor_server
    assert b"431" not in _status_line(_raw_exchange(server, _header_bytes_request(MAX_HEADERS_BYTES)))
    response = _raw_exchange(server, _header_bytes_request(MAX_HEADERS_BYTES + 1))
    assert b"431" in _status_line(response)
    assert server.metrics.snapshot()["oversized"] >= 1


def test_header_count_boundary(monitor_server):
    server, _ = monitor_server

    def request(count):
        headers = b"".join(b"X-%03d: 1\r\n" % index for index in range(count))
        return b"GET /api/state HTTP/1.1\r\nHost: 127.0.0.1\r\n" + headers + b"\r\n"

    # Host counts as one header, so MAX_HEADER_COUNT - 1 extra headers is the
    # largest accepted request. The next one is rejected by our own limit.
    assert b"431" not in _status_line(_raw_exchange(server, request(MAX_HEADER_COUNT - 1)))
    assert b"431" in _status_line(_raw_exchange(server, request(MAX_HEADER_COUNT)))


def test_transfer_encoding_is_rejected(monitor_server):
    server, _ = monitor_server
    request = (
        b"POST / HTTP/1.1\r\n" b"Host: 127.0.0.1\r\n" b"Transfer-Encoding: chunked\r\n" b"Connection: close\r\n\r\n"
    )
    response = _raw_exchange(server, request)
    assert b"400" in _status_line(response)
    assert b'"error"' in response


def test_duplicate_content_length_is_rejected(monitor_server):
    server, _ = monitor_server
    request = (
        b"GET / HTTP/1.1\r\n"
        b"Host: 127.0.0.1\r\n"
        b"Content-Length: 0\r\n"
        b"Content-Length: 0\r\n"
        b"Connection: close\r\n\r\n"
    )
    response = _raw_exchange(server, request)
    assert b"400" in _status_line(response)
    assert b'"error"' in response


def test_zero_content_length_is_accepted(monitor_server):
    server, _ = monitor_server
    request = (
        b"GET /api/state HTTP/1.1\r\n" b"Host: 127.0.0.1\r\n" b"Content-Length: 0\r\n" b"Connection: close\r\n\r\n"
    )
    assert b"200" in _status_line(_raw_exchange(server, request))


def test_oversized_request_line_returns_414(monitor_server):
    server, _ = monitor_server
    request = b"GET /" + b"a" * 5000 + b" HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n"

    response = _raw_exchange(server, request)
    assert b"414" in _status_line(response)
    assert b'"error"' in response
    assert server.metrics.snapshot()["oversized"] >= 1


def test_oversized_header_value_returns_431(monitor_server):
    server, _ = monitor_server
    request = b"GET / HTTP/1.1\r\n" b"Host: 127.0.0.1\r\n" b"X-Big: " + b"a" * 9000 + b"\r\n" b"\r\n"

    response = _raw_exchange(server, request)
    assert b"431" in _status_line(response)
    assert server.metrics.snapshot()["oversized"] >= 1


def test_too_many_headers_returns_431(monitor_server):
    server, _ = monitor_server
    headers = b"".join(b"X-%d: 1\r\n" % index for index in range(150))
    request = b"GET / HTTP/1.1\r\nHost: 127.0.0.1\r\n" + headers + b"\r\n"

    response = _raw_exchange(server, request)
    assert b"431" in _status_line(response)


def test_get_with_body_returns_413(monitor_server):
    server, _ = monitor_server
    request = (
        b"GET /api/frame HTTP/1.1\r\n"
        b"Host: 127.0.0.1\r\n"
        b"Content-Length: 5\r\n"
        b"Connection: close\r\n\r\n"
        b"hello"
    )

    response = _raw_exchange(server, request)
    assert b"413" in _status_line(response)
    assert server.metrics.snapshot()["oversized"] >= 1


def test_slow_client_deadline_is_absolute(monitor_server):
    server, _ = monitor_server
    connection = socket.create_connection(("127.0.0.1", server.server_port))
    try:
        connection.sendall(b"GET / HTTP/1.1\r\n")
        # Keep feeding the socket in small chunks. A per-read timeout would be
        # renewed forever; the absolute deadline must still close the request.
        deadline = time.monotonic() + REQUEST_DEADLINE_SECONDS + 1
        while time.monotonic() < deadline:
            try:
                connection.sendall(b"X-Slow: 1\r\n")
            except (BrokenPipeError, ConnectionResetError):
                break
            time.sleep(0.5)
        connection.settimeout(2.0)
        try:
            assert connection.recv(4096) == b""
        except ConnectionResetError:
            # The server may close with RST after the deadline; either way the
            # slow client is gone.
            pass
    finally:
        connection.close()

    assert server.metrics.snapshot()["timeout"] >= 1
    with urlopen(f"{_base_url(server)}/api/state") as response:
        assert response.status == 200


def test_global_connection_limit_rejects_excess_immediately(monitor_server):
    server, _ = monitor_server
    before = server.metrics.snapshot()["concurrency"]
    holders = []
    try:
        for index in range(MAX_CONNECTIONS):
            connection = socket.create_connection(("127.0.0.1", server.server_port))
            connection.sendall(f"GET /?holder={index} HTTP/1.1\r\n".encode())
            holders.append(connection)
        assert _wait_until(lambda: server.active_connections >= MAX_CONNECTIONS)

        started = time.monotonic()
        error = _rejected_error(f"{_base_url(server)}/")
        elapsed = time.monotonic() - started
        assert error.code in (429, 503)
        assert elapsed < 1.0
        assert server.metrics.snapshot()["concurrency"] == before + 1
    finally:
        for connection in holders:
            connection.close()

    assert _wait_until(lambda: server.active_connections == 0)
    with urlopen(f"{_base_url(server)}/api/state") as response:
        assert response.status == 200


def test_long_poll_limit_rejects_excess(monitor_server):
    server, _ = monitor_server
    before = server.metrics.snapshot()["long_poll_concurrency"]
    request = b"GET /api/frame?after=1 HTTP/1.1\r\n" b"Host: 127.0.0.1\r\n" b"Connection: close\r\n\r\n"
    results = {}
    holders = []

    def hold(index):
        results[index] = _status_line(_raw_exchange(server, request, read_timeout=4.0))

    try:
        for index in range(MAX_LONG_POLLS):
            thread = threading.Thread(target=hold, args=(index,), daemon=True)
            thread.start()
            holders.append(thread)
        assert _wait_until(lambda: server.long_poll_slots._value == 0)  # noqa: SLF001

        error = _rejected_error(f"{_base_url(server)}/api/frame?after=1")
        assert error.code in (429, 503)
        assert server.metrics.snapshot()["long_poll_concurrency"] == before + 1
    finally:
        for thread in holders:
            thread.join(timeout=4)

    assert len(results) == MAX_LONG_POLLS
    assert all(b"204" in results[index] or b"200" in results[index] for index in results)


def test_metrics_expose_all_rejection_counters(monitor_server):
    server, _ = monitor_server

    snapshot = server.metrics.snapshot()
    assert set(snapshot) == {"concurrency", "long_poll_concurrency", "timeout", "oversized"}
    assert all(isinstance(value, int) for value in snapshot.values())
