import json
import math

import pytest

from tests.fakes.geometry_generators import SEED, GeometryGenerators
from vision_core.features.door.infrastructure.adapters.polygon_door_analytics import PolygonDoorAnalytics
from vision_core.features.door.infrastructure.config.zone_loader import load_zones
from vision_core.features.door.infrastructure.polygon_validation import validate_polygon
from vision_core.shared.domain.polygon import Polygon
from vision_core.shared.errors import ZoneConfigurationError

SAMPLE_COUNT = 200
GENERATORS = GeometryGenerators(seed=SEED)


def _write_zones(path, document):
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_generators_are_reproducible():
    first = GeometryGenerators(seed=SEED)
    second = GeometryGenerators(seed=SEED)
    assert first.points(SAMPLE_COUNT) == second.points(SAMPLE_COUNT)
    assert first.rectangles(10) == second.rectangles(10)
    assert first.truncated_json(first.zone_document(), 10) == second.truncated_json(second.zone_document(), 10)


def test_point_in_polygon_classifies_finite_points_for_rectangle():
    polygon = GENERATORS.rectangle(0, 0, 200, 200)
    points = GENERATORS.points(SAMPLE_COUNT) + ((1e9, -1e9), (-1e9, 1e9), (0.0, 0.0), (200.0, 200.0))
    for point in points:
        assert all(math.isfinite(value) for value in point)
        expected = 0.0 <= point[0] <= 200.0 and 0.0 <= point[1] <= 200.0
        assert PolygonDoorAnalytics._point_in_polygon(point, polygon) is expected


def test_point_inside_rectangle_survives_small_perturbations():
    polygon = GENERATORS.rectangle(0, 0, 200, 200)
    center = (100.0, 100.0)
    assert PolygonDoorAnalytics._point_in_polygon(center, polygon)
    for point in GENERATORS.perturbations(center, SAMPLE_COUNT):
        assert PolygonDoorAnalytics._point_in_polygon(point, polygon)


@pytest.mark.parametrize("points", GeometryGenerators(seed=SEED).invalid_polygons())
def test_degenerate_polygons_are_rejected(points):
    polygon = Polygon("inválido", points)
    with pytest.raises(ZoneConfigurationError):
        validate_polygon(polygon)


def test_confirmation_frames_delays_events_until_stable_transition():
    exterior = GENERATORS.rectangle(0, 0, 200, 480, "exterior")
    interior = GENERATORS.rectangle(240, 0, 640, 480, "interior")
    door = GENERATORS.rectangle(200, 0, 240, 480, "door")
    analytics = PolygonDoorAnalytics(exterior, interior, door, confirmation_frames=2)
    events = []
    positions = GENERATORS.trajectory(100, 2, 0) + GENERATORS.trajectory(300, 2, 0)
    for x in positions:
        event = analytics.update("person-1", (x, 240.0))
        if event is not None:
            events.append(event)
    assert [event.event for event in events] == ["PERSON_ENTERED"]


def test_confirmation_frames_prevents_event_on_unstable_transition():
    exterior = GENERATORS.rectangle(0, 0, 200, 480, "exterior")
    interior = GENERATORS.rectangle(240, 0, 640, 480, "interior")
    analytics = PolygonDoorAnalytics(exterior, interior, confirmation_frames=3)
    for x in (100, 300, 100, 300):
        assert analytics.update("person-1", (float(x), 240.0)) is None


@pytest.mark.parametrize("raw", GENERATORS.truncated_json(GENERATORS.zone_document(), 12))
def test_load_zones_rejects_truncated_json_with_typed_error(tmp_path, raw):
    path = tmp_path / "zones.json"
    path.write_text(raw, encoding="utf-8")
    with pytest.raises(ZoneConfigurationError, match="JSON malformado en"):
        load_zones(path)


def test_load_zones_rejects_nan_and_infinite_coordinates(tmp_path):
    invalid = GENERATORS.zone_document(exterior=((0, 0), (1, 0), (1, 1), (math.nan, 1)))
    with pytest.raises(ZoneConfigurationError, match="NaN e Infinity no están permitidos"):
        load_zones(_write_zones(tmp_path / "nan.json", invalid))
    invalid = GENERATORS.zone_document(exterior=((0, 0), (1, 0), (1, 1), (math.inf, 1)))
    with pytest.raises(ZoneConfigurationError, match="NaN e Infinity no están permitidos"):
        load_zones(_write_zones(tmp_path / "inf.json", invalid))


def test_load_zones_rejects_duplicate_keys_with_stable_message(tmp_path):
    path = tmp_path / "zones.json"
    raw = json.dumps(GENERATORS.zone_document())[:-1] + ', "version": "1.0"}'
    path.write_text(raw, encoding="utf-8")
    with pytest.raises(ZoneConfigurationError, match="clave duplicada no permitida: version"):
        load_zones(path)


def test_load_zones_enforces_dto_point_limit(tmp_path):
    with pytest.raises(ZoneConfigurationError, match="supera el máximo de 100 puntos por zona"):
        load_zones(_write_zones(tmp_path / "zones.json", GENERATORS.oversized_zone_document()))
