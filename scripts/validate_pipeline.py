"""python -m scripts.validate_pipeline --video recording.avi --zones zones.json"""
import argparse
import json
import time
from dataclasses import asdict
from pathlib import Path

from application.vision_core_app import VisionCoreApp
from domain.ports import VideoSource, DetectorManager
from infrastructure.video.file_video_source import FileVideoSource
from infrastructure.video.rtsp_video_source import RtspVideoSource
from infrastructure.detection.yolo_detector_manager import YoloDetectorManager
from infrastructure.reid.embedder import TorchvisionEmbeddingExtractor
from infrastructure.reid.memory_reid import InMemoryReID
from infrastructure.door.polygon_door_analytics import PolygonDoorAnalytics
from infrastructure.door.zone_config import load_zones


class LimitedSource(VideoSource):
    def __init__(self, source, limit):
        self.source, self.limit, self.frames = source, limit, 0
    def open(self):
        self.source.open()
    def read_frame(self):
        if self.frames >= self.limit:
            return None
        frame = self.source.read_frame()
        if frame is not None:
            self.frames += 1
        return frame
    def close(self):
        self.source.close()


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
            self.output.write(json.dumps({'kind': 'lost_tracks', 'frame': self.frame, 'ids': lost}) + '\n')
        return lost


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video', help='Si se omite, usa VISION_CORE_RTSP_URL')
    parser.add_argument('--zones', required=True)
    parser.add_argument('--model', default='yolov8n.pt')
    parser.add_argument('--frames', type=int, default=300)
    parser.add_argument('--output', required=True, help='Nuevo archivo JSONL')
    args = parser.parse_args()
    if args.frames <= 0:
        parser.error('--frames debe ser positivo')
    zones = load_zones(args.zones)
    source = LimitedSource(FileVideoSource(args.video) if args.video else RtspVideoSource.from_env(), args.frames)
    with Path(args.output).open('x') as output:
        start = time.perf_counter()
        try:
            detector = RecordedDetector(YoloDetectorManager(args.model), output)
            def emit(event):
                output.write(json.dumps({'kind': 'event', 'frame': source.frames, **event.to_dict()}) + '\n')
            app = VisionCoreApp(source, detector, InMemoryReID(),
                PolygonDoorAnalytics(zones.exterior, zones.interior, zones.door),
                TorchvisionEmbeddingExtractor.from_env(), emit,
                expected_frame_size=(zones.width, zones.height))
            app.run()
        except Exception as error:
            output.write(json.dumps({'kind': 'summary', 'status': 'failed',
                                    'error_type': type(error).__name__, 'frames': source.frames}) + '\n')
            raise
        output.write(json.dumps({'kind': 'summary', 'status': 'completed',
                                'frames': source.frames, 'seconds': time.perf_counter()-start,
                                'reconnections': getattr(source.source, 'reconnections', 0)}) + '\n')


if __name__ == '__main__':
    main()
