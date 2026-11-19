import os
import re
from urllib.parse import urlsplit


def valid_rtsp_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        return parsed.scheme in {"rtsp", "rtsps"} and bool(parsed.hostname)
    except ValueError:
        return False


def redact_sensitive(value: object) -> str:
    text = str(value)
    text = re.sub(
        r"(rtsps?://[^:/\s]+):[^@\s]+@",
        r"\1:***@",
        text,
        flags=re.IGNORECASE,
    )
    try:
        parsed = urlsplit(text)
        if parsed.scheme in {"rtsp", "rtsps"} and parsed.username:
            host = parsed.hostname or ""
            if parsed.port is not None:
                host = f"{host}:{parsed.port}"
            return parsed._replace(netloc=f"{parsed.username}:***@{host}").geturl()
    except ValueError:
        pass
    return text


def apply_ffmpeg_capture_options(options: str) -> None:
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = options


def environment_with_relay_camera(relay_url: str) -> dict[str, str]:
    environment = dict(os.environ)
    environment["FRIGATE_CAMERA_RTSP_URL"] = relay_url
    return environment
