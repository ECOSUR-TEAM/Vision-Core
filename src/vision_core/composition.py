"""Single composition root: wire concrete adapters into the application."""

import logging
import threading

from vision_core.application.vision_core_app import VisionCoreApp
from vision_core.settings import Settings

logger = logging.getLogger(__name__)


def build_zones(path):
    from vision_core.infrastructure.door.zone_loader import load_zones

    return load_zones(path)


def build_video_with(source=None, *, path=None, latest=False):
    from vision_core.features.video.infrastructure.dependencies import build_video

    return build_video(source=source, path=path, latest=latest)


def build_video_source():
    return build_video_with()


def build_door_analytics(zones=None, *, confirmation_frames=None, settings=None):
    if zones is None:
        from vision_core.infrastructure.door.uncalibrated_analytics import (
            UncalibratedAnalytics,
        )

        return UncalibratedAnalytics()
    from vision_core.infrastructure.door.polygon_door_analytics import (
        PolygonDoorAnalytics,
    )

    if confirmation_frames is None:
        settings = settings or Settings.from_env()
        confirmation_frames = settings.zones.confirmation_frames
    return PolygonDoorAnalytics(
        zones.exterior,
        zones.interior,
        zones.door,
        confirmation_frames=confirmation_frames,
    )


def build_vision_core_app(
    *,
    video_source,
    door_analytics,
    on_event,
    on_frame=None,
    expected_frame_size=None,
    detector=None,
    reid_memory=None,
    embedder=None,
    settings=None,
) -> VisionCoreApp:
    if settings is None and (detector is None or reid_memory is None or embedder is None):
        settings = Settings.from_env()
    if detector is None:
        from vision_core.infrastructure.detection.yolo_detector_manager import (
            YoloDetectorManager,
        )

        detector = YoloDetectorManager(
            str(settings.detection.model_path),
            confidence=settings.detection.confidence,
            classes=settings.detection.classes,
            tracking_enabled=settings.detection.tracking_enabled,
            max_missed_frames=settings.detection.max_missed_frames,
        )
    if reid_memory is None:
        from vision_core.infrastructure.reid.memory_reid import InMemoryReID

        reid_memory = InMemoryReID.from_env()
    if embedder is None:
        from vision_core.infrastructure.reid.embedder import (
            TorchvisionEmbeddingExtractor,
        )

        embedder = TorchvisionEmbeddingExtractor.from_env()
    return VisionCoreApp(
        video_source=video_source,
        detector=detector,
        reid_memory=reid_memory,
        door_analytics=door_analytics,
        embedder=embedder,
        on_event=on_event,
        expected_frame_size=expected_frame_size,
        on_frame=on_frame,
    )


def build_monitor_state(*, demo=False):
    from vision_core.application.event_serializer import event_to_dict
    from vision_core.infrastructure.monitor.state import MonitorState

    return MonitorState(demo=demo, event_serializer=event_to_dict)


class MonitorRuntime:
    """Own the monitor pipeline worker thread outside the infrastructure layer."""

    def __init__(self, pipeline, state, *, exit_on_error=False, on_failure=None):
        self._pipeline = pipeline
        self._state = state
        self._exit_on_error = exit_on_error
        self._on_failure = on_failure
        self._stop = threading.Event()
        self._thread = None
        self.failed = threading.Event()

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        try:
            self._pipeline(self._stop.is_set)
            self._state.set_status("stopped")
        except Exception as error:  # noqa: BLE001 - límite del hilo: cualquier fallo se refleja en el estado
            # Do not expose URLs, credentials or native exception messages in HTTP.
            kind = type(error).__name__
            self._state.set_status("error", kind)
            logger.error("Pipeline detenido (%s). Revisa stream, zonas y pesos locales.", kind)
            if self._exit_on_error:
                self.failed.set()
                if self._on_failure is not None:
                    self._on_failure()

    def stop(self):
        self._stop.set()

    def join(self, timeout=None):
        if self._thread is not None:
            self._thread.join(timeout)


def build_monitor_runtime(state, *, zones_file=None, exit_on_error=False, on_failure=None, settings=None):
    from vision_core.infrastructure.monitor.renderer import render_frame
    from vision_core.infrastructure.video.latest_frame_source import LatestFrameSource
    settings = settings or Settings.from_env()

    def pipeline(stop_requested):
        source = None
        try:
            # Adapters load models lazily so the monitor can report startup failures.
            zones = build_zones(zones_file) if zones_file else None
            analytics = build_door_analytics(zones, settings=settings)
            source = LatestFrameSource(build_video_source())
            app = build_vision_core_app(
                video_source=source,
                door_analytics=analytics,
                settings=settings,
                on_event=state.event,
                expected_frame_size=(zones.width, zones.height) if zones else None,
                on_frame=lambda frame, tracks, ms: state.publish(
                    *render_frame(frame, tracks, zones, analytics, state.person_label, demo=state.demo),
                    ms,
                    source.dropped_frames,
                ),
            )
            app.run(stop_requested)
        finally:
            if source is not None:
                source.close()

    return MonitorRuntime(pipeline, state, exit_on_error=exit_on_error, on_failure=on_failure)
