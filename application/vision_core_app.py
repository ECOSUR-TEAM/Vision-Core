import logging
import math
import time
from typing import Callable
import numpy as np

from domain.entities import Event, ResolvedTrack
from domain.attendance import SessionAttendance
from domain.ports import VideoSource, DetectorManager, ReIDMemory, DoorAnalytics


logger = logging.getLogger(__name__)


class VisionCoreApp:
    """VC-APP (Fabricio): orquesta el pipeline completo.

    video -> DetectorManager -> ReIDMemory -> DoorAnalytics -> Event

    Depende solo de los ports (domain.ports), nunca de una implementación
    concreta: eso permite testear con mocks y que cada módulo avance
    en paralelo sin acoplarse a los demás.
    """

    def __init__(
        self,
        video_source: VideoSource,
        detector: DetectorManager,
        reid_memory: ReIDMemory,
        door_analytics: DoorAnalytics,
        embedder: Callable[[np.ndarray], np.ndarray],
        on_event: Callable[[Event], None],
        expected_frame_size: tuple[int, int] | None = None,
        on_frame: Callable[[np.ndarray, tuple[ResolvedTrack, ...], float], None] | None = None,
    ) -> None:
        self._expected_frame_size = expected_frame_size
        self._on_frame = on_frame
        self._video = video_source
        self._detector = detector
        self._reid = reid_memory
        self._door = door_analytics
        self._embed = embedder
        self._on_event = on_event
        self._attendance = SessionAttendance()
        self._person_by_track: dict[int, str] = {}
        self._last_embedding_by_track: dict[int, np.ndarray] = {}

    def run(self, stop_requested: Callable[[], bool] = lambda: False) -> None:
        try:
            self._video.open()
            while not stop_requested():
                frame = self._video.read_frame()
                if frame is None:
                    break
                self._process_frame(frame)
        except BaseException:
            # Preserve the original failure even when resource cleanup also fails.
            try:
                self._video.close()
            except BaseException as close_error:
                logger.error("Falló el cierre de video (%s)", type(close_error).__name__)
            raise
        else:
            self._video.close()

    def _process_frame(self, frame: np.ndarray) -> None:
        started = time.perf_counter()
        resolved = []
        if self._expected_frame_size is not None and (frame.shape[1], frame.shape[0]) != self._expected_frame_size:
            raise ValueError("La resolución del stream no coincide con la calibración de zonas")
        detections = self._detector.process(frame)
        visible_tracks = {det.track_id for det in detections}
        absent_tracks = set(self._person_by_track) - visible_tracks
        expired_tracks = set(self._detector.pop_lost_track_ids())
        # Release identities as soon as they are absent, even if the motion tracker
        # retains its local track for another 30 frames. Visible IDs stay reserved.
        for track_id in (absent_tracks | expired_tracks) - visible_tracks:
            person_id = self._person_by_track.pop(track_id, None)
            embedding = self._last_embedding_by_track.pop(track_id, None)
            if person_id is not None and embedding is not None:
                self._reid.mark_lost(person_id, embedding)

        # Optional for legacy adapters; concrete ReID reserves still-known IDs
        # before a new track can claim the same absent person's appearance.
        begin_frame = getattr(self._reid, 'begin_frame', None)
        if begin_frame is not None:
            begin_frame(visible_tracks)

        for det in detections:
            coordinates = (det.bbox.x1, det.bbox.y1, det.bbox.x2, det.bbox.y2)
            if not all(math.isfinite(value) for value in coordinates):
                raise ValueError("El detector devolvió coordenadas no finitas")
            if det.bbox.x2 <= det.bbox.x1 or det.bbox.y2 <= det.bbox.y1:
                raise ValueError("El detector devolvió una caja sin área")
            height, width = frame.shape[:2]
            x1, y1 = max(0, math.floor(det.bbox.x1)), max(0, math.floor(det.bbox.y1))
            x2, y2 = min(width, math.ceil(det.bbox.x2)), min(height, math.ceil(det.bbox.y2))
            if x2 <= x1 or y2 <= y1:
                raise ValueError("La caja del detector está fuera del frame")
            crop = frame[y1:y2, x1:x2]
            embedding = self._embed(crop)
            person_id = self._reid.resolve(det.track_id, embedding, det.bbox)
            self._person_by_track[det.track_id] = person_id
            self._last_embedding_by_track[det.track_id] = embedding.copy()
            resolved.append(ResolvedTrack(person_id, det.bbox, det.confidence, det.track_id))

            event = self._door.update(person_id, det.bbox.center)
            if event is not None:
                event.metadata.update(self._attendance.apply(event))
                self._on_event(event)
        if self._on_frame is not None:
            self._on_frame(frame, tuple(resolved), (time.perf_counter() - started) * 1000)
