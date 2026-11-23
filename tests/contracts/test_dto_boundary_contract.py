import importlib.util
import sys
from dataclasses import is_dataclass
from pathlib import Path
from typing import Any, get_args, get_origin, get_type_hints

ROOT = Path(__file__).resolve().parents[2]
DTO_ROOT = ROOT / "src" / "vision_core" / "features"
CORE_DTO_ROOT = ROOT / "src" / "vision_core" / "core" / "dto"
FORBIDDEN_ROOTS = {"numpy", "cv2", "torch", "torchvision", "ultralytics"}
LEGACY_DOMAIN_PREFIX = "vision_core" + ".domain"


def _dto_paths():
    feature_dtos = sorted(path for path in DTO_ROOT.glob("*/application/dto/*/*.py") if not path.name.startswith("__"))
    core_dtos = sorted(path for path in CORE_DTO_ROOT.glob("*.py") if not path.name.startswith("__"))
    return feature_dtos + core_dtos


def _load_module(path):
    name = "contract_dto_" + "_".join(path.with_suffix("").parts[-5:]).replace("-", "_")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _annotation_modules(annotation):
    origin = get_origin(annotation)
    if origin is not None:
        for argument in get_args(annotation):
            yield from _annotation_modules(argument)
        return
    module = getattr(annotation, "__module__", None)
    if module is not None:
        yield module


def _dynamic_annotations(annotation):
    if annotation is Any:
        yield "Any"
        return
    if annotation is object:
        yield "object"
        return
    origin = get_origin(annotation)
    if origin in (dict, list, set, tuple) and not get_args(annotation):
        yield origin.__name__
        return
    if origin is not None:
        for argument in get_args(annotation):
            yield from _dynamic_annotations(argument)


def test_dto_type_hints_contain_no_infrastructure_or_domain_types():
    violations = []
    dto_count = 0
    for path in _dto_paths():
        module = _load_module(path)
        for value in vars(module).values():
            if not isinstance(value, type) or not is_dataclass(value) or value.__module__ != module.__name__:
                continue
            dto_count += 1
            for field_name, annotation in get_type_hints(value).items():
                for module_name in _annotation_modules(annotation):
                    root = module_name.split(".", 1)[0]
                    forbidden = (
                        root in FORBIDDEN_ROOTS
                        or module_name == LEGACY_DOMAIN_PREFIX
                        or module_name.startswith(f"{LEGACY_DOMAIN_PREFIX}.")
                        or ".domain." in module_name
                        or ".infrastructure." in module_name
                    )
                    if forbidden:
                        violations.append(f"{path.name}:{value.__name__}.{field_name} -> {module_name}")

    assert dto_count >= 20
    assert not violations


def test_dto_type_hints_reject_dynamic_and_unparameterized_containers():
    violations = []
    for path in _dto_paths():
        module = _load_module(path)
        for value in vars(module).values():
            if not isinstance(value, type) or not is_dataclass(value) or value.__module__ != module.__name__:
                continue
            for field_name, annotation in get_type_hints(value).items():
                for label in _dynamic_annotations(annotation):
                    violations.append(f"{path.name}:{value.__name__}.{field_name} -> {label}")

    assert not violations
