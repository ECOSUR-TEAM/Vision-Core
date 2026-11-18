from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RequestOpenVideo:
    """Apertura sin datos pesados ni dependencias de librerías externas."""
