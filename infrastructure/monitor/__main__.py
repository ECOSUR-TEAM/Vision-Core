"""python -m infrastructure.monitor --demo-zones --port 8080"""
import argparse
import logging
import os
import signal
import threading
from pathlib import Path

from .server import MonitorState, make_server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--zones', default=os.getenv('VISION_CORE_ZONES_FILE'))
    parser.add_argument('--uncalibrated', action='store_true',
                        default=os.getenv('VISION_CORE_MONITOR_UNCALIBRATED', '0') == '1',
                        help='Detectar y recordar personas sin inventar zonas ni cruces')
    parser.add_argument('--demo-zones', action='store_true',
                        default=os.getenv('VISION_CORE_MONITOR_DEMO_ZONES', '0') == '1',
                        help='Zonas ilustrativas de 640 × 480 para webcam')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('Puerto inválido')
    if args.uncalibrated:
        args.zones = None
    elif args.demo_zones:
        args.zones = str(Path(__file__).resolve().parents[2] / 'config/zones.example.json')
    elif not args.zones:
        parser.error('Indica --zones o --demo-zones')
    logging.basicConfig(level=logging.INFO)
    state = MonitorState(demo=args.demo_zones or args.uncalibrated)
    server = make_server(args.host, args.port, state)
    stop = threading.Event()
    failed = threading.Event()

    def pipeline():
        source = None
        try:
            # Load models in the worker so the UI can explain startup/failure.
            from application.vision_core_app import VisionCoreApp
            from infrastructure.video.rtsp_video_source import RtspVideoSource
            from infrastructure.video.latest_frame_source import LatestFrameSource
            from infrastructure.detection.yolo_detector_manager import YoloDetectorManager
            from infrastructure.reid.memory_reid import InMemoryReID
            from infrastructure.reid.embedder import TorchvisionEmbeddingExtractor
            from infrastructure.door.polygon_door_analytics import PolygonDoorAnalytics
            from infrastructure.door.zone_config import load_zones
            from infrastructure.door.uncalibrated_analytics import UncalibratedAnalytics

            zones = load_zones(args.zones) if args.zones else None
            analytics = (PolygonDoorAnalytics(zones.exterior, zones.interior, zones.door,
                confirmation_frames=int(os.getenv('VISION_CORE_ZONE_CONFIRMATION_FRAMES', '3')))
                if zones else UncalibratedAnalytics())
            source = LatestFrameSource(RtspVideoSource.from_env())
            app = VisionCoreApp(source, YoloDetectorManager(), InMemoryReID.from_env(), analytics,
                TorchvisionEmbeddingExtractor.from_env(), state.event,
                expected_frame_size=(zones.width, zones.height) if zones else None,
                on_frame=lambda frame, tracks, ms: state.publish(
                    frame, tracks, ms, zones, analytics, source.dropped_frames))
            app.run(stop.is_set)
            state.set_status('stopped')
        except Exception as error:
            # Do not expose URLs, credentials or native exception messages in HTTP.
            kind = type(error).__name__
            state.set_status('error', kind)
            logging.error('Pipeline detenido (%s). Revisa stream, zonas y pesos locales.', kind)
            if os.getenv('VISION_CORE_MONITOR_EXIT_ON_ERROR', '0') == '1':
                failed.set()
                server.shutdown()
        finally:
            if source is not None:
                source.close()

    worker = threading.Thread(target=pipeline, daemon=True)
    worker.start()
    def terminate(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, terminate)
    print(f'Vision Core: http://{args.host}:{args.port}', flush=True)
    try:
        server.serve_forever(poll_interval=.25)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.server_close()
        worker.join(timeout=2)
    if failed.is_set():
        raise SystemExit(1)


if __name__ == '__main__':
    main()
