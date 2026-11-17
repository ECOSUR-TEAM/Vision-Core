from vision_core.features.monitor.application.dto.response.response_frame import (
    ResponseFrame,
)
from vision_core.features.monitor.application.dto.response.response_snapshot import (
    ResponseSnapshot,
)


def snapshot_to_response(snapshot: dict[str, object]) -> ResponseSnapshot:
    return ResponseSnapshot(
        status=snapshot["status"],
        error=snapshot["error"],
        demo_zones=snapshot["demo_zones"],
        frame=snapshot["frame"],
        updated_at=snapshot["updated_at"],
        age_seconds=snapshot["age_seconds"],
        people=tuple(snapshot["people"]),
        events=tuple(snapshot["events"]),
        counts=dict(snapshot["counts"]),
        processing_ms=snapshot["processing_ms"],
        fps=snapshot["fps"],
        dropped_frames=snapshot["dropped_frames"],
    )


def frame_to_response(jpeg: bytes | None, sequence: int) -> ResponseFrame:
    return ResponseFrame(jpeg=jpeg, sequence=sequence)
