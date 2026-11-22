import collections.abc
import dataclasses

import pytest

from tests.contracts.dto_contract_helpers import build_from_external_dict, dto_classes, sample_value
from vision_core.core.serialization.serialization import to_json_value


@pytest.mark.parametrize(
    ("annotation", "expected"),
    [
        (int | None, 1),
        (bytes | None, b"sample"),
        (tuple[int, ...], (1,)),
        (collections.abc.Mapping[str, int], {"key": 1}),
    ],
)
def test_sample_value_matches_common_annotations(annotation, expected):
    assert sample_value(annotation) == expected


@pytest.mark.parametrize("module_name,name,cls", list(dto_classes()))
def test_dto_can_be_built_from_external_dict_and_serialized(module_name, name, cls):
    instance, payload = build_from_external_dict(cls)
    assert isinstance(instance, cls)
    assert instance.__dataclass_params__.frozen
    assert hasattr(instance, "__slots__")

    serialized = to_json_value(instance)
    expected = to_json_value(payload)
    assert serialized == expected
    for field in dataclasses.fields(cls):
        value = getattr(instance, field.name)
        assert serialized[field.name] == to_json_value(value)


@pytest.mark.parametrize("module_name,name,cls", list(dto_classes()))
def test_dto_rejects_direct_mutation(module_name, name, cls):
    instance, _ = build_from_external_dict(cls)
    field = next(iter(dataclasses.fields(cls)), None)
    if field is None:
        pytest.skip("DTO sin campos mutables")
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(instance, field.name, "changed")
