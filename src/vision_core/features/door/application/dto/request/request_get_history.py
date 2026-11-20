from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RequestGetHistory:
    person_id: str
