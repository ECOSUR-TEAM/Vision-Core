"""Éxito, idempotencia, reintentos, dead-letter y backpressure del despachante."""

import threading

import pytest

from tests.fakes.fake_event_sink import FakeEventSink
from tests.features.events.support import make_envelope, wait_until
from vision_core.core.config.event_sink_settings import EventSinkSettings
from vision_core.core.errors import PipelineError, codes
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
        assert dispatcher._retry_delay(5) <= dispatcher._settings.retry_max_seconds
    finally:
        dispatcher.close()


def test_retry_delay_respects_cap_after_jitter():
    dispatcher = EventSinkDispatcher(
        FakeEventSink(),
        _settings(retry_base_seconds=0.2, retry_max_seconds=0.25, retry_jitter=1.0),
        sleep=lambda _seconds: None,
        jitter=lambda: 1.0,
    )
    try:
        assert dispatcher._retry_delay(5) == 0.25
    finally:
        dispatcher.close()


def test_dead_letter_releases_key_for_producer_retry():
    destination = FakeEventSink(fail_times=1)
    dispatcher = _dispatcher(destination, max_attempts=1)
    try:
        dispatcher.send(make_envelope("dlq-retry"))
        wait_until(lambda: len(dispatcher.dead_letters()) == 1)
        dispatcher.send(make_envelope("dlq-retry"))
        wait_until(lambda: destination.calls == 2)
        assert [item.event_id for item in destination.envelopes] == ["dlq-retry", "dlq-retry"]
        assert len(dispatcher.dead_letters()) == 1
    finally:
        dispatcher.close()


def test_dropped_event_can_be_retried_by_producer():
    block = threading.Event()
    entered = threading.Event()
    destination = FakeEventSink(block=block, entered=entered)
    dispatcher = _dispatcher(destination, queue_size=1, max_attempts=1)
    try:
        dispatcher.send(make_envelope("first"))
        wait_until(entered.is_set)
        dispatcher.send(make_envelope("dropped"))
        dispatcher.send(make_envelope("other"))
        block.set()
        wait_until(lambda: len(destination.envelopes) == 2)
        assert [item.event_id for item in destination.envelopes] == ["first", "other"]
        dispatcher.send(make_envelope("dropped"))
        wait_until(lambda: len(destination.envelopes) == 3)
        assert [item.event_id for item in destination.envelopes] == ["first", "other", "dropped"]
    finally:
        block.set()
        dispatcher.close()


def test_send_after_close_is_dropped_without_enqueueing():
    destination = FakeEventSink()
    metrics = ObservabilityMetrics()
    dispatcher = _dispatcher(destination, metrics=metrics)
    dispatcher.close()
    dispatcher.send(make_envelope("late"))
    assert destination.calls == 0
    assert dispatcher.queue_depth() == 0
    assert metrics.snapshot()["counters"]["vision_core_event_sink_dropped_total"] == 1


def test_close_counts_undelivered_events_and_closes_destination_after_worker():
    class BlockingSink:
        def __init__(self, block: threading.Event, entered: threading.Event) -> None:
            self._block = block
            self._entered = entered
            self.calls = 0
            self.closed = False
            self.closed_during_send = False
            self.envelopes: list = []

        def send(self, envelope) -> None:
            self.closed_during_send = self.closed_during_send or self.closed
            self._entered.set()
            self._block.wait(timeout=5)
            self.calls += 1
            self.envelopes.append(envelope)
            if self.calls == 1:
                raise PipelineError("Fallo temporal", code=codes.PIPELINE_FAILED, retryable=True)

        def close(self) -> None:
            self.closed = True

    block = threading.Event()
    entered = threading.Event()
    destination = BlockingSink(block, entered)
    metrics = ObservabilityMetrics()
    dispatcher = EventSinkDispatcher(destination, _settings(max_attempts=2), metrics=metrics, sleep=lambda _: None)
    closer = threading.Thread(target=dispatcher.close)
    try:
        dispatcher.send(make_envelope("in-flight"))
        wait_until(entered.is_set)
        dispatcher.send(make_envelope("queued"))
        closer.start()
        wait_until(dispatcher._interrupt.is_set)
        block.set()
        closer.join(timeout=3)
        assert not closer.is_alive()
        assert destination.calls == 2
        assert destination.closed is True
        assert destination.closed_during_send is False
        counters = metrics.snapshot()["counters"]
        assert counters.get("vision_core_event_sink_dropped_total", 0) == 1
        assert counters.get("vision_core_event_sink_delivered_total", 0) == 1
    finally:
        block.set()
        if closer.is_alive():
            closer.join(timeout=3)
