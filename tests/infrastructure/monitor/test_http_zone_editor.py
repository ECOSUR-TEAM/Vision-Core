"""Contrato HTTP del editor de zonas: carga, validación y guardado controlado."""

import json
import threading
from http.client import HTTPConnection

import pytest

from vision_core.core.errors import codes
from vision_core.features.monitor.infrastructure.http.server import make_server
from vision_core.features.monitor.infrastructure.state import MonitorState
from vision_core.features.monitor.infrastructure.zone_editor.config import ZoneEditorConfig
from vision_core.features.monitor.infrastructure.zone_editor.service import ZoneEditorService

TOKEN = "token-http"
ZONES = {
    "version": "1.0",
    "frame_size": [640, 480],
    "door": [[290, 120], [350, 120], [350, 420], [290, 420]],
    "exterior": [[0, 0], [320, 0], [320, 479], [0, 479]],
    "interior": [[320, 0], [639, 0], [639, 479], [320, 479]],
}
AUTH = {"Authorization": f"Bearer {TOKEN}", "X-Vision-User": "operador"}


@pytest.fixture
def editor_server(tmp_path):
    path = tmp_path / "zones.json"
    path.write_text(json.dumps(ZONES), encoding="utf-8")
    config = ZoneEditorConfig(enabled=True, zones_file=path, editor_token=TOKEN, audit_file=tmp_path / "audit.jsonl")
    server = make_server("127.0.0.1", 0, MonitorState(), zone_editor=ZoneEditorService(config))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, path, ("127.0.0.1", server.server_port)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def _request(address, method, path, body=None, headers=None):
    connection = HTTPConnection(*address, timeout=5)
    encoded = json.dumps(body).encode() if body is not None else None
    extra = dict(headers or {})
    if encoded is not None:
        extra.setdefault("Content-Type", "application/json")
    connection.request(method, path, body=encoded, headers=extra)
    response = connection.getresponse()
    payload = response.read()
    result = (response.status, dict(response.getheaders()), json.loads(payload) if payload else None)
    connection.close()
    return result


def test_get_zones_exposes_document_and_editor_metadata(editor_server):
    _, _, address = editor_server

    status, headers, payload = _request(address, "GET", "/api/v1/zones")

    assert status == 200
    assert payload["zones"] == ZONES
    assert payload["editor"]["enabled"] is True
    assert payload["editor"]["can_save"] is False
    assert payload["editor"]["schema_version"] == "1.0"
    assert headers["X-Request-ID"]


def test_put_saves_a_valid_edited_vertex(editor_server):
    _, path, address = editor_server
    edited = json.loads(json.dumps(ZONES))
    edited["door"][0] = [280, 120]

    status, _, payload = _request(address, "PUT", "/api/v1/zones", edited, AUTH)

    assert status == 200
    assert json.loads(path.read_text(encoding="utf-8")) == edited
    assert payload["zones"] == edited
    assert payload["audit"]["user"] == "operador"


def test_put_rejects_invalid_polygon_without_saving(editor_server):
    _, path, address = editor_server
    invalid = json.loads(json.dumps(ZONES))
    invalid["door"] = [[1, 1], [2, 2]]

    status, _, payload = _request(address, "PUT", "/api/v1/zones", invalid, AUTH)

    assert status == 422
    assert payload["error"]["code"] == codes.ZONE_GEOMETRY_INVALID
    assert json.loads(path.read_text(encoding="utf-8")) == ZONES


def test_put_without_permission_is_forbidden(editor_server):
    _, path, address = editor_server

    status, _, payload = _request(address, "PUT", "/api/v1/zones", ZONES)

    assert status == 403
    assert payload["error"]["code"] == codes.ZONE_EDITOR_FORBIDDEN
    assert json.loads(path.read_text(encoding="utf-8")) == ZONES


def test_post_validates_without_writing(editor_server):
    _, path, address = editor_server
    edited = json.loads(json.dumps(ZONES))
    edited["door"][0] = [280, 120]

    status, _, payload = _request(address, "POST", "/api/v1/zones/validate", edited)

    assert status == 200
    assert payload["zones"] == edited
    assert json.loads(path.read_text(encoding="utf-8")) == ZONES

    invalid = json.loads(json.dumps(ZONES))
    invalid["door"] = [[1, 1], [2, 2]]
    status, _, payload = _request(address, "POST", "/api/v1/zones/validate", invalid)
    assert status == 422
    assert payload["error"]["code"] == codes.ZONE_GEOMETRY_INVALID


def test_oversized_payload_is_rejected(editor_server):
    _, _, address = editor_server
    oversized = json.loads(json.dumps(ZONES))
    oversized["exterior"] = "x" * (101 * 1024)

    status, _, payload = _request(address, "PUT", "/api/v1/zones", oversized, AUTH)

    assert status == 413
    assert payload["error"]["code"] == codes.VALIDATION_FAILED


def test_duplicate_keys_and_wrong_content_type_are_rejected(editor_server):
    _, _, address = editor_server
    connection = HTTPConnection(*address, timeout=5)
    connection.request(
        "PUT",
        "/api/v1/zones",
        body=b'{"version":"1.0","version":"1.0"}',
        headers={"Content-Type": "application/json", **AUTH},
    )
    response = connection.getresponse()
    payload = json.loads(response.read())
    connection.close()
    assert response.status == 422
    assert payload["error"]["code"] == codes.ZONE_CONFIG_INVALID

    connection = HTTPConnection(*address, timeout=5)
    connection.request("PUT", "/api/v1/zones", body=json.dumps(ZONES), headers={"Content-Type": "text/plain", **AUTH})
    response = connection.getresponse()
    payload = json.loads(response.read())
    connection.close()
    assert response.status == 400
    assert payload["error"]["code"] == codes.VALIDATION_FAILED


def test_legacy_alias_is_available_and_marked_deprecated(editor_server):
    _, _, address = editor_server

    status, headers, payload = _request(address, "GET", "/api/zones")

    assert status == 200
    assert payload["zones"] == ZONES
    assert headers["Deprecation"] == "true"


def test_zone_routes_reject_query_parameters(editor_server):
    _, _, address = editor_server

    assert _request(address, "GET", "/api/v1/zones?extra=1")[0] == 400
    assert _request(address, "POST", "/api/v1/zones/validate?extra=1", ZONES)[0] == 400


def test_editor_disabled_by_flag_returns_not_found():
    server = make_server("127.0.0.1", 0, MonitorState())
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        address = ("127.0.0.1", server.server_port)
        status, _, payload = _request(address, "GET", "/api/v1/zones")
        assert status == 404
        assert payload["error"]["code"] == codes.REQUEST_NOT_FOUND
        status, _, payload = _request(address, "PUT", "/api/v1/zones", ZONES, AUTH)
        assert status == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
