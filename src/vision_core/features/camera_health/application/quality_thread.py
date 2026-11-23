import logging
import threading
from collections import deque

import numpy as np

logger = logging.getLogger(__name__)


class QualityThread(threading.Thread):
    """Analiza el último frame en un hilo propio cuando no hay renderer."""

    def __init__(
        self,
        analyze,
        *,
        poll_interval: float = 0.01,
        on_error=None,
        name: str = "vision-core-camera-quality",
    ) -> None:
        if poll_interval <= 0:
            raise ValueError("poll_interval debe ser positivo")
        super().__init__(name=name, daemon=True)
        self._analyze = analyze
        self._on_error = on_error
        self._poll_interval = poll_interval
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._pending: deque[np.ndarray] = deque(maxlen=1)
        self.error: Exception | None = None
        self.failed = threading.Event()

    def submit(self, frame: np.ndarray) -> None:
        if self._stop_event.is_set() or not isinstance(frame, np.ndarray):
            return
        with self._lock:
            self._pending.append(frame.copy())

    def run(self) -> None:
        while True:
            with self._lock:
                frame = self._pending.popleft() if self._pending else None
            if frame is None:
                if self._stop_event.is_set():
                    break
                self._stop_event.wait(self._poll_interval)
                continue
            try:
                self._analyze(frame)
            except Exception as error:
                self.error = error
                self.failed.set()
                if self._on_error is not None:
                    self._on_error(error)
                else:
                    logger.warning("Falló el análisis de calidad (%s)", type(error).__name__)
                break

    def close(self, timeout: float = 2.0) -> bool:
        self._stop_event.set()
        self.join(timeout=timeout)
        return not self.is_alive()
