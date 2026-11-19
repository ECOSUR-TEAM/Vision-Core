import os
from collections.abc import Callable
from dataclasses import replace

from vision_core.application.pipeline_config import PipelineConfig
from vision_core.features.detection.infrastructure.dependencies import build_detection
from vision_core.features.door.infrastructure.adapters.polygon_door_analytics import PolygonDoorAnalytics
from vision_core.features.door.infrastructure.adapters.uncalibrated_analytics import UncalibratedAnalytics
from vision_core.features.door.infrastructure.config.zone_loader import load_zones
from vision_core.features.door.infrastructure.dependencies import build_door
from vision_core.features.monitor.infrastructure.dependencies import build_monitor
from vision_core.features.monitor.infrastructure.latest_frame_buffer import LatestFrameBuffer
from vision_core.features.monitor.infrastructure.renderer import render_frame
from vision_core.features.monitor.infrastructure.renderer_thread import RendererThread
from vision_core.features.monitor.infrastructure.runtime import MonitorRuntime
from vision_core.features.pipeline.application.mappers.pipeline_mapper import event_to_dict
from vision_core.features.pipeline.infrastructure.dependencies import build_pipeline
from vision_core.features.reid.infrastructure.dependencies import build_reid
from vision_core.features.video.infrastructure.dependencies import build_video
from vision_core.infrastructure.monitor import __main__ as monitor_cli


def build_video_with(source=None, *, path=None, latest=False):
    return build_video(source=source, path=path, latest=latest)


def build_monitor_state(*, demo=False):
    return build_monitor(demo=demo, event_serializer=event_to_dict).state


def build_monitor_runtime(
    state,
    *,
    zones_file=None,
    exit_on_error=False,
    on_failure=None,
    render_enabled=None,
    config=None,
):
    config = config or PipelineConfig.from_env()
    if render_enabled is not None:
        config = replace(config, render_enabled=render_enabled)

    def pipeline(stop_requested: Callable[[], bool]) -> None:
        source = None
        renderer = None
        renderer_error = None
        try:
            zones = load_zones(zones_file) if zones_file else None
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
            source = build_video(latest=True)

            if config.render_enabled:

                def render_job(job):
                    jpeg, people = render_frame(
                        job.frame,
                        job.tracks,
                        job.zones,
                        None,
                        job.label_for,
                        demo=job.demo,
                        zone_by_person=job.zone_by_person,
                    )
                    state.publish(jpeg, people, job.processing_ms, job.dropped)

                renderer = RendererThread(
                    LatestFrameBuffer(),
                    render_job,
                    on_error=lambda error: state.set_status("error", type(error).__name__),
                )
                renderer.start()

            def on_frame(frame, tracks, ms):
                if renderer is None:
                    return
                zone_by_person = {}
                for track in tracks:
                    history = analytics.get_history(track.person_id)
                    zone_by_person[track.person_id] = history[-1].zone if history else "fuera"
                # RenderJob.capture se ejecuta en el hilo de inferencia: copia
                # el frame y congela tracks antes de publicarlos.
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
                # Un fallo del renderer también detiene la inferencia: no tiene
                # sentido seguir produciendo frames que nadie puede publicar.
                return stop_requested() or (renderer is not None and renderer.failed.is_set())

            app = build_pipeline(
                video=source,
                detector=detection.detector,
                reid=reid.memory,
                door=door.analytics,
                embedder=reid.embedder,
                on_event=state.event,
                expected_frame_size=(zones.width, zones.height) if zones else None,
                on_frame=on_frame,
                config=config,
            )
            app.run(should_stop)
            if renderer is not None and renderer.failed.is_set():
                raise renderer.error or RuntimeError("Fallo en el hilo de renderizado")
        finally:
            if renderer is not None:
                renderer.close(timeout=2)
                renderer_error = renderer.error
            if source is not None:
                source.close()
        if renderer_error is not None:
            raise renderer_error

    return MonitorRuntime(pipeline, state, exit_on_error=exit_on_error, on_failure=on_failure)


def main() -> None:
    monitor_cli.main(
        build_state=build_monitor_state,
        build_runtime=build_monitor_runtime,
    )


if __name__ == "__main__":
    main()
