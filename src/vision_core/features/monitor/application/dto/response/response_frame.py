from dataclasses import dataclass


@dataclass(frozen=True)
class ResponseFrame:
    jpeg: bytes | None
    sequence: int
