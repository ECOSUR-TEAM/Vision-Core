"""Carga segura del esquema del JSON de zonas.

Las reglas viven en ``vision_core.core.validation.zone_payload``; este módulo
sólo añade la lectura acotada de archivos y mantiene los nombres públicos
históricos del esquema 1.0.
"""

import json
from pathlib import Path
from typing import Any

from vision_core.core.errors import ZoneConfigurationError
from vision_core.core.validation.zone_payload import (
    MAX_ZONE_PAYLOAD_BYTES,
    MAX_ZONE_POINTS,
    REQUIRED_ZONE_KEYS,
    SUPPORTED_ZONE_SCHEMA_VERSION,
    ZONE_NAMES,
    reject_duplicate_json_keys,
    validate_zone_schema,
)

__all__ = [
    "MAX_CONFIG_FILE_BYTES",
    "MAX_ZONE_POINTS",
    "REQUIRED_KEYS",
    "SUPPORTED_SCHEMA_VERSION",
    "ZONE_NAMES",
    "load_validated_zone_document",
    "reject_duplicate_json_keys",
    "validate_zone_document",
]

SUPPORTED_SCHEMA_VERSION = SUPPORTED_ZONE_SCHEMA_VERSION
MAX_CONFIG_FILE_BYTES = MAX_ZONE_PAYLOAD_BYTES
REQUIRED_KEYS = REQUIRED_ZONE_KEYS

validate_zone_document = validate_zone_schema


def load_validated_zone_document(path: str | Path) -> dict[str, Any]:
    """Lee, parsea y valida el documento de zonas antes de cualquier geometría."""
    source = Path(path)
    try:
        size = source.stat().st_size
    except OSError as exc:
        raise ZoneConfigurationError(f"no se puede acceder al archivo de zonas '{source}': {exc}") from None

    if size > MAX_CONFIG_FILE_BYTES:
        raise ZoneConfigurationError(
            f"el archivo de zonas '{source}' supera el límite de {MAX_CONFIG_FILE_BYTES} bytes (tiene {size} bytes)"
        )

    try:
        raw = source.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ZoneConfigurationError(f"no se puede leer '{source}' como UTF-8: {exc}") from None

    try:
        data = json.loads(raw, object_pairs_hook=reject_duplicate_json_keys)
    except json.JSONDecodeError as exc:
        raise ZoneConfigurationError(
            f"JSON malformado en '{source}' (línea {exc.lineno}, columna {exc.colno}): {exc.msg}"
        ) from None

    return validate_zone_document(data)
