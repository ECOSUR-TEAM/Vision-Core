"""Recursive JSON value used by DTO payload metadata."""

from typing import TypeAlias, Union

JSONValue: TypeAlias = Union[
    None,
    bool,
    int,
    float,
    str,
    tuple["JSONValue", ...],
    dict[str, "JSONValue"],
]
