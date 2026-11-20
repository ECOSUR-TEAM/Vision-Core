"""Dedicated render/JPEG thread decoupled from sequential AI inference."""

import logging
import threading
import time
from collections.abc import Callable

from vision_core.features.monitor.infrastructure.latest_frame_buffer import LatestFrameBuffer
from vision_core.features.monitor.infrastructure.render_job import RenderJob

logger = logging.getLogger(__name__)


class RendererThread(threading.Thread):
    """Consume el buffer de tamaño 1 y renderiza/JPEG en su propio hilo.

    La inferencia sigue siendo secuencial: ``submit`` solo copia el payload y
    publica; nunca espera a que este hilo termine de dibujar ni de codificar.
    """

    def __init__(
        self,
        buffer: LatestFrameBuffer[RenderJob],
        on_render: Callable[[RenderJob], None],
        *,
        poll_interval: float = 0.01,
        on_error: Callable[[Exception], None] | None = None,
        name: str = "vision-core-renderer",
    ) -> None:
        if poll_interval <= 0:
            raise ValueError("poll_interval debe ser positivo")
        super().__init__(name=name, daemon=True)
        self.buffer = buffer
        self.error: Exception | None = None
        self.failed = threading.Event()
        self._on_render = on_render
        self._on_error = on_error
        self._poll_interval = poll_interval
        self._stop_event = threading.Event()
        self._busy = threading.Event()
        self._handoff_lock = threading.Lock()
        self._pending = 0

    def submit(
        self,
        frame,
        tracks,
        *,
        zones=None,
        zone_by_person=None,
        label_for=None,
        demo: bool = False,
        processing_ms: float = 0.0,
        dropped: int = 0,
    ) -> None:
        """Llamado por el hilo de inferencia: copia y publica sin bloquearse."""
        if self._stop_event.is_set():
            return
        job = RenderJob.capture(
            frame,
            tracks,
            zones=zones,
            zone_by_person=zone_by_person,
            label_for=label_for,
            demo=demo,
            processing_ms=processing_ms,
            dropped=dropped,
        )
        with self._handoff_lock:
            if self._stop_event.is_set():
                return
            replaced = self.buffer.publish(job)
            self._pending += 1
            if replaced:
                # El job sobrescrito nunca llegará a renderizarse.
                self._pending -= 1

    def run(self) -> None:
        while True:
            job = None
            with self._handoff_lock:
                if self._stop_event.is_set() and self._pending == 0:
                    break
                job = self.buffer.take()
                if job is not None:
                    # Marcar ocupado bajo el mismo lock con el que ``drain``
                    # consulta el estado cierra la ventana take() -> busy.set().
                    self._busy.set()
            if job is None:
                self._stop_event.wait(self._poll_interval)
                continue
            try:
                self._on_render(job)
            except Exception as error:  # noqa: BLE001 - propagar al dueño del hilo
                self.error = error
                self.failed.set()
                if self._on_error is not None:
                    try:
                        self._on_error(error)
                    except Exception:  # noqa: BLE001 - no ocultar el error original
                        logger.exception("Falló el callback de error del renderer")
                else:
                    logger.exception("Fallo en el hilo de renderizado (%s)", type(error).__name__)
                with self._handoff_lock:
                    self.buffer.clear()
                    self._pending = 0
                    self._busy.clear()
                break
            finally:
                with self._handoff_lock:
                    self._pending = max(0, self._pending - 1)
                    self._busy.clear()

    def drain(self, timeout: float = 2.0) -> bool:
        """Espera a que se rendericen los frames pendientes antes del apagado."""
        deadline = time.perf_counter() + max(timeout, 0.0)
        while time.perf_counter() < deadline:
            with self._handoff_lock:
                if self._pending == 0 and not self._busy.is_set():
                    return True
            time.sleep(0.005)
        return False

    def stop(self, *, timeout: float = 1.0) -> bool:
        """Drena los jobs encolados y despierta el ``wait`` para hacer ``join``."""
        drained = self.drain(timeout=timeout)
        self._stop_event.set()
        return drained

    def close(self, timeout: float = 2.0) -> bool:
        self.stop(timeout=timeout / 2)
        self.join(timeout=timeout)
        if self.is_alive():
            logger.warning("El renderer no terminó en %.2fs", timeout)
        return not self.is_alive()
