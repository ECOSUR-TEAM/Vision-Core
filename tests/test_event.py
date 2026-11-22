import pytest

from vision_core.core.domain.event import Event


def test_invalid_event_name_rejected():
    with pytest.raises(ValueError):
        Event(event="ENTRÓ", person_id="abc")
