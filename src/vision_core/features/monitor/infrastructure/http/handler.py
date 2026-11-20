"""Validación de métodos y parámetros del monitor, sin tocar el contrato HTTP."""

import logging
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

# El número de secuencia es un int de Python ilimitado; solo se acota el número
# de dígitos para evitar parsing patológico, no se lo reduce a un int de C.
MAX_SEQUENCE_DIGITS = 30
_FRAME_PARAMETERS = frozenset({"after"})


class Handler(BaseHTTPRequestHandler):
    def __getattr__(self, name):
        """Cualquier método distinto de GET termina en 405, no en 501."""
        if name.startswith("do_"):
            return self._method_not_allowed
        raise AttributeError(name)

    def _method_not_allowed(self):
        self._send_error(405, "Method not allowed", codes.VALIDATION_FAILED, allow_get=True)

    def do_GET(self):
        request_id = uuid.uuid4().hex
        try:
            url = urlsplit(self.path)
            query = parse_qs(url.query, keep_blank_values=True, strict_parsing=True)
        except ValueError:
            self._send_error(400, "Invalid query string", codes.VALIDATION_FAILED, request_id)
            return
        try:
            body, kind, code, sequence = self._route(url, query)
        except Exception as error:
            code_name, message, code = describe_error(error)
            details = error.as_dict() if isinstance(error, VisionCoreError) else {"code": code_name, "message": message}
            body = dumps_json(error_envelope(code_name, message, request_id)).encode()
            kind, sequence = "application/json", None
            _LOGGER.error("monitor_error request_id=%s error=%s", request_id, details, exc_info=True)
        self._respond(request_id, url.path, code, kind, body, sequence)

    def _send_error(self, code, message, code_name, request_id=None, *, allow_get=False):
        request_id = request_id or uuid.uuid4().hex
        body = dumps_json(error_envelope(code_name, message, request_id)).encode()
        self._respond(request_id, getattr(self, "path", ""), code, "application/json", body, None, allow_get=allow_get)

    def _route(self, url: SplitResult, query: dict[str, list[str]]):
        path = url.path
        server = cast("MonitorHTTPServer", self.server)
        if path == "/":
            if query:
                raise ValidationError("Query parameters are not allowed")
            return server.page, "text/html; charset=utf-8", 200, None
        if path in (f"{API_PREFIX}/state", f"{LEGACY_PREFIX}/state"):
            if query:
                raise ValidationError("Query parameters are not allowed")
            response = server.get_snapshot.execute(RequestSnapshot())
            return dumps_json(response).encode(), "application/json", 200, None
        if path in (f"{API_PREFIX}/frame", f"{LEGACY_PREFIX}/frame"):
            return self._frame(query)
        if path == "/health":
            if query:
                raise ValidationError("Query parameters are not allowed")
            return dumps_json({"status": "alive", "live": True}).encode(), "application/json", 200, None
        if path == "/ready":
            if query:
                raise ValidationError("Query parameters are not allowed")
            server.get_snapshot.execute(RequestSnapshot())
            readiness = server.health.snapshot() if server.health is not None else {"ready": False, "checks": {}}
            return dumps_json(readiness).encode(), "application/json", 200 if readiness["ready"] else 503, None
        if path == "/metrics":
            if query:
                raise ValidationError("Query parameters are not allowed")
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

    def _frame(self, query: dict[str, list[str]]):
        server = cast("MonitorHTTPServer", self.server)
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

        if after is None:
            response = server.get_frame.execute(RequestFrame())
            if response.jpeg:
                return response.jpeg, "image/jpeg", 200, response.sequence
            raise VisionCoreError(
                "Todavía no hay video disponible.",
                code=codes.VIDEO_FRAME_PENDING,
                retryable=True,
            )
        response = server.get_frame.execute(RequestFrame(after))
        if response.jpeg:
            return response.jpeg, "image/jpeg", 200, response.sequence
        return b"", "image/jpeg", 204, response.sequence

    def _respond(self, request_id, path, code, kind, body, sequence, *, allow_get=False):
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
        if allow_get:
            self.send_header("Allow", "GET")
        self.end_headers()
        # RFC 9110: HEAD solo devuelve estado y cabeceras, nunca contenido.
        if self.command != "HEAD":
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def log_message(self, *args):
        pass
