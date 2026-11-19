"""Single composition root: wire concrete adapters into the application."""

import logging
import os
import threading
import time
import uuid

from vision_core.application.vision_core_app import VisionCoreApp
from vision_core.infrastructure.persistence.persistence_service import PersistenceService
from vision_core.infrastructure.persistence.persisting_reid_memory import PersistingReIDMemory
from vision_core.infrastructure.persistence.retention_job import RetentionJob
from vision_core.infrastructure.persistence.retention_worker import RetentionWorker
from vision_core.settings.persistence import PersistenceSettings

logger = logging.getLogger(__name__)


def build_zones(path):
    from vision_core.infrastructure.door.zone_loader import load_zones

    return load_zones(path)


def build_video_with(source=None, *, path=None, latest=False):
    from vision_core.features.video.infrastructure.dependencies import build_video

    return build_video(source=source, path=path, latest=latest)


def build_video_source():
    return build_video_with()


def build_door_analytics(zones=None, *, confirmation_frames=None):
    if zones is None:
        from vision_core.infrastructure.door.uncalibrated_analytics import (
            UncalibratedAnalytics,
        )

        return UncalibratedAnalytics()
    from vision_core.infrastructure.door.polygon_door_analytics import (
        PolygonDoorAnalytics,
    )

    if confirmation_frames is None:
        confirmation_frames = int(os.getenv("VISION_CORE_ZONE_CONFIRMATION_FRAMES", "3"))
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
    persistence=None,
) -> VisionCoreApp:
    if detector is None:
        from vision_core.infrastructure.detection.yolo_detector_manager import (
            YoloDetectorManager,
        )

        detector = YoloDetectorManager()
    if reid_memory is None:
        from vision_core.infrastructure.reid.memory_reid import InMemoryReID

        reid_memory = InMemoryReID.from_env()
    if embedder is None:
        from vision_core.infrastructure.reid.embedder import (
            TorchvisionEmbeddingExtractor,
        )

        embedder = TorchvisionEmbeddingExtractor.from_env()
    if persistence is not None and getattr(getattr(persistence, "settings", None), "enabled", False):
        reid_memory = PersistingReIDMemory(reid_memory, persistence.save_identity)
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


def build_persistence(settings=None) -> PersistenceService:
    if settings is None:
        settings = PersistenceSettings.from_env()
    return PersistenceService(settings)


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


def build_monitor_runtime(
    state,
    *,
    zones_file=None,
    exit_on_error=False,
    on_failure=None,
    persistence=None,
    start_retention=True,
):
    from vision_core.infrastructure.monitor.renderer import render_frame
    from vision_core.infrastructure.video.latest_frame_source import LatestFrameSource

    if persistence is None:
        persistence = build_persistence()
    session_id = str(uuid.uuid4())
    set_persistence = getattr(state, "set_persistence", None)
    if set_persistence is not None:
        health = persistence.health() if hasattr(persistence, "health") else {"enabled": False}
        set_persistence(health)

    def pipeline(stop_requested):
        source = None
        retention_worker = None
        try:
            persistence.start_session(session_id, time.time())
            # Adapters load models lazily so the monitor can report startup failures.
            zones = build_zones(zones_file) if zones_file else None
            if zones is not None:
                persistence.save_zones((zones.door, zones.exterior, zones.interior))
            analytics = build_door_analytics(zones)
            source = LatestFrameSource(build_video_source())

            def on_event(event):
                state.event(event)
                persistence.append_event(event, session_id)
                persistence.record_metric(session_id, event.event, 1.0, event.timestamp)

            def on_frame(frame, tracks, ms):
                for track in tracks:
                    if track.track_id is None:
                        continue
                    bbox = track.bbox
                    persistence.append_track(
                        session_id,
                        track.track_id,
                        track.person_id,
                        (bbox.x1, bbox.y1, bbox.x2, bbox.y2),
                        time.time(),
                    )
                state.publish(
                    *render_frame(frame, tracks, zones, analytics, state.person_label, demo=state.demo),
                    ms,
                    source.dropped_frames,
                )

            app = build_vision_core_app(
                video_source=source,
                door_analytics=analytics,
                on_event=on_event,
                expected_frame_size=(zones.width, zones.height) if zones else None,
                on_frame=on_frame,
                persistence=persistence,
            )
            settings = getattr(persistence, "settings", None)
            if start_retention and settings is not None and settings.enabled:
                retention_worker = RetentionWorker(
                    RetentionJob(persistence),
                    interval_seconds=settings.prune_interval_seconds,
                )
                retention_worker.start()
            app.run(stop_requested)
        finally:
            if retention_worker is not None:
                retention_worker.stop()
            persistence.finish_session(session_id, time.time())
            if source is not None:
                source.close()
            persistence.close()

    return MonitorRuntime(pipeline, state, exit_on_error=exit_on_error, on_failure=on_failure)
