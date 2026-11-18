import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ROOTS = ["domain", "application", "infrastructure", "scripts", "tests", "main.py"]


def _python_files(root: str):
    path = PROJECT_ROOT / root
    if path.is_file():
        return [path] if path.suffix == ".py" else []
    return [candidate for candidate in path.rglob("*.py") if "__pycache__" not in candidate.parts]


def _top_level_classes(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [node.name for node in tree.body if isinstance(node, ast.ClassDef)]


def test_one_class_per_file():
    violations = []
    for root in ROOTS:
        for path in _python_files(root):
            classes = _top_level_classes(path)
            if len(classes) > 1:
                relative = path.relative_to(PROJECT_ROOT)
                violations.append(f"{relative}: {classes}")

    assert not violations, "Archivos con más de una clase de nivel superior:\n" + "\n".join(violations)
