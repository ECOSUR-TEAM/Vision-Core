class FakeMonitorSource:
    dropped_frames = 0

    def __init__(self, inner):
        self.inner = inner
        self.closed = False

    def close(self):
        self.closed = True
