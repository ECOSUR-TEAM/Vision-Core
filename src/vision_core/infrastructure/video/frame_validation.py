"""Contrato de entrada del detector: OpenCV BGR, HWC, uint8."""

import numpy as np

from vision_core.core.errors import ValidationError, codes


def validate_frame(frame: np.ndarray, expected_size=None) -> None:
    if not isinstance(frame, np.ndarray):
        raise ValidationError("El frame debe ser un ndarray", code=codes.VIDEO_FRAME_INVALID)
    if frame.dtype != np.uint8:
        raise ValidationError("El frame debe tener dtype uint8", code=codes.VIDEO_FRAME_INVALID)
    if frame.ndim != 3 or frame.shape[2] != 3 or min(frame.shape[:2]) <= 0:
        raise ValidationError("El frame debe tener forma H x W x 3 y no estar vacío", code=codes.VIDEO_FRAME_INVALID)
    if expected_size is not None and (frame.shape[1], frame.shape[0]) != expected_size:
        raise ValidationError("La resolución cambió o no coincide con la esperada", code=codes.VIDEO_FRAME_INVALID)
