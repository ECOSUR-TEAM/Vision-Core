"""Fake sink para verificar entrega sin red ni dependencias externas."""

import threading

from vision_core.core.dto.event_envelope import EventEnvelope
from vision_core.core.errors import PipelineError, ValidationError, codes


class FakeEventSink:
    def __init__(
        self,
        *,
        fail_times: int = 0,
        fail_with: str = "retryable",
        block: threading.Event | None = None,
        entered: threading.Event | None = None,
    ) -> None:
        self.envelopes: list[EventEnvelope] = []
        self.calls = 0
        self._fail_times = fail_times
        self._fail_with = fail_with
        self._block = block
        self._entered = entered
        self._lock = threading.Lock()

    def send(self, envelope: EventEnvelope) -> None:
        if self._entered is not None:
            self._entered.set()
        if self._block is not None:
            self._block.wait(timeout=5)
        with self._lock:
            self.calls += 1
            self.envelopes.append(envelope)
        if self.calls > self._fail_times:
            return
        if self._fail_with == "permanent":
            raise ValidationError("Destino rechazó el evento", code=codes.VALIDATION_FAILED, retryable=False)
        raise PipelineError("Fallo temporal del destino", code=codes.PIPELINE_FAILED, retryable=True)

    def close(self) -> None:
        return None
