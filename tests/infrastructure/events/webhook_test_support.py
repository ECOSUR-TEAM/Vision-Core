"""Servidor HTTP local que registra peticiones y simula fallos temporales."""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class RecordingHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        state = self.server.state
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        state["requests"].append(
            {
                "path": self.path,
                "headers": dict(self.headers),
                "body": json.loads(body),
            }
        )
        if state.get("delay"):
            time.sleep(state["delay"])
        if state.get("permanent_status") is not None:
            status = state["permanent_status"]
        elif len(state["requests"]) <= state.get("fail_times", 0):
            status = 500
        else:
            status = 200
        self.send_response(status)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return None


def start_recording_server(**state) -> tuple[ThreadingHTTPServer, threading.Thread]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), RecordingHandler)
    server.state = {"requests": [], **state}
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def stop_recording_server(server: ThreadingHTTPServer, thread: threading.Thread) -> None:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
