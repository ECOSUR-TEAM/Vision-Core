"""Structural type for raw video frames crossing the application boundary.

This is the documented exception to the "no heavy frameworks in DTOs" rule:
frames arrive as ``numpy.ndarray`` from the video adapter, but DTOs may not
import numpy. ``FrameLike`` describes only the structural contract used by the
application layer; dtype/shape validation belongs to ``validate_frame`` at the
use-case boundary (and to ``video_mapper`` when encoding/decoding).
"""

from typing import Any, Protocol


class FrameLike(Protocol):
    shape: tuple[int, ...]
    ndim: int

    def __getitem__(self, key: Any) -> Any: ...
