from ..dto.request.request_read_frame import RequestReadFrame
from ..dto.response.response_read_frame import ResponseReadFrame
from ..mappers.video_mapper import frame_to_dto
from ...domain.ports.video_source import VideoSource


class ReadFrame:
    def __init__(self, source: VideoSource) -> None:
        self._source = source

    def execute(self, request: RequestReadFrame) -> ResponseReadFrame:
        return frame_to_dto(self._source.read_frame())
