import logging

from application.vision_core_app import VisionCoreApp
from domain.entities import Event, Polygon
from infrastructure.video.rtsp_video_source import RtspVideoSource
from infrastructure.detection.yolo_detector_manager import YoloDetectorManager
from infrastructure.reid.memory_reid import InMemoryReID
from infrastructure.reid.embedder import TorchvisionEmbeddingExtractor
from infrastructure.door.polygon_door_analytics import PolygonDoorAnalytics


def print_event(event: Event) -> None:
    print(event.to_json())


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    video_source = RtspVideoSource.from_env()

    exterior = Polygon(name="exterior", points=((0, 0), (100, 0), (100, 100), (0, 100)))
    interior = Polygon(name="interior", points=((100, 0), (200, 0), (200, 100), (100, 100)))

    app = VisionCoreApp(
        video_source=video_source,
        detector=YoloDetectorManager(),
        reid_memory=InMemoryReID(),
        door_analytics=PolygonDoorAnalytics(exterior, interior),
        embedder=TorchvisionEmbeddingExtractor(),
        on_event=print_event,
    )
    app.run()


if __name__ == "__main__":
    main()
