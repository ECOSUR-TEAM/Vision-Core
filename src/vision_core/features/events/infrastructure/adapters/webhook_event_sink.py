"""Adaptador webhook: POST del payload canónico con idempotencia y TLS."""

import ipaddress
import socket
import ssl
import warnings
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import SplitResult, urlsplit
from urllib.request import HTTPHandler, HTTPSHandler, Request, build_opener

from vision_core.core.config.event_sink_settings import EventSinkSettings, is_non_public_ip, is_webhook_url_allowed
from vision_core.core.dto.event_envelope import EventEnvelope
from vision_core.core.errors import ConfigurationError, PipelineError, ValidationError
from vision_core.core.serialization.serialization import dumps_json
from vision_core.features.events.infrastructure.adapters.no_redirect_handler import NoRedirectHandler
from vision_core.features.events.infrastructure.adapters.pinned_http_connection import PinnedHTTPConnection
from vision_core.features.events.infrastructure.adapters.pinned_https_connection import PinnedHTTPSConnection

_CLIENT = "vision-core/0.1.0"
_RETRYABLE_STATUSES = frozenset({408, 429})


def _pinned_http_connection(pinned_ip: str, port: int, host_header: str) -> type[PinnedHTTPConnection]:
    class _Connection(PinnedHTTPConnection):
        pass

    _Connection.pinned_ip = pinned_ip
    _Connection.port = port
    _Connection.host_header = host_header
    return _Connection


def _pinned_https_connection(pinned_ip: str, port: int, host_header: str, sni_host: str) -> type[PinnedHTTPSConnection]:
    class _Connection(PinnedHTTPSConnection):
        pass

    _Connection.pinned_ip = pinned_ip
    _Connection.port = port
    _Connection.host_header = host_header
    _Connection.sni_host = sni_host
    return _Connection


class WebhookEventSink:
    """Destino HTTP; nunca registra la URL ni los valores de los headers."""

    def __init__(self, settings: EventSinkSettings) -> None:
        if not settings.webhook_url:
            raise ConfigurationError("VISION_CORE_EVENT_SINK_WEBHOOK_URL: requerida para backend=webhook")
        if not is_webhook_url_allowed(settings.webhook_url, allow_private_hosts=settings.allow_private_hosts):
            raise ConfigurationError("VISION_CORE_EVENT_SINK_WEBHOOK_URL: destino no permitido")
        if not settings.tls_verify:
            warnings.warn(
                "VISION_CORE_EVENT_SINK_TLS_VERIFY=0 desactiva la verificación de certificado y hostname",
                RuntimeWarning,
                stacklevel=2,
            )
        self._url = settings.webhook_url
        self._timeout = settings.timeout_seconds
        self._headers = dict(settings.headers)
        self._allow_private_hosts = settings.allow_private_hosts
        context = ssl.create_default_context()
        if not settings.tls_verify:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        self._context = context

    def send(self, envelope: EventEnvelope) -> None:
        parsed = urlsplit(self._url)
        pinned_ip = self._resolve_pinned_ip(parsed)
        opener = self._build_opener(parsed, pinned_ip)
        body = dumps_json(envelope.payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": _CLIENT,
            **self._headers,
            "Idempotency-Key": envelope.event_id,
        }
        request = Request(self._url, data=body, headers=headers, method="POST")
        try:
            with opener.open(request, timeout=self._timeout) as response:
                status = int(getattr(response, "status", 200))
        except HTTPError as error:
            status = int(error.code)
            error.close()
        except (URLError, TimeoutError, socket.timeout, OSError):
            raise PipelineError(
                "No se pudo entregar el evento al webhook",
                retryable=True,
                context={"transport": "webhook"},
            ) from None

        if 200 <= status < 300:
            return
        if status >= 500 or status in _RETRYABLE_STATUSES:
            raise PipelineError(
                "El webhook respondió con un error temporal",
                retryable=True,
                context={"status": status},
            ) from None
        raise ValidationError(
            "El webhook rechazó el evento",
            retryable=False,
            context={"status": status},
        ) from None

    def _resolve_pinned_ip(self, parsed: SplitResult) -> str:
        host = parsed.hostname or ""
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        try:
            resolved = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except (OSError, UnicodeError):
            raise PipelineError(
                "No se pudo resolver el destino del webhook",
                retryable=True,
                context={"transport": "webhook"},
            ) from None
        if not resolved:
            raise PipelineError(
                "No se pudo resolver el destino del webhook",
                retryable=True,
                context={"transport": "webhook"},
            ) from None
        addresses: list[str] = []
        for info in resolved:
            try:
                address = ipaddress.ip_address(info[4][0])
            except ValueError:
                raise ConfigurationError("El destino del webhook resuelve a una dirección no válida") from None
            if not self._allow_private_hosts and is_non_public_ip(str(address)):
                raise ConfigurationError("El destino del webhook resuelve a una dirección no pública")
            addresses.append(str(address))
        return addresses[0]

    def _build_opener(self, parsed: SplitResult, pinned_ip: str) -> Any:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        host_header = parsed.netloc
        handlers: list[Any] = [NoRedirectHandler()]
        if parsed.scheme == "https":
            https_connection = _pinned_https_connection(pinned_ip, port, host_header, parsed.hostname or "")

            class _PinnedHTTPSHandler(HTTPSHandler):
                https_connection: type[PinnedHTTPSConnection]

            _PinnedHTTPSHandler.https_connection = https_connection
            handlers.append(_PinnedHTTPSHandler(context=self._context))
        else:
            http_connection = _pinned_http_connection(pinned_ip, port, host_header)

            class _PinnedHTTPHandler(HTTPHandler):
                http_connection: type[PinnedHTTPConnection]

            _PinnedHTTPHandler.http_connection = http_connection
            handlers.append(_PinnedHTTPHandler())
        return build_opener(*handlers)

    def close(self) -> None:
        return None
