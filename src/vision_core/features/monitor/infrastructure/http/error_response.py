"""Traducción de errores de dominio a respuestas HTTP del monitor."""

from typing import Any

from vision_core.shared.errors import VisionCoreError, codes

_STATUS_BY_CODE = {
    codes.CONFIGURATION_INVALID: 500,
    codes.VIDEO_SOURCE_UNAVAILABLE: 503,
    codes.VIDEO_SOURCE_MISSING: 500,
    codes.VIDEO_SOURCE_STATE: 500,
    codes.VIDEO_FRAME_PENDING: 503,
    codes.VIDEO_FRAME_INVALID: 400,
    codes.MODEL_UNAVAILABLE: 500,
    codes.MODEL_INPUT_INVALID: 400,
    codes.ZONE_CONFIG_INVALID: 422,
    codes.ZONE_GEOMETRY_INVALID: 422,
    codes.REID_MODEL_INVALID: 500,
    codes.REID_INPUT_INVALID: 400,
    codes.PIPELINE_CALIBRATION_MISMATCH: 409,
    codes.PIPELINE_FAILED: 500,
    codes.VALIDATION_FAILED: 400,
    codes.REQUEST_NOT_FOUND: 404,
    codes.INTERNAL_ERROR: 500,
}

_INTERNAL_MESSAGE = "Error interno del monitor."


def status_for_code(code: str) -> int:
    return _STATUS_BY_CODE.get(code, 500)


def error_envelope(code: str, message: str, request_id: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "request_id": request_id}}


def describe_error(error: BaseException) -> tuple[str, str, int]:
    """Devuelve código, mensaje seguro y estado; nunca expone la excepción nativa."""
    if isinstance(error, VisionCoreError):
        return error.code, error.message, status_for_code(error.code)
    return codes.INTERNAL_ERROR, _INTERNAL_MESSAGE, 500
