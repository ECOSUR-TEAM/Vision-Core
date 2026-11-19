from dataclasses import asdict

from vision_core.features.monitor.application.mappers.monitor_mapper import frame_to_response, snapshot_to_response


def _state():
    return {
        "status": "running",
        "error": None,
        "demo_zones": False,
        "frame": 4,
        "updated_at": 10.0,
        "age_seconds": 0.1,
        "people": ({"person_id": "person-1"},),
        "events": ({"event": "PERSON_ENTERED"},),
        "counts": {"interior": 1},
        "processing_ms": 2.0,
        "fps": 15.0,
        "dropped_frames": 0,
    }


def test_snapshot_to_response_maps_every_field():
    state = _state()

    response = snapshot_to_response(state)

    assert asdict(response) == state


def test_snapshot_to_response_copies_mutable_collections():
    state = _state()
    response = snapshot_to_response(state)

    state["people"] += ({"person_id": "person-2"},)
    state["counts"]["interior"] = 5

    assert response.people == ({"person_id": "person-1"},)
    assert response.counts == {"interior": 1}


def test_frame_to_response_maps_payload_and_sequence():
    assert frame_to_response(b"jpeg", 4).jpeg == b"jpeg"
    assert frame_to_response(b"jpeg", 4).sequence == 4
    assert frame_to_response(None, 0).jpeg is None
