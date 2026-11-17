from http.server import ThreadingHTTPServer
from pathlib import Path

from vision_core.features.monitor.application.use_cases.get_frame import GetFrame
from vision_core.features.monitor.application.use_cases.get_snapshot import GetSnapshot
from vision_core.features.monitor.infrastructure.http.handler import Handler


class MonitorHTTPServer(ThreadingHTTPServer):
    def __init__(self, address, page, get_snapshot, get_frame):
        super().__init__(address, Handler)
        self.page = page
        self.get_snapshot = get_snapshot
        self.get_frame = get_frame


def make_server(host, port, state, page_path=None):
    default_page = Path(__file__).parents[6] / "infrastructure/monitor/index.html"
    page = Path(page_path or default_page).read_bytes()
    return MonitorHTTPServer(
        (host, port),
        page,
        GetSnapshot(state),
        GetFrame(state),
    )
