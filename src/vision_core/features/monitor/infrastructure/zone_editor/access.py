"""Contrato de permisos del editor: sustituye a ticket 42/50 cuando exista auth real."""

import hmac
import re
from collections.abc import Mapping

from vision_core.features.monitor.infrastructure.zone_editor.config import ZoneEditorConfig

_USER_PATTERN = re.compile(r"[^A-Za-z0-9._@-]+")
_MAX_USER_LENGTH = 64


def editor_user(headers: Mapping[str, str]) -> str:
    """Etiqueta de auditoría acotada; nunca se usa para decidir permisos."""
    raw = headers.get("X-Vision-User", "unknown")
    cleaned = _USER_PATTERN.sub("_", str(raw)).strip("_")[:_MAX_USER_LENGTH]
    return cleaned or "unknown"


def can_save_zones(config: ZoneEditorConfig, headers: Mapping[str, str]) -> bool:
    """Sólo autoriza a quien presenta el token configurado.

    Sin token configurado nadie puede guardar: el editor queda en modo vista
    previa hasta que exista autenticación completa (ticket 42/50).
    """
    if not config.available or not config.editor_token:
        return False
    authorization = headers.get("Authorization", "")
    scheme, _, supplied = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return False
    return hmac.compare_digest(supplied.strip(), config.editor_token)
