import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DTO_ROOTS = [
    ROOT / "src" / "vision_core" / "shared" / "application" / "dto",
    *[
        ROOT / "src" / "vision_core" / "features" / slice_name / "application" / "dto"
        for slice_name in ("detection", "door", "monitor", "reid", "video", "pipeline")
    ],
]
FORBIDDEN_ROOTS = {"numpy", "cv2", "torch", "torchvision", "ultralytics"}


def _is_forbidden(module):
    if module.split(".", 1)[0] in FORBIDDEN_ROOTS:
        return True
    if module.startswith("vision_core.domain") or module.startswith("vision_core.infrastructure"):
        return True
    return ".domain" in module or ".infrastructure" in module


def _import_modules(node):
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom):
        module = "." * node.level + (node.module or "")
        return [module] if module else []
    return []


def test_relative_imports_keep_their_level():
    tree = ast.parse("from ..domain import X\nfrom ...infrastructure.foo import Y\n")
    modules = [module for node in ast.walk(tree) for module in _import_modules(node)]
    assert modules == ["..domain", "...infrastructure.foo"]
    assert all(_is_forbidden(module) for module in modules)


def test_dto_modules_do_not_import_forbidden_packages():
    violations = []
    checked = 0
    for root in DTO_ROOTS:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            checked += 1
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                for module in _import_modules(node):
                    if _is_forbidden(module):
                        violations.append(f"{path.relative_to(ROOT)} -> {module}")
    assert checked >= 30
    assert not violations
