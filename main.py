import os

from application.vision_core_app import VisionCoreApp
from domain.entities import Event, Polygon
from infrastructure.video.rtsp_video_source import RtspVideoSource
from infrastructure.detection.yolo_detector_manager import YoloDetectorManager
from infrastructure.reid.memory_reid import InMemoryReID
from infrastructure.door.polygon_door_analytics import PolygonDoorAnalytics


def dummy_embedder(crop):
    raise NotImplementedError("Embedder de ReID pendiente (VC-REID)")


def print_event(event: Event) -> None:
    print(event)


def main() -> None:
    rtsp_url = os.getenv("VISION_CORE_RTSP_URL", "rtsp://frigate:8554/stream")

    exterior = Polygon(name="exterior", points=((0, 0), (100, 0), (100, 100), (0, 100)))
    interior = Polygon(name="interior", points=((100, 0), (200, 0), (200, 100), (100, 100)))

    app = VisionCoreApp(
        video_source=RtspVideoSource(rtsp_url),
        detector=YoloDetectorManager(),
        reid_memory=InMemoryReID(),
        door_analytics=PolygonDoorAnalytics(exterior, interior),
        embedder=dummy_embedder,
        on_event=print_event,
    )
    app.run()


if __name__ == "__main__":
    main()
