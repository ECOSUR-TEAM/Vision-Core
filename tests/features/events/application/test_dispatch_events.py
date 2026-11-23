"""Éxito, idempotencia, reintentos, dead-letter y backpressure del despachante."""

import threading

import pytest

from tests.fakes.fake_event_sink import FakeEventSink
from tests.features.events.support import make_envelope, wait_until
from vision_core.core.config.event_sink_settings import EventSinkSettings
from vision_core.core.errors import codes
from vision_core.core.telemetry.metrics import ObservabilityMetrics
from vision_core.features.events.application.use_cases.dispatch_events import EventSinkDispatcher


def _settings(**overrides) -> EventSinkSettings:
    defaults = {
        "queue_size": 8,
        "max_attempts": 3,
        "retry_base_seconds": 0.001,
        "retry_max_seconds": 0.001,
        "retry_jitter": 0.0,
    }
    defaults.update(overrides)
    return EventSinkSettings(**defaults)


def _dispatcher(destination: FakeEventSink, *, metrics=None, **overrides) -> EventSinkDispatcher:
    return EventSinkDispatcher(
        destination,
        _settings(**overrides),
        metrics=metrics,
        sleep=lambda _seconds: None,
        jitter=lambda: 0.5,
    )


def test_success_delivers_envelope_unchanged():
    destination = FakeEventSink()
    dispatcher = _dispatcher(destination)
    envelope = make_envelope()
    try:
        dispatcher.send(envelope)
        wait_until(lambda: destination.calls == 1)
        assert destination.envelopes == [envelope]
    finally:
        dispatcher.close()


def test_close_drains_pending_events():
    destination = FakeEventSink()
    dispatcher = EventSinkDispatcher(destination, _settings(queue_size=4))
    dispatcher.send(make_envelope("first"))
    dispatcher.send(make_envelope("second"))
    dispatcher.close()
    assert [item.event_id for item in destination.envelopes] == ["first", "second"]


def test_retried_counter_counts_only_actual_retries():
    destination = FakeEventSink(fail_times=1)
    metrics = ObservabilityMetrics()
    dispatcher = _dispatcher(destination, max_attempts=3, metrics=metrics)
    try:
        dispatcher.send(make_envelope("metric"))
        wait_until(lambda: metrics.snapshot()["counters"].get("vision_core_event_sink_delivered_total") == 1)
        counters = metrics.snapshot()["counters"]
        assert counters["vision_core_event_sink_retried_total"] == 1
        assert counters["vision_core_event_sink_delivered_total"] == 1
        assert counters.get("vision_core_event_sink_dead_letter_total", 0) == 0
    finally:
        dispatcher.close()


def test_duplicate_event_id_is_delivered_once():
    destination = FakeEventSink()
    dispatcher = _dispatcher(destination)
    envelope = make_envelope("dup")
    try:
        dispatcher.send(envelope)
        wait_until(lambda: destination.calls == 1)
        dispatcher.send(envelope)
        dispatcher.send(make_envelope("dup"))
        wait_until(lambda: dispatcher.queue_depth() == 0)
        assert destination.calls == 1
    finally:
        dispatcher.close()


def test_retry_succeeds_after_transient_failure():
    destination = FakeEventSink(fail_times=1)
    dispatcher = _dispatcher(destination, max_attempts=3)
    try:
        dispatcher.send(make_envelope("retry"))
        wait_until(lambda: destination.calls >= 2)
        assert destination.calls == 2
        assert dispatcher.dead_letters() == ()
    finally:
        dispatcher.close()


def test_dead_letter_after_limited_attempts():
    destination = FakeEventSink(fail_times=99)
    dispatcher = _dispatcher(destination, max_attempts=2)
    try:
        dispatcher.send(make_envelope("dlq"))
        wait_until(lambda: len(dispatcher.dead_letters()) == 1)
        assert destination.calls == 2
        assert dispatcher.dead_letters()[0][1] == codes.PIPELINE_FAILED
    finally:
        dispatcher.close()


def test_non_retryable_failure_does_not_retry():
    destination = FakeEventSink(fail_times=99, fail_with="permanent")
    dispatcher = _dispatcher(destination, max_attempts=3)
    try:
        dispatcher.send(make_envelope("bad-request"))
        wait_until(lambda: len(dispatcher.dead_letters()) == 1)
        assert destination.calls == 1
        assert dispatcher.dead_letters()[0][1] == codes.VALIDATION_FAILED
    finally:
        dispatcher.close()


def test_full_queue_drops_oldest_without_blocking():
    block = threading.Event()
    entered = threading.Event()
    destination = FakeEventSink(block=block, entered=entered)
    metrics = ObservabilityMetrics()
    dispatcher = _dispatcher(destination, queue_size=1, max_attempts=1, metrics=metrics)
    try:
        dispatcher.send(make_envelope("first"))
        wait_until(entered.is_set)
        dispatcher.send(make_envelope("second"))
        dispatcher.send(make_envelope("third"))
        block.set()
        wait_until(lambda: len(destination.envelopes) == 2)
        assert [item.event_id for item in destination.envelopes] == ["first", "third"]
        counters = metrics.snapshot()["counters"]
        assert counters["vision_core_event_sink_dropped_total"] == 1
    finally:
        block.set()
        dispatcher.close()


def test_full_queue_drop_newest_keeps_older_envelope():
    block = threading.Event()
    entered = threading.Event()
    destination = FakeEventSink(block=block, entered=entered)
    dispatcher = _dispatcher(
        destination,
        queue_size=1,
        max_attempts=1,
        overflow_policy="drop-newest",
    )
    try:
        dispatcher.send(make_envelope("first"))
        wait_until(entered.is_set)
        dispatcher.send(make_envelope("second"))
        dispatcher.send(make_envelope("third"))
        block.set()
        wait_until(lambda: len(destination.envelopes) == 2)
        assert [item.event_id for item in destination.envelopes] == ["first", "second"]
    finally:
        block.set()
        dispatcher.close()


def test_dead_letter_callback_is_invoked():
    seen = []
    destination = FakeEventSink(fail_times=99)
    dispatcher = EventSinkDispatcher(
        destination,
        _settings(max_attempts=1),
        on_dead_letter=lambda envelope, code: seen.append((envelope.event_id, code)),
        sleep=lambda _seconds: None,
    )
    try:
        dispatcher.send(make_envelope("callback"))
        wait_until(lambda: len(seen) == 1)
        assert seen[0][0] == "callback"
    finally:
        dispatcher.close()


@pytest.mark.parametrize("jitter_value", [0.0, 0.25, 1.0])
def test_retry_delay_is_non_negative_for_all_jitter_values(jitter_value):
    destination = FakeEventSink()
    dispatcher = _dispatcher(destination, retry_base_seconds=0.2, retry_jitter=jitter_value)
    try:
        assert dispatcher._retry_delay(1) >= 0
        assert dispatcher._retry_delay(5) <= 0.2 * (1 + jitter_value)
    finally:
        dispatcher.close()
