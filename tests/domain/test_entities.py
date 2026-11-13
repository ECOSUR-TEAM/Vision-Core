import pytest

from domain.entities import Event, EventType


def test_invalid_event_name_rejected():
    with pytest.raises(ValueError):
        Event(event="ENTRÓ", person_id="abc")
