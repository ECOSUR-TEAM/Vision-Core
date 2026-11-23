"""Conexión HTTPS fijada a una IP validada con SNI original."""

import http.client
from collections.abc import Mapping
from typing import Any


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    pinned_ip: str
    port: int
    host_header: str
    sni_host: str

    def __init__(self, _host: str, timeout: float | None = None, **kwargs: Any) -> None:
        super().__init__(self.pinned_ip, self.port, timeout=timeout, **kwargs)

    def connect(self) -> None:
        http.client.HTTPConnection.connect(self)
        tunnel_host = getattr(self, "_tunnel_host", None)
        server_hostname = tunnel_host or self.sni_host
        context = getattr(self, "_context")
        self.sock = context.wrap_socket(self.sock, server_hostname=server_hostname)

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
