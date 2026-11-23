"""Conexión HTTP fijada a una IP validada."""

import http.client
from collections.abc import Mapping
from typing import Any


class PinnedHTTPConnection(http.client.HTTPConnection):
    pinned_ip: str
    port: int
    host_header: str

    def __init__(self, _host: str, timeout: float | None = None, **kwargs: Any) -> None:
        super().__init__(self.pinned_ip, self.port, timeout=timeout, **kwargs)

    def request(
        self,
        method: str,
        url: str,
        body: Any = None,
        headers: Mapping[str, str] | None = None,
        *,
        encode_chunked: bool = False,
    ) -> None:
        request_headers = dict(headers or {})
        request_headers.setdefault("Host", self.host_header)
        super().request(method, url, body, request_headers, encode_chunked=encode_chunked)
