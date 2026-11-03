"""RTSP ingestion with bounded retries and FFmpeg timeouts."""
import logging
import math
import os
import time
from typing import Optional
from urllib.parse import urlsplit

import cv2
import numpy as np

from domain.ports import VideoSource

logger = logging.getLogger(__name__)


class RtspVideoSource(VideoSource):
    """Single-consumer source. Exhausted retries raise ConnectionError, not EOF."""

    def __init__(self, rtsp_url: str, *, open_timeout_ms: int = 5000,
                 read_timeout_ms: int = 5000, reconnect_attempts: int = 5,
                 reconnect_delay_seconds: float = 2.0) -> None:
        try:
            parsed = urlsplit(rtsp_url)
            valid = parsed.scheme in {"rtsp", "rtsps"} and parsed.hostname and parsed.port != 0
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("VISION_CORE_RTSP_URL debe ser una URL RTSP válida")
        if open_timeout_ms <= 0 or read_timeout_ms <= 0:
            raise ValueError("Los timeouts deben ser positivos")
        if reconnect_attempts < 0:
            raise ValueError("Los reintentos no pueden ser negativos")
        if not math.isfinite(reconnect_delay_seconds) or reconnect_delay_seconds < 0:
            raise ValueError("La espera debe ser finita y no negativa")
        self._url = rtsp_url
        self._open_timeout = open_timeout_ms
        self._read_timeout = read_timeout_ms
        self._attempts = reconnect_attempts
        self._delay = reconnect_delay_seconds
        self._cap: Optional[cv2.VideoCapture] = None

    @classmethod
    def from_env(cls) -> "RtspVideoSource":
        """Read process environment; a local .env must be exported by the caller."""
        url = os.environ.get("VISION_CORE_RTSP_URL", "").strip()
        if not url:
            raise ValueError("Configura VISION_CORE_RTSP_URL antes de iniciar")
        return cls(
            url,
            open_timeout_ms=int(os.getenv("VISION_CORE_OPEN_TIMEOUT_MS", "5000")),
            read_timeout_ms=int(os.getenv("VISION_CORE_READ_TIMEOUT_MS", "5000")),
            reconnect_attempts=int(os.getenv("VISION_CORE_RECONNECT_ATTEMPTS", "5")),
            reconnect_delay_seconds=float(os.getenv("VISION_CORE_RECONNECT_DELAY_SECONDS", "2")),
        )

    def _connect(self) -> bool:
        self.close()
        try:
            # Allocate first so even a failed open can be released.
            self._cap = cv2.VideoCapture()
            opened = self._cap.open(self._url, cv2.CAP_FFMPEG, [
                cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, self._open_timeout,
                cv2.CAP_PROP_READ_TIMEOUT_MSEC, self._read_timeout,
            ])
            if opened and self._cap.isOpened():
                return True
        except cv2.error:
            pass  # Native errors may contain credentials; do not log their text.
        except BaseException:
            self.close()
            raise
        self.close()
        return False

    def _wait(self, attempt: int) -> None:
        logger.warning("Stream no disponible; reintento %d/%d", attempt, self._attempts)
        time.sleep(self._delay)

    def open(self) -> None:
        if self._cap is not None and self._cap.isOpened():
            return
        for attempt in range(self._attempts + 1):
            if attempt:
                self._wait(attempt)
            if self._connect():
                return
        raise ConnectionError("No se pudo abrir RTSP; revisa red, URL y credenciales")

    def _read(self) -> Optional[np.ndarray]:
        try:
            ok, frame = self._cap.read()
            if ok and frame is not None and frame.size:
                return frame
        except cv2.error:
            pass
        return None

    def read_frame(self) -> Optional[np.ndarray]:
        if self._cap is None:
            raise RuntimeError("Llama a open() antes de read_frame()")
        frame = self._read()
        if frame is not None:
            return frame
        self.close()
        for attempt in range(1, self._attempts + 1):
            self._wait(attempt)
            if self._connect():
                frame = self._read()
                if frame is not None:
                    return frame
                self.close()
        raise ConnectionError("Stream RTSP interrumpido; se agotaron los reintentos")

    def close(self) -> None:
        cap, self._cap = self._cap, None
        if cap is not None:
            cap.release()
