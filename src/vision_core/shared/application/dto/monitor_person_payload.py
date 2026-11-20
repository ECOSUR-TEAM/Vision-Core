"""Person row rendered in a monitor snapshot.

The renderer adds ``zone`` and ``display_name`` on top of a resolved track, so
these two fields are part of the monitor transport contract. Optional fields
remain explicit (``None``) rather than becoming untyped dict entries.
"""

from dataclasses import dataclass

from vision_core.shared.application.dto.bbox_payload import BBoxPayload


@dataclass(frozen=True, slots=True)
class MonitorPersonPayload:
    person_id: str
    bbox: BBoxPayload | None = None
    confidence: float | None = None
    track_id: int | None = None
    zone: str | None = None
    display_name: str | None = None
