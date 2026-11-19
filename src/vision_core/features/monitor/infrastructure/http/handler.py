import logging
import uuid
from http.server import BaseHTTPRequestHandler
from urllib.parse import ParseResult, parse_qs, urlsplit

from vision_core.features.monitor.application.dto.request.request_frame import RequestFrame
from vision_core.features.monitor.application.dto.request.request_snapshot import RequestSnapshot
from vision_core.features.monitor.infrastructure.http.api import API_PREFIX, LEGACY_PREFIX
from vision_core.features.monitor.infrastructure.http.error_response import describe_error, error_envelope
from vision_core.shared.application.dto.serialization import dumps_json
from vision_core.shared.errors import ValidationError, VisionCoreError, codes

_LOGGER = logging.getLogger(__name__)


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

    def _route(self, url: ParseResult):
        path = url.path
        if path == "/":
            return self.server.page, "text/html; charset=utf-8", 200, None
        if path in (f"{API_PREFIX}/state", f"{LEGACY_PREFIX}/state"):
            response = self.server.get_snapshot.execute(RequestSnapshot())
            body = dumps_json(response).encode()
            return body, "application/json", 200, None
        if path in (f"{API_PREFIX}/frame", f"{LEGACY_PREFIX}/frame"):
            return self._frame(url)
        raise VisionCoreError(
            "La ruta solicitada no existe.",
            code=codes.REQUEST_NOT_FOUND,
            retryable=False,
        )

    def _frame(self, url: ParseResult):
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
            response = self.server.get_frame.execute(RequestFrame(after))
            if response.jpeg:
                return response.jpeg, "image/jpeg", 200, response.sequence
            return b"", "image/jpeg", 204, response.sequence
        response = self.server.get_frame.execute(RequestFrame())
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
