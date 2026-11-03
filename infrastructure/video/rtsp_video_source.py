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
from .frame_validation import validate_frame

logger = logging.getLogger(__name__)


class RtspVideoSource(VideoSource):
    """FFmpeg decode to BGR uint8 with bounded reconnection attempts."""

    def __init__(self, rtsp_url: str, *, attempts=5, delay=2.0, timeout_ms=5000):
        if urlsplit(rtsp_url).scheme not in ('rtsp', 'rtsps') or not urlsplit(rtsp_url).hostname:
            raise ValueError('Se requiere una URL RTSP válida')
        if attempts < 0 or not np.isfinite(delay) or delay < 0 or timeout_ms <= 0:
            raise ValueError('Parámetros de reconexión inválidos')
        self._url = rtsp_url
        self._attempts, self._delay, self._timeout = attempts, delay, timeout_ms
        self._cap = None
        self.reconnections = 0

    @classmethod
    def from_env(cls):
        return cls(os.environ['VISION_CORE_RTSP_URL'],
                   attempts=int(os.getenv('VISION_CORE_RECONNECT_ATTEMPTS', '5')),
                   delay=float(os.getenv('VISION_CORE_RECONNECT_DELAY_SECONDS', '2')),
                   timeout_ms=int(os.getenv('VISION_CORE_TIMEOUT_MS', '5000')))

    def _connect(self):
        self.close()
        self._cap = cv2.VideoCapture()
        try:
            if self._cap.open(self._url, cv2.CAP_FFMPEG, [
                cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, self._timeout,
                cv2.CAP_PROP_READ_TIMEOUT_MSEC, self._timeout,
            ]) and self._cap.isOpened():
                if not self._cap.set(cv2.CAP_PROP_CONVERT_RGB, 1):
                    raise RuntimeError('El backend no permite asegurar salida BGR')
                return True
        except cv2.error:
            pass

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

    def open(self):
        if self._cap is not None and self._cap.isOpened():
            return
        for attempt in range(self._attempts + 1):
            if attempt:
                time.sleep(self._delay)
            if self._connect():
                return
        raise ConnectionError('No se pudo abrir RTSP')

    def _read(self):
        try:
            ok, frame = self._cap.read()
        except cv2.error:
            return None
        if not ok or frame is None or frame.size == 0:
            return None
        validate_frame(frame)
        return frame

    def read_frame(self) -> Optional[np.ndarray]:
        if self._cap is None:
            raise RuntimeError('Llama a open() antes de read_frame()')
        frame = self._read()
        if frame is not None:
            return frame
        self.close()
        for _ in range(self._attempts):
            time.sleep(self._delay)
            if self._connect():
                frame = self._read()
                if frame is not None:
                    self.reconnections += 1
                    return frame
                self.close()
        raise ConnectionError('Se agotaron los reintentos del stream')

    def close(self):
        cap, self._cap = self._cap, None
        if cap is not None:
            cap.release()
