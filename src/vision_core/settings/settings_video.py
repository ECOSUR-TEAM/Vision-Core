from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class VideoSettings:
    source: str
    rtsp_url: str | None
    video_path: Path | None
    transport: str
    open_timeout_ms: int
    read_timeout_ms: int
    reconnect_attempts: int
    reconnect_delay_seconds: float
    decoder_threads: int
    ffmpeg_capture_options: str | None
