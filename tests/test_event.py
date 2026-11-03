import json

import numpy as np
import pytest

from domain.entities import Event, EventType


def test_event_json_dumps_ok():
    e = Event(event="PERSON_ENTERED", person_id="abc")
    data = json.loads(json.dumps(e.to_dict()))
    assert {"event", "person_id", "timestamp"} <= set(data)
    assert data["event"] == "PERSON_ENTERED"
    assert isinstance(data["timestamp"], float)


def test_event_to_json_roundtrip():
    e = Event(EventType.PERSON_EXITED, "abc", metadata={"zone": "interior"})
    assert json.loads(e.to_json())["metadata"] == {"zone": "interior"}


def test_metadata_with_numpy_is_serializable():
    e = Event(
        EventType.FALSE_ALARM,
        "abc",
        metadata={"pos": (np.float32(1.5), 2), "vec": np.zeros(2)},
    )
    json.dumps(e.to_dict())


def test_invalid_event_name_rejected():
    with pytest.raises(ValueError):
        Event(event="ENTRÓ", person_id="abc")