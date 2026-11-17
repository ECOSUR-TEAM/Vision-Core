"""HTTP server for monitor telemetry and frames."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


def make_server(host, port, state):
    page = Path(__file__).with_name('index.html').read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            url = urlsplit(self.path)
            path = url.path
            sequence = None
            if path == '/':
                body, kind, code = page, 'text/html; charset=utf-8', 200
            elif path == '/api/state':
                body = json.dumps(state.snapshot(), allow_nan=False).encode()
                kind, code = 'application/json', 200
            elif path == '/api/frame':
                query = parse_qs(url.query)
                if 'after' in query:
                    try:
                        after = int(query['after'][0])
                        if after < 0:
                            raise ValueError
                    except ValueError:
                        self.send_error(400, 'Invalid frame number')
                        return
                    body, sequence = state.next_frame(after)
                    kind, code = 'image/jpeg', 200 if body else 204
                    body = body or b''
                else:
                    with state.lock:
                        body, sequence = state.jpeg, state.sequence
                    kind, code = 'image/jpeg', 200 if body else 503
                    body = body or b'Esperando video'
            else:
                body, kind, code = b'Not found', 'text/plain', 404
            self.send_response(code)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            if sequence is not None:
                self.send_header('X-Frame-Sequence', str(sequence))
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def log_message(self, *args):
            pass

    return ThreadingHTTPServer((host, port), Handler)
