"""Configuración tipada y validada de los sinks de eventos (ECM-102)."""

import ipaddress
import json
import logging
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from math import isfinite
from urllib.parse import urlsplit

from vision_core.core.config.settings_error import SettingsError
from vision_core.core.config.settings_helpers import parse_bool

_HEADER_NAME = re.compile(r"^[A-Za-z0-9!#$%&'*+.^_`|~-]+$")
_BACKENDS = frozenset({"none", "webhook", "mqtt"})
_OVERFLOW_POLICIES = frozenset({"drop-oldest", "drop-newest"})
_MAX_TIMEOUT_SECONDS = 30.0
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class EventSinkSettings:
    backend: str = "none"
    queue_size: int = 256
    overflow_policy: str = "drop-oldest"
    max_attempts: int = 3
    retry_base_seconds: float = 0.2
    retry_max_seconds: float = 5.0
    retry_jitter: float = 0.2
    timeout_seconds: float = 2.0
    dedupe_size: int = 4096
    dead_letter_size: int = 128
    tls_verify: bool = True
    allow_private_hosts: bool = False
    webhook_url: str = field(default="", repr=False)
    headers: Mapping[str, str] = field(default_factory=dict, repr=False)
    mqtt_host: str = ""
    mqtt_port: int = 1883
    mqtt_topic: str = ""
    mqtt_qos: int = 0

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "EventSinkSettings":
        env = os.environ if environ is None else environ
        errors: list[str] = []

        def integer(name: str, default: int) -> int:
            raw = env.get(name)
            if raw is None or raw.strip() == "":
                return default
            try:
                return int(raw)
            except ValueError:
                errors.append(f"{name}: debe ser un entero")
                return default

        def floating(name: str, default: float) -> float:
            raw = env.get(name)
            if raw is None or raw.strip() == "":
                return default
            try:
                return float(raw)
            except ValueError:
                errors.append(f"{name}: debe ser un número")
                return default

        def boolean(name: str, default: bool) -> bool:
            parsed = parse_bool(name, env.get(name), default)
            if parsed is None:
                errors.append(f"{name}: debe ser 1/0, true/false, yes/no u on/off")
                return default
            return parsed

        backend = env.get("VISION_CORE_EVENT_SINK_BACKEND", "none").strip().lower()
        queue_size = integer("VISION_CORE_EVENT_SINK_QUEUE_SIZE", 256)
        overflow_policy = env.get("VISION_CORE_EVENT_SINK_OVERFLOW_POLICY", "drop-oldest").strip().lower()
        max_attempts = integer("VISION_CORE_EVENT_SINK_MAX_ATTEMPTS", 3)
        retry_base = floating("VISION_CORE_EVENT_SINK_RETRY_BASE_SECONDS", 0.2)
        retry_max = floating("VISION_CORE_EVENT_SINK_RETRY_MAX_SECONDS", 5.0)
        jitter = floating("VISION_CORE_EVENT_SINK_RETRY_JITTER", 0.2)
        timeout = floating("VISION_CORE_EVENT_SINK_TIMEOUT_SECONDS", 2.0)
        dedupe_size = integer("VISION_CORE_EVENT_SINK_DEDUPE_SIZE", 4096)
        dead_letter_size = integer("VISION_CORE_EVENT_SINK_DEAD_LETTER_SIZE", 128)
        tls_verify = boolean("VISION_CORE_EVENT_SINK_TLS_VERIFY", True)
        allow_private_hosts = boolean("VISION_CORE_EVENT_SINK_ALLOW_PRIVATE_HOSTS", False)
        webhook_url = env.get("VISION_CORE_EVENT_SINK_WEBHOOK_URL", "").strip()
        headers = _headers_from_env(env.get("VISION_CORE_EVENT_SINK_HEADERS", ""), errors)
        mqtt_host = env.get("VISION_CORE_EVENT_SINK_MQTT_HOST", "").strip()
        mqtt_port = integer("VISION_CORE_EVENT_SINK_MQTT_PORT", 1883)
        mqtt_topic = env.get("VISION_CORE_EVENT_SINK_MQTT_TOPIC", "").strip()
        mqtt_qos = integer("VISION_CORE_EVENT_SINK_MQTT_QOS", 0)

        if backend not in _BACKENDS:
            errors.append("VISION_CORE_EVENT_SINK_BACKEND: use none, webhook o mqtt")
        if queue_size < 1:
            errors.append("VISION_CORE_EVENT_SINK_QUEUE_SIZE: debe ser mayor que 0")
        if overflow_policy not in _OVERFLOW_POLICIES:
            errors.append("VISION_CORE_EVENT_SINK_OVERFLOW_POLICY: use drop-oldest o drop-newest")
        if max_attempts < 1:
            errors.append("VISION_CORE_EVENT_SINK_MAX_ATTEMPTS: debe ser mayor que 0")
        if not isfinite(retry_base) or retry_base < 0:
            errors.append("VISION_CORE_EVENT_SINK_RETRY_BASE_SECONDS: debe ser finito y no negativo")
        if not isfinite(retry_max) or retry_max < retry_base:
            errors.append("VISION_CORE_EVENT_SINK_RETRY_MAX_SECONDS: debe ser finito y >= base")
        if not isfinite(jitter) or not 0 <= jitter <= 1:
            errors.append("VISION_CORE_EVENT_SINK_RETRY_JITTER: debe estar entre 0 y 1")
        if not isfinite(timeout) or timeout <= 0:
            errors.append("VISION_CORE_EVENT_SINK_TIMEOUT_SECONDS: debe ser mayor que 0")
        if isfinite(timeout) and timeout > _MAX_TIMEOUT_SECONDS:
            errors.append(f"VISION_CORE_EVENT_SINK_TIMEOUT_SECONDS: no puede superar {_MAX_TIMEOUT_SECONDS:g}")
        if dedupe_size < 1:
            errors.append("VISION_CORE_EVENT_SINK_DEDUPE_SIZE: debe ser mayor que 0")
        if dead_letter_size < 1:
            errors.append("VISION_CORE_EVENT_SINK_DEAD_LETTER_SIZE: debe ser mayor que 0")
        if backend == "webhook" and not is_webhook_url_allowed(webhook_url, allow_private_hosts=allow_private_hosts):
            errors.append(
                "VISION_CORE_EVENT_SINK_WEBHOOK_URL: requerida, http(s):// sin credenciales y con host público "
                "(ALLOW_PRIVATE_HOSTS=1 solo en desarrollo)"
            )
        if backend == "mqtt" and (not mqtt_host or not mqtt_topic):
            errors.append("VISION_CORE_EVENT_SINK_MQTT_HOST y _TOPIC: requeridos para backend=mqtt")
        if not 1 <= mqtt_port <= 65535:
            errors.append("VISION_CORE_EVENT_SINK_MQTT_PORT: debe estar entre 1 y 65535")
        if mqtt_qos not in {0, 1, 2}:
            errors.append("VISION_CORE_EVENT_SINK_MQTT_QOS: use 0, 1 o 2")

        if errors:
            raise SettingsError("Configuración de sinks inválida:\n- " + "\n- ".join(errors))

        if not tls_verify:
            logger.warning(
                "VISION_CORE_EVENT_SINK_TLS_VERIFY=0 desactiva la verificación TLS; usar solo en entornos controlados"
            )

        return cls(
            backend=backend,
            queue_size=queue_size,
            overflow_policy=overflow_policy,
            max_attempts=max_attempts,
            retry_base_seconds=retry_base,
            retry_max_seconds=retry_max,
            retry_jitter=jitter,
            timeout_seconds=timeout,
            dedupe_size=dedupe_size,
            dead_letter_size=dead_letter_size,
            tls_verify=tls_verify,
            allow_private_hosts=allow_private_hosts,
            webhook_url=webhook_url,
            headers=headers,
            mqtt_host=mqtt_host,
            mqtt_port=mqtt_port,
            mqtt_topic=mqtt_topic,
            mqtt_qos=mqtt_qos,
        )


