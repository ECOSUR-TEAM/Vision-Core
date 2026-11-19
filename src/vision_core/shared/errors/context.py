"""Contexto seguro para errores: sin secretos, rutas internas ni datos personales."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

_SENSITIVE_KEY_PARTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "credential",
    "authorization",
    "apikey",
    "api_key",
    "url",
    "rtsp",
    "path",
    "filename",
    "file",
    "email",
    "phone",
    "person",
    "dni",
    "name",
)
_CREDENTIALS_IN_URL = re.compile(r"([a-z][a-z0-9+.-]*://)[^/@\s]+:[^/@\s]+@", re.IGNORECASE)
_MAX_STRING_LENGTH = 200


def _clean_string(value: str) -> str:
    return _CREDENTIALS_IN_URL.sub(r"\1***@", value)[:_MAX_STRING_LENGTH]


def _clean_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _clean_string(value)
    if isinstance(value, Mapping):
        return {str(key): _clean_value(item) for key, item in value.items() if not _is_sensitive(str(key))}
    if isinstance(value, (list, tuple, set)):
        return [_clean_value(item) for item in value]
    return type(value).__name__


def _is_sensitive(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in _SENSITIVE_KEY_PARTS)


def sanitize_context(context: Mapping[str, Any] | None) -> dict[str, Any]:
    """Filtra claves sensibles y normaliza valores a tipos serializables simples."""
    if not context:
        return {}
    return {str(key): _clean_value(value) for key, value in context.items() if not _is_sensitive(str(key))}
