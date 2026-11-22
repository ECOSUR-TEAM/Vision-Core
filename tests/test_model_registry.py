import hashlib
import json
import logging
from pathlib import Path

import pytest
import yaml

from vision_core.core.config import Settings, SettingsError
from vision_core.core.errors import ConfigurationError
from vision_core.core.telemetry.health import HealthStatus
from vision_core.core.telemetry.structured_logging import StructuredJsonFormatter
from vision_core.features.reid.infrastructure.dependencies import build_reid
from vision_core.model_registry.activation import resolve_active_models
from vision_core.model_registry.registry_loader import load_model_registry

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = PROJECT_ROOT / "config" / "models.yml"


def _settings(**overrides):
    env = {"VISION_CORE_RTSP_URL": "rtsp://localhost:8554/entrada"}
    env.update(overrides)
    return Settings.from_env(env, validate_startup=False)


def _detection_entry():
    return {
        "id": "detection.person.yolov8n",
        "name": "yolov8n",
        "task": "detection",
        "version": "1.0.0",
        "artifact_version": "unpinned",
        "selector": "yolov8n.pt",
        "source": "Ultralytics YOLOv8n",
        "source_url": None,
        "license": "AGPL-3.0",
        "license_url": None,
        "license_notes": None,
        "registered_at": "2026-11-21",
        "checksum": {"algorithm": "sha256", "value": None},
        "expected_config": {
            "confidence": 0.5,
            "classes": [0],
            "input": "BGR uint8 HxWx3",
            "output_classes": 80,
        },
        "model_card": "docs/model-cards/detection-yolov8n.md",
        "status": "active",
    }


def _embedding_entry():
    return {
        "id": "embedding.person.mobilenet_v3_small",
        "name": "mobilenet_v3_small",
        "task": "embedding",
        "version": "1.0.0",
        "artifact_version": "IMAGENET1K_V1",
        "selector": "mobilenet_v3_small",
        "source": "torchvision",
        "source_url": None,
        "license": "BSD-3-Clause",
        "license_url": None,
        "license_notes": None,
        "registered_at": "2026-11-21",
        "checksum": {"algorithm": "sha256", "value": None},
        "expected_config": {
            "embedding_dim": 576,
            "input": "BGR uint8 recorte de persona",
            "weights": "DEFAULT",
        },
        "model_card": "docs/model-cards/embedding-mobilenet-v3-small.md",
        "status": "active",
    }


def _registry_document():
    return {"schema_version": "1.0", "models": [_detection_entry(), _embedding_entry()]}


def _write_registry(path, document):
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    return path


def test_default_registry_contains_all_pipeline_models():
    registry = load_model_registry(DEFAULT_REGISTRY)
    models = registry.all()
    assert {model.id for model in models} == {
        "detection.person.yolov8n",
        "embedding.person.mobilenet_v3_small",
        "embedding.person.resnet50",
    }
    assert {model.task for model in models} == {"detection", "embedding"}
    for model in models:
        assert model.license
        assert model.checksum_algorithm == "sha256"
        assert (PROJECT_ROOT / model.model_card).is_file()


def test_environment_defaults_reference_registered_models():
    settings = _settings()
    assert settings.models.detection_model_id == "detection.person.yolov8n"
    assert settings.models.embedding_model_id == "embedding.person.mobilenet_v3_small"
    assert settings.models.verify_checksums is True
    active = resolve_active_models(settings)
    assert active.detection.id == settings.models.detection_model_id
    assert active.embedding.id == settings.models.embedding_model_id


def test_unknown_model_id_fails_with_clear_message():
    settings = _settings(VISION_CORE_DETECTION_MODEL_ID="detection.person.desconocido")
    with pytest.raises(ConfigurationError, match="model_id desconocido"):
        resolve_active_models(settings)


def test_selector_mismatch_fails_before_startup():
    settings = _settings(VISION_CORE_EMBEDDING_MODEL="resnet50")
    with pytest.raises(ConfigurationError, match="selector"):
        resolve_active_models(settings)


def test_expected_configuration_mismatch_fails():
    settings = _settings(VISION_CORE_DETECTION_CONFIDENCE="0.7")
    with pytest.raises(ConfigurationError, match="VISION_CORE_DETECTION_CONFIDENCE"):
        resolve_active_models(settings)


def test_settings_reject_empty_model_ids():
    with pytest.raises(SettingsError, match="VISION_CORE_DETECTION_MODEL_ID"):
        _settings(VISION_CORE_DETECTION_MODEL_ID="")
    with pytest.raises(SettingsError, match="VISION_CORE_EMBEDDING_MODEL_ID"):
        _settings(VISION_CORE_EMBEDDING_MODEL_ID="")


def test_registry_rejects_duplicate_keys(tmp_path):
    source = tmp_path / "models.yml"
    source.write_text(
        'schema_version: "1.0"\nschema_version: "1.0"\nmodels: []\n',
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError, match="clave duplicada"):
        load_model_registry(source)


