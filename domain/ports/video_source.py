from abc import ABC, abstractmethod
from typing import Optional
import numpy as np


class VideoSource(ABC):
    """Contrato para cualquier origen de video (RTSP/Frigate, archivo, webcam)."""

    @abstractmethod
    def open(self) -> None:
        ...

    @abstractmethod
    def read_frame(self) -> Optional[np.ndarray]:
        """Devuelve el siguiente frame (BGR) o None si no hay más."""
        ...

    @abstractmethod
    def close(self) -> None:
        ...
