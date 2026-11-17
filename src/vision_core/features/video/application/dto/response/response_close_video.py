from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResponseCloseVideo:
    closed: bool
