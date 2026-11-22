import pytest

from tests.fakes.fake_door import FakeDoor
from vision_core.core.domain.event import Event
from vision_core.core.domain.polygon import Polygon
from vision_core.core.errors import ZoneConfigurationError, codes
from vision_core.features.door.domain.ports.door_analytics import DoorAnalytics
from vision_core.features.door.infrastructure.adapters.polygon_door_analytics import PolygonDoorAnalytics

EXTERIOR = Polygon("ext", ((0, 0), (10, 0), (10, 10), (0, 10)))
INTERIOR = Polygon("int", ((10, 0), (20, 0), (20, 10), (10, 10)))


def _analytics():
    return PolygonDoorAnalytics(EXTERIOR, INTERIOR, confirmation_frames=1)


def _assert_door_contract(analytics):
    assert isinstance(analytics, DoorAnalytics)
    for position in ((5, 5), (5, 5), (15, 5), (15, 5)):
        result = analytics.update("persona-1", position)
    assert result is None or isinstance(result, Event)
    assert isinstance(analytics.get_history("persona-1"), tuple)


def test_fake_door_honours_port_contract():
    _assert_door_contract(FakeDoor())


def test_real_door_honours_port_contract():
    _assert_door_contract(_analytics())


def test_real_door_reports_calibrated_transition_as_event():
    analytics = _analytics()
    assert analytics.update("persona-1", (5, 5)) is None
    event = analytics.update("persona-1", (15, 5))
    assert isinstance(event, Event)
    assert event.event in {"PERSON_ENTERED", "PERSON_EXITED"}


def test_real_door_rejects_invalid_polygon_with_stable_code():
    with pytest.raises(ZoneConfigurationError) as error:
        PolygonDoorAnalytics(Polygon("bad", ((0, 0), (1, 1))), INTERIOR)
    assert error.value.code == codes.ZONE_GEOMETRY_INVALID
