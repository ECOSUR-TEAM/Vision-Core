from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResponseGetHistory:
    observations: tuple[dict[str, object], ...]
