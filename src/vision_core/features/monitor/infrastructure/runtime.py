import logging
import threading

logger = logging.getLogger(__name__)


class MonitorRuntime:
    def __init__(self, pipeline, state, *, exit_on_error=False, on_failure=None):
        self._pipeline = pipeline
        self._state = state
        self._exit_on_error = exit_on_error
        self._on_failure = on_failure
        self._stop = threading.Event()
        self._thread = None
        self.failed = threading.Event()

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        try:
            self._pipeline(self._stop.is_set)
            self._state.set_status("stopped")
        except Exception as error:  # noqa: BLE001 - límite del hilo: cualquier fallo se refleja en el estado
            kind = type(error).__name__
            self._state.set_status("error", kind)
            logger.error(
                "Pipeline detenido (%s). Revisa stream, zonas y pesos locales.",
                kind,
                extra={"error_code": kind},
            )
            if self._exit_on_error:
                self.failed.set()
                if self._on_failure is not None:
                    self._on_failure()

    def stop(self):
        self._stop.set()

    def join(self, timeout=None):
        if self._thread is not None:
            self._thread.join(timeout)
