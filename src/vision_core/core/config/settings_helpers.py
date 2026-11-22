import ipaddress
import os
import re
from urllib.parse import urlsplit

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off"})
_HOST_LABEL = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")


def parse_bool(name: str, value: str | None, default: bool) -> bool | None:
    if value is None or not value.strip():
        return default
    normalized = value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    return None


def normalize_monitor_host(value: object) -> str:
    if value is None:
        raise ValueError("host inválido")
    host = str(value).strip()
    if host in {"", "0"}:
        return "0.0.0.0"
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        pass
    if len(host) > 253 or any(character.isspace() for character in host):
        raise ValueError("host inválido")
    if not all(_HOST_LABEL.fullmatch(label) for label in host.split(".")):
        raise ValueError("host inválido")
    return host


def is_exposed_monitor_host(value: object) -> bool:
    host = normalize_monitor_host(value)
    try:
        return ipaddress.ip_address(host).is_unspecified
    except ValueError:
        return False


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
