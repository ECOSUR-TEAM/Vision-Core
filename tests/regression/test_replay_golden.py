import difflib
import json

import pytest

from tests.regression.replay_runner import TIMING_TOLERANCE_SECONDS, ReplayRunner

FAST_SCENARIOS = [
    "enter_exterior_to_interior",
    "exit_interior_to_exterior",
    "false_alarm",
    "person_stopped",
]
EXTENDED_SCENARIOS = ["lighting_change"]


def _without_timestamps(events):
    return [{key: value for key, value in event.items() if key != "timestamp"} for event in events]


def _assert_timestamps_within_tolerance(actual, expected):
    assert len(actual) == len(expected)
    for index, (current, golden) in enumerate(zip(actual, expected)):
        assert abs(current["timestamp"] - golden["timestamp"]) <= TIMING_TOLERANCE_SECONDS, (
            f"event[{index}] timestamp {current['timestamp']} differs from golden {golden['timestamp']} "
            f"by more than {TIMING_TOLERANCE_SECONDS}s"
        )


def _check_scenario(name, regen_golden):
    runner = ReplayRunner(name)
    actual = runner.run()
    if regen_golden:
        runner.regenerate(actual)
    golden = json.loads(runner.golden_path().read_text(encoding="utf-8"))
    actual_text = json.dumps(_without_timestamps(actual), indent=2, sort_keys=True)
    golden_text = json.dumps(_without_timestamps(golden), indent=2, sort_keys=True)
    assert actual_text == golden_text, "event replay diff:\n" + "\n".join(
        difflib.unified_diff(
            golden_text.splitlines(),
            actual_text.splitlines(),
            fromfile=f"golden/{name}.json",
            tofile="actual",
            lineterm="",
        )
    )
    _assert_timestamps_within_tolerance(actual, golden)


@pytest.mark.parametrize("scenario", FAST_SCENARIOS)
def test_replay_matches_golden(scenario, regen_golden):
    _check_scenario(scenario, regen_golden)


@pytest.mark.replay_extended
@pytest.mark.parametrize("scenario", EXTENDED_SCENARIOS)
def test_replay_extended_matches_golden(scenario, regen_golden):
    _check_scenario(scenario, regen_golden)
