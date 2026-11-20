"""Base de la taxonomía de errores, independiente de HTTP y de frameworks."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from vision_core.shared.errors.codes import INTERNAL_ERROR
from vision_core.shared.errors.context import sanitize_context


class VisionCoreError(Exception):
    """Error esperado con código estable, mensaje seguro y contexto depurado.

    Las subclases fijan valores por defecto; cada instancia puede refinar el
    código y indicar si una nueva tentativa tiene sentido. El mensaje expuesto
    nunca incluye excepciones nativas, rutas ni credenciales.
    """

    default_code = INTERNAL_ERROR
    default_message = "No se pudo completar la operación."
    default_retryable = False

    def __init__(
        self,
        message: str | None = None,
        *args: Any,
        code: str | None = None,
        retryable: bool | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> None:
        if args:
            raise TypeError("VisionCoreError accepts at most one positional message")
        self._code = code or type(self).default_code
        self._message = type(self).default_message if message is None else message
        self._retryable = type(self).default_retryable if retryable is None else bool(retryable)
        self._context = sanitize_context(context)
        super().__init__(self._message)

    @property
    def code(self) -> str:
        return self._code

    @property
    def message(self) -> str:
        return self._message

    @property
    def retryable(self) -> bool:
        return self._retryable

    @property
    def context(self) -> dict[str, Any]:
        return dict(self._context)

    def as_dict(self) -> dict[str, Any]:
        """Representación para logs estructurados; no incluye stack traces."""
        return {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
            "context": self.context,
        }
