from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResponseFrame:
    """Binary frame transport; ``jpeg`` is served as image/jpeg, never as JSON.

    ``dumps_json`` omits binary fields, so this DTO is never passed directly to
    a JSON endpoint without that serializer.
    """

    jpeg: bytes | None
    sequence: int
