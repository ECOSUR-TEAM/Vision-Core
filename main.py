import logging
import os
import sys

from composition import (
    build_door_analytics,
    build_video_source,
    build_vision_core_app,
    build_zones,
)
from vision_core.application.event_serializer import event_to_json
from vision_core.domain.model.event import Event

MONITOR_FLAGS = frozenset(
    {'--host', '--port', '--zones', '--demo-zones', '--uncalibrated'}
)


def print_event(event: Event) -> None:
    print(event_to_json(event))


def run_monitor() -> None:
    from vision_core.infrastructure.monitor.__main__ import main as monitor_main

    monitor_main()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    if os.getenv('VISION_CORE_ENTRYPOINT') == 'monitor' or MONITOR_FLAGS.intersection(sys.argv[1:]):
        run_monitor()
        return
    zones = build_zones(os.environ["VISION_CORE_ZONES_FILE"])

    app = build_vision_core_app(
        video_source=build_video_source(),
        door_analytics=build_door_analytics(zones),
        on_event=print_event,
        expected_frame_size=(zones.width, zones.height),
    )
    app.run()


if __name__ == "__main__":
    main()
