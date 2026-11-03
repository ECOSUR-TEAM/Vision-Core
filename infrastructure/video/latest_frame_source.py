"""Single capture owner; slow inference consumes the newest frame, not a queue."""
import threading

from domain.ports import VideoSource


class LatestFrameSource(VideoSource):
    def __init__(self, source):
        self.source = source
        self._condition = threading.Condition()
        self._stop = threading.Event()
        self._thread = None
        self._frame = None
        self._error = None
        self._ended = False
        self.dropped_frames = 0

    def open(self):
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._capture, daemon=True)
        self._thread.start()

    def _capture(self):
        try:
            self.source.open()
            while not self._stop.is_set():
                frame = self.source.read_frame()
                if frame is None:
                    break
                with self._condition:
                    if self._frame is not None:
                        self.dropped_frames += 1
                    self._frame = frame
                    self._condition.notify_all()
        except Exception as error:
            with self._condition:
                self._error = error
        finally:
            try:
                self.source.close()
            finally:
                with self._condition:
                    self._ended = True
                    self._condition.notify_all()

    def read_frame(self):
        with self._condition:
            self._condition.wait_for(lambda: self._frame is not None or self._ended or self._stop.is_set())
            if self._stop.is_set():
                return None
            if self._error is not None:
                raise self._error
            frame, self._frame = self._frame, None
            return frame

    def close(self):
        # Never release OpenCV from another thread while its read is in progress.
        self._stop.set()
        with self._condition:
            self._condition.notify_all()
        if self._thread is not None:
            self._thread.join(timeout=1)
