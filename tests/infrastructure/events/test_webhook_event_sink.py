"""Entrega webhook real contra servidor local: éxito, timeout, 5xx y secretos."""

import logging
from contextlib import contextmanager

import pytest

from tests.features.events.support import make_envelope, wait_until
from tests.infrastructure.events.webhook_test_support import start_recording_server, stop_recording_server
from vision_core.core.config.event_sink_settings import EventSinkSettings
from vision_core.core.errors import PipelineError, codes
from vision_core.features.events.application.use_cases.dispatch_events import EventSinkDispatcher
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
