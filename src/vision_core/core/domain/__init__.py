"""Value objects y eventos transversales del kernel (ADR 0008)."""

from vision_core.core.domain.bbox import BBox
from vision_core.core.domain.event import Event
from vision_core.core.domain.event_type import EventType
from vision_core.core.domain.polygon import Polygon
from vision_core.core.domain.types import Embedding, Frame

__all__ = ["BBox", "Embedding", "Event", "EventType", "Frame", "Polygon"]
