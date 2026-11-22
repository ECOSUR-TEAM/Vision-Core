import logging
import math
import time
from collections.abc import Callable
from typing import Any

from vision_core.application.frame_profiler import FrameProfiler
from vision_core.application.pipeline_config import PipelineConfig
from vision_core.core.errors import PipelineError, ValidationError, codes
from vision_core.core.validation import validate_frame
from vision_core.features.detection.domain.ports.detector_manager import DetectorManager
from vision_core.features.door.domain.ports.door_analytics import DoorAnalytics
from vision_core.features.pipeline.application.dto.request.request_process_frame import RequestProcessFrame
from vision_core.features.pipeline.application.dto.request.request_run_pipeline import RequestRunPipeline
from vision_core.features.pipeline.application.dto.response.response_pipeline_event import ResponsePipelineEvent
from vision_core.features.pipeline.application.dto.response.response_process_frame import ResponseProcessFrame
from vision_core.features.pipeline.application.mappers.pipeline_mapper import event_to_dto, resolved_track_to_dto
from vision_core.features.pipeline.domain.attendance import SessionAttendance
from vision_core.features.pipeline.domain.entities.resolved_track import ResolvedTrack
from vision_core.features.pipeline.domain.ports.event_consumer import EventConsumer
from vision_core.features.reid.domain.ports.embedding_extractor import EmbeddingExtractor
from vision_core.features.reid.domain.ports.reid_memory import ReIDMemory
from vision_core.features.video.domain.ports.video_source import VideoSource

logger = logging.getLogger(__name__)


