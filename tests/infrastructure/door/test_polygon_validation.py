import pytest

from domain.entities import Polygon
from infrastructure.door.polygon_validation import validate_polygon, validate_vertices_in_frame


@pytest.mark.parametrize('points', [((0,0),(1,1),(2,2)),
    ((0,0),(4,4),(0,4),(4,0)), ((0,0),(4,0),(4,4),(0,0)),
    ((0,0),(4,0),(float('nan'),4))])
def test_invalid_polygons(points):
    with pytest.raises(ValueError):
        validate_polygon(Polygon('bad', points))


def test_concave_polygon_is_valid():
    validate_polygon(Polygon('L', ((0,0),(10,0),(10,4),(4,4),(4,10),(0,10))))


def test_valid_polygon_without_reading_a_file():
    validate_polygon(Polygon('valid', ((0,0),(10,0),(10,10),(0,10))))


def test_vertices_inside_frame():
    validate_vertices_in_frame(Polygon('ok', ((0,0),(9,0),(9,9))), 10, 10)


@pytest.mark.parametrize('point', [(-1,0), (10,0), (0,10)])
def test_vertices_outside_frame(point):
    polygon = Polygon('bad', ((0,0),(9,0),point))
    with pytest.raises(ValueError, match='fuera'):
        validate_vertices_in_frame(polygon, 10, 10)
