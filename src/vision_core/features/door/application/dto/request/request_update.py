from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RequestUpdate:
    person_id: str
    position: tuple[float, float]
