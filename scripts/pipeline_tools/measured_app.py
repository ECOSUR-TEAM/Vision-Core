import json
import time

import torch

from application.vision_core_app import VisionCoreApp


class MeasuredApp(VisionCoreApp):
    def __init__(self, *args, output, **kwargs):
        super().__init__(*args, **kwargs)
        self.output = output
        self.durations = []

    def _process_frame(self, frame):
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        start = time.perf_counter()
        super()._process_frame(frame)
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        elapsed = time.perf_counter() - start
        self.durations.append(elapsed)
        self.output.write(json.dumps({'kind': 'resolved', 'frame': self._video.frames,
            'persons': self._person_by_track, 'processing_ms': elapsed * 1000}) + '\n')
