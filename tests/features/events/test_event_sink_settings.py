"""Validación de la configuración de sinks, host permitido y flag MQTT."""

import logging

import pytest

from vision_core.core.config import Settings, SettingsError
from vision_core.core.config.event_sink_settings import (
    EventSinkSettings,
    is_non_public_ip,
    is_webhook_url_allowed,
)
from vision_core.core.errors import ConfigurationError
from vision_core.features.events.infrastructure.adapters.mqtt_event_sink import MqttEventSink
from vision_core.features.events.infrastructure.dependencies import build_event_sink

_WEBHOOK = "VISION_CORE_EVENT_SINK_WEBHOOK_URL"


def _env(**overrides) -> dict[str, str]:
    env = {
        "VISION_CORE_EVENT_SINK_BACKEND": "webhook",
        _WEBHOOK: "https://hooks.example.com/events",
    }
    env.update(overrides)
    return env


def test_defaults_disable_sinks():
    settings = EventSinkSettings()
    assert settings.backend == "none"
    assert settings.tls_verify is True
    assert settings.allow_private_hosts is False
    assert settings.overflow_policy == "drop-oldest"
    assert build_event_sink(settings) is None


def test_webhook_headers_are_parsed_from_json():
    headers = '{"Authorization": "Bearer token"}'
    settings = EventSinkSettings.from_env(_env(**{"VISION_CORE_EVENT_SINK_HEADERS": headers}))
    assert settings.headers == {"Authorization": "Bearer token"}
    assert "token" not in repr(settings)


def test_blank_values_keep_defaults():
    settings = EventSinkSettings.from_env(
        _env(
            VISION_CORE_EVENT_SINK_QUEUE_SIZE="  ",
            VISION_CORE_EVENT_SINK_TIMEOUT_SECONDS="",
            VISION_CORE_EVENT_SINK_TLS_VERIFY=" ",
        )
    )
    assert settings.queue_size == 256
    assert settings.timeout_seconds == 2.0
    assert settings.tls_verify is True


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("VISION_CORE_EVENT_SINK_QUEUE_SIZE", "many"),
        ("VISION_CORE_EVENT_SINK_TIMEOUT_SECONDS", "soon"),
        ("VISION_CORE_EVENT_SINK_TLS_VERIFY", "maybe"),
    ],
)
def test_non_numeric_or_boolean_values_are_rejected(name, value):
    with pytest.raises(SettingsError, match=name):
        EventSinkSettings.from_env(_env(**{name: value}))


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("VISION_CORE_EVENT_SINK_QUEUE_SIZE", "0"),
        ("VISION_CORE_EVENT_SINK_OVERFLOW_POLICY", "drop-random"),
        ("VISION_CORE_EVENT_SINK_MAX_ATTEMPTS", "0"),
        ("VISION_CORE_EVENT_SINK_RETRY_BASE_SECONDS", "-1"),
        ("VISION_CORE_EVENT_SINK_RETRY_BASE_SECONDS", "inf"),
        ("VISION_CORE_EVENT_SINK_RETRY_MAX_SECONDS", "0"),
        ("VISION_CORE_EVENT_SINK_RETRY_MAX_SECONDS", "nan"),
        ("VISION_CORE_EVENT_SINK_RETRY_JITTER", "-0.1"),
        ("VISION_CORE_EVENT_SINK_RETRY_JITTER", "1.1"),
        ("VISION_CORE_EVENT_SINK_RETRY_JITTER", "inf"),
        ("VISION_CORE_EVENT_SINK_TIMEOUT_SECONDS", "0"),
        ("VISION_CORE_EVENT_SINK_TIMEOUT_SECONDS", "inf"),
        ("VISION_CORE_EVENT_SINK_TIMEOUT_SECONDS", "31"),
        ("VISION_CORE_EVENT_SINK_DEDUPE_SIZE", "0"),
        ("VISION_CORE_EVENT_SINK_DEAD_LETTER_SIZE", "0"),
        ("VISION_CORE_EVENT_SINK_MQTT_PORT", "0"),
        ("VISION_CORE_EVENT_SINK_MQTT_PORT", "70000"),
        ("VISION_CORE_EVENT_SINK_MQTT_QOS", "3"),
    ],
)
def test_out_of_range_numeric_settings_are_rejected(name, value):
    with pytest.raises(SettingsError, match=name):
        EventSinkSettings.from_env(_env(**{name: value}))


