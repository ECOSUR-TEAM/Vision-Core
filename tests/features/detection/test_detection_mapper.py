from vision_core.features.detection.application.mappers.detection_mapper import (
    detection_from_dto,
    detection_to_dto,
    detections_to_response,
    response_to_detections,
)
from vision_core.features.detection.domain.entities.detection import Detection
from vision_core.shared.domain.bbox import BBox


def test_detection_mapper_round_trips_domain_entity():
    detection = Detection(BBox(1.5, 2, 11, 22), 0, 0.9, 3)

    dto = detection_to_dto(detection)

    assert detection_from_dto(dto) == detection


def test_detection_mapper_maps_response_collection():
    detections = [Detection(BBox(1, 2, 11, 22), 0, 0.9, 3)]

    response = detections_to_response(detections)

    assert response_to_detections(response) == detections
