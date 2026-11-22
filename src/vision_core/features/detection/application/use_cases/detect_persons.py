from vision_core.core.validation import validate_frame
from vision_core.features.detection.application.dto.request.request_detector import RequestDetector
from vision_core.features.detection.application.dto.response.response_detector import ResponseDetector
from vision_core.features.detection.application.mappers.detection_mapper import detections_to_response
from vision_core.features.detection.domain.ports.detector_manager import DetectorManager


class DetectPersons:
    """Run person detection through the feature's detector port."""

    def __init__(self, detector: DetectorManager) -> None:
        self._detector = detector

    def execute(self, request: RequestDetector) -> ResponseDetector:
        validate_frame(request.frame)
        detections = self._detector.process(request.frame)
        return detections_to_response(detections)
