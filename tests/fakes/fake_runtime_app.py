import numpy as np

from vision_core.domain.model.event import Event
from vision_core.domain.model.resolved_track import ResolvedTrack
from vision_core.shared.domain.bbox import BBox


class FakeRuntimeApp:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def run(self, _stop_requested):
        self.kwargs["on_event"](Event("PERSON_ENTERED", "p1", 10.0, event_id="evt-1"))
        self.kwargs["on_frame"](
            np.zeros((2, 2, 3), dtype=np.uint8),
            (ResolvedTrack("p1", BBox(1, 2, 3, 4), 0.9, track_id=7),),
            1.0,
        )
