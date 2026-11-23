"""Validación de la configuración de sinks y del flag MQTT."""

import pytest

from vision_core.core.config import Settings, SettingsError
from vision_core.core.config.event_sink_settings import EventSinkSettings
from vision_core.core.errors import ConfigurationError
from vision_core.features.events.infrastructure.adapters.mqtt_event_sink import MqttEventSink
from vision_core.features.events.infrastructure.dependencies import build_event_sink


def test_defaults_disable_sinks():
    settings = EventSinkSettings()
    assert settings.backend == "none"
    assert settings.tls_verify is True
    assert settings.overflow_policy == "drop-oldest"
    assert build_event_sink(settings) is None


def test_webhook_headers_are_parsed_from_json():
    settings = EventSinkSettings.from_env(
        {
            "VISION_CORE_EVENT_SINK_BACKEND": "webhook",
            "VISION_CORE_EVENT_SINK_WEBHOOK_URL": "http://127.0.0.1:8080/hook",
            "VISION_CORE_EVENT_SINK_HEADERS": '{"Authorization": "Bearer token"}',
        }
    )
    assert settings.headers == {"Authorization": "Bearer token"}
    assert "token" not in repr(settings)


def test_webhook_url_with_credentials_is_rejected_without_echoing_value():
    with pytest.raises(SettingsError) as excinfo:
        EventSinkSettings.from_env(
            {
                "VISION_CORE_EVENT_SINK_BACKEND": "webhook",
                "VISION_CORE_EVENT_SINK_WEBHOOK_URL": "https://user:supersecret@example.com/hook",
            }
        )
    assert "supersecret" not in str(excinfo.value)


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
