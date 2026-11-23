"""Editor de zonas: permisos, auditoría, validación y rollback."""

import hashlib
import json
import os
from pathlib import Path

import pytest

from vision_core.core.errors import VisionCoreError, codes
from vision_core.features.monitor.infrastructure.zone_editor.config import ZoneEditorConfig
from vision_core.features.monitor.infrastructure.zone_editor.service import ZoneEditorService

TOKEN = "clave-de-prueba"
AUTH = {"Authorization": f"Bearer {TOKEN}", "X-Vision-User": "operador"}
ZONES = {
    "version": "1.0",
    "frame_size": [640, 480],
    "door": [[290, 120], [350, 120], [350, 420], [290, 420]],
    "exterior": [[0, 0], [320, 0], [320, 479], [0, 479]],
    "interior": [[320, 0], [639, 0], [639, 479], [320, 479]],
}


def _service(tmp_path, *, audit=True, replace=None):
    path = tmp_path / "zones.json"
    path.write_text(json.dumps(ZONES), encoding="utf-8")
    config = ZoneEditorConfig(
        enabled=True,
        zones_file=path,
        editor_token=TOKEN,
        audit_file=tmp_path / "audit.jsonl" if audit else None,
    )
    return ZoneEditorService(config, replace=replace), path


def test_load_returns_valid_document_and_editor_capabilities(tmp_path):
    service, _ = _service(tmp_path)

    assert service.load() == ZONES
    assert service.describe(AUTH)["can_save"] is True
    assert service.describe({})["can_save"] is False
    assert service.describe(AUTH)["schema_version"] == "1.0"


def test_save_flow_updates_file_and_writes_audit(tmp_path):
    service, path = _service(tmp_path)
    previous_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    edited = json.loads(json.dumps(ZONES))
    edited["door"][0][0] = 280

    result = service.save(edited, AUTH)

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved == edited
    assert result["zones"] == saved
    entry = json.loads((tmp_path / "audit.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert entry["user"] == "operador"
    assert entry["timestamp"].endswith("+00:00")
    assert entry["previous_sha256"] == previous_hash
    assert entry["new_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()


def test_invalid_payload_is_rejected_without_touching_the_file(tmp_path):
    service, path = _service(tmp_path)
    before = path.read_bytes()
    invalid = json.loads(json.dumps(ZONES))
    invalid["door"] = [[1, 1], [2, 2]]

    with pytest.raises(VisionCoreError) as error:
        service.save(invalid, AUTH)

    assert error.value.code == codes.ZONE_GEOMETRY_INVALID
    assert path.read_bytes() == before


def test_xss_in_zone_name_is_rejected_and_not_written(tmp_path):
    service, path = _service(tmp_path)
    before = path.read_bytes()
    payload = "<script>alert(1)</script>"
    invalid = json.loads(json.dumps(ZONES))
    invalid[payload] = []

    with pytest.raises(VisionCoreError) as error:
        service.save(invalid, AUTH)

    assert error.value.code == codes.ZONE_CONFIG_INVALID
    assert payload not in path.read_text(encoding="utf-8")
    assert path.read_bytes() == before


def test_save_without_permission_is_forbidden(tmp_path):
    service, path = _service(tmp_path)
    before = path.read_bytes()

    with pytest.raises(VisionCoreError) as error:
        service.save(ZONES, {})

    assert error.value.code == codes.ZONE_EDITOR_FORBIDDEN
    assert path.read_bytes() == before


def test_write_error_restores_previous_file_and_skips_audit(tmp_path):
    before = json.dumps(ZONES).encode("utf-8")
    calls: list[tuple[Path, Path]] = []

    def failing_replace(source: Path, destination: Path):
        calls.append((source, destination))
        if len(calls) == 1:
            destination.write_bytes(b"contenido corrupto")
            raise OSError("disco lleno")
        os.replace(source, destination)

    service, path = _service(tmp_path, replace=failing_replace)
    edited = json.loads(json.dumps(ZONES))
    edited["door"][0][1] = 110

    with pytest.raises(OSError, match="disco lleno"):
        service.save(edited, AUTH)

    assert path.read_bytes() == before
    assert len(calls) >= 2
    assert (tmp_path / "audit.jsonl").exists() is False


def test_editor_behind_flag_is_unavailable():
    service = ZoneEditorService.disabled()

    assert service.describe(AUTH)["enabled"] is False
    with pytest.raises(VisionCoreError, match="no está disponible"):
        service.load()
    with pytest.raises(VisionCoreError, match="no está disponible"):
        service.save(ZONES, AUTH)


def test_audit_user_is_sanitized(tmp_path):
    service, _ = _service(tmp_path)
    headers = {"Authorization": f"Bearer {TOKEN}", "X-Vision-User": "<img src=x onerror=alert(1)>"}

    service.save(ZONES, headers)

    entry = json.loads((tmp_path / "audit.jsonl").read_text(encoding="utf-8"))
    assert "<" not in entry["user"]
    assert ">" not in entry["user"]
