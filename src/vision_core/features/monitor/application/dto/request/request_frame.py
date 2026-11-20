from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RequestFrame:
    after: int | None = None
