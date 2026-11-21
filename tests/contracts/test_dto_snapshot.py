import dataclasses
import importlib
import json
import pathlib


def test_dto_snapshot():
    root = pathlib.Path("src")
    mods = []
    for p in root.rglob("*/dto/**/*.py"):
        if p.name == "__init__.py":
            continue
        mods.append(".".join(p.relative_to(root).with_suffix("").parts))
    dtos = []
    for m in sorted(mods):
        module = importlib.import_module(m)
        for name in sorted(dir(module)):
            obj = getattr(module, name)
            if isinstance(obj, type) and dataclasses.is_dataclass(obj):
                fields = [
                    {
                        "name": f.name,
                        "type": str(f.type),
                        "default": repr(f.default) if f.default is not dataclasses.MISSING else None,
                        "default_factory": f.default_factory is not dataclasses.MISSING,
                    }
                    for f in dataclasses.fields(obj)
                ]
                dtos.append(
                    {
                        "module": m,
                        "class": name,
                        "frozen": obj.__dataclass_params__.frozen,
                        "slots": hasattr(obj, "__slots__"),
                        "fields": fields,
                    }
                )
    dtos.sort(key=lambda d: (d["module"], d["class"]))
    golden = json.loads(pathlib.Path("tests/contracts/dto_snapshot.json").read_text())
    assert dtos == golden
