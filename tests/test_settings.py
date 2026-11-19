from pathlib import Path

import pytest

from vision_core.settings import Settings, SettingsError, redact_sensitive

MODEL = str(Path("yolov8n.pt").resolve())


def complete_env(**overrides):
    env = {
        "VISION_CORE_RTSP_URL": "rtsp://localhost:8554/entrada",
        "VISION_CORE_MODEL_PATH": MODEL,
    }
    env.update(overrides)
    return env


def test_settings_defaults(monkeypatch):
    settings = Settings.from_env(
        complete_env(),
        validate_startup=True,
    )
    assert settings.video.open_timeout_ms == 5000
    assert settings.video.transport == "tcp"
    assert settings.detection.confidence == 0.5
    assert settings.reid.ttl_seconds == 0
    assert settings.monitor.port == 8080
    assert settings.zones.confirmation_frames == 3


def test_settings_overrides():
    settings = Settings.from_env(
        complete_env(
            VISION_CORE_RTSP_TRANSPORT="udp",
            VISION_CORE_RECONNECT_ATTEMPTS="9",
            VISION_CORE_REID_THRESHOLD="0.91",
            VISION_CORE_MONITOR_PORT="9090",
        )
    )
    assert settings.video.transport == "udp"
    assert settings.video.reconnect_attempts == 9
    assert settings.reid.threshold == 0.91
    assert settings.monitor.port == 9090


@pytest.mark.parametrize(
    "variable,value",
    [
        ("VISION_CORE_RTSP_URL", "http://localhost/entrada"),
        ("VISION_CORE_OPEN_TIMEOUT_MS", "-1"),
        ("VISION_CORE_RECONNECT_DELAY_SECONDS", "not-a-number"),
        ("VISION_CORE_DETECTION_CONFIDENCE", "2"),
        ("VISION_CORE_REID_THRESHOLD", "-0.1"),
        ("VISION_CORE_MONITOR_PORT", "70000"),
    ],
)
def test_settings_reports_invalid_values(variable, value):
    with pytest.raises(SettingsError) as exc:
        Settings.from_env(complete_env(**{variable: value}))
    message = str(exc.value)
    assert "Configuración inválida" in message
    assert variable in message


def test_settings_lists_missing_required_value():
    with pytest.raises(SettingsError) as exc:
        Settings.from_env({"VISION_CORE_MODEL_PATH": MODEL})
    assert "VISION_CORE_RTSP_URL" in str(exc.value)


def test_zones_path_is_validated_when_calibration_is_enabled(tmp_path):
    missing = tmp_path / "missing.json"
    with pytest.raises(SettingsError) as exc:
        Settings.from_env(
            complete_env(
                VISION_CORE_ZONES_FILE=str(missing),
                VISION_CORE_MONITOR_UNCALIBRATED="0",
                VISION_CORE_MONITOR_DEMO_ZONES="0",
            )
        )
    assert "VISION_CORE_ZONES_FILE" in str(exc.value)


def test_secret_redaction():
    assert redact_sensitive("rtsp://admin:password@camera.local/live") == "rtsp://admin:***@camera.local/live"
