"""Entrega webhook real contra servidor local: éxito, timeout, 5xx y secretos."""

import http.client
import logging
import socket
import ssl
from contextlib import contextmanager

import pytest

from tests.features.events.support import make_envelope, wait_until
from tests.infrastructure.events.webhook_test_support import start_recording_server, stop_recording_server
from vision_core.core.config.event_sink_settings import EventSinkSettings
from vision_core.core.errors import ConfigurationError, PipelineError, codes
from vision_core.features.events.application.use_cases.dispatch_events import EventSinkDispatcher
from vision_core.features.events.infrastructure.adapters import webhook_event_sink as webhook_module
from vision_core.features.events.infrastructure.adapters.webhook_event_sink import WebhookEventSink


@contextmanager
def recording_server(**state):
    server, thread = start_recording_server(**state)
    try:
        yield server
    finally:
        stop_recording_server(server, thread)


def settings_for(server, **overrides) -> EventSinkSettings:
    defaults = {
        "backend": "webhook",
        "webhook_url": f"http://127.0.0.1:{server.server_port}/hook",
        "timeout_seconds": 0.5,
        "max_attempts": 3,
        "retry_base_seconds": 0.001,
        "retry_max_seconds": 0.001,
        "retry_jitter": 0.0,
        "allow_private_hosts": True,
    }
    defaults.update(overrides)
    return EventSinkSettings(**defaults)


def header(request, name: str) -> str | None:
    return next((value for key, value in request["headers"].items() if key.lower() == name.lower()), None)


def test_webhook_success_sends_payload_and_idempotency_key():
    with recording_server() as server:
        sink = WebhookEventSink(settings_for(server, headers={"Authorization": "Bearer supersecret"}))
        sink.send(make_envelope("ok"))
        requests = server.state["requests"]
        assert len(requests) == 1
        assert requests[0]["path"] == "/hook"
        assert requests[0]["body"]["event"] == "PERSON_ENTERED"
        assert header(requests[0], "Idempotency-Key") == "ok"
        assert header(requests[0], "Authorization") == "Bearer supersecret"


def test_configured_headers_cannot_override_idempotency_key():
    with recording_server() as server:
        sink = WebhookEventSink(settings_for(server, headers={"Idempotency-Key": "forged"}))
        sink.send(make_envelope("real"))
        assert header(server.state["requests"][0], "Idempotency-Key") == "real"


def test_webhook_timeout_is_retryable_and_does_not_leak_url():
    with recording_server(delay=0.25) as server:
        sink = WebhookEventSink(
            settings_for(server, headers={"Authorization": "Bearer supersecret"}, timeout_seconds=0.02)
        )
        with pytest.raises(PipelineError) as excinfo:
            sink.send(make_envelope("timeout"))
        assert excinfo.value.code == codes.PIPELINE_FAILED
        assert excinfo.value.retryable is True
        assert "supersecret" not in str(excinfo.value)
        assert str(server.server_port) not in str(excinfo.value)


def test_webhook_5xx_is_retried_with_same_key():
    with recording_server(fail_times=1) as server:
        settings = settings_for(server)
        dispatcher = EventSinkDispatcher(
            WebhookEventSink(settings),
            settings,
            sleep=lambda _seconds: None,
        )
        try:
            dispatcher.send(make_envelope("retry-5xx"))
            wait_until(lambda: len(server.state["requests"]) == 2)
            keys = [header(request, "Idempotency-Key") for request in server.state["requests"]]
            assert keys == ["retry-5xx", "retry-5xx"]
            assert dispatcher.dead_letters() == ()
        finally:
            dispatcher.close()


def test_webhook_4xx_does_not_retry_and_reaches_dead_letter():
    with recording_server(permanent_status=400) as server:
        settings = settings_for(server, max_attempts=3)
        dispatcher = EventSinkDispatcher(
            WebhookEventSink(settings),
            settings,
            sleep=lambda _seconds: None,
        )
        try:
            dispatcher.send(make_envelope("bad-request"))
            wait_until(lambda: len(dispatcher.dead_letters()) == 1)
            assert len(server.state["requests"]) == 1
            assert dispatcher.dead_letters()[0][1] == codes.VALIDATION_FAILED
        finally:
            dispatcher.close()


def test_webhook_failures_never_log_secrets_or_endpoint(caplog):
    caplog.set_level(logging.WARNING)
    with recording_server(permanent_status=500) as server:
        settings = settings_for(server, headers={"Authorization": "Bearer supersecret"}, max_attempts=1)
        dispatcher = EventSinkDispatcher(
            WebhookEventSink(settings),
            settings,
            sleep=lambda _seconds: None,
        )
        try:
            dispatcher.send(make_envelope("secret-log"))
            wait_until(lambda: len(dispatcher.dead_letters()) == 1)
            assert "supersecret" not in caplog.text
            assert "127.0.0.1" not in caplog.text
            assert "/hook" not in caplog.text
        finally:
            dispatcher.close()


