import time

from domain.ports import VideoSource


class LimitedSource(VideoSource):
    def __init__(self, source, limit):
        self.source, self.limit, self.frames = source, limit, 0
        self.read_seconds = []

    def open(self):
        self.source.open()

    def read_frame(self):
        if self.frames >= self.limit:
            return None
        start = time.perf_counter()
        frame = self.source.read_frame()
        if frame is not None:
            self.read_seconds.append(time.perf_counter() - start)
            self.frames += 1
        return frame

    def close(self):
        self.source.close()
