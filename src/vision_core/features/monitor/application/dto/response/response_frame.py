from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResponseFrame:
    jpeg: bytes | None
    sequence: int
