"""Mappers between transport DTOs and BGR frames used by the pipeline."""

from typing import Any

import cv2
import numpy as np

from vision_core.shared.application.validation import validate_frame
from vision_core.shared.errors import ValidationError, codes

from ..dto.response.response_read_frame import ResponseReadFrame


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
