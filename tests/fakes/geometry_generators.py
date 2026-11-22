import json
import math
import random

from vision_core.core.domain.polygon import Polygon

SEED = 20240517
MAX_ZONE_POINTS = 100


class GeometryGenerators:
    """Seeded, reusable generators for geometry/zone fuzz tests."""

    def __init__(self, seed: int = SEED) -> None:
        self.seed = seed

    def points(self, count: int, x_range=(0.0, 640.0), y_range=(0.0, 480.0)) -> tuple[tuple[float, float], ...]:
        rng = random.Random(self.seed)
        return tuple((rng.uniform(*x_range), rng.uniform(*y_range)) for _ in range(count))

    def rectangle(self, x1: float, y1: float, x2: float, y2: float, name: str = "zona") -> Polygon:
        return Polygon(name, ((x1, y1), (x2, y1), (x2, y2), (x1, y2)))

    def rectangles(self, count: int) -> tuple[Polygon, ...]:
        rng = random.Random(self.seed)
        polygons = []
        for index in range(count):
            x1, x2 = sorted((rng.uniform(0, 300), rng.uniform(301, 640)))
            y1, y2 = sorted((rng.uniform(0, 200), rng.uniform(201, 480)))
            polygons.append(self.rectangle(x1, y1, x2, y2, name=f"rect-{index}"))
        return tuple(polygons)

    def perturbations(self, point: tuple[float, float], count: int, magnitude: float = 1e-6):
        rng = random.Random(self.seed)
        for _ in range(count):
            yield (
                point[0] + rng.uniform(-magnitude, magnitude),
                point[1] + rng.uniform(-magnitude, magnitude),
            )

    def trajectory(self, start: float, length: int, step: float) -> tuple[float, ...]:
        return tuple(start + index * step for index in range(length))

    def zone_document(self, exterior=None, interior=None, door=None, frame_size=(640, 480)) -> dict:
        return {
            "version": "1.0",
            "frame_size": list(frame_size),
            "door": list(door or ((200, 0), (240, 0), (240, 479), (200, 479))),
            "exterior": list(exterior or ((0, 0), (200, 0), (200, 479), (0, 479))),
            "interior": list(interior or ((240, 0), (639, 0), (639, 479), (240, 479))),
        }

    def truncated_json(self, document: dict, count: int) -> tuple[str, ...]:
        raw = json.dumps(document)
        step = max(1, len(raw) // max(count, 1))
        return tuple(raw[:index] for index in range(0, len(raw), step))

    def invalid_polygons(self) -> tuple[tuple[tuple[float, float], ...], ...]:
        return (
            (),
            ((1.0, 1.0),),
            ((1.0, 1.0), (2.0, 2.0)),
            ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 0.0)),
            ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0), (0.0, 0.0)),
            ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (math.nan, 2.0)),
            ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (math.inf, 2.0)),
            ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (-math.inf, 2.0)),
        )

    def oversized_zone_document(self) -> dict:
        points = tuple((float(x), float(x)) for x in range(MAX_ZONE_POINTS + 1))
        return self.zone_document(exterior=points)
