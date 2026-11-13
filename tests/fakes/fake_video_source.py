class FakeVideoSource:
    def __init__(self, frames):
        self._frames = list(frames) + [None]

    def open(self):
        pass

    def read_frame(self):
        return self._frames.pop(0)

    def close(self):
        pass