@pytest.mark.parametrize("invalid", ["not-json", "[1, 2]", '{"bad name": "value"}', '{"Name": 1}'])
def test_invalid_header_objects_are_rejected(invalid):
    with pytest.raises(SettingsError, match="VISION_CORE_EVENT_SINK_HEADERS"):
        EventSinkSettings.from_env(_env(**{"VISION_CORE_EVENT_SINK_HEADERS": invalid}))


def test_webhook_url_with_credentials_is_rejected_without_echoing_value():
    with pytest.raises(SettingsError) as excinfo:
        EventSinkSettings.from_env(_env(**{_WEBHOOK: "https://user:supersecret@example.com/hook"}))
    assert "supersecret" not in str(excinfo.value)


@pytest.mark.parametrize(
    "url",
    [
        "",
        "ftp://example.com/hook",
        "https:///hook",
        "https://example.com/a hook",
        "https://example.com:abc/hook",
        "https://example.com:0/hook",
        "http://[::1",
        "http://127.0.0.1:9000/hook",
        "http://169.254.169.254/latest/meta-data",
    ],
)
def test_webhook_url_must_be_public_http_without_credentials(url):
    with pytest.raises(SettingsError, match=_WEBHOOK):
        EventSinkSettings.from_env(_env(**{_WEBHOOK: url}))


def test_private_webhook_url_is_allowed_only_with_explicit_opt_in():
    private_url = "http://127.0.0.1:9000/hook"
    with pytest.raises(SettingsError, match=_WEBHOOK):
        EventSinkSettings.from_env(_env(**{_WEBHOOK: private_url}))
    allowed = EventSinkSettings.from_env(
        _env(
            **{
                _WEBHOOK: private_url,
                "VISION_CORE_EVENT_SINK_ALLOW_PRIVATE_HOSTS": "yes",
            }
        )
    )
    assert allowed.allow_private_hosts is True


def test_mqtt_backend_requires_host_and_topic():
    with pytest.raises(SettingsError, match="VISION_CORE_EVENT_SINK_MQTT_HOST"):
        EventSinkSettings.from_env(
            {
                "VISION_CORE_EVENT_SINK_BACKEND": "mqtt",
                "VISION_CORE_EVENT_SINK_MQTT_HOST": "broker",
            }
        )


def test_invalid_backend_is_rejected_by_global_settings():
    with pytest.raises(SettingsError, match="VISION_CORE_EVENT_SINK_BACKEND"):
        Settings.from_env({"VISION_CORE_EVENT_SINK_BACKEND": "carrier-pigeon"}, validate_startup=False)


def test_mqtt_backend_fails_closed_without_dependency():
    settings = EventSinkSettings(backend="mqtt", mqtt_host="broker", mqtt_topic="events/v1")
    with pytest.raises(ConfigurationError) as excinfo:
        build_event_sink(settings)
    assert excinfo.value.code == "CONFIGURATION_INVALID"
    with pytest.raises(ConfigurationError):
        MqttEventSink(settings)


def test_tls_opt_out_logs_warning(caplog):
    caplog.set_level(logging.WARNING)
    settings = EventSinkSettings.from_env(_env(**{"VISION_CORE_EVENT_SINK_TLS_VERIFY": "0"}))
    assert settings.tls_verify is False
    assert "VISION_CORE_EVENT_SINK_TLS_VERIFY=0" in caplog.text


@pytest.mark.parametrize("host", ["8.8.8.8", "docs.example.com", "not-an-ip"])
def test_non_public_ip_returns_false_for_public_or_hostname(host):
    assert is_non_public_ip(host) is False


@pytest.mark.parametrize(
    "host",
    [
        "10.0.0.1",
        "100.64.0.1",
        "127.0.0.1",
        "169.254.169.254",
        "192.168.1.1",
        "::1",
        "fe80::1",
        "224.0.0.1",
        "0.0.0.0",
    ],
)
def test_non_public_ip_detects_private_ranges(host):
    assert is_non_public_ip(host) is True


def test_webhook_url_helper_supports_private_opt_in():
    url = "http://127.0.0.1:9000/hook"
    assert is_webhook_url_allowed(url) is False
    assert is_webhook_url_allowed(url, allow_private_hosts=True) is True
    assert is_webhook_url_allowed("http://100.64.0.1/hook") is False
    assert is_webhook_url_allowed("https://hooks.example.com/hook") is True
