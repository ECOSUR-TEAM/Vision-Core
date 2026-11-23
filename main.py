import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import replace

from vision_core.core.config import Settings
from vision_core.core.config.persistence import PersistenceSettings
from vision_core.core.config.pipeline_config import PipelineConfig
from vision_core.core.infrastructure.persistence.persistence_service import PersistenceService
from vision_core.core.infrastructure.persistence.persisting_reid_memory import PersistingReIDMemory
from vision_core.core.infrastructure.persistence.retention_job import RetentionJob
from vision_core.core.infrastructure.persistence.retention_worker import RetentionWorker
from vision_core.core.model_registry.activation import resolve_active_models
from vision_core.core.telemetry.health import HealthStatus
from vision_core.core.telemetry.metrics import get_observability_metrics
from vision_core.features.camera_health.application.camera_quality_monitor import CameraQualityMonitor
from vision_core.features.camera_health.application.quality_thread import QualityThread
from vision_core.features.detection.infrastructure.dependencies import build_detection
from vision_core.features.door.domain.ports.door_analytics import DoorAnalytics
from vision_core.features.door.infrastructure.adapters.polygon_door_analytics import PolygonDoorAnalytics
from vision_core.features.door.infrastructure.adapters.uncalibrated_analytics import UncalibratedAnalytics
from vision_core.features.door.infrastructure.config.zone_loader import load_zones
from vision_core.features.door.infrastructure.dependencies import build_door
from vision_core.features.monitor.infrastructure import __main__ as monitor_cli
from vision_core.features.monitor.infrastructure.dependencies import build_monitor
from vision_core.features.monitor.infrastructure.latest_frame_buffer import LatestFrameBuffer
from vision_core.features.monitor.infrastructure.renderer import render_frame
from vision_core.features.monitor.infrastructure.renderer_thread import RendererThread
from vision_core.features.monitor.infrastructure.runtime import MonitorRuntime
from vision_core.features.pipeline.application.mappers.pipeline_mapper import event_to_json_dict
from vision_core.features.pipeline.infrastructure.dependencies import build_pipeline
from vision_core.features.reid.infrastructure.dependencies import build_reid
from vision_core.features.video.infrastructure.dependencies import build_video

logger = logging.getLogger(__name__)


def build_video_with(source=None, *, path=None, latest=False):
    return build_video(source=source, path=path, latest=latest)


def build_monitor_state(*, demo=False, settings=None, models=None):
    settings = settings or Settings.from_env(validate_startup=False)
    models = models or resolve_active_models(settings)
    metrics = get_observability_metrics()
    health = HealthStatus(
        minimum_free_disk_mb=settings.monitor.minimum_free_disk_mb,
        disk_path=settings.monitor.disk_check_path,
        model_metadata=models.as_health_metadata(),
    )
    health.set_ready(config_valid=True)
    logger.info("Modelos activos resueltos del registro", extra=models.as_log_identity())
    return build_monitor(
        demo=demo,
        event_serializer=event_to_json_dict,
        state=None,
        metrics=metrics,
        health=health,
        camera_id=settings.logging.camera_id,
    ).state


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


