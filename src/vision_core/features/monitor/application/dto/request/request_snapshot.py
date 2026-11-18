from dataclasses import dataclass


@dataclass(frozen=True)
class RequestSnapshot:
    """Request for the current monitor snapshot."""
