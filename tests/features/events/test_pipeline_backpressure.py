"""El pipeline sigue procesando frames aunque la cola del sink esté llena."""

import itertools
import threading
from types import SimpleNamespace

import numpy as np

from tests.fakes.fake_detector import FakeDetector
from tests.fakes.fake_event_sink import FakeEventSink
from tests.fakes.fake_reid import FakeReID
from tests.fakes.fake_video_source import FakeVideoSource
from vision_core.core.config.event_sink_settings import EventSinkSettings
from vision_core.core.domain.event import Event
from vision_core.core.telemetry.metrics import ObservabilityMetrics
from vision_core.features.events.application.use_cases.dispatch_events import EventSinkDispatcher
from vision_core.features.pipeline.application.use_cases.run_pipeline import RunPipeline

_FRAME_COUNT = 12


def test_pipeline_continues_when_sink_queue_is_full():
    block = threading.Event()
    metrics = ObservabilityMetrics()
    destination = FakeEventSink(block=block)
    sink = EventSinkDispatcher(
        destination,
        EventSinkSettings(
            backend="webhook",
            webhook_url="http://127.0.0.1:1/hook",
            queue_size=1,
            max_attempts=1,
        ),
        metrics=metrics,
    )
    frames = [np.zeros((20, 20, 3), dtype=np.uint8) for _ in range(_FRAME_COUNT)]
    sequence = itertools.count()

    def update(person_id, position):
        return Event("PERSON_ENTERED", person_id, metadata={"sequence": next(sequence)})

    door = SimpleNamespace(update=update, get_history=lambda person_id: ())
    processed: list[float] = []
    app = RunPipeline(
        video=FakeVideoSource(frames),
        detector=FakeDetector(),
        reid=FakeReID(),
        door=door,
        embedder=lambda crop: np.zeros(4),
        on_event=lambda event: None,
        event_sink=sink,
        on_frame=lambda frame, tracks, ms: processed.append(ms),
    )
    try:
        app.run()
        counters = metrics.snapshot()["counters"]
        assert len(processed) == _FRAME_COUNT
        assert counters["vision_core_event_sink_submitted_total"] == _FRAME_COUNT
        assert counters["vision_core_event_sink_dropped_total"] > 0
        assert counters.get("vision_core_event_sink_duplicate_total", 0) == 0
    finally:
        block.set()
        sink.close()
