"""Mappers between detection domain entities and transport payloads."""

from collections.abc import Mapping

from vision_core.features.detection.application.dto.response.response_detector import ResponseDetector
from vision_core.features.detection.domain.entities.detection import Detection
from vision_core.shared.application.dto.bbox_payload import BBoxPayload
from vision_core.shared.application.dto.detection_payload import DetectionPayload
from vision_core.shared.application.validation import (
    bounded_int,
    finite_bbox,
    finite_unit_float,
    required_track_id,
)
from vision_core.shared.domain.bbox import BBox


def detection_to_dto(detection: Detection) -> DetectionPayload:
    bbox = detection.bbox
    return DetectionPayload(
        bbox=BBoxPayload(x1=bbox.x1, y1=bbox.y1, x2=bbox.x2, y2=bbox.y2),
        class_id=detection.class_id,
        confidence=detection.confidence,
        track_id=detection.track_id,
    )


def detection_from_dto(data: DetectionPayload | Mapping[str, object]) -> Detection:
    bbox: object
    class_id: object
    confidence: object
    track_id: object
    if isinstance(data, DetectionPayload):
        bbox = data.bbox
        class_id = data.class_id
        confidence = data.confidence
        track_id = data.track_id
    elif isinstance(data, Mapping):
        bbox = data.get("bbox")
        class_id = data.get("class_id")
        confidence = data.get("confidence")
        track_id = data.get("track_id")
    else:
        raise ValueError("Detection DTO must be a DetectionPayload or a mapping")

    x1, y1, x2, y2 = finite_bbox(bbox)
    return Detection(
        bbox=BBox(x1=x1, y1=y1, x2=x2, y2=y2),
        class_id=bounded_int(class_id, "class_id"),
        confidence=finite_unit_float(confidence, "confidence"),
        track_id=required_track_id(track_id),
    )


def detections_to_response(detections: list[Detection]) -> ResponseDetector:
    return ResponseDetector(tuple(detection_to_dto(detection) for detection in detections))


def response_to_detections(response: ResponseDetector) -> list[Detection]:
    return [detection_from_dto(data) for data in response.detections]
