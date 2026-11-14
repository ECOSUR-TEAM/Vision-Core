import logging
import os

from application.event_serializer import event_to_json
from composition import (
    build_door_analytics,
    build_video_source,
    build_vision_core_app,
    build_zones,
)
from domain.entities import Event


def print_event(event: Event) -> None:
    print(event_to_json(event))


def main() -> None:
    logging.basicConfig(level=logging.INFO)
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
