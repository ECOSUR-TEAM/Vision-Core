import copy
import difflib
import json

from tests.contracts.dto_contract_helpers import discover_snapshot, load_golden


def _text(value):
    return json.dumps(value, indent=2, sort_keys=True)


def test_dto_snapshot_matches_golden():
    actual = discover_snapshot()
    golden = load_golden()
    assert _text(actual) == _text(golden), "DTO snapshot diff:\n" + "\n".join(
        difflib.unified_diff(
            _text(golden).splitlines(),
            _text(actual).splitlines(),
            fromfile="dto_snapshot.json (golden)",
            tofile="dto_snapshot.json (actual)",
            lineterm="",
        )
    )


def test_renamed_field_breaks_snapshot_comparison():
    golden = load_golden()
    mutated = copy.deepcopy(golden)
    mutated[0]["fields"][0]["name"] = "renamed_field"
    assert _text(mutated) != _text(golden)


def test_removed_field_breaks_snapshot_comparison():
    golden = load_golden()
    mutated = copy.deepcopy(golden)
    mutated[0]["fields"].pop()
    assert _text(mutated) != _text(golden)


def test_changed_field_type_breaks_snapshot_comparison():
    golden = load_golden()
    mutated = copy.deepcopy(golden)
    mutated[0]["fields"][0]["type"] = "str"
    assert _text(mutated) != _text(golden)


def test_added_optional_field_is_an_explicit_snapshot_change():
    golden = load_golden()
    mutated = copy.deepcopy(golden)
    mutated[0]["fields"].append({"name": "nuevo", "type": "str | None", "default": None, "default_factory": False})
    assert _text(mutated) != _text(golden)
