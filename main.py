import os
import time
import uuid
from collections.abc import Callable

from vision_core.features.detection.infrastructure.dependencies import build_detection
from vision_core.features.door.infrastructure.adapters.polygon_door_analytics import PolygonDoorAnalytics
from vision_core.features.door.infrastructure.adapters.uncalibrated_analytics import UncalibratedAnalytics
from vision_core.features.door.infrastructure.config.zone_loader import load_zones
from vision_core.features.door.infrastructure.dependencies import build_door
from vision_core.features.monitor.infrastructure.dependencies import build_monitor
from vision_core.features.monitor.infrastructure.renderer import render_frame
from vision_core.features.monitor.infrastructure.runtime import MonitorRuntime
from vision_core.features.pipeline.application.mappers.pipeline_mapper import event_to_dict
from vision_core.features.pipeline.infrastructure.dependencies import build_pipeline
from vision_core.features.reid.infrastructure.dependencies import build_reid
from vision_core.features.video.infrastructure.dependencies import build_video
from vision_core.infrastructure.monitor import __main__ as monitor_cli
from vision_core.infrastructure.persistence.persistence_service import PersistenceService
from vision_core.infrastructure.persistence.persisting_reid_memory import PersistingReIDMemory
from vision_core.infrastructure.persistence.retention_job import RetentionJob
from vision_core.infrastructure.persistence.retention_worker import RetentionWorker
from vision_core.settings.persistence import PersistenceSettings


def build_video_with(source=None, *, path=None, latest=False):
    return build_video(source=source, path=path, latest=latest)


def build_monitor_state(*, demo=False):
    return build_monitor(demo=demo, event_serializer=event_to_dict).state


def build_persistence(settings=None):
    return PersistenceService(settings if settings is not None else PersistenceSettings.from_env())


def build_reid_with_persistence(memory, persistence):
    if not persistence.settings.enabled:
        return memory
    return PersistingReIDMemory(
        memory,
        persistence.save_identity,
        list_identities=persistence.list_identities,
        identity_ttl_seconds=persistence.settings.identity_ttl_seconds,
    )


def build_monitor_runtime(
    state,
    *,
    zones_file=None,
    exit_on_error=False,
    on_failure=None,
    persistence=None,
    start_retention=True,
):
    if persistence is None:
        persistence = build_persistence()
    set_persistence_provider = getattr(state, "set_persistence_provider", None)
    if set_persistence_provider is not None:
        set_persistence_provider(lambda: persistence.health())
    else:
        set_persistence = getattr(state, "set_persistence", None)
        if set_persistence is not None:
            set_persistence(persistence.health())

    def pipeline(stop_requested: Callable[[], bool]) -> None:
        source = None
        retention_worker = None
        session_id = str(uuid.uuid4())
        try:
            persistence.start_session(session_id, time.time())
            zones = load_zones(zones_file) if zones_file else None
            if zones is not None:
                persistence.save_zones((zones.door, zones.exterior, zones.interior))
            if zones is None:
                analytics = UncalibratedAnalytics()
            else:
                confirmation_frames = int(os.getenv("VISION_CORE_ZONE_CONFIRMATION_FRAMES", "3"))
                analytics = PolygonDoorAnalytics(
                    zones.exterior,
                    zones.interior,
                    zones.door,
                    confirmation_frames=confirmation_frames,
                )
            door = build_door(analytics=analytics)
            detection = build_detection()
            reid = build_reid()
            memory = build_reid_with_persistence(reid.memory, persistence)
            if memory is not reid.memory:
                reid = build_reid(memory=memory, embedder=reid.embedder)
            source = build_video(latest=True)

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

            app = build_pipeline(
                video=source,
                detector=detection.detector,
                reid=reid.memory,
                door=door.analytics,
                embedder=reid.embedder,
                on_event=on_event,
                expected_frame_size=(zones.width, zones.height) if zones else None,
                on_frame=on_frame,
            )
            settings = persistence.settings
            if start_retention and settings.enabled:
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


def main() -> None:
    monitor_cli.main(
        build_state=build_monitor_state,
        build_runtime=build_monitor_runtime,
    )


if __name__ == "__main__":
    main()
