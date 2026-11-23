"""Adaptador webhook: POST del payload canónico con idempotencia y TLS."""

import ipaddress
import socket
import ssl
import warnings
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPSHandler, Request, build_opener

from vision_core.core.config.event_sink_settings import EventSinkSettings, is_non_public_ip, is_webhook_url_allowed
from vision_core.core.dto.event_envelope import EventEnvelope
from vision_core.core.errors import ConfigurationError, PipelineError, ValidationError
from vision_core.core.serialization.serialization import dumps_json
from vision_core.features.events.infrastructure.adapters.no_redirect_handler import NoRedirectHandler

_CLIENT = "vision-core/0.1.0"
_RETRYABLE_STATUSES = frozenset({408, 429})


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
        self._opener = build_opener(NoRedirectHandler(), HTTPSHandler(context=context))

    def send(self, envelope: EventEnvelope) -> None:
        self._validate_resolved_host()
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
            with self._opener.open(request, timeout=self._timeout) as response:
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

    def _validate_resolved_host(self) -> None:
        if self._allow_private_hosts:
            return
        parsed = urlsplit(self._url)
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
        for info in resolved:
            try:
                address = ipaddress.ip_address(info[4][0])
            except ValueError:
                raise ConfigurationError("El destino del webhook resuelve a una dirección no válida") from None
            if is_non_public_ip(str(address)):
                raise ConfigurationError("El destino del webhook resuelve a una dirección no pública")

    def close(self) -> None:
        return None
