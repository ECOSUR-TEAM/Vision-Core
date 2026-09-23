import pytest

from domain.entities import Polygon
from infrastructure.door.polygon_door_analytics import PolygonDoorAnalytics


def test_diferentes_poligonos_no_interfieren():
    p1_ext = Polygon(name="ext1", points=((0, 0), (10, 0), (10, 10), (0, 10)))
    p1_int = Polygon(name="int1", points=((10, 0), (20, 0), (20, 10), (10, 10)))
    p2_ext = Polygon(name="ext2", points=((0, 0), (50, 0), (50, 50), (0, 50)))
    p2_int = Polygon(name="int2", points=((50, 0), (100, 0), (100, 50), (50, 50)))

    door1 = PolygonDoorAnalytics(p1_ext, p1_int)
    door2 = PolygonDoorAnalytics(p2_ext, p2_int)

    assert door1._exterior != door2._exterior
    assert door1._interior != door2._interior


def test_init_validation_none():
    valid_poly = Polygon(name="ext", points=((0, 0), (10, 0), (10, 10)))
    with pytest.raises(ValueError, match="exterior_zone e interior_zone son obligatorios"):
        PolygonDoorAnalytics(None, valid_poly)
    with pytest.raises(ValueError, match="exterior_zone e interior_zone son obligatorios"):
        PolygonDoorAnalytics(valid_poly, None)


def test_init_validation_points_count():
    invalid_poly = Polygon(name="ext", points=((0, 0), (10, 0)))
    valid_poly = Polygon(name="int", points=((0, 0), (10, 0), (10, 10)))
    with pytest.raises(ValueError, match="un polígono necesita al menos 3 puntos"):
        PolygonDoorAnalytics(invalid_poly, valid_poly)
    with pytest.raises(ValueError, match="un polígono necesita al menos 3 puntos"):
        PolygonDoorAnalytics(valid_poly, invalid_poly)
