import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC = PROJECT_ROOT / "src" / "vision_core"
FEATURES = SRC / "features"
CORE = SRC / "core"
CORE_DTO_ROOT = CORE / "dto"
CORE_DTO = "vision_core.core.dto"
CORE_SERIALIZATION = "vision_core.core.serialization"
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
PACKAGE_NAME = "vision_core"
LEGACY_PACKAGE_NAMES = ("application", "domain", "infrastructure", "settings", "shared", "model_registry")
LEGACY_IMPORT_PREFIXES = tuple(f"{PACKAGE_NAME}.{name}" for name in LEGACY_PACKAGE_NAMES)
ALLOWED_TOP_LEVEL_DIRS = {"__pycache__", "core", "features", "scripts"}
ALLOWED_TOP_LEVEL_FILES = {"__init__.py"}


def _is_legacy_import(module: str) -> bool:
    return any(module == prefix or module.startswith(f"{prefix}.") for prefix in LEGACY_IMPORT_PREFIXES)


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
    try:
        package = path.parent.relative_to(SRC).parts
    except ValueError:
        return f"{'.' * level}{module}"
    if level - 1 > len(package):
        return f"{'.' * level}{module}"
    base = package[: len(package) - (level - 1)]
    parts = ("vision_core", *base)
    if module:
        parts = (*parts, module)
    return ".".join(parts)


def _imports(path: Path) -> list[str]:
    return [_resolve_relative_import(path, module, level) for module, level in _import_records(path)]


def _python_files(root: Path):
    return root.rglob("*.py")


def _assert_no_imports(paths, predicate, message):
    violations = [(path.relative_to(SRC), module) for path in paths for module in _imports(path) if predicate(module)]
    assert not violations, f"{message}: {violations}"


def test_core_does_not_import_features_or_scripts():
    _assert_no_imports(
        _python_files(CORE),
        lambda module: module.startswith("vision_core.features") or module.startswith("vision_core.scripts"),
        "core import boundary violated",
    )


def test_scripts_are_not_imported_by_features_or_core():
    paths = (*_python_files(FEATURES), *_python_files(CORE))
    _assert_no_imports(
        paths,
        lambda module: module.startswith("vision_core.scripts"),
        "scripts import boundary violated",
    )


def test_core_layout_is_present():
    expected = [
        "__init__.py",
        "config/__init__.py",
        "contracts/__init__.py",
        "domain/__init__.py",
        "dto/__init__.py",
        "errors/__init__.py",
        "inference/__init__.py",
        "infrastructure/__init__.py",
        "model_registry/__init__.py",
        "serialization/__init__.py",
        "telemetry/__init__.py",
        "validation/__init__.py",
    ]
    missing = [part for part in expected if not (CORE / part).is_file()]
    assert not missing, f"core layout incomplete: {missing}"


@pytest.mark.parametrize(
    "module",
    [
        "vision_core.core.contracts",
        "vision_core.core.domain",
        "vision_core.core.dto",
        "vision_core.core.errors",
        "vision_core.core.errors.codes",
        "vision_core.core.model_registry",
        "vision_core.core.serialization",
        "vision_core.core.telemetry",
        "vision_core.core.validation",
    ],
)
def test_core_subpackages_are_importable(module):
    __import__(module)


def test_src_vision_core_top_level_entries_are_allowed():
    entries = {path.name: path for path in SRC.iterdir()}
    directories = {name for name, path in entries.items() if path.is_dir()}
    files = {name for name, path in entries.items() if path.is_file()}
    assert directories <= ALLOWED_TOP_LEVEL_DIRS, directories - ALLOWED_TOP_LEVEL_DIRS
    assert files <= ALLOWED_TOP_LEVEL_FILES, files - ALLOWED_TOP_LEVEL_FILES
    assert {"core", "features", "scripts"} <= directories


@pytest.mark.parametrize("name", LEGACY_PACKAGE_NAMES)
def test_legacy_top_level_packages_are_absent(name):
    assert not (SRC / name).exists(), name


@pytest.mark.parametrize("name", LEGACY_PACKAGE_NAMES)
def test_no_legacy_package_imports_remain(name):
    prefix = f"{PACKAGE_NAME}.{name}"
    roots = (SRC, PROJECT_ROOT / "tests", PROJECT_ROOT / "main.py", PROJECT_ROOT / "scripts")
    violations = []
    for root in roots:
        paths = (root,) if root.is_file() else _python_files(root)
        for path in paths:
            for module in _imports(path):
                if module == prefix or module.startswith(f"{prefix}."):
                    violations.append((path.as_posix(), module))
    assert not violations, f"legacy import boundary violated for {name}: {violations}"


