import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC = PROJECT_ROOT / "src" / "vision_core"
FEATURES = SRC / "features"
FORBIDDEN_DTO_IMPORTS = {"numpy", "cv2", "torch", "torchvision", "ultralytics"}
ALLOWED_DTO_STDLIB_IMPORTS = {
    "__future__",
    "abc",
    "collections",
    "collections.abc",
    "dataclasses",
    "datetime",
    "decimal",
    "enum",
    "types",
    "typing",
    "uuid",
}
ALLOWED_DTO_STDLIB_ROOTS = {module.split(".", 1)[0] for module in ALLOWED_DTO_STDLIB_IMPORTS}


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return modules


def _import_records(path: Path) -> list[tuple[str, int]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    records = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            records.extend((alias.name, 0) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            records.append((node.module or "", node.level))
    return records


def _resolve_relative_import(path: Path, module: str, level: int) -> str:
    if level == 0:
        return module
    package = path.parent.relative_to(SRC).parts
    base = package[: len(package) - (level - 1)]
    parts = ("vision_core", *base)
    if module:
        parts = (*parts, module)
    return ".".join(parts)


def _python_files(root: Path):
    return root.rglob("*.py")


def _assert_no_imports(paths, predicate, message):
    violations = [(path.relative_to(SRC), module) for path in paths for module in _imports(path) if predicate(module)]
    assert not violations, f"{message}: {violations}"


def test_shared_does_not_import_features_or_infrastructure():
    _assert_no_imports(
        _python_files(SRC / "shared"),
        lambda module: module.startswith("vision_core.features") or module.startswith("vision_core.infrastructure"),
        "shared import boundary violated",
    )


def test_domain_does_not_import_application_or_infrastructure():
    if not FEATURES.exists():
        return
    paths = (path for feature in FEATURES.iterdir() if feature.is_dir() for path in _python_files(feature / "domain"))
    _assert_no_imports(
        paths,
        lambda module: ".application" in module or ".infrastructure" in module,
        "domain import boundary violated",
    )


def test_application_does_not_import_infrastructure():
    if not FEATURES.exists():
        return
    paths = (
        path for feature in FEATURES.iterdir() if feature.is_dir() for path in _python_files(feature / "application")
    )
    _assert_no_imports(
        paths,
        lambda module: ".infrastructure" in module,
        "application import boundary violated",
    )


def test_features_do_not_import_another_features_infrastructure():
    if not FEATURES.exists():
        return
    violations = []
    for feature in FEATURES.iterdir():
        if not feature.is_dir():
            continue
        prefix = f"vision_core.features.{feature.name}."
        for path in _python_files(feature):
            for module in _imports(path):
                if module.startswith("vision_core.features.") and ".infrastructure" in module:
                    if not module.startswith(prefix):
                        violations.append((path.relative_to(SRC), module))
    assert not violations, f"cross-feature infrastructure import violated: {violations}"


def test_dtos_do_not_import_domain_infrastructure_or_frameworks():
    violations = []
    for dto in FEATURES.glob("*/application/dto"):
        for path in _python_files(dto):
            for module in _imports(path):
                root = module.split(".", 1)[0]
                if ".domain" in module or ".infrastructure" in module or root in FORBIDDEN_DTO_IMPORTS:
                    violations.append((path.relative_to(SRC), module))
    assert not violations, f"DTO import boundary violated: {violations}"


def test_dtos_only_import_allowed_modules():
    violations = []
    for feature in FEATURES.iterdir():
        if not feature.is_dir():
            continue
        dto_root = feature / "application" / "dto"
        if not dto_root.exists():
            continue
        own_dto = f"vision_core.features.{feature.name}.application.dto"
        shared_dto = "vision_core.shared.application.dto"
        for path in _python_files(dto_root):
            for module, level in _import_records(path):
                resolved = _resolve_relative_import(path, module, level)
                allowed = (
                    resolved in ALLOWED_DTO_STDLIB_IMPORTS
                    or resolved.split(".", 1)[0] in ALLOWED_DTO_STDLIB_ROOTS
                    or resolved == own_dto
                    or resolved.startswith(f"{own_dto}.")
                    or resolved == shared_dto
                    or resolved.startswith(f"{shared_dto}.")
                )
                if not allowed:
                    violations.append((path.relative_to(SRC), resolved))
    assert not violations, f"DTO imports must use stdlib, own DTO package or shared DTO base: {violations}"


def test_only_composition_roots_import_multiple_feature_factories():
    factory_importers = []
    roots = [
        SRC,
        PROJECT_ROOT / "application",
        PROJECT_ROOT / "domain",
        PROJECT_ROOT / "infrastructure",
        PROJECT_ROOT / "scripts",
        PROJECT_ROOT / "tests",
        PROJECT_ROOT / "main.py",
    ]
    paths = (path for root in roots for path in _python_files(root))
    for path in paths:
        if path == PROJECT_ROOT / "main.py":
            continue
        modules = _imports(path)
        imported_factories = {
            module
            for module in modules
            if module.startswith("vision_core.features.") and module.endswith(".infrastructure.dependencies")
        }
        if len(imported_factories) > 1:
            factory_importers.append((path, sorted(imported_factories)))

    assert (
        not factory_importers
    ), f"Only the root main.py composition root may import feature factories: {factory_importers}"
