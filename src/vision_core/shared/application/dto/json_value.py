"""Recursive JSON value used by DTO payload metadata."""

from collections.abc import Mapping
from typing import TypeAlias, Union

JSONValue: TypeAlias = Union[
    None,
    bool,
    int,
    float,
    str,
    tuple["JSONValue", ...],
    Mapping[str, "JSONValue"],
]
