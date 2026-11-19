"""HTTP routing, input validation, resource limits and security headers.

Only ``GET`` is allowed, and only ``/``, ``/api/state`` and ``/api/frame``
exist. Every response carries the same restrictive security header set and the
single-page UI uses a per-request nonce, so no inline script/style needs
``unsafe-inline`` in the Content Security Policy.

Validation failures are answered with a small JSON error object; framework
errors are rewritten here so they never leak the native server banner, internal
paths or tracebacks. Request line, headers and bodies are bounded before normal
routing, and an absolute request deadline protects against slow clients while
still allowing the intentional (maximum 1 second) long-poll of ``/api/frame``.
"""

import io
import json
import secrets
import time
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlsplit

from vision_core.features.monitor.application.dto.request.request_frame import RequestFrame
from vision_core.features.monitor.application.dto.request.request_snapshot import RequestSnapshot

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
        "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
        "magnetometer=(), microphone=(), payment=(), usb=()"
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

_ALLOWED_PATHS = frozenset({"/", "/api/state", "/api/frame"})
_FRAME_PARAMETERS = frozenset({"after"})


def csp_for(nonce: str) -> str:
    """Build a CSP with the given nonce for both inline style and script."""
    return f"{_CSP_BASE} script-src 'self' 'nonce-{nonce}'; " f"style-src 'self' 'nonce-{nonce}';"


def security_headers(nonce: str) -> dict[str, str]:
    """Return the complete header set shared by success, error and early 503."""
    return {**_SECURITY_HEADERS, "Content-Security-Policy": csp_for(nonce)}


class Handler(BaseHTTPRequestHandler):
    # ``send_response`` is overridden below, so these are never emitted.
    server_version = ""
    sys_version = ""
    default_request_version = "HTTP/1.0"

    def setup(self):
        # The nonce is created per request in handle_one_request(), not per
        # connection, so keep-alive can never reuse a CSP token.
        self._nonce = secrets.token_urlsafe(16)
        super().setup()

    def version_string(self):
        return "monitor"

    def __getattr__(self, name):
        """Answer any unknown ``do_<METHOD>`` with 405 instead of 501."""
        if name.startswith("do_"):
            return self._method_not_allowed
        raise AttributeError(name)

    def _method_not_allowed(self):
        self._send_error(405, "Method not allowed")

    def send_response(self, code, message=None):
        """Send the status line and Date without the native Server banner."""
        self.send_response_only(code, message)
        self.send_header("Date", self.date_time_string())

    def send_error(self, code, message=None, explain=None):
        """Rewrite framework errors into the API's JSON error contract."""
        self._send_error(code, _SAFE_ERROR_MESSAGES.get(code, "Request error"))

    def _send_security_headers(self):
        for name, value in security_headers(self._nonce).items():
            self.send_header(name, value)

    def _send_error(self, code, message, *, retry_after=None):
        body = json.dumps({"error": message}, allow_nan=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._send_security_headers()
        if retry_after is not None:
            self.send_header("Retry-After", str(retry_after))
        if code == 405:
            self.send_header("Allow", "GET")
        self.end_headers()
        # RFC 9110: a HEAD response has no content, even for an error status.
        if self.command != "HEAD":
            self._write(body)

    def _send_ok(self, code, body=b"", content_type=None, sequence=None):
        self.send_response(code)
        # A 204 must not advertise a body type or length.
        if code != 204 and content_type is not None:
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
        self._send_security_headers()
        if sequence is not None:
            self.send_header("X-Frame-Sequence", str(sequence))
        self.end_headers()
        if code != 204 and body:
            self._write(body)

    def _write(self, body):
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def handle_one_request(self):
        """Read with hard limits and an absolute deadline before dispatching."""
        metrics = self.server.metrics
        self._nonce = secrets.token_urlsafe(16)
        self._deadline = time.monotonic() + REQUEST_DEADLINE_SECONDS
        # Early rejections happen before parse_request() normally sets these.
        self.command = None
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
                self.server.metrics.record("oversized")
                self.send_error(431, "Headers too large")
                return None
            data.extend(line)
            if line in (b"\r\n", b"\n"):
                break
            count += 1
            if count > MAX_HEADER_COUNT:
                self.server.metrics.record("oversized")
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
            self.server.metrics.record("oversized")
            self._send_error(413, "Request body is not allowed")
            return True
        return False

    def do_GET(self):
        try:
            url = urlsplit(self.path)
        except ValueError:
            self._send_error(400, "Invalid URL")
            return

        path = url.path
        if path not in _ALLOWED_PATHS:
            self._send_error(404, "Not found")
            return

        try:
            query = parse_qs(url.query, keep_blank_values=True, strict_parsing=True)
        except ValueError:
            self._send_error(400, "Invalid query string")
            return

        if path in {"/", "/api/state"} and query:
            self._send_error(400, "Query parameters are not allowed")
            return

        if path == "/api/frame":
            self._get_frame(query)
        elif path == "/":
            page = self.server.page.replace(b"__CSP_NONCE__", self._nonce.encode())
            self._send_ok(200, page, "text/html; charset=utf-8")
        else:
            self._get_state()

    def _get_state(self):
        try:
            response = self.server.get_snapshot.execute(RequestSnapshot())
            body = json.dumps(response.__dict__, allow_nan=False).encode()
        except (TypeError, ValueError):
            self._send_error(400, "Invalid state request")
            return
        except Exception:  # noqa: BLE001 - el contrato HTTP debe seguir siendo JSON
            self._send_error(500, "Internal server error")
            return
        self._send_ok(200, body, "application/json")

    def _get_frame(self, query):
        if set(query) - _FRAME_PARAMETERS:
            self._send_error(400, "Unknown query parameter")
            return

        after = None
        if "after" in query:
            values = query["after"]
            if len(values) != 1:
                self._send_error(400, "Duplicate 'after' parameter")
                return
            raw = values[0]
            if not raw.isascii() or not raw.isdigit() or len(raw) > MAX_SEQUENCE_DIGITS:
                self._send_error(400, "Invalid frame number")
                return
            after = int(raw)

        if not self.server.long_poll_slots.acquire(blocking=False):
            self.server.metrics.record("long_poll_concurrency")
            self._send_error(503, "Service unavailable", retry_after=1)
            return
        try:
            response = self.server.get_frame.execute(RequestFrame(after))
        except (TypeError, ValueError):
            self._send_error(400, "Invalid frame request")
            return
        except Exception:  # noqa: BLE001 - el contrato HTTP debe seguir siendo JSON
            self._send_error(500, "Internal server error")
            return
        finally:
            self.server.long_poll_slots.release()

        body, sequence = response.jpeg, response.sequence
        if after is None:
            if not body:
                self._send_error(503, "Esperando video", retry_after=1)
                return
            self._send_ok(200, body, "image/jpeg", sequence)
            return
        if not body:
            self._send_ok(204, sequence=sequence)
            return
        self._send_ok(200, body, "image/jpeg", sequence)

    def log_message(self, *args):
        pass
