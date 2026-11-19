import importlib.util
import sys
from dataclasses import is_dataclass
from pathlib import Path
from typing import get_args, get_origin, get_type_hints

ROOT = Path(__file__).resolve().parents[2]
DTO_ROOT = ROOT / "src" / "vision_core" / "features"
FORBIDDEN_ROOTS = {"numpy", "cv2", "torch", "torchvision", "ultralytics"}


def _dto_paths():
    return sorted(path for path in DTO_ROOT.glob("*/application/dto/*/*.py") if not path.name.startswith("__"))


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
                        or module_name.startswith("vision_core.domain.")
                        or ".domain." in module_name
                        or ".infrastructure." in module_name
                    )
                    if forbidden:
                        violations.append(f"{path.name}:{value.__name__}.{field_name} -> {module_name}")

    assert dto_count >= 20
    assert not violations
