from dataclasses import dataclass

from vision_core.shared.application.dto.frame_like import FrameLike


@dataclass(frozen=True, slots=True)
class RequestDetector:
    """Input frame for a detection operation.

    The raw frame is a structural ``FrameLike`` (a numpy array in production).
    DTOs cannot import numpy, so the use case calls ``validate_frame`` before
    handing the frame to the detector.
    """

    frame: FrameLike
