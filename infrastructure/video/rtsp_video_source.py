from typing import Optional
import cv2
import numpy as np

from domain.ports import VideoSource


class RtspVideoSource(VideoSource):
    """Ingesta desde Frigate/RTSP. Base funcional (VC-INIT)."""

    def __init__(self, rtsp_url: str) -> None:
        self._url = rtsp_url
        self._cap: Optional[cv2.VideoCapture] = None

    def open(self) -> None:
        self._cap = cv2.VideoCapture(self._url)
        if not self._cap.isOpened():
            raise RuntimeError(f"No se pudo abrir el stream: {self._url}")

    def read_frame(self) -> Optional[np.ndarray]:
        if self._cap is None:
            raise RuntimeError("Llama a open() antes de read_frame()")
        ok, frame = self._cap.read()
        return frame if ok else None

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
