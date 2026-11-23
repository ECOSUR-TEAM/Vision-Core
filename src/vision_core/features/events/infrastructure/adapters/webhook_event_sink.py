"""Adaptador webhook: POST del payload canónico con idempotencia y TLS."""

import socket
import ssl
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from vision_core.core.config.event_sink_settings import EventSinkSettings
from vision_core.core.dto.event_envelope import EventEnvelope
from vision_core.core.errors import ConfigurationError, PipelineError, ValidationError
from vision_core.core.serialization.serialization import dumps_json

_CLIENT = "vision-core/0.1.0"


class WebhookEventSink:
    """Destino HTTP; nunca registra la URL ni los valores de los headers."""

    def __init__(self, settings: EventSinkSettings) -> None:
        if not settings.webhook_url:
            raise ConfigurationError("VISION_CORE_EVENT_SINK_WEBHOOK_URL: requerida para backend=webhook")
        self._url = settings.webhook_url
        self._timeout = settings.timeout_seconds
        self._headers = dict(settings.headers)
        context = ssl.create_default_context()
        if not settings.tls_verify:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        self._context = context

    def send(self, envelope: EventEnvelope) -> None:
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
            with urlopen(request, timeout=self._timeout, context=self._context) as response:
                status = int(getattr(response, "status", 200))
        except HTTPError as error:
            status = int(error.code)
        except (URLError, TimeoutError, socket.timeout, OSError):
            raise PipelineError(
                "No se pudo entregar el evento al webhook",
                retryable=True,
                context={"transport": "webhook"},
            ) from None

        if 200 <= status < 300:
            return
        if status >= 500:
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

    def close(self) -> None:
        return None
