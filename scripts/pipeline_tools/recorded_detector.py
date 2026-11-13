import json
from dataclasses import asdict

from domain.ports import DetectorManager


class RecordedDetector(DetectorManager):
    def __init__(self, detector, output):
        self.detector, self.output, self.frame = detector, output, 0

    def process(self, frame):
        self.frame += 1
        detections = self.detector.process(frame)
        self.output.write(json.dumps({'kind': 'detections', 'frame': self.frame,
                                     'detections': [asdict(d) for d in detections]}) + '\n')
        return detections

    def pop_lost_track_ids(self):
        lost = self.detector.pop_lost_track_ids()
        if lost:
            self.output.write(json.dumps({'kind': 'lost_tracks', 'frame': self.frame,
                                          'ids': lost}) + '\n')
        return lost
