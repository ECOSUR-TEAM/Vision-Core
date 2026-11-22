import json
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from tests.fakes.fake_reid import FakeReID
from tests.fakes.fake_video_source import FakeVideoSource
from tests.regression.scripted_detector import ScriptedDetector
from vision_core.core.config.pipeline_config import PipelineConfig
from vision_core.core.domain.bbox import BBox
from vision_core.core.serialization.serialization import to_json_value
from vision_core.features.detection.domain.entities.detection import Detection
from vision_core.features.door.infrastructure.adapters import polygon_door_analytics
from vision_core.features.door.infrastructure.adapters.polygon_door_analytics import PolygonDoorAnalytics
from vision_core.features.door.infrastructure.config.zone_loader import load_zones
from vision_core.features.pipeline.infrastructure.dependencies import build_pipeline

TIMING_TOLERANCE_SECONDS = 0.25
FIXTURES_DIR = Path(__file__).parent / "fixtures"
GOLDEN_DIR = Path(__file__).parent / "golden"


class ReplayRunner:
    def __init__(self, scenario_name: str) -> None:
        self._scenario = json.loads((FIXTURES_DIR / f"{scenario_name}.json").read_text(encoding="utf-8"))
        self._zones = load_zones(FIXTURES_DIR / self._scenario["zones"])
        self._fps = int(self._scenario["fps"])
        self._events: list[dict] = []

    def run(self) -> list[dict]:
        detections = [
            [
                Detection(
                    bbox=BBox(
                        item["x"] - 10,
                        item["y"] - 20,
                        item["x"] + 10,
                        item["y"] + 20,
                    ),
                    class_id=0,
                    confidence=float(item["confidence"]),
                    track_id=int(item["track_id"]),
                )
                for item in frame["detections"]
            ]
            for frame in self._scenario["frames"]
        ]
        detector = ScriptedDetector(detections)
        width, height = self._scenario["resolution"]
        video = FakeVideoSource([np.zeros((height, width, 3), dtype=np.uint8) for _ in detections])
        analytics = PolygonDoorAnalytics(
            self._zones.exterior,
            self._zones.interior,
            self._zones.door,
            confirmation_frames=2,
        )
        clock = SimpleNamespace(time=lambda: round(detector.frame_index / self._fps, 6))
        original_time = polygon_door_analytics.time
        polygon_door_analytics.time = clock
        try:
            pipeline = build_pipeline(
                video,
                detector,
                FakeReID(),
                analytics,
                lambda crop: np.array([1.0, 0.0]),
                self._events.append,
                expected_frame_size=(width, height),
                config=PipelineConfig(render_enabled=False, profiling_enabled=False),
            )
            pipeline.run(lambda: False)
        finally:
            polygon_door_analytics.time = original_time
        return [self._normalize(event) for event in self._events]

    @staticmethod
    def _normalize(event) -> dict:
        payload = asdict(event) if not isinstance(event, dict) else dict(event)
        metadata = dict(payload.get("metadata", {}))
        position = metadata.pop("position", None)
        if position is not None:
            metadata["position"] = [round(float(value), 3) for value in position]
        return {
            "event": payload["event"],
            "person_id": payload["person_id"],
            "timestamp": round(float(payload["timestamp"]), 6),
            "metadata": to_json_value(metadata),
        }

    def golden_path(self) -> Path:
        return GOLDEN_DIR / f"{self._scenario['name']}.json"

    def regenerate(self, actual: list[dict]) -> None:
        self.golden_path().write_text(json.dumps(actual, indent=2, sort_keys=True) + "\n", encoding="utf-8")
