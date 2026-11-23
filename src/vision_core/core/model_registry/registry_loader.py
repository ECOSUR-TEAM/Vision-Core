import re
from datetime import date
from math import isfinite
from pathlib import Path
from typing import Any

import yaml

from vision_core.core.config.settings_precision import is_supported_precision
from vision_core.core.errors import ConfigurationError
from vision_core.core.model_registry.model_descriptor import ModelDescriptor
from vision_core.core.model_registry.model_registry import ModelRegistry
from vision_core.core.model_registry.unique_key_loader import UniqueKeySafeLoader

SUPPORTED_SCHEMA_VERSION = "1.0"
MAX_REGISTRY_FILE_BYTES = 256 * 1024
DOCUMENT_KEYS = frozenset({"schema_version", "models"})
MODEL_KEYS = frozenset(
    {
        "id",
        "name",
        "task",
        "version",
        "artifact_version",
        "selector",
        "source",
        "source_url",
        "license",
        "license_url",
        "license_notes",
        "registered_at",
        "checksum",
        "expected_config",
        "model_card",
        "status",
    }
)
CHECKSUM_KEYS = frozenset({"algorithm", "value"})
DETECTION_CONFIG_KEYS = frozenset({"confidence", "classes", "input", "output_classes", "precision"})
EMBEDDING_CONFIG_KEYS = frozenset({"embedding_dim", "input", "weights", "precision"})
OPTIONAL_CONFIG_KEYS = frozenset({"precision"})
TASKS = frozenset({"detection", "embedding"})
STATUSES = frozenset({"active", "deprecated", "experimental"})
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def load_model_registry(path: str | Path) -> ModelRegistry:
    source = Path(path)
    try:
        size = source.stat().st_size
    except OSError as exc:
        raise ConfigurationError(f"no se puede acceder al registro de modelos '{source}'") from exc
    if size > MAX_REGISTRY_FILE_BYTES:
        raise ConfigurationError(
            f"el registro de modelos supera el límite de {MAX_REGISTRY_FILE_BYTES} bytes (tiene {size} bytes)"
        )
    try:
        raw = source.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ConfigurationError(f"no se puede leer el registro de modelos como UTF-8: {source}") from exc
    try:
        document = yaml.load(raw, Loader=UniqueKeySafeLoader)
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"YAML malformado en el registro de modelos: {exc}") from exc
    return ModelRegistry(_validate_document(document))


def _validate_document(data: object) -> tuple[ModelDescriptor, ...]:
    document = _require_mapping(data, "registro")
    _validate_keys(document, DOCUMENT_KEYS, "registro")
    version = _text(document["schema_version"], "schema_version")
    if version != SUPPORTED_SCHEMA_VERSION:
        raise ConfigurationError(f"schema_version: se espera '{SUPPORTED_SCHEMA_VERSION}', se recibió '{version}'")
    models = document["models"]
    if not isinstance(models, list) or not models:
        raise ConfigurationError("models: debe ser una lista no vacía de modelos")

    descriptors: list[ModelDescriptor] = []
    seen_ids: set[str] = set()
    seen_selectors: set[tuple[str, str]] = set()
    for index, item in enumerate(models):
        descriptor = _validate_model(item, f"models[{index}]")
        if descriptor.id in seen_ids:
            raise ConfigurationError(f"id de modelo duplicado: {descriptor.id}")
        selector_key = (descriptor.task, descriptor.selector)
        if selector_key in seen_selectors:
            raise ConfigurationError(f"selector duplicado para la tarea {descriptor.task}: {descriptor.selector}")
        seen_ids.add(descriptor.id)
        seen_selectors.add(selector_key)
        descriptors.append(descriptor)
    return tuple(descriptors)


def _validate_model(data: object, field: str) -> ModelDescriptor:
    item = _require_mapping(data, field)
    _validate_keys(item, MODEL_KEYS, field)
    task = _text(item["task"], f"{field}.task")
    if task not in TASKS:
        raise ConfigurationError(f"{field}.task: use una de {', '.join(sorted(TASKS))}")
    status = _text(item["status"], f"{field}.status")
    if status not in STATUSES:
        raise ConfigurationError(f"{field}.status: use una de {', '.join(sorted(STATUSES))}")
    checksum_algorithm, checksum_value = _validate_checksum(item["checksum"], f"{field}.checksum")
    return ModelDescriptor(
        id=_text(item["id"], f"{field}.id"),
        name=_text(item["name"], f"{field}.name"),
        task=task,
        version=_text(item["version"], f"{field}.version"),
        artifact_version=_text(item["artifact_version"], f"{field}.artifact_version"),
        selector=_text(item["selector"], f"{field}.selector"),
        source=_text(item["source"], f"{field}.source"),
        source_url=_optional_text(item["source_url"], f"{field}.source_url"),
        license=_text(item["license"], f"{field}.license"),
        license_url=_optional_text(item["license_url"], f"{field}.license_url"),
        license_notes=_optional_text(item["license_notes"], f"{field}.license_notes"),
        registered_at=_validate_date(item["registered_at"], f"{field}.registered_at"),
        checksum_algorithm=checksum_algorithm,
        checksum_value=checksum_value,
        expected_config=_validate_expected_config(item["expected_config"], task, f"{field}.expected_config"),
        model_card=_text(item["model_card"], f"{field}.model_card"),
        status=status,
    )


