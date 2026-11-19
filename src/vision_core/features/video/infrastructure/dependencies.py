import os
from dataclasses import dataclass
from typing import Any

from vision_core.shared.errors import ConfigurationError

from ..application.dto.request.request_close_video import RequestCloseVideo
from ..application.dto.request.request_open_video import RequestOpenVideo
from ..application.dto.request.request_read_frame import RequestReadFrame
from ..application.mappers.video_mapper import dto_to_frame
from ..application.use_cases.close_video import CloseVideo
from ..application.use_cases.open_video import OpenVideo
from ..application.use_cases.read_frame import ReadFrame
from ..domain.ports.video_source import VideoSource
from .adapters.file_video_source import FileVideoSource
from .adapters.latest_frame_source import LatestFrameSource
from .adapters.rtsp_video_source import RtspVideoSource


@dataclass
class VideoDependencies(VideoSource):
    open_video: OpenVideo
    read_frame_use_case: ReadFrame
    close_video: CloseVideo
    source: VideoSource

    def open(self) -> None:
        self.open_video.execute(RequestOpenVideo())

    def read_frame(self) -> Any | None:
        return dto_to_frame(self.read_frame_use_case.execute(RequestReadFrame()))

    def close(self) -> None:
        self.close_video.execute(RequestCloseVideo())

    @property
    def dropped_frames(self) -> int:
        return getattr(self.source, "dropped_frames", 0)


def build_video(
    source: VideoSource | None = None,
    *,
    path: str | None = None,
    latest: bool = False,
) -> VideoDependencies:
    if source is None:
        kind = os.getenv("VISION_CORE_VIDEO_SOURCE", "rtsp").strip().lower()
        if kind == "file":
            selected_path = path or os.getenv("VISION_CORE_VIDEO_PATH", "")
            if not selected_path:
                raise ConfigurationError(
                    "Configura VISION_CORE_VIDEO_PATH para el adaptador file",
                    context={"variable": "VISION_CORE_VIDEO_PATH"},
                )
            source = FileVideoSource(selected_path)
        elif kind == "rtsp":
            source = RtspVideoSource.from_env()
        else:
            raise ConfigurationError(
                "VISION_CORE_VIDEO_SOURCE debe ser rtsp o file",
                context={"variable": "VISION_CORE_VIDEO_SOURCE"},
            )
    if latest:
        source = LatestFrameSource(source)
    return VideoDependencies(
        open_video=OpenVideo(source),
        read_frame_use_case=ReadFrame(source),
        close_video=CloseVideo(source),
        source=source,
    )