def test_registry_rejects_unsupported_schema_and_unknown_keys(tmp_path):
    document = _registry_document()
    document["schema_version"] = "2.0"
    source = _write_registry(tmp_path / "schema.yml", document)
    with pytest.raises(ConfigurationError, match="schema_version"):
        load_model_registry(source)

    document = _registry_document()
    document["extra"] = "no permitido"
    source = _write_registry(tmp_path / "extra.yml", document)
    with pytest.raises(ConfigurationError, match="claves desconocidas"):
        load_model_registry(source)


def test_checksum_mismatch_fails_and_match_resolves(tmp_path):
    weights = tmp_path / "yolov8n.pt"
    weights.write_bytes(b"pesos reales")
    digest = hashlib.sha256(b"pesos reales").hexdigest()
    document = _registry_document()
    document["models"][0]["checksum"]["value"] = hashlib.sha256(b"otros pesos").hexdigest()
    registry_file = _write_registry(tmp_path / "models.yml", document)
    settings = _settings(
        VISION_CORE_MODEL_REGISTRY_FILE=str(registry_file),
        VISION_CORE_MODEL_PATH=str(weights),
    )
    with pytest.raises(ConfigurationError, match="checksum"):
        resolve_active_models(settings)

    document["models"][0]["checksum"]["value"] = digest
    _write_registry(registry_file, document)
    active = resolve_active_models(settings)
    assert active.detection.model_hash == f"sha256:{digest}"


def test_checksum_declared_without_file_fails(tmp_path):
    document = _registry_document()
    document["models"][0]["checksum"]["value"] = hashlib.sha256(b"pesos").hexdigest()
    registry_file = _write_registry(tmp_path / "models.yml", document)
    settings = _settings(
        VISION_CORE_MODEL_REGISTRY_FILE=str(registry_file),
        VISION_CORE_MODEL_PATH=str(tmp_path / "yolov8n.pt"),
    )
    with pytest.raises(ConfigurationError, match="archivo local"):
        resolve_active_models(settings)


def test_checksum_null_with_file_present_reports_unverified(tmp_path):
    weights = tmp_path / "yolov8n.pt"
    weights.write_bytes(b"pesos sin checksum")
    settings = _settings(VISION_CORE_MODEL_PATH=str(weights))
    active = resolve_active_models(settings)
    assert active.detection.model_hash == "unverified"


def test_embedding_checksum_without_local_artifact_fails(tmp_path):
    document = _registry_document()
    document["models"][1]["checksum"]["value"] = hashlib.sha256(b"pesos").hexdigest()
    registry_file = _write_registry(tmp_path / "models.yml", document)
    settings = _settings(VISION_CORE_MODEL_REGISTRY_FILE=str(registry_file))
    with pytest.raises(ConfigurationError, match="no tiene archivo local"):
        resolve_active_models(settings)


def test_resnet50_resolves_with_matching_model_id():
    settings = _settings(
        VISION_CORE_EMBEDDING_MODEL="resnet50",
        VISION_CORE_EMBEDDING_MODEL_ID="embedding.person.resnet50",
    )
    active = resolve_active_models(settings)
    assert active.embedding.id == "embedding.person.resnet50"
    assert active.embedding.selector == "resnet50"


def test_build_reid_injects_model_descriptor(monkeypatch):
    descriptor = resolve_active_models(_settings()).embedding
    embedder = object()
    seen = {}

    def fake_from_env(model_descriptor=None):
        seen["descriptor"] = model_descriptor
        return embedder

    monkeypatch.setattr(
        "vision_core.features.reid.infrastructure.dependencies.TorchvisionEmbeddingExtractor.from_env",
        fake_from_env,
    )
    dependencies = build_reid(model_descriptor=descriptor)
    assert seen["descriptor"] is descriptor
    assert dependencies.embedder is embedder


def test_health_snapshot_exposes_model_identity():
    identity = {
        "model_id": "detection.person.yolov8n",
        "model_version": "1.0.0",
        "model_hash": "unverified",
    }
    health = HealthStatus(minimum_free_disk_mb=0, model_metadata={"detection": identity})
    payload = health.snapshot()
    assert payload["model_id"] == identity["model_id"]
    assert payload["model_version"] == identity["model_version"]
    assert payload["model_hash"] == identity["model_hash"]
    assert payload["models"]["detection"] == identity


def test_json_logs_include_model_identity():
    identity = {
        "model_id": "detection.person.yolov8n",
        "model_version": "1.0.0",
        "model_hash": "unverified",
        "embedding_model_id": "embedding.person.mobilenet_v3_small",
        "embedding_model_version": "1.0.0",
        "embedding_model_hash": "unverified",
    }
    formatter = StructuredJsonFormatter("camera-a", identity)
    record = logging_record()
    payload = json.loads(formatter.format(record))
    for key, value in identity.items():
        assert payload[key] == value


def logging_record():
    return logging.LogRecord("vision_core", logging.INFO, __file__, 1, "ready", (), None)
