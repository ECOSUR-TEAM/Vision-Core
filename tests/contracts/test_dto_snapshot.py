import copy
import difflib
import json
import sys

import pytest

from tests.contracts.dto_contract_helpers import discover_snapshot, load_golden


def _text(value):
    return json.dumps(value, indent=2, sort_keys=True)


def _assert_snapshot_matches_golden():
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


def test_dto_snapshot_matches_golden():
    _assert_snapshot_matches_golden()


def _expect_mutation_to_fail(monkeypatch, mutated):
    monkeypatch.setattr(sys.modules[__name__], "discover_snapshot", lambda: mutated)
    with pytest.raises(AssertionError, match="DTO snapshot diff"):
        _assert_snapshot_matches_golden()


def test_renamed_field_breaks_snapshot_comparison(monkeypatch):
    mutated = copy.deepcopy(load_golden())
    mutated[0]["fields"][0]["name"] = "renamed_field"
    _expect_mutation_to_fail(monkeypatch, mutated)


def test_removed_field_breaks_snapshot_comparison(monkeypatch):
    mutated = copy.deepcopy(load_golden())
    mutated[0]["fields"].pop()
    _expect_mutation_to_fail(monkeypatch, mutated)


def test_changed_field_type_breaks_snapshot_comparison(monkeypatch):
    mutated = copy.deepcopy(load_golden())
    mutated[0]["fields"][0]["type"] = "str"
    _expect_mutation_to_fail(monkeypatch, mutated)


def test_added_optional_field_is_an_explicit_snapshot_change(monkeypatch):
    mutated = copy.deepcopy(load_golden())
    mutated[0]["fields"].append({"name": "nuevo", "type": "str | None", "default": None, "default_factory": False})
    _expect_mutation_to_fail(monkeypatch, mutated)
