from ...domain.ports.video_source import VideoSource
from ..dto.request.request_close_video import RequestCloseVideo
from ..dto.response.response_close_video import ResponseCloseVideo


class CloseVideo:
    def __init__(self, source: VideoSource) -> None:
        self._source = source

    def execute(self, request: RequestCloseVideo) -> ResponseCloseVideo:
        self._source.close()
        return ResponseCloseVideo(closed=True)
