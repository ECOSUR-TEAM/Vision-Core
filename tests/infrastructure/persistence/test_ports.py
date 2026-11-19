import ast
from pathlib import Path

from vision_core.domain.model.event import Event


def test_repository_ports_do_not_depend_on_sqlite():
    root = Path(__file__).resolve().parents[3] / "src/vision_core/domain/repositories"
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(not alias.name.startswith("sqlite3") for alias in node.names), path
            elif isinstance(node, ast.ImportFrom):
                assert "infrastructure" not in (node.module or ""), path


def test_events_have_stable_and_unique_ids():
    first = Event("PERSON_ENTERED", "p1", 1.0)
    second = Event("PERSON_ENTERED", "p1", 1.0)

    assert first.event_id != second.event_id
    assert isinstance(first.event_id, str) and first.event_id
