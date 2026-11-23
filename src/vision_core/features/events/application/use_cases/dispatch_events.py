"""Despachante no bloqueante: cola acotada, idempotencia, reintentos y dead-letter."""

import logging
import queue
import random
import threading
import time
from collections import OrderedDict, deque
from collections.abc import Callable

from vision_core.core.config.event_sink_settings import EventSinkSettings
from vision_core.core.dto.event_envelope import EventEnvelope
from vision_core.core.errors import VisionCoreError, codes
from vision_core.core.telemetry.metrics import ObservabilityMetrics
from vision_core.features.events.domain.ports.event_sink import EventSink

logger = logging.getLogger(__name__)

_DELIVERED = "vision_core_event_sink_delivered_total"
_SUBMITTED = "vision_core_event_sink_submitted_total"
_RETRIED = "vision_core_event_sink_retried_total"
_DROPPED = "vision_core_event_sink_dropped_total"
_DUPLICATE = "vision_core_event_sink_duplicate_total"
_DEAD_LETTER = "vision_core_event_sink_dead_letter_total"
_QUEUE_DEPTH = "vision_core_event_sink_queue_depth"
_STOP_CHECK_SECONDS = 0.01


class EventSinkDispatcher:
    """Implementa ``EventSink`` enviando al destino en un hilo de trabajo.

    ``send`` nunca espera espacio en la cola: aplica la política configurada y
    contabiliza el descarte. La clave se marca como vista solo tras una entrega
    confirmada; un descarte o un dead-letter libera la clave para que el
    productor pueda reenviarla.
    """

    def __init__(
        self,
        destination: EventSink,
        settings: EventSinkSettings | None = None,
        *,
        on_dead_letter: Callable[[EventEnvelope, str], None] | None = None,
        metrics: ObservabilityMetrics | None = None,
        sleep: Callable[[float], None] = time.sleep,
        jitter: Callable[[], float] = random.random,
    ) -> None:
        self._destination = destination
        self._settings = settings or EventSinkSettings()
        self._queue: queue.Queue[EventEnvelope] = queue.Queue(maxsize=self._settings.queue_size)
        self._seen: OrderedDict[str, None] = OrderedDict()
        self._inflight: set[str] = set()
        self._seen_lock = threading.Lock()
        self._queue_lock = threading.Lock()
        self._destination_lock = threading.Lock()
        self._destination_closed = False
        self._dead_letters: deque[tuple[EventEnvelope, str]] = deque(maxlen=self._settings.dead_letter_size)
        self._on_dead_letter = on_dead_letter
        self._metrics = metrics
        self._sleep = sleep
        self._jitter = jitter
        self._closed = threading.Event()
        self._interrupt = threading.Event()
        self._stop = threading.Event()
        self._worker = threading.Thread(target=self._run, name="event-sink-dispatcher", daemon=True)
        self._worker.start()

    def send(self, envelope: EventEnvelope) -> None:
        self._increment(_SUBMITTED)
        if self._closed.is_set():
            self._increment(_DROPPED)
            self._publish_depth()
            return
        if not self._reserve(envelope.event_id):
            self._increment(_DUPLICATE)
            return
        with self._queue_lock:
            if self._closed.is_set():
                self._release(envelope.event_id, delivered=False)
                self._increment(_DROPPED)
                self._publish_depth()
                return
            try:
                self._queue.put_nowait(envelope)
            except queue.Full:
                self._handle_overflow(envelope)
        self._publish_depth()

    def close(self) -> None:
        self._closed.set()
        self._interrupt.set()
        deadline = time.monotonic() + 2.0
        while not self._queue.empty() and time.monotonic() < deadline:
            time.sleep(_STOP_CHECK_SECONDS)
        self._stop.set()
        self._worker.join(timeout=max(0.0, deadline - time.monotonic()))
        if self._worker.is_alive():
            logger.warning("event sink dispatcher shutdown timed out")
        self._drain_pending()
        self._close_destination()

    def dead_letters(self) -> tuple[tuple[EventEnvelope, str], ...]:
        return tuple(self._dead_letters)

    def queue_depth(self) -> int:
        return self._queue.qsize()

    def _reserve(self, event_id: str) -> bool:
        with self._seen_lock:
            if event_id in self._seen or event_id in self._inflight:
                if event_id in self._seen:
                    self._seen.move_to_end(event_id)
                return False
            self._inflight.add(event_id)
            return True

    def _release(self, event_id: str, *, delivered: bool) -> None:
        with self._seen_lock:
            self._inflight.discard(event_id)
            if not delivered:
                return
            self._seen[event_id] = None
            self._seen.move_to_end(event_id)
            while len(self._seen) > self._settings.dedupe_size:
                self._seen.popitem(last=False)

    def _abandon(self, envelope: EventEnvelope) -> None:
        self._release(envelope.event_id, delivered=False)
        self._increment(_DROPPED)

    def _handle_overflow(self, envelope: EventEnvelope) -> None:
        self._increment(_DROPPED)
        if self._settings.overflow_policy == "drop-oldest":
            try:
                dropped = self._queue.get_nowait()
            except queue.Empty:
                self._release(envelope.event_id, delivered=False)
                return
            self._queue.task_done()
            self._release(dropped.event_id, delivered=False)
            try:
                self._queue.put_nowait(envelope)
            except queue.Full:
                self._release(envelope.event_id, delivered=False)
                logger.warning("event sink queue stayed full after overflow")
            return
        self._release(envelope.event_id, delivered=False)

    def _run(self) -> None:
        try:
            while not self._stop.is_set():
                try:
                    envelope = self._queue.get(timeout=0.05)
                except queue.Empty:
                    continue
                try:
                    if self._stop.is_set():
                        self._abandon(envelope)
                    else:
                        self._deliver(envelope)
                finally:
                    self._queue.task_done()
                    self._publish_depth()
        finally:
            self._close_destination()

    def _deliver(self, envelope: EventEnvelope) -> None:
        code = codes.INTERNAL_ERROR
        for attempt in range(1, self._settings.max_attempts + 1):
            if self._stop.is_set():
                self._abandon(envelope)
                return
            try:
                self._destination.send(envelope)
                self._release(envelope.event_id, delivered=True)
                self._increment(_DELIVERED)
                return
            except VisionCoreError as error:
                code = error.code
                retryable = error.retryable
            except Exception:  # noqa: BLE001 - un destino roto no debe detener el pipeline
                code = codes.INTERNAL_ERROR
                retryable = True
            if self._stop.is_set():
                self._abandon(envelope)
                return
            if not retryable or attempt >= self._settings.max_attempts:
                self._record_dead_letter(envelope, code, attempt)
                return
            if self._wait_for_retry(self._retry_delay(attempt)):
                self._abandon(envelope)
                return
            self._increment(_RETRIED)

    def _wait_for_retry(self, delay: float) -> bool:
        if self._sleep is time.sleep:
            return self._interrupt.wait(delay)
        remaining = delay
        while remaining > 0 and not self._interrupt.is_set():
            step = min(remaining, _STOP_CHECK_SECONDS)
            self._sleep(step)
            remaining -= step
        return self._interrupt.is_set()

    def _retry_delay(self, attempt: int) -> float:
        delay = self._settings.retry_base_seconds * 2 ** (attempt - 1)
        noise = 1 - self._settings.retry_jitter + 2 * self._settings.retry_jitter * self._jitter()
        return min(max(0.0, delay * noise), self._settings.retry_max_seconds)

    def _record_dead_letter(self, envelope: EventEnvelope, code: str, attempt: int) -> None:
        self._release(envelope.event_id, delivered=False)
        self._dead_letters.append((envelope, code))
        self._increment(_DEAD_LETTER)
        logger.warning(
            "event sink delivery exhausted event_id=%s code=%s attempts=%s", envelope.event_id, code, attempt
        )
        if self._on_dead_letter is None:
            return
        try:
            self._on_dead_letter(envelope, code)
        except Exception:  # noqa: BLE001 - el callback de DLQ no debe romper el worker
            logger.warning("event sink dead-letter callback failed for event_id=%s", envelope.event_id)

    def _drain_pending(self) -> None:
        with self._queue_lock:
            while True:
                try:
                    envelope = self._queue.get_nowait()
                except queue.Empty:
                    break
                try:
                    self._abandon(envelope)
                finally:
                    self._queue.task_done()
        self._publish_depth()

    def _close_destination(self) -> None:
        with self._destination_lock:
            if self._destination_closed:
                return
            self._destination_closed = True
            try:
                self._destination.close()
            except Exception:  # noqa: BLE001 - el cierre del destino no debe romper el worker
                logger.warning("event sink destination close failed")

    def _increment(self, name: str) -> None:
        if self._metrics is not None:
            self._metrics.increment(name)

    def _publish_depth(self) -> None:
        if self._metrics is not None:
            self._metrics.set_gauge(_QUEUE_DEPTH, self._queue.qsize())
