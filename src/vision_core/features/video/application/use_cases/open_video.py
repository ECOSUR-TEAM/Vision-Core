from ..dto.request.request_open_video import RequestOpenVideo
from ..dto.response.response_open_video import ResponseOpenVideo
from ...domain.ports.video_source import VideoSource


class OpenVideo:
    def __init__(self, source: VideoSource) -> None:
        self._source = source

    def execute(self, request: RequestOpenVideo) -> ResponseOpenVideo:
        self._source.open()
        return ResponseOpenVideo(opened=True)
