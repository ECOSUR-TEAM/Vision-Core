import json
import os
import time
from pathlib import Path

import numpy as np
import pytest

from tests.fakes.fake_detector import FakeDetector
from vision_core.core.config.pipeline_config import PipelineConfig
from vision_core.core.telemetry import STAGES
from vision_core.features.door.infrastructure.adapters.polygon_door_analytics import PolygonDoorAnalytics
from vision_core.features.pipeline.application.use_cases.run_pipeline import RunPipeline
from vision_core.features.reid.infrastructure.adapters.memory_reid import InMemoryReID
from vision_core.features.video.domain.ports.video_source import VideoSource
from vision_core.features.video.infrastructure.adapters.file_video_source import FileVideoSource


class RepeatingVideoSource(VideoSource):
    def __init__(self, frames, duration_seconds: float) -> None:
        self._frames = frames
        self._duration_seconds = duration_seconds
        self._started: float | None = None
        self._index = 0

    def open(self) -> None:
        self._started = time.monotonic()
        self._index = 0

    def read_frame(self):
        if self._started is None or time.monotonic() - self._started >= self._duration_seconds:
            return None
        frame = self._frames[self._index % len(self._frames)]
        self._index += 1
        time.sleep(0.005)
        return frame

    def close(self) -> None:
        self._started = None


@pytest.mark.slow
def test_g0_profiling_baseline_measures_at_least_thirty_seconds(
    tmp_path, synthetic_sample, synthetic_zones, synthetic_scene
):
    detections, _, _ = synthetic_scene
    sample = FileVideoSource(synthetic_sample / "sample.avi")
    sample.open()
    frames = []
    while (frame := sample.read_frame()) is not None:
        frames.append(frame.copy())
    sample.close()
    assert len(frames) == 35

    cycle = len(detections)
    calls = {"index": 0}

    def next_detection(frame):
        index = calls["index"] % cycle
        calls["index"] += 1
        return detections[index]

    def next_lost_ids():
        return []

    detector = FakeDetector()
    detector.process = next_detection
    detector.pop_lost_track_ids = next_lost_ids

    artifact = os.getenv("G0_PROFILING_ARTIFACT")
    output = Path(artifact) if artifact else tmp_path / "profiling_results.json"
    app = RunPipeline(
        RepeatingVideoSource(frames, duration_seconds=30.0),
        detector,
        InMemoryReID(ttl_seconds=0),
        PolygonDoorAnalytics(
            synthetic_zones.exterior,
            synthetic_zones.interior,
            synthetic_zones.door,
            confirmation_frames=2,
        ),
        lambda crop: np.array([1.0, 0.0]),
        lambda event: None,
        expected_frame_size=(synthetic_zones.width, synthetic_zones.height),
        config=PipelineConfig(profiling_enabled=True, profiling_output=str(output), render_enabled=False),
        camera_id="camera-g0-30s",
    )

    app.run()

    profile = json.loads(output.read_text(encoding="utf-8"))
    assert profile["camera_id"] == "camera-g0-30s"
    assert profile["frames"] > 0
    assert profile["elapsed_seconds"] >= 30
    assert set(profile["stages"]) == set(STAGES)
    assert all("p50_ms" in stage and "p95_ms" in stage for stage in profile["stages"].values())
    assert all(stage["samples"] > 0 for stage in profile["stages"].values())
