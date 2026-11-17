import json
import threading
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from infrastructure.monitor.http_server import make_server
from infrastructure.monitor.state import MonitorState


@pytest.fixture
def monitor_server():
    state = MonitorState()
    server = make_server('127.0.0.1', 0, state)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        yield server, state
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_http_routes_keep_monitor_contract(monitor_server):
    server, state = monitor_server
    base_url = f'http://127.0.0.1:{server.server_port}'
    state.publish(b'jpeg', [], 4)

    with urlopen(f'{base_url}/') as response:
        assert response.status == 200
        assert response.headers['Content-Type'] == 'text/html; charset=utf-8'

    with urlopen(f'{base_url}/api/state') as response:
        body = json.load(response)
        assert body['status'] == 'running'
        assert body['frame'] == 1

    with urlopen(f'{base_url}/api/frame') as response:
        assert response.status == 200
        assert response.read() == b'jpeg'
        assert response.headers['X-Frame-Sequence'] == '1'

    with pytest.raises(HTTPError) as error:
        urlopen(f'{base_url}/api/frame?after=-1')
    assert error.value.code == 400
