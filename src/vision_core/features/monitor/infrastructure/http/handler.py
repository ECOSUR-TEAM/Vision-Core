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


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        request_id = uuid.uuid4().hex
        url = urlsplit(self.path)
        try:
            body, kind, code, sequence = self._route(url)
        except Exception as error:
            code_name, message, code = describe_error(error)
            details = error.as_dict() if isinstance(error, VisionCoreError) else {"code": code_name, "message": message}
            body = dumps_json(error_envelope(code_name, message, request_id)).encode()
            kind, sequence = "application/json", None
            _LOGGER.error("monitor_error request_id=%s error=%s", request_id, details, exc_info=True)
        self._respond(request_id, url.path, code, kind, body, sequence)

    def _route(self, url: SplitResult):
        path = url.path
        server = cast("MonitorHTTPServer", self.server)
        if path == "/":
            return server.page, "text/html; charset=utf-8", 200, None
        if path in (f"{API_PREFIX}/state", f"{LEGACY_PREFIX}/state"):
            response = server.get_snapshot.execute(RequestSnapshot())
            body = dumps_json(response).encode()
            return body, "application/json", 200, None
        if path in (f"{API_PREFIX}/frame", f"{LEGACY_PREFIX}/frame"):
            return self._frame(url)
        if path == "/health":
            body = dumps_json({"status": "alive", "live": True}).encode()
            return body, "application/json", 200, None
        if path == "/ready":
            server.get_snapshot.execute(RequestSnapshot())
            readiness = server.health.snapshot() if server.health is not None else {"ready": False, "checks": {}}
            body = dumps_json(readiness).encode()
            return body, "application/json", 200 if readiness["ready"] else 503, None
        if path == "/metrics":
            metrics = (
                server.metrics.snapshot()
                if server.metrics is not None
                else {
                    "counters": {},
                    "gauges": {},
                    "histograms": {},
                    "uptime_seconds": 0,
                }
            )
            body = dumps_json(metrics).encode()
            return body, "application/json", 200, None
        raise VisionCoreError(
            "La ruta solicitada no existe.",
            code=codes.REQUEST_NOT_FOUND,
            retryable=False,
        )

    def _frame(self, url: SplitResult):
        server = cast("MonitorHTTPServer", self.server)
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

    def _respond(self, request_id, path, code, kind, body, sequence):
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
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, *args):
        pass
