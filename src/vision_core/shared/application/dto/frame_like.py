"""Structural type for raw video frames crossing the application boundary.

This is the documented exception to the "no heavy frameworks in DTOs" rule:
frames arrive as ``numpy.ndarray`` from the video adapter, but DTOs may not
import numpy. ``FrameLike`` describes only the structural contract used by the
application layer; dtype/shape validation belongs to ``video_mapper`` at the
boundary, before the frame reaches any use case.
"""

from typing import Any, Protocol


class FrameLike(Protocol):
    shape: tuple[int, ...]
    ndim: int

    def __getitem__(self, key: Any) -> Any: ...
