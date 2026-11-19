import json
import time

import torch

from vision_core.features.pipeline.application.use_cases.run_pipeline import RunPipeline


class MeasuredApp(RunPipeline):
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
        self.output.write(
            json.dumps(
                {
                    "kind": "resolved",
                    "frame": getattr(self._video, "frames", 0) or 0,
                    "persons": self._person_by_track,
                    "processing_ms": elapsed * 1000,
                }
            )
            + "\n"
        )
