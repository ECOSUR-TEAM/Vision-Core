import ast
import json
from pathlib import Path

import numpy as np
import pytest

from vision_core.core.domain.event import Event
from vision_core.core.domain.event_type import EventType
from vision_core.core.infrastructure.persistence.event_identity import event_id_for
from vision_core.core.serialization import event_serializer as legacy_event_serializer
from vision_core.core.serialization.events import (
    event_to_dto,
    event_to_json,
    event_to_json_dict,
    event_to_payload,
)
from vision_core.features.door.application.mappers.door_mapper import event_to_dto as door_event_to_dto

SRC = Path(__file__).resolve().parents[1] / "src" / "vision_core"
CANONICAL = SRC / "core" / "serialization" / "events.py"
IMPLEMENTATION_NAMES = {"event_to_payload", "event_to_json_dict", "event_to_json"}
REEXPORT_NAMES = IMPLEMENTATION_NAMES | {"event_to_dto"}


def _defined_functions(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.append(node.module or "")
    return modules


def test_event_serializers_are_exposed_from_core():
    event = Event(EventType.PERSON_ENTERED, "person-1", timestamp=12.5, metadata={"zone": "interior"})

    payload = event_to_json_dict(event)
    dto = event_to_dto(event)

    assert dto.event == "PERSON_ENTERED"
    assert dto.person_id == "person-1"
    assert dto.timestamp == 12.5
    assert dto.metadata == {"zone": "interior"}
    assert json.loads(event_to_json(event)) == payload
    assert legacy_event_serializer.event_to_payload is event_to_payload
    assert legacy_event_serializer.event_to_json_dict is event_to_json_dict


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


def test_jsonl_keeps_non_ascii_metadata_without_escaping():
    event = Event(EventType.PERSON_ENTERED, "persona-1", metadata={"zona": "interior céntrico"})

    line = json.dumps(event_to_json_dict(event), sort_keys=True, ensure_ascii=False)

    assert "interior céntrico" in line
    assert "\\u00e9" not in line


def test_event_to_json_keeps_validation_error_context():
    event = Event(EventType.PERSON_ENTERED, "person-1", metadata={"bad": float("nan")})

    with pytest.raises(ValueError, match="Cannot serialize event 'PERSON_ENTERED' as JSON"):
        event_to_json(event)


@pytest.mark.parametrize(
    "relative",
    [
        "features/pipeline/application/mappers/pipeline_mapper.py",
        "features/pipeline/application/mappers/__init__.py",
        "features/pipeline/application/__init__.py",
    ],
)
def test_pipeline_modules_do_not_export_event_serializers(relative: str):
    source = (SRC / relative).read_text(encoding="utf-8")

    assert not [name for name in REEXPORT_NAMES if name in source]


def test_event_serializer_implementations_are_unique():
    offenders = [
        str(path.relative_to(SRC))
        for path in SRC.rglob("*.py")
        if path != CANONICAL and IMPLEMENTATION_NAMES.intersection(_defined_functions(path))
    ]

    assert offenders == []


def test_door_mapper_delegates_to_core_serializer():
    event = Event(EventType.PERSON_ENTERED, "person-1", timestamp=12.5, metadata={"zone": "interior"})

    assert door_event_to_dto(event) == event_to_payload(event)
    assert door_event_to_dto(None) is None


def test_core_infrastructure_has_no_feature_imports():
    root = SRC / "core" / "infrastructure"
    files = sorted(root.rglob("*.py"))
    assert files

    offenders = [
        str(path.relative_to(SRC))
        for path in files
        if any(
            module == "vision_core.features" or module.startswith("vision_core.features.")
            for module in _imported_modules(path)
        )
    ]

    assert offenders == []
