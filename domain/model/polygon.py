from dataclasses import dataclass


@dataclass(frozen=True)
class Polygon:
    """Zona ROI (exterior/interior) como lista de puntos (x, y)."""
    name: str
    points: tuple[tuple[float, float], ...]
