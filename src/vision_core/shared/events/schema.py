"""Versión del contrato de eventos serializados.

`schema_version` viaja en cada evento para que consumidores y productores puedan
detectar cambios incompatibles. Cambios compatibles (añadir campos opcionales)
aumentan la parte menor; cambiar tipos, quitar campos o cambiar su significado
exige una versión mayor y una migración anunciada.
"""

from vision_core.shared.application.dto.schema_version import EVENT_SCHEMA_VERSION


def with_schema_version(payload: dict[str, object]) -> dict[str, object]:
    """Devuelve una copia del evento con la versión de esquema acordada."""
    result = dict(payload)
    result.setdefault("schema_version", EVENT_SCHEMA_VERSION)
    return result
