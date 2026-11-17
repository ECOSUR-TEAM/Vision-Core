from domain.model.bbox import BBox
from domain.model.detection import Detection


class FakeDetector:
    def __init__(self, detections_per_frame=None, lost_ids_per_call=None):
        self._detections_per_frame = detections_per_frame
        self._lost_ids_per_call = list(lost_ids_per_call or [])

    def process(self, frame):
        if self._detections_per_frame is not None:
            return self._detections_per_frame.pop(0)
        return [Detection(bbox=BBox(0, 0, 10, 10), class_id=0, confidence=0.9, track_id=1)]

    def pop_lost_track_ids(self):
        return self._lost_ids_per_call.pop(0) if self._lost_ids_per_call else []
