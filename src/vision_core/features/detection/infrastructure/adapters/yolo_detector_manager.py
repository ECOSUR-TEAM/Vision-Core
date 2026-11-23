from typing import TYPE_CHECKING, cast

import numpy as np
import torch

from vision_core.core.config.settings_precision import is_supported_precision
from vision_core.core.domain.bbox import BBox
from vision_core.core.errors import ConfigurationError, ModelError, ValidationError, codes
from vision_core.core.inference.tensor_boxes import iter_prediction_boxes
from vision_core.features.detection.domain.entities.detection import Detection
from vision_core.features.detection.domain.ports.detector_manager import DetectorManager
from vision_core.features.detection.infrastructure.adapters.motion_tracker import (
    MotionTracker,
)
from vision_core.model_registry.model_descriptor import ModelDescriptor

if TYPE_CHECKING:
    from ultralytics.engine.results import Results

PERSON_CLASS_ID = 0
CONFIDENCE_THRESHOLD = 0.5
UNASSIGNED_TRACK_ID = -1


class YoloDetectorManager(DetectorManager):
    """Person detection with local motion/IoU tracking for one video stream."""

    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        *,
        device: str | None = None,
        precision: str = "fp32",
        confidence: float = CONFIDENCE_THRESHOLD,
        classes: tuple[int, ...] = (PERSON_CLASS_ID,),
        tracking_enabled: bool = True,
        max_missed_frames: int = 30,
        model_descriptor: ModelDescriptor | None = None,
    ) -> None:
        if not is_supported_precision(precision):
            raise ConfigurationError(
                "La precisión de detección debe ser fp32, fp16 o int8.",
                context={"variable": "VISION_CORE_DETECTION_PRECISION"},
            )
        resolved_device = device or "cpu"
        if precision == "fp16" and not resolved_device.startswith("cuda"):
            raise ConfigurationError(
                "La precisión fp16 de detección requiere un dispositivo cuda.",
                context={"variable": "VISION_CORE_DETECTION_DEVICE"},
            )
        try:
            from ultralytics import YOLO
        except ImportError as error:
            raise ModelError("La librería de detección no está instalada.") from error
        self._precision = precision
        self._model_path = model_path
        self._model_descriptor = model_descriptor
        self._device = resolved_device
        try:
            self._model = YOLO(model_path)
        except Exception as error:
            context: dict[str, object] = {"operation": "load_model"}
            if model_descriptor is not None:
                context.update(model_descriptor.expected_config)
                context["model_id"] = model_descriptor.id
                context["model_version"] = model_descriptor.version
                context["model_hash"] = model_descriptor.model_hash
            raise ModelError(
                "No se pudo cargar el modelo de detección.",
                context=context,
            ) from error
        self._confidence = confidence
        self._classes = classes
        self._tracking_enabled = tracking_enabled
        self._tracker = MotionTracker(max_missed_frames)
        self._next_track_id = 0

    def process(self, frame: np.ndarray) -> list[Detection]:
        if (
            not isinstance(frame, np.ndarray)
            or frame.dtype != np.uint8
            or frame.ndim != 3
            or frame.shape[2] != 3
            or min(frame.shape[:2]) <= 0
        ):
            raise ValidationError(
                "YOLO requiere un frame BGR uint8 de forma H x W x 3",
                code=codes.MODEL_INPUT_INVALID,
            )
        height, width = frame.shape[:2]
        with torch.inference_mode():
            results = cast(
                "list[Results]",
                self._model.predict(
                    np.ascontiguousarray(frame),
                    verbose=False,
                    classes=list(self._classes),
                    conf=self._confidence,
                    device=self._device,
                ),
            )
        if not results or results[0].boxes is None:
            return []
        detections: list[Detection] = []
        for class_id, confidence, coordinates in iter_prediction_boxes(results[0]):
            if class_id not in self._classes or not self._confidence < confidence <= 1.0:
                continue
            values = np.asarray(coordinates, dtype=float)
            if values.shape != (4,) or not np.isfinite(values).all():
                continue
            x1, y1, x2, y2 = values.tolist()
            x1, x2 = max(0.0, min(x1, width)), max(0.0, min(x2, width))
            y1, y2 = max(0.0, min(y1, height)), max(0.0, min(y2, height))
            if x2 <= x1 or y2 <= y1:
                continue
            detections.append(
                Detection(
                    bbox=BBox(x1=x1, y1=y1, x2=x2, y2=y2),
                    class_id=class_id,
                    confidence=confidence,
                    track_id=UNASSIGNED_TRACK_ID,
                )
            )
        if self._tracking_enabled:
            self._tracker.update(detections)
        else:
            for detection in detections:
                detection.track_id = self._next_track_id
                self._next_track_id += 1
        return detections

    def pop_lost_track_ids(self) -> list[int]:
        return self._tracker.pop_lost_track_ids()
