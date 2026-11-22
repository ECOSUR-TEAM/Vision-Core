import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FEATURES = PROJECT_ROOT / "src" / "vision_core" / "features"
CORE_DTO = PROJECT_ROOT / "src" / "vision_core" / "core" / "dto"


def _dto_files() -> list[Path]:
    files = []
    for feature in FEATURES.iterdir():
        if not feature.is_dir():
            continue
        dto_root = feature / "application" / "dto"
        for direction in ("request", "response"):
            files.extend(path for path in sorted((dto_root / direction).glob("*.py")) if path.name != "__init__.py")
    return files


def _core_dto_files() -> list[Path]:
    return [path for path in sorted(CORE_DTO.glob("*.py")) if path.name != "__init__.py"]


def _all_dto_files() -> list[Path]:
    shared_dto = PROJECT_ROOT / "src" / "vision_core" / "shared" / "application" / "dto"
    shared = [path for path in sorted(shared_dto.glob("*.py")) if path.name != "__init__.py"]
    return _dto_files() + shared + _core_dto_files()


def _contract_dto_files() -> list[Path]:
    return _dto_files() + _core_dto_files()


def _expected_class_name(path: Path) -> str:
    return "".join(part.capitalize() for part in path.stem.split("_"))


def _class_definition(path: Path) -> ast.ClassDef:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]
    assert len(classes) == 1, f"Expected exactly one DTO class in {path}: {[node.name for node in classes]}"
    return classes[0]


def _dataclass_keywords(node: ast.ClassDef) -> dict[str, ast.expr]:
    for decorator in node.decorator_list:
        if not isinstance(decorator, ast.Call):
            continue
        func = decorator.func
        if (isinstance(func, ast.Name) and func.id == "dataclass") or (
            isinstance(func, ast.Attribute) and func.attr == "dataclass"
        ):
            return {keyword.arg: keyword.value for keyword in decorator.keywords if keyword.arg is not None}
    return {}


def _is_true(value: ast.expr) -> bool:
    return isinstance(value, ast.Constant) and value.value is True


@pytest.mark.parametrize("path", _dto_files(), ids=lambda path: path.relative_to(PROJECT_ROOT).as_posix())
def test_dto_file_name_matches_class_name(path):
    assert _class_definition(path).name == _expected_class_name(path)


@pytest.mark.parametrize("path", _contract_dto_files(), ids=lambda path: path.relative_to(PROJECT_ROOT).as_posix())
def test_dtos_are_frozen_and_slotted(path):
    keywords = _dataclass_keywords(_class_definition(path))

    assert _is_true(keywords.get("frozen")), f"{path}: missing frozen=True"
    assert _is_true(keywords.get("slots")), f"{path}: missing slots=True"


@pytest.mark.parametrize("path", _contract_dto_files(), ids=lambda path: path.relative_to(PROJECT_ROOT).as_posix())
def test_dtos_have_no_business_logic(path):
    node = _class_definition(path)

    assert not [
        child for child in ast.walk(node) if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda))
    ]


@pytest.mark.parametrize("path", _all_dto_files(), ids=lambda path: path.relative_to(PROJECT_ROOT).as_posix())
def test_dto_fields_have_concrete_types(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    erased = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.AnnAssign):
            continue
        for child in ast.walk(node.annotation):
            if isinstance(child, ast.Name) and child.id in {"Any", "object"}:
                erased.append(child.id)
            elif isinstance(child, ast.Attribute) and child.attr in {"Any", "object"}:
                erased.append(child.attr)
    assert not erased, f"{path}: DTO fields must not use object/Any: {erased}"


def test_dtos_live_only_in_request_or_response_directories():
    unexpected = []
    for dto_root in FEATURES.glob("*/application/dto"):
        for path in dto_root.rglob("*.py"):
            if path.name == "__init__.py":
                continue
            if path.parent.name not in {"request", "response"}:
                unexpected.append(path.relative_to(PROJECT_ROOT))
    assert not unexpected, f"Unexpected DTO location: {unexpected}"
