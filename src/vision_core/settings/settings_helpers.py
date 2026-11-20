import os
import re
from urllib.parse import urlsplit


def valid_rtsp_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in {"rtsp", "rtsps"}:
            return False
        if not parsed.hostname or " " in value:
            return False
        port = parsed.port  # ValueError si el puerto no es numerico
        if port is not None and not 1 <= port <= 65535:
            return False
        return True
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
        if parsed.scheme not in {"http", "https", "rtsp", "rtsps"}:
            return text
        username = parsed.username or ""
        password = parsed.password or ""
        if not username and not password:
            return text
        host = parsed.hostname or ""
        try:
            if parsed.port is not None:
                host = f"{host}:{parsed.port}"
        except ValueError:
            pass  # puerto invalido: se omite el puerto pero se siguen redactando credenciales
        user_part = f"{username}:" if (username or password) else ""
        netloc = f"{user_part}***@{host}"
        return parsed._replace(netloc=netloc).geturl()
    except ValueError:
        return text


def apply_ffmpeg_capture_options(options: str) -> None:
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = options


def environment_with_relay_camera(relay_url: str) -> dict[str, str]:
    environment = dict(os.environ)
    environment["FRIGATE_CAMERA_RTSP_URL"] = relay_url
    return environment