def build_monitor_pipeline(
    state,
    *,
    zones_file=None,
    settings=None,
    persistence=None,
    start_retention=True,
    config=None,
    render_enabled=None,
    models=None,
):
    settings = settings or Settings.from_env(validate_startup=False)
    models = models or resolve_active_models(settings)
    state.health.set_model_metadata(models.as_health_metadata())
    config = config or PipelineConfig.from_env()
    camera_id = getattr(state, "camera_id", None) or settings.logging.camera_id or "default"
    if render_enabled is not None:
        config = replace(config, render_enabled=render_enabled)
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
        renderer = None
        renderer_error = None
        quality_thread: QualityThread | None = None
        session_id = str(uuid.uuid4())
        try:
            persistence.start_session(session_id, time.time())
            zones = load_zones(zones_file) if zones_file else None
            if zones is not None:
                persistence.save_zones((zones.door, zones.exterior, zones.interior))
            analytics: DoorAnalytics
            if zones is None:
                analytics = UncalibratedAnalytics()
            else:
                analytics = PolygonDoorAnalytics(
                    zones.exterior,
                    zones.interior,
                    zones.door,
                    confirmation_frames=settings.zones.confirmation_frames,
                )

            def on_camera_quality(observation):
                publish_quality = getattr(state, "set_camera_quality", None)
                if publish_quality is not None:
                    publish_quality(observation.status, observation.reason, observation.signals)

            def on_quality_error(_error):
                state.metrics.increment("vision_core_camera_quality_errors_total", camera_id=camera_id)

            quality_monitor = CameraQualityMonitor(
                settings.camera_quality,
                expected_frame_size=(zones.width, zones.height) if zones else None,
                zones=zones,
                on_observation=on_camera_quality,
                on_error=on_quality_error,
            )
            door = build_door(analytics=analytics)
            detection = build_detection(
                model_path=str(settings.detection.model_path),
                device=settings.detection.device,
                precision=settings.detection.precision,
                confidence=settings.detection.confidence,
                classes=settings.detection.classes,
                tracking_enabled=settings.detection.tracking_enabled,
                max_missed_frames=settings.detection.max_missed_frames,
                model_descriptor=models.detection,
            )
            reid = build_reid(model_descriptor=models.embedding)
            memory = build_reid_with_persistence(reid.memory, persistence)
            if memory is not reid.memory:
                reid = build_reid(memory=memory, embedder=reid.embedder)
            source = build_video(latest=True, metrics=state.metrics)
            buffer: LatestFrameBuffer | None = LatestFrameBuffer() if config.render_enabled else None
            if buffer is None and settings.camera_quality.enabled:
                quality_thread = QualityThread(
                    lambda frame: quality_monitor.observe(frame, sampled=True),
                    sample_every_n_frames=settings.camera_quality.sample_every_n_frames,
                    on_error=on_quality_error,
                )
                quality_thread.start()
            if buffer is not None:

                def render_job(job):
                    quality_monitor.observe(job.frame)
                    jpeg, people = render_frame(
                        job.frame,
                        job.tracks,
                        job.zones,
                        None,
                        job.label_for,
                        demo=job.demo,
                        zone_by_person=job.zone_by_person,
                    )
                    stats = buffer.stats()
                    state.publish(
                        jpeg,
                        people,
                        job.processing_ms,
                        job.dropped + stats["dropped"],
                        stats["queued"],
                        camera_id=camera_id,
                    )

                renderer = RendererThread(
                    buffer,
                    render_job,
                    on_error=lambda error: state.set_status("error", type(error).__name__),
                )
                renderer.start()

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
                if renderer is None or buffer is None:
                    if quality_thread is not None:
                        quality_thread.submit(frame)
                    return
                zone_by_person = {}
                for track in tracks:
                    history = analytics.get_history(track.person_id)
                    zone_by_person[track.person_id] = history[-1].zone if history else "fuera"
                renderer.submit(
                    frame,
                    tracks,
                    zones=zones,
                    zone_by_person=zone_by_person,
                    label_for=state.person_label,
                    demo=state.demo,
                    processing_ms=ms,
                    dropped=source.dropped_frames,
                )

            def should_stop() -> bool:
                return stop_requested() or (renderer is not None and renderer.failed.is_set())

            app = build_pipeline(
                video=source,
                detector=detection.detector,
                reid=reid.memory,
                door=door.analytics,
                embedder=reid.embedder,
                on_event=on_event,
                expected_frame_size=(zones.width, zones.height) if zones else None,
                on_frame=on_frame,
                config=config,
                camera_id=camera_id,
            )
            app.set_observability(state.metrics, camera_id=camera_id)
            persistence_settings = persistence.settings
            if start_retention and persistence_settings.enabled:
                retention_worker = RetentionWorker(
                    RetentionJob(persistence),
                    interval_seconds=persistence_settings.prune_interval_seconds,
                )
                retention_worker.start()
            app.run(should_stop)
            if renderer is not None and renderer.failed.is_set():
                raise renderer.error or RuntimeError("Fallo en el hilo de renderizado")
        finally:
            if renderer is not None:
                renderer.close(timeout=2)
                renderer_error = renderer.error
            if quality_thread is not None:
                quality_thread.close(timeout=2)
            if retention_worker is not None:
                retention_worker.stop()
            persistence.finish_session(session_id, time.time())
            if source is not None:
                source.close()
            persistence.close()
        if renderer_error is not None:
            raise renderer_error

    return pipeline


def build_monitor_runtime(
    state,
    *,
    zones_file=None,
    exit_on_error=False,
    on_failure=None,
    settings=None,
    persistence=None,
    start_retention=True,
    config=None,
    render_enabled=None,
    models=None,
):
    settings = settings or Settings.from_env()
    models = models or resolve_active_models(settings)
    state.health.set_model_metadata(models.as_health_metadata())
    return MonitorRuntime(
        build_monitor_pipeline(
            state,
            zones_file=zones_file,
            settings=settings,
            persistence=persistence,
            start_retention=start_retention,
            config=config,
            render_enabled=render_enabled,
            models=models,
        ),
        state,
        exit_on_error=exit_on_error,
        on_failure=on_failure,
    )


def main() -> None:
    monitor_cli.main(
        build_state=build_monitor_state,
        build_runtime=build_monitor_runtime,
    )


if __name__ == "__main__":
    main()
