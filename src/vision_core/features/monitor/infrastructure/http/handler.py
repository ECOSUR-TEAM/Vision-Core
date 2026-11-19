from http.server import BaseHTTPRequestHandler
from typing import TYPE_CHECKING, cast
from urllib.parse import parse_qs, urlsplit

from vision_core.features.monitor.application.dto.request.request_frame import RequestFrame
from vision_core.features.monitor.application.dto.request.request_snapshot import RequestSnapshot
from vision_core.shared.application.dto.serialization import dumps_json

if TYPE_CHECKING:
    from vision_core.features.monitor.infrastructure.http.server import MonitorHTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlsplit(self.path)
        path = url.path
        sequence = None
        server = cast("MonitorHTTPServer", self.server)
        if path == "/":
            body, kind, code = server.page, "text/html; charset=utf-8", 200
        elif path == "/api/state":
            response = server.get_snapshot.execute(RequestSnapshot())
            body = dumps_json(response).encode()
            kind, code = "application/json", 200
        elif path == "/api/frame":
            query = parse_qs(url.query)
            if "after" in query:
                try:
                    after = int(query["after"][0])
                    if after < 0:
                        raise ValueError
                except ValueError:
                    self.send_error(400, "Invalid frame number")
                    return
                response = server.get_frame.execute(RequestFrame(after))
                body, sequence = response.jpeg, response.sequence
                kind, code = "image/jpeg", 200 if body else 204
                body = body or b""
            else:
                response = server.get_frame.execute(RequestFrame())
                body, sequence = response.jpeg, response.sequence
                kind, code = "image/jpeg", 200 if body else 503
                body = body or b"Esperando video"
        else:
            body, kind, code = b"Not found", "text/plain", 404
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if sequence is not None:
            self.send_header("X-Frame-Sequence", str(sequence))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, *args):
        pass
