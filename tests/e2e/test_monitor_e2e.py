import json
import threading
from types import SimpleNamespace
from urllib.request import urlopen

import numpy as np
import pytest

import main
from tests.fakes.fake_detector import FakeDetector
from vision_core.features.monitor.infrastructure.http.server import make_server
from vision_core.features.reid.infrastructure.adapters.memory_reid import InMemoryReID
from vision_core.features.video.infrastructure.adapters.file_video_source import FileVideoSource


@pytest.mark.slow
def test_monitor_e2e_with_video_file_and_real_zones(monkeypatch, synthetic_sample, synthetic_zones, synthetic_scene):
    detections, lost_ids, expected_events = synthetic_scene
    video_path = synthetic_sample / "sample.avi"
    zones_path = synthetic_sample / "zones.json"
    video_source = FileVideoSource(video_path)
    state = main.build_monitor_state()

    monkeypatch.setenv("VISION_CORE_ZONE_CONFIRMATION_FRAMES", "2")
    monkeypatch.setattr(
        main,
        "build_detection",
        lambda: SimpleNamespace(
            detector=FakeDetector(
                detections_per_frame=list(detections),
                lost_ids_per_call=[list(ids) for ids in lost_ids],
            )
        ),
    )
    monkeypatch.setattr(
        main,
        "build_reid",
        lambda: SimpleNamespace(
            memory=InMemoryReID(ttl_seconds=0),
            embedder=lambda crop: np.array([1.0, 0.0]),
        ),
    )
    original_build_video = main.build_video
    monkeypatch.setattr(
        main,
        "build_video",
        lambda latest=False: original_build_video(source=video_source, latest=False),
    )

    server = make_server("127.0.0.1", 0, state)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        main.build_monitor_pipeline(state, zones_file=str(zones_path))(lambda: False)
        base_url = f"http://127.0.0.1:{server.server_port}"

        with urlopen(f"{base_url}/") as response:
            assert response.status == 200
            assert b"<html" in response.read().lower()

        with urlopen(f"{base_url}/api/state") as response:
            snapshot = json.load(response)
        assert snapshot["status"] == "running"
        assert snapshot["frame"] == 35
        chronological = list(reversed(snapshot["events"]))
        assert [
            (event["event"], event["metadata"]["from_zone"], event["metadata"]["to_zone"]) for event in chronological
        ] == list(expected_events)
        assert snapshot["counts"] == {"PERSON_ENTERED": 2, "PERSON_EXITED": 2, "FALSE_ALARM": 1}
        assert snapshot["dropped_frames"] == 0
        assert snapshot["fps"] > 0
        assert snapshot["processing_ms"] >= 0
        assert snapshot["age_seconds"] >= 0
        assert len(snapshot["people"]) == 1
        assert snapshot["people"][0]["zone"] == "exterior"
        assert snapshot["people"][0]["display_name"] == "Persona 1"

        with urlopen(f"{base_url}/api/frame") as response:
            assert response.status == 200
            assert response.read().startswith(b"\xff\xd8")
            assert response.headers["X-Frame-Sequence"] == "35"

        with urlopen(f"{base_url}/api/frame?after=35") as response:
            assert response.status == 204
            assert response.read() == b""

        assert video_source._cap is None
        assert synthetic_zones.width == 810
        assert synthetic_zones.height == 1080
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
