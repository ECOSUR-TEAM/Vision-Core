from collections.abc import Mapping
from typing import cast

from vision_core.features.monitor.application.dto.response.response_frame import ResponseFrame
from vision_core.features.monitor.application.dto.response.response_snapshot import ResponseSnapshot


def snapshot_to_response(snapshot: Mapping[str, object]) -> ResponseSnapshot:
    return ResponseSnapshot(
        status=cast(str, snapshot["status"]),
        error=cast(str | None, snapshot["error"]),
        demo_zones=cast(bool, snapshot["demo_zones"]),
        frame=cast(int, snapshot["frame"]),
        updated_at=cast(float | None, snapshot["updated_at"]),
        age_seconds=cast(float | None, snapshot["age_seconds"]),
        people=tuple(cast(tuple[dict[str, object], ...], snapshot["people"])),
        events=tuple(cast(tuple[dict[str, object], ...], snapshot["events"])),
        counts=dict(cast(Mapping[str, int], snapshot["counts"])),
        processing_ms=cast(float, snapshot["processing_ms"]),
        fps=cast(float, snapshot["fps"]),
        dropped_frames=cast(int, snapshot["dropped_frames"]),
    )


def frame_to_response(jpeg: bytes | None, sequence: int) -> ResponseFrame:
    return ResponseFrame(jpeg=jpeg, sequence=sequence)
