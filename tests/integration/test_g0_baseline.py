import json

import numpy as np

from tests.fakes.fake_detector import FakeDetector
from vision_core.application.frame_profiler import STAGES
from vision_core.application.pipeline_config import PipelineConfig
from vision_core.features.door.infrastructure.adapters.polygon_door_analytics import PolygonDoorAnalytics
from vision_core.features.pipeline.application.use_cases.run_pipeline import RunPipeline
from vision_core.features.reid.infrastructure.adapters.memory_reid import InMemoryReID


def test_g0_baseline_profiling_with_synthetic_video_and_camera_id(
    tmp_path, synthetic_video, synthetic_zones, synthetic_scene
):
    detections, lost_ids, expected_events = synthetic_scene
    detector = FakeDetector(detections_per_frame=list(detections), lost_ids_per_call=[list(ids) for ids in lost_ids])
    events = []
    analytics = PolygonDoorAnalytics(
        synthetic_zones.exterior,
        synthetic_zones.interior,
        synthetic_zones.door,
        confirmation_frames=2,
    )
    output = tmp_path / "profiling_results.json"
    app = RunPipeline(
        synthetic_video,
        detector,
        InMemoryReID(ttl_seconds=0),
        analytics,
        lambda crop: np.array([1.0, 0.0]),
        events.append,
        expected_frame_size=(synthetic_zones.width, synthetic_zones.height),
        config=PipelineConfig(profiling_enabled=True, profiling_output=str(output)),
        camera_id="camera-g0",
    )

    app.run()

    profile = json.loads(output.read_text(encoding="utf-8"))
    assert profile["camera_id"] == "camera-g0"
    assert profile["frames"] == 35
    assert profile["elapsed_seconds"] > 0
    assert profile["fps"] > 0
    assert set(profile["stages"]) == set(STAGES)
    assert all("p50_ms" in stage and "p95_ms" in stage for stage in profile["stages"].values())
    assert [(event.event, event.metadata["from_zone"], event.metadata["to_zone"]) for event in events] == list(
        expected_events
    )
    assert synthetic_video._cap is None