def _require_mapping(value: object, field: str) -> dict[Any, Any]:
    if not isinstance(value, dict):
        raise ConfigurationError(f"{field}: se esperaba un objeto, se recibió {type(value).__name__}")
    return value


def _validate_keys(
    data: dict[Any, Any],
    expected: frozenset[str],
    field: str,
    *,
    optional: frozenset[str] = frozenset(),
) -> None:
    missing = sorted(str(key) for key in expected - optional if key not in data)
    if missing:
        raise ConfigurationError(f"{field}: faltan claves requeridas: {', '.join(missing)}")
    unknown = sorted(str(key) for key in data if key not in expected)
    if unknown:
        raise ConfigurationError(f"{field}: claves desconocidas no permitidas: {', '.join(unknown)}")


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"{field}: se esperaba una cadena no vacía")
    return value.strip()


def _optional_text(value: object, field: str) -> str | None:
    if value is None or value == "":
        return None
    return _text(value, field)


def _validate_date(value: object, field: str) -> str:
    text = _text(value, field)
    try:
        date.fromisoformat(text)
    except ValueError:
        raise ConfigurationError(f"{field}: use una fecha ISO 8601 (YYYY-MM-DD)") from None
    return text


def _validate_checksum(value: object, field: str) -> tuple[str, str | None]:
    checksum = _require_mapping(value, field)
    _validate_keys(checksum, CHECKSUM_KEYS, field)
    algorithm = _text(checksum["algorithm"], f"{field}.algorithm")
    if algorithm != "sha256":
        raise ConfigurationError(f"{field}.algorithm: se espera 'sha256'")
    digest = checksum["value"]
    if digest is None:
        return algorithm, None
    if not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest.strip().lower()):
        raise ConfigurationError(f"{field}.value: use 64 caracteres hexadecimales o null")
    return algorithm, digest.strip().lower()


def _validate_expected_config(value: object, task: str, field: str) -> dict[str, object]:
    expected = _require_mapping(value, field)
    keys = DETECTION_CONFIG_KEYS if task == "detection" else EMBEDDING_CONFIG_KEYS
    _validate_keys(expected, keys, field, optional=OPTIONAL_CONFIG_KEYS)
    config: dict[str, object] = {"input": _text(expected["input"], f"{field}.input")}
    precision = _optional_text(expected.get("precision"), f"{field}.precision") or "fp32"
    if not is_supported_precision(precision):
        raise ConfigurationError(f"{field}.precision: use fp32, fp16 o int8")
    config["precision"] = precision
    if task == "detection":
        confidence = _finite_number(expected["confidence"], f"{field}.confidence")
        if not 0 < confidence <= 1:
            raise ConfigurationError(f"{field}.confidence: debe estar entre 0 y 1")
        config["confidence"] = confidence
        config["classes"] = _int_tuple(expected["classes"], f"{field}.classes")
        config["output_classes"] = _positive_int(expected["output_classes"], f"{field}.output_classes")
        return config
    config["weights"] = _text(expected["weights"], f"{field}.weights")
    config["embedding_dim"] = _positive_int(expected["embedding_dim"], f"{field}.embedding_dim")
    return config


def _finite_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigurationError(f"{field}: se esperaba un número finito")
    number = float(value)
    if not isfinite(number):
        raise ConfigurationError(f"{field}: NaN e Infinity no están permitidos")
    return number


def _positive_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ConfigurationError(f"{field}: se esperaba un entero positivo")
    return value


def _int_tuple(value: object, field: str) -> tuple[int, ...]:
    if not isinstance(value, list) or not value:
        raise ConfigurationError(f"{field}: debe ser una lista no vacía de enteros no negativos")
    items: list[int] = []
    for index, item in enumerate(value):
        if isinstance(item, bool) or not isinstance(item, int) or item < 0:
            raise ConfigurationError(f"{field}[{index}]: se esperaba un entero no negativo")
        items.append(item)
    return tuple(items)
