"""Mappers between transport DTOs and BGR frames used by the pipeline."""

from typing import Any

import cv2
import numpy as np

from vision_core.shared.errors import ValidationError, codes

from ..dto.response.response_read_frame import ResponseReadFrame


def validate_frame(frame: Any, expected_size: tuple[int, int] | None = None) -> None:
    if not isinstance(frame, np.ndarray):
        raise ValidationError("El frame debe ser un ndarray", code=codes.VIDEO_FRAME_INVALID)
    if frame.dtype != np.uint8:
        raise ValidationError("El frame debe tener dtype uint8", code=codes.VIDEO_FRAME_INVALID)
    if frame.ndim != 3 or frame.shape[2] != 3 or min(frame.shape[:2]) <= 0:
        raise ValidationError("El frame debe tener forma H x W x 3 y no estar vacío", code=codes.VIDEO_FRAME_INVALID)
    if expected_size is not None and (frame.shape[1], frame.shape[0]) != expected_size:
        raise ValidationError(
            "La resolución cambió o no coincide con la esperada",
            code=codes.VIDEO_FRAME_INVALID,
            context={"expected_width": expected_size[0], "expected_height": expected_size[1]},
        )


def frame_to_dto(frame: Any | None) -> ResponseReadFrame:
    if frame is None:
        return ResponseReadFrame(frame_png=None)
    validate_frame(frame)
    ok, encoded = cv2.imencode(".png", frame)
    if not ok:
        raise ValidationError("No se pudo codificar el frame", code=codes.VIDEO_FRAME_INVALID)
    return ResponseReadFrame(
        frame_png=encoded.tobytes(),
        width=int(frame.shape[1]),
        height=int(frame.shape[0]),
    )


def dto_to_frame(response: ResponseReadFrame) -> Any | None:
    if response.frame_png is None:
        return None
    encoded = np.frombuffer(response.frame_png, dtype=np.uint8)
    frame = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValidationError("No se pudo decodificar el frame", code=codes.VIDEO_FRAME_INVALID)
    validate_frame(frame, (response.width, response.height))
    return frame
