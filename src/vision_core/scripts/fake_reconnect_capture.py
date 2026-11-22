"""Captura falsa para medir el camino de reconexión RTSP sin red."""

from typing import Any


class FakeReconnectCapture:
    """Devuelve una secuencia programada de lecturas y se comporta como VideoCapture."""

    def __init__(self, frames: list[tuple[bool, Any]]) -> None:
        self._frames = list(frames)

    def open(self, *args: Any, **kwargs: Any) -> bool:
        return True

    def isOpened(self) -> bool:
        return True

    def set(self, *args: Any, **kwargs: Any) -> bool:
        return True

    def read(self) -> tuple[bool, Any]:
        if not self._frames:
            return False, None
        return self._frames.pop(0)

    def release(self) -> None:
        return None
