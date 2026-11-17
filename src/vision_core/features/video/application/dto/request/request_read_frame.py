from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RequestReadFrame:
    """Lectura sin transportar frames ni referencias a OpenCV."""
