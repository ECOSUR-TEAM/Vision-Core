from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CameraSettings:
    rtsp_url: str | None