def _headers_from_env(raw: str, errors: list[str]) -> Mapping[str, str]:
    if not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        errors.append("VISION_CORE_EVENT_SINK_HEADERS: debe ser un objeto JSON")
        return {}
    if not isinstance(parsed, dict):
        errors.append("VISION_CORE_EVENT_SINK_HEADERS: debe ser un objeto JSON")
        return {}
    headers: dict[str, str] = {}
    for name, value in parsed.items():
        if not isinstance(name, str) or not _HEADER_NAME.fullmatch(name) or not isinstance(value, str):
            errors.append("VISION_CORE_EVENT_SINK_HEADERS: nombres y valores deben ser texto válido")
            continue
        headers[name] = value
    return headers


def is_non_public_ip(value: str) -> bool:
    """True para IPs literales que no deben ser destinos de un webhook."""
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    return any(
        (
            not address.is_global,
            address.is_private,
            address.is_loopback,
            address.is_link_local,
            address.is_multicast,
            address.is_unspecified,
            address.is_reserved,
        )
    )


def is_webhook_url_allowed(value: str, *, allow_private_hosts: bool = False) -> bool:
    """Valida sintaxis y, salvo opt-in explícito, rechaza hosts IP no públicos."""
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    if parsed.username or parsed.password or any(character.isspace() for character in value):
        return False
    try:
        port = parsed.port
    except ValueError:
        return False
    if port is not None and not 1 <= port <= 65535:
        return False
    if allow_private_hosts:
        return True
    return not is_non_public_ip(parsed.hostname)
