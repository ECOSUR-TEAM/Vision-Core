import pytest

from vision_core.shared.domain.event import Event
from vision_core.shared.domain.event_type import EventType


def test_invalid_event_name_rejected():
    with pytest.raises(ValueError):
        Event(event="ENTRÓ", person_id="abc")