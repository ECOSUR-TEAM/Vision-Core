"""HTTP routing, input validation, resource limits and security headers.

The versioned monitor contract from ``develop`` is preserved: ``/api/v1``,
legacy aliases with ``Deprecation``, ``/health``, ``/ready``, ``/metrics``,
``X-Request-ID`` and the ``{"error": {"code", "message", "request_id"}}``
envelope. This module only adds bounded reads, strict query validation and a
per-request CSP nonce for the single-page UI.
"""

import io
import logging
import secrets
import time
import uuid
from http.server import BaseHTTPRequestHandler
from typing import TYPE_CHECKING, cast
from urllib.parse import SplitResult, parse_qs, urlsplit

from vision_core.core.errors import ValidationError, VisionCoreError, codes
from vision_core.core.serialization import dumps_json
from vision_core.features.monitor.application.dto.request.request_frame import RequestFrame
from vision_core.features.monitor.application.dto.request.request_snapshot import RequestSnapshot
from vision_core.features.monitor.infrastructure.http.api import API_PREFIX, LEGACY_PREFIX
from vision_core.features.monitor.infrastructure.http.error_response import describe_error, error_envelope

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from vision_core.features.monitor.infrastructure.http.server import MonitorHTTPServer

# ``MonitorState.sequence`` is an unbounded Python int. Only the number of
# digits is bounded, to avoid pathological integer parsing; the value itself is
# intentionally not capped at 2**31 - 1 like a C int.
MAX_SEQUENCE_DIGITS = 30

# Absolute deadline for the whole request, not a per-read timeout that a slow
# client could renew indefinitely. It is deliberately larger than the 1 s
# internal wait used by MonitorState.next_frame.
REQUEST_DEADLINE_SECONDS = 5.0
MAX_REQUEST_LINE = 4096
MAX_HEADERS_BYTES = 8192
# http.client already rejects the 100th header, so keep our own limit at the
# largest value that can actually reach this handler.
MAX_HEADER_COUNT = 99

_CSP_BASE = (
    "default-src 'self'; frame-ancestors 'none'; base-uri 'none'; "
    "object-src 'none'; form-action 'none'; connect-src 'self'; "
    "img-src 'self' blob:;"
)

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": (
        "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()"
    ),
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
}

_SAFE_ERROR_MESSAGES = {
    400: "Bad request",
    403: "Forbidden",
    404: "Not found",
    405: "Method not allowed",
    413: "Payload too large",
    414: "Request URI too long",
    429: "Too many requests",
    431: "Request header fields too large",
    500: "Internal server error",
    501: "Not implemented",
    503: "Service unavailable",
    505: "HTTP version not supported",
}

_FRAME_PARAMETERS = frozenset({"after"})


def csp_for(nonce: str) -> str:
    """Build a CSP with the given nonce for both inline style and script."""
    return f"{_CSP_BASE} script-src 'self' 'nonce-{nonce}'; style-src 'self' 'nonce-{nonce}';"


def security_headers(nonce: str) -> dict[str, str]:
    """Return the complete header set shared by success, error and early 503."""
    return {**_SECURITY_HEADERS, "Content-Security-Policy": csp_for(nonce)}


