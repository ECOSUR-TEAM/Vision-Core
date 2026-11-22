"""Serializable bounding box payload shared by detection and pipeline."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BBoxPayload:
    x1: float
    y1: float
    x2: float
    y2: float
