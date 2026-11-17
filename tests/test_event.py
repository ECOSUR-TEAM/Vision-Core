import pytest

from domain.model.event import Event
from domain.model.event_type import EventType


def test_invalid_event_name_rejected():
    with pytest.raises(ValueError):
        Event(event="ENTRÓ", person_id="abc")