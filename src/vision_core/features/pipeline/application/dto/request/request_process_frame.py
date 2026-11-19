from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RequestProcessFrame:
    frame: object
