"""Manejador urllib que bloquea redirecciones HTTP en los webhooks."""

from typing import NoReturn
from urllib.request import HTTPRedirectHandler, Request

from vision_core.core.errors import ValidationError


class NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req: Request, fp: object, code: int, msg: str, headers: object, newurl: str) -> NoReturn:
        raise ValidationError(
            "El webhook respondió con una redirección no permitida",
            retryable=False,
            context={"status": code},
        ) from None
