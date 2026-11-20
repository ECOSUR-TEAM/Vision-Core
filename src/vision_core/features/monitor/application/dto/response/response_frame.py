from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResponseFrame:
    """Binary frame transport; ``jpeg`` is served as image/jpeg, never as JSON.

    ``dumps_json`` replaces the binary value with ``null``, so this DTO is not a
    JSON image response and must go through the image endpoint.
    """

    jpeg: bytes | None
    sequence: int
