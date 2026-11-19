from collections.abc import Mapping
from typing import cast

from vision_core.features.monitor.application.dto.response.response_frame import ResponseFrame
from vision_core.features.monitor.application.dto.response.response_snapshot import ResponseSnapshot


def snapshot_to_response(snapshot: Mapping[str, object]) -> ResponseSnapshot:
    status = snapshot["status"]
    if not isinstance(status, str):
        raise TypeError("Monitor snapshot status must be a string")

    error = snapshot["error"]
    if error is not None and not isinstance(error, str):
        raise TypeError("Monitor snapshot error must be a string or None")

    demo_zones = snapshot["demo_zones"]
    if not isinstance(demo_zones, bool):
        raise TypeError("Monitor snapshot demo_zones must be a bool")

    frame = int(cast(int, snapshot["frame"]))
    updated_at = snapshot["updated_at"]
    if updated_at is not None:
        updated_at = float(cast(float, updated_at))
    age_seconds = snapshot["age_seconds"]
    if age_seconds is not None:
        age_seconds = float(cast(float, age_seconds))

    people = snapshot["people"]
    if not isinstance(people, (tuple, list)):
        raise TypeError("Monitor snapshot people must be a sequence")
    people = tuple(item for item in people if isinstance(item, dict))

    events = snapshot["events"]
    if not isinstance(events, (tuple, list)):
        raise TypeError("Monitor snapshot events must be a sequence")
    events = tuple(item for item in events if isinstance(item, dict))

    counts_data = snapshot["counts"]
    if not isinstance(counts_data, Mapping):
        raise TypeError("Monitor snapshot counts must be a mapping")
    counts = {str(key): int(value) for key, value in counts_data.items()}

    return ResponseSnapshot(
        status=status,
        error=error,
        demo_zones=demo_zones,
        frame=frame,
        updated_at=updated_at,
        age_seconds=age_seconds,
        people=people,
        events=events,
        counts=counts,
        processing_ms=float(cast(float, snapshot["processing_ms"])),
        fps=float(cast(float, snapshot["fps"])),
        dropped_frames=int(cast(int, snapshot["dropped_frames"])),
    )


def frame_to_response(jpeg: bytes | None, sequence: int) -> ResponseFrame:
    return ResponseFrame(jpeg=jpeg, sequence=sequence)
