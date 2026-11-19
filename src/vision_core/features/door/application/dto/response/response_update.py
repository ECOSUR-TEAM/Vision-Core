from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResponseUpdate:
    event: dict[str, object] | None
