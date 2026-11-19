from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RequestSnapshot:
    """Request for the current monitor snapshot."""
