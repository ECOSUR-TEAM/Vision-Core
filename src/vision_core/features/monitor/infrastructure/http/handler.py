import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlsplit

from vision_core.features.monitor.application.dto.request.request_frame import RequestFrame
from vision_core.features.monitor.application.dto.request.request_snapshot import RequestSnapshot


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlsplit(self.path)
        path = url.path
        sequence = None
        if path == "/":
            body, kind, code = self.server.page, "text/html; charset=utf-8", 200
        elif path == "/api/state":
            response = self.server.get_snapshot.execute(RequestSnapshot())
            body = json.dumps(response.__dict__, allow_nan=False).encode()
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
                response = self.server.get_frame.execute(RequestFrame(after))
                body, sequence = response.jpeg, response.sequence
                kind, code = "image/jpeg", 200 if body else 204
                body = body or b""
            else:
                response = self.server.get_frame.execute(RequestFrame())
                body, sequence = response.jpeg, response.sequence
                kind, code = "image/jpeg", 200 if body else 503
                body = body or b"Esperando video"
        elif path == "/health":
            body = json.dumps({"status": "alive", "live": True}, allow_nan=False).encode()
            kind, code = "application/json", 200
        elif path == "/ready":
            self.server.get_snapshot.execute(RequestSnapshot())
            readiness = (
                self.server.health.snapshot() if self.server.health is not None else {"ready": False, "checks": {}}
            )
            body = json.dumps(readiness, allow_nan=False).encode()
            kind, code = "application/json", 200 if readiness["ready"] else 503
        elif path == "/metrics":
            metrics = (
                self.server.metrics.snapshot()
                if self.server.metrics is not None
                else {
                    "counters": {},
                    "gauges": {},
                    "histograms": {},
                    "uptime_seconds": 0,
                }
            )
            body = json.dumps(metrics, allow_nan=False).encode()
            kind, code = "application/json", 200
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
