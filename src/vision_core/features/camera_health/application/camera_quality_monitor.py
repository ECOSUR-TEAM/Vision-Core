import logging
from collections.abc import Callable, Mapping
from types import MappingProxyType

import cv2
import numpy as np

from vision_core.core.config import CameraQualitySettings
from vision_core.features.camera_health.domain import quality_reasons as reasons
from vision_core.features.camera_health.domain.quality_observation import QualityObservation

logger = logging.getLogger(__name__)

_THUMBNAIL_SIZE = (64, 64)


class CameraQualityMonitor:
    """Mide señales de calidad con muestreo, sin lanzar errores al pipeline."""

    def __init__(
        self,
        settings: CameraQualitySettings,
        *,
        expected_frame_size: tuple[int, int] | None = None,
        zones=None,
        on_observation: Callable[[QualityObservation], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        if settings.sample_every_n_frames < 1:
            raise ValueError("sample_every_n_frames debe ser mayor que 0")
        if settings.frozen_frames < 2:
            raise ValueError("frozen_frames debe ser mayor o igual que 2")
        self._settings = settings
        self._expected_frame_size = expected_frame_size
        self._zones = zones
        self._on_observation = on_observation
        self._on_error = on_error
        self._frames = 0
        self._previous: np.ndarray | None = None
        self._frozen_streak = 0

    def observe(self, frame: np.ndarray) -> QualityObservation | None:
        self._frames += 1
        if not self._settings.enabled:
            return None
        if self._frames % self._settings.sample_every_n_frames:
            return None
        try:
            return self._analyze(frame)
        except Exception as error:
            logger.warning("No se pudo analizar la calidad de la cámara (%s)", type(error).__name__)
            if self._on_error is not None:
                self._on_error(error)
            return None

    def _analyze(self, frame: np.ndarray) -> QualityObservation:
        if not isinstance(frame, np.ndarray) or frame.ndim != 3 or frame.shape[2] < 3:
            raise ValueError("El frame debe ser un array BGR")
        height, width = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        thumbnail = cv2.resize(gray, _THUMBNAIL_SIZE, interpolation=cv2.INTER_AREA)
        brightness = float(thumbnail.mean())
        blur_variance = float(cv2.Laplacian(thumbnail, cv2.CV_64F).var())

        active: dict[str, bool] = {name: False for name in reasons.SIGNALS}
        if self._settings.check_resolution and self._expected_frame_size is not None:
            active[reasons.RESOLUTION_MISMATCH] = (width, height) != tuple(self._expected_frame_size)
        if self._settings.check_frozen:
            active[reasons.FROZEN_FRAME] = self._is_frozen(thumbnail)
        if self._settings.check_blur:
            active[reasons.BLURRY_FRAME] = blur_variance < self._settings.min_blur_variance
        if self._settings.check_exposure:
            active[reasons.EXPOSURE_OUT_OF_RANGE] = not (
                self._settings.min_brightness <= brightness <= self._settings.max_brightness
            )
        if self._settings.check_zones and self._zones is not None:
            active[reasons.ZONES_STALE] = self._zones_are_stale(width, height)

        reason = next((name for name in reasons.REASON_PRIORITY if active[name]), None)
        observation = QualityObservation(
            status=reasons.STATUS_DEGRADED if reason else reasons.STATUS_OK,
            reason=reason,
            signals=MappingProxyType(active),
            width=width,
            height=height,
            brightness=brightness,
            blur_variance=blur_variance,
        )
        if self._on_observation is not None:
            self._on_observation(observation)
        return observation

    def _is_frozen(self, thumbnail: np.ndarray) -> bool:
        if self._previous is None:
            self._previous = thumbnail
            return False
        difference = float(np.abs(thumbnail.astype(np.int16) - self._previous.astype(np.int16)).mean())
        self._previous = thumbnail
        self._frozen_streak = self._frozen_streak + 1 if difference <= self._settings.frozen_difference else 0
        return self._frozen_streak >= self._settings.frozen_frames

    def _zones_are_stale(self, width: int, height: int) -> bool:
        zones = self._zones
        if (zones.width, zones.height) != (width, height):
            return True
        polygons: Mapping[str, object] = {
            "door": zones.door,
            "exterior": zones.exterior,
            "interior": zones.interior,
        }
        for polygon in polygons.values():
            points = getattr(polygon, "points", ())
            if any(not (0 <= x < width and 0 <= y < height) for x, y in points):
                return True
        return False
