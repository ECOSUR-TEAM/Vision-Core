import numpy as np

from tests.fakes.fake_detector import FakeDetector
from vision_core.features.door.infrastructure.adapters.polygon_door_analytics import PolygonDoorAnalytics
from vision_core.features.pipeline.application.use_cases.run_pipeline import RunPipeline
from vision_core.features.reid.infrastructure.adapters.memory_reid import InMemoryReID


def test_synthetic_video_pipeline_events_people_zones_and_cleanup(synthetic_video, synthetic_zones, synthetic_scene):
    detections, lost_ids, expected_events = synthetic_scene
    detector = FakeDetector(detections_per_frame=list(detections), lost_ids_per_call=[list(ids) for ids in lost_ids])
    events = []
    people_by_frame = []
    analytics = PolygonDoorAnalytics(
        synthetic_zones.exterior,
        synthetic_zones.interior,
        synthetic_zones.door,
        confirmation_frames=2,
    )
    app = RunPipeline(
        synthetic_video,
        detector,
        InMemoryReID(ttl_seconds=0),
        analytics,
        lambda crop: np.array([1.0, 0.0]),
        events.append,
        expected_frame_size=(synthetic_zones.width, synthetic_zones.height),
        on_frame=lambda frame, tracks, ms: people_by_frame.append(tuple(track.person_id for track in tracks)),
    )

    app.run()

    assert len(people_by_frame) == 35
    assert [(event.event, event.metadata["from_zone"], event.metadata["to_zone"]) for event in events] == list(
        expected_events
    )
    assert all(event.timestamp > 0 for event in events)
    person_ids = {event.person_id for event in events}
    assert len(person_ids) == 1
    person_id = person_ids.pop()
    history = analytics.get_history(person_id)
    assert len(history) == 31
    assert history[-1].zone == "exterior"
    assert people_by_frame[16] == ()
    assert people_by_frame[20] == (person_id,)
    assert synthetic_video._cap is None
