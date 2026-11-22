import json
from dataclasses import asdict

from vision_core.core.dto import BBoxPayload, EventPayload, MonitorPersonPayload
from vision_core.core.serialization import dumps_json
from vision_core.features.monitor.application.mappers.monitor_mapper import frame_to_response, snapshot_to_response

_PERSON = MonitorPersonPayload(
    person_id="person-1",
    bbox=BBoxPayload(1.0, 2.0, 11.0, 22.0),
    confidence=0.9,
    track_id=7,
    zone="exterior",
    display_name="Persona 1",
)
_EVENT = EventPayload("PERSON_ENTERED", "person-1", 10.0, {"zone": "exterior"})


def _state():
    return {
        "status": "running",
        "error": None,
        "demo_zones": False,
        "frame": 4,
        "updated_at": 10.0,
        "age_seconds": 0.1,
        "people": (asdict(_PERSON),),
        "events": (asdict(_EVENT),),
        "counts": {"interior": 1},
        "processing_ms": 2.0,
        "fps": 15.0,
        "dropped_frames": 0,
        "persistence": {"enabled": True, "migrations": ["001"], "failures": 0},
    }


def test_snapshot_to_response_maps_every_field():
    state = _state()

    response = snapshot_to_response(state)

    assert json.loads(dumps_json(response)) == json.loads(dumps_json(state))
    assert response.people == (_PERSON,)
    assert response.events == (_EVENT,)


def test_snapshot_to_response_copies_mutable_collections():
    state = _state()
    response = snapshot_to_response(state)

    state["people"] += (asdict(_PERSON),)
    state["counts"]["interior"] = 5

    assert response.people == (_PERSON,)
    assert response.counts == {"interior": 1}


def test_frame_to_response_maps_payload_and_sequence():
    assert frame_to_response(b"jpeg", 4).jpeg == b"jpeg"
    assert frame_to_response(b"jpeg", 4).sequence == 4
    assert frame_to_response(None, 0).jpeg is None
