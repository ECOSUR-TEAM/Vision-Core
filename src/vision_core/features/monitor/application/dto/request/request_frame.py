from dataclasses import dataclass


@dataclass(frozen=True)
class RequestFrame:
    after: int | None = None
