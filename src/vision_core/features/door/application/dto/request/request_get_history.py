from dataclasses import dataclass


@dataclass(frozen=True)
class RequestGetHistory:
    person_id: str
