"""Detector determinista que lee las marcas del video sintético generado."""

from typing import Any

import numpy as np

from vision_core.features.detection.domain.entities.detection import Detection
from vision_core.features.detection.domain.ports.detector_manager import DetectorManager
from vision_core.shared.domain.bbox import BBox

ROI_TOP = 100
ROI_BOTTOM = 140


class SyntheticDetector(DetectorManager):
    """Emite detecciones a partir de las marcas blancas/rojas del video de benchmark."""

    def __init__(self, track_ids: list[int], lost_ids: list[list[int]], width: int) -> None:
        if not track_ids or width < 1:
            raise ValueError("Se requieren track_ids no vacíos y un ancho positivo")
        self._track_ids = track_ids
        self._lost_ids = lost_ids
        self._width = width
        self._index = 0

    def process(self, frame: Any) -> list[Detection]:
        index = min(self._index, len(self._track_ids) - 1)
        track_id = self._track_ids[index]
        self._index += 1
        roi = frame[ROI_TOP:ROI_BOTTOM, : self._width]
        if roi.ndim != 3 or roi.shape[2] < 3:
            return []
        red = (roi[:, :, 2] > 240) & (roi[:, :, 0] < 60) & (roi[:, :, 1] < 60)
        if red.any():
            return [Detection(BBox(-15, ROI_TOP, 5, ROI_BOTTOM), 0, 0.9, track_id)]
        white = (roi > 240).all(axis=2)
        if not white.any():
            return []
        x = float(np.nonzero(white)[1].mean())
        return [Detection(BBox(x - 10, ROI_TOP, x + 10, ROI_BOTTOM), 0, 0.9, track_id)]

    def pop_lost_track_ids(self) -> list[int]:
        index = max(0, self._index - 1)
        if index >= len(self._lost_ids):
            return []
        return list(self._lost_ids[index])
