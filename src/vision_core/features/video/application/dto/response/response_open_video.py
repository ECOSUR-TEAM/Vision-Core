from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResponseOpenVideo:
    opened: bool
