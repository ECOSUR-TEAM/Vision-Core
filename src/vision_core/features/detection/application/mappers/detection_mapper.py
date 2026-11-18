from typing import Mapping

from vision_core.features.detection.application.dto.response.response_detector import ResponseDetector
from vision_core.features.detection.domain.entities.detection import Detection
from vision_core.shared.domain.bbox import BBox


def detection_to_dto(detection: Detection) -> dict[str, object]:
    return {
        "bbox": {
            "x1": detection.bbox.x1,
            "y1": detection.bbox.y1,
            "x2": detection.bbox.x2,
            "y2": detection.bbox.y2,
        },
        "class_id": detection.class_id,
        "confidence": detection.confidence,
        "track_id": detection.track_id,
    }


def detection_from_dto(data: Mapping[str, object]) -> Detection:
    bbox_data = data["bbox"]
    if not isinstance(bbox_data, Mapping):
        raise TypeError("Detection DTO bbox must be a mapping")
    return Detection(
        bbox=BBox(
            x1=float(bbox_data["x1"]),
            y1=float(bbox_data["y1"]),
            x2=float(bbox_data["x2"]),
            y2=float(bbox_data["y2"]),
        ),
        class_id=int(data["class_id"]),
        confidence=float(data["confidence"]),
        track_id=int(data["track_id"]),
    )


def detections_to_response(detections: list[Detection]) -> ResponseDetector:
    return ResponseDetector(tuple(detection_to_dto(detection) for detection in detections))


def response_to_detections(response: ResponseDetector) -> list[Detection]:
    return [detection_from_dto(data) for data in response.detections]
