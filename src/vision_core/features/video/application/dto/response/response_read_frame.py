from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResponseReadFrame:
    """Binary frame transport; ``frame_png`` is decoded by the video mapper.

    Binary fields are excluded from JSON by ``dumps_json``; this DTO is not a
    JSON response and must not be serialized with plain ``json.dumps``.
    """

    frame_png: bytes | None
    width: int = 0
    height: int = 0
    format: str = "png"
