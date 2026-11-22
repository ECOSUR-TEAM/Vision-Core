"""Ports compartidos entre vertical slices (ADR 0008)."""

from vision_core.core.contracts.persistence import (
    EventRepository,
    IdentityRepository,
    MetricsRepository,
    SessionRepository,
    TrackRepository,
    ZoneObservationRepository,
    ZoneRepository,
)
from vision_core.core.contracts.reid_memory import ReIDMemory

__all__ = [
    "EventRepository",
    "IdentityRepository",
    "MetricsRepository",
    "ReIDMemory",
    "SessionRepository",
    "TrackRepository",
    "ZoneObservationRepository",
    "ZoneRepository",
]