class Handler(BaseHTTPRequestHandler):
    # ``send_response`` is overridden below, so these are never emitted.
    server_version = ""
    sys_version = ""
    default_request_version = "HTTP/1.0"

    def setup(self):
        self._nonce = secrets.token_urlsafe(16)
        self._request_id = uuid.uuid4().hex
        super().setup()

    def version_string(self):
        return "monitor"

    @property
    def _monitor_server(self) -> "MonitorHTTPServer":
        return cast("MonitorHTTPServer", self.server)

    def __getattr__(self, name):
        """Answer any unknown ``do_<METHOD>`` with 405 instead of 501."""
        if name.startswith("do_"):
            return self._method_not_allowed
        raise AttributeError(name)

    def _method_not_allowed(self):
        self._send_error(405, "Method not allowed", allow_get=True)

    def send_response(self, code, message=None):
        """Send the status line and Date without the native Server banner."""
        self.send_response_only(code, message)
        self.send_header("Date", self.date_time_string())

    def send_error(self, code, message=None, explain=None):
        """Rewrite framework errors into the versioned JSON error contract."""
        self._send_error(code, _SAFE_ERROR_MESSAGES.get(code, "Request error"))

    def _send_error(self, code, message, *, code_name=None, retry_after=None, allow_get=False):
        code_name = code_name or (codes.VALIDATION_FAILED if 400 <= code < 500 else codes.INTERNAL_ERROR)
        body = dumps_json(error_envelope(code_name, message, self._request_id)).encode()
        self._respond(code, "application/json", body, retry_after=retry_after, allow_get=allow_get)

    def _send_exception(self, error: BaseException):
        code_name, message, code = describe_error(error)
        details = error.as_dict() if isinstance(error, VisionCoreError) else {"code": code_name, "message": message}
        _LOGGER.error("monitor_error request_id=%s error=%s", self._request_id, details, exc_info=True)
        retry_after = 1 if code == 503 and getattr(error, "retryable", False) else None
        self._send_error(code, message, code_name=code_name, retry_after=retry_after)

    def _respond(self, code, kind, body, *, sequence=None, retry_after=None, allow_get=False):
        self.send_response(code)
        # A 204 must not advertise a body type or length.
        if code != 204 and kind:
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
        for name, value in security_headers(self._nonce).items():
            self.send_header(name, value)
        self.send_header("X-Request-ID", self._request_id)
        path = getattr(self, "path", "") or ""
        if path.startswith(f"{LEGACY_PREFIX}/") and not path.startswith(f"{API_PREFIX}/"):
            self.send_header("Deprecation", "true")
        if sequence is not None:
            self.send_header("X-Frame-Sequence", str(sequence))
        if retry_after is not None:
            self.send_header("Retry-After", str(retry_after))
        if allow_get:
            self.send_header("Allow", "GET")
        self.end_headers()
        # RFC 9110: HEAD and 204 never carry content, even for an error status.
        if code != 204 and self.command != "HEAD" and body:
            self._write(body)

    def _write(self, body):
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def handle_one_request(self):
        """Read with hard limits and an absolute deadline before dispatching."""
        metrics = self._monitor_server.limits_metrics
        self._nonce = secrets.token_urlsafe(16)
        self._request_id = uuid.uuid4().hex
        self._deadline = time.monotonic() + REQUEST_DEADLINE_SECONDS
        # Early rejections happen before parse_request() normally sets these.
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

            # parse_request() expects to pull headers from self.rfile; feed it
            # the already bounded bytes so it cannot read past our limit.
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
        except ValueError:
            self._send_error(400, "Invalid URL")
            return
        try:
            query = parse_qs(url.query, keep_blank_values=True, strict_parsing=True)
        except ValueError:
            self._send_error(400, "Invalid query string")
            return

        try:
            result = self._route(url, query)
        except Exception as error:  # noqa: BLE001 - el contrato HTTP debe seguir siendo JSON
            self._send_exception(error)
            return
        if result is None:
            return
        body, kind, code, sequence, retry_after = result
        self._respond(code, kind, body, sequence=sequence, retry_after=retry_after)

    def _route(self, url: SplitResult, query: dict[str, list[str]]):
        path = url.path
        server = cast("MonitorHTTPServer", self.server)
        if path == "/":
            if query:
                raise ValidationError("Query parameters are not allowed")
            page = server.page.replace(b"__CSP_NONCE__", self._nonce.encode("ascii"))
            return page, "text/html; charset=utf-8", 200, None, None
        if path in (f"{API_PREFIX}/state", f"{LEGACY_PREFIX}/state"):
            if query:
                raise ValidationError("Query parameters are not allowed")
            response = server.get_snapshot.execute(RequestSnapshot())
            return dumps_json(response).encode(), "application/json", 200, None, None
        if path in (f"{API_PREFIX}/frame", f"{LEGACY_PREFIX}/frame"):
            return self._frame(query, server)
        if path in ("/health", "/ready", "/metrics"):
            if query:
                raise ValidationError("Query parameters are not allowed")
            return self._operations(path, server)
        raise VisionCoreError(
            "La ruta solicitada no existe.",
            code=codes.REQUEST_NOT_FOUND,
            retryable=False,
        )

    @staticmethod
    def _operations(path: str, server: "MonitorHTTPServer"):
        if path == "/health":
            body = dumps_json({"status": "alive", "live": True}).encode()
            return body, "application/json", 200, None, None
        if path == "/ready":
            server.get_snapshot.execute(RequestSnapshot())
            readiness = server.health.snapshot() if server.health is not None else {"ready": False, "checks": {}}
            return (
                dumps_json(readiness).encode(),
                "application/json",
                200 if readiness["ready"] else 503,
                None,
                None,
            )
        metrics = (
            server.metrics.snapshot()
            if server.metrics is not None
            else {"counters": {}, "gauges": {}, "histograms": {}, "uptime_seconds": 0}
        )
        return dumps_json(metrics).encode(), "application/json", 200, None, None

    def _frame(self, query: dict[str, list[str]], server: "MonitorHTTPServer"):
        unknown = set(query) - _FRAME_PARAMETERS
        if unknown:
            raise ValidationError("Unknown query parameter", context={"parameter": sorted(unknown)[0]})

        after = None
        if "after" in query:
            values = query["after"]
            if len(values) != 1:
                raise ValidationError("Duplicate 'after' parameter", context={"parameter": "after"})
            raw = values[0]
            if not raw.isascii() or not raw.isdigit() or len(raw) > MAX_SEQUENCE_DIGITS:
                raise ValidationError("Invalid frame number", context={"parameter": "after"})
            after = int(raw)

        if not server.long_poll_slots.acquire(blocking=False):
            server.limits_metrics.record("long_poll_concurrency")
            self._send_error(503, "Service unavailable", retry_after=1)
            return None
        try:
            response = server.get_frame.execute(RequestFrame(after))
        finally:
            server.long_poll_slots.release()

        body, sequence = response.jpeg, response.sequence
        if after is None:
            if not body:
                raise VisionCoreError(
                    "Todavía no hay video disponible.",
                    code=codes.VIDEO_FRAME_PENDING,
                    retryable=True,
                )
            return body, "image/jpeg", 200, sequence, None
        if not body:
            return b"", "image/jpeg", 204, sequence, None
        return body, "image/jpeg", 200, sequence, None

    def log_message(self, *args):
        pass
