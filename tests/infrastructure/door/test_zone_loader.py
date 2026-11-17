import json
from pathlib import Path

import pytest

from infrastructure.door.polygon_door_analytics import PolygonDoorAnalytics
from infrastructure.door.zone_config import ZoneConfig
from infrastructure.door.zone_loader import load_zones


def test_load_zones_builds_configuration():
    zones = load_zones('config/zones.example.json')

    assert isinstance(zones, ZoneConfig)
    assert (zones.width, zones.height) == (640, 480)
    assert zones.door.name == 'door'
    assert zones.exterior.name == 'exterior'
    assert zones.interior.name == 'interior'


def test_shared_edge_prefers_interior():
    zones = load_zones('config/zones.example.json')
    analytics = PolygonDoorAnalytics(zones.exterior, zones.interior, zones.door, confirmation_frames=1)
    assert analytics._zone_for((320, 200)) == 'interior'
    assert analytics._point_in_polygon((320, 200), zones.door)


def test_configuration_bounds(tmp_path):
    data = json.loads(Path('config/zones.example.json').read_text())
    data['frame_size'] = [300, 480]
    path = tmp_path / 'zones.json'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='fuera'):
        load_zones(path)
