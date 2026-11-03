"""Bounded in-memory telemetry and a local HTTP view. No inference per viewer."""
import json
import threading
import time
from collections import Counter, deque
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import cv2
import numpy as np


class MonitorState:
    def __init__(self, demo=False):
        self.lock = threading.Lock()
        self.status = 'starting'
        self.error = None
        self.demo = demo
        self.jpeg = None
        self.updated = None
        self.previous = None
        self.sequence = 0
        self.people = []
        self.events = deque(maxlen=100)
        self.counts = Counter()
        self.processing_ms = 0.
        self.fps = 0.
        self.dropped = 0

    def set_status(self, status, error=None):
        with self.lock:
            self.status, self.error = status, error

    def event(self, event):
        with self.lock:
            self.events.appendleft(event.to_dict())
            self.counts[event.event] += 1

    def publish(self, frame, tracks, processing_ms, zones, analytics, dropped=0):
        annotated = frame.copy()
        for polygon, color in [(zones.exterior, (220, 175, 90)),
                               (zones.interior, (150, 210, 100)),
                               (zones.door, (70, 200, 240))]:
            points = np.array(polygon.points, dtype=np.int32)
            cv2.polylines(annotated, [points], True, color, 1, cv2.LINE_AA)
            x, y = points[0]
            cv2.putText(annotated, polygon.name, (int(x)+5, int(y)+18),
                        cv2.FONT_HERSHEY_SIMPLEX, .45, color, 1, cv2.LINE_AA)
        people = []
        for track in tracks:
            history = analytics.get_history(track.person_id)
            zone = history[-1].zone if history else 'fuera'
            people.append({**asdict(track), 'zone': zone})
            box = track.bbox
            x1, y1, x2, y2 = map(int, (box.x1, box.y1, box.x2, box.y2))
            color = (150, 240, 175)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            cv2.circle(annotated, tuple(map(int, box.center)), 3, color, -1)
            label = f'{track.person_id[:8]} | T{track.track_id} | {track.confidence:.0%}'
            cv2.putText(annotated, label, (x1, max(18, y1-8)),
                        cv2.FONT_HERSHEY_SIMPLEX, .45, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(annotated, label, (x1, max(18, y1-8)),
                        cv2.FONT_HERSHEY_SIMPLEX, .45, color, 1, cv2.LINE_AA)
        ok, jpeg = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ok:
            raise RuntimeError('No se pudo codificar el frame')
        now = time.monotonic()
        with self.lock:
            if self.previous is not None:
                current = 1 / max(now - self.previous, .000001)
                self.fps = current if not self.fps else .8*self.fps + .2*current
            self.previous = now
            self.updated = time.time()
            self.sequence += 1
            self.jpeg = jpeg.tobytes()
            self.people = people
            self.processing_ms = processing_ms
            self.dropped = dropped
            self.status = 'running'

    def snapshot(self):
        with self.lock:
            age = time.time()-self.updated if self.updated is not None else None
            status = 'stale' if self.status == 'running' and age > 5 else self.status
            return {'status': status, 'error': self.error, 'demo_zones': self.demo,
                    'frame': self.sequence, 'updated_at': self.updated, 'age_seconds': age,
                    'people': self.people if status == 'running' else [],
                    'events': list(self.events), 'counts': dict(self.counts),
                    'processing_ms': self.processing_ms, 'fps': self.fps,
                    'dropped_frames': self.dropped}


def make_server(host, port, state):
    page = Path(__file__).with_name('index.html').read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = self.path.split('?', 1)[0]
            if path == '/':
                body, kind, code = page, 'text/html; charset=utf-8', 200
            elif path == '/api/state':
                body = json.dumps(state.snapshot(), allow_nan=False).encode()
                kind, code = 'application/json', 200
            elif path == '/api/frame':
                with state.lock:
                    body = state.jpeg
                kind, code = 'image/jpeg', 200 if body else 503
                body = body or b'Esperando video'
            else:
                body, kind, code = b'Not found', 'text/plain', 404
            self.send_response(code)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def log_message(self, *args):
            pass

    return ThreadingHTTPServer((host, port), Handler)
