from dataclasses import dataclass

from vision_core.shared.application.dto.frame_like import FrameLike


@dataclass(frozen=True, slots=True)
class RequestProcessFrame:
    """Frame to process; see ``FrameLike`` for the documented numpy exception."""

    frame: FrameLike
