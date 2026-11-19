"""Vision Core package."""

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


def _read_project_version() -> str:
    try:
        return version("vision-core")
    except PackageNotFoundError:
        pass

    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # pragma: no cover - Python 3.10 fallback

    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    with pyproject.open("rb") as source:
        return tomllib.load(source)["project"]["version"]


__version__ = _read_project_version()
