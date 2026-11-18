from abc import ABC, abstractmethod
from typing import Any


class VideoSource(ABC):
    """Contrato de cualquier origen de video (RTSP, archivo, webcam)."""

    @abstractmethod
    def open(self) -> None: ...

    @abstractmethod
    def read_frame(self) -> Any | None:
        """Devuelve un frame BGR o None al terminar."""
        ...

    @abstractmethod
    def close(self) -> None: ...
