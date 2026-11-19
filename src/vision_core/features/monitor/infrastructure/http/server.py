"""Bounded ThreadingHTTPServer for the local monitor.

The accept loop never blocks: when the global connection budget is exhausted
the request is answered immediately with a small JSON 503 and the socket is
closed. A second, smaller budget limits simultaneous long-polls in the handler.
"""

import json
import secrets
import socket
import threading
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from pathlib import Path

from vision_core.features.monitor.application.use_cases.get_frame import GetFrame
from vision_core.features.monitor.application.use_cases.get_snapshot import GetSnapshot
from vision_core.features.monitor.infrastructure.http.handler import Handler, security_headers
from vision_core.features.monitor.infrastructure.http.limits_metrics import MonitorLimitsMetrics

MAX_CONNECTIONS = 4
MAX_LONG_POLLS = 2
_CSP_PLACEHOLDER = b"__CSP_NONCE__"
_REQUIRED_PLACEHOLDERS = 2


class MonitorHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, page, get_snapshot, get_frame):
        super().__init__(address, Handler)
        self.page = page
        self.get_snapshot = get_snapshot
        self.get_frame = get_frame
        self.metrics = MonitorLimitsMetrics()
        self._connections = threading.BoundedSemaphore(MAX_CONNECTIONS)
        self.long_poll_slots = threading.BoundedSemaphore(MAX_LONG_POLLS)
        self._active_lock = threading.Lock()
        self._active = 0

    @property
    def active_connections(self):
        with self._active_lock:
            return self._active

    def process_request(self, request, client_address):
        if not self._connections.acquire(blocking=False):
            self.metrics.record("concurrency")
            self._reject_immediately(
                request,
                HTTPStatus.SERVICE_UNAVAILABLE,
                "Service unavailable",
            )
            return
        try:
            with self._active_lock:
                self._active += 1
            super().process_request(request, client_address)
        except BaseException:
            self._release_connection()
            raise

    def _release_connection(self):
        with self._active_lock:
            self._active = max(0, self._active - 1)
        self._connections.release()

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._release_connection()

    @staticmethod
    def _reject_immediately(request, status, message):
        body = json.dumps({"error": message}, allow_nan=False).encode()
        headers = [
            f"HTTP/1.1 {status.value} {status.phrase}",
            "Content-Type: application/json",
            f"Content-Length: {len(body)}",
            "Retry-After: 1",
            "Connection: close",
        ]
        for name, value in security_headers(secrets.token_urlsafe(16)).items():
            headers.append(f"{name}: {value}")
        response = ("\r\n".join(headers) + "\r\n\r\n").encode("latin-1") + body
        try:
            # Keep the accept loop responsive even if the peer is not reading.
            request.settimeout(1.0)
            request.sendall(response)
        except OSError:
            pass
        finally:
            try:
                request.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            request.close()


def make_server(host, port, state, page_path=None):
    default_page = Path(__file__).resolve().parents[4] / "infrastructure/monitor/index.html"
    page = Path(page_path or default_page).read_bytes()
    if page.count(_CSP_PLACEHOLDER) != _REQUIRED_PLACEHOLDERS:
        raise ValueError(
            f"La página del monitor debe contener exactamente {_REQUIRED_PLACEHOLDERS} "
            f"marcadores {_CSP_PLACEHOLDER.decode()}"
        )
    return MonitorHTTPServer(
        (host, port),
        page,
        GetSnapshot(state),
        GetFrame(state),
    )
