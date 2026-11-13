"""python -m scripts.validate_pipeline --video recording.avi --zones zones.json"""
import argparse
import json
import time
import platform
import numpy as np
import torch
from dataclasses import asdict
from pathlib import Path

from application.vision_core_app import VisionCoreApp
from application.event_serializer import event_to_dict
from domain.ports import VideoSource, DetectorManager
from infrastructure.video.file_video_source import FileVideoSource
from infrastructure.video.rtsp_video_source import RtspVideoSource
from infrastructure.detection.yolo_detector_manager import YoloDetectorManager
from infrastructure.reid.embedder import TorchvisionEmbeddingExtractor
from infrastructure.reid.memory_reid import InMemoryReID
from infrastructure.door.polygon_door_analytics import PolygonDoorAnalytics
from infrastructure.door.zone_config import load_zones


class MeasuredApp(VisionCoreApp):
    def __init__(self, *args, output, **kwargs):
        super().__init__(*args, **kwargs)
        self.output = output
        self.durations = []

    def _process_frame(self, frame):
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        start = time.perf_counter()
        super()._process_frame(frame)
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        elapsed = time.perf_counter() - start
        self.durations.append(elapsed)
        self.output.write(json.dumps({'kind': 'resolved', 'frame': self._video.frames,
            'persons': self._person_by_track, 'processing_ms': elapsed * 1000}) + '\n')


class LimitedSource(VideoSource):
    def __init__(self, source, limit):
        self.source, self.limit, self.frames = source, limit, 0
        self.read_seconds = []
    def open(self):
        self.source.open()
    def read_frame(self):
        if self.frames >= self.limit:
            return None
        start = time.perf_counter()
        frame = self.source.read_frame()
        if frame is not None:
            self.read_seconds.append(time.perf_counter() - start)
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
                output.write(json.dumps({'kind': 'event', 'frame': source.frames,
                                         **event_to_dict(event)}) + '\n')
            app = MeasuredApp(source, detector, InMemoryReID.from_env(),
                PolygonDoorAnalytics(zones.exterior, zones.interior, zones.door),
                TorchvisionEmbeddingExtractor.from_env(), emit,
                expected_frame_size=(zones.width, zones.height), output=output)
            run_start = time.perf_counter()
            app.run()
            run_seconds = time.perf_counter() - run_start
        except Exception as error:
            output.write(json.dumps({'kind': 'summary', 'status': 'failed',
                                    'error_type': type(error).__name__, 'frames': source.frames}) + '\n')
            raise
        output.write(json.dumps({'kind': 'summary', 'status': 'completed',
                                'frames': source.frames, 'seconds': time.perf_counter()-start,
                                'reconnections': getattr(source.source, 'reconnections', 0),
                                'processing_fps': source.frames / sum(app.durations) if app.durations else None,
                                'pipeline_fps': source.frames / run_seconds,
                                'processing_ms': {key: float(np.percentile(app.durations, percentile))*1000
                                    for key, percentile in [('p50',50),('p95',95),('p99',99)]} if app.durations else None,
                                'mean_read_ms': float(np.mean(source.read_seconds))*1000 if source.read_seconds else None,
                                'capture_to_event_latency_ms': None,
                                'environment': {'platform': platform.platform(), 'torch': torch.__version__,
                                    'cuda_available': torch.cuda.is_available(), 'model': args.model}}) + '\n')


if __name__ == '__main__':
    main()
