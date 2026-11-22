from vision_core.core.config.pipeline_config import PipelineConfig
from vision_core.features.detection.domain.ports.detector_manager import DetectorManager
from vision_core.features.door.domain.ports.door_analytics import DoorAnalytics
from vision_core.features.pipeline.application.use_cases.run_pipeline import RunPipeline
from vision_core.features.pipeline.domain.ports.event_consumer import EventConsumer
from vision_core.features.reid.domain.ports.embedding_extractor import EmbeddingExtractor
from vision_core.features.reid.domain.ports.reid_memory import ReIDMemory
from vision_core.features.video.domain.ports.video_source import VideoSource


def build_pipeline(
    video: VideoSource,
    detector: DetectorManager,
    reid: ReIDMemory,
    door: DoorAnalytics,
    embedder: EmbeddingExtractor,
    on_event: EventConsumer,
    *,
    expected_frame_size: tuple[int, int] | None = None,
    on_frame=None,
    config: PipelineConfig | None = None,
    camera_id: str = "default",
) -> RunPipeline:
    return RunPipeline(
        video=video,
        detector=detector,
        reid=reid,
        door=door,
        embedder=embedder,
        on_event=on_event,
        expected_frame_size=expected_frame_size,
        on_frame=on_frame,
        config=config,
        camera_id=camera_id,
    )
