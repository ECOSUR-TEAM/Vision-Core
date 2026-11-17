import pytest
from domain.model.polygon import Polygon
from infrastructure.door import polygon_door_analytics as module


@pytest.fixture
def door():
    return module.PolygonDoorAnalytics(
        Polygon('ext', ((0,0),(10,0),(10,10),(0,10))),
        Polygon('int', ((10,0),(20,0),(20,10),(10,10))), history_limit=12)


POINTS = {'exterior': (5,5), 'interior': (15,5), 'fuera': (30,5)}


def stable(door, person, zone):
    results = [door.update(person, POINTS[zone]) for _ in range(3)]
    assert results[:2] == [None, None]
    return results[-1]


@pytest.mark.parametrize('origin,target,name', [
    ('exterior','interior','PERSON_ENTERED'),
    ('interior','exterior','PERSON_EXITED'),
    ('exterior','fuera','FALSE_ALARM')])
def test_confirmed_events(door, monkeypatch, origin, target, name):
    monkeypatch.setattr(module.time, 'time', lambda: 1234.5)
    assert stable(door, 'alice', origin) is None
    event = stable(door, 'alice', target)
    assert event.event == name and event.person_id == 'alice'
    assert event.timestamp == 1234.5
    assert event.metadata['from_zone'] == origin
    assert event.metadata['to_zone'] == target
    assert door.get_history('alice')[-1].timestamp == event.timestamp
    for _ in range(10):
        assert door.update('alice', POINTS[target]) is None
    assert len(door.get_history('alice')) == 12


def test_border_noise_and_valid_return(door):
    stable(door, 'p', 'exterior')
    for _ in range(10):
        for point in [(10.01,5), (10,5), (9.99,5)]:
            assert door.update('p', point) is None
    assert stable(door, 'p', 'interior').event == 'PERSON_ENTERED'
    assert stable(door, 'p', 'exterior').event == 'PERSON_EXITED'
    assert stable(door, 'p', 'interior').event == 'PERSON_ENTERED'


def test_person_states_independent(door):
    stable(door, 'alice', 'exterior')
    stable(door, 'bob', 'interior')
    for _ in range(2):
        assert door.update('alice', POINTS['interior']) is None
        assert door.update('bob', POINTS['exterior']) is None
    assert door.update('alice', POINTS['interior']).person_id == 'alice'
    assert door.update('bob', POINTS['exterior']).event == 'PERSON_EXITED'
    assert door.get_history('nobody') == ()


def test_no_event_without_confirmed_origin(door):
    assert door.update('p', POINTS['exterior']) is None
    assert stable(door, 'p', 'interior') is None


def test_invalid_position_does_not_change_history(door):
    with pytest.raises(ValueError):
        door.update('p', (float('nan'), 1))
    assert door.get_history('p') == ()


@pytest.mark.parametrize('value', [0, -1, 1.5, True])
def test_invalid_confirmation_threshold(value):
    polygon = Polygon('p', ((0,0),(10,0),(10,10)))
    with pytest.raises(ValueError, match='confirmation_frames'):
        module.PolygonDoorAnalytics(polygon, polygon, confirmation_frames=value)
