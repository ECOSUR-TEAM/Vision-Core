import os
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
from vision_core.shared.errors import ConfigurationError


def build_video_with(source=None, *, path=None, latest=False):
    return build_video(source=source, path=path, latest=latest)


def build_monitor_state(*, demo=False):
    return build_monitor(demo=demo, event_serializer=event_to_dict).state


def build_monitor_runtime(state, *, zones_file=None, exit_on_error=False, on_failure=None):
    def pipeline(stop_requested: Callable[[], bool]) -> None:
        source = None
        try:
            zones = load_zones(zones_file) if zones_file else None
            if zones is None:
                analytics = UncalibratedAnalytics()
            else:
                try:
                    confirmation_frames = int(os.getenv("VISION_CORE_ZONE_CONFIRMATION_FRAMES", "3"))
                except (TypeError, ValueError) as error:
                    raise ConfigurationError(
                        "VISION_CORE_ZONE_CONFIRMATION_FRAMES debe ser un entero positivo.",
                        context={"variable": "VISION_CORE_ZONE_CONFIRMATION_FRAMES"},
                    ) from error
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
            app = build_pipeline(
                video=source,
                detector=detection.detector,
                reid=reid.memory,
                door=door.analytics,
                embedder=reid.embedder,
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


def main() -> None:
    monitor_cli.main(
        build_state=build_monitor_state,
        build_runtime=build_monitor_runtime,
    )


if __name__ == "__main__":
    main()
