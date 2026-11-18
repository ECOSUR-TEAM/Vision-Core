from dataclasses import dataclass


@dataclass(frozen=True)
class ResponseUpdate:
    event: dict[str, object] | None
