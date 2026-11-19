"""RTSP ingestion with bounded retries and FFmpeg timeouts."""

import logging
import math
import os
import time
from urllib.parse import urlsplit

import cv2
import numpy as np

from vision_core.shared.errors import (
    ConfigurationError,
    VideoSourceError,
    VideoSourceStateError,
    VisionCoreError,
)

from ...domain.ports.video_source import VideoSource
from ..frame_validation import validate_frame

logger = logging.getLogger(__name__)


def _env_int(name: str, default: str) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError) as error:
        raise ConfigurationError(
            "Los parámetros numéricos de RTSP no son válidos.",
            context={"variable": name},
        ) from error


def _env_float(name: str, default: str) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError) as error:
        raise ConfigurationError(
            "Los parámetros numéricos de RTSP no son válidos.",
            context={"variable": name},
        ) from error


class RtspVideoSource(VideoSource):
    """FFmpeg decode to BGR uint8 with bounded reconnection attempts."""

    """Single-consumer source. Exhausted retries raise VideoSourceError, not EOF."""

    def __init__(
        self,
        rtsp_url: str,
        *,
        open_timeout_ms: int = 5000,
        read_timeout_ms: int = 5000,
        reconnect_attempts: int = 5,
        reconnect_delay_seconds: float = 2.0,
        decoder_threads: int = 1,
    ) -> None:
        try:
            parsed = urlsplit(rtsp_url)
            valid = parsed.scheme in {"rtsp", "rtsps"} and parsed.hostname and parsed.port != 0
        except ValueError:
            valid = False
        if not valid:
            raise ConfigurationError(
                "VISION_CORE_RTSP_URL debe ser una URL RTSP válida",
                context={"variable": "VISION_CORE_RTSP_URL"},
            )
        if open_timeout_ms <= 0 or read_timeout_ms <= 0:
            raise ConfigurationError("Los timeouts deben ser positivos")
        if reconnect_attempts < 0:
            raise ConfigurationError("Los reintentos no pueden ser negativos")
        if not isinstance(decoder_threads, int) or isinstance(decoder_threads, bool) or decoder_threads < 0:
            raise ConfigurationError("Los hilos de decodificación deben ser un entero no negativo")
        if not math.isfinite(reconnect_delay_seconds) or reconnect_delay_seconds < 0:
            raise ConfigurationError("La espera debe ser finita y no negativa")
        self._url = rtsp_url
        self._open_timeout = open_timeout_ms
        self._read_timeout = read_timeout_ms
        self._attempts = reconnect_attempts
        self._delay = reconnect_delay_seconds
        self._decoder_threads = decoder_threads
        self._cap: cv2.VideoCapture | None = None
        self.reconnections = 0

    @classmethod
    def from_env(cls) -> "RtspVideoSource":
        """Read process environment; a local .env must be exported by the caller."""
        url = os.environ.get("VISION_CORE_RTSP_URL", "").strip()
        if not url:
            raise ConfigurationError(
                "Configura VISION_CORE_RTSP_URL antes de iniciar",
                context={"variable": "VISION_CORE_RTSP_URL"},
            )
        return cls(
            url,
            open_timeout_ms=_env_int("VISION_CORE_OPEN_TIMEOUT_MS", "5000"),
            read_timeout_ms=_env_int("VISION_CORE_READ_TIMEOUT_MS", "5000"),
            reconnect_attempts=_env_int("VISION_CORE_RECONNECT_ATTEMPTS", "5"),
            reconnect_delay_seconds=_env_float("VISION_CORE_RECONNECT_DELAY_SECONDS", "2"),
            decoder_threads=_env_int("VISION_CORE_DECODER_THREADS", "1"),
        )

    def _connect(self) -> bool:
        self.close()
        try:
            self._cap = cv2.VideoCapture()
            opened = self._cap.open(
                self._url,
                cv2.CAP_FFMPEG,
                [
                    cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,
                    self._open_timeout,
                    cv2.CAP_PROP_READ_TIMEOUT_MSEC,
                    self._read_timeout,
                    cv2.CAP_PROP_N_THREADS,
                    self._decoder_threads,
                ],
            )
            if opened and self._cap.isOpened():
                if not self._cap.set(cv2.CAP_PROP_CONVERT_RGB, 1):
                    raise VideoSourceStateError("El backend no permite asegurar salida BGR")
                return True
        except cv2.error:
            pass
        except VisionCoreError:
            self.close()
            raise
        except Exception as error:
            self.close()
            raise VideoSourceError(
                "No se pudo iniciar la captura RTSP.",
                context={"operation": "connect"},
            ) from error
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
        raise VideoSourceError("No se pudo abrir RTSP")

    def _read(self):
        try:
            ok, frame = self._cap.read()
        except cv2.error:
            return None
        if not ok or frame is None or frame.size == 0:
            return None
        validate_frame(frame)
        return frame

    def read_frame(self) -> np.ndarray | None:
        if self._cap is None:
            raise VideoSourceStateError("Llama a open() antes de read_frame()")
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
        raise VideoSourceError("Se agotaron los reintentos del stream")

    def close(self):
        cap, self._cap = self._cap, None
        if cap is not None:
            cap.release()
