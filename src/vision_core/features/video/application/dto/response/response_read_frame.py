from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResponseReadFrame:
    frame_png: bytes | None
    width: int = 0
    height: int = 0
    format: str = "png"
