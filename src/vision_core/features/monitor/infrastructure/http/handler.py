"""Límites de petición y concurrencia del monitor, con errores JSON."""

import io
import logging
import time
import uuid
from http.server import BaseHTTPRequestHandler
from typing import TYPE_CHECKING, cast
from urllib.parse import SplitResult, parse_qs, urlsplit

from vision_core.features.monitor.application.dto.request.request_frame import RequestFrame
from vision_core.features.monitor.application.dto.request.request_snapshot import RequestSnapshot
from vision_core.features.monitor.infrastructure.http.api import API_PREFIX, LEGACY_PREFIX
from vision_core.features.monitor.infrastructure.http.error_response import describe_error, error_envelope
from vision_core.shared.application.dto.serialization import dumps_json
from vision_core.shared.errors import ValidationError, VisionCoreError, codes

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from vision_core.features.monitor.infrastructure.http.server import MonitorHTTPServer

# Deadline absoluto de la petición completa; no renovable por un cliente lento.
# Debe ser mayor que la espera interna de 1 s de MonitorState.next_frame.
REQUEST_DEADLINE_SECONDS = 5.0
MAX_REQUEST_LINE = 4096
MAX_HEADERS_BYTES = 8192
MAX_HEADER_COUNT = 99

_SAFE_ERROR_MESSAGES = {
    400: "Bad request",
    404: "Not found",
    413: "Payload too large",
    414: "Request URI too long",
    431: "Request header fields too large",
    500: "Internal server error",
    501: "Not implemented",
    505: "HTTP version not supported",
}


