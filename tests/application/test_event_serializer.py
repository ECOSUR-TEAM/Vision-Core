import json

import numpy as np

from application.event_serializer import event_to_dict, event_to_json
from domain.entities import Event, EventType


def test_event_to_dict_preserves_public_contract():
    event = Event(EventType.PERSON_ENTERED, "abc", timestamp=12.5,
                  metadata={"zone": "interior"})

    assert event_to_dict(event) == {
        "event": "PERSON_ENTERED",
        "person_id": "abc",
        "timestamp": 12.5,
        "metadata": {"zone": "interior"},
    }


def test_event_to_json_serializes_numpy_metadata():
    event = Event(
        EventType.FALSE_ALARM,
        "abc",
        metadata={"pos": (np.float32(1.5), 2), "vec": np.zeros(2)},
    )

    data = json.loads(event_to_json(event))

    assert data["metadata"] == {"pos": [1.5, 2], "vec": [0.0, 0.0]}
