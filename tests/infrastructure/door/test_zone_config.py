import json
import pytest
from domain.entities import Polygon
from infrastructure.door.zone_config import load_zones, validate_polygon
from infrastructure.door.polygon_door_analytics import PolygonDoorAnalytics


@pytest.mark.parametrize('point,expected', [((5,5), True), ((-1,5), False),
    ((0,0), True), ((10,0), True), ((0,10), True), ((10,10), True),
    ((0,5), True), ((5,0), True), ((10,5), True), ((5,10), True),
    ((10.001,5), False)])
def test_boundaries(point, expected):
    pts = ((0,0), (10,0), (10,10), (0,10))
    for order in (pts, pts[::-1]):
        assert PolygonDoorAnalytics._point_in_polygon(point, Polygon('test', order)) == expected


def test_shared_edge_prefers_interior():
    zones = load_zones('config/zones.example.json')
    analytics = PolygonDoorAnalytics(zones.exterior, zones.interior, zones.door)
    assert analytics._zone_for((320, 200)) == 'interior'
    assert analytics._point_in_polygon((320, 200), zones.door)


@pytest.mark.parametrize('points', [((0,0),(1,1),(2,2)),
    ((0,0),(4,4),(0,4),(4,0)), ((0,0),(4,0),(4,4),(0,0)),
    ((0,0),(4,0),(float('nan'),4))])
def test_invalid_polygons(points):
    with pytest.raises(ValueError):
        validate_polygon(Polygon('bad', points))


def test_concave_polygon():
    polygon = Polygon('L', ((0,0),(10,0),(10,4),(4,4),(4,10),(0,10)))
    validate_polygon(polygon)
    assert PolygonDoorAnalytics._point_in_polygon((2,8), polygon)
    assert not PolygonDoorAnalytics._point_in_polygon((8,8), polygon)


def test_configuration_bounds(tmp_path):
    from pathlib import Path
    data = json.loads(Path('config/zones.example.json').read_text())
    data['frame_size'] = [300, 480]
    path = tmp_path / 'zones.json'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='fuera'):
        load_zones(path)
