import collections.abc
import dataclasses
import importlib
import json
import pathlib
import types
import typing

GOLDEN_PATH = pathlib.Path("tests/contracts/dto_snapshot.json")
_UNION_ORIGINS = (typing.Union, types.UnionType)
_SEQUENCE_ORIGINS = (list, collections.abc.Sequence, collections.abc.MutableSequence)
_SET_ORIGINS = (set, frozenset, collections.abc.Set, collections.abc.MutableSet)
_MAPPING_ORIGINS = (dict, collections.abc.Mapping, collections.abc.MutableMapping)


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
                    "type": _type_text(field.type),
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


def _origin_text(origin):
    if isinstance(origin, type):
        if origin.__module__ == "builtins":
            return origin.__name__
        return f"{origin.__module__}.{origin.__qualname__}"
    return str(origin)


def _arg_text(annotation):
    if annotation is Ellipsis:
        return "..."
    if isinstance(annotation, typing.ForwardRef):
        return repr(annotation.__forward_arg__)
    if isinstance(annotation, type):
        if annotation.__module__ == "builtins":
            return annotation.__name__
        return f"{annotation.__module__}.{annotation.__qualname__}"
    return _type_text(annotation)


def _type_text(annotation):
    if annotation is Ellipsis:
        return "..."
    if isinstance(annotation, typing.ForwardRef):
        return repr(annotation.__forward_arg__)
    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)
    if origin in _UNION_ORIGINS:
        return " | ".join("None" if arg is type(None) else _arg_text(arg) for arg in args)
    if origin is not None and args:
        return f"{_origin_text(origin)}[{', '.join(_arg_text(arg) for arg in args)}]"
    return str(annotation)


def _is_frame_like(annotation):
    return getattr(annotation, "__name__", "") == "FrameLike"


def sample_value(annotation, depth=0):
    if depth > 8:
        return None
    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)
    if origin in _UNION_ORIGINS:
        for arg in args:
            if arg is not type(None):
                return sample_value(arg, depth + 1)
        return None
    if origin is typing.Annotated:
        return sample_value(args[0], depth + 1)
    if origin is typing.Literal:
        return args[0]
    if origin is typing.ForwardRef or isinstance(annotation, typing.ForwardRef):
        return "forward-ref"
    if origin is tuple or annotation is tuple:
        if not args:
            return (1.0, 2.0)
        if len(args) == 2 and args[1] is Ellipsis:
            return (sample_value(args[0], depth + 1),)
        return tuple(sample_value(arg, depth + 1) for arg in args)
    if origin in _SEQUENCE_ORIGINS:
        return [sample_value(args[0], depth + 1)] if args else []
    if origin in _SET_ORIGINS:
        item = sample_value(args[0], depth + 1) if args else None
        return frozenset({item}) if origin in (frozenset, collections.abc.Set) else {item}
    if origin in _MAPPING_ORIGINS:
        value_type = args[1] if len(args) == 2 else str
        return {"key": sample_value(value_type, depth + 1)}
    if annotation is type(None):
        return None
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
    if _is_frame_like(annotation):
        return {"shape": (4, 4, 3), "ndim": 3}
    if isinstance(annotation, type) and dataclasses.is_dataclass(annotation):
        return build_from_external_dict(annotation, depth + 1)[0]
    return None


def _value_matches(value, annotation, depth=0):
    if depth > 8:
        return True
    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)
    if annotation is typing.Any:
        return True
    if origin in _UNION_ORIGINS:
        return any(_value_matches(value, arg, depth + 1) for arg in args)
    if origin is typing.Annotated:
        return _value_matches(value, args[0], depth + 1)
    if origin is typing.Literal:
        return value in args
    if origin is typing.ForwardRef or isinstance(annotation, typing.ForwardRef):
        return value is None or isinstance(value, (bool, int, float, str, list, tuple, dict))
    if annotation is type(None):
        return value is None
    if origin is tuple or annotation is tuple:
        if not isinstance(value, tuple):
            return False
        if not args:
            return True
        if len(args) == 2 and args[1] is Ellipsis:
            return all(_value_matches(item, args[0], depth + 1) for item in value)
        return len(value) == len(args) and all(
            _value_matches(item, item_type, depth + 1) for item, item_type in zip(value, args)
        )
    if origin in _SEQUENCE_ORIGINS:
        return isinstance(value, list) and all(_value_matches(item, args[0], depth + 1) for item in value)
    if origin in _SET_ORIGINS:
        return isinstance(value, (set, frozenset)) and all(_value_matches(item, args[0], depth + 1) for item in value)
    if origin in _MAPPING_ORIGINS:
        if not isinstance(value, dict):
            return False
        if not args:
            return True
        key_type, value_type = args[0], args[1]
        return all(
            _value_matches(key, key_type, depth + 1) and _value_matches(item, value_type, depth + 1)
            for key, item in value.items()
        )
    if _is_frame_like(annotation):
        return isinstance(value, dict) and "shape" in value and "ndim" in value
    if isinstance(annotation, type):
        if dataclasses.is_dataclass(annotation):
            return isinstance(value, annotation)
        if annotation is bool:
            return value.__class__ is bool
        if annotation is int:
            return value.__class__ is int
        if annotation is float:
            return value.__class__ is float
        if annotation is str:
            return isinstance(value, str)
        if annotation is bytes:
            return isinstance(value, bytes)
        return isinstance(value, annotation)
    return True


def build_from_external_dict(cls, depth=0):
    hints = typing.get_type_hints(cls)
    payload = {field.name: sample_value(hints[field.name], depth) for field in dataclasses.fields(cls)}
    for field in dataclasses.fields(cls):
        if not _value_matches(payload[field.name], hints[field.name]):
            raise AssertionError(f"{cls.__name__}.{field.name}: valor de muestra incompatible con {hints[field.name]}")
    return cls(**payload), payload