class RunPipeline:
    def __init__(
        self,
        video: VideoSource,
        detector: DetectorManager,
        reid: ReIDMemory,
        door: DoorAnalytics,
        embedder: EmbeddingExtractor,
        on_event: EventConsumer,
        expected_frame_size: tuple[int, int] | None = None,
        on_frame: Callable[[Any, tuple[ResolvedTrack, ...], float], None] | None = None,
        config: PipelineConfig | None = None,
        camera_id: str = "default",
    ) -> None:
        self._expected_frame_size = expected_frame_size
        self._on_frame = on_frame
        self._video = video
        self._detector = detector
        self._reid = reid
        self._door = door
        self._embed = embedder
        self._on_event = on_event
        self._attendance = SessionAttendance()
        self._person_by_track: dict[int, str] = {}
        self._last_embedding_by_track: dict[int, Any] = {}
        self._config = config or PipelineConfig(profiling_enabled=False)
        self._camera_id = camera_id or "default"
        self.profiler = FrameProfiler(enabled=self._config.profiling_enabled, camera_id=self._camera_id)
        self._profiling_output = self._config.profiling_output
        self.embedding_batch_size = self._config.embedding_batch_size
        self.embedding_frame_stride = self._config.embedding_frame_stride
        self._metrics = None
        self._metrics_camera_id: str | None = None

    def set_observability(self, metrics, *, camera_id: str | None = None) -> None:
        self._metrics = metrics
        self._metrics_camera_id = camera_id or self._camera_id

    def run(
        self,
        stop_requested: Callable[[], bool] = lambda: False,
        *,
        request: RequestRunPipeline | None = None,
    ) -> None:
        if request is not None and request.expected_frame_size is not None:
            self._expected_frame_size = request.expected_frame_size
        self.profiler.reset()
        failed = False
        try:
            self._video.open()
            while not stop_requested():
                with self.profiler.measure("decode"):
                    frame = self._video.read_frame()
                if frame is None:
                    break
                self._process_frame(frame)
        except Exception:  # noqa: BLE001 - preserve pipeline failure
            failed = True
            if self._metrics is not None:
                self._metrics.increment("vision_core_errors_total", camera_id=self._metrics_camera_id)
            raise
        finally:
            try:
                self._video.close()
            except Exception as close_error:  # noqa: BLE001 - preserve pipeline failure
                logger.error("Falló el cierre de video (%s)", type(close_error).__name__)
                if not failed:
                    raise
            finally:
                self._save_profile()

    def _save_profile(self) -> None:
        if not self.profiler.enabled or not self._profiling_output:
            return
        try:
            path = self.profiler.save(self._profiling_output)
            logger.info("Profiling guardado en %s", path)
        except OSError as error:  # noqa: BLE001 - el fallback no debe matar el pipeline
            logger.warning("No se pudo guardar el profiling (%s)", type(error).__name__)

    def process_frame(self, request: RequestProcessFrame) -> ResponseProcessFrame:
        validate_frame(request.frame)
        return self._process_frame(request.frame)

    def _process_frame(self, frame: Any) -> ResponseProcessFrame:
        started = time.perf_counter()
        resolved = []
        events: list[ResponsePipelineEvent] = []
        if self._expected_frame_size is not None and (frame.shape[1], frame.shape[0]) != self._expected_frame_size:
            raise PipelineError(
                "La resolución del stream no coincide con la calibración de zonas",
                code=codes.PIPELINE_CALIBRATION_MISMATCH,
                context={"operation": "frame_size"},
            )
        inference_started = time.perf_counter()
        with self.profiler.measure("detection"):
            detections = self._detector.process(frame)
        if self._metrics is not None:
            self._metrics.observe(
                "vision_core_inference_latency_ms",
                (time.perf_counter() - inference_started) * 1000,
                camera_id=self._metrics_camera_id,
            )
        visible_tracks = {det.track_id for det in detections}
        new_tracks = sum(track_id not in self._person_by_track for track_id in visible_tracks)
        absent_tracks = set(self._person_by_track) - visible_tracks
        expired_tracks = set(self._detector.pop_lost_track_ids())
        if self._metrics is not None:
            self._metrics.increment(
                "vision_core_tracks_lost_total", len(expired_tracks), camera_id=self._metrics_camera_id
            )
        with self.profiler.measure("reid_tracking"):
            for track_id in (absent_tracks | expired_tracks) - visible_tracks:
                person_id = self._person_by_track.pop(track_id, None)
                embedding = self._last_embedding_by_track.pop(track_id, None)
                if person_id is not None and embedding is not None:
                    self._reid.mark_lost(person_id, embedding)
            begin_frame = getattr(self._reid, "begin_frame", None)
            if begin_frame is not None:
                begin_frame(visible_tracks)
        for det in detections:
            coordinates = (det.bbox.x1, det.bbox.y1, det.bbox.x2, det.bbox.y2)
            if not all(math.isfinite(value) for value in coordinates):
                raise ValidationError("El detector devolvió coordenadas no finitas")
            if det.bbox.x2 <= det.bbox.x1 or det.bbox.y2 <= det.bbox.y1:
                raise ValidationError("El detector devolvió una caja sin área")
            height, width = frame.shape[:2]
            x1, y1 = max(0, math.floor(det.bbox.x1)), max(0, math.floor(det.bbox.y1))
            x2, y2 = min(width, math.ceil(det.bbox.x2)), min(height, math.ceil(det.bbox.y2))
            if x2 <= x1 or y2 <= y1:
                raise ValidationError("La caja del detector está fuera del frame")
            crop = frame[y1:y2, x1:x2]
            reid_started = time.perf_counter()
            with self.profiler.measure("embedding"):
                embedding = self._embed(crop)
            with self.profiler.measure("reid_tracking"):
                person_id = self._reid.resolve(det.track_id, embedding, det.bbox)
            if self._metrics is not None:
                self._metrics.observe(
                    "vision_core_reid_latency_ms",
                    (time.perf_counter() - reid_started) * 1000,
                    camera_id=self._metrics_camera_id,
                )
            self._person_by_track[det.track_id] = person_id
            self._last_embedding_by_track[det.track_id] = embedding.copy()
            resolved.append(ResolvedTrack(person_id, det.bbox, det.confidence, det.track_id))
            with self.profiler.measure("analytics"):
                event = self._door.update(person_id, det.bbox.center)
            if event is not None:
                event.metadata.update(self._attendance.apply(event))
                events.append(event_to_dto(event))
                self._on_event(event)
        if self._metrics is not None:
            self._metrics.increment("vision_core_tracks_created_total", new_tracks, camera_id=self._metrics_camera_id)
            self._metrics.set_gauge(
                "vision_core_active_people", len(self._person_by_track), camera_id=self._metrics_camera_id
            )
        processing_ms = (time.perf_counter() - started) * 1000
        self.profiler.record("frame_total", processing_ms / 1000)
        self.profiler.record_frame()
        if self._on_frame is not None:
            self._on_frame(frame, tuple(resolved), processing_ms)
        return ResponseProcessFrame(
            people=tuple(resolved_track_to_dto(track) for track in resolved),
            events=tuple(events),
            processing_ms=processing_ms,
        )
