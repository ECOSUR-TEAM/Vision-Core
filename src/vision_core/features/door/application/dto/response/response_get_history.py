from dataclasses import dataclass


@dataclass(frozen=True)
class ResponseGetHistory:
    observations: tuple[dict[str, object], ...]