class Handler(BaseHTTPRequestHandler):
    @property
    def _monitor_server(self) -> "MonitorHTTPServer":
        return cast("MonitorHTTPServer", self.server)

    def send_error(self, code, message=None, explain=None):
        """Los errores del framework también usan el envelope versionado."""
        self._send_error(code, _SAFE_ERROR_MESSAGES.get(code, "Request error"))

    def _send_error(self, code, message, *, code_name=None, retry_after=None):
        code_name = code_name or (codes.VALIDATION_FAILED if 400 <= code < 500 else codes.INTERNAL_ERROR)
        body = dumps_json(error_envelope(code_name, message, self._request_id)).encode()
        self._respond(
            self._request_id,
            getattr(self, "path", "") or "",
            code,
            "application/json",
            body,
            None,
            retry_after=retry_after,
        )

    def handle_one_request(self):
        """Lee con límites duros antes de despachar al handler normal."""
        metrics = self._monitor_server.limits_metrics
        self._request_id = uuid.uuid4().hex
        self._deadline = time.monotonic() + REQUEST_DEADLINE_SECONDS
        self.command = ""
        self.request_version = self.protocol_version
        self.requestline = ""
        self.close_connection = True
        try:
            self.raw_requestline = self._read_limited_line(MAX_REQUEST_LINE)
            if len(self.raw_requestline) > MAX_REQUEST_LINE:
                metrics.record("oversized")
                self.send_error(414, "Request line too long")
                return
            if not self.raw_requestline:
                return

            header_bytes = self._read_limited_headers()
            if header_bytes is None:
                return

            original_rfile = self.rfile
            self.rfile = io.BytesIO(header_bytes)
            try:
                if not self.parse_request():
                    return
            finally:
                self.rfile = original_rfile

            if self._reject_body():
                return

            method = getattr(self, "do_" + self.command)
            method()
            self.wfile.flush()
        except TimeoutError:
            metrics.record("timeout")

    def _read_limited_line(self, limit):
        remaining = self._deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError
        self.connection.settimeout(remaining)
        return self.rfile.readline(limit + 1)

    def _read_limited_headers(self):
        data = bytearray()
        count = 0
        while True:
            line = self._read_limited_line(MAX_HEADERS_BYTES)
            if not line:
                break
            if len(data) + len(line) > MAX_HEADERS_BYTES:
                self._monitor_server.limits_metrics.record("oversized")
                self.send_error(431, "Headers too large")
                return None
            data.extend(line)
            if line in (b"\r\n", b"\n"):
                break
            count += 1
            if count > MAX_HEADER_COUNT:
                self._monitor_server.limits_metrics.record("oversized")
                self.send_error(431, "Too many headers")
                return None
        return bytes(data)

    def _reject_body(self):
        if "Transfer-Encoding" in self.headers:
            self._send_error(400, "Transfer-Encoding is not allowed")
            return True
        lengths = self.headers.get_all("Content-Length") or []
        if len(lengths) > 1:
            self._send_error(400, "Duplicate Content-Length")
            return True
        if not lengths:
            return False
        raw = lengths[0]
        if not raw.isascii() or not raw.isdigit():
            self._send_error(400, "Invalid Content-Length")
            return True
        if int(raw) > 0:
            self._monitor_server.limits_metrics.record("oversized")
            self._send_error(413, "Request body is not allowed")
            return True
        return False

    def do_GET(self):
        try:
            url = urlsplit(self.path)
            result = self._route(url)
        except Exception as error:  # noqa: BLE001 - el contrato HTTP debe seguir siendo JSON
            code_name, message, code = describe_error(error)
            details = error.as_dict() if isinstance(error, VisionCoreError) else {"code": code_name, "message": message}
            body = dumps_json(error_envelope(code_name, message, self._request_id)).encode()
            retry_after = 1 if code == 503 and getattr(error, "retryable", False) else None
            _LOGGER.error("monitor_error request_id=%s error=%s", self._request_id, details, exc_info=True)
            self._respond(self._request_id, url.path, code, "application/json", body, None, retry_after=retry_after)
            return
        if result is None:
            return
        body, kind, code, sequence = result
        self._respond(self._request_id, url.path, code, kind, body, sequence)

    def _route(self, url: SplitResult):
        path = url.path
        server = self._monitor_server
        if path == "/":
            return server.page, "text/html; charset=utf-8", 200, None
        if path in (f"{API_PREFIX}/state", f"{LEGACY_PREFIX}/state"):
            response = server.get_snapshot.execute(RequestSnapshot())
            return dumps_json(response).encode(), "application/json", 200, None
        if path in (f"{API_PREFIX}/frame", f"{LEGACY_PREFIX}/frame"):
            return self._frame(url)
        if path == "/health":
            return dumps_json({"status": "alive", "live": True}).encode(), "application/json", 200, None
        if path == "/ready":
            server.get_snapshot.execute(RequestSnapshot())
            readiness = server.health.snapshot() if server.health is not None else {"ready": False, "checks": {}}
            return dumps_json(readiness).encode(), "application/json", 200 if readiness["ready"] else 503, None
        if path == "/metrics":
            metrics = (
                server.metrics.snapshot()
                if server.metrics is not None
                else {"counters": {}, "gauges": {}, "histograms": {}, "uptime_seconds": 0}
            )
            return dumps_json(metrics).encode(), "application/json", 200, None
        raise VisionCoreError(
            "La ruta solicitada no existe.",
            code=codes.REQUEST_NOT_FOUND,
            retryable=False,
        )

    def _frame(self, url: SplitResult):
        server = self._monitor_server
        if not server.long_poll_slots.acquire(blocking=False):
            server.limits_metrics.record("long_poll_concurrency")
            self._send_error(503, "Service unavailable", retry_after=1)
            return None
        try:
            query = parse_qs(url.query)
            if "after" in query:
                try:
                    after = int(query["after"][0])
                    if after < 0:
                        raise ValueError
                except (TypeError, ValueError):
                    raise ValidationError(
                        "El parámetro 'after' debe ser un entero no negativo.",
                        context={"parameter": "after"},
                    ) from None
                response = server.get_frame.execute(RequestFrame(after))
                if response.jpeg:
                    return response.jpeg, "image/jpeg", 200, response.sequence
                return b"", "image/jpeg", 204, response.sequence
            response = server.get_frame.execute(RequestFrame())
            if response.jpeg:
                return response.jpeg, "image/jpeg", 200, response.sequence
            raise VisionCoreError(
                "Todavía no hay video disponible.",
                code=codes.VIDEO_FRAME_PENDING,
                retryable=True,
            )
        finally:
            server.long_poll_slots.release()

    def _respond(self, request_id, path, code, kind, body, sequence, *, retry_after=None):
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Request-ID", request_id)
        if path.startswith(f"{LEGACY_PREFIX}/") and not path.startswith(f"{API_PREFIX}/"):
            self.send_header("Deprecation", "true")
        if sequence is not None:
            self.send_header("X-Frame-Sequence", str(sequence))
        if retry_after is not None:
            self.send_header("Retry-After", str(retry_after))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, *args):
        pass
