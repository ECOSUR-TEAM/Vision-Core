import dataclasses
import importlib
import json
import pathlib
import typing

GOLDEN_PATH = pathlib.Path("tests/contracts/dto_snapshot.json")


def dto_modules():
    root = pathlib.Path("src")
    for path in sorted(root.rglob("*/dto/**/*.py")):
        if path.name == "__init__.py":
            continue
        yield ".".join(path.relative_to(root).with_suffix("").parts)


def dto_classes():
    seen = set()
    for module_name in dto_modules():
        module = importlib.import_module(module_name)
        for name in sorted(dir(module)):
            obj = getattr(module, name)
            key = (module_name, name)
            if key in seen or not isinstance(obj, type) or not dataclasses.is_dataclass(obj):
                continue
            seen.add(key)
            yield module_name, name, obj


def discover_snapshot():
    dtos = []
    for module_name, name, obj in dto_classes():
        fields = []
        for field in dataclasses.fields(obj):
            fields.append(
                {
                    "name": field.name,
                    "type": str(field.type),
                    "default": repr(field.default) if field.default is not dataclasses.MISSING else None,
                    "default_factory": field.default_factory is not dataclasses.MISSING,
                }
            )
        dtos.append(
            {
                "module": module_name,
                "class": name,
                "frozen": obj.__dataclass_params__.frozen,
                "slots": hasattr(obj, "__slots__"),
                "fields": fields,
            }
        )
    return sorted(dtos, key=lambda dto: (dto["module"], dto["class"]))


def load_golden():
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


def sample_value(annotation, depth=0):
    if depth > 8:
        return None
    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)
    if origin is typing.Union or isinstance(origin, getattr(typing, "UnionType", type(None))):
        for arg in args:
            if arg is not type(None):
                return sample_value(arg, depth + 1)
        return None
    if origin is typing.ForwardRef or isinstance(annotation, typing.ForwardRef):
        return "forward-ref"
    if origin is tuple or annotation is tuple:
        if not args:
            return (1.0, 2.0)
        return tuple(sample_value(arg, depth + 1) for arg in args)
    if origin in (list, set):
        return [sample_value(arg, depth + 1) for arg in args] if args else []
    if origin is dict or str(origin) == "collections.abc.Mapping":
        value_type = args[1] if len(args) == 2 else str
        return {"key": sample_value(value_type, depth + 1)}
    if annotation is str:
        return "sample"
    if annotation is int:
        return 1
    if annotation is float:
        return 1.5
    if annotation is bool:
        return True
    if annotation is bytes:
        return b"sample"
    if isinstance(annotation, type) and dataclasses.is_dataclass(annotation):
        return build_from_external_dict(annotation, depth + 1)
    if getattr(annotation, "__name__", "") == "FrameLike":
        return {"shape": (4, 4, 3), "ndim": 3}
    return "sample"


def build_from_external_dict(cls, depth=0):
    payload = {
        field.name: sample_value(typing.get_type_hints(cls)[field.name], depth) for field in dataclasses.fields(cls)
    }
    return cls(**payload), payload
