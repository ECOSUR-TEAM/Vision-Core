"""Contrato de entrada del detector: OpenCV BGR, HWC, uint8."""
import numpy as np


def validate_frame(frame: np.ndarray, expected_size=None) -> None:
    if not isinstance(frame, np.ndarray):
        raise ValueError('El frame debe ser un ndarray')
    if frame.dtype != np.uint8:
        raise ValueError('El frame debe tener dtype uint8')
    if frame.ndim != 3 or frame.shape[2] != 3 or min(frame.shape[:2]) <= 0:
        raise ValueError('El frame debe tener forma H x W x 3 y no estar vacío')
    if expected_size is not None and (frame.shape[1], frame.shape[0]) != expected_size:
        raise ValueError('La resolución cambió o no coincide con la esperada')
    # BGR is guaranteed by the decoder, not inferable from arbitrary pixel values.