def test_redirect_is_rejected_without_retrying_or_forwarding_headers():
    with recording_server(redirect_to="http://127.0.0.2:9/steal") as server:
        settings = settings_for(server, headers={"Authorization": "Bearer supersecret"})
        dispatcher = EventSinkDispatcher(WebhookEventSink(settings), settings, sleep=lambda _seconds: None)
        try:
            dispatcher.send(make_envelope("redirect"))
            wait_until(lambda: len(dispatcher.dead_letters()) == 1)
            assert len(server.state["requests"]) == 1
            assert dispatcher.dead_letters()[0][1] == codes.VALIDATION_FAILED
        finally:
            dispatcher.close()


@pytest.mark.parametrize("statuses", [[429, 200], [408, 200]])
def test_request_limiting_and_request_timeout_are_retried(statuses):
    with recording_server(statuses=statuses) as server:
        settings = settings_for(server)
        dispatcher = EventSinkDispatcher(WebhookEventSink(settings), settings, sleep=lambda _seconds: None)
        try:
            dispatcher.send(make_envelope("retry-status"))
            wait_until(lambda: len(server.state["requests"]) == 2)
            assert [header(request, "Idempotency-Key") for request in server.state["requests"]] == [
                "retry-status",
                "retry-status",
            ]
            assert dispatcher.dead_letters() == ()
        finally:
            dispatcher.close()


def test_tls_opt_out_emits_warning():
    with recording_server() as server:
        with pytest.warns(RuntimeWarning, match="TLS"):
            WebhookEventSink(settings_for(server, tls_verify=False))


def test_adapter_rejects_private_literal_url():
    settings = EventSinkSettings(webhook_url="http://127.0.0.1:9/hook")
    with pytest.raises(ConfigurationError):
        WebhookEventSink(settings)


def test_adapter_rejects_public_host_resolving_to_private_address(monkeypatch):
    monkeypatch.setattr(
        webhook_module.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", 443))],
    )
    settings = EventSinkSettings(webhook_url="https://public.example/hook")
    sink = WebhookEventSink(settings)
    with pytest.raises(ConfigurationError):
        sink.send(make_envelope("dns-private"))


def test_adapter_marks_dns_failure_retryable(monkeypatch):
    def fail(*_args, **_kwargs):
        raise socket.gaierror("resolution failed")

    monkeypatch.setattr(webhook_module.socket, "getaddrinfo", fail)
    sink = WebhookEventSink(EventSinkSettings(webhook_url="https://public.example/hook"))
    with pytest.raises(PipelineError) as excinfo:
        sink.send(make_envelope("dns-failure"))
    assert excinfo.value.retryable is True


def test_adapter_pins_the_single_validated_dns_answer(monkeypatch):
    responses = [
        [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))],
        [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))],
    ]
    calls = []

    def resolve(*_args, **_kwargs):
        calls.append(True)
        return responses.pop(0)

    monkeypatch.setattr(webhook_module.socket, "getaddrinfo", resolve)
    sink = WebhookEventSink(EventSinkSettings(webhook_url="https://public.example/hook"))
    assert sink._resolve_pinned_ip(webhook_module.urlsplit(sink._url)) == "8.8.8.8"
    assert len(calls) == 1


def test_adapter_send_uses_pinned_ip(monkeypatch):
    captured = {}

    def fake_build_opener(_self, _parsed, pinned_ip):
        captured["pinned_ip"] = pinned_ip
        raise RuntimeError("opener detenido")

    monkeypatch.setattr(WebhookEventSink, "_build_opener", fake_build_opener)
    monkeypatch.setattr(
        webhook_module.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))],
    )
    sink = WebhookEventSink(EventSinkSettings(webhook_url="https://public.example/hook"))
    with pytest.raises(RuntimeError):
        sink.send(make_envelope("pinned"))
    assert captured["pinned_ip"] == "8.8.8.8"


def test_adapter_rejects_cgnat_dns_answer(monkeypatch):
    monkeypatch.setattr(
        webhook_module.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("100.64.0.1", 443))],
    )
    sink = WebhookEventSink(EventSinkSettings(webhook_url="https://public.example/hook"))
    with pytest.raises(ConfigurationError):
        sink.send(make_envelope("cgnat"))


def test_pinned_https_connection_keeps_original_sni(monkeypatch):
    captured = {}

    def fake_wrap_socket(_self, sock, **kwargs):
        captured["sni"] = kwargs["server_hostname"]
        return sock

    monkeypatch.setattr(http.client.HTTPConnection, "connect", lambda _self: None)
    monkeypatch.setattr(ssl.SSLContext, "wrap_socket", fake_wrap_socket)
    connection_class = webhook_module._pinned_https_connection("8.8.8.8", 443, "public.example:443", "public.example")
    connection = connection_class("ignored", timeout=0.1)
    connection.sock = socket.socket()
    try:
        connection.connect()
    finally:
        connection.close()
    assert captured["sni"] == "public.example"
