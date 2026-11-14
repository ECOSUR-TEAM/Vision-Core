from abc import ABC, abstractmethod
from typing import Optional

from domain.types import Frame


class VideoSource(ABC):
    """Contrato para cualquier origen de video (RTSP/Frigate, archivo, webcam)."""

    @abstractmethod
    def open(self) -> None:
        ...

    @abstractmethod
    def read_frame(self) -> Optional[Frame]:
        """Devuelve BGR o None al terminar. Puede lanzar ConnectionError si falla la fuente."""
        ...

    @abstractmethod
    def close(self) -> None:
        ...
