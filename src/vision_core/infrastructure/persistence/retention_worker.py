import logging
import threading
import time

from vision_core.infrastructure.persistence.retention_job import RetentionJob

logger = logging.getLogger(__name__)


class RetentionWorker:
    def __init__(self, job: RetentionJob, *, interval_seconds: float, sleep=time.sleep, clock=time.time):
        self._job = job
        self._interval = max(1.0, float(interval_seconds))
        self._sleep = sleep
        self._clock = clock
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="vision-core-retention", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout)
        self._thread = None

    def _run(self) -> None:
        while not self._stop.is_set():
            self._sleep(self._interval)
            if self._stop.is_set():
                break
            try:
                self._job.run_once(now=self._clock())
            except Exception as error:
                logger.warning("retention worker failed: %s", error)
