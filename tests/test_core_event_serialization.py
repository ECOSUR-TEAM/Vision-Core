import json
from pathlib import Path

import numpy as np
import pytest

from vision_core.core.domain.event import Event
from vision_core.core.domain.event_type import EventType
from vision_core.core.infrastructure.persistence.event_identity import event_id_for
from vision_core.core.serialization.events import (
    event_to_dto,
    event_to_json,
    event_to_json_dict,
)

SRC = Path(__file__).resolve().parents[1] / "src" / "vision_core"


def test_event_serializers_are_exposed_from_core():
    event = Event(EventType.PERSON_ENTERED, "person-1", timestamp=12.5, metadata={"zone": "interior"})

    payload = event_to_json_dict(event)

    assert event_to_dto(event).event == "PERSON_ENTERED"
    assert json.loads(event_to_json(event)) == payload


def test_event_id_and_jsonl_match_pre_move_baseline():
    event = Event(
        EventType.PERSON_ENTERED,
        "person-1",
        timestamp=12.5,
        metadata={"zone": "interior", "vec": np.zeros(2)},
    )

    line = json.dumps(
        {"kind": "event", "frame": 7, **event_to_json_dict(event)},
        sort_keys=True,
        ensure_ascii=False,
    )

    assert event_id_for(event) == "97973da2c491559b373cd2e7b181bda06348a3ab23602d8aa320269155725bc8"
    assert line == (
        '{"event": "PERSON_ENTERED", "frame": 7, "kind": "event", '
        '"metadata": {"vec": [0.0, 0.0], "zone": "interior"}, '
        '"person_id": "person-1", "schema_version": "1.0.0", "timestamp": 12.5}'
    )


def test_event_to_json_keeps_validation_error_context():
    event = Event(EventType.PERSON_ENTERED, "person-1", metadata={"bad": float("nan")})

    with pytest.raises(ValueError, match="Cannot serialize event 'PERSON_ENTERED' as JSON"):
        event_to_json(event)


def test_pipeline_mapper_has_no_event_serializers():
    source = (SRC / "features/pipeline/application/mappers/pipeline_mapper.py").read_text(encoding="utf-8")

    assert "event_to_dto" not in source
    assert "event_to_json" not in source


def test_core_persistence_has_no_feature_imports():
    root = SRC / "core" / "infrastructure" / "persistence"
    offenders = [
        str(path.relative_to(SRC))
        for path in root.rglob("*.py")
        if "vision_core.features" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []
