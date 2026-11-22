import ast
from pathlib import Path

from vision_core.core.domain.event import Event


def test_repository_ports_do_not_depend_on_sqlite():
    root = Path(__file__).resolve().parents[3] / "src/vision_core/core/contracts/persistence"
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(not alias.name.startswith("sqlite3") for alias in node.names), path
            elif isinstance(node, ast.ImportFrom):
                assert "infrastructure" not in (node.module or ""), path


def test_events_do_not_generate_random_ids():
    first = Event("PERSON_ENTERED", "p1", 1.0)
    second = Event("PERSON_ENTERED", "p1", 1.0)

    assert first.event_id == second.event_id == ""