def test_legacy_import_rule_detects_every_forbidden_prefix():
    for name in LEGACY_PACKAGE_NAMES:
        assert _is_legacy_import(f"{PACKAGE_NAME}.{name}")
        assert _is_legacy_import(f"{PACKAGE_NAME}.{name}.child")
    assert not _is_legacy_import(f"{PACKAGE_NAME}.core.domain")


def test_core_rule_detects_forbidden_imports(tmp_path, monkeypatch):
    core = tmp_path / "core"
    core.mkdir(parents=True)
    (core / "bad.py").write_text(
        "from vision_core.features.door.application.use_cases import UpdateZone\n", encoding="utf-8"
    )
    monkeypatch.setitem(globals(), "SRC", tmp_path)
    monkeypatch.setitem(globals(), "CORE", core)

    with pytest.raises(AssertionError, match="core import boundary violated"):
        test_core_does_not_import_features_or_scripts()


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
    dto_roots = (*FEATURES.glob("*/application/dto"), CORE_DTO_ROOT)
    for dto_root in dto_roots:
        for path in _python_files(dto_root):
            for module in _imports(path):
                root = module.split(".", 1)[0]
                if ".domain" in module or ".infrastructure" in module or root in FORBIDDEN_DTO_IMPORTS:
                    violations.append((path.relative_to(SRC), module))
    assert not violations, f"DTO import boundary violated: {violations}"


def test_dtos_only_import_allowed_modules():
    violations = []
    dto_roots = [
        (feature / "application" / "dto", f"vision_core.features.{feature.name}.application.dto")
        for feature in FEATURES.iterdir()
        if feature.is_dir()
    ]
    dto_roots.append((CORE_DTO_ROOT, CORE_DTO))
    for dto_root, own_dto in dto_roots:
        if not dto_root.exists():
            continue
        for path in _python_files(dto_root):
            for module, level in _import_records(path):
                resolved = _resolve_relative_import(path, module, level)
                core_allowed = (
                    resolved == CORE_DTO
                    or resolved.startswith(f"{CORE_DTO}.")
                    or resolved == CORE_SERIALIZATION
                    or resolved.startswith(f"{CORE_SERIALIZATION}.")
                )
                allowed = (
                    resolved in ALLOWED_DTO_STDLIB_IMPORTS
                    or resolved.split(".", 1)[0] in ALLOWED_DTO_STDLIB_ROOTS
                    or resolved == own_dto
                    or resolved.startswith(f"{own_dto}.")
                    or core_allowed
                )
                if not allowed:
                    violations.append((path.relative_to(SRC), resolved))
    assert not violations, f"DTO imports must use stdlib, own DTO package or core DTO/serialization base: {violations}"


def test_only_composition_roots_import_multiple_feature_factories():
    factory_importers = []
    roots = [
        SRC,
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

    message = f"Only the root main.py composition root may import feature factories: {factory_importers}"
    assert not factory_importers, message


def test_imports_resolve_relative_modules():
    path = FEATURES / "detection" / "domain" / "sample.py"

    assert _resolve_relative_import(path, "application.use_cases", 2) == (
        "vision_core.features.detection.application.use_cases"
    )
    assert _resolve_relative_import(path, "", 1) == "vision_core.features.detection.domain"


def test_domain_rule_detects_relative_imports(tmp_path, monkeypatch):
    domain = tmp_path / "features" / "detection" / "domain"
    domain.mkdir(parents=True)
    (domain / "bad.py").write_text("from ..application.use_cases import Foo\n", encoding="utf-8")
    monkeypatch.setitem(globals(), "SRC", tmp_path)
    monkeypatch.setitem(globals(), "FEATURES", tmp_path / "features")

    with pytest.raises(AssertionError, match="domain import boundary violated"):
        test_domain_does_not_import_application_or_infrastructure()


def test_cross_feature_rule_detects_relative_imports(tmp_path, monkeypatch):
    domain = tmp_path / "features" / "door" / "domain"
    domain.mkdir(parents=True)
    (domain / "bad.py").write_text(
        "from ...pipeline.infrastructure.dependencies import build_pipeline\n", encoding="utf-8"
    )
    monkeypatch.setitem(globals(), "SRC", tmp_path)
    monkeypatch.setitem(globals(), "FEATURES", tmp_path / "features")

    with pytest.raises(AssertionError, match="cross-feature infrastructure import violated"):
        test_features_do_not_import_another_features_infrastructure()
