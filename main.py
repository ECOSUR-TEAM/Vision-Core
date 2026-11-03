import logging
import os

from application.vision_core_app import VisionCoreApp
from domain.entities import Event
from infrastructure.video.rtsp_video_source import RtspVideoSource
from infrastructure.detection.yolo_detector_manager import YoloDetectorManager
from infrastructure.reid.memory_reid import InMemoryReID
from infrastructure.reid.embedder import TorchvisionEmbeddingExtractor
from infrastructure.door.polygon_door_analytics import PolygonDoorAnalytics
from infrastructure.door.zone_config import load_zones


def print_event(event: Event) -> None:
    print(event.to_json())


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    video_source = RtspVideoSource.from_env()

    zones = load_zones(os.environ["VISION_CORE_ZONES_FILE"])

    app = VisionCoreApp(
        video_source=video_source,
        detector=YoloDetectorManager(),
        reid_memory=InMemoryReID(),
        door_analytics=PolygonDoorAnalytics(zones.exterior, zones.interior, zones.door,
            confirmation_frames=int(os.getenv("VISION_CORE_ZONE_CONFIRMATION_FRAMES", "3"))),
        embedder=TorchvisionEmbeddingExtractor.from_env(),
        on_event=print_event,
        expected_frame_size=(zones.width, zones.height),
    )
    app.run()


if __name__ == "__main__":
    main()
